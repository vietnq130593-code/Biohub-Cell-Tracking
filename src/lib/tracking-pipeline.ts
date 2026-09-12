/**
 * Thư viện mô phỏng pipeline bài nộp Kaggle
 * "Biohub — Cell Tracking During Development"
 *
 * Nội dung:
 *  1) Sinh dữ liệu GT (giữ nguyên hành vi bản cũ + thêm "cửa sổ mờ" — tế bào
 *     rơi ra khỏi mặt phẳng chiếu sáng vài khung → thuật toán thật sẽ bỏ sót)
 *  2) Render thể tích 3D tổng hợp (lưới downsample như notebook: z×2, xy×4)
 *  3) PORT TRUNG THÀNH 2 phiên bản thuật toán:
 *     - ver 0 (baseline getting-started): P90 · 6-conn · tâm hình học ·
 *       Hungarian gate cố định 15 µm · không phân bào · không frame-skip
 *     - ver 1 (Stage 0+2): P92 · 26-conn · CoM theo cường độ · MIN/MAX voxels ·
 *       motion model EMA + gate thích ứng 5–12 µm · phân bào (10/12 µm + bảo
 *       toàn độ sáng) · frame-skip + nội suy node tại khung mất
 *  4) Bộ chấm điểm dùng chung + division Jaccard theo "dòng con" (lineage) —
 *     sát mô tả metric chính thức hơn bản trước
 *
 * Toàn bộ deterministic (PRNG có seed) → tái lập được.
 * Không phụ thuộc DOM/React — chạy được trong harness bun.
 */

// ---------------------------------------------------------------------------
// Hằng số mô phỏng
// ---------------------------------------------------------------------------

export const T = 60
export const LAST_FRAME = T - 1

/** Trường nhìn 2D (µm) */
export const WORLD_W = 160
export const WORLD_H = 90

/** Ngưỡng ghép node tối đa của metric cuộc thi (µm) */
export const MATCH_UM = 7.0

/** Thang vật lý trục z (µm/voxel) — xy đã tính trực tiếp bằng µm */
export const Z_UM_PER_VOXEL = 1.625

/** Các khung hình có phân bào */
const DIV_FRAMES = [12, 19, 26, 35, 42, 50]

// --- lưới thể tích tổng hợp (không gian DOWNSAMPLE như notebook ver 1) ---
const DS_XY_UM = 1.625 // 0.40625 × 4
const DS_Z_UM = 3.25 // 1.625 × 2
const GX = 99 // 160 µm / 1.625
const GY = 56 // 90 µm / 1.625
const GZ = 32 // 64 lát z gốc / 2
const GZ0 = GZ >> 1 // lưới ver 0: z×4 → 16

// --- tham số render thể tích (hiệu chỉnh bằng harness) ---
// Cơ chế mô phỏng ảnh kính hiển vi thật:
//  · Nền phát sáng tự nhiên (autofluorescence) = trường "glow" tĩnh —
//    cung cấp ~8% thể tích sáng cho percentile → ngưỡng ổn định giữa glow
//    và nhân (đúng cơ chế dữ liệu Kaggle: hàng nghìn nhân + nền có cấu trúc)
//  · Nhân = lõi PHẲNG SÁNG + mép Gaussian hẹp (không phải Gaussian mờ —
//    tránh đuôi dài làm gộp các nhân liền kề)
//  · Cửa sổ mờ: nhân rời mặt phẳng chiếu → biên độ tụt dưới ngưỡng
const BG_LEVEL = 320
const NOISE_AMP = 13
const EDGE_SIGMA = 0.27 // độ rộng mép (đơn vị bán kính lõi)
const CORE_RC_FRAC = 0.82 // bán kính lõi phẳng ≈ 0.82 × bán kính hiển thị
const Z_ELONG = 0.95 // nhân hơi dẹt theo z
const GLOW_BASE = 22
const GLOW_HUMPS = 0 // quần thể ~100 nhân tự phủ 8% — không cần nền cấu trúc
const GLOW_HUMP_SIGXY_LO = 10
const GLOW_HUMP_SIGXY_HI = 16
const GLOW_HUMP_SIGZ_LO = 5
const GLOW_HUMP_SIGZ_HI = 8
const GLOW_HUMP_AMP_LO = 450
const GLOW_HUMP_AMP_HI = 620
const SPECKLE_LAMBDA = 3.0 // số đốm nhiễu sáng trung bình mỗi khung
const SPECKLE_SIGMA_XY = 0.42
const SPECKLE_SIGMA_Z = 0.6
const SPECKLE_AMP_LO = 500
const SPECKLE_AMP_HI = 1400

// --- cửa sổ mờ (thử thách detection) ---
const DIM_PROB = 0.42
const DIM_I_LO = 25
const DIM_I_HI = 45

// --- ver 0 (baseline Kaggle gốc) ---
const V0 = {
  percentile: 90,
  linkGateUm: 15,
}

// --- ver 1 (đúng notebook kaggle/ver-1 · cell 2) ---
const V1 = {
  percentile: 92,
  smoothSize: 3,
  minNvox: 4,
  maxNvox: 1000,
  conn26: true,
  baseGateUm: 8,
  gateMedianMult: 2.5,
  gateMinUm: 5,
  gateMaxUm: 12,
  velSmooth: 0.5,
  skipGateUm: 10,
  maxSkipFrames: 1,
  interpolate: true,
  divEnabled: true,
  divParentGateUm: 10,
  divSiblingGateUm: 12,
  divMinChildFrac: 0.15,
  divBrightCheck: true,
  divBrightRatio: [0.55, 1.8] as const,
}

// ---------------------------------------------------------------------------
// PRNG & tiện ích
// ---------------------------------------------------------------------------

export function mulberry32(seed: number): () => number {
  let a = seed >>> 0
  return () => {
    a |= 0
    a = (a + 0x6d2b79f5) | 0
    let t = Math.imul(a ^ (a >>> 15), 1 | a)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function gauss(rng: () => number): number {
  const u1 = Math.max(1e-9, rng())
  const u2 = rng()
  return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2)
}

export const clamp = (v: number, lo: number, hi: number): number =>
  Number.isFinite(v) ? Math.min(hi, Math.max(lo, v)) : lo
export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t

/** Khoảng cách vật lý 3D (xy µm, z theo voxel) */
export const dist3 = (
  ax: number, ay: number, az: number,
  bx: number, by: number, bz: number,
): number => Math.hypot(ax - bx, ay - by, Z_UM_PER_VOXEL * (az - bz))

// ---------------------------------------------------------------------------
// Sinh dữ liệu ground-truth
// ---------------------------------------------------------------------------

export interface FrameState {
  x: number; y: number; z: number
  r: number; i: number
  labeled: boolean
}

export interface Track {
  id: number
  start: number
  end: number
  frames: FrameState[]
  parent: number | null
  divisionFrame: number | null
}

export interface Division {
  mother: number
  frame: number
  daughters: [number, number]
}

export interface SimData {
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

export function buildSimulation(seed: number): SimData {
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
      rB: 2.7 + rng() * 1.3,
      iB: 2600 + rng() * 1200,
    })
    return tr
  }

  // 100 tế bào ban đầu (mật độ phôi thật — coverage 8% đến từ chính quần thể)
  // đặt cách nhau tối thiểu 14.5 µm (z weighted 1.35 — z merge nhanh hơn xy)
  const placed: [number, number, number][] = []
  for (let k = 0; k < 100; k++) {
    let p: [number, number, number] = [0, 0, 0]
    for (let attempt = 0; attempt < 120; attempt++) {
      const cand: [number, number, number] = [
        8 + rng() * (WORLD_W - 16),
        6 + rng() * (WORLD_H - 12),
        4 + rng() * 56,
      ]
      const ok = placed.every((q) => {
        const dz = (cand[2] - q[2]) * 1.625
        return Math.hypot(cand[0] - q[0], cand[1] - q[1], dz) >= 17
      })
      if (ok) { p = cand; break }
      p = cand
    }
    placed.push(p)
    newTrack(0, p)
  }
  newTrack(12, [6, 10 + rng() * (WORLD_H - 20), 3 + rng() * 56])
  newTrack(24, [WORLD_W - 6, 10 + rng() * (WORLD_H - 20), 3 + rng() * 56])
  newTrack(38, [20 + rng() * (WORLD_W - 40), WORLD_H - 6, 3 + rng() * 56])
  newTrack(48, [WORLD_W * 0.5 + (rng() - 0.5) * 60, 6, 3 + rng() * 56])

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

  const swirlA = rng() * Math.PI * 2
  const intensitySum: number[] = new Array<number>(T).fill(0)

  for (let t = 0; t < T; t++) {
    // --- lượt 1: động học (chảy + random walk + phản xạ biên) ---
    const aliveNow: Track[] = []
    for (const tr of tracks) {
      if (tr.start > t || tr.end < t) continue
      const s = rt.get(tr.id)
      if (s === undefined) continue
      aliveNow.push(tr)

      if (t > tr.start) {
        // trường chảy sin dao động cục bộ, TẮT dần gần vách (không dồn cell vào rìa)
        const ph = swirlA + t * 0.05
        const wallDamp =
          Math.sin((Math.PI * s.pos[0]) / WORLD_W) *
          Math.sin((Math.PI * s.pos[1]) / WORLD_H)
        const flowX = 0.9 * Math.sin((2 * Math.PI * s.pos[1]) / WORLD_H + ph) * wallDamp
        const flowY = 0.9 * Math.sin((2 * Math.PI * s.pos[0]) / WORLD_W - ph) * wallDamp
        s.vel[0] = s.vel[0] * 0.84 + (flowX + (rng() - 0.5) * 1.9) * 0.55
        s.vel[1] = s.vel[1] * 0.84 + (flowY + (rng() - 0.5) * 1.9) * 0.55
        s.vel[2] = s.vel[2] * 0.85 + (rng() - 0.5) * 2.2
        s.pos[0] += s.vel[0]
        s.pos[1] += s.vel[1]
        s.pos[2] += s.vel[2]
        // phản xạ tại biên (giữ phân bố đều, không dồn vào vách)
        if (s.pos[0] < 4) { s.pos[0] = 8 - s.pos[0]; s.vel[0] = Math.abs(s.vel[0]) }
        if (s.pos[0] > WORLD_W - 4) { s.pos[0] = 2 * (WORLD_W - 4) - s.pos[0]; s.vel[0] = -Math.abs(s.vel[0]) }
        if (s.pos[1] < 4) { s.pos[1] = 8 - s.pos[1]; s.vel[1] = Math.abs(s.vel[1]) }
        if (s.pos[1] > WORLD_H - 4) { s.pos[1] = 2 * (WORLD_H - 4) - s.pos[1]; s.vel[1] = -Math.abs(s.vel[1]) }
        if (s.pos[2] < 2.5) { s.pos[2] = 5 - s.pos[2]; s.vel[2] = Math.abs(s.vel[2]) }
        if (s.pos[2] > 60.5) { s.pos[2] = 121 - s.pos[2]; s.vel[2] = -Math.abs(s.vel[2]) }
      }
    }

    // --- lượt 2: đẩy thể tích loại trừ (tissue mechanics) — giữ khoảng cách
    // giữa các tế bào ~13 µm mãi mãi; MIỄN cặp mẹ–con mới sinh (≤ 10 khung) ---
    if (aliveNow.length > 1) {
      const stOf = (tr: Track): RtState | undefined => rt.get(tr.id)
      for (let a = 0; a < aliveNow.length; a++) {
        for (let b = a + 1; b < aliveNow.length; b++) {
          const trA = aliveNow[a]!
          const trB = aliveNow[b]!
          const A = stOf(trA)
          const B = stOf(trB)
          if (A === undefined || B === undefined) continue
          // miễn đẩy: con mới sinh với mẹ & với chị em ruột (cần thời gian tách tự nhiên)
          const exempt =
            (trA.parent === trB.id && t - trA.start <= 10) ||
            (trB.parent === trA.id && t - trB.start <= 10) ||
            (trA.parent !== null && trA.parent === trB.parent && t - trA.start <= 10 && t - trB.start <= 10)
          if (exempt) continue
          const dx = A.pos[0] - B.pos[0]
          const dy = A.pos[1] - B.pos[1]
          const dz = (A.pos[2] - B.pos[2]) * 1.625
          const d = Math.hypot(dx, dy, dz)
          if (d >= 17 || d < 1e-6) continue
          const push = 0.55 * (17 - d) / d
          A.pos[0] += dx * push
          A.pos[1] += dy * push
          A.pos[2] += (dz * push) / 1.625
          B.pos[0] -= dx * push
          B.pos[1] -= dy * push
          B.pos[2] -= (dz * push) / 1.625
        }
      }
    }

    // --- lượt 3: ghi trạng thái khung ---
    for (const tr of aliveNow) {
      const s = rt.get(tr.id)
      if (s === undefined) continue
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

    const dv = pending.get(t)
    if (dv !== undefined) {
      const mother = tracks.find((x) => x.id === dv.mother)
      const ms = mother !== undefined ? rt.get(mother.id) : undefined
      if (mother !== undefined && ms !== undefined && mother.frames.length > 0) {
        const ang = rng() * Math.PI * 2
        const off = 3.2 + rng() * 2.2
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
            cs.vel = [Math.cos(ang) * 1.0 * sgn, Math.sin(ang) * 1.0 * sgn, 0]
            cs.rB = ms.rB * 0.75
            cs.iB = ms.iB * (0.5 + rng() * 0.25) // mỗi con nhận ~0.5–0.75 độ sáng mẹ
          }
        }
      }
    }
  }

  // gắn nhãn thưa (~88%): đục "cửa sổ mờ nhãn" 2–7 khung, bảo vệ vùng phân bào
  const holeRng = mulberry32(seed ^ 0x9e3779b9)
  for (const tr of tracks) {
    let i = 2 + Math.floor(holeRng() * 8)
    while (i < tr.frames.length) {
      const len = 2 + Math.floor(holeRng() * 5)
      for (let j = i; j < Math.min(i + len, tr.frames.length); j++) {
        tr.frames[j]!.labeled = false
      }
      i += len + 4 + Math.floor(holeRng() * 9)
    }
    if (tr.divisionFrame !== null) {
      for (
        let j = Math.max(0, tr.divisionFrame - 1 - tr.start);
        j <= tr.divisionFrame - tr.start;
        j++
      ) {
        tr.frames[j]!.labeled = true
      }
    }
    if (tr.parent !== null) {
      tr.frames[0]!.labeled = true
      if (tr.frames.length > 1) tr.frames[1]!.labeled = true
    }
  }

  // cửa sổ mờ (intensity tụt dưới ngưỡng phát hiện vài khung) — tránh vùng
  // phân bào (5 khung trước khi mẹ tách) và 7 khung đầu đời của con
  const dimRng = mulberry32(seed ^ 0x71f3a1)
  for (const tr of tracks) {
    if (dimRng() > DIM_PROB) continue
    const nWin = dimRng() < 0.3 ? 2 : 1
    for (let w = 0; w < nWin; w++) {
      const divIdx =
        tr.divisionFrame !== null ? tr.divisionFrame - tr.start : -1
      const lo = tr.parent !== null ? 7 : 2
      const hi = tr.frames.length - 1
      if (hi - lo < 3) continue
      const len = 1 + Math.floor(dimRng() * (dimRng() < 0.6 ? 2 : 3))
      const st = lo + Math.floor(dimRng() * Math.max(1, hi - lo - len))
      if (divIdx >= 0 && st + len > divIdx - 5) continue
      for (let k = st; k < Math.min(st + len, tr.frames.length); k++) {
        tr.frames[k]!.i = Math.round(DIM_I_LO + dimRng() * (DIM_I_HI - DIM_I_LO))
      }
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
// Phát hiện (detection) — Det dùng chung cho mọi chế độ
// ---------------------------------------------------------------------------

export interface Det {
  x: number; y: number; z: number
  r: number; i: number
  mass: number // tổng cường độ component (cho logic phân bào)
  src: number | null // track nguồn (null = node giả / không rõ)
}

/** Gán src: track thật gần nhất trong bán kính cho phép (để phân loại neutral) */
function nearestSrc(
  sim: SimData,
  t: number,
  x: number,
  y: number,
  z: number,
  maxUm: number,
): number | null {
  let best: number | null = null
  let bestD = maxUm
  for (const tr of sim.tracks) {
    if (tr.start > t || tr.end < t) continue
    const f = tr.frames[t - tr.start]
    if (f === undefined) continue
    const d = dist3(x, y, z, f.x, f.y, f.z)
    if (d <= bestD) {
      bestD = d
      best = tr.id
    }
  }
  return best
}

// ---------------------------------------------------------------------------
// Render thể tích tổng hợp
// ---------------------------------------------------------------------------

/** Trường phát sáng nền tĩnh (autofluorescence) — mỗi seed một mảng */
function makeGlowField(seed: number): Float32Array {
  const g = new Float32Array(GZ * GY * GX)
  g.fill(GLOW_BASE)
  const rng = mulberry32((seed ^ 0x6c0ffee) >>> 0)
  for (let h = 0; h < GLOW_HUMPS; h++) {
    const cx = rng() * GX
    const cy = rng() * GY
    const cz = 3 + rng() * (GZ - 6)
    const sxy = GLOW_HUMP_SIGXY_LO + rng() * (GLOW_HUMP_SIGXY_HI - GLOW_HUMP_SIGXY_LO)
    const sz = GLOW_HUMP_SIGZ_LO + rng() * (GLOW_HUMP_SIGZ_HI - GLOW_HUMP_SIGZ_LO)
    const amp = GLOW_HUMP_AMP_LO + rng() * (GLOW_HUMP_AMP_HI - GLOW_HUMP_AMP_LO)
    const x0 = Math.max(0, Math.floor(cx - 3.2 * sxy))
    const x1 = Math.min(GX - 1, Math.ceil(cx + 3.2 * sxy))
    const y0 = Math.max(0, Math.floor(cy - 3.2 * sxy))
    const y1 = Math.min(GY - 1, Math.ceil(cy + 3.2 * sxy))
    const z0 = Math.max(0, Math.floor(cz - 3.2 * sz))
    const z1 = Math.min(GZ - 1, Math.ceil(cz + 3.2 * sz))
    for (let z = z0; z <= z1; z++) {
      const dz2 = (z - cz) * (z - cz)
      for (let y = y0; y <= y1; y++) {
        const dy2 = (y - cy) * (y - cy)
        for (let x = x0; x <= x1; x++) {
          const dx2 = (x - cx) * (x - cx)
          g[(z * GY + y) * GX + x] +=
            amp * Math.exp(-0.5 * (dx2 / (sxy * sxy) + dy2 / (sxy * sxy) + dz2 / (sz * sz)))
        }
      }
    }
  }
  return g
}

function renderVolume(
  sim: SimData,
  t: number,
  out: Float32Array,
  glow: Float32Array,
  rng: () => number,
): void {
  const n = out.length
  // nền + glow + nhiễu sensor
  for (let i = 0; i < n; i++) {
    out[i] = BG_LEVEL + glow[i]! + (rng() - 0.5) * 2 * NOISE_AMP
  }
  // các tế bào (cả khung chưa gắn nhãn — thuật toán nhìn ảnh, không nhìn nhãn)
  for (const tr of sim.tracks) {
    if (tr.start > t || tr.end < t) continue
    const f = tr.frames[t - tr.start]!
    const gx = f.x / DS_XY_UM
    const gy = f.y / DS_XY_UM
    const gz = f.z / 2 // z raw-voxel → ds-voxel (lưới ver 1)
    const amp = f.i
    const rcxy = (CORE_RC_FRAC * f.r) / DS_XY_UM
    const rcz = (CORE_RC_FRAC * f.r * Z_ELONG) / DS_Z_UM
    // vùng vẽ: lõi + 3.4σ mép
    const x0 = Math.max(0, Math.floor(gx - rcxy * (1 + 3.4 * EDGE_SIGMA)))
    const x1 = Math.min(GX - 1, Math.ceil(gx + rcxy * (1 + 3.4 * EDGE_SIGMA)))
    const y0 = Math.max(0, Math.floor(gy - rcxy * (1 + 3.4 * EDGE_SIGMA)))
    const y1 = Math.min(GY - 1, Math.ceil(gy + rcxy * (1 + 3.4 * EDGE_SIGMA)))
    const z0 = Math.max(0, Math.floor(gz - rcz * (1 + 3.4 * EDGE_SIGMA)))
    const z1 = Math.min(GZ - 1, Math.ceil(gz + rcz * (1 + 3.4 * EDGE_SIGMA)))

    for (let z = z0; z <= z1; z++) {
      const qz = (z - gz) * (z - gz) / (rcz * rcz)
      const zPlane = z * GY * GX
      for (let y = y0; y <= y1; y++) {
        const qyz = qz + (y - gy) * (y - gy) / (rcxy * rcxy)
        const rowBase = zPlane + y * GX
        for (let x = x0; x <= x1; x++) {
          const q = qyz + (x - gx) * (x - gx) / (rcxy * rcxy)
          let v: number
          if (q <= 1) {
            v = amp // lõi phẳng sáng
          } else {
            const e = Math.sqrt(q) - 1
            v = amp * Math.exp(-0.5 * (e / EDGE_SIGMA) * (e / EDGE_SIGMA)) // mép sắc
          }
          out[rowBase + x] += v
        }
      }
    }
  }
  // đốm nhiễu sáng (false positive cho detector)
  const nSpeck = Math.floor(SPECKLE_LAMBDA * (0.4 + rng() * 1.2))
  for (let k = 0; k < nSpeck; k++) {
    const gx = 1 + rng() * (GX - 2)
    const gy = 1 + rng() * (GY - 2)
    const gz = rng() * (GZ - 1)
    const amp = SPECKLE_AMP_LO + rng() * (SPECKLE_AMP_HI - SPECKLE_AMP_LO)
    for (let z = Math.max(0, Math.floor(gz - 3)); z <= Math.min(GZ - 1, Math.ceil(gz + 3)); z++) {
      for (let y = Math.max(0, Math.floor(gy - 3)); y <= Math.min(GY - 1, Math.ceil(gy + 3)); y++) {
        for (let x = Math.max(0, Math.floor(gx - 3)); x <= Math.min(GX - 1, Math.ceil(gx + 3)); x++) {
          const d2 =
            ((x - gx) * (x - gx) + (y - gy) * (y - gy)) / (SPECKLE_SIGMA_XY * SPECKLE_SIGMA_XY) +
            ((z - gz) * (z - gz)) / (SPECKLE_SIGMA_Z * SPECKLE_SIGMA_Z)
          out[(z * GY + y) * GX + x] += amp * Math.exp(-0.5 * d2)
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Xử lý ảnh: làm mượt, percentile, connected components
// ---------------------------------------------------------------------------

/** uniform_filter size 3 (separable, biên reflect) — như scipy.ndimage */
function smooth3(vol: Float32Array, out: Float32Array, Z: number, Y: number, X: number): void {
  // trục x: vol → out
  for (let z = 0; z < Z; z++) {
    for (let y = 0; y < Y; y++) {
      const base = (z * Y + y) * X
      for (let x = 0; x < X; x++) {
        const a = vol[base + Math.max(0, x - 1)]!
        const b = vol[base + x]!
        const c = vol[base + Math.min(X - 1, x + 1)]!
        out[base + x] = (a + b + c) / 3
      }
    }
  }
  // trục y: out → vol
  for (let z = 0; z < Z; z++) {
    for (let y = 0; y < Y; y++) {
      const bRow = (z * Y + Math.max(0, y - 1)) * X
      const cRow = (z * Y + y) * X
      const aRow = (z * Y + Math.min(Y - 1, y + 1)) * X
      for (let x = 0; x < X; x++) {
        vol[cRow + x] = (out[bRow + x]! + out[cRow + x]! + out[aRow + x]!) / 3
      }
    }
  }
  // trục z: vol → out (kết quả cuối)
  for (let z = 0; z < Z; z++) {
    const zb = Math.max(0, z - 1)
    const za = Math.min(Z - 1, z + 1)
    for (let y = 0; y < Y; y++) {
      const base = (z * Y + y) * X
      const baseB = (zb * Y + y) * X
      const baseA = (za * Y + y) * X
      for (let x = 0; x < X; x++) {
        out[base + x] = (vol[baseB + x]! + vol[base + x]! + vol[baseA + x]!) / 3
      }
    }
  }
}

/** percentile qua histogram (đủ chính xác để chọn ngưỡng) */
function percentileOf(vol: Float32Array, p: number): number {
  const N_BINS = 4096
  const BIN_W = 2.0
  const hist = new Int32Array(N_BINS)
  const n = vol.length
  for (let i = 0; i < n; i++) {
    let b = (vol[i]! / BIN_W) | 0
    if (b < 0) b = 0
    else if (b >= N_BINS) b = N_BINS - 1
    hist[b]++
  }
  const target = (p / 100) * n
  let acc = 0
  for (let b = 0; b < N_BINS; b++) {
    acc += hist[b]!
    if (acc >= target) return (b + 0.5) * BIN_W
  }
  return (N_BINS - 0.5) * BIN_W
}

interface CompStat {
  count: number
  w: number // Σ intensity
  wz: number; wy: number; wx: number // Σ intensity·coord (CoM)
  cz: number; cy: number; cx: number // Σ coord (tâm hình học)
}

/** Connected components trên vol > thr. conn26 = liên kết 26 ô, ngược lại 6 ô */
function labelComponents(
  vol: Float32Array,
  thr: number,
  conn26: boolean,
  Z: number,
  Y: number,
  X: number,
): CompStat[] {
  const labels = new Int32Array(vol.length)
  const comps: CompStat[] = []
  const stack: number[] = []
  const offs: number[] = []
  if (conn26) {
    for (const dz of [-1, 0, 1]) {
      for (const dy of [-1, 0, 1]) {
        for (let dx = -1; dx <= 1; dx++) {
          if (dz === 0 && dy === 0 && dx === 0) continue
          offs.push(dz * Y * X + dy * X + dx)
        }
      }
    }
  } else {
    offs.push(-Y * X, Y * X, -X, X, -1, 1)
  }

  for (let start = 0; start < vol.length; start++) {
    if (vol[start]! <= thr || labels[start]! !== 0) continue
    const st: CompStat = { count: 0, w: 0, wz: 0, wy: 0, wx: 0, cz: 0, cy: 0, cx: 0 }
    comps.push(st)
    const cid = comps.length
    labels[start] = cid
    stack.push(start)
    while (stack.length > 0) {
      const idx = stack.pop()!
      const v = vol[idx]!
      const z = (idx / (Y * X)) | 0
      const rem = idx - z * Y * X
      const y = (rem / X) | 0
      const x = rem - y * X
      st.count++
      st.w += v
      st.wz += z * v
      st.wy += y * v
      st.wx += x * v
      st.cz += z
      st.cy += y
      st.cx += x
      for (let oi = 0; oi < offs.length; oi++) {
        const nb = idx + offs[oi]!
        if (nb < 0 || nb >= vol.length) continue
        if (labels[nb] !== 0 || vol[nb]! <= thr) continue
        // chặn offset quay vòng qua biên hàng/cột/lát
        const nz = (nb / (Y * X)) | 0
        const nrem = nb - nz * Y * X
        const ny = (nrem / X) | 0
        const nx = nrem - ny * X
        if (Math.abs(nz - z) > 1 || Math.abs(ny - y) > 1 || Math.abs(nx - x) > 1) continue
        labels[nb] = cid
        stack.push(nb)
      }
    }
  }
  return comps
}

// ---------------------------------------------------------------------------
// Gán song phân tối ưu (Hungarian, O(n³)) — như metric cuộc thi
// ---------------------------------------------------------------------------

export function hungarian(cost: number[][]): (number | null)[] {
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
    for (let j = 0; j < nCols; j++) a[i + 1]![j + 1] = cost[i]![j]!
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
// Đồ thị GT + bộ chấm điểm dùng chung
// ---------------------------------------------------------------------------

export interface GtNode {
  key: string
  trackId: number
  t: number
  x: number; y: number; z: number
}

export interface GtEdge {
  key: string
  t: number
  x1: number; y1: number
  x2: number; y2: number
}

export interface GtGraph {
  nodesByFrame: GtNode[][]
  edges: GtEdge[]
  edgeSet: Set<string>
  keySet: Set<string>
  labeledAt: (tr: Track, t: number) => boolean
}

export function buildGtGraph(sim: SimData, sparse: boolean): GtGraph {
  const labeledAt = (tr: Track, t: number): boolean => {
    if (t < tr.start || t > tr.end) return false
    return sparse ? tr.frames[t - tr.start]!.labeled : true
  }

  const nodesByFrame: GtNode[][] = Array.from({ length: T }, () => [])
  const keySet = new Set<string>()
  for (const tr of sim.tracks) {
    for (let t = tr.start; t <= tr.end; t++) {
      if (!labeledAt(tr, t)) continue
      const f = tr.frames[t - tr.start]!
      const key = `${tr.id}@${t}`
      nodesByFrame[t]!.push({ key, trackId: tr.id, t, x: f.x, y: f.y, z: f.z })
      keySet.add(key)
    }
  }

  const edges: GtEdge[] = []
  const edgeSet = new Set<string>()
  for (const tr of sim.tracks) {
    for (let t = tr.start; t < tr.end; t++) {
      if (!labeledAt(tr, t) || !labeledAt(tr, t + 1)) continue
      const fa = tr.frames[t - tr.start]!
      const fb = tr.frames[t + 1 - tr.start]!
      const key = `${tr.id}@${t}=>${tr.id}@${t + 1}`
      edges.push({ key, t, x1: fa.x, y1: fa.y, x2: fb.x, y2: fb.y })
      edgeSet.add(key)
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
      edges.push({ key, t: dv.frame, x1: mf.x, y1: mf.y, x2: df.x, y2: df.y })
      edgeSet.add(key)
    }
  }

  return { nodesByFrame, edges, edgeSet, keySet, labeledAt }
}

export type PredCls = 'matched' | 'neutral' | 'spurious'

export interface PredNode {
  key: string
  t: number
  det: Det
  gtKey: string | null
  gtTrackId: number | null
  cls: PredCls
}

/** Cạnh dạng tham chiếu chỉ số: node (at, ai) → (bt, bi) — liền khung */
export interface EdgeRef {
  at: number
  ai: number
  bt: number
  bi: number
}

export interface Metrics {
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

export interface Analysis {
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
  /** chi tiết từng lần phân bào GT: bắt được hay không */
  divDetail: { frame: number; hit: boolean }[]
}

/**
 * Chấm điểm một bộ phát hiện + cạnh bất kỳ (dùng chung cho ver 0 / ver 1 /
 * chế độ tùy chỉnh). Division Jaccard theo dòng con (lineage): với mỗi lần
 * phân bào GT, thành phần dự đoán phủ giai đoạn trước khi tách phải chạm cả
 * hai dòng con gái — sát mô tả metric chính thức.
 */
export function scoreDetections(
  sim: SimData,
  gt: GtGraph,
  det: Det[][],
  edgeRefs: EdgeRef[],
): Analysis {
  // ---- ghép node tối ưu 7 µm + phân loại ----
  const nodes: PredNode[][] = []
  for (let t = 0; t < T; t++) {
    const dets = det[t] ?? []
    const gts = gt.nodesByFrame[t] ?? []
    const cost = dets.map((d) =>
      gts.map((g) => {
        const dd = dist3(d.x, d.y, d.z, g.x, g.y, g.z)
        return dd <= MATCH_UM ? dd : 1e9
      }),
    )
    const assign = hungarian(cost)
    nodes[t] = dets.map((d, i): PredNode => {
      const col = assign[i]
      const g = col !== null ? gts[col] : undefined
      const gtKey =
        g !== undefined && dist3(d.x, d.y, d.z, g.x, g.y, g.z) <= MATCH_UM
          ? g.key
          : null
      let cls: PredCls = 'spurious'
      if (gtKey !== null) cls = 'matched'
      else if (d.src !== null && !gt.keySet.has(`${d.src}@${t}`)) cls = 'neutral'
      return {
        key: `${t}:${i}`,
        t,
        det: d,
        gtKey,
        gtTrackId: gtKey !== null ? Number(gtKey.split('@')[0]) : null,
        cls,
      }
    })
  }

  const nodeByKey = new Map<string, PredNode>()
  for (const frameNodes of nodes) {
    for (const nd of frameNodes) nodeByKey.set(nd.key, nd)
  }

  // ---- cạnh + phân loại ----
  const covered = new Set<string>()
  const predEdges: {
    er: EdgeRef
    a: PredNode
    b: PredNode
    cls: 'tp' | 'fp' | 'neutral'
  }[] = []
  const outDeg = new Map<string, number>()
  const fwd = new Map<string, string[]>()

  for (const er of edgeRefs) {
    const a = (nodes[er.at] ?? [])[er.ai]
    const b = (nodes[er.bt] ?? [])[er.bi]
    if (a === undefined || b === undefined) continue
    let cls: 'tp' | 'fp' | 'neutral'
    if (a.cls === 'matched' && b.cls === 'matched') {
      const gk = `${a.gtKey}=>${b.gtKey}`
      if (gt.edgeSet.has(gk) && !covered.has(gk)) {
        cls = 'tp'
        covered.add(gk)
      } else {
        cls = 'fp'
      }
    } else if (a.cls === 'spurious' || b.cls === 'spurious') {
      cls = 'fp'
    } else {
      cls = 'neutral'
    }
    predEdges.push({ er, a, b, cls })
    outDeg.set(a.key, (outDeg.get(a.key) ?? 0) + 1)
    const arr = fwd.get(a.key)
    if (arr === undefined) fwd.set(a.key, [b.key])
    else arr.push(b.key)
  }

  // ---- metric cạnh ----
  const gtNodeTotal = gt.nodesByFrame.reduce((s, g) => s + g.length, 0)
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
  const fn = gt.edges.length - tp
  const denomE = tp + fp + fn + spurious
  const adjEJ = denomE > 0 ? tp / denomE : 0

  // ---- phân bào: TP theo dòng con (lineage) ----
  let divTP = 0
  const divDetail: { frame: number; hit: boolean }[] = []
  for (const dv of sim.divisions) {
    let hit = false
    for (let t = Math.max(0, dv.frame - 2); t <= dv.frame && !hit; t++) {
      for (const nd of nodes[t] ?? []) {
        if (nd.cls !== 'matched' || nd.gtTrackId !== dv.mother) continue
        // BFS tiến qua cạnh dự đoán, giới hạn khung ≤ dv.frame + 12
        const visited = new Set<string>([nd.key])
        const queue: string[] = [nd.key]
        let touchA = false
        let touchB = false
        let qi = 0
        while (qi < queue.length && visited.size < 400) {
          const ck = queue[qi++]!
          const cnode = nodeByKey.get(ck)
          if (cnode === undefined) continue
          if (cnode.t > dv.frame + 12) continue
          if (
            cnode.cls === 'matched' &&
            cnode.t >= dv.frame + 1 &&
            cnode.gtTrackId !== null
          ) {
            if (cnode.gtTrackId === dv.daughters[0]) touchA = true
            if (cnode.gtTrackId === dv.daughters[1]) touchB = true
          }
          for (const nk of fwd.get(ck) ?? []) {
            if (!visited.has(nk)) {
              visited.add(nk)
              queue.push(nk)
            }
          }
        }
        if (touchA && touchB) {
          hit = true
          break
        }
      }
    }
    if (hit) divTP++
    divDetail.push({ frame: dv.frame, hit })
  }

  // ---- phân bào: FP — node khớp GT có ≥ 2 cạnh ra nhưng GT không tách ----
  let divFP = 0
  for (const frameNodes of nodes) {
    for (const nd of frameNodes) {
      if (nd.cls !== 'matched') continue
      if ((outDeg.get(nd.key) ?? 0) < 2) continue
      const tr = nd.gtTrackId !== null ? sim.byId.get(nd.gtTrackId) : undefined
      if (tr === undefined) continue
      const t = nd.t
      if (tr.divisionFrame === t) continue // kỳ vọng 2 cạnh ra
      if (t + 1 <= tr.end) {
        if (!gt.labeledAt(tr, t + 1)) continue // không kiểm chứng được (GT thưa)
        divFP++ // kỳ vọng 1 cạnh → 2 cạnh ra là phân bào giả
      } else {
        divFP++ // track GT kết thúc → mọi cạnh ra đều thừa
      }
    }
  }

  const divFN = sim.divisions.length - divTP
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

  // ---- dữ liệu vẽ ----
  const frames = Array.from({ length: T }, (_, t) => ({
    gtEdges: gt.edges
      .filter((e) => e.t === t)
      .map((e) => ({ ...e, fn: !covered.has(e.key) })),
    predEdges: predEdges
      .filter((e) => e.er.at === t)
      .map((e) => ({
        x1: e.a.det.x, y1: e.a.det.y,
        x2: e.b.det.x, y2: e.b.det.y,
        cls: e.cls,
      })),
  }))
  const gtCountByFrame = gt.nodesByFrame.map((g) => g.length)

  return { det, nodes, frames, gtCountByFrame, metrics, divDetail }
}

// ---------------------------------------------------------------------------
// PIPELINE — chạy thuật toán thật trên thể tích tổng hợp
// ---------------------------------------------------------------------------

export type PipelineVersion = 'ver0' | 'ver1'

export interface PipelineStats {
  nodes: number
  edges: number
  divisions: number
  ms: number
  /** mốc 30/60 khung (mô phỏng log Kaggle in định kỳ) */
  nodes30: number
  edges30: number
  div30: number
  ms30: number
}

export interface PipelineRun {
  version: PipelineVersion
  stats: PipelineStats
  det: Det[][]
  edges: EdgeRef[]
}

/** Kết quả phát hiện 1 khung ở toạ độ ds-voxel lưới ver 1 */
interface RawDet {
  gx: number; gy: number; gz: number
  mass: number
  nvox: number
}

const physDist = (
  a: readonly [number, number, number],
  b: readonly [number, number, number],
): number => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])

/** (dùng cho harness) đo ngưỡng & phân bố component tại 1 khung */
export function probeVolume(sim: SimData, seed: number, t: number): {
  thr1: number
  frac1: number
  nComp1: number
  compSizes1: number[]
  alive: number
  dets1: number
  compCenters: { x: number; y: number; z: number; size: number }[]
  cellVals: { id: number; val: number; i: number }[]
} {
  const vol = new Float32Array(GZ * GY * GX)
  const sm = new Float32Array(GZ * GY * GX)
  const glow = makeGlowField(seed)
  const rng = mulberry32((seed * 7919 + t * 104729) >>> 0)
  renderVolume(sim, t, vol, glow, rng)
  smooth3(vol, sm, GZ, GY, GX)
  const thr = percentileOf(sm, V1.percentile)
  const comps = labelComponents(sm, thr, true, GZ, GY, GX)
  const alive = sim.tracks.filter((tr) => tr.start <= t && t <= tr.end).length
  let dets1 = 0
  for (const c of comps) {
    if (c.count >= V1.minNvox && c.count <= V1.maxNvox && c.w > 0) dets1++
  }
  let above = 0
  for (let i = 0; i < sm.length; i++) if (sm[i]! > thr) above++
  const compCenters = comps.map((c) => ({
    x: (c.wx / c.w) * DS_XY_UM,
    y: (c.wy / c.w) * DS_XY_UM,
    z: (c.wz / c.w) * 2,
    size: c.count,
  }))
  const cellVals: { id: number; val: number; i: number }[] = []
  for (const tr of sim.tracks) {
    if (tr.start > t || tr.end < t) continue
    const f = tr.frames[t - tr.start]!
    const cx = clamp(Math.round(f.x / DS_XY_UM), 0, GX - 1)
    const cy = clamp(Math.round(f.y / DS_XY_UM), 0, GY - 1)
    const cz = clamp(Math.round(f.z / 2), 0, GZ - 1)
    cellVals.push({ id: tr.id, val: sm[(cz * GY + cy) * GX + cx]!, i: f.i })
  }
  return {
    thr1: thr,
    frac1: above / sm.length,
    nComp1: comps.length,
    compSizes1: comps.map((c) => c.count).sort((a, b) => b - a).slice(0, 12),
    alive,
    dets1,
    compCenters,
    cellVals,
  }
}

/** Chạy cả 2 phiên bản trên cùng một chuỗi thể tích (render 1 lần/khung) */
export function runBothPipelines(sim: SimData, seed: number): {
  ver0: PipelineRun
  ver1: PipelineRun
} {
  const vol = new Float32Array(GZ * GY * GX)
  const smoothed = new Float32Array(GZ * GY * GX)
  const sub0 = new Float32Array(GZ0 * GY * GX)
  const sm0 = new Float32Array(GZ0 * GY * GX)
  const glow = makeGlowField(seed)

  const det0: Det[][] = Array.from({ length: T }, () => [])
  const det1: Det[][] = Array.from({ length: T }, () => [])
  const edges0: EdgeRef[] = []
  const edges1: EdgeRef[] = []

  // ---- tracker ver 0: Hungarian gate 15 µm, không motion/division/skip ----
  const active0 = new Map<number, { pos: [number, number, number]; ref: { t: number; i: number } }>()
  let nid0 = 0

  // ---- tracker ver 1: port class Tracker của notebook ----
  const active1 = new Map<
    number,
    { pos: [number, number, number]; vel: [number, number, number]; mass: number; ref: { t: number; i: number } }
  >()
  const pending1 = new Map<
    number,
    { pos: [number, number, number]; vel: [number, number, number]; mass: number; ref: { t: number; i: number }; missed: number }
  >()
  const recentSteps: number[] = []
  let nid1 = 0
  let divCount1 = 0

  const gate1 = (): number => {
    if (recentSteps.length < 5) return V1.baseGateUm
    const srt = [...recentSteps].sort((a, b) => a - b)
    const mid = srt[Math.floor(srt.length / 2)]!
    return clamp(V1.gateMedianMult * mid, V1.gateMinUm, V1.gateMaxUm)
  }

  const t0 = performance.now()
  let ms0 = 0
  let ms1 = 0
  let nodes30v0 = 0, edges30v0 = 0, nodes30v1 = 0, edges30v1 = 0, div30v1 = 0
  let ms30v0 = 0, ms30v1 = 0

  for (let t = 0; t < T; t++) {
    const rng = mulberry32((seed * 7919 + t * 104729) >>> 0)
    renderVolume(sim, t, vol, glow, rng)

    // ---- VER 0 · detect (subsample z trước khi vol bị làm mượt đè) ----
    const ta = performance.now()
    for (let z = 0; z < GZ0; z++) {
      const src = (2 * z) * GY * GX
      sub0.set(vol.subarray(src, src + GY * GX), z * GY * GX)
    }
    smooth3(sub0, sm0, GZ0, GY, GX)
    {
      const thr = percentileOf(sm0, V0.percentile)
      const comps = labelComponents(sm0, thr, false, GZ0, GY, GX)
      for (const c of comps) {
        if (c.count <= 0) continue
        const x = clamp((c.cx / c.count) * DS_XY_UM, 0.5, WORLD_W - 0.5)
        const y = clamp((c.cy / c.count) * DS_XY_UM, 0.5, WORLD_H - 0.5)
        const z = clamp((c.cz / c.count) * 4, 0.5, 63.5)
        det0[t]!.push({
          x, y, z,
          r: clamp(0.62 * Math.cbrt(Math.max(1, c.count)) * DS_XY_UM, 1.2, 5.5),
          i: Math.round(c.w / c.count),
          mass: c.w,
          src: nearestSrc(sim, t, x, y, z, 4.0),
        })
      }
    }
    // ---- VER 0 · link: Hungarian gate 15 µm ----
    {
      const pos0 = det0[t]!.map(
        (d): [number, number, number] => [d.z * Z_UM_PER_VOXEL, d.y, d.x],
      )
      const prevIds = [...active0.keys()]
      const next0 = new Map<number, { pos: [number, number, number]; ref: { t: number; i: number } }>()
      if (prevIds.length > 0 && pos0.length > 0) {
        const cost = prevIds.map((p) =>
          pos0.map((c) => {
            const dd = physDist(active0.get(p)!.pos, c)
            return dd <= V0.linkGateUm ? dd : 1e9
          }),
        )
        const assign = hungarian(cost)
        for (let pi = 0; pi < prevIds.length; pi++) {
          const ci = assign[pi]
          if (ci === null) continue
          const st = active0.get(prevIds[pi]!)!
          edges0.push({ at: t - 1, ai: st.ref.i, bt: t, bi: ci })
          next0.set(prevIds[pi]!, { pos: pos0[ci]!, ref: { t, i: ci } })
        }
      }
      for (let ci = 0; ci < pos0.length; ci++) {
        if ([...next0.values()].some((s) => s.ref.t === t && s.ref.i === ci)) continue
        nid0++
        next0.set(nid0, { pos: pos0[ci]!, ref: { t, i: ci } })
      }
      active0.clear()
      for (const [k, v] of next0) active0.set(k, v)
    }
    ms0 += performance.now() - ta

    // ---- VER 1 · detect: CoM, 26-conn, MIN/MAX voxels ----
    const tb = performance.now()
    smooth3(vol, smoothed, GZ, GY, GX)
    {
      const thr = percentileOf(smoothed, V1.percentile)
      const comps = labelComponents(smoothed, thr, V1.conn26, GZ, GY, GX)
      for (const c of comps) {
        if (c.count < V1.minNvox || c.count > V1.maxNvox) continue
        if (c.w <= 0) continue
        const x = clamp((c.wx / c.w) * DS_XY_UM, 0.5, WORLD_W - 0.5)
        const y = clamp((c.wy / c.w) * DS_XY_UM, 0.5, WORLD_H - 0.5)
        const z = clamp((c.wz / c.w) * 2, 0.5, 63.5)
        det1[t]!.push({
          x, y, z,
          r: clamp(0.62 * Math.cbrt(Math.max(1, c.count)) * DS_XY_UM, 1.2, 5.5),
          i: Math.round(c.w / c.count),
          mass: c.w,
          src: nearestSrc(sim, t, x, y, z, 4.0),
        })
      }
    }

    // ---- VER 1 · tracker (port Tracker.step) ----
    {
      const pos = det1[t]!.map(
        (d): [number, number, number] => [d.z * Z_UM_PER_VOXEL, d.y, d.x],
      )
      const mass = det1[t]!.map((d) => d.mass)
      const n = det1[t]!.length
      const frameEdges: EdgeRef[] = []
      const matchedCurr = new Map<number, number>() // curr idx → prev nid

      const prevIds = [...active1.keys()]
      if (prevIds.length > 0 && n > 0) {
        const gate = gate1()
        const D: number[][] = prevIds.map((p) => {
          const a = active1.get(p)!
          const pred: [number, number, number] = [
            a.pos[0] + a.vel[0],
            a.pos[1] + a.vel[1],
            a.pos[2] + a.vel[2],
          ]
          return pos.map((c) => physDist(pred, c))
        })
        const cost = D.map((row) => row.map((d) => (d <= gate ? d : 1e9)))
        const assign = hungarian(cost)
        for (let ri = 0; ri < prevIds.length; ri++) {
          const ci = assign[ri]
          if (ci === null) continue
          if (D[ri]![ci]! > gate) continue
          const p = prevIds[ri]!
          matchedCurr.set(ci, p)
          const st = active1.get(p)!
          frameEdges.push({ at: t - 1, ai: st.ref.i, bt: t, bi: ci })
          recentSteps.push(physDist(pos[ci]!, st.pos))
        }
        if (recentSteps.length > 200) recentSteps.splice(0, 100)
      }

      const newActive = new Map<number, { pos: [number, number, number]; vel: [number, number, number]; mass: number; ref: { t: number; i: number } }>()
      for (const [ci, p] of matchedCurr) {
        const a = active1.get(p)!
        const disp: [number, number, number] = [
          pos[ci]![0] - a.pos[0],
          pos[ci]![1] - a.pos[1],
          pos[ci]![2] - a.pos[2],
        ]
        newActive.set(p, {
          pos: pos[ci]!,
          vel: [
            V1.velSmooth * disp[0] + (1 - V1.velSmooth) * a.vel[0],
            V1.velSmooth * disp[1] + (1 - V1.velSmooth) * a.vel[1],
            V1.velSmooth * disp[2] + (1 - V1.velSmooth) * a.vel[2],
          ],
          mass: mass[ci]!,
          ref: { t, i: ci },
        })
      }

      // (b) phân bào: mẹ đã match nhận thêm con thứ 2
      let unmatched: number[] = []
      for (let j = 0; j < n; j++) if (!matchedCurr.has(j)) unmatched.push(j)
      if (V1.divEnabled && matchedCurr.size > 0) {
        const cands: { dP: number; p: number; j: number }[] = []
        for (const [ci, p] of matchedCurr) {
          const aP = active1.get(p)!
          const P = aP.pos
          const mP = aP.mass
          const C1 = pos[ci]!
          const mC1 = mass[ci]!
          for (const j of unmatched) {
            const B2 = pos[j]!
            const mB2 = mass[j]!
            const dP = physDist(P, B2)
            if (dP > V1.divParentGateUm) continue
            const dS = physDist(C1, B2)
            if (dS > V1.divSiblingGateUm) continue
            if (mP > 0) {
              if (mB2 < V1.divMinChildFrac * mP) continue
              if (V1.divBrightCheck) {
                const ratio = (mC1 + mB2) / mP
                if (ratio < V1.divBrightRatio[0] || ratio > V1.divBrightRatio[1]) continue
              }
            }
            cands.push({ dP, p, j })
          }
        }
        cands.sort((a, b) => a.dP - b.dP)
        const usedP = new Set<number>()
        const usedJ = new Set<number>()
        for (const { dP, p, j } of cands) {
          if (usedP.has(p) || usedJ.has(j)) continue
          usedP.add(p)
          usedJ.add(j)
          const aP = active1.get(p)!
          const P = aP.pos
          nid1++
          newActive.set(nid1, {
            pos: pos[j]!,
            vel: [pos[j]![0] - P[0], pos[j]![1] - P[1], pos[j]![2] - P[2]],
            mass: mass[j]!,
            ref: { t, i: j },
          })
          frameEdges.push({ at: t - 1, ai: aP.ref.i, bt: t, bi: j })
          divCount1++
        }
        unmatched = unmatched.filter((j) => !usedJ.has(j))
      }

      // (c) frame-skip + nội suy node tại khung mất
      if (pending1.size > 0 && unmatched.length > 0) {
        const pendIds = [...pending1.keys()]
        const pred = pendIds.map((q) => {
          const Q = pending1.get(q)!
          const m = Q.missed + 1
          return [
            Q.pos[0] + Q.vel[0] * m,
            Q.pos[1] + Q.vel[1] * m,
            Q.pos[2] + Q.vel[2] * m,
          ] as [number, number, number]
        })
        const C = unmatched.map((j) => pos[j]!)
        const D = pred.map((pp) => C.map((c) => physDist(pp, c)))
        const cost = D.map((row) => row.map((d) => (d <= V1.skipGateUm ? d : 1e9)))
        const assign = hungarian(cost)
        const takenJ = new Set<number>()
        for (let ri = 0; ri < pendIds.length; ri++) {
          const ci = assign[ri]
          if (ci === null) continue
          if (D[ri]![ci]! > V1.skipGateUm) continue
          const q = pendIds[ri]!
          const j = unmatched[ci]!
          takenJ.add(j)
          const Q = pending1.get(q)!
          const gap = Q.missed + 1
          let chain = Q.ref
          if (V1.interpolate && gap >= 2) {
            for (let k = 1; k < gap; k++) {
              const tk = t - gap + k
              const pm: [number, number, number] = [
                Q.pos[0] + (pos[j]![0] - Q.pos[0]) * (k / gap),
                Q.pos[1] + (pos[j]![1] - Q.pos[1]) * (k / gap),
                Q.pos[2] + (pos[j]![2] - Q.pos[2]) * (k / gap),
              ]
              const x = pm[2]
              const y = pm[1]
              const z = pm[0] / Z_UM_PER_VOXEL
              det1[tk]!.push({
                x, y, z,
                r: 2.6,
                i: Math.round((Q.mass + mass[j]!) / 54),
                mass: (Q.mass + mass[j]!) / 2,
                src: nearestSrc(sim, tk, x, y, z, 4.0),
              })
              const midIdx = det1[tk]!.length - 1
              frameEdges.push({ at: chain.t, ai: chain.i, bt: tk, bi: midIdx })
              chain = { t: tk, i: midIdx }
            }
          }
          frameEdges.push({ at: chain.t, ai: chain.i, bt: t, bi: j })
          newActive.set(q, {
            pos: pos[j]!,
            vel: [
              (pos[j]![0] - Q.pos[0]) / gap,
              (pos[j]![1] - Q.pos[1]) / gap,
              (pos[j]![2] - Q.pos[2]) / gap,
            ],
            mass: mass[j]!,
            ref: { t, i: j },
          })
          pending1.delete(q)
        }
        unmatched = unmatched.filter((j) => !takenJ.has(j))
      }

      // (d) dọn dẹp
      for (const [q, st] of pending1) {
        st.missed++
        if (st.missed > V1.maxSkipFrames) pending1.delete(q)
      }
      const matchedPrev = new Set(matchedCurr.values())
      for (const p of prevIds) {
        if (matchedPrev.has(p) || newActive.has(p)) continue
        const a = active1.get(p)!
        pending1.set(p, { ...a, missed: 1 })
      }
      for (const j of unmatched) {
        if ([...newActive.values()].some((s) => s.ref.t === t && s.ref.i === j)) continue
        nid1++
        newActive.set(nid1, { pos: pos[j]!, vel: [0, 0, 0], mass: mass[j]!, ref: { t, i: j } })
      }
      active1.clear()
      for (const [k, v] of newActive) active1.set(k, v)
      edges1.push(...frameEdges)
    }
    ms1 += performance.now() - tb

    if (t === 29) {
      nodes30v0 = det0.reduce((s, f) => s + f.length, 0)
      edges30v0 = edges0.length
      nodes30v1 = det1.reduce((s, f) => s + f.length, 0)
      edges30v1 = edges1.length
      div30v1 = divCount1
      ms30v0 = ms0
      ms30v1 = ms1
    }
  }

  const stats0: PipelineStats = {
    nodes: det0.reduce((s, f) => s + f.length, 0),
    edges: edges0.length,
    divisions: 0,
    ms: ms0,
    nodes30: nodes30v0, edges30: edges30v0, div30: 0, ms30: ms30v0,
  }
  const stats1: PipelineStats = {
    nodes: det1.reduce((s, f) => s + f.length, 0),
    edges: edges1.length,
    divisions: divCount1,
    ms: ms1,
    nodes30: nodes30v1, edges30: edges30v1, div30: div30v1, ms30: ms30v1,
  }
  return {
    ver0: { version: 'ver0', stats: stats0, det: det0, edges: edges0 },
    ver1: { version: 'ver1', stats: stats1, det: det1, edges: edges1 },
  }
}
