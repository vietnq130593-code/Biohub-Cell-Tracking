"""Kiểm chứng ver 4 trên dữ liệu Zarr tổng hợp (mô phỏng cấu trúc Kaggle).

Kịch bản test — nhắm thẳng mục tiêu ver 4 (nối lại track đứt):
  1. BLOB-BREAK (M/N): 2 tế bào gộp blob 1 đỉnh 4 khung (sep 19 vox < 2,4σ
     → không dip → 1 node CoM) rồi tách. Track bạn đồng hành (M) cưỡi CoM,
     track N chết (4 miss > MAX_SKIP 3) → STITCHING phải nối N(t4)→N'(t9)
     qua 4 node nội suy. Đối chứng STITCH_ENABLED=False: track đứt hẳn.
  2. MỜ + QUẸO (P): tế bào mờ đúng 3 khung (amp 5) và QUẸO 90° trong lúc
     mờ (+x → +y, 8,6 vox/khung) → dự đoán pos+vel·gap trượt 16,2µm >
     SKIP_GATE 12 → frame-skip THẤT BẠI → stitching gap 4 (14µm ≤ gate 16)
     phải nối lại + 3 node nội suy ĐÚNG vị trí thật (quỹ đạo thẳng).
  3. MERGE-SPLIT KHÉO (G/H — regression ver 3): gộp sâu 4 khung (khối lượng
     ~2×) rồi tách xa dần — phân bào phải bị chặn bằng "ổn định khối lượng
     mẹ" (rise 2,0 > 1,7); sau đó H'.start(t7) được stitch về H.end(t2).
  4. Regression ver 3: phân bào thật (D, mẹ sáng dần) xác nhận; merge-split
     đứng yên (E/F) bị động học từ chối; blob có eo (B/C) tách 2 node;
     tế bào mờ 2 khung (J) nội suy tại chỗ bởi frame-skip.
  5. Format: cột đúng, node_id duy nhất, mọi cạnh liền khung (stitch không
     bao giờ tạo cạnh nhảy), node khớp vị trí ≤ 7µm.
"""
import itertools
import json
import os
import sys
import time

import numpy as np

BASE4 = '/home/z/my-project/kaggle/ver-4'
ROOT = '/home/z/ver4test'


def load_cells(ns, base, names):
    for name in names:
        path = os.path.join(base, name)
        src = open(path).read()
        exec(compile(src, path, 'exec'), ns)


G4 = {'__name__': '__main__'}
load_cells(G4, BASE4, ['cell1code.py', 'cell2code.py'])
G4B = {'__name__': '__main__'}
load_cells(G4B, BASE4, ['cell1code.py', 'cell2code.py'])
G4B['STITCH_ENABLED'] = False          # đối chứng: stitching TẮT

# ==== tạo dataset tổng hợp ====
import blosc2

SCALE = G4['SCALE']
T, Z, Y, X = 18, 40, 150, 150

rng = np.random.default_rng(11)
vol = np.zeros((T, Z, Y, X), dtype=np.float64)
TRUE = []


def put(t, z, y, x, sz, syx, amp):
    """Cộng dồn Gaussian (SUM — đúng vật lý huỳnh quang: blob gộp có khối
    lượng ~2×; 2 tế bào cách < ~2,4σ không có dip → 1 đỉnh duy nhất)."""
    z0, z1 = max(0, int(z - 5 * sz)), min(Z, int(z + 5 * sz) + 1)
    y0, y1 = max(0, int(y - 5 * syx)), min(Y, int(y + 5 * syx) + 1)
    x0, x1 = max(0, int(x - 5 * syx)), min(X, int(x + 5 * syx) + 1)
    zz, yy, xx = np.mgrid[z0:z1, y0:y1, x0:x1]
    r2 = ((zz - z) / sz) ** 2 + ((yy - y) / syx) ** 2 + ((xx - x) / syx) ** 2
    vol[t, z0:z1, y0:y1, x0:x1] += amp * np.exp(-r2 / 2.0)
    TRUE.append((t, z, y, x))


# --- A: di chuyển chéo nhẹ (tham chiếu độ chính xác; đặt xa G ≥ 40 vox
#     để không gộp blob — bài học debug vòng 1) ---
for t in range(T):
    put(t, 22, 12 + 2 * (t // 4), 12 + (t // 4), 1.5, 8.5, 3000)

# --- B/C: blob GỘP CÓ EO (24 vox ≈ 2,8σ — 1 component, 2 đỉnh) ---
for t in range(T):
    put(t, 20, 90, 30, 1.5, 8.5, 2600)
    put(t, 20, 90, 54, 1.5, 8.5, 2400)

# --- D: phân bào THẬT, MẸ SÁNG DẦN (3200 → 4200 ≈ rise 1,3), chia t=7 ---
D_AMP = [3200, 3200, 3200, 3200, 3200, 3800, 4200]
for t in range(0, 7):
    put(t, 30, 44, 20, 1.5, 8.5, D_AMP[t])
for t in range(7, T):
    k = t - 7
    put(t, 30, 40 - 2.0 * k, 24 + k, 1.5, 8.5, 2000)   # d1 (tách nhanh để
    put(t, 30, 44 + 2.0 * k, 26 + k, 1.5, 8.5, 2000)   # d2  blob tách ~t=11)

# --- E/F: merge-split ĐỨNG YÊN (regression: xác nhận động học từ chối) ---
for t in range(T):
    put(t, 8, 20, 120, 1.5, 8.5, 2800)
    if t >= 2:
        put(t, 8, 20, 146, 1.5, 8.5, 2200)

# --- G/H: merge-split GIÁO KHÉO — gộp sâu 4 khung (khối lượng ~2×) rồi
#     tách xa dần (vượt được DIV_SEP_GROWTH) → phải bị MASS STABILITY chặn;
#     sau tách, H' phải được stitching nối về H ---
HX = [42, 38, 36, 18, 19, 19, 19, 34, 40, 46, 52, 58, 63, 67, 71, 74, 77, 80]
for t in range(T):
    put(t, 16, 60, 12, 1.5, 8.5, 3000)            # G đứng yên
    put(t, 16, 60, HX[t], 1.5, 8.5, 3000)         # H tiến vào, gộp, tách xa dần

# --- M/N: BLOB-BREAK — N tiến sát M (sep 19 vox < 2,4σ → 1 đỉnh), gộp
#     4 khung (t=5..8) rồi lùi ra; M cưỡi CoM, N chết → stitch nối lại ---
NX = [88, 84, 80, 76, 72, 59, 59, 59, 59] + [66 + 5 * (t - 9) for t in range(9, T)]
for t in range(T):
    put(t, 20, 30, 40, 1.5, 8.5, 2600)            # M đứng yên
    put(t, 20, 30, NX[t], 1.5, 8.5, 2600)         # N tiến vào, gộp, lùi ra

# --- J: mờ đúng 2 khung t=8,9 (regression: frame-skip + nội suy tại chỗ) ---
for t in range(T):
    amp = 5 if t in (8, 9) else 2800
    put(t, 12, 15 + t // 5, 45 + t // 6, 1.5, 8.5, amp)

# --- P: MỜ + QUẸO — đi +x (y=20 cố định, t=0..7), mờ 3 khung t=8..10 và
#     quẹo +y 8,6 vox/khung, xuất hiện lại t=11 → frame-skip trượt (16,2µm
#     > SKIP_GATE 12 vì vel +x cũ), stitching gap 4 (14µm ≤ gate 16) nối
#     lại + nội suy ĐÚNG quỹ đạo thẳng (dạng 20+8,6(t−7)) ---
PY = {t: (20.0 if t < 8 else 20.0 + 8.6 * (t - 7)) for t in range(T)}
for t in range(T):
    amp = 5 if t in (8, 9, 10) else 2800
    if t < 8:
        put(t, 32, PY[t], 50 + 5 * t, 1.5, 8.5, amp)
    else:
        put(t, 32, PY[t], 85.0, 1.5, 8.5, amp)

# --- W: ĐỨNG YÊN + MỜ 4 KHUNG (t=8..11 > MAX_SKIP 3) → d(end,start) = 0 —
#     đúng trường hợp bug d<=0 đã vá: stitch phải nối lại tại CHÍNH vị trí đó ---
for t in range(T):
    amp = 5 if 8 <= t <= 11 else 2800
    put(t, 12, 100, 20, 1.5, 8.5, amp)

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

# ==== chạy ver 4 (stitch BẬT) và ver 4b (stitch TẮT) trên cùng dữ liệu ====
for G, out in ((G4, 'out4'), (G4B, 'out4b')):
    G['TEST_DIR'] = test_dir
    G['DATA_DIR'] = test_dir
    G['RUN_PREVIEW'] = False
    os.makedirs(f'{ROOT}/{out}', exist_ok=True)
    os.chdir(f'{ROOT}/{out}')
    load_cells(G, BASE4, ['cell3code.py', 'cell4code.py'])


def d_um(a, b):
    return float(np.linalg.norm((np.array(a) - np.array(b)) * SCALE))


fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' — {extra}' if extra else ''))
    if not cond:
        fails.append(name)


def build(sub):
    """Trả về (nodes, edges, tpos, comp: nid → gốc thành phần liên thông yếu)."""
    rows = sub.to_dict('records')
    nodes = [r for r in rows if r['row_type'] == 'node']
    edges = [r for r in rows if r['row_type'] == 'edge']
    tpos = {r['node_id']: (r['t'], r['z'], r['y'], r['x']) for r in nodes}
    parent = {r['node_id']: r['node_id'] for r in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e in edges:
        s, d = e['source_id'], e['target_id']
        if s in parent and d in parent:
            parent[find(s)] = find(d)
    comp = {nid: find(nid) for nid in parent}
    return nodes, edges, tpos, comp


def node_near(nodes, t, pos, rad_um=9.0):
    best, bd = None, 1e9
    for r in nodes:
        if r['t'] != t:
            continue
        d = d_um((r['z'], r['y'], r['x']), pos)
        if d < bd:
            bd, best = d, r
    return best if bd <= rad_um else None


def forks_of(edges):
    forks = {}
    for e in edges:
        forks.setdefault(e['source_id'], []).append(e['target_id'])
    return [s for s, tg in forks.items() if len(tg) >= 2]


sub4 = G4['submission']
sub4b = G4B['submission']
rows4 = sub4.to_dict('records')
nodes4 = [r for r in rows4 if r['row_type'] == 'node']
edges4 = [r for r in rows4 if r['row_type'] == 'edge']
_, _, _, comp4 = build(sub4)
nodes4b, edges4b, _, comp4b = build(sub4b)

# ---------- kiểm tra format ----------
check('cột đúng', list(sub4.columns) == G4['COLS'])
check('index tên id', sub4.index.name == 'id')
check('chỉ 1 dataset', set(r['dataset'] for r in rows4) == {'synth'})

nids = [r['node_id'] for r in nodes4]
check('node_id duy nhất', len(set(nids)) == len(nids))
nid_set = set(nids)
check('node t/z/y/x nguyên & ≥ 0',
      all(r['t'] >= 0 and r['z'] >= 0 and r['y'] >= 0 and r['x'] >= 0 for r in nodes4))
check('edge tham chiếu node tồn tại',
      all(r['source_id'] in nid_set and r['target_id'] in nid_set for r in edges4))
check('không tự nối / trùng cạnh',
      all(r['source_id'] != r['target_id'] for r in edges4) and
      len({(r['source_id'], r['target_id']) for r in edges4}) == len(edges4))

tpos4 = {r['node_id']: (r['t'], r['z'], r['y'], r['x']) for r in nodes4}
check('mọi cạnh liền khung (không cạnh nhảy)',
      all(tpos4[e['source_id']][0] + 1 == tpos4[e['target_id']][0] for e in edges4))

# ---------- kịch bản 1+2+3: stitching nối lại track đứt ----------
def same_track(nodes, comp, t0, p0, t1, p1):
    a = node_near(nodes, t0, p0)
    b = node_near(nodes, t1, p1)
    if a is None or b is None:
        return False, (a, b)
    return comp[a['node_id']] == comp[b['node_id']], (a, b)


for name, t0, p0, t1, p1 in [
    ('N (blob-break): t=0 ↔ t=17 cùng 1 track', 0, (20, 30, NX[0]), 17, (20, 30, NX[17])),
    ('H (merge-split khéo): t=0 ↔ t=17 cùng 1 track', 0, (16, 60, HX[0]), 17, (16, 60, HX[17])),
    ('P (mờ + quẹo): t=0 ↔ t=17 cùng 1 track', 0, (32, PY[0], 50), 17, (32, PY[17], 85)),
    ('W (đứng yên + mờ 4 khung): t=0 ↔ t=17 cùng 1 track', 0, (12, 100, 20), 17, (12, 100, 20)),
]:
    ok, ab = same_track(nodes4, comp4, t0, p0, t1, p1)
    check('stitch BẬT · ' + name, ok, f'{ab[0] and tpos4[ab[0]["node_id"]]} → {ab[1] and tpos4[ab[1]["node_id"]]}')

for name, t0, p0, t1, p1 in [
    ('N: t=0 ↔ t=17 NGẮT track', 0, (20, 30, NX[0]), 17, (20, 30, NX[17])),
    ('H: t=0 ↔ t=17 NGẮT track', 0, (16, 60, HX[0]), 17, (16, 60, HX[17])),
    ('P: t=0 ↔ t=17 NGẮT track', 0, (32, PY[0], 50), 17, (32, PY[17], 85)),
    ('W: t=0 ↔ t=17 NGẮT track', 0, (12, 100, 20), 17, (12, 100, 20)),
]:
    ok, _ab = same_track(nodes4b, comp4b, t0, p0, t1, p1)
    check('stitch TẮT · ' + name, not ok)

check('stitch thêm cạnh + node nội suy (A/B)',
      len(edges4) > len(edges4b) and len(nodes4) > len(nodes4b),
      f'cạnh {len(edges4b)} → {len(edges4)} · node {len(nodes4b)} → {len(nodes4)}')

# node nội suy P tại khung mờ phải ĐÚNG vị trí thật (quỹ đạo thẳng) và có cạnh vào
def interp_near(t, true_pos, tol=3.0):
    cand = [r for r in nodes4 if r['t'] == t]
    if not cand:
        return None
    best = min(cand, key=lambda r: d_um((r['z'], r['y'], r['x']), true_pos))
    dd = d_um((best['z'], best['y'], best['x']), true_pos)
    has_in = any(e['target_id'] == best['node_id'] for e in edges4)
    return best if dd <= tol and has_in else None


for t in (8, 9, 10):
    check(f'P nội suy khung mờ t={t} (≤3µm + có cạnh vào)',
          interp_near(t, (32, PY[t], 85)) is not None)

# ---------- kịch bản 4: regression ver 3 ----------
f4 = forks_of(edges4)


def forks_near(center, t_lo, t_hi, radius):
    out = []
    for s in f4:
        t, z, y, x = tpos4[s]
        if t_lo <= t <= t_hi and d_um((z, y, x), center) <= radius:
            out.append((s, t, (z, y, x)))
    return out


d_forks = forks_near((30, 44, 20), 6, 12, 15.0)
e_forks = forks_near((8, 20, 120), 3, 17, 20.0)
g_forks = forks_near((16, 60, 15), 5, 12, 10.0)
m_forks = forks_near((20, 30, 50), 6, 12, 15.0)

check('phân bào D (mẹ sáng dần) được xác nhận', len(d_forks) == 1, f'{d_forks}')
check('merge-split đứng yên (E/F) KHÔNG tạo phân bào', len(e_forks) == 0, f'{e_forks}')
check('merge-split khéo (G/H) KHÔNG tạo phân bào — cửa mass stability',
      len(g_forks) == 0, f'{g_forks}')
check('blob-break (M/N) KHÔNG tạo phân bào giả', len(m_forks) == 0, f'{m_forks}')
check('ver 4: đúng 1 phân bào (chỉ D), không thừa', len(f4) == 1,
      f'tổng fork: {[(s, tpos4[s]) for s in f4]}')
check('mass stability đã chặn ≥ 1 ứng viên (G/H hoặc M/N)', G4['TRK'].n_rej_mass >= 1,
      f'n_rej_mass={G4["TRK"].n_rej_mass}')
check('xác nhận động học đã từ chối ≥ 1 (E/F)', G4['TRK'].n_rej_dyn >= 1,
      f'n_rej_dyn={G4["TRK"].n_rej_dyn}')

# blob có eo tách 2 node (B/C)
def nodes_near(t, y0, x0, rad=10):
    return [r for r in nodes4 if r['t'] == t and np.hypot(r['y'] - y0, r['x'] - x0) < rad]


split_ok = all(len(nodes_near(t, 90, 30)) >= 1 and len(nodes_near(t, 90, 54)) >= 1
               for t in [0, 5, 15])
check('tách blob gộp B/C thành 2 node', split_ok)

# J mờ 2 khung → frame-skip nội suy tại chỗ (regression ver 3)
j_t8 = (12, 15 + 8 // 5, 45 + 8 // 6)
j_t9 = (12, 15 + 9 // 5, 45 + 9 // 6)
check('J nội suy khung mất t=8', interp_near(8, j_t8, tol=7.0) is not None)
check('J nội suy khung mất t=9', interp_near(9, j_t9, tol=7.0) is not None)

# ---------- độ chính xác vị trí ≤ 7 µm ----------
def nearest_d(t, z, y, x):
    cand = [r for r in nodes4 if r['t'] == t]
    if not cand:
        return 999.0
    return min(d_um((r['z'], r['y'], r['x']), (z, y, x)) for r in cand)


acc_ok, worst = True, 0.0
for (t, z, y, x) in TRUE:
    d = nearest_d(t, z, y, x)
    worst = max(worst, d)
    if d > 7.0:
        acc_ok = False
check('node khớp vị trí ≤ 7 µm (kể cả khung mờ/gộp)', acc_ok, f'worst={worst:.2f} µm')

# ---------- thống kê ----------
per_frame = {}
for r in nodes4:
    per_frame[r['t']] = per_frame.get(r['t'], 0) + 1
print('node/khung:', dict(sorted(per_frame.items())))
print(f'ver 4 confirmed/rejected: {G4["TRK"].n_div_confirmed}/{G4["TRK"].n_div_rejected} '
      f'(mass {G4["TRK"].n_rej_mass} · dyn {G4["TRK"].n_rej_dyn} · lost {G4["TRK"].n_rej_lost})')
print(f'stitch on/off: {len(nodes4)}/{len(nodes4b)} node · {len(edges4)}/{len(edges4b)} cạnh')

print()
print('TỔNG: ' + ('ĐẠT TẤT CẢ' if not fails else f'{len(fails)} LỖI: {fails}'))
sys.exit(0 if not fails else 1)
