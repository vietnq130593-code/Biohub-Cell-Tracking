'use client'

/**
 * Trình mô phỏng theo dõi tế bào
 * Kaggle competition: "Biohub - Cell Tracking During Development"
 *
 * Mô phỏng một "cửa sổ dữ liệu" kính hiển vi 3D + thời gian của phôi zebrafish:
 * - ~24-32 tế bào phát huỳnh quang di chuyển trong trường nhìn (random walk + dòng chảy phôi)
 * - 6 sự kiện phân bào (mẹ → 2 con), đánh dấu amber + xung vòng tròn lan tỏa
 * - Gắn nhãn thưa (sparse GT): một số frame không được gắn nhãn → hiển thị "ghost"
 * - Node / cạnh / phân bào được tính đúng ngữ nghĩa cuộc thi (nodes + edges, mẹ có ≥ 2 cạnh đi ra)
 *
 * Toàn bộ dữ liệu được sinh trước bằng PRNG có seed (mulberry32) → tất định.
 */

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Activity,
  CircleDot,
  GitBranch,
  Microscope,
  MousePointerClick,
  Pause,
  Play,
  RotateCcw,
  Spline,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardAction, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'

// ---------------------------------------------------------------------------
// Hằng số mô phỏng (gần với dữ liệu thật: (T,Z,Y,X)=(100,64,256,256), uint16)
// ---------------------------------------------------------------------------

/** Số khung hình mô phỏng: t = 0..59 */
const T = 60
const LAST_FRAME = T - 1

/** Trường nhìn 2D (phép chiếu max-projection của khối 104×104×104 µm) */
const WORLD_W = 160 // µm
const WORLD_H = 90 // µm  (160:90 = 16:9 khớp aspect-video)

/** Tốc độ phát cơ bản: khung hình / giây ở 1× */
const BASE_FPS = 2.5

/** Thời gian mô phỏng: phút sau thụ tinh (2.5 hpf + 1.5 phút/khung) */
const MPF_BASE = 150
const MPF_PER_FRAME = 1.5

/** Số khung hình tối đa của vệt track hiển thị */
const TRAIL_LENGTH = 26

// ---------------------------------------------------------------------------
// PRNG có seed
// ---------------------------------------------------------------------------

function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v))
const lerp = (a: number, b: number, u: number): number => a + (b - a) * u
const hsla = (h: number, s: number, l: number, a: number): string =>
  `hsla(${h}, ${s}%, ${l}%, ${a})`

// ---------------------------------------------------------------------------
// Kiểu dữ liệu mô phỏng
// ---------------------------------------------------------------------------

/** Trạng thái một tế bào tại một khung hình */
interface CellFrame {
  x: number // µm
  y: number // µm
  z: number // voxel 0..63
  r: number // bán kính µm
  i: number // cường độ 0..1
  labeled: boolean // có nằm trong GT thưa tại frame này không
}

/** Một track = một node trong đồ thị theo dõi */
interface Track {
  id: number
  parent: number | null // track mẹ (nếu là con của phân bào)
  divisionFrame: number | null // frame mà tế bào này phân bào (frame cuối của mẹ)
  start: number // frame đầu
  end: number // frame cuối (bao gồm cả đầu)
  hue: number // 148..170: emerald → teal
  frames: CellFrame[]
}

interface SimData {
  tracks: Track[]
  byId: Map<number, Track>
  divisionFrames: number[]
  meanIntensity: number[]
}

// ---------------------------------------------------------------------------
// Sinh dữ liệu mô phỏng (tất định)
// ---------------------------------------------------------------------------

function buildSimulation(): SimData {
  const rng = mulberry32(0x51f00d2a)
  const rand = (a: number, b: number): number => a + (b - a) * rng()
  const randInt = (a: number, b: number): number => Math.floor(rand(a, b + 1))

  interface Plan {
    id: number
    parent: number | null
    start: number
    end: number
    divisionFrame: number | null
  }

  const plans: Plan[] = []
  let nextId = 1

  // 26 tế bào ban đầu + 3 tế bào đi vào trường nhìn giữa phim
  for (let k = 0; k < 26; k++) {
    plans.push({ id: nextId++, parent: null, start: 0, end: LAST_FRAME, divisionFrame: null })
  }
  for (const s of [8, 19, 30]) {
    plans.push({ id: nextId++, parent: null, start: s, end: LAST_FRAME, divisionFrame: null })
  }

  // 6 sự kiện phân bào rải đều suốt phim
  const divisionFrames: number[] = []
  for (const base of [11, 18, 26, 34, 42, 50]) {
    const d = clamp(base + randInt(-1, 1), 8, 51)
    const eligible = plans.filter(
      (p) => p.parent === null && p.divisionFrame === null && p.end >= d + 8 && d - p.start >= 5,
    )
    if (eligible.length === 0) continue
    const mother = eligible[Math.floor(rng() * eligible.length)]
    mother.divisionFrame = d
    mother.end = d
    plans.push({ id: nextId++, parent: mother.id, start: d + 1, end: LAST_FRAME, divisionFrame: null })
    plans.push({ id: nextId++, parent: mother.id, start: d + 1, end: LAST_FRAME, divisionFrame: null })
    divisionFrames.push(d)
  }
  divisionFrames.sort((a, b) => a - b)

  // Vài track kết thúc sớm (rời trường nhìn / hết gắn nhãn) → fade out
  const usedExit = new Set<number>()
  const plain = plans.filter((p) => p.parent === null && p.divisionFrame === null)
  for (const target of [34, 41, 48, 53]) {
    const candidates = plain.filter((p) => !usedExit.has(p.id) && p.start <= target - 12)
    if (candidates.length === 0) continue
    const pick = candidates[Math.floor(rng() * candidates.length)]
    pick.end = target + randInt(-1, 1)
    usedExit.add(pick.id)
  }
  const daughters = plans.filter((p) => p.parent !== null)
  for (const target of [46, 55]) {
    const candidates = daughters.filter((p) => !usedExit.has(p.id) && p.start <= target - 14)
    if (candidates.length === 0) continue
    const pick = candidates[Math.floor(rng() * candidates.length)]
    pick.end = target + randInt(-1, 1)
    usedExit.add(pick.id)
  }

  // ---- Trạng thái sinh động cho từng track ----
  interface WorkingTrack extends Track {
    x: number
    y: number
    z: number
    vx: number
    vy: number
    baseR: number
    intensity: number
    sepX: number // hướng tách của con sau phân bào (đơn vị)
    sepY: number
  }

  const byId = new Map<number, WorkingTrack>()
  const working: WorkingTrack[] = plans.map((p) => {
    const w: WorkingTrack = {
      id: p.id,
      parent: p.parent,
      divisionFrame: p.divisionFrame,
      start: p.start,
      end: p.end,
      hue: rand(148, 170),
      frames: [],
      x: 0,
      y: 0,
      z: 32,
      vx: 0,
      vy: 0,
      baseR: rand(2.7, 3.8),
      intensity: rand(0.55, 1),
      sepX: 0,
      sepY: 0,
    }
    byId.set(w.id, w)
    return w
  })

  // Vị trí ban đầu: sample cách đều (rejection sampling) để không chồng lấn
  const placed: Array<{ x: number; y: number }> = []
  for (const w of working) {
    if (w.start !== 0) continue
    let bx = rand(12, WORLD_W - 12)
    let by = rand(12, WORLD_H - 12)
    let bd = -1
    for (let attempt = 0; attempt < 14; attempt++) {
      const cx = rand(12, WORLD_W - 12)
      const cy = rand(12, WORLD_H - 12)
      let d = Infinity
      for (const p of placed) d = Math.min(d, Math.hypot(p.x - cx, p.y - cy))
      if (d > bd) {
        bd = d
        bx = cx
        by = cy
      }
    }
    w.x = bx
    w.y = by
    w.vx = rand(-0.3, 0.3)
    w.vy = rand(-0.3, 0.3)
    w.z = rand(8, 55)
    placed.push({ x: bx, y: by })
  }

  // ---- Mô phỏng theo từng khung hình ----
  for (let t = 0; t < T; t++) {
    for (const w of working) {
      if (t < w.start || t > w.end) continue

      if (t === w.start) {
        if (w.parent !== null) {
          // Con của phân bào: nảy ra từ vị trí mẹ, tách theo hai hướng đối xứng
          const mother = byId.get(w.parent)
          const mf = mother !== undefined ? mother.frames[mother.frames.length - 1] : undefined
          if (mother !== undefined && mf !== undefined) {
            const theta = (mother.id * 2.399) % (Math.PI * 2)
            const dir = w.id % 2 === 0 ? theta : theta + Math.PI + rand(-0.3, 0.3)
            const ux = Math.cos(dir)
            const uy = Math.sin(dir)
            w.x = mf.x + ux * rand(0.6, 1)
            w.y = mf.y + uy * rand(0.6, 1)
            w.vx = ux * rand(0.75, 1.15)
            w.vy = uy * rand(0.75, 1.15)
            w.sepX = ux
            w.sepY = uy
            w.z = clamp(mf.z + rand(-3, 3), 3, 60)
            w.baseR = mother.baseR * rand(0.78, 0.86)
            w.intensity = clamp(mother.intensity * rand(0.92, 1.02), 0.4, 1)
          } else {
            w.x = rand(20, WORLD_W - 20)
            w.y = rand(20, WORLD_H - 20)
          }
        } else if (w.start > 0) {
          // Tế bào đi vào trường nhìn từ rìa
          const side = randInt(0, 3)
          if (side === 0) {
            w.x = rand(10, WORLD_W - 10)
            w.y = 2
            w.vy = rand(0.45, 0.85)
            w.vx = rand(-0.25, 0.25)
          } else if (side === 1) {
            w.x = WORLD_W - 2
            w.y = rand(10, WORLD_H - 10)
            w.vx = -rand(0.45, 0.85)
            w.vy = rand(-0.25, 0.25)
          } else if (side === 2) {
            w.x = rand(10, WORLD_W - 10)
            w.y = WORLD_H - 2
            w.vy = -rand(0.45, 0.85)
            w.vx = rand(-0.25, 0.25)
          } else {
            w.x = 2
            w.y = rand(10, WORLD_H - 10)
            w.vx = rand(0.45, 0.85)
            w.vy = rand(-0.25, 0.25)
          }
          w.z = rand(8, 55)
        }
      } else {
        // Random walk trơn + dòng chảy phôi nhất quán + giữ trong trường nhìn
        w.vx += (rng() - 0.5) * 0.3
        w.vy += (rng() - 0.5) * 0.3
        w.vx *= 0.93
        w.vy *= 0.93
        // con sau phân bào tiếp tục tách rời trong ~15 frame đầu
        if (w.parent !== null && t - w.start < 15) {
          w.vx += w.sepX * 0.07
          w.vy += w.sepY * 0.07
        }
        const swirl = 0.004 * Math.sin((t / T) * Math.PI * 1.3 + 0.7)
        const driftA = 0.9 * Math.PI * Math.sin(t / 23)
        const cx = WORLD_W / 2
        const cy = WORLD_H / 2
        w.vx += -(w.y - cy) * swirl + 0.045 * Math.cos(driftA)
        w.vy += (w.x - cx) * swirl + 0.045 * Math.sin(driftA)
        const m = 7
        if (w.x < m) w.vx += (m - w.x) * 0.035
        if (w.x > WORLD_W - m) w.vx -= (w.x - (WORLD_W - m)) * 0.035
        if (w.y < m) w.vy += (m - w.y) * 0.035
        if (w.y > WORLD_H - m) w.vy -= (w.y - (WORLD_H - m)) * 0.035
        w.x = clamp(w.x + w.vx, 1.5, WORLD_W - 1.5)
        w.y = clamp(w.y + w.vy, 1.5, WORLD_H - 1.5)
        // depth random-walk, có xu hướng về giữa khối Z
        w.z = clamp(w.z + (rng() - 0.5) * 3.2 + (32 - w.z) * 0.012, 3, 60)
        // cường độ dao động nhẹ (photobleaching-ish)
        w.intensity = clamp(w.intensity + (rng() - 0.5) * 0.07, 0.38, 1)
      }

      // Bán kính: mẹ phình nhẹ trước khi phân bào, con lớn dần sau khi sinh
      let r = w.baseR
      if (w.divisionFrame !== null && t >= w.divisionFrame - 3 && t <= w.divisionFrame) {
        r *= 1 + 0.05 * (t - (w.divisionFrame - 3))
      }
      if (w.parent !== null) {
        const age = t - w.start
        r *= 0.62 + 0.2 * Math.min(1, age / 12)
      }
      w.frames.push({ x: w.x, y: w.y, z: w.z, r, i: w.intensity, labeled: true })
    }
  }

  // ---- Gắn nhãn thưa: các "cửa sổ mờ" ngẫu nhiên trên từng track ----
  for (const w of working) {
    const len = w.frames.length
    if (len < 10) continue
    const windows = len > 26 ? (rng() < 0.45 ? 2 : 1) : rng() < 0.5 ? 1 : 0
    for (let k = 0; k < windows; k++) {
      const wl = randInt(2, 7)
      const ws = randInt(0, len - wl - 1)
      for (let j = 0; j < wl; j++) w.frames[ws + j].labeled = false
    }
  }
  // Lân cận phân bào luôn được gắn nhãn (đảm bảo cạnh phân bào tồn tại trong GT)
  for (const w of working) {
    if (w.divisionFrame !== null) {
      const from = Math.max(0, w.divisionFrame - 3 - w.start)
      for (let j = from; j < w.frames.length; j++) w.frames[j].labeled = true
    }
    if (w.parent !== null) {
      for (let j = 0; j < Math.min(5, w.frames.length); j++) w.frames[j].labeled = true
    }
  }

  // ---- Cường độ trung bình mỗi frame (đơn vị uint16-ish) ----
  const meanIntensity: number[] = []
  for (let t = 0; t < T; t++) {
    let sum = 0
    let n = 0
    for (const w of working) {
      if (w.start <= t && t <= w.end) {
        sum += w.frames[t - w.start].i
        n++
      }
    }
    meanIntensity.push(n === 0 ? 0 : Math.round(820 + (sum / n) * 1420 + (rng() - 0.5) * 70))
  }

  const tracks: Track[] = working.map((w) => ({
    id: w.id,
    parent: w.parent,
    divisionFrame: w.divisionFrame,
    start: w.start,
    end: w.end,
    hue: w.hue,
    frames: w.frames,
  }))
  const trackById = new Map<number, Track>()
  for (const tr of tracks) trackById.set(tr.id, tr)

  return { tracks, byId: trackById, divisionFrames, meanIntensity }
}

// ---------------------------------------------------------------------------
// Texture nhiễu sensor (chỉ chạy phía client, dùng trong draw)
// ---------------------------------------------------------------------------

function createNoiseCanvas(): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = 128
  c.height = 128
  const nctx = c.getContext('2d')
  if (nctx !== null) {
    const img = nctx.createImageData(128, 128)
    const nrng = mulberry32(0x90150128)
    for (let p = 0; p < img.data.length; p += 4) {
      const v = 120 + Math.floor(nrng() * 135)
      img.data[p] = Math.floor(v * 0.75)
      img.data[p + 1] = v
      img.data[p + 2] = Math.floor(v * 0.85)
      img.data[p + 3] = Math.floor(nrng() * nrng() * 42)
    }
    nctx.putImageData(img, 0, 0)
  }
  return c
}

// ---------------------------------------------------------------------------
// Component chính
// ---------------------------------------------------------------------------

interface RuntimeState {
  playing: boolean
  speed: number
  showTracks: boolean
  showLabels: boolean
  showDivisions: boolean
  sparseMode: boolean
}

interface VisCell {
  g: Track
  x: number
  y: number
  z: number
  r: number
  i: number
  alpha: number
  ghost: boolean
}

export default function TrackingDemo() {
  const sim = useMemo(() => buildSimulation(), [])

  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [frame, setFrame] = useState(0)
  const [showTracks, setShowTracks] = useState(true)
  const [showLabels, setShowLabels] = useState(false)
  const [showDivisions, setShowDivisions] = useState(true)
  const [sparseMode, setSparseMode] = useState(true)

  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const wrapRef = useRef<HTMLDivElement | null>(null)
  const timeRef = useRef(0) // thời gian liên tục (frame đơn vị float)
  const frameRef = useRef(0) // frame nguyên hiện tại (tránh setState thừa)
  const tickRef = useRef(0) // đếm số lần vẽ (đổi offset nhiễu)
  const sizeRef = useRef({ w: 0, h: 0, dpr: 1 })
  const noiseRef = useRef<{ pattern: CanvasPattern | null; width: number } | null>(null)
  const stateRef = useRef<RuntimeState>({
    playing: true,
    speed: 1,
    showTracks: true,
    showLabels: false,
    showDivisions: true,
    sparseMode: true,
  })

  useEffect(() => {
    stateRef.current = { playing, speed, showTracks, showLabels, showDivisions, sparseMode }
  }, [playing, speed, showTracks, showLabels, showDivisions, sparseMode])

  // ---- Vẽ một khung (đọc mọi trạng thái động từ ref) ----
  const draw = useCallback((): void => {
    const canvas = canvasRef.current
    if (canvas === null) return
    const ctx = canvas.getContext('2d')
    if (ctx === null) return
    const { w, h, dpr } = sizeRef.current
    if (w < 4 || h < 4) return

    const st = stateRef.current
    const tracks = sim.tracks
    const tau = timeRef.current
    const fi = Math.floor(tau)
    const f = Math.min(fi, LAST_FRAME)
    const u = f === LAST_FRAME ? 0 : tau - fi
    const scaleX = w / WORLD_W
    const scaleY = h / WORLD_H
    const S = clamp(w / 900, 0.8, 1.4)

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)

    // --- nền tối kiểu kính hiển vi ---
    ctx.globalCompositeOperation = 'source-over'
    ctx.globalAlpha = 1
    ctx.fillStyle = '#04100b'
    ctx.fillRect(0, 0, w, h)

    // vùng chiếu sáng nhẹ (illumination field lệch tâm)
    const ill = ctx.createRadialGradient(
      w * 0.42,
      h * 0.38,
      0,
      w * 0.42,
      h * 0.38,
      Math.max(w, h) * 0.72,
    )
    ill.addColorStop(0, 'rgba(45, 212, 160, 0.05)')
    ill.addColorStop(1, 'rgba(45, 212, 160, 0)')
    ctx.fillStyle = ill
    ctx.fillRect(0, 0, w, h)

    // nhiễu sensor (nảy theo từng frame)
    if (noiseRef.current === null || noiseRef.current.width !== canvas.width) {
      const nc = createNoiseCanvas()
      noiseRef.current = { pattern: ctx.createPattern(nc, 'repeat'), width: canvas.width }
    }
    const noise = noiseRef.current
    if (noise !== null && noise.pattern !== null) {
      ctx.save()
      ctx.globalCompositeOperation = 'lighter'
      const offX = (tickRef.current * 11) % 128
      const offY = (tickRef.current * 7) % 128
      ctx.translate(-offX, -offY)
      ctx.fillStyle = noise.pattern
      ctx.fillRect(offX, offY, w, h)
      ctx.restore()
    }

    // --- gom trạng thái hiển thị của các tế bào (nội suy giữa 2 frame) ---
    const vis: VisCell[] = []
    const visById = new Map<number, VisCell>()

    for (const g of tracks) {
      if (!(g.start <= f + 1 && g.end >= f)) continue
      const fa = f >= g.start && f <= g.end ? g.frames[f - g.start] : null
      const fb = f + 1 >= g.start && f + 1 <= g.end ? g.frames[f + 1 - g.start] : null
      if (fa === null && fb === null) continue

      let x: number
      let y: number
      let z: number
      let r: number
      let i: number
      let mode: 'mid' | 'end' | 'birth'

      if (fa !== null && fb !== null) {
        x = lerp(fa.x, fb.x, u)
        y = lerp(fa.y, fb.y, u)
        z = lerp(fa.z, fb.z, u)
        r = lerp(fa.r, fb.r, u)
        i = lerp(fa.i, fb.i, u)
        mode = 'mid'
      } else if (fa !== null) {
        // track kết thúc ở bước này: phân bào (tách đôi) hoặc rời khỏi chú thích
        x = fa.x
        y = fa.y
        z = fa.z
        r = fa.r
        i = fa.i
        mode = 'end'
      } else if (fb !== null) {
        // track mới sinh ở frame kế (con của phân bào / đi vào trường nhìn)
        const mother = g.parent !== null ? sim.byId.get(g.parent) : undefined
        const mf = mother !== undefined ? mother.frames[mother.frames.length - 1] : undefined
        if (mother !== undefined && mf !== undefined) {
          const grow = u * u
          x = lerp(mf.x, fb.x, grow)
          y = lerp(mf.y, fb.y, grow)
          z = lerp(mf.z, fb.z, u)
          r = fb.r * (0.75 + 0.25 * u)
          i = fb.i
        } else {
          x = fb.x
          y = fb.y
          z = fb.z
          r = fb.r
          i = fb.i
        }
        mode = 'birth'
      } else {
        continue
      }

      const endsByDivision = g.divisionFrame !== null && g.divisionFrame === g.end
      const fadeIn = g.parent !== null ? 1 : (tau - g.start + 1) / 4
      const fadeOut = endsByDivision ? 1 : (g.end - tau + 1) / 4
      let alpha: number
      if (mode === 'birth' && g.parent !== null) {
        alpha = 0.15 + 0.85 * u // con "trồi" ra khỏi vị trí mẹ
      } else if (mode === 'end' && endsByDivision) {
        alpha = 1 - 0.85 * u // mẹ tan vào xung phân bào
      } else {
        alpha = clamp(Math.min(fadeIn, fadeOut), 0, 1)
      }

      const ghost = st.sparseMode && (fa !== null ? !fa.labeled : fb !== null && !fb.labeled)

      const cell: VisCell = { g, x, y, z, r, i, alpha, ghost }
      vis.push(cell)
      visById.set(g.id, cell)
    }

    // --- vệt track (polyline quá khứ, mờ dần; đứt đoạn tại frame không nhãn) ---
    if (st.showTracks) {
      ctx.lineCap = 'round'
      ctx.lineWidth = Math.max(1, 1.1 * S)
      for (const g of tracks) {
        if (!(g.start <= f && g.end >= f - 5)) continue
        const from = Math.max(g.start, f - TRAIL_LENGTH)
        const to = Math.min(f, g.end)
        let px = 0
        let py = 0
        let has = false
        const denom = Math.max(1, to - from + 1)
        for (let t = from; t <= to; t++) {
          const fr = g.frames[t - g.start]
          if (st.sparseMode && !fr.labeled) {
            has = false
            continue
          }
          if (has) {
            const a = 0.03 + 0.34 * ((t - from + 1) / denom)
            ctx.strokeStyle = hsla(g.hue, 65, 55, a)
            ctx.beginPath()
            ctx.moveTo(px * scaleX, py * scaleY)
            ctx.lineTo(fr.x * scaleX, fr.y * scaleY)
            ctx.stroke()
          }
          px = fr.x
          py = fr.y
          has = true
        }
        // cạnh "sống": frame hiện tại → vị trí nội suy
        const v = visById.get(g.id)
        if (has && v !== undefined && !v.ghost) {
          ctx.strokeStyle = hsla(g.hue, 72, 60, 0.5 * v.alpha)
          ctx.beginPath()
          ctx.moveTo(px * scaleX, py * scaleY)
          ctx.lineTo(v.x * scaleX, v.y * scaleY)
          ctx.stroke()
        }
      }
    }

    // --- tế bào (vẽ từ sâu lên cạn; z ảnh hưởng kích thước + độ mờ) ---
    vis.sort((a, b) => b.z - a.z)
    for (const c of vis) {
      const dz = c.z / 63
      const depthScale = 1 - 0.32 * dz
      const depthAlpha = 1 - 0.42 * dz
      const R = Math.max(2.5, c.r * scaleX * depthScale)
      const bright = clamp(c.i * c.alpha * depthAlpha, 0, 1)
      const X = c.x * scaleX
      const Y = c.y * scaleY

      if (c.ghost) {
        // chưa gắn nhãn trong GT thưa: nét đứt, rất mờ
        ctx.setLineDash([4 * S, 4 * S])
        ctx.strokeStyle = hsla(c.g.hue, 35, 62, 0.3 * c.alpha)
        ctx.fillStyle = hsla(c.g.hue, 45, 60, 0.05 * c.alpha)
        ctx.lineWidth = 1.2 * S
        ctx.beginPath()
        ctx.arc(X, Y, R * 1.2, 0, Math.PI * 2)
        ctx.fill()
        ctx.stroke()
        ctx.setLineDash([])
      } else {
        const halo = R * 2.5
        const grad = ctx.createRadialGradient(X, Y, 0, X, Y, halo)
        grad.addColorStop(0, hsla(c.g.hue, 90, 74, 0.9 * bright))
        grad.addColorStop(0.32, hsla(c.g.hue, 85, 58, 0.38 * bright))
        grad.addColorStop(1, hsla(c.g.hue, 85, 55, 0))
        ctx.fillStyle = grad
        ctx.beginPath()
        ctx.arc(X, Y, halo, 0, Math.PI * 2)
        ctx.fill()
        // nhân sáng (pseudo-nucleus)
        ctx.fillStyle = hsla(c.g.hue, 96, 86, 0.85 * bright)
        ctx.beginPath()
        ctx.arc(X, Y, R * 0.42, 0, Math.PI * 2)
        ctx.fill()
      }

      // viền amber cho các tế bào lân cận phân bào
      if (st.showDivisions) {
        let age = -99
        if (c.g.parent !== null) age = tau - c.g.start
        else if (c.g.divisionFrame !== null) age = c.g.divisionFrame - tau
        if (age > -1.2 && age < 5) {
          const aa = clamp(1 - Math.max(0, age) / 5, 0, 1) * c.alpha
          ctx.strokeStyle = `rgba(251, 191, 36, ${(0.65 * aa).toFixed(3)})`
          ctx.lineWidth = 1.6 * S
          ctx.beginPath()
          ctx.arc(X, Y, R * 1.45 + 3 * S, 0, Math.PI * 2)
          ctx.stroke()
        }
      }
    }

    // --- xung phân bào: vòng tròn amber lan tỏa + nhãn "phân bào" ---
    if (st.showDivisions) {
      for (const g of tracks) {
        if (g.divisionFrame === null) continue
        const d = g.divisionFrame
        const p = (tau - d) / 1.9
        if (p <= 0 || p >= 1) continue
        const mf = g.frames[d - g.start]
        const X = mf.x * scaleX
        const Y = mf.y * scaleY
        const ease = 1 - Math.pow(1 - p, 3)
        const fade = Math.pow(1 - p, 1.6)
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

    // --- nhãn node (ID track) ---
    if (st.showLabels) {
      ctx.font = `${Math.round(10 * S)}px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace`
      ctx.textAlign = 'left'
      ctx.textBaseline = 'middle'
      ctx.shadowColor = 'rgba(0, 0, 0, 0.85)'
      ctx.shadowBlur = 3
      for (const c of vis) {
        const dz = c.z / 63
        const R = Math.max(2.5, c.r * scaleX * (1 - 0.32 * dz))
        ctx.fillStyle = c.ghost ? 'rgba(125, 145, 135, 0.7)' : 'rgba(167, 243, 208, 0.85)'
        ctx.fillText(String(c.g.id), c.x * scaleX + R + 4 * S, c.y * scaleY - R * 0.6)
      }
      ctx.shadowBlur = 0
      ctx.shadowColor = 'transparent'
    }

    // --- vignette ---
    const vg = ctx.createRadialGradient(
      w / 2,
      h / 2,
      Math.min(w, h) * 0.32,
      w / 2,
      h / 2,
      Math.max(w, h) * 0.72,
    )
    vg.addColorStop(0, 'rgba(0, 0, 0, 0)')
    vg.addColorStop(1, 'rgba(0, 0, 0, 0.5)')
    ctx.fillStyle = vg
    ctx.fillRect(0, 0, w, h)

    // --- HUD ---
    const pad = 12 * S
    const mono = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace'

    // trạng thái phát/tạm dừng
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

    // góc trên trái: t + thời gian sau thụ tinh
    ctx.textAlign = 'left'
    ctx.textBaseline = 'top'
    ctx.font = `600 ${Math.round(13 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(209, 250, 229, 0.92)'
    ctx.fillText(`t = ${String(f).padStart(2, '0')} / ${String(LAST_FRAME).padStart(2, '0')}`, pad + 18 * S, pad)
    ctx.font = `${Math.round(10.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(149, 202, 178, 0.62)'
    ctx.fillText(
      `${(MPF_BASE + tau * MPF_PER_FRAME).toFixed(1)} phút sau thụ tinh (mpf)`,
      pad + 18 * S,
      pad + 18 * S,
    )

    // góc trên phải: cường độ trung bình + kiểu dữ liệu
    ctx.textAlign = 'right'
    ctx.font = `600 ${Math.round(13 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(209, 250, 229, 0.92)'
    ctx.fillText(`⟨I⟩ = ${sim.meanIntensity[f]}`, w - pad, pad)
    ctx.font = `${Math.round(10.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(149, 202, 178, 0.62)'
    ctx.fillText('uint16 · max-projection Z', w - pad, pad + 18 * S)

    // góc dưới trái: shape dữ liệu + tỉ lệ voxel
    ctx.textAlign = 'left'
    ctx.font = `${Math.round(9.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(149, 202, 178, 0.45)'
    ctx.fillText('(T, Z, Y, X) = (60, 64, 256, 256) · uint16', pad, h - pad - 25 * S)
    ctx.fillText('xy 0.40625 µm/voxel · z 1.625 µm/voxel', pad, h - pad - 13 * S)

    // góc dưới phải: thước tỉ lệ 50 µm
    const barLen = 50 * scaleX
    const bx0 = w - pad - barLen
    const by0 = h - pad - 8 * S
    ctx.strokeStyle = 'rgba(209, 250, 229, 0.85)'
    ctx.lineWidth = 1.5 * S
    ctx.beginPath()
    ctx.moveTo(bx0, by0)
    ctx.lineTo(bx0 + barLen, by0)
    ctx.moveTo(bx0, by0 - 3 * S)
    ctx.lineTo(bx0, by0 + 3 * S)
    ctx.moveTo(bx0 + barLen, by0 - 3 * S)
    ctx.lineTo(bx0 + barLen, by0 + 3 * S)
    ctx.stroke()
    ctx.textAlign = 'center'
    ctx.textBaseline = 'bottom'
    ctx.font = `600 ${Math.round(10.5 * S)}px ${mono}`
    ctx.fillStyle = 'rgba(209, 250, 229, 0.85)'
    ctx.fillText('50 µm', bx0 + barLen / 2, by0 - 5 * S)

    tickRef.current += 1
  }, [sim])

  // ---- vòng lặp requestAnimationFrame ----
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

  // ---- thao tác điều khiển ----
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

  // ---- thống kê theo frame hiện tại (đúng ngữ nghĩa node/edge của cuộc thi) ----
  const stats = useMemo(() => {
    let nodes = 0
    let edges = 0
    let divs = 0
    for (const g of sim.tracks) {
      const labeledAt = (t: number): boolean => {
        if (!sparseMode) return true
        const fr = g.frames[t - g.start]
        return fr !== undefined && fr.labeled
      }
      if (g.start <= frame && frame <= g.end && labeledAt(frame)) nodes += 1
      if (g.start <= frame && frame + 1 <= g.end && labeledAt(frame) && labeledAt(frame + 1)) {
        edges += 1
      }
      if (g.divisionFrame !== null && g.divisionFrame <= frame) divs += 1
    }
    // mỗi phân bào tạo 2 cạnh (mẹ → 2 con) giữa frame d và d+1
    for (const d of sim.divisionFrames) {
      if (d === frame) edges += 2
    }
    return { nodes, edges, divs, intensity: sim.meanIntensity[frame] }
  }, [frame, sparseMode, sim])

  return (
    <Card className="gap-0 overflow-hidden py-0">
      <CardHeader className="px-4 pt-5 pb-4 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-emerald-500/25 bg-emerald-500/10">
            <Microscope className="size-5 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div className="min-w-0">
            <CardTitle className="text-base sm:text-lg">Trình mô phỏng theo dõi tế bào</CardTitle>
            <CardDescription className="mt-1 text-xs sm:text-sm">
              Mô phỏng dữ liệu kính hiển vi 3D + thời gian của phôi zebrafish — phát hiện tế bào
              (node), liên kết qua các khung hình (edge) và phát hiện phân bào (division).
            </CardDescription>
          </div>
        </div>
        <CardAction>
          <Badge
            variant="outline"
            className="gap-1.5 border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
          >
            <MousePointerClick className="size-3" />
            Mô phỏng tương tác
          </Badge>
        </CardAction>
      </CardHeader>

      {/* vùng canvas: full-bleed, bo góc theo Card */}
      <div
        ref={wrapRef}
        className="relative aspect-video w-full overflow-hidden bg-[#04100b]"
      >
        <canvas
          ref={canvasRef}
          className="absolute inset-0 h-full w-full"
          role="img"
          aria-label="Mô phỏng theo dõi tế bào phôi zebrafish: 60 khung hình, các tế bào phát huỳnh quang di chuyển, phân bào và một số không được gắn nhãn"
        />
      </div>

      {/* thanh điều khiển */}
      <div className="flex flex-col gap-4 px-4 pt-4 pb-5 sm:px-6">
        {/* phát / dừng / tua */}
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
        </div>

        {/* tốc độ + các công tắc hiển thị */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="flex items-center gap-2.5">
            <span className="hidden text-xs text-muted-foreground sm:inline">Tốc độ</span>
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
              <ToggleGroupItem value="0.5" aria-label="Tốc độ 0,5 lần">
                0.5×
              </ToggleGroupItem>
              <ToggleGroupItem value="1" aria-label="Tốc độ 1 lần">
                1×
              </ToggleGroupItem>
              <ToggleGroupItem value="2" aria-label="Tốc độ 2 lần">
                2×
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 sm:flex sm:flex-wrap sm:items-center sm:gap-x-5 sm:gap-y-2">
            <div className="flex items-center gap-2">
              <Switch id="tracking-demo-tracks" checked={showTracks} onCheckedChange={setShowTracks} />
              <Label htmlFor="tracking-demo-tracks" className="cursor-pointer text-xs text-muted-foreground">
                Hiện track
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="tracking-demo-labels" checked={showLabels} onCheckedChange={setShowLabels} />
              <Label htmlFor="tracking-demo-labels" className="cursor-pointer text-xs text-muted-foreground">
                Hiện nhãn node
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                id="tracking-demo-divisions"
                checked={showDivisions}
                onCheckedChange={setShowDivisions}
              />
              <Label htmlFor="tracking-demo-divisions" className="cursor-pointer text-xs text-muted-foreground">
                Hiện phân bào
              </Label>
            </div>
            <div className="flex items-center gap-2">
              <Switch id="tracking-demo-sparse" checked={sparseMode} onCheckedChange={setSparseMode} />
              <Label htmlFor="tracking-demo-sparse" className="cursor-pointer text-xs text-muted-foreground">
                Chế độ GT thưa
              </Label>
            </div>
          </div>
        </div>

        {/* thống kê frame hiện tại */}
        <div className="flex flex-wrap items-center gap-2">
          <StatChip
            icon={<CircleDot className="size-3.5" />}
            label="Node"
            value={String(stats.nodes)}
            tone="emerald"
          />
          <StatChip
            icon={<Spline className="size-3.5" />}
            label="Cạnh"
            value={String(stats.edges)}
            tone="teal"
          />
          <StatChip
            icon={<GitBranch className="size-3.5" />}
            label="Phân bào"
            value={`${stats.divs}/${sim.divisionFrames.length}`}
            tone="amber"
          />
          <StatChip
            icon={<Activity className="size-3.5" />}
            label="⟨I⟩ TB"
            value={String(stats.intensity)}
            tone="emerald"
          />
        </div>

        {/* chú giải */}
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t pt-3 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-2">
            <span
              className="size-2.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.9)]"
              aria-hidden
            />
            Tế bào (node)
          </span>
          <span className="inline-flex items-center gap-2">
            <span
              className="size-2.5 rounded-full border-2 border-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.7)]"
              aria-hidden
            />
            Phân bào (division)
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="size-2.5 rounded-full border border-dashed border-emerald-500/60" aria-hidden />
            Chưa gắn nhãn
          </span>
          <span className="inline-flex items-center gap-2">
            <span className="h-0.5 w-5 rounded-full bg-emerald-400/70" aria-hidden />
            Cạnh liên kết (edge)
          </span>
          <span className="ml-auto hidden text-[11px] text-muted-foreground/70 lg:inline">
            Mẹo: kéo thanh thời gian để tua · tắt chế độ GT thưa để xem chú thích dày đặc
          </span>
        </div>
      </div>
    </Card>
  )
}

// ---------------------------------------------------------------------------
// Chip thống kê nhỏ
// ---------------------------------------------------------------------------

interface StatChipProps {
  icon: ReactNode
  label: string
  value: string
  tone: 'emerald' | 'teal' | 'amber'
}

function StatChip({ icon, label, value, tone }: StatChipProps) {
  const toneClass =
    tone === 'emerald'
      ? 'text-emerald-600 dark:text-emerald-300'
      : tone === 'teal'
        ? 'text-teal-600 dark:text-teal-300'
        : 'text-amber-600 dark:text-amber-300'
  return (
    <div className="flex items-center gap-2 rounded-lg border bg-muted/30 px-2.5 py-1.5">
      <span className={toneClass}>{icon}</span>
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`font-mono text-sm font-semibold tabular-nums ${toneClass}`}>{value}</span>
    </div>
  )
}
