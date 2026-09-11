'use client'

/**
 * Trình mô phỏng & chấm điểm bài nộp
 * Kaggle: "Biohub - Cell Tracking During Development"
 *
 * Mô phỏng một mẫu dữ liệu kính hiển vi 3D+time (phôi zebrafish, 60 khung hình):
 * - Lớp ground-truth (GT): tế bào thật + đồ thị node/cạnh + 6 phân bào, gắn nhãn thưa
 * - Lớp dự đoán: sinh từ "thuật toán" giả lập (nearest-neighbor tracker) với tham số
 *   tùy chỉnh: recall, node giả (FP), nhiễu định vị, ngưỡng liên kết, phát hiện phân bào
 * - Chấm điểm đúng tinh thần metric cuộc thi:
 *   + Ghép node tối ưu (Hungarian) trong ngưỡng 7.0 µm theo khoảng cách vật lý
 *   + Cạnh TP / FP / FN, Edge Jaccard điều chỉnh (phạt node dự đoán thừa)
 *   + Division Jaccard (phân bào TP/FP/FN)
 *   + score = adj_edge_jaccard + 0.1 × division_jaccard (có thể vượt 1.0)
 *
 * Toàn bộ dữ liệu sinh bằng PRNG có seed (mulberry32) → tái lập được.
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import {
  Activity,
  CircleDot,
  Crosshair,
  Dices,
  Gauge,
  GitBranch,
  Microscope,
  Pause,
  Play,
  RotateCcw,
  Spline,
  Target,
  Wand2,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardAction,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Progress } from '@/components/ui/progress'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

// ---------------------------------------------------------------------------
// Hằng số mô phỏng (gần dữ liệu thật: (T,Z,Y,X)=(100,64,256,256)·uint16)
// ---------------------------------------------------------------------------

const T = 60
const LAST_FRAME = T - 1

/** Trường nhìn 2D (µm) — phép chiếu max-projection của khối dữ liệu */
const WORLD_W = 160
const WORLD_H = 90

/** Tốc độ phát cơ bản (khung hình/giây ở 1×) */
const BASE_FPS = 2.5

/** Thời gian mô phỏng: 2.5 hpf + 1.5 phút/khung hình */
const MPF_BASE = 150
const MPF_PER_FRAME = 1.5

/** Ngưỡng ghép node tối đa của metric cuộc thi (µm) */
const MATCH_UM = 7.0

/** Thang vật lý trục z (µm/voxel) — xy đã tính trực tiếp bằng µm */
const Z_UM_PER_VOXEL = 1.625

/** Các khung hình có phân bào */
const DIV_FRAMES = [12, 19, 26, 35, 42, 50]

// ---------------------------------------------------------------------------
// PRNG & tiện ích
// ---------------------------------------------------------------------------

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function gauss(rng: () => number): number {
  const u1 = Math.max(1e-9, rng())
  const u2 = rng()
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
}

const clamp = (v: number, lo: number, hi: number): number =>
  Math.min(hi, Math.max(lo, v))
const lerp = (a: number, b: number, t: number): number => a + (b - a) * t

/** Khoảng cách vật lý 3D giữa 2 điểm (xy µm, z theo voxel) */
const dist3 = (
  ax: number, ay: number, az: number,
  bx: number, by: number, bz: number,
): number => Math.hypot(ax - bx, ay - by, Z_UM_PER_VOXEL * (az - bz))

// ---------------------------------------------------------------------------
// Mô phỏng sinh học (ground truth)
// ---------------------------------------------------------------------------

interface FrameState {
  x: number; y: number; z: number
  r: number; i: number
  labeled: boolean
}

interface Track {
  id: number
  start: number
  end: number
  frames: FrameState[]
  parent: number | null
  divisionFrame: number | null
}

interface Division {
  mother: number
  frame: number
  daughters: [number, number]
}

interface SimData {
  tracks: Track[]
  byId: Map<number, Track>
  divisions: Division[]
  meanIntensity: number[]
}

interface RtState {
  pos: [number, number, number]
  vel: [number, number, number]
  rB: number
  iB: number
}

function buildSimulation(seed: number): SimData {
  const rng = mulberry32(seed)
  const tracks: Track[] = []
  const rt = new Map<number, RtState>()
  const divisions: Division[] = []
  let nextId = 1

  const newTrack = (start: number, pos: [number, number, number]): Track => {
    const tr: Track = {
      id: nextId++,
      start,
      end: LAST_FRAME,
      frames: [],
      parent: null,
      divisionFrame: null,
    }
    tracks.push(tr)
    rt.set(tr.id, {
      pos,
      vel: [0, 0, 0],
      rB: 1.9 + rng() * 1.3,
      iB: 700 + rng() * 2500,
    })
    return tr
  }

  // 26 tế bào ban đầu
  for (let k = 0; k < 26; k++) {
    newTrack(0, [
      14 + rng() * (WORLD_W - 28),
      12 + rng() * (WORLD_H - 24),
      4 + rng() * 56,
    ])
  }
  // 3 tế bào đi vào trường nhìn giữa phim
  newTrack(14, [6, 10 + rng() * (WORLD_H - 20), 3 + rng() * 56])
  newTrack(27, [WORLD_W - 6, 10 + rng() * (WORLD_H - 20), 3 + rng() * 56])
  newTrack(41, [20 + rng() * (WORLD_W - 40), WORLD_H - 6, 3 + rng() * 56])

  // lên lịch 6 phân bào: chọn mẹ hợp lệ, cắt track mẹ tại khung phân bào
  for (const d of DIV_FRAMES) {
    const elig = tracks.filter(
      (tr) =>
        tr.start <= d - 2 &&
        tr.end === LAST_FRAME &&
        tr.divisionFrame === null &&
        !(tr.parent !== null && d - tr.start < 8),
    )
    if (elig.length === 0) continue
    const mother = elig[Math.floor(rng() * elig.length)]
    mother.end = d
    mother.divisionFrame = d
    const dA = nextId++
    const dB = nextId++
    for (const cid of [dA, dB]) {
      tracks.push({
        id: cid,
        start: d + 1,
        end: LAST_FRAME,
        frames: [],
        parent: mother.id,
        divisionFrame: null,
      })
      rt.set(cid, { pos: [0, 0, 0], vel: [0, 0, 0], rB: 1.2, iB: 800 })
    }
    divisions.push({ mother: mother.id, frame: d, daughters: [dA, dB] })
  }

  const pending = new Map<number, Division>()
  for (const dv of divisions) pending.set(dv.frame, dv)

  // mô phỏng từng khung hình
  const swirlA = rng() * Math.PI * 2
  const intensitySum: number[] = new Array<number>(T).fill(0)

  for (let t = 0; t < T; t++) {
    for (const tr of tracks) {
      if (tr.start > t || tr.end < t) continue
      const s = rt.get(tr.id)
      if (s === undefined) continue

      if (t > tr.start) {
        // dòng chảy xoáy của phôi + random walk có damping
        const dx = s.pos[0] - WORLD_W / 2
        const dy = s.pos[1] - WORLD_H / 2
        const dC = Math.hypot(dx, dy) + 1e-6
        const ph = swirlA + t * 0.012
        const fx = (-dy / dC) * 0.32 + Math.cos(ph) * 0.1
        const fy = (dx / dC) * 0.32 + Math.sin(ph) * 0.1
        s.vel[0] = s.vel[0] * 0.86 + (fx + (rng() - 0.5) * 0.55) * 0.5
        s.vel[1] = s.vel[1] * 0.86 + (fy + (rng() - 0.5) * 0.55) * 0.5
        s.vel[2] = s.vel[2] * 0.9 + (rng() - 0.5) * 0.9
        s.pos[0] = clamp(s.pos[0] + s.vel[0], 5, WORLD_W - 5)
        s.pos[1] = clamp(s.pos[1] + s.vel[1], 5, WORLD_H - 5)
        s.pos[2] = clamp(s.pos[2] + s.vel[2], 2.5, 60.5)
      }

      const swell =
        tr.divisionFrame !== null && t >= tr.divisionFrame - 4
          ? 1 + 0.3 * ((t - (tr.divisionFrame - 4)) / 4)
          : 1
      const grow =
        tr.parent !== null
          ? 0.72 + 0.28 * clamp((t - tr.start) / 8, 0, 1)
          : 1

      tr.frames.push({
        x: s.pos[0],
        y: s.pos[1],
        z: s.pos[2],
        r: s.rB * swell * grow,
        i: Math.round(s.iB * (0.85 + rng() * 0.3)),
        labeled: true,
      })
      intensitySum[t] += s.iB
    }

    // xử lý phân bào tại khung t: đặt vị trí 2 con quanh mẹ
    const dv = pending.get(t)
    if (dv !== undefined) {
      const mother = tracks.find((x) => x.id === dv.mother)
      const ms = mother !== undefined ? rt.get(mother.id) : undefined
      if (mother !== undefined && ms !== undefined && mother.frames.length > 0) {
        const ang = rng() * Math.PI * 2
        const off = 2.2 + rng() * 1.8
        for (const [cid, sgn] of [
          [dv.daughters[0], 1],
          [dv.daughters[1], -1],
        ] as const) {
          const cs = rt.get(cid)
          if (cs !== undefined) {
            cs.pos = [
              ms.pos[0] + Math.cos(ang) * off * sgn,
              ms.pos[1] + Math.sin(ang) * off * sgn,
              ms.pos[2],
            ]
            cs.vel = [Math.cos(ang) * 0.5 * sgn, Math.sin(ang) * 0.5 * sgn, 0]
            cs.rB = ms.rB * 0.75
            cs.iB = ms.iB * (0.9 + rng() * 0.2)
          }
        }
      }
    }
  }

  // gắn nhãn thưa (~88%): đục "cửa sổ mờ" 2–7 khung, luôn bảo vệ vùng phân bào
  const holeRng = mulberry32(seed ^ 0x9e3779b9)
  for (const tr of tracks) {
    let i = 2 + Math.floor(holeRng() * 8)
    while (i < tr.frames.length) {
      const len = 2 + Math.floor(holeRng() * 5)
      for (let j = i; j < Math.min(i + len, tr.frames.length); j++) {
        tr.frames[j].labeled = false
      }
      i += len + 4 + Math.floor(holeRng() * 9)
    }
    if (tr.divisionFrame !== null) {
      for (
        let j = Math.max(0, tr.divisionFrame - 1 - tr.start);
        j <= tr.divisionFrame - tr.start;
        j++
      ) {
        tr.frames[j].labeled = true
      }
    }
    if (tr.parent !== null) {
      tr.frames[0].labeled = true
      if (tr.frames.length > 1) tr.frames[1].labeled = true
    }
  }

  const byId = new Map<number, Track>()
  for (const tr of tracks) byId.set(tr.id, tr)

  const meanIntensity: number[] = []
  for (let t = 0; t < T; t++) {
    const alive = tracks.filter((tr) => tr.start <= t && t <= tr.end).length
    meanIntensity.push(
      alive > 0
        ? Math.round(intensitySum[t] / alive + 1400 * Math.sin(t / 9))
        : 1500,
    )
  }

  return { tracks, byId, divisions, meanIntensity }
}

// ---------------------------------------------------------------------------
// "Thuật toán" giả lập: sinh phát hiện (detection) từ tham số
// ---------------------------------------------------------------------------

interface Det {
  x: number; y: number; z: number
  r: number; i: number
  src: number | null // track nguồn (null = node giả)
}

interface Params {
  recall: number
  fpRate: number
  jitter: number
  linkUm: number
  division: boolean
}

const DEFAULT_PARAMS: Params = {
  recall: 0.92,
  fpRate: 0.02,
  jitter: 0.7,
  linkUm: 8,
  division: true,
}

const PRESETS: { name: string; p: Params }[] = [
  { name: 'Mặc định', p: DEFAULT_PARAMS },
  {
    name: 'Lý tưởng',
    p: { recall: 1, fpRate: 0, jitter: 0, linkUm: 8, division: true },
  },
  {
    name: 'Thiếu phát hiện',
    p: { recall: 0.72, fpRate: 0.02, jitter: 0.7, linkUm: 8, division: true },
  },
  {
    name: 'Nhiễu cao',
    p: { recall: 0.92, fpRate: 0.02, jitter: 3.2, linkUm: 8, division: true },
  },
  {
    name: 'Liên kết lỏng',
    p: { recall: 0.92, fpRate: 0.02, jitter: 0.7, linkUm: 14, division: true },
  },
  {
    name: 'Bỏ phân bào',
    p: { recall: 0.92, fpRate: 0.02, jitter: 0.7, linkUm: 8, division: false },
  },
]

function genDetections(sim: SimData, p: Params, seed: number): Det[][] {
  const rng = mulberry32(seed ^ 0x51ab3f)
  const out: Det[][] = []
  for (let t = 0; t < T; t++) {
    const dets: Det[] = []
    for (const tr of sim.tracks) {
      if (tr.start > t || tr.end < t) continue
      if (rng() > p.recall) continue
      const f = tr.frames[t - tr.start]
      dets.push({
        x: clamp(f.x + gauss(rng) * p.jitter, 3, WORLD_W - 3),
        y: clamp(f.y + gauss(rng) * p.jitter, 3, WORLD_H - 3),
        z: clamp(f.z + gauss(rng) * p.jitter * 0.5, 1, 62),
        r: f.r,
        i: f.i,
        src: tr.id,
      })
    }
    // node giả (false positive) rải ngẫu nhiên
    const nSpur = Math.round(dets.length * p.fpRate * (0.6 + rng() * 0.8))
    for (let k = 0; k < nSpur; k++) {
      dets.push({
        x: 8 + rng() * (WORLD_W - 16),
        y: 6 + rng() * (WORLD_H - 12),
        z: 2 + rng() * 58,
        r: 1.6 + rng() * 1.6,
        i: 500 + Math.round(rng() * 1500),
        src: null,
      })
    }
    out.push(dets)
  }
  return out
}

// ---------------------------------------------------------------------------
// Gán song phân tối ưu (Hungarian, O(n³)) — như metric cuộc thi
// ---------------------------------------------------------------------------

/** Trả về col gán cho mỗi row (hoặc null nếu chi phí >= BIG) */
function hungarian(cost: number[][]): (number | null)[] {
  const nRows = cost.length
  if (nRows === 0) return []
  const nCols = cost[0]?.length ?? 0
  if (nCols === 0) return new Array<number | null>(nRows).fill(null)
  const n = Math.max(nRows, nCols)
  const BIG = 1e9
  const INF = 1e18

  const a: number[][] = Array.from({ length: n + 1 }, () =>
    new Array<number>(n + 1).fill(BIG),
  )
  for (let i = 0; i < nRows; i++) {
    for (let j = 0; j < nCols; j++) a[i + 1][j + 1] = cost[i]![j]!
  }

  const u = new Array<number>(n + 1).fill(0)
  const v = new Array<number>(n + 1).fill(0)
  const p = new Array<number>(n + 1).fill(0)
  const way = new Array<number>(n + 1).fill(0)

  for (let i = 1; i <= n; i++) {
    p[0] = i
    let j0 = 0
    const minv = new Array<number>(n + 1).fill(INF)
    const used = new Array<boolean>(n + 1).fill(false)
    do {
      used[j0] = true
      const i0 = p[j0]!
      let delta = INF
      let j1 = 0
      for (let j = 1; j <= n; j++) {
        if (!used[j]) {
          const cur = a[i0]![j]! - u[i0]! - v[j]!
          if (cur < minv[j]!) {
            minv[j] = cur
            way[j] = j0
          }
          if (minv[j]! < delta) {
            delta = minv[j]!
            j1 = j
          }
        }
      }
      for (let j = 0; j <= n; j++) {
        if (used[j]) {
          u[p[j]!]! += delta
          v[j]! -= delta
        } else {
          minv[j]! -= delta
        }
      }
      j0 = j1
    } while (p[j0] !== 0)
    do {
      const j1 = way[j0]!
      p[j0] = p[j1]!
      j0 = j1
    } while (j0 !== 0)
  }

  const rowToCol: (number | null)[] = new Array<number | null>(nRows).fill(null)
  for (let j = 1; j <= n; j++) {
    const i = p[j]!
    if (i >= 1 && i <= nRows) {
      const c = a[i]![j]!
      if (c < BIG) rowToCol[i - 1] = j - 1
    }
  }
  return rowToCol
}

// ---------------------------------------------------------------------------
// Phân tích: đồ thị GT, đồ thị dự đoán, và metric
// ---------------------------------------------------------------------------

interface GtNode {
  key: string
  trackId: number
  t: number
  x: number; y: number; z: number
}

interface GtEdge {
  key: string
  t: number
  x1: number; y1: number
  x2: number; y2: number
}

type PredCls = 'matched' | 'neutral' | 'spurious'

interface PredNode {
  key: string
  t: number
  det: Det
  gtKey: string | null
  cls: PredCls
}

interface PredEdge {
  a: PredNode
  b: PredNode
  cls: 'tp' | 'fp' | 'neutral'
}

interface Metrics {
  gtNodes: number
  predNodes: number
  matchedPred: number
  matchedGT: number
  spurious: number
  nodeRecall: number
  tp: number
  fp: number
  fn: number
  adjEJ: number
  divTP: number
  divFP: number
  divFN: number
  divJ: number
  combined: number
}

interface Analysis {
  det: Det[][]
  nodes: PredNode[][]
  frames: {
    gtEdges: (GtEdge & { fn: boolean })[]
    predEdges: {
      x1: number; y1: number
      x2: number; y2: number
      cls: 'tp' | 'fp' | 'neutral'
    }[]
  }[]
  gtCountByFrame: number[]
  metrics: Metrics
}

function analyze(
  sim: SimData,
  p: Params,
  sparse: boolean,
  seed: number,
): Analysis {
  const labeledAt = (tr: Track, t: number): boolean => {
    if (t < tr.start || t > tr.end) return false
    return sparse ? tr.frames[t - tr.start]!.labeled : true
  }

  // ---- đồ thị GT ----
  const gtNodesByFrame: GtNode[][] = Array.from({ length: T }, () => [])
  const gtKeySet = new Set<string>()
  for (const tr of sim.tracks) {
    for (let t = tr.start; t <= tr.end; t++) {
      if (!labeledAt(tr, t)) continue
      const f = tr.frames[t - tr.start]!
      const key = `${tr.id}@${t}`
      gtNodesByFrame[t]!.push({ key, trackId: tr.id, t, x: f.x, y: f.y, z: f.z })
      gtKeySet.add(key)
    }
  }

  const gtEdges: GtEdge[] = []
  const gtEdgeSet = new Set<string>()
  for (const tr of sim.tracks) {
    for (let t = tr.start; t < tr.end; t++) {
      if (!labeledAt(tr, t) || !labeledAt(tr, t + 1)) continue
      const fa = tr.frames[t - tr.start]!
      const fb = tr.frames[t + 1 - tr.start]!
      const key = `${tr.id}@${t}=>${tr.id}@${t + 1}`
      gtEdges.push({ key, t, x1: fa.x, y1: fa.y, x2: fb.x, y2: fb.y })
      gtEdgeSet.add(key)
    }
  }
  for (const dv of sim.divisions) {
    const m = sim.byId.get(dv.mother)
    if (m === undefined || !labeledAt(m, dv.frame)) continue
    const mf = m.frames[dv.frame - m.start]!
    for (const did of dv.daughters) {
      const d = sim.byId.get(did)
      if (d === undefined || !labeledAt(d, dv.frame + 1)) continue
      const df = d.frames[0]!
      const key = `${m.id}@${dv.frame}=>${d.id}@${dv.frame + 1}`
      gtEdges.push({ key, t: dv.frame, x1: mf.x, y1: mf.y, x2: df.x, y2: df.y })
      gtEdgeSet.add(key)
    }
  }

  // ---- phát hiện + gán song phân theo ngưỡng 7.0 µm ----
  const det = genDetections(sim, p, seed)
  const nodes: PredNode[][] = []
  for (let t = 0; t < T; t++) {
    const dets = det[t]!
    const gts = gtNodesByFrame[t]!
    const cost = dets.map((d) =>
      gts.map((g) => {
        const dd = dist3(d.x, d.y, d.z, g.x, g.y, g.z)
        return dd <= MATCH_UM ? dd : 1e9
      }),
    )
    const assign = hungarian(cost)
    nodes[t] = dets.map((d, i): PredNode => {
      const col = assign[i]
      const gtKey =
        col !== null && dist3(d.x, d.y, d.z, gts[col]!.x, gts[col]!.y, gts[col]!.z) <= MATCH_UM
          ? gts[col]!.key
          : null
      let cls: PredCls = 'spurious'
      if (gtKey !== null) cls = 'matched'
      else if (d.src !== null && !gtKeySet.has(`${d.src}@${t}`)) cls = 'neutral'
      return { key: `${t}:${i}`, t, det: d, gtKey, cls }
    })
  }

  // ---- tracker nearest-neighbor (giả lập notebook getting-started) ----
  const predEdges: PredEdge[] = []
  const predEdgeKeySet = new Set<string>()
  const covered = new Set<string>()

  const addEdge = (a: PredNode, b: PredNode): void => {
    predEdgeKeySet.add(`${a.key}=>${b.key}`)
    let cls: 'tp' | 'fp' | 'neutral'
    if (a.cls === 'matched' && b.cls === 'matched') {
      const gk = `${a.gtKey}=>${b.gtKey}`
      if (gtEdgeSet.has(gk) && !covered.has(gk)) {
        cls = 'tp'
        covered.add(gk)
      } else {
        cls = 'fp'
      }
    } else if (a.cls === 'spurious' || b.cls === 'spurious') {
      cls = 'fp'
    } else {
      // chạm vùng GT thưa → metric "tính đến" nhãn thưa, bỏ qua
      cls = 'neutral'
    }
    predEdges.push({ a, b, cls })
  }

  for (let t = 0; t < T - 1; t++) {
    const A = nodes[t]!
    const B = nodes[t + 1]!
    const pairs: { ai: number; bi: number; d: number }[] = []
    for (let ai = 0; ai < A.length; ai++) {
      for (let bi = 0; bi < B.length; bi++) {
        const da = A[ai]!.det
        const db = B[bi]!.det
        const d = dist3(da.x, da.y, da.z, db.x, db.y, db.z)
        if (d <= p.linkUm) pairs.push({ ai, bi, d })
      }
    }
    pairs.sort((x, y) => x.d - y.d)
    const usedA = new Set<number>()
    const usedB = new Set<number>()
    const primary = new Map<number, number>()
    for (const pr of pairs) {
      if (usedA.has(pr.ai) || usedB.has(pr.bi)) continue
      usedA.add(pr.ai)
      usedB.add(pr.bi)
      primary.set(pr.ai, pr.bi)
      addEdge(A[pr.ai]!, B[pr.bi]!)
    }
    // phát hiện phân bào: cho phép 1 node nối thêm "con thứ 2" nằm gần
    if (p.division) {
      for (const [ai, bi1] of primary) {
        const da = A[ai]!.det
        const db1 = B[bi1]!.det
        for (let bi = 0; bi < B.length; bi++) {
          if (usedB.has(bi)) continue
          const db = B[bi]!.det
          const d2 = dist3(da.x, da.y, da.z, db.x, db.y, db.z)
          const d3 = dist3(db1.x, db1.y, db1.z, db.x, db.y, db.z)
          if (d2 <= p.linkUm && d3 <= p.linkUm) {
            usedB.add(bi)
            addEdge(A[ai]!, B[bi]!)
          }
        }
      }
    }
  }

  // ---- metric ----
  const gtNodeTotal = gtNodesByFrame.reduce((s, g) => s + g.length, 0)
  const matchedGTSet = new Set<string>()
  let spurious = 0
  let matchedPred = 0
  const predNodeTotal = nodes.reduce((s, f) => s + f.length, 0)
  for (const frameNodes of nodes) {
    for (const nd of frameNodes) {
      if (nd.cls === 'matched') {
        matchedPred++
        matchedGTSet.add(nd.gtKey!)
      } else if (nd.cls === 'spurious') {
        spurious++
      }
    }
  }

  const tp = covered.size
  const fp = predEdges.filter((e) => e.cls === 'fp').length
  const fn = gtEdges.length - tp
  const denomE = tp + fp + fn + spurious
  const adjEJ = denomE > 0 ? tp / denomE : 0

  // ---- phân bào ----
  let divTP = 0
  let divFP = 0
  const divTotal = sim.divisions.length
  for (const dv of sim.divisions) {
    const mKey = `${dv.mother}@${dv.frame}`
    const d1Key = `${dv.daughters[0]}@${dv.frame + 1}`
    const d2Key = `${dv.daughters[1]}@${dv.frame + 1}`
    const pm = nodes[dv.frame]!.find(
      (n) => n.cls === 'matched' && n.gtKey === mKey,
    )
    const pd1 = nodes[dv.frame + 1]!.find(
      (n) => n.cls === 'matched' && n.gtKey === d1Key,
    )
    const pd2 = nodes[dv.frame + 1]!.find(
      (n) => n.cls === 'matched' && n.gtKey === d2Key,
    )
    if (
      pm !== undefined &&
      pd1 !== undefined &&
      pd2 !== undefined &&
      predEdgeKeySet.has(`${pm.key}=>${pd1.key}`) &&
      predEdgeKeySet.has(`${pm.key}=>${pd2.key}`)
    ) {
      divTP++
    }
  }
  // phân bào giả: node dự đoán (đã khớp GT) có ≥ 2 cạnh đi ra nhưng GT không có
  for (const frameNodes of nodes) {
    for (const nd of frameNodes) {
      if (nd.cls !== 'matched') continue
      const outDeg = predEdges.filter(
        (e) => e.a === nd && e.b.cls === 'matched',
      ).length
      if (outDeg < 2) continue
      const gtTrackId = Number(nd.gtKey!.split('@')[0])
      const tr = Number.isFinite(gtTrackId) ? sim.byId.get(gtTrackId) : undefined
      const t = nd.t
      const gtOut =
        (tr !== undefined && t + 1 <= tr.end && labeledAt(tr, t + 1) ? 1 : 0) +
        (tr !== undefined && tr.divisionFrame === t ? 2 : 0)
      if (gtOut < 2) divFP++
    }
  }
  const divFN = divTotal - divTP
  const divDenom = divTP + divFP + divFN
  const divJ = divDenom > 0 ? divTP / divDenom : 0

  const metrics: Metrics = {
    gtNodes: gtNodeTotal,
    predNodes: predNodeTotal,
    matchedPred,
    matchedGT: matchedGTSet.size,
    spurious,
    nodeRecall: gtNodeTotal > 0 ? matchedGTSet.size / gtNodeTotal : 0,
    tp,
    fp,
    fn,
    adjEJ,
    divTP,
    divFP,
    divFN,
    divJ,
    combined: adjEJ + 0.1 * divJ,
  }

  // ---- dữ liệu vẽ theo khung ----
  const frames = Array.from({ length: T }, (_, t) => ({
    gtEdges: gtEdges
      .filter((e) => e.t === t)
      .map((e) => ({ ...e, fn: !covered.has(e.key) })),
    predEdges: predEdges
      .filter((e) => e.a.t === t)
      .map((e) => ({
        x1: e.a.det.x, y1: e.a.det.y,
        x2: e.b.det.x, y2: e.b.det.y,
        cls: e.cls,
      })),
  }))
  const gtCountByFrame = gtNodesByFrame.map((g) => g.length)

  return { det, nodes, frames, gtCountByFrame, metrics }
}

// ---------------------------------------------------------------------------
// nhiễu sensor (canvas pattern)
// ---------------------------------------------------------------------------

function createNoiseCanvas(): HTMLCanvasElement {
  const nc = document.createElement('canvas')
  nc.width = 128
  nc.height = 128
  const nctx = nc.getContext('2d')
  if (nctx !== null) {
    const img = nctx.createImageData(128, 128)
    const nrng = mulberry32(0x1234abcd)
    for (let k = 0; k < img.data.length; k += 4) {
      const val = 8 + Math.floor(nrng() * 14)
      img.data[k] = val
      img.data[k + 1] = val + 4
      img.data[k + 2] = val
      img.data[k + 3] = 255
    }
    nctx.putImageData(img, 0, 0)
  }
  return nc
}

// ---------------------------------------------------------------------------
// UI nhỏ: chip thống kê & thanh metric & thanh tham số
// ---------------------------------------------------------------------------

function StatChip({
  icon,
  label,
  value,
  tone,
}: {
  icon: ReactNode
  label: string
  value: string
  tone: 'emerald' | 'teal' | 'amber' | 'rose'
}) {
  const tones: Record<string, string> = {
    emerald: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    teal: 'border-teal-500/30 bg-teal-500/10 text-teal-700 dark:text-teal-300',
    amber: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    rose: 'border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-300',
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] font-semibold tabular-nums ${tones[tone]}`}
    >
      <span className="[&_svg]:size-3">{icon}</span>
      {label}: {value}
    </span>
  )
}

function MetricBar({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium">{label}</span>
        <span className="font-mono text-xs font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
          {value.toFixed(3)}
        </span>
      </div>
      <Progress
        value={clamp(value, 0, 1) * 100}
        className="h-2"
        aria-label={`${label}: ${(value * 100).toFixed(1)}%`}
      />
    </div>
  )
}

function ParamSlider({
  label,
  hint,
  value,
  min,
  max,
  step,
  fmt,
  onChange,
}: {
  label: string
  hint: string
  value: number
  min: number
  max: number
  step: number
  fmt: (v: number) => string
  onChange: (v: number) => void
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <Label className="text-xs font-medium">{label}</Label>
        <span className="font-mono text-xs font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
          {fmt(value)}
        </span>
      </div>
      <Slider
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={(v) => onChange(v[0] ?? value)}
        aria-label={label}
      />
      <p className="text-[11px] leading-snug text-muted-foreground">{hint}</p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component chính
// ---------------------------------------------------------------------------

interface RuntimeState {
  playing: boolean
  speed: number
  showGt: boolean
  showPred: boolean
  showEdges: boolean
  showLabels: boolean
  sparse: boolean
}

export default function TrackingDemo() {
  const [seed, setSeed] = useState(20260911)
  const sim = useMemo(() => buildSimulation(seed), [seed])

  const [params, setParams] = useState<Params>({ ...DEFAULT_PARAMS })
  const [sparseMode, setSparseMode] = useState(true)
  const analysis = useMemo(
    () => analyze(sim, params, sparseMode, seed),
    [sim, params, sparseMode, seed],
  )

  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [frame, setFrame] = useState(0)
  const [showGt, setShowGt] = useState(true)
  const [showPred, setShowPred] = useState(true)
  const [showEdges, setShowEdges] = useState(true)
  const [showLabels, setShowLabels] = useState(false)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const timeRef = useRef(0)
  const frameRef = useRef(0)
  const tickRef = useRef(0)
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 })
  const noiseRef = useRef<{ pattern: CanvasPattern | null; width: number } | null>(null)
  const stateRef = useRef<RuntimeState>({
    playing: true,
    speed: 1,
    showGt: true,
    showPred: true,
    showEdges: true,
    showLabels: false,
    sparse: true,
  })
  const dataRef = useRef<{ sim: SimData; analysis: Analysis } | null>(null)

  useEffect(() => {
    stateRef.current = {
      playing, speed, showGt, showPred, showEdges, showLabels, sparse: sparseMode,
    }
  }, [playing, speed, showGt, showPred, showEdges, showLabels, sparseMode])

  useEffect(() => {
    dataRef.current = { sim, analysis }
  }, [sim, analysis])

  // ---- vẽ một khung ----
  const draw = useCallback((): void => {
    const canvas = canvasRef.current
    if (canvas === null) return
    const ctx = canvas.getContext('2d')
    if (ctx === null) return
    const data = dataRef.current
    if (data === null) return
    const { w, h, dpr } = sizeRef.current
    if (w < 4 || h < 4) return

    const st = stateRef.current
    const { sim: sm, analysis: an } = data
    const tau = timeRef.current
    const fi = Math.floor(tau)
    const f = Math.min(fi, LAST_FRAME)
    const u = f === LAST_FRAME ? 0 : tau - fi
    const scaleX = w / WORLD_W
    const scaleY = h / WORLD_H
    const S = clamp(w / 900, 0.8, 1.4)

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    // --- nền tối kính hiển vi ---
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
    ctx.fillStyle = '#04100b'
    ctx.fillRect(0, 0, w, h)

    const ill = ctx.createRadialGradient(
      w * 0.42, h * 0.38, 0,
      w * 0.42, h * 0.38, Math.max(w, h) * 0.72,
    )
    ill.addColorStop(0, 'rgba(45, 212, 160, 0.05)')
    ill.addColorStop(1, 'rgba(45, 212, 160, 0)')
    ctx.fillStyle = ill
    ctx.fillRect(0, 0, w, h)

    if (noiseRef.current === null || noiseRef.current.width !== canvas.width) {
      noiseRef.current = {
        pattern: ctx.createPattern(createNoiseCanvas(), 'repeat'),
        width: canvas.width,
      }
    }
    const noise = noiseRef.current
    if (noise !== null && noise.pattern !== null) {
      ctx.save()
      ctx.globalCompositeOperation = 'lighter'
      ctx.globalAlpha = 0.5
      const offX = (tickRef.current * 11) % 128
      const offY = (tickRef.current * 7) % 128
      ctx.translate(-offX, -offY)
      ctx.fillStyle = noise.pattern
      ctx.fillRect(offX, offY, w, h)
      ctx.restore()
    }

    // --- cạnh ---
    const fd = an.frames[f]!
    const line = (
      x1: number, y1: number, x2: number, y2: number,
      color: string, lw: number, dash?: number[],
    ): void => {
      ctx.strokeStyle = color
      ctx.lineWidth = lw
      ctx.setLineDash(dash ?? [])
      ctx.beginPath()
      ctx.moveTo(x1 * scaleX, y1 * scaleY)
      ctx.lineTo(x2 * scaleX, y2 * scaleY)
      ctx.stroke()
      ctx.setLineDash([])
    }

    if (st.showGt) {
      for (const e of fd.gtEdges) {
        if (e.fn && st.showEdges) continue
        line(e.x1, e.y1, e.x2, e.y2, 'rgba(52, 211, 153, 0.20)', 1 * S)
      }
    }
    if (st.showEdges) {
      for (const e of fd.gtEdges) {
        if (!e.fn) continue
        line(e.x1, e.y1, e.x2, e.y2, 'rgba(251, 191, 36, 0.85)', 1.6 * S, [5, 4])
      }
      for (const e of fd.predEdges) {
        if (e.cls === 'tp') {
          line(e.x1, e.y1, e.x2, e.y2, 'rgba(52, 211, 153, 0.55)', 1.6 * S)
        } else if (e.cls === 'fp') {
          line(e.x1, e.y1, e.x2, e.y2, 'rgba(244, 63, 94, 0.6)', 1.5 * S)
        } else {
          line(e.x1, e.y1, e.x2, e.y2, 'rgba(148, 163, 158, 0.14)', 1 * S)
        }
      }
    }

    // --- tế bào GT (nội suy mượt giữa 2 khung) ---
    if (st.showGt) {
      for (const tr of sm.tracks) {
        if (!(tr.start <= f + 1 && tr.end >= f)) continue
        const fa = f >= tr.start && f <= tr.end ? tr.frames[f - tr.start] ?? null : null
        const fb = f + 1 >= tr.start && f + 1 <= tr.end ? tr.frames[f + 1 - tr.start] ?? null : null
        if (fa === null && fb === null) continue

        let x: number, y: number, z: number, r: number
        let labeled: boolean
        if (fa !== null && fb !== null) {
          x = lerp(fa.x, fb.x, u)
          y = lerp(fa.y, fb.y, u)
          z = lerp(fa.z, fb.z, u)
          r = lerp(fa.r, fb.r, u)
          labeled = fa.labeled
        } else if (fa !== null) {
          x = fa.x; y = fa.y; z = fa.z; r = fa.r
          labeled = fa.labeled
        } else {
          const mother = tr.parent !== null ? sm.byId.get(tr.parent) : undefined
          const mf = mother !== undefined ? mother.frames[mother.frames.length - 1] : undefined
          if (mother !== undefined && mf !== undefined && tr.parent !== null) {
            const grow = u * u
            x = lerp(mf.x, fb!.x, grow)
            y = lerp(mf.y, fb!.y, grow)
            z = lerp(mf.z, fb!.z, u)
            r = lerp(mf.r * 1.2, fb!.r, grow)
          } else {
            x = fb!.x; y = fb!.y; z = fb!.z; r = fb!.r
          }
          labeled = fb!.labeled
        }

        const X = x * scaleX
        const Y = y * scaleY
        const dz = z / 63
        const R = Math.max(2.5, r * scaleX * (1 - 0.28 * dz))
        const ghost = st.sparse && !labeled

        if (ghost) {
          ctx.strokeStyle = 'rgba(110, 231, 183, 0.22)'
          ctx.lineWidth = 1 * S
          ctx.setLineDash([3, 3])
          ctx.beginPath()
          ctx.arc(X, Y, R, 0, Math.PI * 2)
          ctx.stroke()
          ctx.setLineDash([])
        } else {
          const g = ctx.createRadialGradient(X, Y, 0, X, Y, R)
          const aBase = 0.9 - 0.35 * dz
          g.addColorStop(0, `rgba(209, 250, 229, ${aBase.toFixed(3)})`)
          g.addColorStop(0.45, `rgba(52, 211, 153, ${(aBase * 0.75).toFixed(3)})`)
          g.addColorStop(1, 'rgba(6, 78, 59, 0)')
          ctx.fillStyle = g
          ctx.beginPath()
          ctx.arc(X, Y, R, 0, Math.PI * 2)
          ctx.fill()
          ctx.fillStyle = `rgba(236, 254, 255, ${(0.85 - 0.3 * dz).toFixed(3)})`
          ctx.beginPath()
          ctx.arc(X, Y, Math.max(1, R * 0.16), 0, Math.PI * 2)
          ctx.fill()
        }

        if (st.showLabels && !ghost) {
          ctx.font = `600 ${Math.round(9.5 * S)}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
          ctx.textAlign = 'left'
          ctx.textBaseline = 'middle'
          ctx.shadowColor = 'rgba(0, 0, 0, 0.85)'
          ctx.shadowBlur = 3
          ctx.fillStyle = 'rgba(167, 243, 208, 0.9)'
          ctx.fillText(String(tr.id), X + R + 4 * S, Y - R * 0.6)
          ctx.shadowBlur = 0
          ctx.shadowColor = 'transparent'
        }
      }
    }

    // --- lớp dự đoán: vòng teal + node giả (×) ---
    if (st.showPred) {
      const frameNodes = an.nodes[f]!
      for (const nd of frameNodes) {
        const d = nd.det
        const X = d.x * scaleX
        const Y = d.y * scaleY
        const dz = d.z / 63
        const R = Math.max(2.5, d.r * scaleX * (1 - 0.28 * dz))

        if (nd.cls === 'spurious') {
          ctx.strokeStyle = 'rgba(251, 113, 133, 0.9)'
          ctx.lineWidth = 1.8 * S
          const k = 4.5 * S
          ctx.beginPath()
          ctx.moveTo(X - k, Y - k); ctx.lineTo(X + k, Y + k)
          ctx.moveTo(X + k, Y - k); ctx.lineTo(X - k, Y + k)
          ctx.stroke()
        } else {
          const a = nd.cls === 'matched' ? 0.95 - 0.25 * dz : 0.5 - 0.15 * dz
          ctx.strokeStyle = `rgba(45, 212, 191, ${a.toFixed(3)})`
          ctx.lineWidth = 1.7 * S
          ctx.beginPath()
          ctx.arc(X, Y, R + 2.5 * S, 0, Math.PI * 2)
          ctx.stroke()
          if (nd.cls === 'matched') {
            ctx.fillStyle = `rgba(45, 212, 191, ${(0.8 - 0.2 * dz).toFixed(3)})`
            ctx.beginPath()
            ctx.arc(X, Y, Math.max(1, R * 0.12), 0, Math.PI * 2)
            ctx.fill()
          }
        }

        if (st.showLabels) {
          ctx.font = `600 ${Math.round(9 * S)}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
          ctx.textAlign = 'right'
          ctx.textBaseline = 'middle'
          ctx.shadowColor = 'rgba(0, 0, 0, 0.85)'
          ctx.shadowBlur = 3
          ctx.fillStyle =
            nd.cls === 'matched'
              ? 'rgba(94, 234, 212, 0.92)'
              : nd.cls === 'neutral'
                ? 'rgba(94, 234, 212, 0.45)'
                : 'rgba(251, 113, 133, 0.9)'
          const labelText =
            nd.cls === 'matched'
              ? `→${nd.gtKey!.split('@')[0]}`
              : nd.cls === 'neutral'
                ? '·'
                : 'FP'
          ctx.fillText(labelText, X - R - 4 * S, Y + R * 0.55)
          ctx.shadowBlur = 0
          ctx.shadowColor = 'transparent'
        }
      }
    }

    // --- xung phân bào (lớp GT) ---
    if (st.showGt && st.showEdges) {
      for (const dv of sm.divisions) {
        if (!(tau >= dv.frame && tau < dv.frame + 1.8)) continue
        const mother = sm.byId.get(dv.mother)
        const mf = mother !== undefined ? mother.frames[mother.frames.length - 1] : undefined
        if (mf === undefined) continue
        const p = (tau - dv.frame) / 1.8
        const ease = 1 - Math.pow(1 - p, 3)
        const fade = Math.pow(1 - p, 1.6)
        const X = mf.x * scaleX
        const Y = mf.y * scaleY
        ctx.strokeStyle = `rgba(251, 191, 36, ${(0.9 * fade).toFixed(3)})`
        ctx.lineWidth = 2.2 * S
        ctx.beginPath()
        ctx.arc(X, Y, (6 + 34 * ease) * S, 0, Math.PI * 2)
        ctx.stroke()
        ctx.strokeStyle = `rgba(252, 211, 77, ${(0.45 * fade).toFixed(3)})`
        ctx.lineWidth = 1.2 * S
        ctx.beginPath()
        ctx.arc(X, Y, (4 + 18 * ease) * S, 0, Math.PI * 2)
        ctx.stroke()
        ctx.font = `600 ${Math.round(11 * S)}px ui-sans-serif, system-ui, sans-serif`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'alphabetic'
        ctx.shadowColor = 'rgba(0, 0, 0, 0.85)'
        ctx.shadowBlur = 4
        ctx.fillStyle = `rgba(252, 211, 77, ${clamp(1.15 - p * 0.35, 0, 1).toFixed(3)})`
        ctx.fillText('phân bào', X, Y - (mf.r * scaleX + 14 * S))
        ctx.shadowBlur = 0
        ctx.shadowColor = 'transparent'
      }
    }

    // --- vignette ---
    const vg = ctx.createRadialGradient(
      w / 2, h / 2, Math.min(w, h) * 0.32,
      w / 2, h / 2, Math.max(w, h) * 0.72,
    )
    vg.addColorStop(0, 'rgba(0, 0, 0, 0)')
    vg.addColorStop(1, 'rgba(0, 0, 0, 0.5)')
    ctx.fillStyle = vg
    ctx.fillRect(0, 0, w, h)

    // --- HUD ---
    const pad = 12 * S
    const mono = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

    ctx.fillStyle = 'rgba(167, 243, 208, 0.65)'
    if (st.playing) {
      ctx.beginPath()
      ctx.moveTo(pad + 3.5 * S, pad + 2 * S)
      ctx.lineTo(pad + 3.5 * S, pad + 12 * S)
      ctx.lineTo(pad + 12 * S, pad + 7 * S)
      ctx.closePath()
      ctx.fill()
    } else {
      ctx.fillRect(pad + 3.5 * S, pad + 2 * S, 3 * S, 10 * S)
      ctx.fillRect(pad + 8.5 * S, pad + 2 * S, 3 * S, 10 * S)
    }

    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.font = `600 ${Math.round(13 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(209, 250, 229, 0.92)'
    ctx.fillText(
      `t = ${String(f).padStart(2, '0')} / ${String(LAST_FRAME).padStart(2, '0')}`,
      pad + 18 * S, pad,
    )
    ctx.font = `${Math.round(10.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(149, 202, 178, 0.62)'
    ctx.fillText(
      `${(MPF_BASE + tau * MPF_PER_FRAME).toFixed(1)} phút sau thụ tinh (mpf)`,
      pad + 18 * S, pad + 18 * S,
    )

    ctx.textAlign = 'right'
    ctx.font = `600 ${Math.round(13 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(209, 250, 229, 0.92)'
    ctx.fillText(`⟨I⟩ = ${sm.meanIntensity[f] ?? 0}`, w - pad, pad)
    ctx.font = `${Math.round(10.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(149, 202, 178, 0.62)'
    ctx.fillText('uint16 · max-projection Z', w - pad, pad + 18 * S)

    ctx.textAlign = 'left'
    ctx.font = `${Math.round(9.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(149, 202, 178, 0.45)'
    ctx.fillText('(T, Z, Y, X) = (60, 64, 256, 256) · uint16', pad, h - pad - 25 * S)
    ctx.fillText('xy µm · z 1.625 µm/voxel', pad, h - pad - 13 * S)

    const barLen = 50 * scaleX
    const bx0 = w - pad - barLen
    const by0 = h - pad - 8 * S
    ctx.strokeStyle = 'rgba(209, 250, 229, 0.85)'
    ctx.lineWidth = 1.5 * S
    ctx.beginPath()
    ctx.moveTo(bx0, by0); ctx.lineTo(bx0 + barLen, by0)
    ctx.moveTo(bx0, by0 - 3 * S); ctx.lineTo(bx0, by0 + 3 * S)
    ctx.moveTo(bx0 + barLen, by0 - 3 * S); ctx.lineTo(bx0 + barLen, by0 + 3 * S)
    ctx.stroke()
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    ctx.font = `600 ${Math.round(10.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(209, 250, 229, 0.85)'
    ctx.fillText('50 µm', bx0 + barLen / 2, by0 - 5 * S)

    tickRef.current += 1
  }, [])

  // ---- vòng lặp rAF ----
  useEffect(() => {
    let raf = 0
    let last = performance.now()
    const loop = (now: number): void => {
      raf = requestAnimationFrame(loop)
      const dt = Math.min(0.06, (now - last) / 1000)
      last = now
      if (typeof document !== 'undefined' && document.hidden) return
      const st = stateRef.current
      if (st.playing) {
        timeRef.current += dt * BASE_FPS * st.speed
        if (timeRef.current >= LAST_FRAME) timeRef.current = 0
      }
      draw()
      const fi = Math.min(LAST_FRAME, Math.floor(timeRef.current))
      if (fi !== frameRef.current) {
        frameRef.current = fi
        setFrame(fi)
      }
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [draw])

  // ---- canvas co giãn theo container + devicePixelRatio ----
  useEffect(() => {
    const wrap = wrapRef.current
    const canvas = canvasRef.current
    if (wrap === null || canvas === null) return
    const resize = (): void => {
      const rect = wrap.getBoundingClientRect()
      const dpr = clamp(window.devicePixelRatio || 1, 1, 2)
      const w = Math.max(1, Math.round(rect.width))
      const h = Math.max(1, Math.round(rect.height))
      const cw = Math.round(w * dpr)
      const ch = Math.round(h * dpr)
      if (canvas.width !== cw) canvas.width = cw
      if (canvas.height !== ch) canvas.height = ch
      sizeRef.current = { w, h, dpr }
    }
    resize()
    const ro = new ResizeObserver(resize)
    ro.observe(wrap)
    return () => ro.disconnect()
  }, [])

  // ---- điều khiển ----
  const handleScrub = useCallback((v: number[]): void => {
    const nf = clamp(Math.round(v[0] ?? 0), 0, LAST_FRAME)
    timeRef.current = nf
    frameRef.current = nf
    setFrame(nf)
  }, [])

  const handleReset = useCallback((): void => {
    timeRef.current = 0
    frameRef.current = 0
    setFrame(0)
  }, [])

  // ---- thống kê khung hiện tại ----
  const m = analysis.metrics
  const curNodes = analysis.nodes[frame] ?? []
  const curFrame = analysis.frames[frame] ?? { gtEdges: [], predEdges: [] }
  const matchedNow = curNodes.filter((n) => n.cls === 'matched').length
  const tpNow = curFrame.predEdges.filter((e) => e.cls === 'tp').length
  const fpNow = curFrame.predEdges.filter((e) => e.cls === 'fp').length
  const fnNow = curFrame.gtEdges.filter((e) => e.fn).length
  const gtNow = analysis.gtCountByFrame[frame] ?? 0

  return (
    <Card className="gap-0 overflow-hidden py-0">
      <CardHeader className="px-4 pt-5 pb-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-emerald-500/25 bg-emerald-500/10">
            <Microscope className="size-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="min-w-0">
            <CardTitle className="text-base sm:text-lg">
              Trình mô phỏng &amp; chấm điểm bài nộp
            </CardTitle>
            <CardDescription className="mt-1 text-xs sm:text-sm">
              Dữ liệu kính hiển vi 3D+time của phôi zebrafish — lớp{' '}
              <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                ground-truth
              </span>{' '}
              (đốm emerald) đối chiếu lớp{' '}
              <span className="font-semibold text-teal-700 dark:text-teal-300">
                dự đoán
              </span>{' '}
              (vòng teal) từ &quot;thuật toán&quot; nearest-neighbor. Chỉnh tham
              số và xem điểm thay đổi theo đúng tinh thần metric cuộc thi.
            </CardDescription>
          </div>
        </div>
        <CardAction>
          <Badge
            variant="outline"
            className="hidden gap-1.5 border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 sm:inline-flex"
          >
            <Gauge className="size-3" />
            60 khung · 6 phân bào · GT thưa
          </Badge>
        </CardAction>
      </CardHeader>

      {/* vùng canvas */}
      <div
        ref={wrapRef}
        className="relative aspect-video w-full overflow-hidden bg-[#04100b]"
      >
        <canvas
          ref={canvasRef}
          className="absolute inset-0 h-full w-full"
          role="img"
          aria-label="Mô phỏng theo dõi tế bào: lớp ground-truth màu emerald, lớp dự đoán màu teal, cạnh đúng màu lục, cạnh sai màu đỏ, cạnh bỏ sót màu vàng nét đứt"
        />
      </div>

      <div className="flex flex-col gap-5 px-4 pt-4 pb-5 sm:px-6">
        {/* 1 · phát / tua / tốc độ */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <Button
            type="button"
            variant="secondary"
            size="icon"
            onClick={() => setPlaying((p) => !p)}
            aria-label={playing ? 'Tạm dừng phát' : 'Phát'}
            className="border border-emerald-500/20 bg-emerald-500/15 text-emerald-700 hover:bg-emerald-500/25 dark:text-emerald-300"
          >
            {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
          </Button>
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={handleReset}
            aria-label="Quay về khung hình đầu"
          >
            <RotateCcw className="size-4" />
          </Button>
          <div className="order-last w-full min-w-0 sm:order-none sm:w-auto sm:flex-1">
            <Slider
              value={[frame]}
              min={0}
              max={LAST_FRAME}
              step={1}
              onValueChange={handleScrub}
              onPointerDown={() => setPlaying(false)}
              aria-label="Khung hình hiện tại"
              className="w-full"
            />
          </div>
          <span className="w-full text-right font-mono text-xs tabular-nums text-muted-foreground sm:w-auto sm:text-left">
            t = {String(frame).padStart(2, '0')} / {String(LAST_FRAME).padStart(2, '0')}
          </span>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={String(speed)}
            onValueChange={(v) => {
              if (v !== '') setSpeed(Number(v))
            }}
            aria-label="Tốc độ phát"
          >
            <ToggleGroupItem value="0.5" aria-label="Tốc độ 0,5 lần">0.5×</ToggleGroupItem>
            <ToggleGroupItem value="1" aria-label="Tốc độ 1 lần">1×</ToggleGroupItem>
            <ToggleGroupItem value="2" aria-label="Tốc độ 2 lần">2×</ToggleGroupItem>
          </ToggleGroup>
        </div>

        {/* 2 · chip thống kê khung hiện tại */}
        <div className="flex flex-wrap items-center gap-2">
          <StatChip icon={<CircleDot />} label="GT node" value={String(gtNow)} tone="emerald" />
          <StatChip icon={<Target />} label="Dự đoán" value={String(curNodes.length)} tone="teal" />
          <StatChip icon={<Crosshair />} label="Khớp" value={String(matchedNow)} tone="emerald" />
          <StatChip
            icon={<Spline />}
            label="TP·FP·FN"
            value={`${tpNow}·${fpNow}·${fnNow}`}
            tone="rose"
          />
          <StatChip
            icon={<GitBranch />}
            label="Phân bào"
            value={`${m.divTP}/${sim.divisions.length}`}
            tone="amber"
          />
          <StatChip
            icon={<Activity />}
            label="⟨I⟩"
            value={String(sim.meanIntensity[frame] ?? 0)}
            tone="emerald"
          />
        </div>

        {/* 3 · lớp hiển thị */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {(
            [
              ['td-gt', showGt, setShowGt, 'Hiện GT (đáp án)'],
              ['td-pred', showPred, setShowPred, 'Hiện dự đoán'],
              ['td-edges', showEdges, setShowEdges, 'Cạnh & lỗi (TP·FP·FN)'],
              ['td-labels', showLabels, setShowLabels, 'Nhãn node'],
              ['td-sparse', sparseMode, setSparseMode, 'GT thưa (sparse)'],
            ] as const
          ).map(([id, checked, setter, text]) => (
            <div key={id} className="flex items-center gap-2">
              <Switch
                id={id}
                checked={checked}
                onCheckedChange={(c) => setter(c)}
              />
              <Label htmlFor={id} className="cursor-pointer text-xs text-muted-foreground">
                {text}
              </Label>
            </div>
          ))}
        </div>

        {/* 4 · bảng chấm điểm */}
        <div className="rounded-xl border bg-muted/30 p-4 sm:p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
            <Gauge className="size-4 text-emerald-600 dark:text-emerald-400" />
            Kết quả chấm điểm — tổng trên toàn bộ 60 khung hình
          </div>
          <div className="grid gap-4 lg:grid-cols-5">
            <div className="flex flex-col justify-center rounded-xl border border-emerald-500/25 bg-gradient-to-br from-emerald-500/10 to-transparent p-4 lg:col-span-2">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Điểm tổng (mô phỏng)
              </p>
              <p className="mt-1 font-mono text-4xl font-extrabold leading-none tabular-nums text-emerald-700 dark:text-emerald-300">
                {m.combined.toFixed(3)}
              </p>
              <p className="mt-2 font-mono text-[11px] text-muted-foreground">
                = adj_edge_jaccard + 0.1 × division_jaccard
              </p>
              <p className="mt-1.5 text-[10px] leading-snug text-muted-foreground/80">
                Adj = TP / (TP + FP + FN + node thừa) — phạt over-predict node
                (đơn giản hóa để minh họa; metric chính thức chi tiết hơn).
                Ghép node tối ưu trong ngưỡng 7.0 µm.
              </p>
            </div>
            <div className="space-y-3.5 lg:col-span-3">
              <MetricBar label="Phát hiện node (recall)" value={m.nodeRecall} />
              <MetricBar label="Edge Jaccard (điều chỉnh)" value={m.adjEJ} />
              <MetricBar label="Division Jaccard" value={m.divJ} />
              <div className="flex flex-wrap gap-2 pt-0.5">
                <span className="rounded-full border bg-background px-2.5 py-1 font-mono text-[11px] tabular-nums">
                  Cạnh TP {m.tp} · FP {m.fp} · FN {m.fn}
                </span>
                <span className="rounded-full border bg-background px-2.5 py-1 font-mono text-[11px] tabular-nums">
                  Phân bào TP {m.divTP} · FP {m.divFP} · FN {m.divFN}
                </span>
                <span className="rounded-full border bg-background px-2.5 py-1 font-mono text-[11px] tabular-nums">
                  Node GT {m.gtNodes} · khớp {m.matchedGT} · thừa {m.spurious}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 5 · tham số thuật toán */}
        <div className="rounded-xl border bg-muted/30 p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Wand2 className="size-4 text-emerald-600 dark:text-emerald-400" />
              Tham số &quot;thuật toán&quot; giả lập
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {PRESETS.map((pr) => (
                <Button
                  key={pr.name}
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-7 px-2.5 text-xs"
                  onClick={() => setParams({ ...pr.p })}
                >
                  {pr.name}
                </Button>
              ))}
              <Button
                type="button"
                variant="secondary"
                size="sm"
                className="h-7 gap-1.5 px-2.5 text-xs"
                onClick={() => setSeed((s) => s + 101)}
              >
                <Dices className="size-3.5" />
                Dữ liệu mới
              </Button>
            </div>
          </div>
          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
            <ParamSlider
              label="Phát hiện (recall)"
              hint="Xác suất bắt được từng tế bào ở mỗi khung — thiếu sẽ sinh cạnh FN."
              value={params.recall}
              min={0.5}
              max={1}
              step={0.01}
              fmt={(v) => v.toFixed(2)}
              onChange={(v) => setParams((p) => ({ ...p, recall: v }))}
            />
            <ParamSlider
              label="Node giả (FP)"
              hint="Tỉ lệ phát hiện thừa — bị trừ trực tiếp vào mẫu số điểm cạnh."
              value={params.fpRate}
              min={0}
              max={0.15}
              step={0.005}
              fmt={(v) => `${(v * 100).toFixed(1)}%`}
              onChange={(v) => setParams((p) => ({ ...p, fpRate: v }))}
            />
            <ParamSlider
              label="Nhiễu định vị"
              hint="Sai số tâm node — quá lớn thì vượt ngưỡng ghép 7.0 µm, gây FN."
              value={params.jitter}
              min={0}
              max={4}
              step={0.1}
              fmt={(v) => `${v.toFixed(1)} µm`}
              onChange={(v) => setParams((p) => ({ ...p, jitter: v }))}
            />
            <ParamSlider
              label="Ngưỡng liên kết"
              hint="Bán kính tối đa nối node giữa 2 khung — quá lỏng sẽ tạo cạnh FP chéo."
              value={params.linkUm}
              min={3}
              max={16}
              step={0.5}
              fmt={(v) => `${v.toFixed(1)} µm`}
              onChange={(v) => setParams((p) => ({ ...p, linkUm: v }))}
            />
          </div>
          <div className="mt-4 flex items-center justify-between gap-3 rounded-lg border bg-background/60 px-3.5 py-2.5">
            <div className="flex items-center gap-2.5">
              <Switch
                id="td-division"
                checked={params.division}
                onCheckedChange={(c) => setParams((p) => ({ ...p, division: c }))}
              />
              <Label htmlFor="td-division" className="cursor-pointer text-xs">
                Phát hiện phân bào (nối 1 node tới 2 node con)
              </Label>
            </div>
            <p className="hidden text-[11px] text-muted-foreground sm:block">
              Tắt → mất điểm division (10% tổng điểm)
            </p>
          </div>
        </div>

        {/* 6 · chú giải */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t pt-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-2">
            <span
              className="size-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]"
              aria-hidden
            />
            Tế bào GT (node)
          </span>
          <span className="inline-flex items-center gap-2">
            <span
              className="size-2.5 rounded-full border-2 border-teal-400"
              aria-hidden
            />
            Dự đoán (node)
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="font-mono text-rose-500" aria-hidden>✕</span>
            Node thừa (FP)
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="h-0.5 w-5 rounded-full bg-emerald-400/80" aria-hidden />
            Cạnh TP
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="h-0.5 w-5 rounded-full bg-rose-500/80" aria-hidden />
            Cạnh FP
          </span>
          <span className="inline-flex items-center gap-2">
            <span
              className="h-0.5 w-5 rounded-full border-t-2 border-dashed border-amber-400"
              aria-hidden
            />
            Cạnh FN (bỏ sót)
          </span>
          <span className="inline-flex items-center gap-2">
            <span
              className="size-2.5 rounded-full border-2 border-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
              aria-hidden
            />
            Phân bào
          </span>
          <span className="ml-auto hidden text-[11px] text-muted-foreground/70 lg:inline">
            GT thưa: nét đứt mờ = tế bào chưa được gắn nhãn (metric đã tính đến)
          </span>
        </div>
      </div>
    </Card>
  )
}
