#!/usr/bin/env python3
"""test-wave1-replay.py — unit test local (không cần tracksdata):
  1) lắp lại replay từ file đã build bằng cách exec đúng phần cần (monkey)
  2) kịch bản synth: 1 mẹ + 2 con (1 GT division) + 1 duplicate pair
  3) kiểm tra: replay chấp nhận đúng cặp GT khi gate vừa; nới gate nhận thêm
     duplicate; P_div floor chặn duplicate; W rerank đảo thứ tự budget.
"""
from __future__ import annotations
import types
import sys
from pathlib import Path

BUILT = Path(__file__).resolve().parent / 'wave1' / 'wave1-sweep.py'
src = BUILT.read_text()

# --- tách riêng hàm wave1_replay_safe_div bằng AST (tránh import cả file) ---
import ast
tree = ast.parse(src)
wanted = {'wave1_replay_safe_div'}
mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef)
                       and n.name in wanted], type_ignores=[])
ns = {'Counter': __import__('collections').Counter}
exec(compile(mod, '<replay>', 'exec'), ns)
replay = ns['wave1_replay_safe_div']

GATES = {'SAFE_DIV_MAX_UM': 9.0, 'SAFE_DIV_SISTER_MAX_UM': 14.0,
         'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.6, 'SAFE_DIV_DIVERGE_UM': 2.25,
         'SAFE_DIV_EXISTING_CHILD_MAX_UM': 10.0, 'SAFE_DIV_FRAME_FRAC_CAP': 0.0076,
         'SAFE_DIV_GLOBAL_FRAC_CAP': 0.00375, 'DEEPCENTER_SAFE_DIV_THRESHOLD': 0.20}

# ---- kịch bản -------------------------------------------------------------
# nodes: 1=P(mẹ,t=0) đã có con 2=C1(t=1); 3=C2 mồ côi (t=1, GT-div con thứ hai)
#        4=D duplicate (t=1, rất gần C1 → mutual-NN của C1 là 4?? — đặt 4 xa hơn)
# edges: P→C1. GT: P có 2 con C1, C2.
nodes = {1: {'t': 0}, 2: {'t': 1}, 3: {'t': 1}, 4: {'t': 1}}
edges = [{'source_id': 1, 'target_id': 2}]

def feat(src_, cand_, p_d, s_d, div_m, sym, dc, gt):
    return {'stem': 'S', 't': 0, 'source_id': src_, 'candidate_id': cand_,
            'existing_child_id': 2, 'parent_dist': p_d, 'sister_dist': s_d,
            'child_dist': 5.0, 'mutual_nn': True, 'diverge_margin': div_m,
            'symmetry_ratio': sym, 'dc_score': dc, 'p_div': p_d if p_d is not None else None,
            'gt_div_edge': gt, 'gt_source': 1 if gt else None,
            'gt_candidate': cand_ if gt else None}

# cặp GT: p_div cao (0.8); cặp duplicate: p_div thấp (0.1)
feats = [feat(1, 3, 0.8, 6.0, 4.0, 0.1, 0.9, True),    # C2 — division thật
         feat(1, 4, 0.1, 3.0, 3.0, 0.2, 0.9, False)]   # D — duplicate

fails = []

def check(name, cond, extra=''):
    print(f"[{'PASS' if cond else 'FAIL'}] {name} {extra}")
    if not cond:
        fails.append(name)

# 1) gate production: cả 2 cặp đều vượt gate → mutual-NN? CẢ HAI đều mutual_nn=True
#    trong test (giả lập) → cả 2 vào proposals; rank geometry:
#    GT: 6.0+0.15*4.0=6.6 ; dup: 3.0+0.15*3.0=3.45 → dup thắng → nhận dup (đúng
#    triệu chứng megayak: budget tiêu vào duplicate!)
added, st = replay(feats, edges, GATES, None, nodes)
check('production nhận 1 cạnh (frame_cap=1)', len(added) == 1, f"added={added}")
check('production chọn DUPLICATE (geometry rank)', added[0]['target_id'] == 4,
      f"target={added[0]['target_id']}")

# 2) rank với W=15: GT: 6.6-15*0.8=-5.4 ; dup: 3.45-15*0.1=1.95 → GT thắng
added, st = replay(feats, edges, GATES, (15.0, None), nodes)
check('divnet W15 đảo rank → nhận GT', added and added[0]['target_id'] == 3,
      f"added={[(a['source_id'], a['target_id']) for a in added]}")

# 3) P_div floor 0.5 chặn duplicate: floor=0.5 loại cặp p_div=0.1
added, st = replay(feats, edges, GATES, (15.0, 0.5), nodes)
check('pdiv floor 0.5 loại duplicate', all(a['target_id'] != 4 for a in added)
      and len(added) == 1, f"added={[(a['source_id'], a['target_id']) for a in added]}")

# 4) gate khắt khe (diverge 10.0) → không cạnh nào qua
tight = dict(GATES, SAFE_DIV_DIVERGE_UM=10.0)
added, st = replay(feats, edges, tight, None, nodes)
check('gate diverge chặt → 0 cạnh', len(added) == 0)

# 5) global cap: 1 cạnh * 0.00375 → round(0.00375)=0 → max(1, 0)=1... đúng
#    frame_cap: 1 nguồn * 0.0076 → 1. Kiểm tra cap_skipped khi 2 nguồn
feats2 = [feat(1, 3, 0.8, 6.0, 4.0, 0.1, 0.9, True),
          feat(5, 6, 0.8, 6.0, 4.0, 0.1, 0.9, False)]
nodes2 = {1: {'t': 0}, 2: {'t': 1}, 3: {'t': 1}, 4: {'t': 1},
          5: {'t': 0}, 6: {'t': 1}, 7: {'t': 1}}
edges2 = [{'source_id': 1, 'target_id': 2}, {'source_id': 5, 'target_id': 7}]
added, st = replay(feats2, edges2, dict(GATES, SAFE_DIV_GLOBAL_FRAC_CAP=0.06), None, nodes2)
# global cap = round(2*0.06)=0 → max(1,0)=1 → chỉ 1 cạnh
check('global cap 1 cạnh khi frac=0.06x2 cạnh', len(added) == 1,
      f"added={[(a['source_id'], a['target_id']) for a in added]}")

# 6) diverge_margin None → bị loại khi REQUIRE_DIVERGENCE (g_diverge>0)
feats3 = [feat(1, 3, 0.8, 6.0, None, 0.1, 0.9, True)]
added, st = replay(feats3, edges, GATES, None, nodes)
check('diverge None → loại', len(added) == 0)

# 7) dc_score < threshold → loại
feats4 = [feat(1, 3, 0.8, 6.0, 4.0, 0.1, 0.05, True)]
added, st = replay(feats4, edges, GATES, None, nodes)
check('dc thấp → loại', len(added) == 0)

# 8) symmetry > tau → loại
feats5 = [feat(1, 3, 0.8, 6.0, 4.0, 0.9, 0.9, True)]
added, st = replay(feats5, edges, GATES, None, nodes)
check('symmetry cao → loại', len(added) == 0)

# 9) frame budget: 2 nguồn, frame_frac=0.0076*2→round(0.03)=0→1 cạnh/khung
added, st = replay(feats2, edges2, GATES, None, nodes2)
check('frame cap 1 cạnh', len(added) == 1)

print()
if fails:
    print('THẤT BẠI:', fails)
    sys.exit(1)
print('ALL PASS — replay logic đúng thiết kế.')
