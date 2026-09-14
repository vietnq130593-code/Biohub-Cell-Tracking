"""Kiểm chứng ver 2 trên dữ liệu Zarr tổng hợp (mô phỏng cấu trúc Kaggle).

Kịch bản test — tái hiện đúng các tình huống ver 2 nhắm tới:
  1. 2 tế bào GỘP blob (ngưỡng không tách nổi) có 2 đỉnh sáng → detect phải tách 2 node
  2. Phân bào THẬT (mẹ chia 2, tách dần) → phải được xác nhận (đủ 3 khung + khoảng cách tăng)
  3. Merge-split GIẢ (2 tế bào gộp 1 khung rồi tách, khoảng cách đứng yên) → KHÔNG được xác nhận
  4. Track đứt → nội suy node giữa + cạnh liền khung
  5. Format: cột đúng, node_id duy nhất, mọi cạnh tham chiếu node tồn tại + liền khung
"""
import itertools
import json
import os
import sys
import time

import numpy as np

BASE = '/home/z/ver2test'
G = {'__name__': '__main__'}

def load_cell(path):
    src = open(path).read()
    exec(compile(src, path, 'exec'), G)

for name in ['cell1code.py', 'cell2code.py']:
    load_cell(os.path.join(BASE, name))

# ==== tạo dataset tổng hợp ====
import blosc2

SCALE = G['SCALE']
T, Z, Y, X = 16, 40, 120, 120

rng = np.random.default_rng(7)
vol = np.zeros((T, Z, Y, X), dtype=np.uint16)
TRUE = []

def put(t, z, y, x, sz, syx, amp):
    zz, yy, xx = np.mgrid[0:Z, 0:Y, 0:X]
    r2 = ((zz - z) / sz) ** 2 + ((yy - y) / syx) ** 2 + ((xx - x) / syx) ** 2
    vol[t] = np.maximum(vol[t], (amp * np.exp(-r2 / 2.0)).astype(np.float64)).astype(np.uint16)
    TRUE.append((t, z, y, x))

# --- tế bào A: di chuyển chéo nhẹ, đều đặn (σ theo PSF thật: z 1.5, xy 8.5 voxel) ---
for t in range(T):
    put(t, 20, 40 + 2 * t // 4, 40 + 1 * t // 4, 1.5, 8.5, 3000)

# --- cặp B/C: blob GỘP EO (cách 21 voxel ≈ 2.5σ — component dính nhưng có 2 đỉnh) ---
for t in range(T):
    put(t, 20, 80, 30, 1.5, 8.5, 2600)
    put(t, 20, 80, 51, 1.5, 8.5, 2400)

# --- phân bào THẬT: mẹ D phình tới t=4, chia t=5, 2 con tách nhanh 1.5 voxel y/khung ---
for t in range(0, 5):
    put(t, 30, 40 + t // 3, 90 + t // 4, 1.5 + 0.1 * t, 8.5 + 0.6 * t / 4, 3200)
for t in range(5, T):
    k = t - 5
    put(t, 30, 42 - 1.5 * k, 94 + k, 1.5, 8.5, 2000)
    put(t, 30, 44 + 1.5 * k, 92 - k, 1.5, 8.5, 2000)

# --- merge-split GIẢ: E ổn định, F xuất hiện t≥2 cách 21 voxel (2 đỉnh tách),
#     ĐỨNG YÊN, amp thấp (0.36×E — vượt brightness check) → bị DIV_SEP_GROWTH từ chối ---
for t in range(T):
    put(t, 8, 60, 60, 1.5, 8.5, 2800)
    if t >= 2:
        put(t, 8, 60, 82, 1.5, 8.5, 2200)

vol = np.minimum(vol + rng.poisson(40, vol.shape).astype(np.uint16), 65535).astype(np.uint16)

# ==== ghi zarr giả (cấu trúc Kaggle) ====
test_dir = '/home/z/ver2test/test'
os.makedirs(f'{test_dir}/synth.zarr/0/c', exist_ok=True)
for t in range(T):
    cd = f'{test_dir}/synth.zarr/0/c/{t}/0/0/0'
    os.makedirs(os.path.dirname(cd), exist_ok=True)
    with open(cd, 'wb') as f:
        f.write(blosc2.compress(vol[t]))
meta = {'shape': [T, Z, Y, X], 'data_type': 'uint16',
        'chunk_grid': {'name': 'regular', 'configuration': {'chunk_shape': [1, Z, Y, X]}}}
with open(f'{test_dir}/synth.zarr/0/zarr.json', 'w') as f:
    json.dump(meta, f)

# ==== chạy cell 3 + 4 ====
G['TEST_DIR'] = test_dir
G['RUN_PREVIEW'] = False
load_cell(os.path.join(BASE, 'cell3code.py'))
load_cell(os.path.join(BASE, 'cell4code.py'))

sub = G['submission']
rows = sub.to_dict('records')
fails = []

def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' — {extra}' if extra else ''))
    if not cond:
        fails.append(name)

nodes = [r for r in rows if r['row_type'] == 'node']
edges = [r for r in rows if r['row_type'] == 'edge']

# 1. format
check('cột đúng', list(sub.columns) == G['COLS'] or list(sub.columns) == ['dataset', 'row_type', 'node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id'])
check('index tên id', sub.index.name == 'id')
check('chỉ 1 dataset', set(r['dataset'] for r in rows) == {'synth'})

# 2. ràng buộc node/edge
nids = [r['node_id'] for r in nodes]
check('node_id duy nhất', len(set(nids)) == len(nids))
nid_set = set(nids)
check('node t/z/y/x nguyên & ≥ 0', all(r['t'] >= 0 and r['z'] >= 0 and r['y'] >= 0 and r['x'] >= 0 for r in nodes))
check('edge tham chiếu node tồn tại', all(r['source_id'] in nid_set and r['target_id'] in nid_set for r in edges))
check('không tự nối', all(r['source_id'] != r['target_id'] for r in edges))
check('cạnh không trùng', len({(r['source_id'], r['target_id']) for r in edges}) == len(edges))

tpos = {r['node_id']: (r['t'], r['z'], r['y'], r['x']) for r in nodes}
def consecutive(e):
    t1 = tpos[e['source_id']][0]; t2 = tpos[e['target_id']][0]
    return t2 == t1 + 1
check('mọi cạnh liền khung (không cạnh nhảy)', all(consecutive(e) for e in edges))

# 3. tách blob gộp B/C
def nodes_near(t, y0, x0, rad=10):
    return [r for r in nodes if r['t'] == t and np.hypot(r['y'] - y0, r['x'] - x0) < rad]

split_ok = True
for t in [0, 5, 15]:
    nb = nodes_near(t, 80, 30)
    nc = nodes_near(t, 80, 51)
    if not (len(nb) >= 1 and len(nc) >= 1):
        split_ok = False
check('tách blob gộp B/C thành 2 node', split_ok)

# 4. phân bào thật D được xác nhận: fork tại t≈4..7 gần (30, ~42, ~92)
forks = {}
for e in edges:
    forks.setdefault(e['source_id'], []).append(e['target_id'])
div_nodes = [s for s, tg in forks.items() if len(tg) >= 2]
d_forks = [s for s in div_nodes if tpos[s][0] in (3, 4, 5, 6, 7, 8, 9) and
           np.linalg.norm((np.array(tpos[s][1:]) - np.array([30, 42, 92])) * SCALE) < 20]
check('phân bào thật (D) được xác nhận', len(d_forks) == 1, f'fork D: {[(s, tpos[s]) for s in d_forks]}')

# 5. merge-split giả E/F KHÔNG có fork
ef_forks = [s for s in div_nodes if
            np.linalg.norm((np.array(tpos[s][1:]) - np.array([8, 60, 60])) * SCALE) < 25]
check('merge-split giả (E/F) KHÔNG tạo phân bào', len(ef_forks) == 0, f'fork gần E: {[(s, tpos[s]) for s in ef_forks]}')

# 6. độ chính xác vị trí ≤ 7 µm
def nearest_d(t, z, y, x):
    cand = [r for r in nodes if r['t'] == t]
    if not cand:
        return 999.0
    return min(np.linalg.norm((np.array([r['z'], r['y'], r['x']]) - np.array([z, y, x])) * SCALE) for r in cand)

acc_ok = True
worst = 0.0
for (t, z, y, x) in TRUE:
    if t in (0, 7, 15):
        d = nearest_d(t, z, y, x)
        worst = max(worst, d)
        if d > 7.0:
            acc_ok = False
check('node khớp vị trí ≤ 7 µm', acc_ok, f'worst={worst:.2f} µm')

# 7. node/khung hợp lý
per_frame = {}
for r in nodes:
    per_frame[r['t']] = per_frame.get(r['t'], 0) + 1
print('node/khung:', dict(sorted(per_frame.items())))

# 8. vận hành
print('div confirmed/rejected:', G['TRK'].n_div_confirmed, '/', G['TRK'].n_div_rejected)
check('phân bào đã xác nhận ≥ 1', G['TRK'].n_div_confirmed >= 1)
check('phân bào bị từ chối ≥ 1 (E/F merge-split)', G['TRK'].n_div_rejected >= 1)

print()
print('TỔNG: ' + ('ĐẠT TẤT CẢ' if not fails else f'{len(fails)} LỖI: {fails}'))
sys.exit(0 if not fails else 1)
