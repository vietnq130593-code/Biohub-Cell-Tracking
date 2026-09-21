#!/usr/bin/env python3
"""fp-anatomy.py — Phân tích giải phẫu các division FP của output v12.1 RUN 2
trên cửa sổ GT replica (0 GPU). Mục tiêu: tìm separator hình học tách FP khỏi TP
(t=24 05db) — quyết định có đáng làm v12.2 (production run thứ 3) hay không.

Semantics FP (compute_division_confusion monolith): fork pred (out-degree>=2) khớp
node GT g, g CÓ cạnh ra (gt_out), và g không phải TP-source → FP. Tức fork rơi vào
vị trí GT nói "không chia" (track tuyến tính / 1 con).
"""
from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'ver-12'))

import numpy as np

# ---- engine scorer2code (verify 100% receipt alfonso) ----
_ns = {'__name__': 'scorer2code'}
exec('import itertools\nimport json\nimport os\nimport blosc2\nimport numpy as np\n'
     'import pandas as pd\nfrom scipy.optimize import linear_sum_assignment\n'
     'MAX_DISTANCE = 7.0\nSCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)\n'
     'ADJUSTMENT_ALPHA = 0.1\nSCORE_DIVISION_WEIGHT = 0.1\n', _ns)
exec((HERE.parent / 'scorer' / 'scorer2code.py').read_text(), _ns)
Graph = _ns['Graph']
load_submission_graphs = _ns['load_submission_graphs']
match_nodes = _ns['match_nodes']

from v12lab import read_gt_graph, TEST_STEMS

SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)


def pos_um(g: Graph, i: int) -> np.ndarray:
    return g.pos[i]


def anatomy(csv_path: str) -> None:
    preds = load_submission_graphs(csv_path)
    print(f'=== FP ANATOMY: {csv_path} ===')
    for stem in TEST_STEMS:
        if stem not in preds:
            continue
        pred = preds[stem]
        gt = Graph(read_gt_graph(stem))
        p2g = match_nodes(pred, gt)

        # độ ra theo node gốc
        out_by: dict[int, list[int]] = {}
        in_deg: dict[int, int] = {}
        # cần map node gốc -> internal idx: pred.edges đã là internal idx
        # internal idx -> node gốc (đảo id2idx): dùng pos/t trực tiếp theo thứ tự file
        # load_submission_graphs giữ ids gốc trong g['ids'] — truy cập qua pred internal
        # đơn giản: rebuild từ graph dict
        # (Graph chỉ giữ idx — nhưng p2g key là idx; cần gốc id cho báo cáo)
        # → đọc lại dict gốc:
        # HACK: dùng _ns['csv_to_graphs'] internals — load_submission_graphs trả Graph;
        #   nên tự rebuild map từ CSV luôn cho id gốc.
        import csv as _csv
        nodes: dict[int, dict] = {}
        edges: list[tuple[int, int]] = []
        stem_prefix = stem
        with open(csv_path) as fh:
            for row in _csv.DictReader(fh):
                if row['dataset'] != stem_prefix:
                    continue
                nid = int(row['node_id'])
                if row['row_type'] == 'node':
                    nodes[nid] = {'t': int(row['t']), 'z': float(row['z']),
                                  'y': float(row['y']), 'x': float(row['x'])}
                else:
                    edges.append((int(row['source_id']), int(row['target_id'])))
        out_orig: dict[int, list[int]] = {}
        gt_out: dict[int, set[int]] = {}
        # GT out-degree theo id gốc GT
        gt_ids = read_gt_graph(stem)['ids']
        gt_edges = read_gt_graph(stem)['edges']
        for s, d in gt_edges:
            gt_out.setdefault(int(s), set()).add(int(d))
        for s, d in edges:
            out_orig.setdefault(s, []).append(d)
        # p2g: internal idx -> gt internal idx; cần gốc id:_pred pos theo thứ tự đọc
        # (Graph remap theo id2idx của g['ids'] — cùng thứ tự dict). Dùng bảng gốc:
        pred_ids = list(nodes.keys())  # thứ tự CSV — Graph cũng build từ cùng dict
        # an toàn: khớp lại bằng (t, pos) — nhưng internal của Graph = thứ tự g['ids']
        # load_submission_graphs nội bộ đọc CSV theo cùng thứ tự → pred_ids[i] = id gốc idx i
        idx2orig = pred_ids

        # độ vào pred
        in_orig: dict[int, int] = {}
        for s, d in edges:
            in_orig[d] = in_orig.get(d, 0) + 1

        def um(a: dict, b: dict) -> float:
            pa = np.array([a['z'], a['y'], a['x']]) * SCALE
            pb = np.array([b['z'], b['y'], b['x']]) * SCALE
            return float(np.linalg.norm(pa - pb))

        # --- enumerate forks ---
        events = []
        for n, outs in out_orig.items():
            if len(outs) < 2:
                continue
            g = p2g.get(n)
            g_gt_id = None
            if g is not None:
                # gt internal idx -> gốc id
                g_gt_id = int(gt_ids[g])
            # phân loại theo semantics compute_division_confusion:
            if g is None or int(g_gt_id) not in gt_out:
                kind = 'ignored (fork khớp node GT không-cạnh-ra hoặc không khớp)'
                continue
            # TP/FN check: fork này có thoả lineage TP không? đơn giản hoá: fork được
            # tính TP nếu nó là anchor của 1 GT division TP; ở đây đánh dấu theo đếm
            # tổng đã biết từ replica (TP ít) — cứ liệt kê tất cả fork-on-GT-out.
            kind = 'FP-or-TP (fork trên node GT có cạnh ra)'
            nd = nodes[n]
            kids = [nodes[k] for k in outs[:2]]
            kid_ids = list(outs[:2])
            sister = um(kids[0], kids[1])
            p1 = um(nd, kids[0])
            p2 = um(nd, kids[1])
            sym = abs(p1 - p2) / max((p1 + p2) / 2.0, 1e-6)
            # divergence: d(successor của 2 con ở t+2) − sister
            div = None
            succ_pair = []
            for kid_id in kid_ids:
                so = out_orig.get(kid_id, [])
                succ_pair.append(nodes[so[0]] if len(so) >= 1 else None)
            if succ_pair[0] and succ_pair[1]:
                gc = um(succ_pair[0], succ_pair[1])
                div = gc - sister
            # GT continuation: con GT của node g
            gt_kids = sorted(gt_out[int(g_gt_id)]) if int(g_gt_id) in gt_out else []
            events.append({
                'fork': n, 't': nd['t'], 'gt_node': int(g_gt_id),
                'gt_outdeg': len(gt_kids), 'kids': kid_ids,
                'p1': round(p1, 2), 'p2': round(p2, 2),
                'sister': round(sister, 2), 'sym': round(sym, 3),
                'divergence': (round(div, 2) if div is not None else None),
                'gt_kids': len(gt_kids),
            })
        print(f'\n[{stem}] forks trên node-GT-có-cạnh-ra: {len(events)} (TP mong đợi ở 05db)')
        for ev in events:
            print(f"  t={ev['t']:>3} fork={ev['fork']} gt_node={ev['gt_node']} gt_outdeg={ev['gt_kids']} "
                  f"| p1={ev['p1']}µm p2={ev['p2']}µm sister={ev['sister']}µm sym={ev['sym']} "
                  f"divergence={ev['divergence']}")


if __name__ == '__main__':
    anatomy(sys.argv[1] if len(sys.argv) > 1 else '/home/z/Biohub-Cell-Tracking/kaggle/api/output/latest/submission.csv')
