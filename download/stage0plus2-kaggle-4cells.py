# Biohub — Cell Tracking · Stage 0+2 (bản 4 cells khớp notebook Kaggle gốc)
#
# Rà soát & nâng cấp so với bản 15-cell trước (commit 6075af3):
#   1) Đọc dữ liệu: lắp ghép ĐỦ chunk có mặt (chunk 0/0/0 vẫn là đường nhanh)
#   2) Detection: label() dùng liên kết 26-ô (chống tách nhân giữa các lát z)
#   3) Tracking: tâm float nội bộ (chỉ round khi xuất — bớt nhiễu lượng tử hóa)
#   4) Frame-skip: NỘI SUY node giữa + 2 cạnh liền khung (thay vì bỏ trống) —
#      metric chỉ tính cạnh TP khi 2 đầu khớp GT ≤ 7 µm và GT nối TRỰC TIẾP
#      bằng cạnh, nên cạnh nhảy t→t+2 luôn FP; node nội suy nằm giữa 2 node
#      đã khớp nên tỉ lệ khớp GT cao → +2 TP thay vì 0
#   5) Phân bào: chặn con thứ 2 quá mờ (DIV_MIN_CHILD_FRAC) chống node giả
#   6) Vận hành: tiến trình mỗi 50 khung + TIME_LIMIT_HOURS dừng sớm ghi submission
#
# Cách dùng: dán 4 cell dưới vào notebook Kaggle (thay cell tương ứng),
# Add Input competition → Save Version → Save & Run All → Submit.

# %% CELL 1 — IMPORTS
# ============================================================
import itertools
import json
import os
import time

import blosc2
import numpy as np
import pandas as pd
from scipy.ndimage import center_of_mass, label, uniform_filter
from scipy.optimize import linear_sum_assignment

# %% CELL 2 — SIÊU THAM SỐ (mọi núm tune nằm ở đây)
# ============================================================
TEST_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/test'

# Thang vật lý (Z, Y, X) — µm/voxel, theo đề bài
SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)

# --- Tầng 1 · DETECTION ---
DS_Z, DS_Y, DS_X = 2, 4, 4       # downsample bất đối xứng: z giữ kỹ hơn
SMOOTH_SIZE = 3                   # uniform_filter, trong không gian downsample
PERCENTILE = 92.0                 # ngưỡng sáng — QUÉT 88/90/92/94/96
MIN_NVOXELS = 4                   # bỏ component li ti (nhiễu)
MAX_NVOXELS = 1000                # bỏ blob khổng lồ (merge/nền)
CONN26 = True                     # liên kết 26-ô: chống tách nhân giữa các lát z

# --- Tầng 2 · LINKING (motion model + gate thích ứng) ---
BASE_GATE_UM = 8.0                # gate khi chưa đủ thống kê bước đi
GATE_MEDIAN_MULT = 2.5            # gate = mult × trung vị bước đi gần nhất
GATE_MIN_UM, GATE_MAX_UM = 5.0, 12.0
VEL_SMOOTH = 0.5                  # vận tốc EMA: v ← 0.5·mới + 0.5·cũ
BRIGHT_WEIGHT = 0.0               # phạt chênh độ sáng trong cost (0 = tắt; thử 0.05–0.15)

# --- Frame-skip + nội suy ---
ALLOW_FRAME_SKIP = True           # nối lại track khi mất 1 khung
SKIP_GATE_UM = 10.0
MAX_SKIP_FRAMES = 1
INTERPOLATE_MISSED_FRAMES = True  # chèn node nội suy + 2 cạnh liền khung tại khung mất
TIME_LIMIT_HOURS = 11.0           # dừng sớm ghi nốt submission (giới hạn Kaggle 12h)

# --- Tầng 3 · PHÂN BÀO ---
DIVISION_ENABLED = True
DIV_PARENT_GATE_UM = 10.0         # mẹ → con thứ hai
DIV_SIBLING_GATE_UM = 12.0        # 2 con mới sinh hay bị ngưỡng gộp tới ~8–10 µm
DIV_MIN_CHILD_FRAC = 0.15         # con thứ 2 phải ≥ 15% độ sáng mẹ (chặn nhiễu li ti)
DIV_BRIGHTNESS_CHECK = True       # bảo toàn độ sáng: I(con1)+I(con2) ≈ I(mẹ)
DIV_BRIGHTNESS_RATIO = (0.55, 1.8)

# --- Soát bằng mắt (vẽ 1 khung đầu tiên) ---
RUN_PREVIEW = True

NODE_ID = itertools.count(1)      # node_id duy nhất toàn cục
BIG = 1e9

# %% CELL 3 — PIPELINE: ĐỌC ZARR → DETECTION → TRACKING → PHÂN BÀO
# ============================================================
T_START = time.time()


def _over_time_budget():
    return (time.time() - T_START) > TIME_LIMIT_HOURS * 3600.0


# ---------- 1) ĐỌC DỮ LIỆU ----------
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


# ---------- 2) DETECTION ----------
def detect_nodes(vol):
    """Trả về list dict: z, y, x (voxel gốc, int — đúng format đề bài) và
    zf, yf, xf (float — cho tracking), mass (tổng cường độ), nvox."""
    ds = vol[::DS_Z, ::DS_Y, ::DS_X].astype(np.float32)
    if ds.size == 0:
        return []
    smoothed = uniform_filter(ds, size=SMOOTH_SIZE)
    thr = np.percentile(smoothed, PERCENTILE)
    labeled, n = label(smoothed > thr, structure=np.ones((3, 3, 3), dtype=bool) if CONN26 else None)
    if n == 0:
        return []

    lab_flat = labeled.ravel()
    counts = np.bincount(lab_flat, minlength=n + 1)
    wsums = np.bincount(lab_flat, weights=smoothed.ravel(), minlength=n + 1).astype(np.float64)
    coms = center_of_mass(smoothed, labeled, index=range(1, n + 1))

    nodes = []
    for i in range(1, n + 1):
        nv = int(counts[i])
        if nv < MIN_NVOXELS or nv > MAX_NVOXELS:
            continue
        cz, cy, cx = coms[i - 1]
        nodes.append({
            'z': int(round(cz * DS_Z)), 'y': int(round(cy * DS_Y)), 'x': int(round(cx * DS_X)),
            'zf': cz * DS_Z, 'yf': cy * DS_Y, 'xf': cx * DS_X,
            'mass': float(wsums[i]), 'nvox': nv,
        })
    return nodes


# ---------- 3) TRACKER ----------
class Tracker:
    """Nearest-neighbor tracking kèm motion model, phân bào, frame-skip.

    Mỗi khung gồm 4 bước:
      (a) Hungarian giữa node khung trước (đặt tại vị trí DỰ ĐOÁN
          = vị trí + vận tốc EMA) và node khung hiện tại, gate thích ứng
      (b) phân bào: mẹ vừa match nhận thêm con thứ 2 (2 gate + bảo toàn độ sáng)
      (c) frame-skip: track mất 1 khung được nối lại — nếu bật nội suy thì
          chèn node giữa + 2 cạnh liền khung thay vì bỏ trống
      (d) dọn dẹp: node chưa ai nhận thành track mới, track mất vào pending,
          hết hạn sau MAX_SKIP_FRAMES
    """

    def __init__(self):
        self.active = {}        # nid → dict(pos µm, vel µm/khung, mass)
        self.pending = {}       # nid → dict(pos, vel, mass, missed)
        self.recent_steps = []  # bước đi (µm) của các match gần đây

    def _gate(self):
        if len(self.recent_steps) < 5:
            return BASE_GATE_UM
        med = float(np.median(self.recent_steps))
        return float(np.clip(GATE_MEDIAN_MULT * med, GATE_MIN_UM, GATE_MAX_UM))

    def step(self, dets, t):
        """Xử lý khung t. Trả về (nodes, edges, divisions, interp_nodes).

        nodes        : list (nid, det) — node thực của khung t
        edges        : list (src_nid, dst_nid) — cạnh t-1 → t (gồm phân bào)
        divisions    : list (src_nid, dst_nid) — tập con của edges
        interp_nodes : list (nid, t_giữa, det) — node nội suy tại khung mất
        """
        nodes = [(next(NODE_ID), d) for d in dets]
        ids = [nid for nid, _ in nodes]
        pos = np.array(
            [[d['zf'], d['yf'], d['xf']] for _, d in nodes], dtype=np.float64,
        ).reshape(-1, 3) * SCALE
        mass = [float(d['mass']) for _, d in nodes]

        edges, divisions, interp_nodes = [], [], []
        matched_curr = {}  # curr_idx → prev nid

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
            new_active[ids[c]] = {'pos': pos[c], 'vel': vel, 'mass': mass[c]}

        # ---- (b) phân bào: mẹ đã match nhận thêm con thứ 2 ----
        unmatched = [j for j in range(len(ids)) if j not in matched_curr]
        if DIVISION_ENABLED and matched_curr:
            cands = []
            for c, p in matched_curr.items():
                P, mP = self.active[p]['pos'], self.active[p]['mass']
                C1, mC1 = pos[c], mass[c]
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
                    cands.append((dP, p, j))
            cands.sort()
            used_p, used_j = set(), set()
            for dP, p, j in cands:
                if p in used_p or j in used_j:
                    continue
                used_p.add(p)
                used_j.add(j)
                P = self.active[p]['pos']
                new_active[ids[j]] = {'pos': pos[j], 'vel': pos[j] - P, 'mass': mass[j]}
                edges.append((p, ids[j]))
                divisions.append((p, ids[j]))
            unmatched = [j for j in unmatched if j not in used_j]

        # ---- (c) frame-skip: nối lại track mất 1 khung ----
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
                    # Chèn node nội suy tại các khung bị mất rồi nối 2 cạnh
                    # LIỀN KHUNG — node nằm giữa 2 node đã khớp nên khả năng
                    # khớp GT ≤ 7 µm cao (cạnh nhảy t→t+2 thì chắc chắn FP).
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
                }
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
                               'mass': a['mass'], 'missed': 1}

        for j in unmatched:
            if ids[j] not in new_active:
                new_active[ids[j]] = {'pos': pos[j], 'vel': np.zeros(3), 'mass': mass[j]}

        self.active = new_active
        return nodes, edges, divisions, interp_nodes


# ---------- 4) CHẠY TOÀN BỘ TEST SET ----------
if not os.path.isdir(TEST_DIR):
    hint = os.listdir('/kaggle/input') if os.path.isdir('/kaggle/input') else 'không có /kaggle/input'
    raise FileNotFoundError(f'Không thấy {TEST_DIR} — hãy Add Input competition. /kaggle/input: {hint}')

test_folder_names = sorted(
    d.replace('.zarr', '') for d in os.listdir(TEST_DIR) if d.endswith('.zarr')
)
if not test_folder_names:
    raise RuntimeError(f'Không tìm thấy thư mục .zarr nào trong {TEST_DIR}: {os.listdir(TEST_DIR)[:10]}')
print(f'{len(test_folder_names)} dataset: {test_folder_names}')

all_rows = []
summary = []
STOPPED_EARLY = False

for folder_name in test_folder_names:
    zarr_path = os.path.join(TEST_DIR, folder_name + '.zarr')
    shape, dtype, chunk = read_zarr_meta(zarr_path)
    n_t = shape[0]

    trk = Tracker()
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
        nodes, edges, divisions, interp_nodes = trk.step(dets, t)

        for nid, d in nodes:
            all_rows.append({
                'dataset': folder_name, 'row_type': 'node', 'node_id': nid,
                't': t, 'z': d['z'], 'y': d['y'], 'x': d['x'],
                'source_id': -1, 'target_id': -1,
            })
        for nid, tk, d in interp_nodes:
            all_rows.append({
                'dataset': folder_name, 'row_type': 'node', 'node_id': nid,
                't': tk, 'z': d['z'], 'y': d['y'], 'x': d['x'],
                'source_id': -1, 'target_id': -1,
            })
        for src, dst in edges:
            all_rows.append({
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

    zarr_path = os.path.join(TEST_DIR, test_folder_names[0] + '.zarr')
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
    axes[1].set_title(f'phát hiện: {len(dets)} node')
    plt.tight_layout()
    plt.show()

# %% CELL 4 — XUẤT SUBMISSION
# ============================================================
COLS = ['dataset', 'row_type', 'node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id']
submission = pd.DataFrame(all_rows, columns=COLS)
submission.index.name = 'id'
submission.to_csv('submission.csv')

n_nodes = int((submission['row_type'] == 'node').sum())
n_edges = int((submission['row_type'] == 'edge').sum())
n_div = sum(s[3] for s in summary)
print(f'Đã ghi submission.csv: {len(submission)} hàng '
      f'({n_nodes} node · {n_edges} cạnh · {n_div} phân bào)')
print(submission['row_type'].value_counts().to_string())
print(submission.head(8).to_string())
