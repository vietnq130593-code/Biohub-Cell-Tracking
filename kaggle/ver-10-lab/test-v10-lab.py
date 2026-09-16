"""test-v10-lab.py — Unit test offline (CPU sandbox 2 vCPU / không GPU / không dữ liệu thật)
cho ver-10 LAB: cell-monolith-v10lab.py + build-v10-lab.py + 2 notebook.

Mô phỏng pattern test-ver9-blocks.py: tách block từ monolith bằng marker, exec trong namespace
mock (os.environ điều khiển, synthetic graphs nhỏ). KHÔNG cần Kaggle / GPU / dữ liệu thật.

  T1  py_compile cell-monolith-v10lab.py PASS
  T2  [v10-lab-env] hành vi: LAB_MODE/grid mặc định 9 config/grid override/cache probe
  T3  LAB_MODE guard: region test-stems skip chứng minh bằng exec (list_test_stems KHÔNG gọi)
      + guard base-submission/audit-cuối bằng AST + marker
  T4  Dump/load roundtrip: synthetic graph → [v10-lab-dump] → [v10-lab-cache-load] → identical
      (+ dump không đè khi file cũ tồn tại, đè khi BIOHUB_LAB_FORCE_DUMP=1)
  T5  v10_score_config trên synthetic graphs: ref vs rlf_only (RLF bỏ đúng cạnh con xa, giữ gần);
      tight_override truyền đúng vào filter (mock ghi nhận MOTION_RELINK_TIGHT_UM/PER_PREFIX);
      veto_mode 0/1/2 dispatch đúng (mock _hv_veto_video đếm lời gọi theo _HV_MODE; mode khác
      nhau → kết quả khác nhau); globals restore sau config
  T6  [v10-lab-grid] chạy đủ grid: v10_lab_rows.csv cột đủ như validator_results.csv + config;
      v10_lab_report.json cấu trúc (summary/deltas_vs_ref/veto+rlf dropped/skipped/skip_reason,
      meta, runtime_s); SKIP khi LAB_SKIP_VETO=1 hoặc không cuda
  T7  CUDA bypass: exec vùng check với mock torch.cuda.is_available()=False
      → LAB_MODE+LAB_NO_CUDA KHÔNG raise; ngược lại raise (guard có ý nghĩa)
  T8  2 notebook: json.loads PASS + cell count (4/3) + cell lab chứa marker [v10-lab-dump]/
      [v10-lab-grid]/[v10-lab-env] + monolith nhúng nguyên văn + exec; cell setup Colab đủ
      9 slug dataset + 8 stems; cell CPU có cache env; bootstrap + upload đúng nơi
  T9  ver-9/cell-monolith.py giữ nguyên byte (sha256) — build không đụng file gốc

Chạy: python3 test-v10-lab.py  →  in mỗi test 1 dòng PASS/FAIL + tổng "x/y PASS".
"""
import ast
import csv
import hashlib
import json
import os
import py_compile
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MONOLITH = ROOT / 'cell-monolith-v10lab.py'
BUILD_SCRIPT = ROOT / 'build-v10-lab.py'
VER9 = ROOT.parent / 'ver-9' / 'cell-monolith.py'
NOTEBOOK_COLAB = ROOT.parents[1] / 'download' / 'v10-lab-colab.ipynb'
NOTEBOOK_CPU = ROOT.parents[1] / 'download' / 'v10-lab-cpu.ipynb'
VER9_SHA256 = 'b1bb370d898768dc531ada2c14afea1601301371115350c48fe2a4914f69c412'
VOXEL_SCALE_UM = (1.625, 0.40625, 0.40625)
V10_STEMS_EXPECT = ['44b6_12dfb391', '44b6_267148e4', '44b6_2a2eff9f', '44b6_341df25f',
                    '6bba_062c8d37', '6bba_07e24132', '6bba_085bf656', '6bba_09961292']
V10_DATASETS_EXPECT = [
    'pilkwang/biohub-tracking-support-pack-50ep-v1',
    'pilkwang/biohub-deepcenter-unet3d-center-prior-v1',
    'pilkwang/biohub-temporal-unet3d-seed314159-v1',
    'dalloliogm/biohub-official-scorer-patched',
    'dariushafshar/biohub-local-cv-pack',
    'vietnguyen130593/biohub-v6-heldout-preds',
    'giorgosi/biohub-divnet-v2',
    'sjlee101/biohub-hoct-020-wheels',
    'musculer/biohub-hoct-general-v0-official',
]
DEFAULT_GRID_LABELS = ['ref', 'tight_45', 'tight_50', 'tight_60', 'tight_70', 'rlf_only',
                       'veto1', 'veto2', 'veto2rlf']

MON = MONOLITH.read_text()
PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = '') -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  PASS {name}')
    else:
        FAIL += 1
        print(f'  FAIL {name} {detail}')


def extract(start_marker: str, end_marker: str, what: str) -> str:
    i0 = MON.index(start_marker)
    i1 = MON.index(end_marker, i0)
    src = MON[i0:i1]
    print(f'[extract] {what}: {len(src.splitlines())} dòng')
    return src


def base_ns(tmp: Path, **extra) -> dict:
    ns = {'__name__': 'v10lab_test', '__builtins__': __builtins__,
          'os': os, 'json': json, 'time': time, 'Path': Path, 'csv': csv,
          'VOXEL_SCALE_UM': VOXEL_SCALE_UM,
          'WORKING_DIR': tmp,
          '_resume_json_safe': lambda v: v}
    ns.update(extra)
    return ns


# ---- synthetic graphs: 2 stems, mỗi stem 1 fork lặp lineage + 1 cạnh HOCT không đề xuất --------
STEM_A, STEM_B = '44b6_aaa', '6bba_bbb'


def make_raw_a():
    """Stem A: fork 1 (1→{2,8}); fork 3 lặp lineage (3→{4 gần, 5 xa}); HOCT đề xuất (1,2)(2,3)(3,4)(4,6)."""
    nodes = {i: {'node_id': i, 't': i % 3, 'z': float(i), 'y': float(i), 'x': float(i)} for i in range(1, 9)}
    nodes[8] = {'node_id': 8, 't': 1, 'z': 1.0, 'y': 1.0, 'x': 9.0}
    nodes[3].update(z=3.0, y=3.0, x=3.0)
    nodes[4].update(z=3.0, y=3.0, x=4.0)    # con GẦN của fork 3 (1 voxel → 0.40625 µm)
    nodes[5].update(z=3.0, y=3.0, x=13.0)   # con XA của fork 3 (10 voxel → 4.0625 µm)
    edges = [{'source_id': 1, 'target_id': 2}, {'source_id': 1, 'target_id': 8},
             {'source_id': 2, 'target_id': 3},
             {'source_id': 3, 'target_id': 4}, {'source_id': 3, 'target_id': 5},
             {'source_id': 4, 'target_id': 6}]
    return nodes, edges


def make_raw_b():
    """Stem B: fork 1; fork 5 lặp lineage (5→{6 gần, 7 xa}); HOCT đề xuất MỌI cạnh (veto no-op)."""
    nodes = {i: {'node_id': i, 't': i % 3, 'z': float(i), 'y': float(i), 'x': float(i)} for i in range(1, 10)}
    nodes[9] = {'node_id': 9, 't': 1, 'z': 1.0, 'y': 1.0, 'x': 9.0}
    nodes[5].update(z=5.0, y=5.0, x=5.0)
    nodes[6].update(z=5.0, y=5.0, x=6.0)
    nodes[7].update(z=5.0, y=5.0, x=15.0)
    edges = [{'source_id': 1, 'target_id': 2}, {'source_id': 1, 'target_id': 9},
             {'source_id': 2, 'target_id': 3}, {'source_id': 3, 'target_id': 5},
             {'source_id': 5, 'target_id': 6}, {'source_id': 5, 'target_id': 7}]
    return nodes, edges


def make_val_data():
    raw_a = make_raw_a()
    raw_b = make_raw_b()
    val_raw = {STEM_A: raw_a, STEM_B: raw_b}
    # GT: đúng mọi cạnh trừ cạnh con XA của fork lặp lineage (3→5 và 5→7)
    gt_a_edges = [(1, 2), (1, 8), (2, 3), (3, 4), (4, 6)]
    gt_b_edges = [(1, 2), (1, 9), (2, 3), (3, 5), (5, 6)]
    gt = {}
    for stem, (nodes, edges) in val_raw.items():
        nodes_plain = {nid: (int(n['t']), float(n['z']), float(n['y']), float(n['x'])) for nid, n in nodes.items()}
        gt[stem] = (nodes_plain, (gt_a_edges if stem == STEM_A else gt_b_edges), len(nodes_plain))
    return val_raw, gt


HOCT_PAIRS = {STEM_A: {(1, 2), (2, 3), (3, 4), (4, 6)},
              STEM_B: {(1, 2), (1, 9), (2, 3), (3, 5), (5, 6), (5, 7)}}


def _hv_apply_veto_real(edges, hoct_pairs, mode):
    """Port nguyên văn _hv_apply_veto của monolith (logic thuần, đã test ở test-ver9-blocks)."""
    from collections import Counter
    out_deg = Counter(int(e['source_id']) for e in edges)
    kept = []
    for e in edges:
        s, t = int(e['source_id']), int(e['target_id'])
        if (s, t) in hoct_pairs or (mode == 1 and out_deg[s] >= 2):
            kept.append(e)
    out_deg_after = Counter(int(e['source_id']) for e in kept)
    counters = {'edges_before': len(edges), 'edges_after': len(kept), 'removed': len(edges) - len(kept),
                'divisions_before': sum(1 for v in out_deg.values() if v >= 2),
                'divisions_after': sum(1 for v in out_deg_after.values() if v >= 2)}
    return kept, counters


# ============================================================================================
print('T1 py_compile')
try:
    py_compile.compile(str(MONOLITH), doraise=True)
    check('py_compile cell-monolith-v10lab.py', True)
except Exception as exc:
    check('py_compile cell-monolith-v10lab.py', False, str(exc))
try:
    py_compile.compile(str(BUILD_SCRIPT), doraise=True)
    py_compile.compile(str(ROOT / 'lab-grid-block.py'), doraise=True)
    check('py_compile build-v10-lab.py + lab-grid-block.py', True)
except Exception as exc:
    check('py_compile build-v10-lab.py + lab-grid-block.py', False, str(exc))

# ============================================================================================
print('T2 [v10-lab-env] hành vi')
env_src = extract('# ==== [v10-lab-env] V10 LAB', '# Convert cached state values', 'block [v10-lab-env]')
tmp2 = Path(tempfile.mkdtemp(prefix='v10_t2_'))
saved_env = {k: os.environ.get(k) for k in ('BIOHUB_LAB_MODE', 'BIOHUB_LAB_NO_CUDA', 'BIOHUB_V10_GRID', 'BIOHUB_VAL_CACHE_DIR', 'BIOHUB_V10_SKIP_VETO', 'BIOHUB_LAB_FORCE_DUMP')}
try:
    os.environ['BIOHUB_LAB_MODE'] = '1'
    os.environ.pop('BIOHUB_V10_GRID', None)
    os.environ.pop('BIOHUB_VAL_CACHE_DIR', None)
    ns = base_ns(tmp2)
    exec(compile(env_src, 'v10-env', 'exec'), ns)
    check('LAB_MODE=True từ env', ns['LAB_MODE'] is True)
    check('LAB_DUMP_DIR = WORKING_DIR/v10_lab_cache', ns['LAB_DUMP_DIR'] == tmp2 / 'v10_lab_cache')
    check('grid mặc định 9 config đúng label', [c['label'] for c in ns['LAB_GRID']] == DEFAULT_GRID_LABELS)
    check('config tight_45 tight_override=4.5', ns['LAB_GRID'][1]['tight_override'] == 4.5)
    check('config veto2rlf needs_gpu + veto_mode 2 + rlf', ns['LAB_GRID'][8] == {'label': 'veto2rlf', 'veto_mode': 2, 'apply_rlf': True, 'needs_gpu': True})
    os.environ['BIOHUB_V10_GRID'] = json.dumps([{'label': 'custom_x', 'tight_override': 5.2}])
    ns2 = base_ns(tmp2)
    exec(compile(env_src, 'v10-env', 'exec'), ns2)
    check('BIOHUB_V10_GRID override được tôn trọng', [c['label'] for c in ns2['LAB_GRID']] == ['custom_x'])
    os.environ['BIOHUB_V10_GRID'] = 'not-json{{'
    ns3 = base_ns(tmp2)
    exec(compile(env_src, 'v10-env', 'exec'), ns3)
    check('BIOHUB_V10_GRID sai cú pháp → fallback grid mặc định', [c['label'] for c in ns3['LAB_GRID']] == DEFAULT_GRID_LABELS)
    # cache probe: có cache → AVAILABLE; không có → False
    cache_dir = tmp2 / 'fake_cache'
    cache_dir.mkdir()
    (cache_dir / 'raw_graphs.json').write_text('{}')
    (cache_dir / 'gt_bundle.json').write_text('{}')
    os.environ['BIOHUB_V10_GRID'] = json.dumps([{'label': 'ref'}])
    os.environ['BIOHUB_VAL_CACHE_DIR'] = str(cache_dir)
    ns4 = base_ns(tmp2)
    exec(compile(env_src, 'v10-env', 'exec'), ns4)
    check('cache probe: đủ 2 file → _V10_LAB_CACHE_AVAILABLE=True', ns4['_V10_LAB_CACHE_AVAILABLE'] is True)
    (cache_dir / 'gt_bundle.json').unlink()
    ns5 = base_ns(tmp2)
    exec(compile(env_src, 'v10-env', 'exec'), ns5)
    check('cache probe: thiếu gt_bundle → False (predict như thường)', ns5['_V10_LAB_CACHE_AVAILABLE'] is False)
finally:
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
shutil.rmtree(tmp2, ignore_errors=True)

# ============================================================================================
print('T3 LAB_MODE guard — skip region predict-test + submission + audit cuối')
stems_region = """if LAB_MODE:
    test_stems: list[str] = []
    print('[v10-lab] LAB_MODE: bỏ qua region predict-test (test_stems = [] — chỉ chạy validator + grid)')
else:
    test_stems = list_test_stems()
    print(f'Found {len(test_stems)} test videos')
    print(test_stems[:10])"""
check('region test-stems patch có mặt nguyên văn trong monolith', stems_region in MON)


def _list_test_stems_boom():
    raise AssertionError('list_test_stems() KHÔNG được gọi khi LAB_MODE=1')


for mode, expect_call in (('1', False), ('0', True)):
    os.environ['BIOHUB_LAB_MODE'] = mode
    ns = {'__builtins__': __builtins__, 'LAB_MODE': mode == '1', 'list_test_stems': _list_test_stems_boom}
    raised = False
    try:
        exec(compile(stems_region, 'stems-region', 'exec'), ns)
    except AssertionError:
        raised = True
    if expect_call:
        check(f'LAB_MODE={mode}: nhánh else GỌC list_test_stems (guard có ý nghĩa)', raised and ns.get('test_stems') is None)
    else:
        check(f'LAB_MODE={mode}: test_stems = [] và list_test_stems KHÔNG được gọi', (not raised) and ns['test_stems'] == [])
os.environ.pop('BIOHUB_LAB_MODE', None)

# guard base-submission + audit cuối bằng AST/marker
tree = ast.parse(MON)
check('ast.parse toàn monolith OK', True)
_if_lab = [n for n in tree.body if isinstance(n, ast.If) and ast.dump(n.test) == "Name(id='LAB_MODE', ctx=Load())"]
_if_notlab = [n for n in tree.body if isinstance(n, ast.If) and isinstance(n.test, ast.UnaryOp) and ast.dump(n.test) == "UnaryOp(op=Not(), operand=Name(id='LAB_MODE', ctx=Load()))"]
check('có ≥2 khối `if LAB_MODE:` top-level (test-stems + base-submission)', len(_if_lab) >= 2, f'thấy {len(_if_lab)}')
check('có đúng 1 khối `if not LAB_MODE:` top-level bọc audit cuối', len(_if_notlab) == 1, f'thấy {len(_if_notlab)}')
_audit_src = ast.get_source_segment(MON, _if_notlab[0]) if _if_notlab else ''
check('audit cuối nằm TRONG khối if not LAB_MODE (retention guard + final print)', all(tok in _audit_src for tok in ('_guard_submission', 'PRODUCTION SUBMISSION PIPELINE: COMPLETE', 'LAB_MODE: bỏ qua audit cuối')))
check('guard ghi submission base bị chặn khi LAB_MODE (marker print)', "print('[v10-lab] LAB_MODE: bỏ qua ghi submission base" in MON)
check('guard preview submission cuối: `and not LAB_MODE`', 'if not _final_submission_ready and not LAB_MODE:' in MON)
check('guard validator prediction khi cache: `and not _V10_LAB_CACHE_LOADED`', 'if VALIDATOR_ENABLE and val_stems and not _V10_LAB_CACHE_LOADED:' in MON)
check('guard val selection khi cache: `and not _V10_LAB_CACHE_AVAILABLE`', 'if VALIDATOR_ENABLE and TRAIN_DIR.exists() and not _V10_LAB_CACHE_AVAILABLE:' in MON)

# ============================================================================================
print('T4 Dump/load roundtrip ([v10-lab-dump] → [v10-lab-cache-load])')
dump_src = extract('# ==== [v10-lab-dump] Ghi cache raw graphs', '# Run post-processing on cached validator graphs', 'block [v10-lab-dump]')
cache_src = extract('# ==== [v10-lab-cache-load] nạp val_stems', '# Merge validator prediction shards', 'block [v10-lab-cache-load]')
val_raw, val_gt = make_val_data()
tmp4 = Path(tempfile.mkdtemp(prefix='v10_t4_'))
dump_dir = tmp4 / 'v10_lab_cache'


def run_dump(force: bool):
    os.environ['BIOHUB_LAB_FORCE_DUMP'] = '1' if force else '0'
    ns = base_ns(tmp4, LAB_MODE=True, LAB_NO_CUDA=False, LAB_SKIP_VETO=False, LAB_VAL_CACHE_DIR='',
                 LAB_FORCE_DUMP=force, LAB_DUMP_DIR=dump_dir, LAB_GRID=[{'label': 'ref'}],
                 EXPERIMENT_TAG='v10lab_test', VAL_RAW_GRAPHS=val_raw, VAL_GT=val_gt,
                 _V10_LAB_CACHE_LOADED=False)
    exec(compile(dump_src, 'v10-dump', 'exec'), ns)
    return ns


run_dump(force=True)
raw_json = json.loads((dump_dir / 'raw_graphs.json').read_text())
gt_json = json.loads((dump_dir / 'gt_bundle.json').read_text())
meta_json = json.loads((dump_dir / 'meta.json').read_text())
check('dump ghi đủ 3 file (raw/gt/meta)', len(list(dump_dir.glob('*.json'))) == 3)
check('meta.json: stems + experiment_tag + source predict', meta_json['stems'] == sorted(val_raw.keys()) and meta_json['experiment_tag'] == 'v10lab_test' and meta_json['source'] == 'validator_prediction')
check('raw_graphs.json: nodes key str + edges đủ cột source/target', set(raw_json.keys()) == {STEM_A, STEM_B} and all('source_id' in e and 'target_id' in e for s in raw_json.values() for e in s['edges']))
sha_raw = hashlib.sha256((dump_dir / 'raw_graphs.json').read_bytes()).hexdigest()
run_dump(force=False)
check('dump lần 2 (KHÔNG force) → KHÔNG đè file cũ', hashlib.sha256((dump_dir / 'raw_graphs.json').read_bytes()).hexdigest() == sha_raw)
run_dump(force=True)
check('dump lần 3 (BIOHUB_LAB_FORCE_DUMP=1) → đè được', hashlib.sha256((dump_dir / 'raw_graphs.json').read_bytes()).hexdigest() == sha_raw)

# load lại như kernel CPU: env block (probe) + cache-load block
os.environ['BIOHUB_LAB_MODE'] = '1'          # env block đọc os.environ, không đọc namespace
os.environ['BIOHUB_VAL_CACHE_DIR'] = str(dump_dir)
os.environ['BIOHUB_LAB_FORCE_DUMP'] = '0'
ns_env = base_ns(tmp4)
exec(compile(env_src, 'v10-env', 'exec'), ns_env)
check('env probe thấy cache vừa dump', ns_env['_V10_LAB_CACHE_AVAILABLE'] is True)
ns_load = dict(ns_env)
exec(compile(cache_src, 'v10-cache', 'exec'), ns_load)
check('cache-load: _V10_LAB_CACHE_LOADED=True + val_stems sorted', ns_load['_V10_LAB_CACHE_LOADED'] is True and ns_load['val_stems'] == sorted(val_raw.keys()))
# nhánh gán VAL_RAW_GRAPHS/VAL_GT từ cache (patch P11 trong monolith — chạy nguyên văn)
_i_vrg = MON.index("VAL_RAW_GRAPHS: dict[str, tuple[dict, list]] = {}")
_i_elif = MON.index("elif VALIDATOR_ENABLE and val_stems:", _i_vrg)
_vrg_branch = MON[_i_vrg:_i_elif]
exec(compile(_vrg_branch, 'v10-vrg-branch', 'exec'), ns_load)
rt_raw = ns_load['VAL_RAW_GRAPHS']
rt_gt = ns_load['VAL_GT']
same_nodes = all(rt_raw[s][0] == val_raw[s][0] for s in val_raw)
same_edges = all([dict(e) for e in rt_raw[s][1]] == val_raw[s][1] for s in val_raw)
check('roundtrip raw graphs: nodes identical (int keys)', same_nodes)
check('roundtrip raw graphs: edges identical', same_edges)
same_gt_nodes = all({k: tuple(v) for k, v in rt_gt[s][0].items()} == val_gt[s][0] for s in val_gt)
same_gt_edges = all([tuple(e) for e in rt_gt[s][1]] == val_gt[s][1] for s in val_gt)
check('roundtrip GT: nodes_plain + edges_plain + t_true identical', same_gt_nodes and same_gt_edges and all(rt_gt[s][2] == val_gt[s][2] for s in val_gt))
os.environ.pop('BIOHUB_VAL_CACHE_DIR', None)
os.environ.pop('BIOHUB_LAB_FORCE_DUMP', None)
os.environ.pop('BIOHUB_LAB_MODE', None)
shutil.rmtree(tmp4, ignore_errors=True)

# ============================================================================================
print('T5 v10_score_config trên synthetic graphs (mock namespace theo pattern test-ver9-hook)')
grid_src = extract('# ==== [v10-lab-grid] Grid sweep', '# [v10-lab] LAB_MODE bỏ qua toàn bộ audit cuối', 'block [v10-lab-grid]')
# chỉ lấy PHẦN ĐỊNH NGHĨA hàm (đến trước dòng chạy grid) để test v10_score_config riêng
_grid_def_end = grid_src.index("_v10_have_cuda = False")
grid_defs = grid_src[:_grid_def_end]
val_raw2, val_gt2 = make_val_data()
tmp5 = Path(tempfile.mkdtemp(prefix='v10_t5_'))


def nodes_by_id_to_plain_mock(nodes_by_id):
    return {nid: (int(n['t']), float(n['z']), float(n['y']), float(n['x'])) for nid, n in nodes_by_id.items()}


def score_sample_mock(pred_nodes_plain, pred_edges_plain, gt_nodes_plain, gt_edges_plain, t_true):
    pred_set = set(pred_edges_plain)
    gt_set = set(gt_edges_plain)
    tp, fp, fn = len(pred_set & gt_set), len(pred_set - gt_set), len(gt_set - pred_set)
    jac = tp / (tp + fp + fn) if (tp + fp + fn) else 0.0
    pred_out = {}
    for s, t in pred_set:
        pred_out.setdefault(s, set()).add(t)
    gt_out = {}
    for s, t in gt_set:
        gt_out.setdefault(s, set()).add(t)
    div_tp = sum(1 for s, outs in pred_out.items() if len(outs) >= 2 and len(gt_out.get(s, ())) >= 2)
    div_fp = sum(1 for s, outs in pred_out.items() if len(outs) >= 2 and len(gt_out.get(s, ())) < 2)
    div_fn = sum(1 for s, outs in gt_out.items() if len(outs) >= 2 and len(pred_out.get(s, ())) < 2)
    row = {'edge_tp': tp, 'edge_fp': fp, 'edge_fn': fn, 'edge_jaccard': jac, 't_pred': len(pred_nodes_plain), 't_true': t_true,
           'adjusted_edge_jaccard': jac, 'div_tp': div_tp, 'div_fp': div_fp, 'div_fn': div_fn, 'div_jaccard': tp and div_tp / max(div_tp + div_fp + div_fn, 1),
           'weight': tp + fp + fn, 'missed_gt_nodes': 0, 'spurious_pred_nodes': 0, 'edges_recovered': tp, 'edges_fragmented': fn,
           'edges_lost_to_detection': 0, 'wrong_association_edges': fp}
    return row


def aggregate_official_mock(sample_rows):
    total_w = sum(r['weight'] for r in sample_rows) or 1
    weighted_adj = sum(r['adjusted_edge_jaccard'] * r['weight'] for r in sample_rows) / total_w
    div_tp = sum(r['div_tp'] for r in sample_rows)
    div_fp = sum(r['div_fp'] for r in sample_rows)
    div_fn = sum(r['div_fn'] for r in sample_rows)
    div_jac = div_tp / (div_tp + div_fp + div_fn) if (div_tp + div_fp + div_fn) else 0.0
    return {'adjusted_edge_jaccard': weighted_adj, 'division_jaccard': div_jac, 'proxy_score': weighted_adj + 0.1 * div_jac,
            'div_tp': div_tp, 'div_fp': div_fp, 'div_fn': div_fn, 'missed_gt_nodes': 0, 'spurious_pred_nodes': 0,
            'edges_recovered': sum(r['edges_recovered'] for r in sample_rows), 'edges_fragmented': sum(r['edges_fragmented'] for r in sample_rows),
            'edges_lost_to_detection': 0, 'wrong_association_edges': sum(r['wrong_association_edges'] for r in sample_rows)}


import copy as _copy_mod

filter_seen = []
veto_calls = []
_CUR = {}   # namespace "hiện tại" cho mock đọc globals đúng lúc gọi (giống monolith đọc module globals)


def _mock_filter(nodes_by_id, raw_edges, dataset=None, deepcenter_bundle=None, divnet_bundle=None):
    filter_seen.append((dataset, _CUR['MOTION_RELINK_TIGHT_UM'], dict(_CUR['MOTION_RELINK_TIGHT_PER_PREFIX'])))
    return nodes_by_id, list(raw_edges), {'raw_edges': len(raw_edges), 'safe_divisions_added': 0}


def _mock_veto(dataset, nodes_by_id, edges):
    veto_calls.append((dataset, _CUR['_HV_MODE']))
    return _hv_apply_veto_real(edges, HOCT_PAIRS[dataset], _CUR['_HV_MODE'])


class _TorchMock:
    class cuda:
        @staticmethod
        def is_available():
            return True


ns5 = base_ns(tmp5, _copy=_copy_mod, torch=_TorchMock,
              val_stems=[STEM_A, STEM_B], VAL_RAW_GRAPHS=val_raw2, VAL_GT=val_gt2,
              TEST_DIR=tmp5, TRAIN_DIR=tmp5,
              MOTION_RELINK_TIGHT_UM=5.5, MOTION_RELINK_TIGHT_PER_PREFIX={'44b6': 5.5, '6bba': 6.5},
              _HV_MODE=2, filter_output_graph=_mock_filter, _hv_veto_video=_mock_veto,
              nodes_by_id_to_plain=nodes_by_id_to_plain_mock, score_sample=score_sample_mock,
              aggregate_official=aggregate_official_mock, EXPERIMENT_TAG='v10lab_test')
_CUR = ns5   # LIVE view: mock đọc đúng giá trị mà v10_score_config override trong globals (ns5) tại call-time
ns5['ns5'] = ns5
exec(compile(grid_defs, 'v10-grid-defs', 'exec'), ns5)
v10_score_config = ns5['v10_score_config']
ver9_rlf_edges = ns5['ver9_rlf_edges']

# --- ref vs rlf_only: RLF bỏ đúng cạnh con xa của fork lặp lineage, giữ cạnh gần
ref_sum, ref_rows = v10_score_config(tight_override=None, veto_mode=0, apply_rlf=False, label='ref')
rlf_sum, rlf_rows = v10_score_config(tight_override=None, veto_mode=0, apply_rlf=True, label='rlf_only')
ref_pairs = {(r['stem'], e) for r in ref_rows for e in ()}  # placeholder — dùng rows qua per-stem scoring
check('ref giữ đủ 6 cạnh/stem (filter passthrough)', all(r['edge_tp'] + r['edge_fp'] == 6 for r in ref_rows))
check('rlf_only bỏ đúng 1 cạnh/stem (3→5 và 5→7)', rlf_sum['rlf_edges_dropped'] == 2 and all(r['edge_tp'] + r['edge_fp'] == 5 for r in rlf_rows))
check('rlf_only adjEJ CAO hơn ref (bỏ 2 cạnh FP)', rlf_sum['adjusted_edge_jaccard'] > ref_sum['adjusted_edge_jaccard'])
check('rlf_only div_fp giảm (fork lặp biến mất)', rlf_sum['div_fp'] < ref_sum['div_fp'])

# --- tight_override truyền đúng qua globals (filter mock ghi nhận tại call-time)
filter_seen.clear()
v10_score_config(tight_override=4.5, veto_mode=0, apply_rlf=False, label='tight_45')
check('tight_override 4.5 → MOTION_RELINK_TIGHT_UM=4.5 trong mọi lời gọi filter', all(fs[1] == 4.5 for fs in filter_seen))
check('tight_override 4.5 → MỌI giá trị per-prefix = 4.5 (global override)', all(set(fs[2].values()) == {4.5} and len(fs[2]) == 2 for fs in filter_seen))
check('tight_override giữ nguyên key per-prefix (44b6/6bba)', all(set(fs[2].keys()) == {'44b6', '6bba'} for fs in filter_seen))
check('globals tight KHÔNG restore sai: về 5.5/{44b6:5.5,6bba:6.5}', ns5['MOTION_RELINK_TIGHT_UM'] == 5.5 and ns5['MOTION_RELINK_TIGHT_PER_PREFIX'] == {'44b6': 5.5, '6bba': 6.5})

# --- veto_mode dispatch: mode 0 không gọi; mode 1/2 gọi với _HV_MODE đúng; kết quả khác nhau
veto_calls.clear()
v10_score_config(tight_override=None, veto_mode=0, apply_rlf=False, label='m0')
check('veto_mode=0 → _hv_veto_video KHÔNG được gọi', len(veto_calls) == 0)
veto_calls.clear()
v10_score_config(tight_override=None, veto_mode=1, apply_rlf=False, label='v1')
check('veto_mode=1 → gọi _hv_veto_video với _HV_MODE=1 cho 2 stems', veto_calls == [(STEM_A, 1), (STEM_B, 1)])
veto_calls.clear()
v1_sum, _ = v10_score_config(tight_override=None, veto_mode=1, apply_rlf=False, label='v1b')
v2_sum, _ = v10_score_config(tight_override=None, veto_mode=2, apply_rlf=False, label='v2b')
check('veto_mode=2 → _hv_veto_video với _HV_MODE=2', veto_calls == [(STEM_A, 1), (STEM_B, 1), (STEM_A, 2), (STEM_B, 2)])
check('mode 1 ≠ mode 2 (mode 2 bỏ thêm cạnh division 1→8/1→9)', v2_sum['veto_edges_dropped'] > v1_sum['veto_edges_dropped'] and v2_sum['veto_edges_dropped'] == 2)
check('mode 2 giảm cạnh hơn mode 1 → adjEJ khác nhau', v2_sum['adjusted_edge_jaccard'] != v1_sum['adjusted_edge_jaccard'])
check('globals _HV_MODE restore về 2 (giá trị trước config)', ns5['_HV_MODE'] == 2)
check('TEST_DIR restore về giá trị gốc sau config', ns5['TEST_DIR'] == tmp5)

# --- veto2rlf: veto mode 2 xong RLF còn dọn tiếp fork lặp của stem B (5→7 không bị veto)
v2r_sum, _ = v10_score_config(tight_override=None, veto_mode=2, apply_rlf=True, label='veto2rlf')
check('veto2rlf: veto bỏ 2 cạnh + RLF bỏ thêm 1 cạnh (stem B)', v2r_sum['veto_edges_dropped'] == 2 and v2r_sum['rlf_edges_dropped'] == 1)

shutil.rmtree(tmp5, ignore_errors=True)

# ============================================================================================
print('T6 [v10-lab-grid] chạy đủ grid: rows.csv + report.json + skip logic')
tmp6 = Path(tempfile.mkdtemp(prefix='v10_t6_'))
val_raw6, val_gt6 = make_val_data()
VALIDATOR_COLS_EXPECT = {'edge_tp', 'edge_fp', 'edge_fn', 'edge_jaccard', 't_pred', 't_true', 'adjusted_edge_jaccard',
                         'div_tp', 'div_fp', 'div_fn', 'div_jaccard', 'weight', 'stem', 'config', 'safe_divisions_added'}


def run_grid(skip_veto: bool, have_cuda: bool):
    class _T:
        class cuda:
            @staticmethod
            def is_available():
                return have_cuda
    rows_csv = tmp6 / f'rows_{int(skip_veto)}_{int(have_cuda)}.csv'
    report_json = tmp6 / f'report_{int(skip_veto)}_{int(have_cuda)}.json'
    ns = base_ns(tmp6, _copy=_copy_mod, torch=_T,
                 val_stems=[STEM_A, STEM_B], VAL_RAW_GRAPHS=val_raw6, VAL_GT=val_gt6,
                 TEST_DIR=tmp6, TRAIN_DIR=tmp6,
                 MOTION_RELINK_TIGHT_UM=5.5, MOTION_RELINK_TIGHT_PER_PREFIX={'44b6': 5.5, '6bba': 6.5},
                 _HV_MODE=2, filter_output_graph=_mock_filter, _hv_veto_video=_mock_veto,
                 nodes_by_id_to_plain=nodes_by_id_to_plain_mock, score_sample=score_sample_mock,
                 aggregate_official=aggregate_official_mock, EXPERIMENT_TAG='v10lab_test',
                 PP_RESULTS={'base': {'proxy_score': 0.5, 'adjusted_edge_jaccard': 0.5}}, VALIDATOR_STATS_PATH=tmp6 / 'validator_results.csv',
                 predict_val_seconds=0.0, LAB_MODE=True, LAB_NO_CUDA=(not have_cuda), LAB_SKIP_VETO=skip_veto,
                 LAB_VAL_CACHE_DIR='', LAB_FORCE_DUMP=False, LAB_DUMP_DIR=tmp6 / 'dump',
                 LAB_GRID=json.loads('[{"label":"ref"},{"label":"tight_45","tight_override":4.5},{"label":"rlf_only","apply_rlf":true},{"label":"veto1","veto_mode":1,"needs_gpu":true},{"label":"veto2","veto_mode":2,"needs_gpu":true},{"label":"veto2rlf","veto_mode":2,"apply_rlf":true,"needs_gpu":true}]'),
                 _V10_LAB_CACHE_LOADED=False,
                 V10_LAB_ROWS_PATH=rows_csv, V10_LAB_REPORT_PATH=report_json)
    ns['ns'] = ns
    veto_calls.clear()
    filter_seen.clear()
    global _CUR
    _CUR = ns   # LIVE view cho mock đọc override tại call-time (fix snapshot cũ)
    exec(compile(grid_src, 'v10-grid', 'exec'), ns)
    return rows_csv, report_json, ns


rows_csv, report_json, ns6 = run_grid(skip_veto=False, have_cuda=True)
with rows_csv.open() as f:
    rows_list = list(csv.DictReader(f))
check('v10_lab_rows.csv: 12 per-stem rows (6 config chạy × 2 stems)', len(rows_list) == 12)
cols = set(rows_list[0].keys())
check('rows.csv đủ cột như validator_results.csv (+config)', VALIDATOR_COLS_EXPECT <= cols)
check('rows.csv có cột traceability (veto_mode/tight_override/apply_rlf)', {'veto_mode', 'tight_override', 'apply_rlf'} <= cols)
check('rows.csv mỗi config đủ 2 stems', {r['config'] for r in rows_list} == {'ref', 'tight_45', 'rlf_only', 'veto1', 'veto2', 'veto2rlf'} and all(sum(1 for r in rows_list if r['config'] == c) == 2 for c in {'ref', 'rlf_only'}))
rep = json.loads(report_json.read_text())
check('report.json: 6 config + meta + runtime_s + lab_env', set(rep['configs'].keys()) == {'ref', 'tight_45', 'rlf_only', 'veto1', 'veto2', 'veto2rlf'} and 'meta' in rep and 'runtime_s' in rep and 'lab_env' in rep)
check('report.json ref: deltas_vs_ref rỗng + ref_label=ref', rep['configs']['ref']['deltas_vs_ref'] == {} and rep['configs']['ref']['ref_label'] == 'ref')
check('report.json mỗi config có summary đầy đủ + veto/rlf_edges_dropped + skipped=False', all(set(['summary', 'veto_edges_dropped', 'rlf_edges_dropped', 'skipped', 'seconds']) <= set(e.keys()) for e in rep['configs'].values()))
_d = rep['configs']['rlf_only']['deltas_vs_ref']
check('report.json deltas_vs_ref đủ 6 khóa metric', set(_d.keys()) == {'adjusted_edge_jaccard', 'division_jaccard', 'proxy_score', 'div_tp', 'div_fp', 'div_fn'})
check('deltas rlf_only: adjEJ dương (bỏ cạnh FP)', _d['adjusted_edge_jaccard'] > 0 and _d['div_fp'] < 0)
check('meta.json: stems + cache_loaded + cuda + validator_base', rep['meta']['stems'] == [STEM_A, STEM_B] and rep['meta']['cache_loaded'] is False and rep['meta']['cuda'] is True and rep['meta']['valid_validator_base'] is True)
check('LAB_SKIP_VETO=False + cuda=True → KHÔNG config nào bị skip', all(not e.get('skipped') for e in rep['configs'].values()))

rows_csv2, report_json2, _ = run_grid(skip_veto=True, have_cuda=False)
rep2 = json.loads(report_json2.read_text())
skipped = {k: e.get('skip_reason') for k, e in rep2['configs'].items() if e.get('skipped')}
check('LAB_SKIP_VETO=1 → veto1/veto2/veto2rlf skip với skip_reason', set(skipped.keys()) == {'veto1', 'veto2', 'veto2rlf'} and all('LAB_SKIP_VETO' in v for v in skipped.values()))
with rows_csv2.open() as f:
    rows_list2 = list(csv.DictReader(f))
check('grid skip: rows.csv chỉ còn 6 rows (3 config CPU × 2 stems)', len(rows_list2) == 6)

rows_csv3, report_json3, _ = run_grid(skip_veto=False, have_cuda=False)
rep3 = json.loads(report_json3.read_text())
skipped3 = {k for k, e in rep3['configs'].items() if e.get('skipped')}
check('không cuda + không skip_veto → veto configs skip với lý do no cuda', skipped3 == {'veto1', 'veto2', 'veto2rlf'} and all('no cuda' in rep3['configs'][k]['skip_reason'] for k in skipped3))
shutil.rmtree(tmp6, ignore_errors=True)

# ============================================================================================
print('T7 CUDA bypass (LAB_NO_CUDA)')
cuda_src = extract('# Require a cuda device before launching gpu inference', '# Apply eight-view d4 detection tta', 'vùng CUDA check')


class _TorchNoCuda:
    class cuda:
        @staticmethod
        def is_available():
            return False


def run_cuda_check(lab_mode: bool, lab_no_cuda: bool):
    ns = {'__builtins__': __builtins__, '_torch': _TorchNoCuda, 'LAB_MODE': lab_mode, 'LAB_NO_CUDA': lab_no_cuda}
    try:
        exec(compile(cuda_src, 'cuda-check', 'exec'), ns)
        return None
    except RuntimeError as exc:
        return str(exc)


check('LAB_MODE=1 + LAB_NO_CUDA=1 + không cuda → KHÔNG raise (bypass)', run_cuda_check(True, True) is None)
check('LAB_MODE=0 + không cuda → raise RuntimeError (guard gốc có ý nghĩa)', 'CUDA GPU is required' in (run_cuda_check(False, False) or ''))
check('LAB_MODE=1 + LAB_NO_CUDA=0 + không cuda → vẫn raise (phải set cả 2)', 'CUDA GPU is required' in (run_cuda_check(True, False) or ''))

# ============================================================================================
print('T8 2 notebook ipynb — json + cell count + marker + monolith nhúng')
for path, n_cells, name in ((NOTEBOOK_COLAB, 4, 'colab'), (NOTEBOOK_CPU, 3, 'cpu')):
    nb = json.loads(path.read_text())
    check(f'{name}: json.loads PASS + {n_cells} cell đúng', len(nb['cells']) == n_cells)
    srcs = {c['id']: ''.join(c['source']) for c in nb['cells']}
    lab = srcs.get(f'v10-lab-{name}-lab', '')
    check(f'{name}: cell lab chứa marker [v10-lab-env]/[v10-lab-dump]/[v10-lab-grid]', all(m in lab for m in ('[v10-lab-env]', '[v10-lab-dump]', '[v10-lab-grid]')))
    check(f'{name}: monolith v10lab nhúng NGUYÊN VĂN vào cell lab (r\'\'\'+exec)', ('_MONOLITH_V10LAB = r\'\'\'\n' + MON + '\n\'\'\'') in lab and 'exec(compile(_MONOLITH_V10LAB' in lab)

nb_colab = json.loads(NOTEBOOK_COLAB.read_text())
setup_src = ''.join(nb_colab['cells'][1]['source'])
check('colab setup: đủ 9 slug dataset', all(slug in setup_src for slug in V10_DATASETS_EXPECT))
check('colab setup: đủ 8 stems validator', all(stem in setup_src for stem in V10_STEMS_EXPECT))
check('colab setup: phân trang files (--page-token) + 4 luồng (ThreadPoolExecutor max_workers=4)', '--page-token' in setup_src and 'ThreadPoolExecutor(max_workers=4)' in setup_src)
check('colab setup: đọc + thực thi kaggle_dependency_install_command.txt', 'kaggle_dependency_install_command.txt' in setup_src)
check('colab setup: cài wheel HOCT từ biohub-hoct-020-wheels', 'biohub-hoct-020-wheels' in setup_src and '.whl' in setup_src)
check('colab setup: %pip --upgrade kaggle>=2.2 (fix 2.0.x thiếu __main__)', '%pip install -q --upgrade "kaggle>=2.2"' in setup_src)
check('colab setup: preflight V10_KAGGLE_CMD + fallback console script shutil.which', all(t in setup_src for t in ('def _v10_kaggle_base_cmd', 'V10_KAGGLE_CMD = _v10_kaggle_base_cmd()', '[*V10_KAGGLE_CMD, *args]', 'shutil.which("kaggle")')))
check('colab setup: tổng bytes fallback cột size khi thiếu totalBytes', 'r.get("totalBytes") or r.get("size") or 0' in setup_src)
check('colab setup: token KGAT nhúng sẵn + ưu tiên Colab Secrets', 'KAGGLE_API_TOKEN = "KGAT_' in setup_src and 'KGAT_DAN_TOKEN_VAO_DAY' not in setup_src and 'userdata.get' in setup_src)
lab_colab = ''.join(nb_colab['cells'][2]['source'])
check('colab lab cell: env LAB_MODE + DEADLINE 9h + MAX_VIDEO_S 900 + VALIDATOR + HOCT_VETO 2 + RLF 1 + GRID default', all(t in lab_colab for t in ('os.environ["BIOHUB_LAB_MODE"] = "1"', 'os.environ["BIOHUB_HOCT_DEADLINE_H"] = "9"', 'os.environ["BIOHUB_HOCT_MAX_VIDEO_S"] = "900"', 'os.environ["BIOHUB_VALIDATOR_ENABLE"] = "1"', 'os.environ["BIOHUB_HOCT_VETO"] = "2"', 'os.environ["BIOHUB_RLF_ENABLE"] = "1"', 'os.environ["BIOHUB_V10_GRID"]')))
res_colab = ''.join(nb_colab['cells'][3]['source'])
check('colab results: bootstrap 10_000 + seed cố định + paired theo stem', 'N_BOOT = 10_000' in res_colab and 'default_rng' in res_colab and 'percentile' in res_colab)
check('colab results: upload dataset biohub-v10-lab-cache + version 409-fallback + try/except không crash', 'vietnguyen130593/biohub-v10-lab-cache' in res_colab and 'datasets", "version' in res_colab and 'UPLOAD LỖI' in res_colab)

nb_cpu = json.loads(NOTEBOOK_CPU.read_text())
lab_cpu = ''.join(nb_cpu['cells'][1]['source'])
check('cpu lab cell: LAB_NO_CUDA=1 + VAL_CACHE_DIR + SKIP_VETO=1', all(t in lab_cpu for t in ('os.environ["BIOHUB_LAB_NO_CUDA"] = "1"', 'os.environ["BIOHUB_VAL_CACHE_DIR"] = "/kaggle/input/biohub-v10-lab-cache/v10_lab_cache"', 'os.environ["BIOHUB_V10_SKIP_VETO"] = "1"')))
md_cpu = ''.join(nb_cpu['cells'][0]['source'])
check('cpu markdown: cảnh báo chỉ chạy khi dataset cache tồn tại', 'biohub-v10-lab-cache' in md_cpu and 'tồn tại' in md_cpu)
res_cpu = ''.join(nb_cpu['cells'][2]['source'])
check('cpu results: có bootstrap, KHÔNG upload', 'N_BOOT = 10_000' in res_cpu and 'datasets create' not in res_cpu and 'vietnguyen130593/biohub-v10-lab-cache' not in res_cpu)

# cell lab của 2 notebook dùng CHÍNH XÁC monolith đã build (không lệch bản)
_mon_txt = MONOLITH.read_text()
for path, name in ((NOTEBOOK_COLAB, 'colab'), (NOTEBOOK_CPU, 'cpu')):
    nb = json.loads(path.read_text())
    lab = next(''.join(c['source']) for c in nb['cells'] if c.get('id') == f'v10-lab-{name}-lab')
    check(f'{name}: chuỗi monolith trong cell == file cell-monolith-v10lab.py', ('_MONOLITH_V10LAB = r\'\'\'\n' + _mon_txt + '\n\'\'\'') in lab)

# ============================================================================================
print('T10 [v10-lab-roots] root override — Colab mount /kaggle/* read-only')
import re as _re10
_mon_txt10 = MONOLITH.read_text()
check('monolith: header [v10-lab-roots] + _v10_p + V10_INPUT_ROOT/V10_WORKING_ROOT env', all(t in _mon_txt10 for t in ('# ==== [v10-lab-roots]', 'def _v10_p(', "V10_INPUT_ROOT = os.environ.get('V10_INPUT_ROOT', '/kaggle/input')", "V10_WORKING_ROOT = os.environ.get('V10_WORKING_ROOT', '/kaggle/working')")))
_lit_re10 = _re10.compile(r"[fF]{0,2}['\"](/kaggle/(?:input|working)[^'\"]*)['\"]")
_i0_10 = _mon_txt10.index('# ==== [v10-lab-roots]')
_i1_10 = _mon_txt10.index("os.environ['BIOHUB_MODEL_ARTIFACTS']")
_n_wrap10 = _mon_txt10.count('_v10_p(') - 1
_n_out10 = len(_lit_re10.findall(_mon_txt10)) - len(_lit_re10.findall(_mon_txt10[_i0_10:_i1_10]))
check(f'monolith: mọi literal /kaggle/* ngoài header roots đều đã wrap trong _v10_p ({_n_out10} literal)', _n_wrap10 == _n_out10 and _n_wrap10 >= 30, f'wrap={_n_wrap10} ngoài-header={_n_out10}')
check("monolith: WORKING_DIR resolve qua _v10_p (không còn Path '/kaggle/working' trần)", "WORKING_DIR = Path(_v10_p('/kaggle/working')) if Path(_v10_p('/kaggle/working')).exists() else Path('.')" in _mon_txt10)
check('monolith: COMP_DIR candidates + discovery input_root đều qua _v10_p', "Path(_v10_p(f'/kaggle/input/competitions/{COMPETITION}'))" in _mon_txt10 and "input_root = Path(_v10_p('/kaggle/input'))" in _mon_txt10)

# functional: exec header block với env override rồi test _v10_p dịch path
_header10 = _mon_txt10[_i0_10:_i1_10]
import os as _os10
_saved10 = {k: _os10.environ.get(k) for k in ('V10_INPUT_ROOT', 'V10_WORKING_ROOT')}
try:
    _os10.environ['V10_INPUT_ROOT'] = '/tmp/fake_in'
    _os10.environ['V10_WORKING_ROOT'] = '/tmp/fake_wk'
    _ns10 = {'os': _os10}
    exec(compile(_header10, 'roots-header', 'exec'), _ns10)
    _p10 = _ns10['_v10_p']
    ok10 = (_p10('/kaggle/input/foo/bar') == '/tmp/fake_in/foo/bar'
            and _p10('/kaggle/input') == '/tmp/fake_in'
            and _p10('/kaggle/working/submission.csv') == '/tmp/fake_wk/submission.csv'
            and _p10('/kaggle/inputx/other') == '/kaggle/inputx/other'
            and _p10('relative/path') == 'relative/path'
            and _p10(None) is None)
    check('functional _v10_p: dịch đúng input/working, không dịch path gần đúng, pass-through non-str', ok10)
finally:
    for _k10, _v10 in _saved10.items():
        if _v10 is None:
            _os10.environ.pop(_k10, None)
        else:
            _os10.environ[_k10] = _v10
_ns10b = {'os': _os10}
exec(compile(_header10, 'roots-header', 'exec'), _ns10b)
_p10b = _ns10b['_v10_p']
check('functional _v10_p: KHÔNG override khi env thiếu (Kaggle: path nguyên vẹn)', _p10b('/kaggle/input/x') == '/kaggle/input/x' and _p10b('/kaggle/working/y') == '/kaggle/working/y')

check('colab setup: dò root ghi được (_v10_writable + _v10_pick_roots) + export env V10_INPUT_ROOT/V10_WORKING_ROOT', all(t in setup_src for t in ('def _v10_writable', 'def _v10_pick_roots', 'os.environ["V10_INPUT_ROOT"] = str(INPUT_ROOT)', 'os.environ["V10_WORKING_ROOT"] = str(WORKING_DIR)', '/content/kaggle/input')))
check('colab setup: skip dataset khi root read-only đã có sẵn (attached)', 'not _v10_writable(INPUT_ROOT) and _dest.exists()' in setup_src)
check('colab setup: deps command rewrite theo INPUT_ROOT (cả 2 dạng path)', setup_src.count('str(INPUT_ROOT / _slug)') >= 2)
check('colab lab: roots block dò lại khi restart runtime + mkdir + print roots', all(t in lab_colab for t in ('if "V10_INPUT_ROOT" not in os.environ', 'if "V10_WORKING_ROOT" not in os.environ', '/content/kaggle/input', '/content/kaggle/working')))
check('colab results: WORKING_DIR từ env V10_WORKING_ROOT + fallback dò /content khi thiếu report', 'os.environ.get("V10_WORKING_ROOT")' in res_colab and '/content/kaggle/working' in res_colab)
check('colab results: cảnh báo upload khi thiếu token (restart runtime)', 'thiếu KAGGLE_API_TOKEN' in res_colab)
check('cpu lab: KHÔNG set V10_INPUT_ROOT/V10_WORKING_ROOT (Kaggle dùng mặc định ver-9)', 'os.environ["V10_INPUT_ROOT"]' not in lab_cpu and 'os.environ["V10_WORKING_ROOT"]' not in lab_cpu)

# T11 [v10-lab-cli] kaggle CLI preflight — 2.0.x thiếu __main__ → upgrade >=2.2 + fallback console script
print('T11 [v10-lab-cli] preflight kaggle CLI (upgrade >=2.2 + fallback console script)')
_i_pf0 = setup_src.index('def _v10_kaggle_base_cmd')
_i_pf1 = setup_src.index('V10_KAGGLE_CMD = _v10_kaggle_base_cmd()')
_pf_src = setup_src[_i_pf0:_i_pf1]

# (a) functional nhánh chính: dò python nào có `python -m kaggle --version` exit 0 (venv sandbox 2.2.4)
import subprocess as _sp11
import sys as _sys11
import shutil as _sh11
_pf_py = None
for _cand11 in (_sys11.executable, '/home/z/.venv/bin/python', '/usr/bin/python3'):
    try:
        _rr11 = _sp11.run([_cand11, '-m', 'kaggle', '--version'], capture_output=True, text=True, timeout=180)
        if _rr11.returncode == 0:
            _pf_py = _cand11
            break
    except Exception:
        continue
if _pf_py:
    class _FakeSys11:
        executable = _pf_py
    _ns11 = {'subprocess': _sp11, 'sys': _FakeSys11(), 'shutil': _sh11, 'print': print}
    exec(compile(_pf_src, 'preflight', 'exec'), _ns11)
    _cmd11 = _ns11['_v10_kaggle_base_cmd']()
    check('functional preflight: môi trường có kaggle >=2.2 → trả [python, -m, kaggle]', _cmd11 == [_pf_py, '-m', 'kaggle'], str(_cmd11))
else:
    check('functional preflight: môi trường có kaggle >=2.2 → trả [python, -m, kaggle]', True, 'SKIP — sandbox test-env không có kaggle CLI')

# (b) functional nhánh fallback: -m fail "No module named kaggle.__main__" → console script
class _FakeRun11:
    def __init__(self, rc=0, out='', err=''):
        self.returncode, self.stdout, self.stderr = rc, out, err

class _FakeSP11:
    def run(self, cmd, **kw):
        if '-m' in cmd[:3] and cmd[cmd.index('-m') + 1:cmd.index('-m') + 2] == ['kaggle'][:1]:
            return _FakeRun11(1, '', "No module named kaggle.__main__; 'kaggle' is a package and cannot be directly executed")
        return _FakeRun11(0, 'Kaggle CLI 2.0.2', '')

_ns12 = {'subprocess': _FakeSP11(), 'sys': _sys11, 'shutil': _sh11, 'print': lambda *a, **k: None}
_ns12['shutil'] = type('_FS', (), {'which': staticmethod(lambda n: '/fake/bin/kaggle' if n == 'kaggle' else None)})()
exec(compile(_pf_src, 'preflight', 'exec'), _ns12)
_cmd12 = _ns12['_v10_kaggle_base_cmd']()
check('functional preflight: 2.0.x thiếu __main__ → fallback console script', _cmd12 == ['/fake/bin/kaggle'], str(_cmd12))

# (c) functional nhánh chết: cả -m lẫn console đều fail → RuntimeError rõ ràng
_ns13 = {'subprocess': _FakeSP11(), 'sys': _sys11, 'shutil': type('_FS', (), {'which': staticmethod(lambda n: None)})(), 'print': lambda *a, **k: None}
exec(compile(_pf_src, 'preflight', 'exec'), _ns13)
try:
    _ns13['_v10_kaggle_base_cmd']()
    check('functional preflight: cả hai fail → RuntimeError hướng dẫn', False, 'không raise')
except RuntimeError as _e13:
    check('functional preflight: cả hai fail → RuntimeError hướng dẫn', 'restart' in str(_e13).lower(), str(_e13)[:80])

check('colab results: upload dùng _v10_sp_kaggle + bắt lỗi __main__', '_v10_sp_kaggle' in res_colab and 'No module named kaggle.__main__' in res_colab)

# ============================================================================================
print('T9 ver-9 gốc giữ nguyên byte (KHÔNG sửa file ngoài ver-10-lab + download)')
ver9_sha = hashlib.sha256(VER9.read_bytes()).hexdigest()
check('sha256 ver-9/cell-monolith.py không đổi', ver9_sha == VER9_SHA256, ver9_sha)
_gg = VER9.parent / 'cell-monolith.py'
mtime_ok = True
check('cell-monolith-v10lab.py KHÔNG ghi đè lên ver-9 (file khác thư mục)', MONOLITH.resolve() != _gg.resolve())

print()
print(f'KẾT QUẢ: {PASS} PASS / {FAIL} FAIL')
sys.exit(1 if FAIL else 0)
