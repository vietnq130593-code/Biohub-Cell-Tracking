# %% [markdown]
# # Biohub — Cell Tracking · Baseline cải tiến (Stage 0 + 2)
#
# Nâng cấp notebook *getting-started nearest-neighbor* — giữ nguyên khung đọc Zarr và
# format `submission.csv`. Bốn đòn tăng điểm, xếp theo tỷ lệ (điểm thu được / công sức):
#
# | # | Cải tiến | Tác động lên metric |
# |---|---|---|
# | 1 | Centroid **center-of-mass theo cường độ** + downsample bất đối xứng (z×2, xy×4) | node khớp ≤ 7 µm nhiều hơn → nhiều cạnh TP |
# | 2 | **Motion model** — matching theo vị trí dự đoán (vận tốc EMA), gate thích ứng theo bước đi trung vị | bớt cạnh FP/FN |
# | 3 | **Phát hiện phân bào** — cạnh thứ 2, gate cha/con + bảo toàn độ sáng | `division_jaccard` (+0.1 điểm thưởng) |
# | 4 | **Frame-skip** — nối lại track khi mất 1 khung, *không* phát cạnh nhảy (cạnh t→t+2 luôn là FP theo metric) | tránh đứt track gây FN dây chuyền |
#
# **Cách dùng trên Kaggle**
#
# 1. **File → Import Notebook** → chọn file này, rồi **Add Input** → gắn competition
#    `biohub-cell-tracking-during-development`
# 2. Bật `RUN_PREVIEW = True` (mặc định) để soát 1 khung bằng mắt trước khi chạy hết
# 3. **Save Version → Save & Run All (Commit)** → từ run đã xong, bấm **Submit**

# %%
import itertools
import json
import os

import blosc2
import numpy as np
import pandas as pd
from scipy.ndimage import center_of_mass, label, uniform_filter
from scipy.optimize import linear_sum_assignment

# %% [markdown]
# ## 0 · Siêu tham số — mọi núm tinh chỉnh nằm ở đây
#
# Thứ tự đáng quét trước (rẻ nhất trước):
#
# - `PERCENTILE`: 88 → 96 (bước 2). Quá thấp = node giả; quá cao = sót tế bào mờ
# - `GATE_MEDIAN_MULT`: 2.0 → 3.5 (gate linking quá chặt thì FN cạnh tăng)
# - `DIV_SIBLING_GATE_UM`: 6 → 15 — hai con sinh ra sát nhau hay bị ngưỡng gộp
#   thành 1 component vài khung, nên phân bào thường chỉ phát hiện được sau khi
#   chúng tách ra; nếu miss phân bào thì nới gate này
# - `MIN_NVOXELS`: 2 → 8 nếu scorer cho thấy nhiều node giả li ti

# %%
TEST_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/test'
SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)   # Z, Y, X — µm/voxel

# --- Tầng 1 · Detection ---
DS_Z, DS_Y, DS_X = 2, 4, 4         # downsample bất đối xứng: z giữ kỹ hơn (1.625 µm/voxel)
SMOOTH_SIZE = 3                     # uniform_filter, tính trong không gian downsample
PERCENTILE = 92.0                   # ngưỡng sáng — QUÉT 88/90/92/94/96
MIN_NVOXELS = 4                     # bỏ component li ti (nhiễu)
MAX_NVOXELS = 1000                  # bỏ blob khổng lồ (merge/nền)

# --- Tầng 2 · Linking ---
BASE_GATE_UM = 8.0                  # gate khi chưa đủ thống kê bước đi
GATE_MEDIAN_MULT = 2.5              # gate = mult × trung vị bước đi gần nhất
GATE_MIN_UM, GATE_MAX_UM = 5.0, 12.0
VEL_SMOOTH = 0.5                    # vận tốc EMA: v ← 0.5·mới + 0.5·cũ
BIG = 1e9

# --- Frame-skip (nối lại track, KHÔNG phát cạnh nhảy) ---
ALLOW_FRAME_SKIP = True
SKIP_GATE_UM = 10.0
MAX_SKIP_FRAMES = 1

# --- Tầng 3 · Phân bào ---
DIVISION_ENABLED = True
DIV_PARENT_GATE_UM = 10.0           # mẹ → con thứ hai
DIV_SIBLING_GATE_UM = 12.0          # hai con phải gần nhau — hai con mới sinh hay bị
                                     # ngưỡng gộp thành 1 component tới khi cách ~8-10 µm,
                                     # nên gate này cần rộng hơn gate linking
DIV_BRIGHTNESS_CHECK = True         # bảo toàn độ sáng: I(con1) + I(con2) ≈ I(mẹ)
DIV_BRIGHTNESS_RATIO = (0.55, 1.8)

NODE_ID = itertools.count(1)        # node_id duy nhất toàn cục (an toàn với mọi cách scorer join)

# %% [markdown]
# ## 1 · Tầng Detection
#
# Giữ nguyên cách ngưỡng percentile của baseline, nhưng:
#
# - downsample **z×2, xy×4** (baseline ×4 cả 3 trục) — mỗi bước z xê xích 1 voxel
#   là đã 1.6 µm, giữ z kỹ giúp tâm chính xác hơn nhiều
# - centroid = **center-of-mass theo cường độ sáng** thay vì trung bình hình học —
#   tế bào sáng không đều, tâm theo độ sáng gần tâm sinh học hơn
# - lọc component theo kích thước (bỏ nhiễu li ti và blob khổng lồ)

# %%
def load_volume(zarr_path, t, shape, dtype):
    """Đọc 1 khung (Z, Y, X) từ chunk Zarr như notebook gốc."""
    chunk_path = os.path.join(zarr_path, '0', 'c', str(t), '0', '0', '0')
    with open(chunk_path, 'rb') as f:
        raw = blosc2.decompress(f.read())
    return np.frombuffer(raw, dtype=dtype).reshape(shape[1:])


def detect_nodes(vol):
    """Phát hiện tế bào trong 1 khung (Z, Y, X).

    Trả về list dict: z, y, x (voxel gốc), mass (tổng cường độ), nvox.
    """
    ds = vol[::DS_Z, ::DS_Y, ::DS_X].astype(np.float32)
    if ds.size == 0:
        return []
    smoothed = uniform_filter(ds, size=SMOOTH_SIZE)
    thr = np.percentile(smoothed, PERCENTILE)
    labeled, n = label(smoothed > thr)
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
            'z': int(round(cz * DS_Z)),
            'y': int(round(cy * DS_Y)),
            'x': int(round(cx * DS_X)),
            'mass': float(wsums[i]),
            'nvox': nv,
        })
    return nodes

# %% [markdown]
# ## 2 · Tầng Tracker — motion model + phân bào + frame-skip
#
# Mỗi khung `t` xử lý theo 4 bước:
#
# 1. **Matching chính** — Hungarian giữa node khung trước (đặt tại *vị trí dự đoán*
#    = vị trí + vận tốc EMA) và node khung hiện tại, trong gate thích ứng
#    `2.5 × trung vị bước đi` (kẹp trong 5–12 µm)
# 2. **Phân bào** — với mỗi cặp (mẹ → con1) vừa match, tìm con thứ 2 trong các node
#    chưa match: gần mẹ ≤ `DIV_PARENT_GATE_UM`, gần anh em ≤ `DIV_SIBLING_GATE_UM`,
#    và **bảo toàn độ sáng**: khối sáng 2 con ≈ khối sáng mẹ
# 3. **Frame-skip** — node khung trước bị mất (không match) được thử lại với node
#    chưa match của khung này. Track được nối tiếp nhưng **KHÔNG phát cạnh**:
#    GT của cuộc thi chỉ có cạnh giữa 2 khung liên tiếp, nên cạnh nhảy t→t+2
#    chắc chắn là FP
# 4. **Dọn dẹp** — node chưa ai nhận thành track mới, node mất chuyển vào
#    pending và hết hạn sau `MAX_SKIP_FRAMES`

# %%
class Tracker:
    """Nearest-neighbor tracking kèm motion model, phân bào và frame-skip."""

    def __init__(self):
        self.active = {}        # nid → dict(pos µm, vel µm/khung, mass)
        self.pending = {}       # nid → dict(pos, vel, mass, missed)
        self.recent_steps = []  # bước đi thô (µm) của các match gần đây

    def _gate(self):
        if len(self.recent_steps) < 5:
            return BASE_GATE_UM
        med = float(np.median(self.recent_steps))
        return float(np.clip(GATE_MEDIAN_MULT * med, GATE_MIN_UM, GATE_MAX_UM))

    def step(self, dets):
        """Xử lý 1 khung. Trả về (nodes, edges, divisions).

        nodes     : list (nid, det) — node_id vừa cấp
        edges     : list (src_nid, dst_nid) — cạnh t-1 → t (gồm cả phân bào)
        divisions : list (src_nid, dst_nid) — tập con của edges
        """
        nodes = [(next(NODE_ID), d) for d in dets]
        ids = [nid for nid, _ in nodes]
        pos = np.array(
            [[d['z'], d['y'], d['x']] for _, d in nodes], dtype=np.float64,
        ).reshape(-1, 3) * SCALE
        mass = [float(d['mass']) for _, d in nodes]

        edges, divisions = [], []
        matched_curr = {}  # curr_idx → prev nid

        # ---- (a) matching chính: Hungarian trên vị trí DỰ ĐOÁN ----
        prev_ids = list(self.active.keys())
        if prev_ids and ids:
            pred = np.array(
                [self.active[p]['pos'] + self.active[p]['vel'] for p in prev_ids],
            )
            D = np.linalg.norm(pred[:, None, :] - pos[None, :, :], axis=2)
            gate = self._gate()
            cost = np.where(D <= gate, D, BIG)
            ri, ci = linear_sum_assignment(cost)
            for r, c in zip(ri, ci):
                if D[r, c] > gate:
                    continue
                p = prev_ids[r]
                matched_curr[c] = p
                edges.append((p, ids[c]))
                step_um = float(np.linalg.norm(pos[c] - self.active[p]['pos']))
                self.recent_steps.append(step_um)
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
                    dS = float(np.linalg.norm(C1 - B2))
                    if dP > DIV_PARENT_GATE_UM or dS > DIV_SIBLING_GATE_UM:
                        continue
                    if DIV_BRIGHTNESS_CHECK and mP > 0:
                        ratio = (mC1 + mB2) / mP
                        if not (DIV_BRIGHTNESS_RATIO[0] <= ratio <= DIV_BRIGHTNESS_RATIO[1]):
                            continue
                    cands.append((dP, p, j))
            cands.sort()
            used_p, used_j = set(), set()
            for dP, p, j in cands:
                if p in used_p or j in used_j or j in matched_curr:
                    continue
                used_p.add(p)
                used_j.add(j)
                P = self.active[p]['pos']
                new_active[ids[j]] = {'pos': pos[j], 'vel': pos[j] - P, 'mass': mass[j]}
                edges.append((p, ids[j]))
                divisions.append((p, ids[j]))
            unmatched = [j for j in unmatched if j not in used_j]

        # ---- (c) frame-skip: nối lại track (KHÔNG phát cạnh — xem giải thích trên) ----
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
                gap = self.pending[q]['missed'] + 1
                new_active[ids[j]] = {
                    'pos': pos[j],
                    'vel': (pos[j] - self.pending[q]['pos']) / gap,
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
            self.pending[p] = {'pos': a['pos'], 'vel': a['vel'], 'mass': a['mass'], 'missed': 1}

        for j in unmatched:
            if ids[j] not in new_active:
                new_active[ids[j]] = {'pos': pos[j], 'vel': np.zeros(3), 'mass': mass[j]}

        self.active = new_active
        return nodes, edges, divisions

# %% [markdown]
# ## 3 · Chạy toàn bộ test set
#
# Vòng lặp giống hệt notebook gốc (đọc từng chunk theo t), thay thuật toán
# theo tầng ở trên. Node_id cấp duy nhất toàn cục.

# %%
test_folder_names = sorted(
    d.replace('.zarr', '') for d in os.listdir(TEST_DIR) if d.endswith('.zarr')
)

all_rows = []
summary = []

for folder_name in test_folder_names:
    zarr_path = os.path.join(TEST_DIR, folder_name + '.zarr')
    with open(os.path.join(zarr_path, '0', 'zarr.json')) as f:
        arr_meta = json.load(f)
    shape = tuple(arr_meta['shape'])   # (T, Z, Y, X)
    dtype = np.dtype(arr_meta['data_type'])
    n_t = shape[0]

    trk = Tracker()
    n_nodes = n_edges = n_div = 0

    for t in range(n_t):
        vol = load_volume(zarr_path, t, shape, dtype)
        dets = detect_nodes(vol)
        nodes, edges, divisions = trk.step(dets)

        for nid, d in nodes:
            all_rows.append({
                'dataset': folder_name,
                'row_type': 'node',
                'node_id': nid,
                't': t,
                'z': d['z'], 'y': d['y'], 'x': d['x'],
                'source_id': -1,
                'target_id': -1,
            })
        for src, dst in edges:
            all_rows.append({
                'dataset': folder_name,
                'row_type': 'edge',
                'node_id': -1,
                't': -1,
                'z': -1, 'y': -1, 'x': -1,
                'source_id': src,
                'target_id': dst,
            })
        n_nodes += len(nodes)
        n_edges += len(edges)
        n_div += len(divisions)

    summary.append((folder_name, n_nodes, n_edges, n_div))
    print(f'{folder_name}: {n_nodes} nodes · {n_edges} edges · {n_div} phân bào')

# %% [markdown]
# ## 4 · Soát bằng mắt (tuỳ chọn)
#
# Vẽ 1 khung của phôi đầu tiên + vòng phát hiện. Sau khi tin tưởng kết quả,
# đặt `RUN_PREVIEW = False` rồi Save Version để chạy nhanh hơn chút.

# %%
RUN_PREVIEW = True

if RUN_PREVIEW and test_folder_names:
    import matplotlib.pyplot as plt

    zarr_path = os.path.join(TEST_DIR, test_folder_names[0] + '.zarr')
    with open(os.path.join(zarr_path, '0', 'zarr.json')) as f:
        meta = json.load(f)
    shape, dtype = tuple(meta['shape']), np.dtype(meta['data_type'])
    vol = load_volume(zarr_path, 0, shape, dtype)
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

# %% [markdown]
# ## 5 · Xuất submission
#
# Format giống hệt notebook gốc: node row và edge row, index tên `id`.

# %%
COLS = ['dataset', 'row_type', 'node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id']
submission = pd.DataFrame(all_rows, columns=COLS)
submission.index.name = 'id'
submission.to_csv('submission.csv')

n_nodes = int((submission['row_type'] == 'node').sum())
n_edges = int((submission['row_type'] == 'edge').sum())
n_div = sum(s[3] for s in summary)
print(f'Done. {len(submission)} rows ({n_nodes} node · {n_edges} edge · {n_div} phân bào) → submission.csv')

# %% [markdown]
# ## Bước tiếp theo (ngoài phạm vi notebook này)
#
# 1. **Chạy submit thật** để lấy điểm sàn trên leaderboard — so với baseline
#    nearest-neighbor gốc để đo Gain
# 2. **Local scorer**: cài metric cuộc thi (match 7 µm, edge/division jaccard)
#    chạy trên GT thưa của train để tuning offline, không đốt quota submit
# 3. **Stage 1 — detection tốt hơn**: ngưỡng cục bộ theo z-slab, watershed tách
#    tế bào dính nhau (hiện 2 con sát nhau bị gộp 1 component), DoG blob
# 4. **Stage 3 — U-Net centroid heatmap** (đòn lớn nhất, cần GPU + weights
#    gắn kèm dạng Kaggle Dataset)
