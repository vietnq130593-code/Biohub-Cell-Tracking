"""Kiểm chứng local scorer trên .geff tự tạo + 2 submission có điểm tính tay.

GT (voxel, 7 node, 5 cạnh, 1 phân bào tại A1, n_total=7):
  A0 t0 (0,0,0) → A1 t1 (0,1,0) [divider] → c1 t2 (0,2,0)
                                            → c2 t2 (0,2,12)
  B0 t0 (0,50,0) → B1 t1 (0,51,0) → B2 t2 (0,52,0)

Submission TỐT: đủ node + đủ cạnh + đủ phân bào
  → EJ=1.0 · adj=1.0 (n_pred=7=n_total) · divJ=1.0 · score = 1.100

Submission XẤU: + node X,Y xa (không match); cạnh X→Y (bỏ qua — không FP);
  cạnh chéo A1→B2 (FP); thiếu cạnh A1→c2 (FN + mất phân bào)
  → matched 6/7 (recall 6/7) · TP=4 FP=1 FN=1 → EJ=4/6=0.667
  · n_pred=9 → ratio=2/7 → adj=0.667·(1−0.1·2/7)=0.648
  · div: fork A1 (→c1,→B2): c2 không nằm trên nhánh nào → không TP;
    fork evaluable → FP → div TP=0 FP=1 FN=1 → divJ=0
  · score = 0.648
"""
import itertools
import json
import os
import sys

import blosc2
import numpy as np
import pandas as pd

BASE = '/home/z/ver2test/scorer-test'
G = {'__name__': '__main__'}


def load_cell(path):
    exec(compile(open(path).read(), path, 'exec'), G)


for name in ['scorer1code.py', 'scorer2code.py']:
    load_cell(os.path.join('/home/z/my-project/kaggle/scorer', name))


# ---------- tạo .geff ----------
def write_arr(arr_dir, data):
    os.makedirs(arr_dir, exist_ok=True)
    data = np.ascontiguousarray(data)
    if data.ndim == 1:
        chunks = [len(data)]
    else:
        chunks = list(data.shape)
    meta = {
        'chunks': chunks, 'compressor': {'id': 'blosc', 'cname': 'zstd',
                                          'clevel': 5, 'shuffle': 1},
        'dtype': data.dtype.str, 'fill_value': 0, 'filters': None,
        'order': 'C', 'shape': list(data.shape), 'zarr_format': 2,
    }
    with open(os.path.join(arr_dir, '.zarray'), 'w') as f:
        json.dump(meta, f)
    # zarr v2: chunk key có đúng số phần tử bằng số chiều mảng
    key = '.'.join('0' for _ in data.shape)
    with open(os.path.join(arr_dir, key), 'wb') as f:
        f.write(blosc2.compress(data.tobytes(), typesize=1))


def write_geff(path, nodes, edges, n_total):
    # nodes: list (nid, t, z, y, x); edges: list (s, d)
    os.makedirs(path, exist_ok=True)
    ids = np.array([n[0] for n in nodes], dtype=np.uint64)
    t = np.array([n[1] for n in nodes], dtype=np.float32)
    z = np.array([n[2] for n in nodes], dtype=np.float32)
    y = np.array([n[3] for n in nodes], dtype=np.float32)
    x = np.array([n[4] for n in nodes], dtype=np.float32)
    e = np.array(edges, dtype=np.uint64).reshape(-1, 2)

    attrs = {'geff': {'directed': True, 'geff_version': '0.3.0',
                      'extra': {'estimated_number_of_nodes': n_total}}}
    with open(os.path.join(path, '.zattrs'), 'w') as f:
        json.dump(attrs, f)
    write_arr(os.path.join(path, 'nodes', 'ids'), ids)
    for nm, v in [('t', t), ('z', z), ('y', y), ('x', x)]:
        write_arr(os.path.join(path, 'nodes', 'props', nm, 'values'), v)
    write_arr(os.path.join(path, 'edges', 'ids'), e)


train_dir = os.path.join(BASE, 'train')
os.makedirs(train_dir, exist_ok=True)

GT_NODES = [
    (1, 0, 0, 0, 0),      # A0
    (2, 1, 0, 1, 0),      # A1 — divider
    (3, 2, 0, 2, 0),      # c1
    (4, 2, 0, 2, 12),     # c2
    (5, 0, 0, 50, 0),     # B0
    (6, 1, 0, 51, 0),     # B1
    (7, 2, 0, 52, 0),     # B2
]
GT_EDGES = [(1, 2), (2, 3), (2, 4), (5, 6), (6, 7)]
write_geff(os.path.join(train_dir, 'synth.geff'), GT_NODES, GT_EDGES, 7)

# ---------- submission tốt ----------
good_rows = []
for nid, t, z, y, x in GT_NODES:
    good_rows.append({'dataset': 'synth', 'row_type': 'node', 'node_id': nid,
                      't': t, 'z': z, 'y': y, 'x': x,
                      'source_id': -1, 'target_id': -1})
for s, d in GT_EDGES:
    good_rows.append({'dataset': 'synth', 'row_type': 'edge', 'node_id': -1,
                      't': -1, 'z': -1, 'y': -1, 'x': -1,
                      'source_id': s, 'target_id': d})
good = pd.DataFrame(good_rows)

# ---------- submission xấu ----------
bad_nodes = [(101, 0, 0, 0, 0), (102, 1, 0, 1, 0), (103, 2, 0, 2, 0),
             (104, 2, 0, 2, 12), (105, 0, 0, 50, 0), (106, 1, 0, 51, 0),
             (107, 2, 0, 52, 0),
             (108, 1, 100, 100, 100), (109, 2, 100, 100, 101)]
bad_edges = [(101, 102), (102, 103), (105, 106), (106, 107),
             (108, 109),      # X→Y: không match GT → bị bỏ (không FP)
             (102, 107)]      # chéo A1→B2: FP
bad_rows = []
for nid, t, z, y, x in bad_nodes:
    bad_rows.append({'dataset': 'synth', 'row_type': 'node', 'node_id': nid,
                     't': t, 'z': z, 'y': y, 'x': x,
                     'source_id': -1, 'target_id': -1})
for s, d in bad_edges:
    bad_rows.append({'dataset': 'synth', 'row_type': 'edge', 'node_id': -1,
                     't': -1, 'z': -1, 'y': -1, 'x': -1,
                     'source_id': s, 'target_id': d})
bad = pd.DataFrame(bad_rows)

good.to_csv(os.path.join(BASE, 'good.csv'), index=False)
bad.to_csv(os.path.join(BASE, 'bad.csv'), index=False)

# ---------- chạy engine ----------
fails = []


def check(name, cond, extra=''):
    print(('PASS ' if cond else 'FAIL ') + name + (f' — {extra}' if extra else ''))
    if not cond:
        fails.append(name)


# test reader
gg = G['read_geff'](os.path.join(train_dir, 'synth.geff'))
check('đọc .geff: 7 node', len(gg['ids']) == 7)
check('đọc .geff: 5 cạnh', gg['edges'].shape == (5, 2))
check('đọc .geff: n_total = 7', gg['n_total'] == 7.0)
check('đọc .geff: t/xyz đúng', np.allclose(gg['t'], [0, 1, 2, 2, 0, 1, 2])
      and np.allclose(gg['y'], [0, 1, 2, 2, 50, 51, 52]))

gt = G['Graph'](gg)

for label, csv, exp in [
    ('TỐT', os.path.join(BASE, 'good.csv'),
     dict(recall=7 / 7, tp=5, fp=0, fn=0, ej=1.0, adj=1.0,
          dtp=1, dfp=0, dfn=0, divj=1.0, score=1.1)),
    ('XẤU', os.path.join(BASE, 'bad.csv'),
     dict(recall=7 / 7, tp=4, fp=1, fn=1, ej=4 / 6,
          adj=(4 / 6) * (1 - 0.1 * 2 / 7), dtp=0, dfp=1, dfn=1, divj=0.0,
          score=(4 / 6) * (1 - 0.1 * 2 / 7))),
]:
    graphs = G['load_submission_graphs'](csv)
    check(f'[{label}] nạp 1 graph', set(graphs) == {'synth'})
    r = G['evaluate_one'](graphs['synth'], gt)
    for k, v in exp.items():
        got = r[{'recall': 'node_recall', 'tp': 'edge_tp', 'fp': 'edge_fp',
                 'fn': 'edge_fn', 'ej': 'edge_jaccard', 'adj': 'adj_edge_jaccard',
                 'dtp': 'division_tp', 'dfp': 'division_fp', 'dfn': 'division_fn',
                 'divj': 'division_jaccard', 'score': 'score'}[k]]
        ok = abs(got - v) < 1e-9
        check(f'[{label}] {k} = {v:.4f}', ok, f'thực tế {got:.4f}')

    s = G['summarise']([dict(r, dataset='synth')])
    ok = abs(s['score'] - exp['score']) < 1e-9
    check(f'[{label}] summarise score = {exp["score"]:.4f}', ok,
          f'thực tế {s["score"]:.4f}')

print()
print('TỔNG: ' + ('ĐẠT TẤT CẢ' if not fails else f'{len(fails)} LỖI: {fails}'))
sys.exit(0 if not fails else 1)
