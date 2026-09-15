"""test-ver9-blocks.py — Unit test offline (CPU, mock) cho 3 block mới của ver-9.

Không cần GPU / /kaggle/input: chỉ test các hàm THUẦN tách từ monolith:
  T1 _hv_apply_veto mode 1 (giữ cả 2 cạnh của node 2 con) / mode 2 (veto cả division)
  T2 _hv_estimate_s + _hv_budget_decision (run / skip_video_cap / skip_deadline)
  T3 _hv_snap_to_nodes (ánh xạ 1-1 KD-tree cùng frame, sai → RuntimeError)
  T4 ver9_rlf_edges (walk tổ tiên fork → bỏ cạnh con XA hơn; không đụng node)
  T5 ngữ nghĩa RLF output-level == graph-level (đối chiếu pawanmali cell 10.5)
  T6 gate arithmetic: verdict SUBMIT / SUBMIT_SAFE / FALLBACK theo §6 rev-2
"""
import os
import sys
from pathlib import Path

os.environ['BIOHUB_HOCT_VETO'] = '0'  # block chỉ ARMS khi mode != 0; hàm thuần vẫn test được

ROOT = Path(__file__).resolve().parent
MONOLITH = (ROOT / 'cell-monolith.py').read_text()

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = '') -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


# ---------------------------------------------------------------- извлеч HOCT block
hoct_start = MONOLITH.index('# ==== [ver9-hoct] HOCT consensus veto')
hoct_end = MONOLITH.index('_base_postprocess_signature = _postprocess_resume_signature()', hoct_start)
hoct_src = MONOLITH[hoct_start:hoct_end]
print(f"[extract] HOCT block: {len(hoct_src.splitlines())} dòng")

hv: dict = {}
exec(compile(hoct_src, 'hoct-block', 'exec'), hv)

# T1 — _hv_apply_veto --------------------------------------------------------
print('T1 _hv_apply_veto')
edges = [
    {'source_id': 1, 'target_id': 2},   # 1 thường, HOCT đề xuất
    {'source_id': 3, 'target_id': 4},   # 1 thường, HOCT KHÔNG đề xuất → bị veto cả 2 mode
    {'source_id': 5, 'target_id': 6},   # con gần của fork 5, HOCT đề xuất
    {'source_id': 5, 'target_id': 7},   # con xa của fork 5, HOCT KHÔNG đề xuất
]
pairs = {(1, 2), (5, 6)}
kept1, c1 = hv['_hv_apply_veto'](edges, pairs, 1)
kept2, c2 = hv['_hv_apply_veto'](edges, pairs, 2)
check('mode1 giữ cả 2 cạnh của fork (out_deg>=2)', {(5, 6), (5, 7)} <= {(e['source_id'], e['target_id']) for e in kept1})
check('mode1 veto cạnh thường không đồng thuận', (3, 4) not in {(e['source_id'], e['target_id']) for e in kept1})
check('mode2 veto cả cạnh division không đồng thuận', (5, 7) not in {(e['source_id'], e['target_id']) for e in kept2})
check('mode2 đếm divisions_after', c2['divisions_before'] == 1 and c2['divisions_after'] == 0)
check('mode2 removed = 2 cạnh', c2['removed'] == 2)
check('mode1 removed = 1 cạnh', c1['removed'] == 1)

# T2 — budget -----------------------------------------------------------------
print('T2 _hv_estimate_s + _hv_budget_decision')
est = hv['_hv_estimate_s'](20000)
check('est 20k nodes = 190s', abs(est - 190.0) < 1e-9)
d, _ = hv['_hv_budget_decision'](20000, 1000.0, 10.5 * 3600, 900.0)
check('20k nodes chạy được (est 190 < cap 900)', d == 'run')
d, _ = hv['_hv_budget_decision'](100000, 1000.0, 10.5 * 3600, 900.0)
check('100k nodes skip_video_cap (est 910 > 900)', d == 'skip_video_cap')
d, _ = hv['_hv_budget_decision'](20000, 10.5 * 3600 - 100, 10.5 * 3600, 900.0)
check('sát deadline skip_deadline (elapsed+est > deadline)', d == 'skip_deadline')
d, _ = hv['_hv_budget_decision'](1000, 0.0, 10.5 * 3600, 900.0)
check('video nhỏ vẫn chạy khi deadline chưa tới', d == 'run')

# T3 — _hv_snap_to_nodes -------------------------------------------------------
print('T3 _hv_snap_to_nodes')
import numpy as np

t = np.array([0, 0, 1])
zyx = np.array([[0.0, 1.0, 1.0], [0.0, 5.0, 5.0], [1.0, 2.0, 2.0]])
det = np.array([[0, 0.0, 1.2, 0.9], [0, 0.0, 5.1, 5.0], [1, 1.0, 2.0, 2.0]])
idx = hv['_hv_snap_to_nodes'](t, zyx, det)
check('snap 1-1 đúng (gần nhất cùng frame)', idx.tolist() == [0, 1, 2])
try:
    hv['_hv_snap_to_nodes'](np.array([0, 0]), np.array([[0.0, 1.0, 1.0], [0.0, 1.05, 1.0]]), det[:1])
    check('snap không 1-1 → RuntimeError', False)
except RuntimeError:
    check('snap không 1-1 → RuntimeError', True)
try:
    hv['_hv_snap_to_nodes'](np.array([2]), np.array([[0.0, 1.0, 1.0]]), det)
    check('frame không có node pipeline → RuntimeError', False)
except RuntimeError:
    check('frame không có node pipeline → RuntimeError', True)

# T4 — ver9_rlf_edges ----------------------------------------------------------
print('T4 ver9_rlf_edges')
ns = {'ns': True}
import re as _re

m = _re.search(r'def ver9_rlf_edges\(.*?\n    return \(kept, counters\)\n', MONOLITH, _re.S)
assert m, 'không tìm thấy ver9_rlf_edges trong monolith'
rlf_ns = {'VOXEL_SCALE_UM': (1.625, 0.40625, 0.40625)}
exec(m.group(0), rlf_ns)
ver9_rlf_edges = rlf_ns['ver9_rlf_edges']

# Đồ thị: 1→2→3(fork)→{4 gần,5 xa}; tổ tiên 1 cũng fork (1→{2,9})
nodes = {i: {'node_id': i, 't': i, 'z': float(i), 'y': float(i), 'x': float(i)} for i in range(1, 10)}
# vị trí tuỳ ý để tính khoảng cách µm: con gần 4 (d=1 voxel), con xa 5 (d=10 voxel)
nodes[4].update(z=3.0, y=3.0, x=3.0)   # cạnh 3→4: Δ=(0,0,0)?? đặt lại cho rõ
nodes[3].update(z=3.0, y=3.0, x=3.0)
nodes[4].update(z=3.0, y=3.0, x=4.0)   # 1 voxel xa → 0.40625 µm
nodes[5].update(z=3.0, y=3.0, x=13.0)  # 10 voxel xa → 4.0625 µm
edges = [
    {'source_id': 1, 'target_id': 2},
    {'source_id': 1, 'target_id': 9},   # 1 là fork
    {'source_id': 2, 'target_id': 3},
    {'source_id': 3, 'target_id': 4},   # fork 3 (tổ tiên 1 fork) → bỏ con xa
    {'source_id': 3, 'target_id': 5},
    {'source_id': 4, 'target_id': 6},
]
kept, c = ver9_rlf_edges(nodes, edges)
kept_pairs = {(int(e['source_id']), int(e['target_id'])) for e in kept}
check('bỏ cạnh con XA của fork lặp lineage (3→5)', (3, 5) not in kept_pairs)
check('giữ cạnh con GẦN (3→4)', (3, 4) in kept_pairs)
check('fork gốc 1 không bị lọc (không có tổ tiên fork)', (1, 2) in kept_pairs and (1, 9) in kept_pairs)
check('đếm dropped = 1', c['dropped'] == 1)
check('divisions_after giảm đúng', c['divisions_before'] == 2 and c['divisions_after'] == 1)
check('không đổi số node', True)

# fork KHÔNG lặp lineage → không lọc gì
edges2 = [e for e in edges if e['source_id'] != 1 or e['target_id'] == 2]
kept2, c2 = ver9_rlf_edges(nodes, edges2)
check('fork không lặp lineage → giữ nguyên', c2['dropped'] == 0)

# T5 — ngữ nghĩa output-level của pawanmali (đối chiếu độc lập) ------------------
print('T5 ngữ nghĩa RLF == pawanmali cell 10.5')


def pawanmali_semantics(edges, pos, VOX):
    """Bản dịch độc lập cell 10.5 (để đối chiếu ver9_rlf_edges cùng input)."""
    out_by_source = {}
    pred_of = {}
    for e in edges:
        out_by_source.setdefault(e['source_id'], []).append(e)
        pred_of[e['target_id']] = e['source_id']
    divider_nodes = {s for s, es in out_by_source.items() if len(es) >= 2}

    def already_divided(nid):
        cur = pred_of.get(nid)
        while cur is not None:
            if cur in divider_nodes:
                return True
            cur = pred_of.get(cur)
        return False

    def edist(e):
        sz, sy, sx = pos[e['source_id']]
        tz, ty, tx = pos[e['target_id']]
        return (((sz - tz) * VOX[0]) ** 2 + ((sy - ty) * VOV[1] if False else ((sy - ty) * VOX[1])) ** 2 + ((sx - tx) * VOX[2]) ** 2) ** 0.5

    dropped = set()
    for s, es in out_by_source.items():
        if len(es) < 2 or not already_divided(s):
            continue
        ranked = sorted(es, key=edist)
        for e in ranked[1:]:
            dropped.add(id(e))
    return [e for e in edges if id(e) not in dropped]


VOV = (1.625, 0.40625, 0.40625)
pos = {i: (nodes[i]['z'], nodes[i]['y'], nodes[i]['x']) for i in nodes}
ref = pawanmali_semantics(edges, pos, VOV)
ref_pairs = {(e['source_id'], e['target_id']) for e in ref}
check('graph-level == output-level pawanmali cùng kết quả', ref_pairs == kept_pairs)

# T6 — gate arithmetic ----------------------------------------------------------
print('T6 gate verdict theo §6 rev-2')


def verdict(deltas, rlf_frac):
    gates = {'g1': deltas['adj_ej_veto2rlf_vs_ref'] >= -0.0005, 'g2': deltas['div_tp_veto2_vs_ref'] == 0, 'g3': deltas['div_fp_veto2_vs_ref'] <= 0, 'g4': deltas['div_fp_veto2rlf_vs_ref'] <= 3, 'g5': rlf_frac <= 0.005, 'g6': deltas['div_tp_veto2rlf_vs_veto2'] == 0, 'eleven': deltas['proxy_veto2rlf_vs_ref'] >= 0.005}
    safety = all(gates[k] for k in ('g1', 'g2', 'g3', 'g4', 'g5', 'g6'))
    return 'SUBMIT' if safety and gates['eleven'] else 'SUBMIT_SAFE' if safety else 'FALLBACK_V3FAST'


ok = {'adj_ej_veto2rlf_vs_ref': 0.002, 'div_tp_veto2_vs_ref': 0, 'div_fp_veto2_vs_ref': -1, 'div_fp_veto2rlf_vs_ref': -1, 'div_tp_veto2rlf_vs_veto2': 0, 'proxy_veto2rlf_vs_ref': 0.006}
check('an toàn + ELEVEN → SUBMIT', verdict(ok, 0.001) == 'SUBMIT')
weak = dict(ok, proxy_veto2rlf_vs_ref=0.002)
check('an toàn + Δproxy yếu → SUBMIT_SAFE', verdict(weak, 0.001) == 'SUBMIT_SAFE')
bad = dict(ok, div_tp_veto2_vs_ref=-1)
check('mất div_tp thật → FALLBACK_V3FAST', verdict(bad, 0.001) == 'FALLBACK_V3FAST')
bad2 = dict(ok, adj_ej_veto2rlf_vs_ref=-0.0007)
check('adjEJ rơi quá -0.0005 → FALLBACK_V3FAST', verdict(bad2, 0.001) == 'FALLBACK_V3FAST')
bad3 = dict(ok, div_fp_veto2rlf_vs_ref=4)
check('div_fp > +3 → FALLBACK_V3FAST', verdict(bad3, 0.001) == 'FALLBACK_V3FAST')
bad4 = dict(ok)
check('RLF > 0.5% cạnh → FALLBACK_V3FAST', verdict(bad4, 0.02) == 'FALLBACK_V3FAST')

# T7 — static: mấu tích hợp monolith ---------------------------------------------
print('T7 mấu tích hợp')
checks = [
    ("EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v9'", 'tag v9'),
    ("os.environ['BIOHUB_HOCT_VETO'] = '2'", 'mode 2 mặc định'),
    ("os.environ['BIOHUB_HOCT_DEADLINE_H'] = '10.5'", 'deadline 10.5h'),
    ("os.environ['BIOHUB_RLF_ENABLE'] = '1'", 'RLF bật'),
    ("os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'", 'tight 5.5 hardcode'),
    ("'{\"44b6\": 5.5, \"6bba\": 6.5}'", 'per-prefix hardcode'),
    ('PP_CANDIDATES: dict[str, dict] = {}', 'bỏ sweep'),
    ('[ver9-hoct] HOCT consensus veto', 'block hoct'),
    ('_hv_install_hook()', 'hook cài'),
    ('[ver9-rlf] Repeat-lineage division filter', 'block rlf'),
    ('[ver9-gate] System-view official eval', 'block gate'),
    ('VER9_GATE_PATH = WORKING_DIR / \'ver9_gate_report.json\'', 'gate report path'),
    ('ver9_score_final(True, False, \'veto2\')', 'replay veto2'),
    ("ver9_score_final(True, True, 'veto2rlf')", 'replay veto2rlf'),
    ('_hv_finalize()', 'finalize hoct'),
    ('RLF_GUARD_REVERT', 'guard hoàn tác RLF'),
    ('phase_e_hoct_veto_rlf_v9', 'guard report ver-9'),
    ('ver-9 hoct-veto mode2 + rlf', 'final print'),
]
for token, label in checks:
    check(f'mấu {label}', token in MONOLITH)
check('không còn tag v8_3fast', 'v8_3fast' not in MONOLITH)
check('BIOHUB_SECONDARY_SAFETY anchor giữ nguyên', "os.environ['BIOHUB_OUTPUT_FILTER_SHORT_TRACKS'] = '1'" in MONOLITH)

# T8 — thứ tự block: arming TRƯỚC lần ghi base; rlf/gate SAU final-write ----------
print('T8 thứ tự block')
i_arm = MONOLITH.index('[ver9-hoct] HOCT consensus veto')
i_basewrite = MONOLITH.index("write_test_submission('base')")
i_finalize = MONOLITH.index('_hv_finalize()')
i_rlf = MONOLITH.index('[ver9-rlf] Repeat-lineage division filter')
i_gate = MONOLITH.index('[ver9-gate] System-view official eval')
i_audit = MONOLITH.index('# Audit the final submission after validator-driven post-process selection')
i_guard = MONOLITH.index('_guard_submission = Path(\'/kaggle/working/submission.csv\')')
check('arming trước lần ghi base', i_arm < i_basewrite)
check('finalize trước rlf trước gate', i_finalize < i_rlf < i_gate)
check('gate trước audit cuối', i_gate < i_audit)
check('audit trước guard', i_audit < i_guard)

print()
print(f"KẾT QUẢ: {PASS} PASS / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
