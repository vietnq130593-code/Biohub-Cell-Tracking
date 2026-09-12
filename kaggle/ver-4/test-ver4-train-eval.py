"""Kiểm chứng E2E notebook ver4-train-eval.ipynb (chạy trên TRAIN + local scorer).

Dựng 1 dataset synthetic có CẢ .zarr (ảnh) LẪN .geff (nhãn GT đúng format),
rồi exec tuần tự đúng 7 cell của download/ver4-train-eval.ipynb trong một
namespace — mô phỏng đúng "Import Notebook → Run All" trên Kaggle.

Kỳ vọng:
  * chạy sạch không exception (đủ 6 cell code)
  * node_recall ≥ 0,9 (nội suy khung mờ + blob CoM phủ GT)
  * adj_edge_jaccard ≥ 0,75 (kỳ vọng ~0,85+; FN chỉ còn ở khung gộp blob)
  * division_tp ≥ 1 (phân bào D tách nhanh ngay từ khung sinh → fork đúng
    timing GT t=6 → metric division khớp được)
"""
import itertools
import json
import os
import sys

import numpy as np

BASE = '/home/z/my-project/kaggle'
NB_PATH = '/home/z/my-project/download/ver4-train-eval.ipynb'
ROOT = '/home/z/ver4train'

os.makedirs(ROOT, exist_ok=True)
train_dir = os.path.join(ROOT, 'train')
os.makedirs(train_dir, exist_ok=True)

T, Z, Y, X = 18, 40, 150, 150
rng = np.random.default_rng(11)
vol = np.zeros((T, Z, Y, X), dtype=np.float64)


def put(t, z, y, x, sz, syx, amp):
    z0, z1 = max(0, int(z - 5 * sz)), min(Z, int(z + 5 * sz) + 1)
    y0, y1 = max(0, int(y - 5 * syx)), min(Y, int(y + 5 * syx) + 1)
    x0, x1 = max(0, int(x - 5 * syx)), min(X, int(x + 5 * syx) + 1)
    zz, yy, xx = np.mgrid[z0:z1, y0:y1, x0:x1]
    r2 = ((zz - z) / sz) ** 2 + ((yy - y) / syx) ** 2 + ((xx - x) / syx) ** 2
    vol[t, z0:z1, y0:y1, x0:x1] += amp * np.exp(-r2 / 2.0)


# ==== quỹ đạo (đồng thời sinh ảnh + GT) ====
GT_NODES, GT_EDGES = [], []
GID = itertools.count(1)


def add_chain(pos, amp, t0=0, t1=T - 1):
    ids = []
    for t in range(t0, t1 + 1):
        z, y, x = pos(t)
        put(t, z, y, x, 1.5, 8.5, amp(t))
        nid = next(GID)
        GT_NODES.append((nid, t, int(round(z)), int(round(y)), int(round(x))))
        ids.append(nid)
    GT_EDGES.extend(zip(ids[:-1], ids[1:]))
    return ids


HX = [42, 38, 36, 18, 19, 19, 19, 34, 40, 46, 52, 58, 63, 67, 71, 74, 77, 80]
NX = [88, 84, 80, 76, 72, 59, 59, 59, 59] + [66 + 5 * (t - 9) for t in range(9, T)]
PY = {t: (20.0 if t < 8 else 20.0 + 8.6 * (t - 7)) for t in range(T)}
D_AMP = [3200, 3200, 3200, 3200, 3200, 3800, 4200]

add_chain(lambda t: (22, 12 + 2 * (t // 4), 12 + (t // 4)), lambda t: 3000)      # A
add_chain(lambda t: (20, 90, 30), lambda t: 2600)                                  # B
add_chain(lambda t: (20, 90, 54), lambda t: 2400)                                  # C
mom = add_chain(lambda t: (30, 30, 60), lambda t: D_AMP[t], 0, 6)                  # D mẹ
d1 = add_chain(lambda t: (30, 28 - 1.5 * (t - 7), 48 - (t - 7)), lambda t: 2000, 7)   # d1
d2 = add_chain(lambda t: (30, 32 + 1.5 * (t - 7), 72 + (t - 7)), lambda t: 2000, 7)   # d2
GT_EDGES += [(mom[-1], d1[0]), (mom[-1], d2[0])]                                   # cạnh phân bào
add_chain(lambda t: (8, 20, 120), lambda t: 2800)                                   # E
add_chain(lambda t: (8, 20, 146), lambda t: 2200, 2)                               # F
add_chain(lambda t: (16, 60, 12), lambda t: 3000)                                   # G
add_chain(lambda t: (16, 60, HX[t]), lambda t: 3000)                                # H
add_chain(lambda t: (20, 30, 40), lambda t: 2600)                                   # M
add_chain(lambda t: (20, 30, NX[t]), lambda t: 2600)                                # N
add_chain(lambda t: (12, 15 + t // 5, 45 + t // 6),                                 # J (mờ t=8,9)
          lambda t: 5 if t in (8, 9) else 2800)
add_chain(lambda t: (32, PY[t], 95 + 5 * t if t < 8 else 130),                     # P (mờ+quẹo)
          lambda t: 5 if t in (8, 9, 10) else 2800)

vol = np.minimum(vol + rng.poisson(40, vol.shape), 65535).astype(np.uint16)

# ==== ghi .zarr (cấu trúc Kaggle) ====
import blosc2

zpath = os.path.join(train_dir, 'synth.zarr')
os.makedirs(f'{zpath}/0/c', exist_ok=True)
for t in range(T):
    cd = f'{zpath}/0/c/{t}/0/0/0'
    os.makedirs(os.path.dirname(cd), exist_ok=True)
    with open(cd, 'wb') as f:
        f.write(blosc2.compress(vol[t]))
with open(f'{zpath}/0/zarr.json', 'w') as f:
    json.dump({'shape': [T, Z, Y, X], 'data_type': 'uint16',
               'chunk_grid': {'name': 'regular',
                              'configuration': {'chunk_shape': [1, Z, Y, X]}}}, f)

# ==== ghi .geff (zarr v2 như BTC — tái dùng cách của test-scorer-synth) ====
def write_arr(arr_dir, data):
    os.makedirs(arr_dir, exist_ok=True)
    data = np.ascontiguousarray(data)
    chunks = [len(data)] if data.ndim == 1 else list(data.shape)
    meta = {'chunks': chunks, 'compressor': {'id': 'blosc', 'cname': 'zstd',
                                             'clevel': 5, 'shuffle': 1},
            'dtype': data.dtype.str, 'fill_value': 0, 'filters': None,
            'order': 'C', 'shape': list(data.shape), 'zarr_format': 2}
    with open(os.path.join(arr_dir, '.zarray'), 'w') as f:
        json.dump(meta, f)
    key = '.'.join('0' for _ in data.shape)
    with open(os.path.join(arr_dir, key), 'wb') as f:
        f.write(blosc2.compress(data.tobytes(), typesize=1))


def write_geff(path, nodes, edges, n_total):
    os.makedirs(os.path.join(path, 'nodes', 'props'), exist_ok=True)
    os.makedirs(os.path.join(path, 'edges'), exist_ok=True)
    write_arr(os.path.join(path, 'nodes', 'ids'),
              np.array([n[0] for n in nodes], dtype=np.int64))
    for i, name in enumerate(('t', 'z', 'y', 'x')):
        write_arr(os.path.join(path, 'nodes', 'props', name, 'values'),
                  np.array([n[i + 1] for n in nodes], dtype=np.float64))
    write_arr(os.path.join(path, 'edges', 'ids'),
              np.array(edges, dtype=np.int64).reshape(-1, 2))
    attrs = {'geff': {'directed': True, 'geff_version': '0.3.0',
                      'extra': {'estimated_number_of_nodes': n_total}}}
    with open(os.path.join(path, '.zattrs'), 'w') as f:
        json.dump(attrs, f)


write_geff(os.path.join(train_dir, 'synth.geff'), GT_NODES, GT_EDGES, len(GT_NODES))
print(f'GT: {len(GT_NODES)} node · {len(GT_EDGES)} cạnh (1 phân bào)')

# ==== chạy đúng 7 cell của notebook ====
nb = json.load(open(NB_PATH))
G = {'__name__': '__main__'}
out_dir = os.path.join(ROOT, 'out')
os.makedirs(out_dir, exist_ok=True)
os.chdir(out_dir)

code_cells = [c for c in nb['cells'] if c['cell_type'] == 'code']
assert len(code_cells) == 6, len(code_cells)
for i, c in enumerate(code_cells):
    src = c['source'] if isinstance(c['source'], str) else ''.join(c['source'])
    exec(compile(src, f'<nb-cell{i}>', 'exec'), G)
    if i == 1:      # sau cell 2' (tham số) — trỏ vào dataset synthetic
        G['TRAIN_DIR'] = train_dir
        G['DATA_DIR'] = train_dir

fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' — {extra}' if extra else ''))
    if not cond:
        fails.append(name)


s = G['s']
check('notebook chạy đủ 7 cell không exception', True)
check('scorer ra kết quả tổng hợp', s is not None and s['n'] == 1)
check(f"node_recall ≥ 0,9", s['node_recall'] >= 0.9, f"{s['node_recall']:.3f}")
check(f"adj_edge_jaccard ≥ 0,75", s['adj_edge_jaccard'] >= 0.75, f"{s['adj_edge_jaccard']:.3f}")
check('bắt được phân bào D (division_tp ≥ 1)', s['division_tp'] >= 1,
      f"div {s['division_tp']}/{s['division_fp']}/{s['division_fn']}")
check('FN cạnh < TP cạnh (track đã nối lại phần lớn)',
      s['edge_fn'] < s['edge_tp'], f"TP {s['edge_tp']} · FP {s['edge_fp']} · FN {s['edge_fn']}")
print(f"score = {s['score']:.4f} (adjEJ {s['adj_edge_jaccard']:.4f} + "
      f"0,1·divJ {s['division_jaccard']:.4f})")

print()
print('TỔNG: ' + ('ĐẠT TẤT CẢ' if not fails else f'{len(fails)} LỖI: {fails}'))
sys.exit(0 if not fails else 1)
