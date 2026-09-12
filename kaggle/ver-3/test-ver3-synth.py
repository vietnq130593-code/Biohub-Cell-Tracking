"""Kiểm chứng ver 3 trên dữ liệu Zarr tổng hợp (mô phỏng cấu trúc Kaggle).

Kịch bản test — tái hiện đúng các tình huống tri thức mới từ discussion #740573:
  1. Phân bào THẬT với MẸ SÁNG DẦN trước khi chia (amp 3200→4200, rise ~1,3×)
     → phải được xác nhận (rise ≤ 1,7 — không bị cửa "ổn định khối lượng" chặn)
  2. Phân bào THẬT với cặp CHỊ EM XA 13,4 µm ngay từ khung sinh (p99 thật 13,9)
     → ver 3 (gate 14,5) phải bắt; ver 2 (gate 12 + parent 10) BỎ SÓT
  3. Merge-split GIÁO KHÉO: 2 tế bào gộp sâu thành blob ~2× khối lượng 4 khung
     rồi tách ra và đi xa DẦN (vượt được xác nhận động học của ver 2!)
     → ver 3 phải chặn bằng "ổn định khối lượng mẹ" (rise ≈ 2 > 1,7)
     → ver 2 XÁC NHẬN NHẦM (FP) — chạy đối chứng để minh hoạ
  4. Regression ver 2: blob gộp có eo tách 2 node; merge-split đứng yên bị
     xác nhận động học từ chối; tế bào mờ 2 khung → nội suy node giữa
  5. Format: cột đúng, node_id duy nhất, cạnh liền khung, độ chính xác ≤ 7 µm
"""
import itertools
import json
import os
import sys
import time

import numpy as np

BASE3 = '/home/z/my-project/kaggle/ver-3'
BASE2 = '/home/z/my-project/kaggle/ver-2'
ROOT = '/home/z/ver3test'


def load_cells(ns, base, names):
    for name in names:
        path = os.path.join(base, name)
        src = open(path).read()
        exec(compile(src, path, 'exec'), ns)


G3 = {'__name__': '__main__'}
load_cells(G3, BASE3, ['cell1code.py', 'cell2code.py'])
G2 = {'__name__': '__main__'}
load_cells(G2, BASE2, ['cell1code.py', 'cell2code.py'])

# ==== tạo dataset tổng hợp ====
import blosc2

SCALE = G3['SCALE']
T, Z, Y, X = 18, 40, 120, 120

rng = np.random.default_rng(7)
vol = np.zeros((T, Z, Y, X), dtype=np.float64)
TRUE = []

def put(t, z, y, x, sz, syx, amp):
    """Cộng dồn Gaussian (SUM — đúng vật lý huỳnh quang: 2 tế bào chồng nhau
    thì độ sáng CỘNG, không phải max — blob gộp có khối lượng ~2×)."""
    z0, z1 = max(0, int(z - 5 * sz)), min(Z, int(z + 5 * sz) + 1)
    y0, y1 = max(0, int(y - 5 * syx)), min(Y, int(y + 5 * syx) + 1)
    x0, x1 = max(0, int(x - 5 * syx)), min(X, int(x + 5 * syx) + 1)
    zz, yy, xx = np.mgrid[z0:z1, y0:y1, x0:x1]
    r2 = ((zz - z) / sz) ** 2 + ((yy - y) / syx) ** 2 + ((xx - x) / syx) ** 2
    vol[t, z0:z1, y0:y1, x0:x1] += amp * np.exp(-r2 / 2.0)
    TRUE.append((t, z, y, x))

# --- A: di chuyển chéo nhẹ (tham chiếu độ chính xác) ---
for t in range(T):
    put(t, 20, 40 + 2 * (t // 4), 40 + 1 * (t // 4), 1.5, 8.5, 3000)

# --- B/C: blob GỘP CÓ EO (24 voxel ≈ 2.8σ — 1 component, 2 đỉnh) ---
for t in range(T):
    put(t, 20, 70, 30, 1.5, 8.5, 2600)
    put(t, 20, 70, 54, 1.5, 8.5, 2400)

# --- D: phân bào THẬT, MẸ SÁNG DẦN (3200 → 4200 ≈ rise 1,3), chia t=7 ---
D_AMP = [3200, 3200, 3200, 3200, 3200, 3800, 4200]
for t in range(0, 7):
    put(t, 30, 40 + t // 3, 90 + t // 4, 1.5, 8.5, D_AMP[t])
for t in range(7, T):
    k = t - 7
    put(t, 30, 42 - 1.5 * k, 94 + k, 1.5, 8.5, 2000)
    put(t, 30, 44 + 1.5 * k, 92 - k, 1.5, 8.5, 2000)

# --- E/F: merge-split ĐỨNG YÊN (regression: xác nhận động học từ chối) ---
for t in range(T):
    put(t, 8, 60, 60, 1.5, 8.5, 2800)
    if t >= 2:
        put(t, 8, 60, 86, 1.5, 8.5, 2200)

# --- G/H: merge-split GIÁO KHÉO — gộp sâu 4 khung (khối lượng ~2×) rồi tách,
#     2 con đi xa DẦN (vượt được DIV_SEP_GROWTH của ver 2!) ---
HX = [50, 46, 44, 26, 27, 27, 27, 42, 48, 54, 60, 66, 71, 75, 79, 82, 85, 88]
for t in range(T):
    put(t, 16, 100, 20, 1.5, 8.5, 3000)          # G đứng yên
    put(t, 16, 100, HX[t], 1.5, 8.5, 3000)        # H tiến vào, gộp, rồi tách xa dần

# --- I: phân bào THẬT, CHỊ EM XA 13,4 µm ngay khung sinh (bất đối xứng:
#     d1 sát mẹ 2 µm — mẹ khớp Hungarian; d2 cách mẹ 11,4 µm ≤ parent gate 12) ---
for t in range(0, 6):
    put(t, 24, 12, 60, 1.5, 8.5, 3000)
for t in range(6, T):
    put(t, 24, 12, 55 - (t - 6), 1.5, 8.5, 1700)  # d1
    put(t, 24, 12, 88 + (t - 6), 1.5, 8.5, 1700)  # d2

# --- J: mờ đúng 2 khung t=8,9 (regression: skip + nội suy node giữa) ---
for t in range(T):
    amp = 5 if t in (8, 9) else 2800
    put(t, 12, 15 + t // 5, 45 + t // 6, 1.5, 8.5, amp)

vol = np.minimum(vol + rng.poisson(40, vol.shape), 65535).astype(np.uint16)

# ==== ghi zarr giả (cấu trúc Kaggle) ====
test_dir = f'{ROOT}/test'
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

# ==== chạy ver 3 rồi ver 2 trên CÙNG dữ liệu (đối chứng) ====
for G, out, base in ((G3, 'out3', BASE3), (G2, 'out2', BASE2)):
    G['TEST_DIR'] = test_dir
    G['RUN_PREVIEW'] = False
    os.makedirs(f'{ROOT}/{out}', exist_ok=True)
    os.chdir(f'{ROOT}/{out}')
    load_cells(G, base, ['cell3code.py', 'cell4code.py'])


def forks_of(sub):
    rows = sub.to_dict('records')
    nodes = [r for r in rows if r['row_type'] == 'node']
    edges = [r for r in rows if r['row_type'] == 'edge']
    tpos = {r['node_id']: (r['t'], r['z'], r['y'], r['x']) for r in nodes}
    forks = {}
    for e in edges:
        forks.setdefault(e['source_id'], []).append(e['target_id'])
    return [s for s, tg in forks.items() if len(tg) >= 2], tpos, nodes, edges


def d_um(a, b):
    return float(np.linalg.norm((np.array(a) - np.array(b)) * SCALE))


fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' — {extra}' if extra else ''))
    if not cond:
        fails.append(name)


sub3 = G3['submission']
sub2 = G2['submission']

# ---------- kiểm tra chung (ver 3) ----------
rows3 = sub3.to_dict('records')
nodes3 = [r for r in rows3 if r['row_type'] == 'node']
edges3 = [r for r in rows3 if r['row_type'] == 'edge']

check('cột đúng', list(sub3.columns) == G3['COLS'])
check('index tên id', sub3.index.name == 'id')
check('chỉ 1 dataset', set(r['dataset'] for r in rows3) == {'synth'})

nids = [r['node_id'] for r in nodes3]
check('node_id duy nhất', len(set(nids)) == len(nids))
nid_set = set(nids)
check('node t/z/y/x nguyên & ≥ 0',
      all(r['t'] >= 0 and r['z'] >= 0 and r['y'] >= 0 and r['x'] >= 0 for r in nodes3))
check('edge tham chiếu node tồn tại',
      all(r['source_id'] in nid_set and r['target_id'] in nid_set for r in edges3))
check('không tự nối / trùng cạnh',
      all(r['source_id'] != r['target_id'] for r in edges3) and
      len({(r['source_id'], r['target_id']) for r in edges3}) == len(edges3))

tpos3 = {r['node_id']: (r['t'], r['z'], r['y'], r['x']) for r in nodes3}


def consecutive(e):
    return tpos3[e['source_id']][0] + 1 == tpos3[e['target_id']][0]


check('mọi cạnh liền khung (không cạnh nhảy)', all(consecutive(e) for e in edges3))

# ---------- tình huống 1+2: 2 phân bào thật (D sáng dần + I chị em xa) ----------
f3, _, _, _ = forks_of(sub3)


def forks_near(center, t_lo, t_hi, radius, forks, tpos):
    out = []
    for s in forks:
        t, z, y, x = tpos[s]
        if t_lo <= t <= t_hi and d_um((z, y, x), center) <= radius:
            out.append((s, t, (z, y, x)))
    return out


d_forks = forks_near((30, 43, 93), 8, 16, 15.0, f3, tpos3)
i_forks = forks_near((24, 12, 60), 4, 12, 15.0, f3, tpos3)
e_forks = forks_near((8, 60, 60), 2, 17, 20.0, f3, tpos3)
g_forks = forks_near((16, 100, 23), 5, 12, 10.0, f3, tpos3)

check('phân bào D (mẹ sáng dần) được xác nhận', len(d_forks) == 1,
      f'{d_forks}')
check('phân bào I (chị em xa 13,4 µm) được xác nhận', len(i_forks) == 1,
      f'{i_forks}')
check('merge-split đứng yên (E/F) KHÔNG tạo phân bào', len(e_forks) == 0,
      f'{e_forks}')
check('merge-split khéo (G/H) KHÔNG tạo phân bào — cửa mass stability',
      len(g_forks) == 0, f'{g_forks}')
check('ver 3: đúng 2 phân bào, không thừa', len(f3) == 2,
      f'tổng fork: {[(s, tpos3[s]) for s in f3]}')
check('ver 3: mass stability đã chặn ≥ 1 ứng viên', G3['TRK'].n_rej_mass >= 1,
      f'n_rej_mass={G3["TRK"].n_rej_mass}')
check('ver 3: xác nhận động học đã từ chối ≥ 1 (E/F)', G3['TRK'].n_rej_dyn >= 1,
      f'n_rej_dyn={G3["TRK"].n_rej_dyn}')

# ---------- đối chứng ver 2 trên CÙNG dữ liệu ----------
f2, tpos2, _, _ = forks_of(sub2)
g2_forks = forks_near((16, 100, 23), 5, 12, 10.0, f2, tpos2)
i2_forks = forks_near((24, 12, 60), 4, 12, 15.0, f2, tpos2)
e2_forks = forks_near((8, 60, 60), 2, 17, 20.0, f2, tpos2)
print(f'[đối chứng ver 2] fork gần G (FP merge-split khéo): {len(g2_forks)} — '
      f'{g2_forks if g2_forks else "ver 2 cũng chặn (?!)"}')
print(f'[đối chứng ver 2] fork gần I (chị em xa): {len(i2_forks)} — '
      f'kỳ vọng 0 (gate 12/10 bỏ sót)')
print(f'[đối chứng ver 2] fork gần E (đứng yên): {len(e2_forks)} — kỳ vọng 0')
check('MINH HOẠ: ver 2 xác nhận nhầm merge-split khéo (G/H), ver 3 chặn',
      len(g2_forks) >= 1 and len(g_forks) == 0)
check('MINH HOẠ: ver 2 bỏ sót chị em xa (I), ver 3 bắt',
      len(i2_forks) == 0 and len(i_forks) == 1)

# ---------- regression: tách blob gộp B/C ----------
def nodes_near3(t, y0, x0, rad=10):
    return [r for r in nodes3 if r['t'] == t and np.hypot(r['y'] - y0, r['x'] - x0) < rad]


split_ok = True
for t in [0, 5, 15]:
    nb, nc = nodes_near3(t, 70, 30), nodes_near3(t, 70, 54)
    if not (len(nb) >= 1 and len(nc) >= 1):
        split_ok = False
check('tách blob gộp B/C thành 2 node', split_ok)

# ---------- regression: nội suy node tại khung mờ (J, t=8,9) ----------
j_t8 = (12, 15 + 8 // 5, 45 + 8 // 6)
j_t9 = (12, 15 + 9 // 5, 45 + 9 // 6)


def interp_ok(t, true_pos):
    cand = [r for r in nodes3 if r['t'] == t]
    if not cand:
        return False
    best = min(cand, key=lambda r: d_um((r['z'], r['y'], r['x']), true_pos))
    if d_um((best['z'], best['y'], best['x']), true_pos) > 7.0:
        return False
    return any(e['target_id'] == best['node_id'] for e in edges3)


check('nội suy node khung mất t=8 (gần vị trí J + có cạnh vào)', interp_ok(8, j_t8))
check('nội suy node khung mất t=9 (gần vị trí J + có cạnh vào)', interp_ok(9, j_t9))

# ---------- độ chính xác vị trí ≤ 7 µm ----------
def nearest_d(t, z, y, x):
    cand = [r for r in nodes3 if r['t'] == t]
    if not cand:
        return 999.0
    return min(d_um((r['z'], r['y'], r['x']), (z, y, x)) for r in cand)


acc_ok, worst = True, 0.0
for (t, z, y, x) in TRUE:
    d = nearest_d(t, z, y, x)
    worst = max(worst, d)
    if d > 7.0:
        acc_ok = False
check('node khớp vị trí ≤ 7 µm', acc_ok, f'worst={worst:.2f} µm')

# ---------- thống kê ----------
per_frame = {}
for r in nodes3:
    per_frame[r['t']] = per_frame.get(r['t'], 0) + 1
print('node/khung:', dict(sorted(per_frame.items())))
print(f'ver 3 confirmed/rejected: {G3["TRK"].n_div_confirmed}/{G3["TRK"].n_div_rejected} '
      f'(mass {G3["TRK"].n_rej_mass} · dyn {G3["TRK"].n_rej_dyn} · lost {G3["TRK"].n_rej_lost})')
print(f'ver 2 confirmed/rejected: {G2["TRK"].n_div_confirmed}/{G2["TRK"].n_div_rejected}')

print()
print('TỔNG: ' + ('ĐẠT TẤT CẢ' if not fails else f'{len(fails)} LỖI: {fails}'))
sys.exit(0 if not fails else 1)
