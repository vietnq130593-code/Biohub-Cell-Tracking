#!/usr/bin/env python3
"""fp-anatomy2.py — Phân tích giải phẫu TOÀN BỘ division FP (semantics chính thức
evaluate_divisions của scorer2code) trên output v12.1 RUN 2 (0 GPU).

FP_forks = (considered ∪ evaluable_forks ∪ invalid_forks) − pairing.values()
  - evaluable_forks : fork khớp node GT có out-degree >= 1 (kể cả track tuyến tính)
  - considered      : fork cục bộ quanh sự kiện division GT nhưng không được pair TP
  - invalid_forks   : cross_component (2 nhánh vào 2 GT-component khác nhau) hoặc
                      malformed (con có >1 cha / grandchildren sai cấu trúc)

Mục tiêu: anatomy từng FP (khoảng cách cha-con, sister, divergence, symmetry,
GT context) + đối chiếu TP t=24 05db → tìm separator hình học cho v12.2 khả dĩ.
"""
from __future__ import annotations
import sys
import csv as _csv
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'ver-12'))

import numpy as np

_ns = {'__name__': 'scorer2code'}
exec('import itertools\nimport json\nimport os\nimport blosc2\nimport numpy as np\n'
     'import pandas as pd\nfrom scipy.optimize import linear_sum_assignment\n'
     'MAX_DISTANCE = 7.0\nSCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)\n'
     'ADJUSTMENT_ALPHA = 0.1\nSCORE_DIVISION_WEIGHT = 0.1\n', _ns)
exec((HERE.parent / 'scorer' / 'scorer2code.py').read_text(), _ns)
Graph = _ns['Graph']
load_submission_graphs = _ns['load_submission_graphs']
match_nodes = _ns['match_nodes']
_extract_divisions = _ns['_extract_divisions']
_branch_component_evidence = _ns['_branch_component_evidence']
_gt_weak_components = _ns['_gt_weak_components']
_bipartite_max_matching = _ns['_bipartite_max_matching']
_is_strongly_connected = _ns['_is_strongly_connected']

from v12lab import read_gt_graph, TEST_STEMS

SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)


def anatomy(csv_path: str) -> None:
    preds = load_submission_graphs(csv_path)
    print(f'=== FP ANATOMY v2 (semantics chính thức): {csv_path} ===')
    grand_total = {'tp': 0, 'fp': 0, 'fn': 0}
    for stem in TEST_STEMS:
        if stem not in preds:
            continue
        pred = preds[stem]
        gt_raw = read_gt_graph(stem)
        gt = Graph(gt_raw)
        pred_div_nodes = set(pred.dividing_nodes())
        full_match = match_nodes(pred, gt, 7.0)

        # map internal pred idx -> gốc node_id (thứ tự load_submission_graphs = CSV)
        nodes: dict[int, dict] = {}
        edges: list[tuple[int, int]] = []
        with open(csv_path) as fh:
            for row in _csv.DictReader(fh):
                if row['dataset'] != stem:
                    continue
                nid = int(row['node_id'])
                if row['row_type'] == 'node':
                    nodes[nid] = {'t': int(row['t']), 'z': float(row['z']),
                                  'y': float(row['y']), 'x': float(row['x'])}
                else:
                    edges.append((int(row['source_id']), int(row['target_id'])))
        pred_ids = list(nodes.keys())
        idx2orig = pred_ids  # internal idx i -> gốc id
        gt_ids = list(map(int, gt_raw['ids']))
        gt_out = {}
        for s, d in gt_raw['edges']:
            gt_out.setdefault(int(s), set()).add(int(d))

        def um(a: dict, b: dict) -> float:
            pa = np.array([a['z'], a['y'], a['x']]) * SCALE
            pb = np.array([b['z'], b['y'], b['x']]) * SCALE
            return float(np.linalg.norm(pa - pb))

        # ---- chạy lại đúng evaluate_divisions nhưng giữ chi tiết ----
        divs = _extract_divisions(gt)
        evaluable_forks = {p for p in pred_div_nodes
                           if p in full_match and gt.out_deg.get(full_match[p], 0) >= 1}
        gt_comp = _gt_weak_components(gt)
        cross_component, malformed = set(), set()
        for p in pred_div_nodes:
            branch_evidence = []
            broke = False
            for child in pred.successors(p):
                comp, bad = _branch_component_evidence(pred, p, child, full_match, gt_comp)
                if bad:
                    malformed.add(p)
                    broke = True
                    break
                if comp is not None:
                    branch_evidence.append(comp)
            if not broke and len(set(branch_evidence)) >= 2:
                cross_component.add(p)
        invalid_forks = cross_component | malformed

        candidates = {}
        considered = set()
        for div, info in divs.items():
            m = match_nodes(pred, gt, 7.0, gt_subset=info['keep'])
            node_to_gt = {p: g for p, g in m.items()}
            children = info['children']
            if len(children) < 2:
                candidates[div] = set()
                continue
            parent_side = {div, *info['parents']}
            parent_ids = {p for p, g in node_to_gt.items() if g in parent_side}
            daughter_ids = [{p for p, g in node_to_gt.items() if g in {c, *gt.successors(c)}}
                            for c in children]
            if not parent_ids or sum(bool(x) for x in daughter_ids) < 2:
                candidates[div] = set()
                continue
            local_nodes = set(parent_ids)
            for p in list(parent_ids):
                local_nodes.update(pred.successors(p))
            local_forks = local_nodes & pred_div_nodes
            considered |= local_forks
            candidates[div] = {f for f in local_forks - invalid_forks
                               if _is_strongly_connected(pred, f, parent_ids, daughter_ids)}

        pairing = _bipartite_max_matching(list(candidates), candidates)
        tp = sum(1 for d in candidates if d in pairing)
        fn = len(candidates) - tp
        fp_forks = (considered | evaluable_forks | invalid_forks) - set(pairing.values())
        grand_total['tp'] += tp
        grand_total['fp'] += len(fp_forks)
        grand_total['fn'] += fn
        print(f'\n[{stem}] div TP/FN/FP = {tp}/{fn}/{len(fp_forks)} | pred forks tổng: {len(pred_div_nodes)}')

        def tag(p: int) -> str:
            tags = []
            if p in evaluable_forks:
                tags.append('EVAL')
            if p in considered:
                tags.append('CONSID')
            if p in cross_component:
                tags.append('CROSS')
            if p in malformed:
                tags.append('MALF')
            return '+'.join(tags) or 'NONE'

        # anatomy từng FP fork
        for p in sorted(fp_forks, key=lambda x: pred.t[x]):
            n_orig = idx2orig[p]
            nd = nodes[n_orig]
            kids_idx = pred.successors(p)[:2]
            kid_origs = [idx2orig[k] for k in kids_idx]
            kids = [nodes[k] for k in kid_origs]
            g = full_match.get(p)
            g_gt = int(gt_ids[g]) if g is not None else None
            g_outdeg = len(gt_out.get(g_gt, ())) if g_gt is not None else None
            sister = um(kids[0], kids[1]) if len(kids) == 2 else float('nan')
            p1 = um(nd, kids[0]) if kids else float('nan')
            p2 = um(nd, kids[1]) if len(kids) > 1 else float('nan')
            sym = abs(p1 - p2) / max((p1 + p2) / 2.0, 1e-6)
            out_orig: dict[int, list[int]] = {}
            for s, d in edges:
                out_orig.setdefault(s, []).append(d)
            div = None
            succs = []
            ok = True
            for ko in kid_origs:
                so = out_orig.get(ko, [])
                if len(so) != 1:
                    ok = False
                    break
                succs.append(nodes[so[0]])
            if ok and len(succs) == 2:
                gc = um(succs[0], succs[1])
                # đúng t+2?
                t2s = [out_orig[ko][0] for ko in kid_origs]
                if all(nodes[t2]['t'] == nd['t'] + 2 for t2 in t2s):
                    div = gc - sister
            # in-deg children (malformed check hiển thị)
            in_deg: dict[int, int] = {}
            for s, d in edges:
                in_deg[d] = in_deg.get(d, 0) + 1
            indegs = [in_deg.get(ko, 0) for ko in kid_origs]
            print(f"  FP t={nd['t']:>3} fork={n_orig} [{tag(p)}] gt={g_gt} gt_out={g_outdeg}"
                  f" | p1={p1:.2f} p2={p2:.2f} sister={sister:.2f}µm sym={sym:.3f}"
                  f" divergence={(f'{div:.2f}' if div is not None else 'n/a')}"
                  f" child_indeg={indegs}")

        # anatomy TP nếu có
        for div, paired_fork in pairing.items():
            p = paired_fork
            n_orig = idx2orig[p]
            nd = nodes[n_orig]
            kids_idx = pred.successors(p)[:2]
            kid_origs = [idx2orig[k] for k in kids_idx]
            kids = [nodes[k] for k in kid_origs]
            sister = um(kids[0], kids[1])
            p1 = um(nd, kids[0])
            p2 = um(nd, kids[1])
            sym = abs(p1 - p2) / max((p1 + p2) / 2.0, 1e-6)
            out_orig: dict[int, list[int]] = {}
            for s, d in edges:
                out_orig.setdefault(s, []).append(d)
            div_val = None
            succs = []
            ok = True
            for ko in kid_origs:
                so = out_orig.get(ko, [])
                if len(so) != 1:
                    ok = False
                    break
                succs.append(nodes[so[0]])
            if ok and len(succs) == 2 and all(nodes[out_orig[ko][0]]['t'] == nd['t'] + 2 for ko in kid_origs):
                div_val = um(succs[0], succs[1]) - sister
            print(f"  TP t={nd['t']:>3} fork={n_orig} (GT div {int(gt_ids[div])})"
                  f" | p1={p1:.2f} p2={p2:.2f} sister={sister:.2f}µm sym={sym:.3f}"
                  f" divergence={(f'{div_val:.2f}' if div_val is not None else 'n/a')}")

    print(f"\nTOTAL TP/FP/FN = {grand_total['tp']}/{grand_total['fp']}/{grand_total['fn']} → divJ = "
          f"{grand_total['tp'] / max(1, grand_total['tp'] + grand_total['fp'] + grand_total['fn']):.4f}")


if __name__ == '__main__':
    anatomy(sys.argv[1] if len(sys.argv) > 1 else '/home/z/Biohub-Cell-Tracking/kaggle/api/output/latest/submission.csv')
