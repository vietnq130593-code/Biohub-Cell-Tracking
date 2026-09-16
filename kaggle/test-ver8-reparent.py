#!/usr/bin/env python3
"""test-ver8-reparent.py — unit test add_reparent_divisions_postlink (ver-8).

Trích hàm qua AST từ ver-8/cell-monolith.py, mock dependencies (divnet bundle,
deepcenter, np). Kịch bản:
  1. Re-parent cơ bản: mẹ M(D1) + D2 có cạnh YẾU Y→D2 + P_div(M) cao
     → REMOVE Y→D2, ADD M→D2 (topology: M 2 con, D2 1 cha)
  2. Cạnh hiện tại MẠNH (prob cao + gần) → KHÔNG re-parent
  3. P_div(M) thấp → KHÔNG (gate divnet chặn)
  4. Mẹ quá xa (MAX_UM) → KHÔNG
  5. Thiếu divergence (cháu không tách) → KHÔNG
  6. Budget: global cap chặn
  7. Đối xứng tệ (tau) → KHÔNG
  8. DeepCenter veto → KHÔNG
"""
from __future__ import annotations
import ast
import sys
from pathlib import Path

MONO = Path(__file__).resolve().parent / 'ver-8' / 'cell-monolith.py'
src = MONO.read_text()
tree = ast.parse(src)
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
          and n.name == 'add_reparent_divisions_postlink')
mod = ast.Module(body=[fn], type_ignores=[])

# --- mock môi trường module -----------------------------------------------
VOXEL = (1.625, 0.40625, 0.40625)

def edge_distance_um(a, b):
    dz = (float(a['z']) - float(b['z'])) * VOXEL[0]
    dy = (float(a['y']) - float(b['y'])) * VOXEL[1]
    dx = (float(a['x']) - float(b['x'])) * VOXEL[2]
    return (dz * dz + dy * dy + dx * dx) ** 0.5

def node_point(n):
    return (float(n['z']), float(n['y']), float(n['x']))

DIVNET_PROBS = {}   # (t, round(z,3)) -> p_div
_divnet_qkey = lambda q: (int(q[0]), round(float(q[1]), 3))

def _divnet_score_queries(bundle, dataset, queries, frame_cache, t_lo, t_hi):
    return [DIVNET_PROBS.get(_divnet_qkey(q), 0.1) for q in queries]  # mặc định thấp

DC_VETO = {}        # node_id -> True (veto) / False (chấp)
DC_CALLS = []
def deepcenter_accept_repair_point(dataset, t, point, bundle, fc, dc, stats, prefix, threshold):
    DC_CALLS.append((t, point, prefix))
    # tra theo z,y,x point
    key = (round(point[0], 3), round(point[1], 3), round(point[2], 3))
    return not DC_VETO.get(key, False)

import types
np_mock = types.SimpleNamespace(ndarray=object)

ns = {
    'REPARENT_ENABLE': True,
    'REPARENT_MAX_UM': 12.0,
    'REPARENT_SISTER_UM': 16.0,
    'REPARENT_TAU': 1.0,
    'REPARENT_EDGE_PROB': 0.35,
    'REPARENT_CURRENT_FAR_UM': 7.5,
    'REPARENT_MIN_PDIV': 0.3,
    'REPARENT_W_UM': 15.0,
    'REPARENT_DIVERGE_UM': 2.25,
    'REPARENT_REQUIRE_DIVERGENCE': True,
    'REPARENT_FRAME_FRAC_CAP': 0.0076,
    'REPARENT_GLOBAL_FRAC_CAP': 0.00375,
    'DEEPCENTER_SAFE_DIV_VETO': True,
    'DEEPCENTER_SAFE_DIV_THRESHOLD': 0.20,
    'edge_distance_um': edge_distance_um,
    'node_point': node_point,
    '_divnet_score_queries': _divnet_score_queries,
    'deepcenter_accept_repair_point': deepcenter_accept_repair_point,
    'np': np_mock,
}
exec(compile(mod, '<reparent>', 'exec'), ns)
reparent = ns['add_reparent_divisions_postlink']

# --- dựng world: z/Y/X theo voxel (đặt toạ độ voxel để µm dễ tính) ----------
# M(t=0) ở gốc; D1(t=1) cách M 3µm theo z; D2(t=1) cách M 5µm z, cách D1 8µm
# Y(t=0) ở xa (z=8µm từ D2 → current edge dài 8 ≥ 7.5 = YẾU)
def node(nid, t, z, y=0.0, x=0.0):
    return {'node_id': nid, 't': t, 'z': z, 'y': y, 'x': x}

M, D1, D2, Y = 1, 2, 3, 4
G1, G2 = 5, 6  # grandchildren của D1, D2 (t=2) — tách nhau 12µm
nodes = {
    M: node(M, 0, 0.0),
    D1: node(D1, 1, 3.0 / 1.625),          # 3µm theo z
    D2: node(D2, 1, 5.0 / 1.625),          # 5µm theo z (cách D1 2µm)
    Y: node(Y, 0, 5.0 / 1.625 + 8.0 / 1.625),  # Y→D2 dài 8µm (far ≥ 7.5)
    G1: node(G1, 2, 3.0 / 1.625),          # D1 tiếp tục thẳng
    G2: node(G2, 2, 5.0 / 1.625 + 7.0 / 1.625),  # cháu D2 tách xa
}
# G1↔G2: |3 - 12| = 9µm? tính: G1 z=3µm, G2 z=12µm → 9µm; sister D1↔D2 = 2µm
# → diverge margin = 9 - 2 = 7 ≥ 2.25 ✓
edges = [
    {'source_id': M, 'target_id': D1, 'edge_prob': 0.9, 'distance_um': 3.0},
    {'source_id': Y, 'target_id': D2, 'edge_prob': 0.1, 'distance_um': 8.0},
    {'source_id': D1, 'target_id': G1, 'edge_prob': 0.9, 'distance_um': 1.0},
    {'source_id': D2, 'target_id': G2, 'edge_prob': 0.9, 'distance_um': 7.0},
]
DIVNET_PROBS.clear(); DIVNET_PROBS[(0, 0.0)] = 0.9  # M: t=0, z=0
DC_VETO.clear()

fails = []
def check(name, cond, extra=''):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

# 1) re-parent cơ bản
stats = {k: 0 for k in ('reparent_candidates', 'reparent_added', 'reparent_skipped_cap',
                        'reparent_dist_rejected', 'reparent_symmetry_rejected',
                        'reparent_divergence_rejected', 'reparent_deepcenter_rejected',
                        'reparent_pdiv_rejected')}
out = reparent(nodes, [dict(e) for e in edges], stats, dataset='S', divnet_bundle={'mock': 1})
pairs = {(int(e['source_id']), int(e['target_id'])) for e in out}
check('re-parent cơ bản: thêm M→D2', (M, D2) in pairs)
check('re-parent cơ bản: xoá Y→D2', (Y, D2) not in pairs)
check('giữ các cạnh khác', (M, D1) in pairs and (D1, G1) in pairs and (D2, G2) in pairs)
check('stats added=1', stats['reparent_added'] == 1, f"stats={stats}")
# topology: M có 2 con, D2 có 1 cha
out_by_src = {}
in_deg = {}
for e in out:
    out_by_src.setdefault(int(e['source_id']), []).append(int(e['target_id']))
    in_deg[int(e['target_id'])] = in_deg.get(int(e['target_id']), 0) + 1
check('M có đúng 2 con', len(out_by_src.get(M, [])) == 2)
check('D2 có đúng 1 cha', in_deg.get(D2, 0) == 1)

# 2) cạnh hiện tại MẠNH → không re-parent
strong = [dict(e) for e in edges]
strong[1] = {'source_id': Y, 'target_id': D2, 'edge_prob': 0.9, 'distance_um': 2.0}
stats2 = dict(stats); stats2.update({k: 0 for k in stats})
out2 = reparent(nodes, strong, stats2, dataset='S', divnet_bundle={'mock': 1})
pairs2 = {(int(e['source_id']), int(e['target_id'])) for e in out2}
check('cạnh mạnh → KHÔNG re-parent', (M, D2) not in pairs2 and (Y, D2) in pairs2)

# 3) P_div(M) thấp → không
DIVNET_PROBS[M] = 0.05
DIVNET_PROBS[(0, 0.0)] = 0.05
stats3 = dict(stats); stats3.update({k: 0 for k in stats})
out3 = reparent(nodes, [dict(e) for e in edges], stats3, dataset='S', divnet_bundle={'mock': 1})
pairs3 = {(int(e['source_id']), int(e['target_id'])) for e in out3}
check('p_div thấp → KHÔNG re-parent', (M, D2) not in pairs3)
check('stats pdiv_rejected ≥ 1', stats3['reparent_pdiv_rejected'] >= 1)
DIVNET_PROBS[M] = 0.9
DIVNET_PROBS[(0, 0.0)] = 0.9

# 4) mẹ quá xa: D2 cách M 15µm
nodes_far = dict(nodes)
nodes_far[D2] = node(D2, 1, 15.0 / 1.625)
edges_far = [dict(e) for e in edges]
edges_far[1] = {'source_id': Y, 'target_id': D2, 'edge_prob': 0.1, 'distance_um': 8.0}
stats4 = dict(stats); stats4.update({k: 0 for k in stats})
out4 = reparent(nodes_far, edges_far, stats4, dataset='S', divnet_bundle={'mock': 1})
pairs4 = {(int(e['source_id']), int(e['target_id'])) for e in out4}
check('mẹ 15µm → KHÔNG re-parent', (M, D2) not in pairs4)
check('stats dist_rejected ≥ 1', stats4['reparent_dist_rejected'] >= 1)

# 5) thiếu divergence: D2 không có cháu
edges_nodiv = [e for e in edges if e['source_id'] != D2]
stats5 = dict(stats); stats5.update({k: 0 for k in stats})
out5 = reparent(nodes, edges_nodiv, stats5, dataset='S', divnet_bundle={'mock': 1})
pairs5 = {(int(e['source_id']), int(e['target_id'])) for e in out5}
check('không divergence → KHÔNG re-parent', (M, D2) not in pairs5)
check('stats divergence_rejected ≥ 1', stats5['reparent_divergence_rejected'] >= 1)

# 6) symmetry quá lệch: tau gate
ns['REPARENT_TAU'] = 0.3   # siết
stats6 = dict(stats); stats6.update({k: 0 for k in stats})
out6 = ns['add_reparent_divisions_postlink'](nodes, [dict(e) for e in edges], stats6, dataset='S', divnet_bundle={'mock': 1})
pairs6 = {(int(e['source_id']), int(e['target_id'])) for e in out6}
check('tau 0.3 siết → KHÔNG (child 3 vs parent 5µm, ratio 0.5)', (M, D2) not in pairs6)
ns['REPARENT_TAU'] = 1.0

# 7) DeepCenter veto D2
DC_VETO[(round(float(nodes[D2]['z']), 3), 0.0, 0.0)] = True
stats7 = dict(stats); stats7.update({k: 0 for k in stats})
out7 = ns['add_reparent_divisions_postlink'](nodes, [dict(e) for e in edges], stats7, dataset='S', divnet_bundle={'mock': 1})
pairs7 = {(int(e['source_id']), int(e['target_id'])) for e in out7}
check('DeepCenter veto D2 → KHÔNG re-parent', (M, D2) not in pairs7)
check('stats dc_rejected ≥ 1', stats7['reparent_deepcenter_rejected'] >= 1)
DC_VETO.clear()

# 8) budget: global cap = round(4 × 0.00375) = 0 → max(1, 0) = 1 cạnh — thêm 2 mẹ
M2, D1b, D2b, Y2 = 11, 12, 13, 14
G1b, G2b = 15, 16
nodes2 = dict(nodes)
nodes2.update({
    M2: node(M2, 0, 100.0), D1b: node(D1b, 1, 100.0 + 3.0 / 1.625),
    D2b: node(D2b, 1, 100.0 + 5.0 / 1.625),
    Y2: node(Y2, 0, 100.0 + 13.0 / 1.625),
    G1b: node(G1b, 2, 100.0 + 3.0 / 1.625),
    G2b: node(G2b, 2, 100.0 + 12.0 / 1.625),
})
edges2 = edges + [
    {'source_id': M2, 'target_id': D1b, 'edge_prob': 0.9, 'distance_um': 3.0},
    {'source_id': Y2, 'target_id': D2b, 'edge_prob': 0.1, 'distance_um': 8.0},
    {'source_id': D1b, 'target_id': G1b, 'edge_prob': 0.9, 'distance_um': 1.0},
    {'source_id': D2b, 'target_id': G2b, 'edge_prob': 0.9, 'distance_um': 7.0},
]
DIVNET_PROBS[M2] = 0.95
DIVNET_PROBS[(0, 100.0)] = 0.95
stats8 = dict(stats); stats8.update({k: 0 for k in stats})
out8 = ns['add_reparent_divisions_postlink'](nodes2, [dict(e) for e in edges2], stats8, dataset='S', divnet_bundle={'mock': 1})
pairs8 = {(int(e['source_id']), int(e['target_id'])) for e in out8}
n_rp = sum(1 for (s, t) in pairs8 if (s, t) in {(M, D2), (M2, D2b)})
check('global cap: đúng 1 re-parent trong 2 ứng viên', n_rp == 1,
      f"added pairs: {sorted(p for p in pairs8 if p in {(M, D2), (M2, D2b)})}")

print()
if fails:
    print('THẤT BẠI:', fails)
    sys.exit(1)
print('ALL PASS — re-parent đúng thiết kế.')
