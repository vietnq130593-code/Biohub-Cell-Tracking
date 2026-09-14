# ver 4 · cell 3 — PIPELINE: ĐỌC ZARR → DETECTION (+TÁCH BLOB) → TRACKING
#                          → PHÂN BÀO THEO PROFILE ĐỘ SÁNG → STITCHING HẬU KIỂM
# Dán đè Cell 3 của notebook Kaggle (toàn bộ thuật toán nằm ở đây).
# ============================================================
# Thay đổi so với ver 3 (nhắm thẳng điểm nghẽn số 1 của 0.198 — track đứt):
#   * GATE_MIN_UM 5 → 7 (p99 bước GT 6,9µm — xem cell 2).
#   * MAX_SKIP_FRAMES 2 → 3.
#   * MỚI — STITCHING HẬU KIỂM: sau khi chạy hết dataset, mọi track kết
#     thúc ở khung t (node không có cạnh ra) được nối với track mở đầu ở
#     khung t+gap (node không có cạnh vào) nếu nằm trong gate + khối lượng
#     tương thích; gap ≥ 2 thì chèn node nội suy → chỉ cạnh liền khung.
#     Ba tình huống được cứu: (a) tế bào mờ > MAX_SKIP_FRAMES khung;
#     (b) blob gộp > MAX_SKIP_FRAMES khung làm track bạn đồng hành chết;
#     (c) tế bào quẹo khi mờ → dự đoán pos+vel·gap trượt khỏi SKIP_GATE.
# Phát hiện / phân bào giữ nguyên ver 3 (mass stability + 5 cửa).
# ============================================================
# Hotfix 13/09: cấu trúc 26-liên kết tạo TRỰC TIẾP trong detect_nodes —
# Cell 3 tự chứa, dán thiếu dòng đầu không còn gây NameError.
# Hotfix 14/09: TỰ CHỨA HOÀN TOÀN — cell 3 tự import (maximum_filter & co.)
# và tự kèm bộ cấu hình mặc định ver 4 → dán đè ĐƠN LẼ cell 3 vào notebook
# đang giữ cell 1/cell 2 BẢN CŨ vẫn chạy đúng (lỗi thực tế trên Kaggle:
# cell 1 cũ thiếu `maximum_filter` → NameError ngay khung đầu tiên).
# Cell 2 ver-4 đã chạy thì núm tune ở đó vẫn thắng (xem khối 0b bên dưới).
# ============================================================

# ---------- 0) IMPORT TỰ CHỮA ----------
# Import lại là vô hại (module đã load thì Python lấy từ cache) — cell 1
# ver-4 có dòng import trùng cũng không đổi hành vi gì.
import itertools
import json
import os
import time

import numpy as np
import pandas as pd
from scipy.ndimage import center_of_mass, label, maximum_filter, uniform_filter
from scipy.optimize import linear_sum_assignment
from scipy.spatial.distance import cdist

try:
    import blosc2
except ImportError as _e:
    raise ImportError(
        'Chưa có blosc2 — hãy chạy Cell 1 (pip install) trước rồi chạy lại '
        'cell này, hoặc gõ  !pip install -q blosc2  trong 1 cell riêng.'
    ) from _e

# ---------- 0b) CẤU HÌNH MẶC ĐỊNH ver 4 (phòng khi chỉ dán đè cell 3) ----------
# CHỈ áp khi cell 2 ver-4 CHƯA chạy trong notebook này (chưa có
# PIPELINE_CONFIG_VERSION) — cell 2 ver-4 đã chạy thì giữ nguyên núm của nó
# (tune ở cell 2). DATA_DIR đã được ai đó đặt sẵn (bản chạy-train, test cục
# bộ) cũng được tôn trọng. Bộ giá trị bên dưới PHẢI GIỮ ĐỒNG BỘ với cell 2.
if globals().get('PIPELINE_CONFIG_VERSION', 0) < 4:
    if 'DATA_DIR' not in globals():
        TEST_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/test'
        # bản nộp bài đọc test; muốn chấm bằng local scorer thì trỏ sang train
        DATA_DIR = TEST_DIR

    # Thang vật lý (Z, Y, X) — µm/voxel, theo đề bài
    SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)

    # --- Tầng 1 · DETECTION ---
    DS_Z, DS_Y, DS_X = 2, 4, 4       # downsample bất đối xứng: z giữ kỹ hơn
    SMOOTH_SIZE = 3                  # uniform_filter, trong không gian downsample
    PERCENTILE = 90.0                # bắt thêm nhân mờ (recall > precision)
    MIN_NVOXELS = 4                  # bỏ component li ti (nhiễu)
    MAX_NVOXELS = 3000               # blob gộp vẫn nhận, tách ở tầng 1b
    CONN26 = True                    # liên kết 26-ô: chống tách nhân giữa các lát z

    # --- Tầng 1b · TÁCH BLOB GỘP ---
    SPLIT_MIN_NVOXELS = 90           # component ds lớn hơn mới xét tách
    PEAK_SIZE = (3, 5, 5)            # maximum_filter tìm đỉnh cục bộ (z,y,x ds)
    MIN_PEAK_DIST_DS = 4.0           # 2 đỉnh cách ≥ 4 voxel ds
    PEAK_MIN_BRIGHT = 1.15           # đỉnh sáng hơn ngưỡng ít nhất 15%

    # --- Tầng 2 · LINKING (ver 4: GATE_MIN 5 → 7) ---
    BASE_GATE_UM = 9.0
    GATE_MEDIAN_MULT = 2.5
    GATE_MIN_UM, GATE_MAX_UM = 7.0, 14.0   # p99 bước GT 6,9µm — min 5 giết bước hợp lệ
    VEL_SMOOTH = 0.5                 # vận tốc EMA: v ← 0.5·mới + 0.5·cũ
    BRIGHT_WEIGHT = 0.0              # phạt chênh độ sáng trong cost (tắt)

    # --- Frame-skip + nội suy (ver 4: MAX_SKIP 2 → 3) ---
    ALLOW_FRAME_SKIP = True
    SKIP_GATE_UM = 12.0
    MAX_SKIP_FRAMES = 3
    INTERPOLATE_MISSED_FRAMES = True  # GT 100% cạnh liền khung → nội suy bắt buộc
    TIME_LIMIT_HOURS = 11.0

    # --- ver 4 · STITCHING HẬU KIỂM (chạy trong cell 3) ---
    STITCH_ENABLED = True
    STITCH_GAP_MAX = 5               # nối lại track đứt cách ≤ 5 khung
    STITCH_GATE_UM = 10.0            # gate tại gap=1: bắt bước 7–10µm
    STITCH_GATE_PER_GAP = 2.0        # gate(g) = 10 + 2·(g−1) µm (g=5 → 18)
    STITCH_MAX_LOGMASS = 1.1         # |ln(m_start/m_end)| ≤ 1,1 (~3×)
    STITCH_COLLISION_UM = 0.0        # 0 = tắt: hành lang nối blob-break đi đúng
                                     # qua node CoM của track bạn đồng hành

    # --- Tầng 3 · PHÂN BÀO THEO PROFILE ĐỘ SÁNG ---
    DIVISION_ENABLED = True
    DIV_PARENT_GATE_UM = 12.0        # cửa sổ tìm kiếm (base rate 24:1)
    DIV_SIBLING_GATE_UM = 14.5       # p99 sister sep 13,9, max 14,65
    DIV_MIN_CHILD_FRAC = 0.15
    DIV_BRIGHTNESS_CHECK = True
    DIV_BRIGHTNESS_RATIO = (0.55, 1.8)
    DIV_CONFIRM_FRAMES = 3
    DIV_SEP_GROWTH = 1.15
    MASS_HISTORY = 12
    MASS_SKIP_LAST = 2
    DIV_MOM_MAX_RISE = 1.7
    DIV_MOM_MIN_FRAC = 0.5
    DIV_MOM_BRIGHT_BONUS = 1.05
    MASS_BASE_MIN_FRAMES = 4

    # --- Soát bằng mắt (vẽ 1 khung đầu tiên) — tôn trọng ai đã tắt trước đó ---
    RUN_PREVIEW = globals().get('RUN_PREVIEW', True)

    # --- Chẩn đoán ---
    DIAGNOSE = True

    NODE_ID = itertools.count(1)     # node_id duy nhất toàn cục
    BIG = 1e9

    PIPELINE_CONFIG_VERSION = 4      # đánh dấu đã áp cấu hình ver-4

T_START = time.time()


def _over_time_budget():
    return (time.time() - T_START) > TIME_LIMIT_HOURS * 3600.0


# ---------- 1) ĐỌC DỮ LIỆU (giữ nguyên ver 2) ----------
def read_zarr_meta(zarr_path):
    """Đọc shape/dtype/chunk grid từ zarr.json của mảng (như notebook gốc)."""
    with open(os.path.join(zarr_path, '0', 'zarr.json')) as f:
        meta = json.load(f)
    shape = tuple(int(v) for v in meta['shape'])            # (T, Z, Y, X)
    dtype = np.dtype(meta['data_type'])
    chunk = meta.get('chunk_grid', {}).get('configuration', {}).get('chunk_shape')
    if not chunk or len(chunk) != 4:
        chunk = [1, shape[1], shape[2], shape[3]]
    return shape, dtype, [int(c) for c in chunk]


def load_volume(zarr_path, t, shape, dtype, chunk):
    """Đọc khung t → (Z, Y, X). Chunk 0/0/0 là đường nhanh như notebook gốc;
    nếu khung được chia nhiều chunk thì lắp ghép đủ các chunk có mặt."""
    T, Z, Y, X = shape
    _, cZ, cY, cX = chunk
    croot = os.path.join(zarr_path, '0', 'c', str(t))
    if not os.path.isdir(croot):
        raise FileNotFoundError(f'không tìm thấy khung t={t}: {croot}')

    def read_chunk(cz, cy, cx):
        p = os.path.join(croot, str(cz), str(cy), str(cx))
        with open(p, 'rb') as f:
            return np.frombuffer(blosc2.decompress(f.read()), dtype=dtype)

    # Đường nhanh: metadata nói 1 chunk chứa cả khung
    if (cZ, cY, cX) == (Z, Y, X):
        try:
            arr = read_chunk(0, 0, 0)
            if arr.size == Z * Y * X:
                return arr.reshape(Z, Y, X)
        except Exception:
            pass  # rơi xuống đường đa chunk bên dưới

    vol = np.zeros((Z, Y, X), dtype=dtype)
    placed = 0
    for cz in range((Z + cZ - 1) // cZ):
        for cy in range((Y + cY - 1) // cY):
            for cx in range((X + cX - 1) // cX):
                p = os.path.join(croot, str(cz), str(cy), str(cx))
                if not os.path.isfile(p):
                    continue
                try:
                    arr = read_chunk(cz, cy, cx)
                except Exception:
                    continue
                vz = min(cZ, Z - cz * cZ)
                vy = min(cY, Y - cy * cY)
                vx = min(cX, X - cx * cX)
                if vz <= 0 or vy <= 0 or vx <= 0:
                    continue
                if arr.size >= cZ * cY * cX:      # chunk đầy (zarr v3 pad theo fill)
                    block = arr[:cZ * cY * cX].reshape(cZ, cY, cX)[:vz, :vy, :vx]
                elif arr.size >= vz * vy * vx:     # biến thể chunk gọn ở biên
                    block = arr[:vz * vy * vx].reshape(vz, vy, vx)
                else:
                    continue
                vol[cz * cZ:cz * cZ + vz, cy * cY:cy * cY + vy, cx * cX:cx * cX + vx] = block
                placed += 1
    if placed == 0:
        raise FileNotFoundError(f'khung t={t}: không đọc được chunk nào từ {croot}')
    return vol


# ---------- 2) DETECTION + TÁCH BLOB GỘP (giữ nguyên ver 2) ----------
def _com(coords, w):
    """Center-of-mass theo cường độ của tập voxel (z,y,x ds, float)."""
    s = w.sum()
    if s <= 0:
        return coords.mean(axis=0)
    return (coords * w[:, None]).sum(axis=0) / s


def detect_nodes(vol):
    """Trả về list dict: z, y, x (voxel gốc, int — đúng format đề bài) và
    zf, yf, xf (float — cho tracking), mass (tổng cường độ), nvox."""
    ds = vol[::DS_Z, ::DS_Y, ::DS_X].astype(np.float32)
    if ds.size == 0:
        return []
    smoothed = uniform_filter(ds, size=SMOOTH_SIZE)
    thr = np.percentile(smoothed, PERCENTILE)
    mask = smoothed > thr
    labeled, n = label(mask, structure=np.ones((3, 3, 3), dtype=bool) if CONN26 else None)
    if n == 0:
        return []

    # đỉnh cục bộ (tính 1 lần cả khung): voxel = max trong lân cận PEAK_SIZE
    # và sáng hơn ngưỡng ít nhất PEAK_MIN_BRIGHT (chống đỉnh nhiễu)
    mf = maximum_filter(smoothed, size=PEAK_SIZE)
    is_peak = (smoothed == mf) & mask & (smoothed >= thr * PEAK_MIN_BRIGHT)

    lab_flat = labeled.ravel()
    counts = np.bincount(lab_flat, minlength=n + 1)
    wsums = np.bincount(lab_flat, weights=smoothed.ravel(), minlength=n + 1).astype(np.float64)
    coms = center_of_mass(smoothed, labeled, index=range(1, n + 1))

    # trọng số khoảng cách trong không gian ds: z gấp đôi (bước z dài gấp đôi)
    ZW = np.array([2.0, 1.0, 1.0])

    nodes = []
    for i in range(1, n + 1):
        nv = int(counts[i])
        if nv < MIN_NVOXELS or nv > MAX_NVOXELS:
            continue

        split_done = False
        if nv > SPLIT_MIN_NVOXELS:
            comp = np.argwhere(labeled == i)                # (N, 3) z,y,x
            pk_mask = is_peak[comp[:, 0], comp[:, 1], comp[:, 2]]
            peaks = comp[pk_mask]
            if len(peaks) >= 2:
                # giữ các đỉnh sáng nhất, bỏ đỉnh quá gần một đỉnh đã giữ
                vals = smoothed[peaks[:, 0], peaks[:, 1], peaks[:, 2]]
                order = np.argsort(-vals)
                kept = []
                for idx in order:
                    p = peaks[idx].astype(np.float64)
                    too_close = False
                    for q in kept:
                        if np.linalg.norm((p - q) * ZW) < MIN_PEAK_DIST_DS:
                            too_close = True
                            break
                    if not too_close:
                        kept.append(p)
                if len(kept) >= 2:
                    # gán mỗi voxel component → đỉnh gần nhất; CoM riêng từng vùng
                    P = np.array(kept)
                    D = cdist(comp.astype(np.float64) * ZW, P * ZW)
                    assign = D.argmin(axis=1)
                    w_all = smoothed[comp[:, 0], comp[:, 1], comp[:, 2]].astype(np.float64)
                    for k in range(len(kept)):
                        sel = assign == k
                        sub = comp[sel]
                        w = w_all[sel]
                        if sub.shape[0] < MIN_NVOXELS:
                            continue
                        cz, cy, cx = _com(sub.astype(np.float64), w)
                        nodes.append({
                            'z': int(round(cz * DS_Z)), 'y': int(round(cy * DS_Y)),
                            'x': int(round(cx * DS_X)),
                            'zf': cz * DS_Z, 'yf': cy * DS_Y, 'xf': cx * DS_X,
                            'mass': float(w.sum()), 'nvox': int(sub.shape[0]),
                        })
                    split_done = True
        if split_done:
            continue

        cz, cy, cx = coms[i - 1]
        nodes.append({
            'z': int(round(cz * DS_Z)), 'y': int(round(cy * DS_Y)), 'x': int(round(cx * DS_X)),
            'zf': cz * DS_Z, 'yf': cy * DS_Y, 'xf': cx * DS_X,
            'mass': float(wsums[i]), 'nvox': nv,
        })
    return nodes


# ---------- 3) TRACKER (ver 3: profile độ sáng cho phân bào) ----------
def _mass_baseline(hist):
    """Baseline khối lượng của track: PERCENTILE 25 của MASS_HISTORY giá trị
    gần nhất, BỎ MASS_SKIP_LAST khung cuối (đúng khoảng mẹ sáng lên trước
    khi chia). Dùng p25 thay vì median: blob gộp merge-split (≈2×) tồn tại
    nửa cửa sổ vẫn không kéo được baseline lên — median thì được (bug đã
    bắt gặp khi kiểm chứng trên mô phỏng TS), còn p25 vẫn kháng được 1–2
    khung mờ nháp. Trả về None nếu chưa đủ dữ liệu."""
    if len(hist) < MASS_BASE_MIN_FRAMES + MASS_SKIP_LAST:
        return None
    kept = hist[-(MASS_HISTORY + MASS_SKIP_LAST):-MASS_SKIP_LAST]
    if not kept:
        return None
    return float(np.percentile(kept, 25))


class Tracker:
    """Hungarian + motion model + tách blob + PHÂN BÀO THEO PROFILE ĐỘ SÁNG.

    Mỗi khung gồm 5 bước:
      (a) Hungarian giữa node khung trước (đặt tại vị trí DỰ ĐOÁN) và node
          khung hiện tại, gate thích ứng
      (b) phân bào ỨNG VIÊN — 5 CỬA:
          1. parent gate 12µm (cửa sổ tìm kiếm — base rate 24:1 nên khoảng
             cách không còn là tín hiệu)
          2. sibling gate 14,5µm (p99 thật 13,9 — bắt cả cặp chị em xa)
          3. bảo toàn độ sáng (con1+con2 ≈ mẹ) + con thứ 2 ≥ 15% mẹ
          4. MỚI — ỔN ĐỊNH KHỐI LƯỢNG MẸ: khối lượng blob mẹ tại khung tách
             ≤ 1,7× baseline riêng của nó (blob gộp 2 tế bào ≈ 2×; mẹ thật
             chỉ sáng lên nhẹ) và ≥ 0,5× (mẹ không phai đột ngột)
          5. MỚI — Ưu tiên appearance: ứng viên có mẹ sáng dần ≥ 5% xếp trước
          Cạnh divergence vẫn HOÃN chờ bước (e)
      (c) frame-skip: nối lại track mất ≤ 2 khung + nội suy node giữa
      (d) dọn dẹp
      (e) xác nhận động học: 2 con sống ≥ DIV_CONFIRM_FRAMES khung và
          khoảng cách tăng ≥ 15% — cạnh + division chỉ ghi khi vượt hết
    """

    def __init__(self):
        self.active = {}        # nid → dict(pos, vel, mass, mass_hist)
        self.pending = {}       # nid → dict(pos, vel, mass, mass_hist, missed)
        self.recent_steps = []  # bước đi (µm) của các match gần đây
        self.div_pending = []   # ứng viên phân bào chờ xác nhận
        self.n_div_confirmed = 0
        self.n_div_rejected = 0
        # ver 3: đếm lý do từ chối để chẩn đoán
        self.n_rej_mass = 0        # rớt ổn định khối lượng mẹ (bước b — MỚI)
        self.n_rej_lost = 0        # một con biến mất (bước e)
        self.n_rej_dyn = 0         # không tách ra đủ (bước e)

    def _gate(self):
        if len(self.recent_steps) < 5:
            return BASE_GATE_UM
        med = float(np.median(self.recent_steps))
        return float(np.clip(GATE_MEDIAN_MULT * med, GATE_MIN_UM, GATE_MAX_UM))

    @staticmethod
    def _push_hist(hist, m):
        h = list(hist)
        h.append(float(m))
        if len(h) > MASS_HISTORY + MASS_SKIP_LAST + 2:
            del h[:len(h) - (MASS_HISTORY + MASS_SKIP_LAST + 2)]
        return h

    def step(self, dets, t):
        """Xử lý khung t. Trả về (nodes, edges, divisions, interp_nodes)."""
        nodes = [(next(NODE_ID), d) for d in dets]
        ids = [nid for nid, _ in nodes]
        pos = np.array(
            [[d['zf'], d['yf'], d['xf']] for _, d in nodes], dtype=np.float64,
        ).reshape(-1, 3) * SCALE
        mass = [float(d['mass']) for _, d in nodes]

        edges, divisions, interp_nodes = [], [], []
        matched_curr = {}   # curr_idx → prev nid
        succ = {}           # prev nid → nid khung này (nối mạch cho bước (e))

        # ---- (a) matching chính: Hungarian trên vị trí DỰ ĐOÁN ----
        prev_ids = list(self.active.keys())
        if prev_ids and ids:
            pred = np.array(
                [self.active[p]['pos'] + self.active[p]['vel'] for p in prev_ids],
            )
            D = np.linalg.norm(pred[:, None, :] - pos[None, :, :], axis=2)
            gate = self._gate()
            cost = D
            if BRIGHT_WEIGHT > 0:
                mp = np.maximum(
                    np.array([self.active[p]['mass'] for p in prev_ids])[:, None], 1e-9)
                mc = np.maximum(np.array(mass)[None, :], 1e-9)
                cost = D * (1.0 + BRIGHT_WEIGHT * np.abs(np.log(mc / mp)))
            cost = np.where(D <= gate, cost, BIG)
            ri, ci = linear_sum_assignment(cost)
            for r, c in zip(ri, ci):
                if D[r, c] > gate:
                    continue
                p = prev_ids[r]
                matched_curr[c] = p
                succ[p] = ids[c]
                edges.append((p, ids[c]))
                self.recent_steps.append(
                    float(np.linalg.norm(pos[c] - self.active[p]['pos'])))
            if len(self.recent_steps) > 200:
                del self.recent_steps[:100]

        new_active = {}
        for c, p in matched_curr.items():
            a = self.active[p]
            disp = pos[c] - a['pos']
            vel = VEL_SMOOTH * disp + (1.0 - VEL_SMOOTH) * a['vel']
            # ver 3: lịch sử khối lượng đi THEO TRACK (chuyển từ nid cũ sang nid mới)
            new_active[ids[c]] = {
                'pos': pos[c], 'vel': vel, 'mass': mass[c],
                'mass_hist': self._push_hist(a['mass_hist'], mass[c]),
            }

        # ---- (b) phân bào ỨNG VIÊN (5 cửa — cạnh hoãn chờ bước (e)) ----
        unmatched = [j for j in range(len(ids)) if j not in matched_curr]
        if DIVISION_ENABLED and matched_curr:
            cands = []
            A_vel_cache = {p: self.active[p]['vel'] for p in matched_curr.values()}
            for c, p in matched_curr.items():
                A = self.active[p]
                P, mP, hist = A['pos'], A['mass'], A['mass_hist']
                C1, mC1 = pos[c], mass[c]
                base = _mass_baseline(hist)          # None nếu track quá non
                for j in unmatched:
                    B2, mB2 = pos[j], mass[j]
                    dP = float(np.linalg.norm(P - B2))
                    if dP > DIV_PARENT_GATE_UM:
                        continue
                    dS = float(np.linalg.norm(C1 - B2))
                    if dS > DIV_SIBLING_GATE_UM:
                        continue
                    if mP > 0:
                        if mB2 < DIV_MIN_CHILD_FRAC * mP:
                            continue
                        if DIV_BRIGHTNESS_CHECK:
                            ratio = (mC1 + mB2) / mP
                            if not (DIV_BRIGHTNESS_RATIO[0] <= ratio <= DIV_BRIGHTNESS_RATIO[1]):
                                continue
                    # --- MỚI ver 3: cửa 4 — ổn định khối lượng mẹ ---
                    rise = (mP / base) if (base and base > 0) else None
                    if rise is not None:
                        if rise > DIV_MOM_MAX_RISE:
                            # blob "mẹ" gộp ~2 tế bào → merge-split giả
                            self.n_rej_mass += 1
                            continue
                        if rise < DIV_MOM_MIN_FRAC:
                            # mẹ phai đột ngột → detection không ổn định
                            self.n_rej_mass += 1
                            continue
                    # --- MỚI ver 3: cửa 5 (soft) — ưu tiên mẹ sáng dần ---
                    bright = (rise is not None and rise >= DIV_MOM_BRIGHT_BONUS)
                    cands.append((0 if bright else 1, dP, p, c, j, rise))
            # sort: (mẹ sáng dần trước, rồi tới khoảng cách)
            cands.sort()
            used_p, used_j = set(), set()
            for _prio, dP, p, c, j, rise in cands:
                if p in used_p or j in used_j:
                    continue
                used_p.add(p)
                used_j.add(j)
                # con thứ 2 khởi động như track mới; cạnh p→ids[j] HOÃN,
                # chỉ ghi nếu được xác nhận ở bước (e) của các khung sau
                # QUAN TRỌNG: con KẾ THỪA vận tốc mẹ — không phải vectơ
                # mẹ→con! (vectơ đó làm dự đoán khung sau vọt xa vị trí thật
                # → con không match được → ứng viên chết "lost" và bị đề
                # xuất lại mỗi khung — vòng lặp đã bắt gặp khi kiểm chứng)
                new_active[ids[j]] = {
                    'pos': pos[j], 'vel': np.array(A_vel_cache[p]), 'mass': mass[j],
                    'mass_hist': [mass[j]],
                }
                self.div_pending.append({
                    't': t, 'mother': p, 'mother_mass': self.active[p]['mass'],
                    'mother_rise': rise,
                    'c1': ids[c], 'c2': ids[j], 'c2_start': ids[j],
                    'd0': float(np.linalg.norm(pos[c] - pos[j])), 'age': 0,
                })
            unmatched = [j for j in unmatched if j not in used_j]

        # ---- (c) frame-skip: nối lại track mất ≤ MAX_SKIP_FRAMES khung ----
        if ALLOW_FRAME_SKIP and self.pending and unmatched:
            pend_ids = list(self.pending.keys())
            pred = np.array([
                self.pending[q]['pos'] + self.pending[q]['vel'] * (self.pending[q]['missed'] + 1)
                for q in pend_ids
            ])
            C = pos[np.array(unmatched, dtype=int)]
            D = np.linalg.norm(pred[:, None, :] - C[None, :, :], axis=2)
            cost = np.where(D <= SKIP_GATE_UM, D, BIG)
            ri, ci = linear_sum_assignment(cost)
            for r, c in zip(ri, ci):
                if D[r, c] > SKIP_GATE_UM:
                    continue
                q, j = pend_ids[r], unmatched[c]
                Q = self.pending[q]
                gap = Q['missed'] + 1
                if INTERPOLATE_MISSED_FRAMES and gap >= 2:
                    # Chèn node nội suy tại các khung bị mất rồi nối các cạnh
                    # LIỀN KHUNG — cạnh nhảy t→t+2 bị metric bỏ hẳn.
                    chain = q
                    for k in range(1, gap):
                        pm = Q['pos'] + (pos[j] - Q['pos']) * (k / gap)  # µm
                        vf = pm / SCALE
                        mid = next(NODE_ID)
                        interp_nodes.append((mid, t - gap + k, {
                            'z': int(round(vf[0])), 'y': int(round(vf[1])), 'x': int(round(vf[2])),
                            'zf': float(vf[0]), 'yf': float(vf[1]), 'xf': float(vf[2]),
                            'mass': (Q['mass'] + mass[j]) / 2.0, 'nvox': 0,
                        }))
                        edges.append((chain, mid))
                        chain = mid
                    edges.append((chain, ids[j]))
                new_active[ids[j]] = {
                    'pos': pos[j],
                    'vel': (pos[j] - Q['pos']) / gap,
                    'mass': mass[j],
                    'mass_hist': self._push_hist(Q['mass_hist'], mass[j]),
                }
                succ[q] = ids[j]
                self.pending.pop(q, None)
            unmatched = [j for j in unmatched if ids[j] not in new_active]

        # ---- (d) dọn dẹp ----
        for q in list(self.pending.keys()):
            self.pending[q]['missed'] += 1
            if self.pending[q]['missed'] > MAX_SKIP_FRAMES:
                del self.pending[q]

        matched_prev = set(matched_curr.values())
        for p in prev_ids:
            if p in matched_prev:
                continue
            a = self.active[p]
            self.pending[p] = {'pos': a['pos'], 'vel': a['vel'],
                               'mass': a['mass'], 'mass_hist': a['mass_hist'],
                               'missed': 1}

        for j in unmatched:
            if ids[j] not in new_active:
                new_active[ids[j]] = {
                    'pos': pos[j], 'vel': np.zeros(3), 'mass': mass[j],
                    'mass_hist': [mass[j]],
                }

        # ---- (e) xác nhận phân bào: đủ tuổi + khoảng cách 2 con tăng ----
        still_pending = []
        for cand in self.div_pending:
            if cand['age'] == 0:
                # candidate vừa tạo ở bước (b) của CHÍNH step này — c1/c2 là
                # node của khung hiện tại, chưa bao giờ là "prev" nên chưa
                # có trong succ; chỉ tăng tuổi và chờ step sau
                cand['age'] = 1
                still_pending.append(cand)
                continue
            c1 = succ.get(cand['c1'])
            c2 = succ.get(cand['c2'])
            if c1 is None or c2 is None:
                self.n_div_rejected += 1          # một "con" biến mất → bỏ
                self.n_rej_lost += 1
                continue
            cand['c1'], cand['c2'] = c1, c2
            cand['age'] += 1
            if cand['age'] > DIV_CONFIRM_FRAMES:
                a1, a2 = new_active.get(c1), new_active.get(c2)
                if a1 is not None and a2 is not None:
                    d_now = float(np.linalg.norm(a1['pos'] - a2['pos']))
                    if d_now >= DIV_SEP_GROWTH * cand['d0']:
                        # XÁC NHẬN: ghi cạnh hoãn (mẹ t-1 → con thứ 2 t) —
                        # vẫn là cạnh liền khung vì mẹ/con1/con2 sinh cùng lượt
                        edges.append((cand['mother'], cand['c2_start']))
                        divisions.append((cand['mother'], cand['c2_start']))
                        self.n_div_confirmed += 1
                        continue
                self.n_div_rejected += 1          # không tách ra → merge-split giả
                self.n_rej_dyn += 1
                continue
            still_pending.append(cand)
        self.div_pending = still_pending

        self.active = new_active
        return nodes, edges, divisions, interp_nodes


# ---------- 4) CHẠY TOÀN BỘ TEST SET + CHẨN ĐOÁN ----------
def diagnose(rows):
    """Thống kê "sức khoẻ" submission — phát hiện sớm lỗi cấu trúc.
    Trả về chuỗi log để in cùng kết quả dataset."""
    nd = [r for r in rows if r['row_type'] == 'node']
    ed = [r for r in rows if r['row_type'] == 'edge']
    if not nd:
        return 'không có node'
    node_ids = {r['node_id'] for r in nd}
    has_in = {r['target_id'] for r in ed if r['target_id'] in node_ids}
    forks = {}
    for r in ed:
        if r['source_id'] in node_ids:
            forks[r['source_id']] = forks.get(r['source_id'], 0) + 1
    n_div = sum(1 for v in forks.values() if v >= 2)
    # track = thành phần liên thông yếu
    parent = {i: i for i in node_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in ed:
        s, d = r['source_id'], r['target_id']
        if s in parent and d in parent:
            parent[find(s)] = find(d)
    from collections import Counter
    sizes = Counter(find(i) for i in node_ids)
    med_track = float(np.median(list(sizes.values()))) if sizes else 0.0
    n_no_in = sum(1 for r in nd if r['node_id'] not in has_in)
    t_lo = min(r['t'] for r in nd)
    t_hi = max(r['t'] for r in nd)
    frames = t_hi - t_lo + 1
    return (f"{len(nd)} node · {len(ed)} cạnh · {n_div} phân bào · "
            f"{n_no_in}/{len(nd)} node không cạnh vào ({100.0 * n_no_in / len(nd):.0f}%) · "
            f"{len(sizes)} track · trung vị {med_track:.0f} node/track · "
            f"{len(nd) / max(1, frames):.1f} node/khung · "
            f"phân bào xác nhận/từ chối: {TRK.n_div_confirmed}/{TRK.n_div_rejected} "
            f"(rớt mass: {TRK.n_rej_mass} · rớt động học: {TRK.n_rej_dyn} · "
            f"mất con: {TRK.n_rej_lost})")


# ---------- 4.5) STITCHING HẬU KIỂM (mới ver 4) ----------
def stitch_tracks(rows, meta):
    """Nối lại track đứt SAU khi chạy hết dataset — xem cell 2 (ver 4).

    end = node không có cạnh ra; start = node không có cạnh vào. Với mỗi
    gap = 1..STITCH_GAP_MAX (xét từ nhỏ đến lớn): mọi cặp (end ở khung t,
    start ở khung t+gap) trong gate STITCH_GATE_UM + STITCH_GATE_PER_GAP·
    (gap−1) và |ln khối lượng| ≤ STITCH_MAX_LOGMASS → Hungarian toàn cục
    trên nhóm (một end ghép một start) → gap ≥ 2 chèn node nội suy tại
    các khung giữa rồi nối CHUỖI cạnh liền khung (không bao giờ tạo cạnh
    nhảy t→t+k — metric bỏ hẳn cạnh nhảy).

    STITCH_COLLISION_UM > 0 sẽ chặn nếu đường nội suy đụng node đã có —
    MẶC ĐỊNH TẮT vì hành lang nối blob-break đi đúng qua node CoM của
    track bạn đồng hành; metric tự collapse cạnh trùng (merge-collapse)
    nên chuỗi song song không tạo FP cạnh, còn node thừa chỉ bị phạt nhẹ.

    Trả về (n_stitch, n_interp, n_edge); sửa `rows` tại chỗ."""
    if not STITCH_ENABLED:
        return 0, 0, 0
    node_rows = [r for r in rows if r['row_type'] == 'node']
    edge_rows = [r for r in rows if r['row_type'] == 'edge']
    has_out = {r['source_id'] for r in edge_rows}
    has_in = {r['target_id'] for r in edge_rows}

    ends_by_t, starts_by_t, nodes_by_t = {}, {}, {}
    for r in node_rows:
        if r['node_id'] not in meta:
            continue
        nodes_by_t.setdefault(r['t'], []).append(r['node_id'])
        if r['node_id'] not in has_out:
            ends_by_t.setdefault(r['t'], []).append(r['node_id'])
        if r['node_id'] not in has_in:
            starts_by_t.setdefault(r['t'], []).append(r['node_id'])

    def _pos(nid):
        return np.array(meta[nid][1:4])          # (z, y, x) µm float

    def _blocked(mid_pos, t):
        """đường nội suy đụng node đã có (chỉ khi bật collision check)."""
        if STITCH_COLLISION_UM <= 0:
            return False
        for nid in nodes_by_t.get(t, ()):         # noqa: B007
            if float(np.linalg.norm(_pos(nid) - mid_pos)) < STITCH_COLLISION_UM:
                return True
        return False

    dataset = rows[0]['dataset'] if rows else ''
    used_e, used_s = set(), set()
    added_nodes, added_edges = [], []
    n_stitch = 0

    for gap in range(1, STITCH_GAP_MAX + 1):
        gate = STITCH_GATE_UM + STITCH_GATE_PER_GAP * (gap - 1)
        for te in sorted(ends_by_t):
            E = [e for e in ends_by_t[te] if e not in used_e]
            S = [s for s in starts_by_t.get(te + gap, []) if s not in used_s]
            if not E or not S:
                continue
            cand = []
            for e in E:
                pe = _pos(e)
                me = meta[e][4]
                for s in S:
                    ps = _pos(s)
                    d = float(np.linalg.norm(ps - pe))
                    if d > gate:
                        continue    # d = 0 hợp lệ: tế bào đứng yên mờ rồi sáng lại
                    ms = meta[s][4]
                    if me > 0 and ms > 0 and abs(np.log(ms / me)) > STITCH_MAX_LOGMASS:
                        continue
                    ok = True
                    for k in range(1, gap):
                        pm = pe + (ps - pe) * (k / gap)
                        if _blocked(pm, te + k):
                            ok = False
                            break
                    if ok:
                        cand.append((d, e, s))
            if not cand:
                continue
            ei = sorted({e for _, e, _ in cand})
            si = sorted({s for _, _, s in cand})
            ie = {e: i for i, e in enumerate(ei)}
            isx = {s: i for i, s in enumerate(si)}
            D = np.full((len(ei), len(si)), BIG)
            for d, e, s in cand:
                D[ie[e], isx[s]] = d
            ri, ci = linear_sum_assignment(D)
            for r_, c_ in zip(ri, ci):
                if D[r_, c_] >= BIG:
                    continue
                e, s = ei[r_], si[c_]
                used_e.add(e)
                used_s.add(s)
                pe, ps = _pos(e), _pos(s)
                chain = e
                for k in range(1, gap):
                    pm = pe + (ps - pe) * (k / gap)          # µm
                    vf = pm / SCALE                             # voxel float
                    mid = next(NODE_ID)
                    meta[mid] = (te + k, float(pm[0]), float(pm[1]), float(pm[2]),
                                 (meta[e][4] + meta[s][4]) / 2.0)
                    nodes_by_t.setdefault(te + k, []).append(mid)
                    added_nodes.append({
                        'dataset': dataset, 'row_type': 'node', 'node_id': mid,
                        't': te + k, 'z': int(round(vf[0])), 'y': int(round(vf[1])),
                        'x': int(round(vf[2])), 'source_id': -1, 'target_id': -1,
                    })
                    added_edges.append((chain, mid))
                    chain = mid
                added_edges.append((chain, s))
                n_stitch += 1

    for a, b in added_edges:
        rows.append({
            'dataset': dataset, 'row_type': 'edge', 'node_id': -1,
            't': -1, 'z': -1, 'y': -1, 'x': -1,
            'source_id': a, 'target_id': b,
        })
    rows.extend(added_nodes)
    return n_stitch, len(added_nodes), len(added_edges)


if not os.path.isdir(DATA_DIR):
    hint = os.listdir('/kaggle/input') if os.path.isdir('/kaggle/input') else 'không có /kaggle/input'
    raise FileNotFoundError(f'Không thấy {DATA_DIR} — hãy Add Input competition. /kaggle/input: {hint}')

test_folder_names = sorted(
    d.replace('.zarr', '') for d in os.listdir(DATA_DIR) if d.endswith('.zarr')
)
if not test_folder_names:
    raise RuntimeError(f'Không tìm thấy thư mục .zarr nào trong {DATA_DIR}: {os.listdir(DATA_DIR)[:10]}')
print(f'{len(test_folder_names)} dataset: {test_folder_names}')

all_rows = []
summary = []
STOPPED_EARLY = False

for folder_name in test_folder_names:
    zarr_path = os.path.join(DATA_DIR, folder_name + '.zarr')
    shape, dtype, chunk = read_zarr_meta(zarr_path)
    n_t = shape[0]

    TRK = Tracker()
    ds_rows = []
    node_meta = {}     # nid → (t, zµm, yµm, xµm, mass) — cho stitching hậu kiểm
    n_nodes = n_edges = n_div = 0
    t0 = time.time()

    for t in range(n_t):
        if _over_time_budget():
            print(f'!! Gần hết ngân sách {TIME_LIMIT_HOURS}h — dừng tại {folder_name} t={t}')
            STOPPED_EARLY = True
            break
        try:
            vol = load_volume(zarr_path, t, shape, dtype, chunk)
        except (FileNotFoundError, ValueError) as e:
            print(f'  [{folder_name}] lỗi đọc khung {t}: {e} — bỏ qua')
            continue
        dets = detect_nodes(vol)
        nodes, edges, divisions, interp_nodes = TRK.step(dets, t)

        for nid, d in nodes:
            ds_rows.append({
                'dataset': folder_name, 'row_type': 'node', 'node_id': nid,
                't': t, 'z': d['z'], 'y': d['y'], 'x': d['x'],
                'source_id': -1, 'target_id': -1,
            })
            node_meta[nid] = (t, d['zf'] * SCALE[0], d['yf'] * SCALE[1],
                              d['xf'] * SCALE[2], float(d['mass']))
        for nid, tk, d in interp_nodes:
            ds_rows.append({
                'dataset': folder_name, 'row_type': 'node', 'node_id': nid,
                't': tk, 'z': d['z'], 'y': d['y'], 'x': d['x'],
                'source_id': -1, 'target_id': -1,
            })
            node_meta[nid] = (tk, d['zf'] * SCALE[0], d['yf'] * SCALE[1],
                              d['xf'] * SCALE[2], float(d['mass']))
        for src, dst in edges:
            ds_rows.append({
                'dataset': folder_name, 'row_type': 'edge', 'node_id': -1,
                't': -1, 'z': -1, 'y': -1, 'x': -1,
                'source_id': src, 'target_id': dst,
            })
        n_nodes += len(nodes) + len(interp_nodes)
        n_edges += len(edges)
        n_div += len(divisions)

        if (t + 1) % 50 == 0 or t == n_t - 1:
            print(f'  [{folder_name}] {t + 1}/{n_t} khung · {n_nodes} node · '
                  f'{n_edges} cạnh · {n_div} phân bào · {time.time() - t0:.0f}s', flush=True)

    # ---- ver 4: stitching hậu kiểm — nối lại track đứt + node nội suy ----
    n_st, n_in, n_ed = stitch_tracks(ds_rows, node_meta)
    if STITCH_ENABLED and n_st:
        print(f'  [stitch {folder_name}] nối lại {n_st} track · +{n_in} node nội suy · '
              f'+{n_ed} cạnh', flush=True)
    n_nodes += n_in
    n_edges += n_ed

    all_rows.extend(ds_rows)
    if DIAGNOSE:
        print(f'  [chẩn đoán {folder_name}] {diagnose(ds_rows)}', flush=True)
    summary.append((folder_name, n_nodes, n_edges, n_div))
    print(f'== {folder_name}: {n_nodes} nodes · {n_edges} edges · {n_div} phân bào '
          f'({time.time() - t0:.0f}s)', flush=True)
    if STOPPED_EARLY:
        break

if STOPPED_EARLY:
    print('CẢNH BÁO: dừng sớm do ngân sách thời gian — kết quả chỉ một phần!')

# ---------- 5) SOÁT BẰNG MẮT (tuỳ chọn) ----------
if RUN_PREVIEW and test_folder_names:
    import matplotlib.pyplot as plt

    zarr_path = os.path.join(DATA_DIR, test_folder_names[0] + '.zarr')
    shape, dtype, chunk = read_zarr_meta(zarr_path)
    vol = load_volume(zarr_path, 0, shape, dtype, chunk)
    dets = detect_nodes(vol)

    zc = shape[1] // 2
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax in axes:
        ax.imshow(vol[zc], cmap='gray')
        ax.set_xticks([])
        ax.set_yticks([])
    axes[0].set_title(f'{test_folder_names[0]} · t=0 · lát z={zc}')
    for d in dets:
        axes[1].plot(d['x'], d['y'], 'o', mfc='none', mec='lime', ms=9, mew=1.2)
    axes[1].set_title(f'phát hiện: {len(dets)} node (ver 4: P{PERCENTILE:g} + tách blob + stitch)')
    plt.tight_layout()
    plt.show()
