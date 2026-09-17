"""test-ver10-blocks.py — Unit test offline (CPU, mock) cho ver-10: veto mode 1 + guard mật độ.

Không cần GPU / /kaggle/input: chỉ test các hàm THUẦN tách từ monolith ver-10:
  T1 _hv_apply_veto mode 1 (giữ cả 2 cạnh của node 2 con) / mode 2 (veto cả division)
  T2 _hv_estimate_s density-aware: công thức + hiệu chuẩn 8 stems đo thật (V10-LAB 17/9)
  T3 _hv_budget_decision: run / skip_video_cap / skip_deadline + hệ số 3× khi d_max > 550
  T4 _hv_snap_to_nodes (ánh xạ 1-1 KD-tree cùng frame, sai → RuntimeError)
  T5 _hvDeadlineAbort: (a) nảy giữa chunk trong _hv_predict_pairs; (b) KHÔNG bị retry bởi
     _hv_hoct_pairs (trái với RuntimeError solver vẫn retry 3 lần); (c) _hv_veto_video bắt
     riêng → status aborted_deadline + graph gốc giữ nguyên
  T6 static: mấu tích hợp monolith ver-10 (mode 1, deadline 7.5, cap 300, strip ver-9 sạch)
  T7 thứ tự block: arming TRƯỚC lần ghi base; finalize SAU final-write, TRƯỚC audit
"""
import os
import sys
import types
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
hoct_start = MONOLITH.index('# ==== [ver10-hoct] HOCT consensus veto')
hoct_end = MONOLITH.index('_base_postprocess_signature = _postprocess_resume_signature()', hoct_start)
hoct_src = MONOLITH[hoct_start:hoct_end]
print(f"[extract] HOCT block: {len(hoct_src.splitlines())} dòng")

hv: dict = {}
exec(compile(hoct_src, 'hoct-block-v10', 'exec'), hv)

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
check('mode1 divisions_after giữ nguyên', c1['divisions_before'] == 1 and c1['divisions_after'] == 1)

# T2 — estimator density-aware + hiệu chuẩn 8 stems đo thật --------------------
print('T2 _hv_estimate_s density-aware (hiệu chuẩn V10-LAB 17/9)')
est = hv['_hv_estimate_s'](10000, 100)
check('est(10k nodes, 100/frame) = 72s', abs(est - (2.2e-5 * 10000 * 100 + 50.0)) < 1e-9 and abs(est - 72.0) < 1e-9)
check('d_max=1 floor: est nhỏ nhất = fixed', abs(hv['_hv_estimate_s'](0, 1) - 50.0) < 1e-9)
# k·n·d_max + fixed, ×3 khi d_max > 550 (vùng ngoài hiệu chuẩn)
check('hệ số 3× khi d_max=600 (ngoài 550)', abs(hv['_hv_estimate_s'](1000, 600) - (2.2e-5 * 1000 * 600 + 50.0) * 3.0) < 1e-9)
check('không nhân 3 khi d_max=550 (biên)', abs(hv['_hv_estimate_s'](1000, 550) - (2.2e-5 * 1000 * 550 + 50.0)) < 1e-9)

# 8 stems validator đo thật (log v10_cell3.log: HOCT time chunks=1; n = final nodes
# theo log, d_max = raw graph đếm từ raw_graphs.json — xấp xỉ保守 của final)
VAL = [
    # dataset, n_final(log), d_max(raw), actual_s(log)
    ('44b6_12dfb391', 44955, 527, 315),
    ('44b6_267148e4', 22270, 286, 130),
    ('44b6_2a2eff9f', 40120, 498, 257),
    ('44b6_341df25f', 8413, 102, 65),
    ('6bba_062c8d37', 5857, 71, 58),
    ('6bba_07e24132', 29184, 365, 162),
    ('6bba_085bf656', 8292, 126, 64),
    ('6bba_09961292', 29747, 348, 162),
]
GAIN_STEMS = ('6bba_09961292', '6bba_07e24132')   # +0.00491 / +0.00452 (V10-RESULTS §3.3)
SKIP_STEMS = ('44b6_12dfb391', '44b6_2a2eff9f')   # ±0 / −0.00445 — est > cap 300
all_over = all(hv['_hv_estimate_s'](n, d) >= a for _, n, d, a in VAL)
check('est >= actual cho TẤT CẢ 8 stems (thiên về an toàn)', all_over)
over_ratio = [hv['_hv_estimate_s'](n, d) / a for _, n, d, a in VAL]
check('est/actual trong [1.0, 2.0] (không quá ước lượng vô lý)', all(1.0 <= r <= 2.0 for r in over_ratio), f'{[round(r, 2) for r in over_ratio]}')
runs, skips = [], []
for ds, n, d, a in VAL:
    decision, est_v = hv['_hv_budget_decision'](n, d, 0.0, 7.5 * 3600.0, 300.0)
    (runs if decision == 'run' else skips).append(ds)
check('2 stem sinh gain CHÍNH đều được RUN (est < 300)', all(s in runs for s in GAIN_STEMS), f'runs={runs}')
check('2 stem 44b6 khổng lồ bị SKIP (est > 300, đều vô hại/âm)', sorted(skips) == sorted(SKIP_STEMS), f'skips={skips}')
check('6/8 video validator được veto', len(runs) == 6 and len(skips) == 2)

# T3 — budget decision ---------------------------------------------------------
print('T3 _hv_budget_decision')
d, _ = hv['_hv_budget_decision'](20000, 300, 0.0, 7.5 * 3600.0, 300.0)
check('20k nodes/300 per-frame chạy được (est 182 < cap 300)', d == 'run')
d, _ = hv['_hv_budget_decision'](100000, 500, 0.0, 7.5 * 3600.0, 300.0)
check('100k nodes/500 per-frame skip_video_cap (est 1150 > 300)', d == 'skip_video_cap')
d, _ = hv['_hv_budget_decision'](20000, 600, 0.0, 7.5 * 3600.0, 300.0)
check('video LỚN + dày 600/frame bị ×3 → skip (kịch bản giết ver-9)', d == 'skip_video_cap')
d, _ = hv['_hv_budget_decision'](1000, 10, 7.5 * 3600.0 - 10.0, 7.5 * 3600.0, 300.0)
check('sát deadline skip_deadline (elapsed+est > deadline)', d == 'skip_deadline')
d, _ = hv['_hv_budget_decision'](1000, 10, 7.5 * 3600.0, 7.5 * 3600.0, 300.0)
check('đã qua deadline → skip_deadline', d == 'skip_deadline')
d, _ = hv['_hv_budget_decision'](100, 10, 0.0, 7.5 * 3600.0, 300.0)
check('video nhỏ vẫn chạy khi deadline chưa tới', d == 'run')

# T4 — _hv_snap_to_nodes -------------------------------------------------------
print('T4 _hv_snap_to_nodes')
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

# T5 — _hvDeadlineAbort --------------------------------------------------------
print('T5 _hvDeadlineAbort (abort giữa video — không retry, fail-safe)')


class _FakeSeries:
    def __init__(self, vals):
        self._vals = list(vals)

    def to_numpy(self):
        return np.asarray(self._vals)

    def to_list(self):
        return list(self._vals)


class _FakeSol:
    def __init__(self):
        self._empty = []

    def node_attrs(self, attr_keys):
        return {k: _FakeSeries([]) for k in attr_keys}

    def edge_attrs(self, attr_keys):
        return {'source_id': _FakeSeries([]), 'target_id': _FakeSeries([])}


class _InferenceMode:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


fake_torch = types.ModuleType('torch')
fake_torch.inference_mode = _InferenceMode
fake_torch.cuda = types.SimpleNamespace(empty_cache=lambda: None)
fake_hoct = types.ModuleType('hoct')
fake_hoct.predict = lambda *a, **k: _FakeSol()
fake_tracksdata = types.ModuleType('tracksdata')
fake_tracksdata.functional = types.ModuleType('tracksdata.functional')
fake_tracksdata.functional.TilingScheme = lambda tile_shape, overlap_shape: None
for name, mod in (('torch', fake_torch), ('hoct', fake_hoct), ('tracksdata', fake_tracksdata),
                 ('tracksdata.functional', fake_tracksdata.functional)):
    sys.modules.setdefault(name, mod)

labels4 = np.zeros((4, 1, 1, 1), dtype=np.int16)
det4 = np.array([[0, 0.0, 0.0, 0.0], [1, 0.0, 1.0, 0.0], [2, 0.0, 2.0, 0.0], [3, 0.0, 3.0, 0.0]])
ids4 = np.array([10, 11, 12, 13])

# (a) giữa chunk: chunk 0 xong, chunk 1 nảy _hvDeadlineAbort khi deadline đã qua
hv['_hv_notebook_elapsed_s'] = lambda: 7.5 * 3600.0 + 1.0
try:
    hv['_hv_predict_pairs'](None, labels4, None, det4, ids4, 2)
    check('(a) chunk 2/2 nảy _hvDeadlineAbort khi qua deadline', False)
except hv['_hvDeadlineAbort']:
    check('(a) chunk 2/2 nảy _hvDeadlineAbort khi qua deadline', True)
#对照: deadline chưa tới → chạy trọn vẹn (trả set rỗng từ fake predict)
hv['_hv_notebook_elapsed_s'] = lambda: 1.0
try:
    out = hv['_hv_predict_pairs'](None, labels4, None, det4, ids4, 2)
    check('(a对照) deadline chưa tới → 2 chunk chạy trọn', out == set())
except Exception as exc:
    check('(a对照) deadline chưa tới → 2 chunk chạy trọn', False, repr(exc))

# (b) _hv_hoct_pairs KHÔNG retry _hvDeadlineAbort (solver-failure RuntimeeError thì retry 3 lần)
hv['_hv_notebook_elapsed_s'] = lambda: 0.0
hv['_hv_install_and_load'] = lambda: 'fake_model'
hv['_hv_read_volume'] = lambda ds: labels4
hv['_hv_rasterize_spheres'] = lambda det, shape: np.zeros(shape, dtype=np.int16)
calls = {'abort': 0, 'solver': 0}


def _pp_abort(model, labels, images, det, ids, n_chunks):
    calls['abort'] += 1
    raise hv['_hvDeadlineAbort']('deadline test')


hv['_hv_predict_pairs'] = _pp_abort
nodes1 = {10: {'t': 0, 'z': 0.0, 'y': 0.0, 'x': 0.0}, 11: {'t': 1, 'z': 0.0, 'y': 1.0, 'x': 0.0}}
try:
    hv['_hv_hoct_pairs']('ds_test', nodes1)
    check('(b) _hv_hoct_pairs để _hvDeadlineAbort nổ lên (không nuốt)', False)
except hv['_hvDeadlineAbort']:
    check('(b) _hv_hoct_pairs để _hvDeadlineAbort nổ lên (không nuốt)', True)
check('(b) KHÔNG retry abort (predict gọi đúng 1 lần)', calls['abort'] == 1, f"calls={calls['abort']}")


def _pp_solver(model, labels, images, det, ids, n_chunks):
    calls['solver'] += 1
    raise RuntimeError('SCIP cannot solve')


hv['_hv_predict_pairs'] = _pp_solver
try:
    hv['_hv_hoct_pairs']('ds_test2', nodes1)
    check('(b对照) solver fail → RuntimeError "no solution" sau 3 chunk', False)
except RuntimeError as exc:
    check('(b对照) solver fail → RuntimeError "no solution" sau 3 chunk', 'HOCT produced no solution' in str(exc))
check('(b对照) solver fail được retry 3 lần (n_chunks 1,2,4)', calls['solver'] == 3, f"calls={calls['solver']}")

# (c) _hv_veto_video bắt _hvDeadlineAbort → aborted_deadline + graph gốc giữ nguyên
hv['_hv_notebook_elapsed_s'] = lambda: 0.0


def _hp_abort(dataset, nodes_by_id):
    raise hv['_hvDeadlineAbort']('mid-video deadline')


hv['_hv_hoct_pairs'] = _hp_abort
edges_in = [{'source_id': 10, 'target_id': 11}]
kept_edges, cc = hv['_hv_veto_video']('ds_test3', dict(nodes1), list(edges_in))
check('(c) status == aborted_deadline', cc['status'] == 'aborted_deadline', cc)
check('(c) graph gốc giữ nguyên (edges không đổi)', kept_edges == edges_in and cc['removed'] == 0)
check('(c) counts[aborted_deadline] tăng', hv['_HV_STATE']['counts']['aborted_deadline'] >= 1)
check('(c) không tính vào failed', hv['_HV_STATE']['counts']['failed'] == 0)

# (d) fail-safe thường: HOCT hỏng kiểu khác → failed + graph giữ nguyên


def _hp_fail(dataset, nodes_by_id):
    raise RuntimeError('boom')


hv['_hv_hoct_pairs'] = _hp_fail
kept_edges2, cc2 = hv['_hv_veto_video']('ds_test4', dict(nodes1), list(edges_in))
check('(d) lỗi thường → status failed, graph giữ nguyên', cc2['status'] == 'failed' and kept_edges2 == edges_in)

# T6 — static: mấu tích hợp monolith ver-10 ------------------------------------
print('T6 mấu tích hợp')
checks = [
    ("EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v10'", 'tag v10'),
    ("os.environ['BIOHUB_HOCT_VETO'] = '1'", 'mode 1 mặc định'),
    ("os.environ['BIOHUB_HOCT_DEADLINE_H'] = '7.5'", 'deadline 7.5h'),
    ("os.environ['BIOHUB_HOCT_MAX_VIDEO_S'] = '300'", 'cap 300s'),
    ("os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'", 'tight 5.5 hardcode'),
    ("'{\"44b6\": 5.5, \"6bba\": 6.5}'", 'per-prefix hardcode'),
    ('PP_CANDIDATES: dict[str, dict] = {}', 'bỏ sweep'),
    ('[ver10-hoct] HOCT consensus veto', 'block hoct v10'),
    ('class _hvDeadlineAbort', 'class abort'),
    ('_HV_K_ND = 2.2e-5', 'slope density model'),
    ('_HV_DENSITY_CAL = 550.0', 'ngưỡng hiệu chuẩn'),
    ('_hv_install_hook()', 'hook cài'),
    ('_hv_finalize()', 'finalize hoct'),
    ('phase_f_hoct_veto1_v10', 'guard report ver-10'),
    ('ver-10 hoct-veto mode1 (division-safe, density-guarded)', 'final print'),
]
for token, label in checks:
    check(f'mấu {label}', token in MONOLITH)
for forbidden, label in (('[ver9-rlf]', 'block RLF ver-9'), ('[ver9-gate]', 'block gate ver-9'),
                         ('ver9_rlf_edges', 'hàm RLF'), ('ver9_score_final', 'hàm gate replay'),
                         ('VER9_GATE', 'gate report'), ('BIOHUB_RLF_ENABLE', 'env RLF')):
    check(f'ĐÃ STRIP {label}', forbidden not in MONOLITH)
check('không còn tag v9 trong EXPERIMENT_TAG', 'reparent_hoct_v9' not in MONOLITH)
check('BIOHUB_SECONDARY_SAFETY anchor giữ nguyên', "os.environ['BIOHUB_OUTPUT_FILTER_SHORT_TRACKS'] = '1'" in MONOLITH)
check('gate production tau 0.6', "BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU'] = '0.6'" in MONOLITH)
check('gate production diverge 2.25', "BIOHUB_SAFE_DIV_DIVERGE_UM'] = '2.25'" in MONOLITH)
check('re-parent giữ 0.25', "BIOHUB_REPARENT_EDGE_PROB'] = '0.25'" in MONOLITH)

# T7 — thứ tự block ------------------------------------------------------------
print('T7 thứ tự block')
i_arm = MONOLITH.index('[ver10-hoct] HOCT consensus veto')
i_arm_end = MONOLITH.index('_base_postprocess_signature = _postprocess_resume_signature()', i_arm)
i_basewrite = MONOLITH.index("write_test_submission('base')")
i_finalize = MONOLITH.index('_hv_finalize()', i_arm_end)   # LỜI GỌI (sau block arming), không phải def
i_audit = MONOLITH.index('# Audit the final submission after validator-driven post-process selection')
i_guard = MONOLITH.index("_guard_submission = Path('/kaggle/working/submission.csv')")
check('arming trước lần ghi base', i_arm < i_basewrite)
check('finalize sau lần ghi base, trước audit cuối', i_basewrite < i_finalize < i_audit)
check('audit trước guard', i_audit < i_guard)

print()
print(f"KẾT QUẢ: {PASS} PASS / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
