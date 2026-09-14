'use client'

/**
 * Trình mô phỏng & chấm điểm bài nộp
 * Kaggle: "Biohub - Cell Tracking During Development"
 *
 * Môi trường mô phỏng nội bộ các phiên bản pipeline ver-6 / ver-7 / ver-8:
 *  - ver 8 · Phase D re-parenting (ĐANG CHẠY trên Kaggle GPU T4×2): nền
 *    ver-7 + DivNet RANK-ONLY W=15 µm (giữ NGUYÊN gate production tau
 *    0.6 / diverge 2.25 — khác ver-7b đã thất bại vì nới gate) + re-parenting
 *    division recovery (tháo cạnh sai Y→D2, nối mẹ thật M→D2 khi DivNet +
 *    geometry + DeepCenter đồng thuận) + PPSWEEP 16 candidates — phần mô
 *    phỏng chạy trên nền ensemble ver-7
 *  - ver 7 · port notebook Reyhan 0.947 (public LB 0.947 ✓): nền ver-6 +
 *    DeepCenter veto (bỏ node sửa chữa có center-prior thấp) + TTA 8-view
 *    × 3 chip + PPSWEEP chọn tight55 (MOTION_RELINK_TIGHT_UM 5.5)
 *  - ver 6 · Kaggle 0.945 deterministic ×2 (kernel biohub-ver6): 2 lượt phát
 *    hiện độc lập (primary + seed 314159) + fusion theo src + Hungarian gate
 *    7.2 µm + safe-div (mẹ ≤ 6.0 µm, chị em ≤ 11.5 µm, khối lượng hợp lý,
 *    xác nhận động học sau 1 khung) + retention guard (gap ≤ 2,
 *    bước ≤ 3.6 + 0.4×gap µm)
 * rồi chấm điểm bằng đúng tinh thần metric cuộc thi:
 *   + Ghép node tối ưu (Hungarian) trong ngưỡng 7.0 µm theo khoảng cách vật lý
 *   + Cạnh TP/FP/FN, Edge Jaccard điều chỉnh (phạt node dự đoán thừa)
 *   + Division Jaccard theo dòng con (lineage)
 *   + score = adj_edge_jaccard + 0.1 × division_jaccard (có thể vượt 1.0)
 * Kèm 2 bảng số liệu KAGGLE THẬT: kết quả các phiên bản đã nộp / đang chạy
 * và 8 video held-out của validator ver-7 + thanh leaderboard.
 * Ngoài ra còn chế độ "Tùy chỉnh" — mô hình tham số giả lập tracker
 * nearest-neighbor để thí nghiệm các loại lỗi.
 */

import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
  type ReactNode,
} from 'react'
import {
  Activity,
  CircleDot,
  Crosshair,
  Database,
  Dices,
  Gauge,
  GitBranch,
  Microscope,
  Pause,
  Play,
  RotateCcw,
  Spline,
  Target,
  Trophy,
  Video,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

import {
  HELDOUT_MICRO_ADJEJ,
  HELDOUT_STEMS,
  KAGGLE_RESULTS,
  LB_CONTEXT,
  type KaggleRunStatus,
} from '@/lib/competition-data'

import {
  buildGtGraph,
  buildSimulation,
  clamp,
  dist3,
  gauss,
  genVer6Ensemble,
  genVer7Ensemble,
  lerp,
  mulberry32,
  scoreDetections,
  T,
  LAST_FRAME,
  WORLD_W,
  WORLD_H,
  type Analysis,
  type Det,
  type EdgeRef,
  type EnsembleRun,
  type GtGraph,
  type SimData,
} from '@/lib/tracking-pipeline'

/** Tốc độ phát cơ bản (khung hình/giây ở 1×) */
const BASE_FPS = 2.5

/** Thời gian mô phỏng: 2.5 hpf + 1.5 phút/khung hình */
const MPF_BASE = 150
const MPF_PER_FRAME = 1.5

// ---------------------------------------------------------------------------
// Chế độ "Tùy chỉnh": giả lập nearest-neighbor tracker bằng tham số
// ---------------------------------------------------------------------------

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
        mass: Math.round(f.i * 27),
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
        mass: 18000,
        src: null,
      })
    }
    out.push(dets)
  }
  return out
}

/** Chấm điểm chế độ tùy chỉnh: greedy nearest-neighbor + phân bào giả lập */
function analyzeCustom(
  sim: SimData,
  gt: GtGraph,
  p: Params,
  seed: number,
): Analysis {
  const det = genDetections(sim, p, seed)
  const edgeRefs: EdgeRef[] = []
  for (let t = 0; t < T - 1; t++) {
    const A = det[t]!
    const B = det[t + 1]!
    const pairs: { ai: number; bi: number; d: number }[] = []
    for (let ai = 0; ai < A.length; ai++) {
      for (let bi = 0; bi < B.length; bi++) {
        const da = A[ai]!
        const db = B[bi]!
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
      edgeRefs.push({ at: t, ai: pr.ai, bt: t + 1, bi: pr.bi })
    }
    // phát hiện phân bào: cho phép 1 node nối thêm "con thứ 2" nằm gần
    if (p.division) {
      for (const [ai, bi1] of primary) {
        const da = A[ai]!
        const db1 = B[bi1]!
        for (let bi = 0; bi < B.length; bi++) {
          if (usedB.has(bi)) continue
          const db = B[bi]!
          const d2 = dist3(da.x, da.y, da.z, db.x, db.y, db.z)
          const d3v = dist3(db1.x, db1.y, db1.z, db.x, db.y, db.z)
          if (d2 <= p.linkUm && d3v <= p.linkUm) {
            usedB.add(bi)
            edgeRefs.push({ at: t, ai, bt: t + 1, bi })
          }
        }
      }
    }
  }
  return scoreDetections(sim, gt, det, edgeRefs)
}

/** Khung rỗng dự phòng — chống crash khi index ngoài phạm vi */
const EMPTY_FRAME_VIEW: Analysis['frames'][number] = { gtEdges: [], predEdges: [] }

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

type Mode = 'ver8' | 'ver6' | 'ver7' | 'custom'

const MODE_LABEL: Record<Mode, string> = {
  ver8: 'Ver 8 · đang chạy',
  ver7: 'Ver 7 · Kaggle 0.947',
  ver6: 'Ver 6 · Kaggle 0.945',
  custom: 'Tùy chỉnh',
}

/** Các phiên bản ensemble chạy trên cùng dữ liệu (mặc định Ver 8 — tái dùng nền ver-7) */
const ENSEMBLE_RUNS = ['ver6', 'ver7'] as const
type EnsembleKey = (typeof ENSEMBLE_RUNS)[number]

/** Pipeline chips hiển thị cho từng phiên bản (đúng kernel biohub-ver6/ver7/ver8) */
const VERSION_INFO: Record<Exclude<Mode, 'custom'>, string[]> = {
  ver8: [
    'nền ver-7 (dual-seed + fusion + safe-div + retention + DeepCenter + TTA)',
    'divnet division rank: RANK-ONLY W=15 µm · giữ gate gốc tau 0.6 / diverge 2.25',
    're-parenting: tháo cạnh sai Y→D2 · nối mẹ thật M→D2',
    'đồng thuận DivNet + geometry + DeepCenter — 6/12 sự kiện GT (≈ +0.0077 điểm/ca)',
    'PPSWEEP 16 candidates: 6 rp-* (tuning + rp-off escape) + 7 gốc + 3 adjEJ mới',
    'validator held-out tự chọn theo gate ±0.0005 adjEJ',
  ],
  ver6: [
    '2 lượt phát hiện độc lập (primary + seed 314159)',
    'fusion theo src: cả hai thấy → trung bình vị trí',
    '1 lượt thấy → cửa sổ mờ, nhân dimFactor',
    'Hungarian gate 7.2 µm + motion EMA',
    'safe-div: mẹ ≤ 6.0 µm · chị em ≤ 11.5 µm',
    'khối lượng hợp lý + xác nhận động học 1 khung',
    'retention guard: gap ≤ 2 · bước ≤ 3.6 + 0.4×gap µm',
  ],
  ver7: [
    'nền ver-6 (dual-seed + fusion + safe-div + retention)',
    'DeepCenter veto: bỏ node center-prior thấp',
    'TTA 8-view × 3 chip',
    'PPSWEEP chọn tight55 (MOTION_RELINK_TIGHT_UM 5.5)',
    'port nguyên văn notebook Reyhan public LB 0.947',
    'chỉ vá 5 dòng env path → dataset pilkwang',
  ],
}

/** Trạng thái Kaggle → badge tương ứng */
const STATUS_BADGE: Record<KaggleRunStatus, { label: string; cls: string }> = {
  COMPLETE: {
    label: 'COMPLETE',
    cls: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
  },
  PENDING: {
    label: 'ĐANG CHẤM',
    cls: 'border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300',
  },
  RUNNING: {
    label: 'ĐANG CHẠY',
    cls: 'border-teal-500/40 bg-teal-500/10 text-teal-700 dark:text-teal-300',
  },
}

/** Cache ensemble theo seed — module scope, dữ liệu deterministic */
const ENSEMBLE_CACHE = new Map<string, Record<EnsembleKey, EnsembleRun>>()

export default function TrackingDemo() {
  const [seed, setSeed] = useState(20260911)
  const sim = useMemo(() => buildSimulation(seed), [seed])

  const [mode, setMode] = useState<Mode>('ver8')
  const [params, setParams] = useState<Params>({ ...DEFAULT_PARAMS })
  const [sparseMode, setSparseMode] = useState(true)

  const gtGraph = useMemo(() => buildGtGraph(sim, sparseMode), [sim, sparseMode])

  // 2 phiên bản ensemble chạy trên cùng một chuỗi thể tích — cache theo seed
  const ensembles = useMemo(() => {
    const key = `${seed}`
    let v = ENSEMBLE_CACHE.get(key)
    if (v === undefined) {
      v = {
        ver6: genVer6Ensemble(sim, seed),
        ver7: genVer7Ensemble(sim, seed),
      }
      if (ENSEMBLE_CACHE.size > 8) ENSEMBLE_CACHE.clear()
      ENSEMBLE_CACHE.set(key, v)
    }
    return v
  }, [seed, sim])

  const ensembleAnalyses = useMemo(() => {
    const out = {} as Record<EnsembleKey, Analysis>
    for (const v of ENSEMBLE_RUNS) {
      out[v] = scoreDetections(sim, gtGraph, ensembles[v].det, ensembles[v].edges)
    }
    return out
  }, [ensembles, gtGraph, sim])

  const customAnalysis = useMemo(
    () => analyzeCustom(sim, gtGraph, params, seed),
    [sim, gtGraph, params, seed],
  )

  const analysis: Analysis =
    mode === 'custom'
      ? customAnalysis
      : ensembleAnalyses[mode === 'ver8' ? 'ver7' : mode]

  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState(1)
  const [frame, setFrame] = useState(0)
  const [showGt, setShowGt] = useState(true)
  const [showPred, setShowPred] = useState(true)
  const [showEdges, setShowEdges] = useState(true)
  const [showLabels, setShowLabels] = useState(false)

  // Thời gian chạy (ms) do performance.now() đo — khác nhau giữa Node (SSR) và
  // browser (hydrate). useSyncExternalStore trả về false trong SSR / lần render
  // hydrate đầu tiên (server snapshot) và true ngay sau đó — text hai phía khớp
  // nhau, tránh lỗi hydration mismatch mà không cần setState trong effect.
  const msReady = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  )
  const fmtMs = useCallback(
    (v: number) => (msReady ? `${Math.round(v)} ms` : '… ms'),
    [msReady],
  )

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
    // Vô hiệu hoá NaN/âm (state bị nhiễu) → luôn cho ra chỉ số khung hợp lệ
    const tauRaw = timeRef.current
    const tau = Number.isFinite(tauRaw) ? Math.max(0, tauRaw) : 0
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
    const fd = an.frames[f] ?? EMPTY_FRAME_VIEW
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
        let ii: number
        if (fa !== null && fb !== null) {
          x = lerp(fa.x, fb.x, u)
          y = lerp(fa.y, fb.y, u)
          z = lerp(fa.z, fb.z, u)
          r = lerp(fa.r, fb.r, u)
          labeled = fa.labeled
          ii = lerp(fa.i, fb.i, u)
        } else if (fa !== null) {
          x = fa.x; y = fa.y; z = fa.z; r = fa.r
          labeled = fa.labeled
          ii = fa.i
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
          ii = fb!.i
        }

        const X = x * scaleX
        const Y = y * scaleY
        const dz = z / 63
        const R = Math.max(2.5, r * scaleX * (1 - 0.28 * dz))
        const ghost = st.sparse && !labeled
        // tế bào trong "cửa sổ mờ" (rời mặt phẳng chiếu) tối hơn rõ rệt
        const dimF = clamp(Math.pow(ii / 1800, 0.6), 0.22, 1.08)

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
          const aBase = (0.9 - 0.35 * dz) * dimF
          g.addColorStop(0, `rgba(209, 250, 229, ${aBase.toFixed(3)})`)
          g.addColorStop(0.45, `rgba(52, 211, 153, ${(aBase * 0.75).toFixed(3)})`)
          g.addColorStop(1, 'rgba(6, 78, 59, 0)')
          ctx.fillStyle = g
          ctx.beginPath()
          ctx.arc(X, Y, R, 0, Math.PI * 2)
          ctx.fill()
          ctx.fillStyle = `rgba(236, 254, 255, ${((0.85 - 0.3 * dz) * dimF).toFixed(3)})`
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
        if (!Number.isFinite(timeRef.current) || timeRef.current >= LAST_FRAME) {
          timeRef.current = 0
        }
      }
      draw()
      const tauNow = timeRef.current
      const fi = Number.isFinite(tauNow)
        ? Math.min(LAST_FRAME, Math.max(0, Math.floor(tauNow)))
        : 0
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
              Chạy <span className="font-semibold text-emerald-700 dark:text-emerald-300">thật</span>{' '}
              thuật toán từng phiên bản nộp bài (port JS từ notebook Kaggle) trên
              thể tích 3D tổng hợp của phôi zebrafish, rồi chấm điểm đúng metric
              cuộc thi. Ver 8 (Phase D re-parenting) đang chạy trên Kaggle
              (GPU T4×2) — phần mô phỏng dưới đây chạy trên nền ver-7. Ver 7
              (port notebook Reyhan — public LB 0.947, hạng 342/3523) và Ver 6
              (Kaggle 0.945 deterministic) cho số GẦN NHAU trên cùng dữ liệu —
              đúng bằng chứng paired A/B thật: ΔadjEJ +0.0000. Đổi phiên bản để
              so sánh, hoặc dùng chế độ{' '}
              <span className="font-semibold text-teal-700 dark:text-teal-300">
                Tùy chỉnh
              </span>{' '}
              để thí nghiệm các loại lỗi.
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
              const n = v === '' ? Number.NaN : Number(v)
              if (Number.isFinite(n) && n > 0) setSpeed(n)
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

        {/* 5 · phiên bản thuật toán nộp bài */}
        <div className="rounded-xl border bg-muted/30 p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Wand2 className="size-4 text-emerald-600 dark:text-emerald-400" />
              Thuật toán nộp bài (theo phiên bản)
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <ToggleGroup
                type="single"
                variant="outline"
                size="sm"
                value={mode}
                onValueChange={(v) => {
                  if (v === 'ver8' || v === 'ver6' || v === 'ver7' || v === 'custom') setMode(v)
                }}
                aria-label="Chọn phiên bản thuật toán"
                className="flex-wrap"
              >
                <ToggleGroupItem value="ver8" aria-label="Ver 8, Phase D re-parenting division recovery — đang chạy trên Kaggle">
                  Ver 8 · đang chạy
                </ToggleGroupItem>
                <ToggleGroupItem value="ver7" aria-label="Ver 7, port notebook Reyhan — public LB 0.947">
                  Ver 7 · 0.947
                </ToggleGroupItem>
                <ToggleGroupItem value="ver6" aria-label="Ver 6, dual-seed ensemble — Kaggle 0.945 deterministic">
                  Ver 6 · Kaggle 0.945
                </ToggleGroupItem>
                <ToggleGroupItem value="custom" aria-label="Chế độ tùy chỉnh tham số">
                  Tùy chỉnh
                </ToggleGroupItem>
              </ToggleGroup>
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

          {mode === 'custom' ? (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-1.5">
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
            </>
          ) : (
            <>
              {/* console log mô phỏng Kaggle — 8 dòng (ver-8) / 10 dòng (ver-7) / 9 dòng (ver-6) */}
              <pre className="mb-4 max-h-72 overflow-auto rounded-lg bg-[#04100b] p-3 font-mono text-[11px] leading-relaxed text-emerald-200/90">
                {(() => {
                  const run = ensembles[mode === 'ver8' ? 'ver7' : mode]
                  const st = run.stats
                  const base = [
                    `[ensemble] 2 lượt phát hiện độc lập · primary + seed 314159 · ${st.rawA} + ${st.rawB} node`,
                    `[fusion] cả hai thấy ${st.fusedBoth} (trung bình vị trí) · 1 lượt ${st.fusedSingle} (dimFactor)`,
                    `[link] Hungarian gate 7.2 µm · ${st.edges} cạnh · retention nối ${st.retPairs} track · +${st.retInterp} node`,
                    `[safe-div] xác nhận ${st.divisions} · từ chối động học ${st.divRejDyn} · mất con ${st.divRejLost}`,
                  ]
                  if (mode === 'ver8') {
                    return [
                      ...base,
                      `[ver8·divnet] division rank RANK-ONLY W=15 µm · giữ NGUYÊN gate production tau 0.6 / diverge 2.25 (khác ver-7b nới gate đã thất bại)`,
                      `[ver8·re-parent] tháo cạnh sai Y→D2 · nối mẹ thật M→D2 · DivNet + geometry + DeepCenter đồng thuận · 6/12 sự kiện GT (≈ +0.0077 điểm/ca)`,
                      `[ppsweep] 16 candidates: 6 rp-* (re-parent tuning + rp-off escape) + 7 gốc + 3 adjEJ mới — validator held-out tự chọn (gate ±0.0005 adjEJ)`,
                      `[submit] biohub-ver8 v1 · GPU T4×2 · push 21:20 14/9 → ĐANG CHẠY (~2,5–3 h)`,
                    ].join('\n')
                  }
                  if (mode === 'ver7') {
                    return [
                      ...base,
                      `[deepcenter] veto ${st.vetoed} node center-prior thấp`,
                      `[tta] 8-view × 3 chip — tái xác nhận tâm node`,
                      `[ppsweep] chọn tight55 · MOTION_RELINK_TIGHT_UM 5.5`,
                      `[validator] proxy held-out 0.9490 → 0.9511 (tight55) · adjEJ micro 0.9345`,
                      `[kaggle] 241.356 dòng · sha256 d34533806b3153dd… · T4×2 117 phút COMPLETE`,
                      `[submit] 56217216 → PUBLIC LB 0.947 ✓ (+0.002 so với ver-6) · hạng 342 — mục tiêu ver-8: ≥ 0.948`,
                    ].join('\n')
                  }
                  return [
                    ...base,
                    `[validator] 4 video rule cũ · adjEJ 0.9230 · divJ 0.2000 · PROXY 0.9430`,
                    `[kaggle] 241.761 dòng (122.975 node + 118.786 cạnh) · 200 phân bào / 4 phim (62/51/9/78)`,
                    `[run] T4×2 · v2 2147 s · v3 2290 s — deterministic khớp tuyệt đối`,
                    `[submit] 56207468 (v2) → public LB 0.945`,
                    `[submit] 56210873 (v3) → public LB 0.945 ✓ deterministic`,
                  ].join('\n')
                })()}
              </pre>

              {/* pipeline của phiên bản đang chọn */}
              <div className="mb-4 flex flex-wrap items-center gap-1.5">
                <span className="mr-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Pipeline
                </span>
                {VERSION_INFO[mode].map((s) => (
                  <span
                    key={s}
                    className="rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2 py-0.5 font-mono text-[10px] text-emerald-700 dark:text-emerald-300"
                  >
                    {s}
                  </span>
                ))}
              </div>

              {/* so sánh 2 phiên bản trên cùng dữ liệu */}
              <div className="overflow-x-auto">
                <table className="w-full min-w-[440px] border-collapse text-left text-xs">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="py-2 pr-3 font-medium">Trên cùng dữ liệu này</th>
                      {ENSEMBLE_RUNS.map((v) => (
                        <th
                          key={v}
                          className={`px-2.5 py-2 font-medium ${mode === v ? 'rounded-t-lg bg-emerald-500/10' : ''}`}
                        >
                          {MODE_LABEL[v]}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="font-mono tabular-nums">
                    {(() => {
                      const a = ensembleAnalyses
                      const ms = ENSEMBLE_RUNS.map((v) => a[v].metrics)
                      /** So sánh theo SỐ, hiển thị theo chuỗi — đánh dấu ▲ ô tốt nhất */
                      const cells = (
                        getNum: (m: (typeof ms)[number]) => number | null,
                        fmt: (m: (typeof ms)[number]) => string,
                        better: 'max' | 'min' = 'max',
                      ) => {
                        const vals = ms.map((m) => getNum(m))
                        let bi = -1
                        if (vals.every((v) => v !== null)) {
                          const nums = vals as number[]
                          for (let k = 0; k < nums.length; k++) {
                            if (nums[k] !== nums[0]) bi = 0 // có khác biệt mới đánh dấu
                          }
                          if (bi === 0) {
                            for (let k = 1; k < nums.length; k++) {
                              if (better === 'max' ? nums[k]! > nums[bi]! : nums[k]! < nums[bi]!) bi = k
                            }
                          }
                        }
                        return ENSEMBLE_RUNS.map((_, k) => ({
                          text: fmt(ms[k]!),
                          best: k === bi,
                        }))
                      }
                      const tpFpFn = (m: (typeof ms)[number]): string => `${m.tp} · ${m.fp} · ${m.fn}`
                      const rows: { label: string; c: { text: string; best: boolean }[] }[] = [
                        { label: 'Phát hiện node (recall)', c: cells((m) => m.nodeRecall, (m) => m.nodeRecall.toFixed(3)) },
                        { label: 'Edge Jaccard (điều chỉnh)', c: cells((m) => m.adjEJ, (m) => m.adjEJ.toFixed(3)) },
                        { label: 'Division Jaccard', c: cells((m) => m.divJ, (m) => m.divJ.toFixed(3)) },
                        { label: 'Cạnh TP', c: cells((m) => m.tp, tpFpFn) },
                        { label: 'Phân bào TP', c: cells((m) => m.divTP, (m) => `${m.divTP} · ${m.divFP} · ${m.divFN}`) },
                        { label: 'Node thừa (spurious)', c: cells((m) => m.spurious, (m) => String(m.spurious), 'min') },
                        { label: 'Thời gian 60 khung', c: cells(() => null, (m) => fmtMs(ensembles[ENSEMBLE_RUNS[ms.indexOf(m)]].stats.ms)) },
                        { label: 'Điểm tổng (mô phỏng)', c: cells((m) => m.combined, (m) => m.combined.toFixed(3)) },
                      ]
                      return rows.map((r) => (
                        <tr key={r.label} className="border-b border-border/50 last:border-0">
                          <td className="py-1.5 pr-3 font-sans text-muted-foreground">{r.label}</td>
                          {ENSEMBLE_RUNS.map((v, k) => (
                            <td
                              key={v}
                              className={`px-2.5 py-1.5 ${mode === v ? 'bg-emerald-500/10 font-bold' : ''}`}
                            >
                              {r.c[k]!.text}
                              {r.c[k]!.best && (
                                <span className="ml-1 font-sans text-[10px] text-emerald-600 dark:text-emerald-400" aria-label="tốt nhất">
                                  ▲
                                </span>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))
                    })()}
                  </tbody>
                </table>
              </div>
              <p className="mt-2.5 text-[11px] leading-snug text-muted-foreground">
                Cùng một thể tích tổng hợp (seed {seed}) chạy qua cả 2 phiên bản —
                khác biệt đến từ thuật toán, không phải dữ liệu. Trên Kaggle thật,
                paired A/B trên 4 video chung cho{' '}
                <span className="font-mono font-semibold text-foreground">
                  ΔadjEJ +0.0000 (CI95 ±0.0001)
                </span>{' '}
                — hai phiên bản KHÔNG regression so với nhau (guards 5/5); điểm
                tuyệt đối trên mô phỏng sẽ khác data thật.
              </p>
            </>
          )}
        </div>

        {/* 6 · số liệu Kaggle thật */}
        <div className="rounded-xl border bg-muted/30 p-4 sm:p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Database className="size-4 text-emerald-600 dark:text-emerald-400" />
              Số liệu Kaggle thật — các phiên bản đã nộp / đang chạy
            </div>
            <Badge
              variant="outline"
              className="border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
            >
              cập nhật từ kernel &amp; submission thật
            </Badge>
          </div>

          <div className="overflow-x-auto rounded-lg border bg-background">
            <div className="max-h-96 overflow-y-auto">
              <Table className="min-w-[760px]">
                <TableHeader className="sticky top-0 z-10 bg-background">
                  <TableRow>
                    <TableHead className="text-xs">Phiên bản</TableHead>
                    <TableHead className="text-xs">Tham chiếu Kaggle</TableHead>
                    <TableHead className="text-right text-xs">Public LB</TableHead>
                    <TableHead className="text-center text-xs">Trạng thái</TableHead>
                    <TableHead className="text-right text-xs">Run</TableHead>
                    <TableHead className="text-right text-xs">Dòng</TableHead>
                    <TableHead className="text-right text-xs">Proxy</TableHead>
                    <TableHead className="text-right text-xs">adjEJ</TableHead>
                    <TableHead className="text-right text-xs">divJ</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {KAGGLE_RESULTS.map((r) => {
                    const sb = STATUS_BADGE[r.status]
                    return (
                      <Fragment key={r.id}>
                        <TableRow>
                          <TableCell className="py-2 text-xs font-semibold">{r.label}</TableCell>
                          <TableCell className="py-2 font-mono text-[11px] text-muted-foreground">
                            {r.kaggleRef}
                          </TableCell>
                          <TableCell className="py-2 text-right font-mono text-xs font-semibold tabular-nums">
                            {r.lbScore === null ? '—' : r.lbScore.toFixed(3)}
                          </TableCell>
                          <TableCell className="py-2 text-center">
                            <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${sb.cls}`}>
                              {sb.label}
                            </span>
                          </TableCell>
                          <TableCell className="py-2 text-right font-mono text-xs tabular-nums">
                            {r.runSeconds === null ? '—' : `${Math.round(r.runSeconds / 60)}′`}
                          </TableCell>
                          <TableCell className="py-2 text-right font-mono text-xs tabular-nums">
                            {r.submissionRows === null ? '—' : new Intl.NumberFormat('vi-VN').format(r.submissionRows)}
                          </TableCell>
                          <TableCell className="py-2 text-right font-mono text-xs tabular-nums">
                            {r.proxy === null ? '—' : r.proxy.toFixed(4)}
                          </TableCell>
                          <TableCell className="py-2 text-right font-mono text-xs tabular-nums">
                            {r.adjEJ === null ? '—' : r.adjEJ.toFixed(4)}
                          </TableCell>
                          <TableCell className="py-2 text-right font-mono text-xs tabular-nums">
                            {r.divJ === null ? '—' : r.divJ.toFixed(3)}
                          </TableCell>
                        </TableRow>
                        <TableRow className="hover:bg-transparent">
                          <TableCell colSpan={9} className="py-1.5 pb-2.5">
                            <ul className="list-none space-y-0.5 text-[11px] leading-snug text-muted-foreground">
                              {r.notes.map((n) => (
                                <li key={n}>· {n}</li>
                              ))}
                            </ul>
                          </TableCell>
                        </TableRow>
                      </Fragment>
                    )
                  })}
                </TableBody>
              </Table>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* 8 video held-out của validator ver-7 */}
            <div className="rounded-lg border bg-background p-3.5">
              <div className="mb-2.5 flex items-center gap-2 text-sm font-semibold">
                <Video className="size-4 text-teal-600 dark:text-teal-400" aria-hidden />
                Validator ver-7 — 8 video held-out
              </div>
              <div className="overflow-x-auto">
                <Table className="min-w-[280px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="text-xs">stem (dataset)</TableHead>
                      <TableHead className="text-xs">phôi</TableHead>
                      <TableHead className="text-right text-xs">adjEJ</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {HELDOUT_STEMS.map((v) => (
                      <TableRow key={v.stem}>
                        <TableCell className="py-1.5 font-mono text-[11px]">{v.stem}</TableCell>
                        <TableCell className="py-1.5 font-mono text-[11px] text-muted-foreground">
                          {v.embryo}
                        </TableCell>
                        <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                          {v.estimated ? (
                            <span title="video chưa có số riêng — dùng adjEJ micro của 8 video">
                              {HELDOUT_MICRO_ADJEJ.toFixed(4)} *
                            </span>
                          ) : (
                            <span className="font-semibold">{v.adjEJDisplay.toFixed(4)}</span>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                    <TableRow className="bg-muted/50 font-semibold">
                      <TableCell className="py-1.5 text-xs">micro (8 video)</TableCell>
                      <TableCell className="py-1.5 text-xs text-muted-foreground">—</TableCell>
                      <TableCell className="py-1.5 text-right font-mono text-xs tabular-nums">
                        {HELDOUT_MICRO_ADJEJ.toFixed(4)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </div>
              <p className="mt-2 text-[11px] leading-snug text-muted-foreground">
                * 4 video chưa công bố số riêng — hiển thị adjEJ micro{' '}
                {HELDOUT_MICRO_ADJEJ.toFixed(4)} của cả 8 video (scorer 075fc5f).
                Phân bào: div 0/0/12 (tp/fp/evaluable).
              </p>
            </div>

            {/* thanh leaderboard */}
            <div className="rounded-lg border bg-background p-3.5">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
                <Trophy className="size-4 text-amber-500" aria-hidden />
                Bối cảnh public leaderboard
              </div>
              {(() => {
                const LO = 0.9
                const HI = 0.975
                const pos = (s: number): string =>
                  `${clamp(((s - LO) / (HI - LO)) * 100, 2, 98).toFixed(1)}%`
                return (
                  <div>
                    <div
                      className="relative h-10"
                      role="img"
                      aria-label={`Leaderboard: đội mình ${LB_CONTEXT.ourScore} xếp hạng ${LB_CONTEXT.ourRank}; bức tường ${LB_CONTEXT.wallScore} của ${LB_CONTEXT.wallTeams} đội; top 1 ${LB_CONTEXT.topScore}`}
                    >
                      <div className="absolute inset-x-0 top-4 h-2 rounded-full bg-muted" />
                      <div
                        className="absolute top-4 h-2 rounded-l-full bg-gradient-to-r from-emerald-500/70 to-emerald-400"
                        style={{ left: 0, width: pos(LB_CONTEXT.ourScore) }}
                      />
                      {[
                        { s: LB_CONTEXT.ourScore, label: 'team ta', cls: 'bg-emerald-500', txt: 'text-emerald-700 dark:text-emerald-300' },
                        { s: LB_CONTEXT.wallScore, label: 'bức tường', cls: 'bg-amber-500', txt: 'text-amber-700 dark:text-amber-300' },
                        { s: LB_CONTEXT.topScore, label: 'top 1', cls: 'bg-rose-500', txt: 'text-rose-700 dark:text-rose-300' },
                      ].map((mk) => (
                        <div
                          key={mk.label}
                          className="absolute flex -translate-x-1/2 flex-col items-center"
                          style={{ left: pos(mk.s), top: 0 }}
                        >
                          <span className={`font-mono text-[10px] font-bold tabular-nums ${mk.txt}`}>
                            {mk.s.toFixed(3)}
                          </span>
                          <span className={`mt-0.5 size-2.5 rounded-full ring-2 ring-background ${mk.cls}`} />
                        </div>
                      ))}
                    </div>
                    <ul className="mt-2 space-y-1.5 text-xs">
                      <li className="flex items-center justify-between gap-2">
                        <span className="text-muted-foreground">
                          <span className="mr-1.5 inline-block size-2 rounded-full bg-emerald-500" aria-hidden />
                          Team ta — ver-6 0.945
                        </span>
                        <span className="font-mono font-semibold tabular-nums">
                          hạng ≈ {LB_CONTEXT.ourRank}
                        </span>
                      </li>
                      <li className="flex items-center justify-between gap-2">
                        <span className="text-muted-foreground">
                          <span className="mr-1.5 inline-block size-2 rounded-full bg-amber-500" aria-hidden />
                          Bức tường {LB_CONTEXT.wallScore.toFixed(3)} — 360 đội copy notebook Reyhan
                        </span>
                        <span className="font-mono font-semibold tabular-nums">
                          {LB_CONTEXT.wallTeams} đội
                        </span>
                      </li>
                      <li className="flex items-center justify-between gap-2">
                        <span className="text-muted-foreground">
                          <span className="mr-1.5 inline-block size-2 rounded-full bg-rose-500" aria-hidden />
                          Top 1 · Sergio Alvarez
                        </span>
                        <span className="font-mono font-semibold tabular-nums">
                          {LB_CONTEXT.topScore.toFixed(3)}
                        </span>
                      </li>
                    </ul>
                    <p className="mt-2.5 text-[11px] leading-snug text-muted-foreground">
                      Ver-7 (port nguyên văn notebook Reyhan) đang được chấm —
                      kỳ vọng rơi vào đúng bức tường 0.947; ver-7b đang chạy
                      nhắm điểm yếu phân bào để vượt tường.
                    </p>
                  </div>
                )
              })()}
            </div>
          </div>
        </div>

        {/* 7 · chú giải */}
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
