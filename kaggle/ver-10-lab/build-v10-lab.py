"""build-v10-lab.py — Dựng ver-10 LAB: monolith patch + 2 notebook (Colab GPU + Kaggle CPU).

V10 LAB = ver-9 monolith patch cho chế độ lab (validator + grid sweep, KHÔNG predict test /
KHÔNG ghi submission / KHÔNG audit cuối):
  [v10-lab-env]     LAB_MODE/LAB_NO_CUDA/LAB_VAL_CACHE_DIR/LAB_GRID/LAB_DUMP_DIR/LAB_SKIP_VETO
  [v10-lab-cache]   load val_stems + raw graphs + GT từ cache (BIOHUB_VAL_CACHE_DIR) thay predict
  [v10-lab-dump]    ghi v10_lab_cache/{raw_graphs,gt_bundle,meta}.json sau khi VAL_RAW_GRAPHS đầy
  [v10-lab-grid]    thay [ver9-hoct-finalize]+[ver9-rlf]+[ver9-gate]: grid tight×veto×RLF trên
                    8 stems → v10_lab_rows.csv + v10_lab_report.json + bảng so sánh
  LAB_MODE guard:   bỏ region predict-test (test_stems=[]), bỏ ghi submission base/final,
                    bỏ audit cuối (wrap `if not LAB_MODE:`), CUDA hard-require bypass khi
                    LAB_NO_CUDA=1, BIOHUB_HOCT_DEADLINE_H mặc định 9h (notebook có thể đè).

Output:
  kaggle/ver-10-lab/cell-monolith-v10lab.py   (bản patch — KHÔNG đụng ver-9 gốc)
  download/v10-lab-colab.ipynb                (4 cell: hướng dẫn + setup tải 9 dataset +
                                               8 stems train + lab + kết quả/bootstrap/upload)
  download/v10-lab-cpu.ipynb                  (3 cell cho Kaggle CPU kernel TƯƠNG LAI — replay
                                               từ dataset vietnguyen130593/biohub-v10-lab-cache)

TUYỆT ĐỐI KHÔNG push gì lên Kaggle — script chỉ ghi file local.
"""
import json
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent              # <project>/kaggle/ver-10-lab/
VER9_MONOLITH = ROOT.parent / "ver-9" / "cell-monolith.py"
LAB_GRID_BLOCK = (ROOT / "lab-grid-block.py").read_text()
OUT_MONOLITH = ROOT / "cell-monolith-v10lab.py"
DOWNLOAD = ROOT.parents[1] / "download"             # <project>/download/
OUT_COLAB = DOWNLOAD / "v10-lab-colab.ipynb"
OUT_CPU = DOWNLOAD / "v10-lab-cpu.ipynb"

V10_DEFAULT_GRID_JSON = '[{"label":"ref"},{"label":"tight_45","tight_override":4.5},{"label":"tight_50","tight_override":5.0},{"label":"tight_60","tight_override":6.0},{"label":"tight_70","tight_override":7.0},{"label":"rlf_only","apply_rlf":true},{"label":"veto1","veto_mode":1,"needs_gpu":true},{"label":"veto2","veto_mode":2,"needs_gpu":true},{"label":"veto2rlf","veto_mode":2,"apply_rlf":true,"needs_gpu":true}]'
V10_DATASETS = [
    "pilkwang/biohub-tracking-support-pack-50ep-v1",
    "pilkwang/biohub-deepcenter-unet3d-center-prior-v1",
    "pilkwang/biohub-temporal-unet3d-seed314159-v1",
    "dalloliogm/biohub-official-scorer-patched",
    "dariushafshar/biohub-local-cv-pack",
    "vietnguyen130593/biohub-v6-heldout-preds",
    "giorgosi/biohub-divnet-v2",
    "sjlee101/biohub-hoct-020-wheels",
    "musculer/biohub-hoct-general-v0-official",
]
V10_STEMS = [
    "44b6_12dfb391", "44b6_267148e4", "44b6_2a2eff9f", "44b6_341df25f",
    "6bba_062c8d37", "6bba_07e24132", "6bba_085bf656", "6bba_09961292",
]
V10_COMPETITION = "biohub-cell-tracking-during-development"
V10_PATH_WRAP_COUNT = 0  # số literal /kaggle/* được wrap trong _v10_p — điền bởi build_monolith()


def must_replace(text: str, old: str, new: str, what: str) -> str:
    if text.count(old) != 1:
        sys.exit(f"[build] THẤT BẠI ở {what}: anchor xuất hiện {text.count(old)} lần (cần 1)")
    return text.replace(old, new)


def fill(template: str, values: dict) -> str:
    """Thay placeholder @@KEY@@ — tránh f-string (cell chứa nhiều '{{' literal)."""
    out = template
    for key, val in values.items():
        token = f"@@{key}@@"
        if token not in out:
            sys.exit(f"[build] THẤT BẠI: template thiếu placeholder {token}")
        out = out.replace(token, val)
    if "@@" in out:
        idx = out.index("@@")
        sys.exit(f"[build] THẤT BẠI: còn placeholder chưa thay: {out[idx:idx + 40]!r}")
    return out


# ---------------------------------------------------------------------------
# 1. Dựng monolith v10lab từ ver-9 (bản COPY — file gốc giữ nguyên byte)
# ---------------------------------------------------------------------------

ROOTS_BLOCK_MONOLITH = '''# ==== [v10-lab-roots] root override — Google Colab: /kaggle/* mount READ-ONLY → V10_INPUT_ROOT/V10_WORKING_ROOT ====
# Image Colab mới có sẵn /kaggle/input (đôi khi cả /kaggle/working) dạng mount read-only.
# Cell setup Colab export V10_INPUT_ROOT + V10_WORKING_ROOT trỏ tới /content/kaggle/* (ghi được);
# mọi path literal '/kaggle/input…' | '/kaggle/working…' trong monolith được _v10_p dịch sang root đó lúc runtime.
# Trên Kaggle thật (kernel CPU replay): env không set → mặc định /kaggle/* → hành vi GIỐNG HỆT ver-9.
V10_INPUT_ROOT = os.environ.get('V10_INPUT_ROOT', '/kaggle/input').rstrip('/') or '/kaggle/input'
V10_WORKING_ROOT = os.environ.get('V10_WORKING_ROOT', '/kaggle/working').rstrip('/') or '/kaggle/working'


def _v10_p(p):
    # [v10-lab-roots] dịch path literal /kaggle/input… | /kaggle/working… sang root override (nếu có)
    if isinstance(p, str):
        if (p == '/kaggle/input' or p.startswith('/kaggle/input/')) and V10_INPUT_ROOT != '/kaggle/input':
            return V10_INPUT_ROOT + p[len('/kaggle/input'):]
        if (p == '/kaggle/working' or p.startswith('/kaggle/working/')) and V10_WORKING_ROOT != '/kaggle/working':
            return V10_WORKING_ROOT + p[len('/kaggle/working'):]
    return p
'''

ENV_BLOCK_TEMPLATE = """
# ==== [v10-lab-env] V10 LAB — chế độ lab: validator + grid, KHÔNG predict test / submission ====
# LAB_MODE=1        : bỏ region predict-test + ghi submission + audit cuối (chỉ validator + grid).
# LAB_NO_CUDA=1     : bypass hard-require CUDA (chạy CPU — replay cache, bỏ qua config veto).
# BIOHUB_VAL_CACHE_DIR: nếu trỏ tới thư mục có raw_graphs.json + gt_bundle.json → LOAD raw graphs
#                     + GT + val_stems từ cache THAY VÌ predict validator (bỏ qua UNet inference).
# BIOHUB_V10_GRID   : JSON list config grid (mặc định 9 config: ref + tight 4.5-7.0 + rlf + veto).
# LAB_DUMP_DIR      : WORKING_DIR/v10_lab_cache — nơi ghi cache dump ([v10-lab-dump]).
# BIOHUB_V10_SKIP_VETO=1 : bỏ qua mọi config needs_gpu (tiết kiệm thời gian, không cần HOCT).
LAB_MODE = os.environ.get('BIOHUB_LAB_MODE', '0') == '1'
LAB_NO_CUDA = os.environ.get('BIOHUB_LAB_NO_CUDA', '0') == '1'
LAB_VAL_CACHE_DIR = os.environ.get('BIOHUB_VAL_CACHE_DIR', '')
LAB_SKIP_VETO = os.environ.get('BIOHUB_V10_SKIP_VETO', '0') == '1'
LAB_FORCE_DUMP = os.environ.get('BIOHUB_LAB_FORCE_DUMP', '0') == '1'
LAB_DUMP_DIR = WORKING_DIR / 'v10_lab_cache'
V10_LAB_GRID_DEFAULT_JSON = '@@GRID_JSON@@'
try:
    LAB_GRID = json.loads(os.environ.get('BIOHUB_V10_GRID', '') or V10_LAB_GRID_DEFAULT_JSON)
except Exception as _v10_grid_error:
    print(f'[v10-lab] BIOHUB_V10_GRID không parse được ({type(_v10_grid_error).__name__}: {_v10_grid_error}) — dùng grid mặc định')
    LAB_GRID = None
if not isinstance(LAB_GRID, list) or not LAB_GRID:
    LAB_GRID = json.loads(V10_LAB_GRID_DEFAULT_JSON)
_V10_LAB_T0 = time.time()
_V10_LAB_CACHE_AVAILABLE = False
if LAB_MODE and LAB_VAL_CACHE_DIR:
    _v10_cache_probe = Path(LAB_VAL_CACHE_DIR)
    if (_v10_cache_probe / 'raw_graphs.json').is_file() and (_v10_cache_probe / 'gt_bundle.json').is_file():
        _V10_LAB_CACHE_AVAILABLE = True
        print(f'[v10-lab] cache khả dụng tại {LAB_VAL_CACHE_DIR} — sẽ load raw graphs/GT thay vì predict validator')
    else:
        print(f'[v10-lab] BIOHUB_VAL_CACHE_DIR={LAB_VAL_CACHE_DIR!r} thiếu raw_graphs.json/gt_bundle.json — predict validator như thường (GPU)')
print('[v10-lab] LAB_MODE =', LAB_MODE, '· NO_CUDA =', LAB_NO_CUDA, '· SKIP_VETO =', LAB_SKIP_VETO, '· FORCE_DUMP =', LAB_FORCE_DUMP, '· grid =', [str(_c.get('label')) for _c in LAB_GRID])
"""

CACHE_BLOCK_TEMPLATE = """
# ==== [v10-lab-cache-load] nạp val_stems + raw graphs + GT từ cache (BIOHUB_VAL_CACHE_DIR) ======
_V10_LAB_CACHE_LOADED = False
_V10_LAB_CACHE_RAW: dict = {}
_V10_LAB_CACHE_GT: dict = {}
if LAB_MODE and _V10_LAB_CACHE_AVAILABLE:
    _v10_cache_dir = Path(LAB_VAL_CACHE_DIR)
    _v10_raw_json = json.loads((_v10_cache_dir / 'raw_graphs.json').read_text())
    _v10_gt_json = json.loads((_v10_cache_dir / 'gt_bundle.json').read_text())
    _V10_LAB_CACHE_RAW = {str(stem): ({int(nid): dict(nd) for nid, nd in payload['nodes'].items()}, [dict(e) for e in payload['edges']]) for stem, payload in _v10_raw_json.items()}
    _V10_LAB_CACHE_GT = {str(stem): ({int(nid): tuple(v) for nid, v in payload['nodes_plain'].items()}, [tuple(e) for e in payload['edges_plain']], payload['t_true']) for stem, payload in _v10_gt_json.items() if stem in _V10_LAB_CACHE_RAW}
    _v10_missing_gt = sorted(set(_V10_LAB_CACHE_RAW) - set(_V10_LAB_CACHE_GT))
    if _v10_missing_gt:
        raise RuntimeError(f'[v10-lab] cache thiếu GT cho stems: {_v10_missing_gt}')
    val_stems = sorted(_V10_LAB_CACHE_RAW.keys())
    _V10_LAB_CACHE_LOADED = True
    print(f'[v10-lab] CACHE LOAD OK: {len(val_stems)} stems từ {LAB_VAL_CACHE_DIR} — bỏ qua validator prediction (UNet inference)')
"""

DUMP_BLOCK_TEMPLATE = r"""
# ==== [v10-lab-dump] Ghi cache raw graphs + GT (để replay CPU lần sau không cần predict) =======
if LAB_MODE and not _V10_LAB_CACHE_LOADED and VAL_RAW_GRAPHS:
    LAB_DUMP_DIR.mkdir(parents = True, exist_ok = True)
    _v10_dump_raw_path = LAB_DUMP_DIR / 'raw_graphs.json'
    _v10_dump_gt_path = LAB_DUMP_DIR / 'gt_bundle.json'
    _v10_dump_meta_path = LAB_DUMP_DIR / 'meta.json'
    if (_v10_dump_raw_path.exists() or _v10_dump_gt_path.exists()) and not LAB_FORCE_DUMP:
        print(f'[v10-lab] DUMP SKIP: cache đã tồn tại trong {LAB_DUMP_DIR} (set BIOHUB_LAB_FORCE_DUMP=1 để đè)')
    else:
        _v10_dump_raw = {str(_stem): {'nodes': {str(nid): dict(nd) for nid, nd in _raw_nodes.items()}, 'edges': [{'source_id': int(e['source_id']), 'target_id': int(e['target_id']), **({'edge_prob': float(e['edge_prob'])} if e.get('edge_prob') is not None else {})} for e in _raw_edges]} for _stem, (_raw_nodes, _raw_edges) in VAL_RAW_GRAPHS.items()}
        _v10_dump_gt = {str(_stem): {'nodes_plain': {str(nid): list(tv) for nid, tv in _gt_nodes.items()}, 'edges_plain': [list(et) for et in _gt_edges], 't_true': int(_t_true)} for _stem, (_gt_nodes, _gt_edges, _t_true) in VAL_GT.items()}
        _v10_dump_meta = {'stems': sorted(VAL_RAW_GRAPHS.keys()), 'experiment_tag': EXPERIMENT_TAG, 'dumped_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'source': 'validator_prediction', 'lab_env': {'LAB_MODE': LAB_MODE, 'LAB_NO_CUDA': LAB_NO_CUDA, 'LAB_SKIP_VETO': LAB_SKIP_VETO, 'LAB_VAL_CACHE_DIR': LAB_VAL_CACHE_DIR, 'grid_labels': [str(_c.get('label')) for _c in LAB_GRID]}, 'n_nodes_total': sum((len(v[0]) for v in VAL_RAW_GRAPHS.values())), 'n_edges_total': sum((len(v[1]) for v in VAL_RAW_GRAPHS.values()))}
        _v10_dump_raw_path.write_text(json.dumps(_resume_json_safe(_v10_dump_raw)))
        _v10_dump_gt_path.write_text(json.dumps(_resume_json_safe(_v10_dump_gt)))
        _v10_dump_meta_path.write_text(json.dumps(_resume_json_safe(_v10_dump_meta), indent = 2, sort_keys = True) + '\n')
        print(f'[v10-lab] DUMP OK → {LAB_DUMP_DIR} ({len(_v10_dump_raw)} stems, {_v10_dump_meta["n_nodes_total"]:,} nodes, {_v10_dump_meta["n_edges_total"]:,} edges)')
"""


def build_monolith() -> str:
    text = VER9_MONOLITH.read_text()
    if "@@" in text:
        sys.exit("[build] THẤT BẠI: ver-9 monolith chứa '@@' — placeholder xung đột")

    # P1 — EXPERIMENT_TAG ver-10 lab
    text = must_replace(
        text,
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v9'",
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_v10lab_grid'",
        "EXPERIMENT_TAG v10lab",
    )

    # P2 — [ver9] deadline: lab mặc định 9h (Colab session ~12h), notebook có thể đè trước
    text = must_replace(
        text,
        "os.environ['BIOHUB_HOCT_DEADLINE_H'] = '10.5'",
        "os.environ['BIOHUB_HOCT_DEADLINE_H'] = os.environ.get('BIOHUB_HOCT_DEADLINE_H') or '9'  # [v10-lab] lab mặc định 9h (Colab ~12h session)",
        "deadline 9h lab",
    )

    # P3 — [v10-lab-env] inject sau RESUME_DIR.mkdir (sau WORKING_DIR def)
    env_anchor = "RESUME_SCHEMA_VERSION = 'biohub_0947_live_resume_v1'\nRESUME_DIR.mkdir(parents = True, exist_ok = True)\n"
    env_block = env_anchor + fill(ENV_BLOCK_TEMPLATE, {"GRID_JSON": V10_DEFAULT_GRID_JSON})
    text = must_replace(text, env_anchor, env_block, "block [v10-lab-env]")

    # P4 — CUDA hard-require bypass khi LAB_NO_CUDA
    cuda_anchor = """# Require a cuda device before launching gpu inference
if not _torch.cuda.is_available():
    raise RuntimeError('CUDA GPU is required for this notebook. Enable a Kaggle GPU accelerator and commit again.')

print('CUDA device:', _torch.cuda.get_device_name(0))"""
    cuda_new = """# Require a cuda device before launching gpu inference
# [v10-lab] LAB_NO_CUDA=1 (kèm LAB_MODE=1): cho phép chạy CPU — replay cache / grid không veto.
if not _torch.cuda.is_available() and not (LAB_MODE and LAB_NO_CUDA):
    raise RuntimeError('CUDA GPU is required for this notebook. Enable a Kaggle GPU accelerator and commit again.')

if _torch.cuda.is_available():
    print('CUDA device:', _torch.cuda.get_device_name(0))
else:
    print('[v10-lab] CUDA không khả dụng — chế độ LAB_NO_CUDA (CPU replay, config veto sẽ bị skip)')"""
    text = must_replace(text, cuda_anchor, cuda_new, "CUDA bypass [v10-lab]")

    # P5 — test_stems = [] trong LAB_MODE (bỏ toàn bộ region predict-test)
    stems_anchor = """# Collect test movies and prepare deterministic prediction sharding
test_stems = list_test_stems()
print(f'Found {len(test_stems)} test videos')
print(test_stems[:10])"""
    stems_new = """# Collect test movies and prepare deterministic prediction sharding
if LAB_MODE:
    test_stems: list[str] = []
    print('[v10-lab] LAB_MODE: bỏ qua region predict-test (test_stems = [] — chỉ chạy validator + grid)')
else:
    test_stems = list_test_stems()
    print(f'Found {len(test_stems)} test videos')
    print(test_stems[:10])"""
    text = must_replace(text, stems_anchor, stems_new, "test_stems LAB_MODE guard")

    # P6 — test prediction state: LAB_MODE coi như đã xong (predict_seconds=0)
    state_anchor = "_test_prediction_state = _read_resume_json(TEST_PREDICTION_STATE_PATH)\n_test_prediction_ready = bool(_test_prediction_state and _test_prediction_state.get('resume_schema') == RESUME_SCHEMA_VERSION and _test_prediction_state.get('status') == 'complete' and _test_prediction_state.get('signature') == _test_prediction_signature and _resume_prediction_complete(METHOD, test_stems) and _resume_retention_guard_complete(test_stems))"
    state_new = "_test_prediction_state = {'predict_seconds': 0.0, 'lab_mode': True} if LAB_MODE else _read_resume_json(TEST_PREDICTION_STATE_PATH)\n_test_prediction_ready = True if LAB_MODE else bool(_test_prediction_state and _test_prediction_state.get('resume_schema') == RESUME_SCHEMA_VERSION and _test_prediction_state.get('status') == 'complete' and _test_prediction_state.get('signature') == _test_prediction_signature and _resume_prediction_complete(METHOD, test_stems) and _resume_retention_guard_complete(test_stems))"
    text = must_replace(text, state_anchor, state_new, "test prediction state LAB_MODE")

    # P7 — bỏ qua ghi submission base trong LAB_MODE
    base_anchor = """if _base_submission_ready or _final_submission_ready_before_base:
    _replay_stage_output(BASE_SUBMISSION_LOG_PATH)
    _base_preview_records = (_base_submission_state or {}).get('preview_records', [])

    if _base_preview_records:
        display(pd.DataFrame(_base_preview_records, columns = CSV_COLUMNS))
else:"""
    base_new = """if LAB_MODE:
    print('[v10-lab] LAB_MODE: bỏ qua ghi submission base (không predict test, không submission.csv)')
elif _base_submission_ready or _final_submission_ready_before_base:
    _replay_stage_output(BASE_SUBMISSION_LOG_PATH)
    _base_preview_records = (_base_submission_state or {}).get('preview_records', [])

    if _base_preview_records:
        display(pd.DataFrame(_base_preview_records, columns = CSV_COLUMNS))
else:"""
    text = must_replace(text, base_anchor, base_new, "base submission skip LAB_MODE")

    # P8 — val selection bỏ qua khi cache sẵn (tiết kiệm đọc toàn bộ train GT)
    text = must_replace(
        text,
        "if VALIDATOR_ENABLE and TRAIN_DIR.exists():\n    train_stems_all = sorted((p.name[:-5] for p in TRAIN_DIR.iterdir() if p.name.endswith('.zarr')))",
        "if VALIDATOR_ENABLE and TRAIN_DIR.exists() and not _V10_LAB_CACHE_AVAILABLE:  # [v10-lab] cache → val_stems lấy từ cache, bỏ selection tốn kém\n    train_stems_all = sorted((p.name[:-5] for p in TRAIN_DIR.iterdir() if p.name.endswith('.zarr')))",
        "val selection cache guard",
    )

    # P9 — [v10-lab-cache-load] sau khối chọn val_stems
    cache_anchor = "elif VALIDATOR_ENABLE:\n    pass\n\n# Merge validator prediction shards and verify complete held-out coverage"
    cache_new = "elif VALIDATOR_ENABLE:\n    pass\n" + CACHE_BLOCK_TEMPLATE + "\n# Merge validator prediction shards and verify complete held-out coverage"
    text = must_replace(text, cache_anchor, cache_new, "block [v10-lab-cache-load]")

    # P10 — validator prediction: bỏ qua khi đã load cache
    vp_anchor = "if VALIDATOR_ENABLE and val_stems:\n    val_splits_path = REPO_DIR / 'kaggle_val_splits.json'"
    vp_new = "if VALIDATOR_ENABLE and val_stems and not _V10_LAB_CACHE_LOADED:  # [v10-lab] cache → bỏ qua UNet validator prediction\n    val_splits_path = REPO_DIR / 'kaggle_val_splits.json'"
    text = must_replace(text, vp_anchor, vp_new, "validator prediction cache guard")

    # P11 — VAL_RAW_GRAPHS/VAL_GT từ cache thay vì .geff prediction
    vrg_anchor = """VAL_RAW_GRAPHS: dict[str, tuple[dict, list]] = {}
VAL_GT: dict[str, tuple[list, list, object]] = {}
if VALIDATOR_ENABLE and val_stems:
    val_pred_paths = {stem: found for stem in val_stems if (found := next((REPO_DIR / 'predictions').rglob(f'{stem}.geff'), None)) is not None}"""
    vrg_new = """VAL_RAW_GRAPHS: dict[str, tuple[dict, list]] = {}
VAL_GT: dict[str, tuple[list, list, object]] = {}
if _V10_LAB_CACHE_LOADED:
    VAL_RAW_GRAPHS = _V10_LAB_CACHE_RAW
    VAL_GT = _V10_LAB_CACHE_GT
    print(f'[v10-lab] VAL_RAW_GRAPHS/VAL_GT nạp từ cache: {len(VAL_RAW_GRAPHS)} stems, {sum(len(v[0]) for v in VAL_RAW_GRAPHS.values()):,} raw nodes')
elif VALIDATOR_ENABLE and val_stems:
    val_pred_paths = {stem: found for stem in val_stems if (found := next((REPO_DIR / 'predictions').rglob(f'{stem}.geff'), None)) is not None}"""
    text = must_replace(text, vrg_anchor, vrg_new, "VAL_RAW_GRAPHS cache branch")

    # P12 — [v10-lab-dump] sau khi VAL_RAW_GRAPHS/VAL_GT đầy
    dump_anchor = "        VAL_RAW_GRAPHS[stem] = (raw_nodes_by_id, raw_edges)\n\n# Run post-processing on cached validator graphs and score one candidate"
    dump_new = "        VAL_RAW_GRAPHS[stem] = (raw_nodes_by_id, raw_edges)\n" + DUMP_BLOCK_TEMPLATE + "\n# Run post-processing on cached validator graphs and score one candidate"
    text = must_replace(text, dump_anchor, dump_new, "block [v10-lab-dump]")

    # P13 — bỏ preview submission cuối trong LAB_MODE
    fin_anchor = """else:
    if not _final_submission_ready:
        _final_preview = pd.read_csv(SUBMISSION_PATH, nrows = 8)"""
    fin_new = """else:
    if not _final_submission_ready and not LAB_MODE:
        _final_preview = pd.read_csv(SUBMISSION_PATH, nrows = 8)"""
    text = must_replace(text, fin_anchor, fin_new, "final submission preview LAB_MODE")

    # P14 — thay [ver9-hoct-finalize] + [ver9-rlf] + [ver9-gate] bằng [v10-lab-grid]
    i_gate = text.index("# ==== [ver9-hoct-finalize]")
    i_audit = text.index("# Audit the final submission after validator-driven post-process selection")
    if not i_gate < i_audit:
        sys.exit("[build] THẤT BẠI: thứ tự block [ver9-hoct-finalize] / audit không đúng")
    text = text[:i_gate] + LAB_GRID_BLOCK.rstrip("\n") + "\n\n\n" + text[i_audit:]

    # P15 — wrap audit cuối (tới EOF) trong `if not LAB_MODE:`
    i_audit = text.index("# Audit the final submission after validator-driven post-process selection")
    tail = text[i_audit:]
    if "'''" in tail:
        sys.exit("[build] THẤT BẠI: vùng audit chứa ''' — không thể wrap an toàn")
    tail_lines = ["    " + ln if ln.strip() else ln for ln in tail.split("\n")]
    tail_wrapped = ("# [v10-lab] LAB_MODE bỏ qua toàn bộ audit cuối (không có submission.csv)\n"
                    "if not LAB_MODE:\n" + "\n".join(tail_lines).rstrip("\n")
                    + "\nelse:\n    print('[v10-lab] LAB_MODE: bỏ qua audit cuối + retention guard — pipeline lab kết thúc tại [v10-lab-grid]')\n"
                    + "    print('[v10-lab] TOTAL LAB RUNTIME: %.0fs' % (time.time() - _V10_LAB_T0))\n")
    text = text[:i_audit] + tail_wrapped

    # P16 — [v10-lab-roots] wrap mọi path literal '/kaggle/input…' | '/kaggle/working…' vào _v10_p(...)
    _path_re = re.compile(r"(?P<pre>[fF]{0,2})(?P<q>['\"])(?P<path>/kaggle/(?:input|working)[^'\"]*)(?P=q)")
    if re.search(r"[rRbBuU]{1,2}['\"](/kaggle/)", text):
        sys.exit("[build] THẤT BẠI: monolith có literal /kaggle/ với prefix r/b/u — không wrap an toàn")
    global V10_PATH_WRAP_COUNT
    V10_PATH_WRAP_COUNT = len(_path_re.findall(text))

    def _wrap_path(m):
        return "_v10_p(" + m.group("pre") + m.group("q") + m.group("path") + m.group("q") + ")"

    text = _path_re.sub(_wrap_path, text)

    # P17 — [v10-lab-roots] inject header _v10_p + V10_*_ROOT ngay sau `import os` (TRƯỚC lần dùng đầu tiên)
    text = must_replace(
        text,
        "from __future__ import annotations\nimport os\n\n",
        "from __future__ import annotations\nimport os\n\n" + ROOTS_BLOCK_MONOLITH + "\n",
        "block [v10-lab-roots]",
    )
    return text


# ---------------------------------------------------------------------------
# 2. Notebook cells (template + placeholder — KHÔNG dùng f-string cho cell code)
# ---------------------------------------------------------------------------

def to_source_lines(text: str) -> list[str]:
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        if i < len(lines) - 1:
            out.append(line + "\n")
        else:
            if line != "":
                out.append(line)
    return out


COLAB_HEADER_MD_TEMPLATE = """# V10 LAB — Grid sweep tight × HOCT-veto × RLF trên 8 stems validator (Colab GPU)

Notebook này chạy **đầy đủ pipeline validator của ver-9 trên Google Colab (T4 GPU)** nhưng
**KHÔNG predict test / KHÔNG ghi submission.csv** — chỉ chạy validator 8 stems held-out rồi
sweep 9 cấu hình hậu xử lý (grid `BIOHUB_V10_GRID`), ghi cache + kết quả, và **tự upload về
Kaggle dataset `vietnguyen130593/biohub-v10-lab-cache`** để lần sau replay trên CPU không tốn GPU.

## Cách chạy (5 bước)

1. **Runtime → Change runtime type → T4 GPU** (bắt buộc; T4 là đủ, không cần A100).
2. Token Kaggle **đã nhúng sẵn trong Cell 2** (KGAT_...) — không cần cấu hình gì thêm.
   (Tuỳ chọn: tạo Colab Secret tên `KAGGLE_API_TOKEN` thì Cell 2 sẽ ưu tiên secret đó.)
3. **Runtime → Run all** (Ctrl+F9). Notebook tự nhận diện `/kaggle/input` read-only của Colab
   và chuyển sang `/content/kaggle/input` (ghi được) — không cần sửa gì.
4. Chờ **4–8 giờ** — giữ tab mở (Colab ngắt runtime khi idle; thỉnh thoảng bấm vào tab).
   Cell 2 tải 9 dataset + 8 video train (~10–30 GB, 30–90 phút); Cell 3 cài deps + chạy
   validator 8 stems (~1–1.5h) + grid 9 config (~1.5–2.5h); Cell 4 tổng hợp + upload.
5. Xong: Cell 4 in bảng so sánh + bootstrap CI 95% và tự upload cache về Kaggle.
   Nếu upload lỗi, Cell 4 in hướng dẫn tải manual (Files → download `v10_lab_upload.zip`).

## 9 config mặc định (BIOHUB_V10_GRID)

| label | ý nghĩa |
|---|---|
| `ref` | tight hardcode 5.5/6.5 per-prefix, không veto, không RLF (baseline = v3-fast) |
| `tight_45/50/60/70` | đè global tight = 4.5 / 5.0 / 6.0 / 7.0 µm (cả 2 prefix cùng giá trị) |
| `rlf_only` | + repeat-lineage division filter (bỏ cạnh con xa của fork lặp lineage) |
| `veto1` / `veto2` | HOCT consensus veto mode 1 / mode 2 (cần GPU — skip nếu không có) |
| `veto2rlf` | veto mode 2 + RLF (cấu hình ver-9) |

Override: sửa `V10_DEFAULT_GRID_JSON` trong Cell 3 (JSON list, mỗi phần tử có `label`,
`tight_override`, `veto_mode`, `apply_rlf`, `needs_gpu`).

## Lưu ý kỹ thuật

- Notebook **KHÔNG dùng GPU quota Kaggle** — mọi tính toán trên Colab; Kaggle chỉ nhận dataset
  cache qua upload tự động của Cell 4 (không version kernel, không tốn submission).
- 8 stems validator thực tế của ver-9: @@STEMS@@.
- Kết quả: `/kaggle/working/v10_lab_cache/` (cache raw graphs + GT), `v10_lab_rows.csv`
  (per-stem per-config), `v10_lab_report.json` (summary + deltas vs ref + skip_reason).
- Cell 2 tải đúng các file `train/<stem>.*` của competition (cả .zarr chunk + .geff GT) bằng
  competitions files API phân trang + 4 luồng tải song song `-f` (mỗi file zip được giải nén
  về đúng path con).
"""

CPU_HEADER_MD = """# V10 LAB (CPU replay) — grid từ cache, không cần GPU Kaggle

⚠️ **Kernel này chỉ chạy khi dataset `vietnguyen130593/biohub-v10-lab-cache` đã tồn tại**
(upload bởi notebook Colab `v10-lab-colab.ipynb`). Chưa có cache thì kernel này KHÔNG chạy
được — không cần user làm gì, agent chính sẽ push khi cache sẵn sàng.

Yêu cầu input (gắn khi push kernel — không phải việc của user):
- dataset `vietnguyen130593/biohub-v10-lab-cache` (cache raw graphs + GT 8 stems);
- 9 dataset của ver-9 (support-pack, deepcenter, secondary-seed, official-scorer, local-cv,
  v6-heldout-preds, divnet-v2, hoct-wheels, hoct-general-v0) — DivNet/DeepCenter replay cần
  checkpoint; HOCT wheels không dùng vì `BIOHUB_V10_SKIP_VETO=1`;
- **competition `biohub-cell-tracking-during-development`** — replay hậu xử lý đọc frame
  train .zarr (gap-refine / DeepCenter / DivNet image lags).

Kernel chạy với `BIOHUB_LAB_MODE=1`, `BIOHUB_LAB_NO_CUDA=1` (bỏ hard-require CUDA),
`BIOHUB_VAL_CACHE_DIR=/kaggle/input/biohub-v10-lab-cache/v10_lab_cache` (load raw graphs
thay vì UNet inference), `BIOHUB_V10_SKIP_VETO=1` (bỏ config veto — HOCT load_model cần cuda).
Kết quả giống notebook Colab trừ các config veto (skip, ghi `skip_reason` trong report).

Ghi chú: fallback v7-heldout-preds (.geff format khác) KHÔNG hỗ trợ ở phiên bản này —
chỉ hỗ trợ format cache mới của v10-lab.
"""

COLAB_SETUP_TEMPLATE = r'''# [v10-lab-colab S2] SETUP — token Kaggle + 9 dataset + 8 stems train competition
import os
import sys
import io
import csv
import json
import time
import shutil
import zipfile
import tempfile
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- token Kaggle KGAT_... — đã nhúng sẵn; nếu có Colab Secret KAGGLE_API_TOKEN thì ưu tiên secret ---
KAGGLE_API_TOKEN = "KGAT_14164511bf6b0ba6b14ed9050ffdea66"
try:
    from google.colab import userdata  # noqa: E402
    _sec = (userdata.get("KAGGLE_API_TOKEN") or "").strip()
    if _sec.startswith("KGAT_"):
        KAGGLE_API_TOKEN = _sec
        print("[v10-lab-setup] token lấy từ Colab Secrets (ưu tiên secret)")
    else:
        print("[v10-lab-setup] dùng token nhúng sẵn trong cell")
except Exception:
    print("[v10-lab-setup] dùng token nhúng sẵn trong cell (không dùng Colab Secrets)")
assert KAGGLE_API_TOKEN and KAGGLE_API_TOKEN.startswith("KGAT_"), (
    "Chưa có token Kaggle hợp lệ! Dán token KGAT_... vào biến KAGGLE_API_TOKEN "
    "ở đầu cell này, hoặc tạo Colab Secret tên KAGGLE_API_TOKEN rồi chạy lại.")
os.environ["KAGGLE_API_TOKEN"] = KAGGLE_API_TOKEN
%pip install -q kaggle

V10_COMPETITION = "@@COMPETITION@@"
V10_DATASETS = @@DATASETS@@
V10_STEMS = @@STEMS@@


# --- chọn root GHI ĐƯỢC: image Colab mới mount /kaggle/input (đôi khi cả working) READ-ONLY --------
def _v10_writable(p):
    try:
        _probe = p / ".v10_write_probe"
        _probe.write_text("ok")
        _probe.unlink()
        return True
    except OSError:
        return False


def _v10_pick_roots():
    _inp = Path("/kaggle/input")
    try:
        _inp.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if _v10_writable(_inp) or any((_inp / _full.split("/", 1)[1]).exists() for _full in V10_DATASETS):
        _input_root, _note = _inp, "/kaggle/input ghi được hoặc đã có dataset gắn sẵn"
    else:
        _input_root = Path("/content/kaggle/input")
        _input_root.mkdir(parents=True, exist_ok=True)
        _note = "Colab: /kaggle/input là mount READ-ONLY → chuyển sang /content"
    _wrk = Path("/kaggle/working")
    try:
        _wrk.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    if _v10_writable(_wrk):
        _working_root = _wrk
    else:
        _working_root = Path("/content/kaggle/working")
        _working_root.mkdir(parents=True, exist_ok=True)
    return _input_root, _working_root, _note


INPUT_ROOT, WORKING_DIR, _root_note = _v10_pick_roots()
os.environ["V10_INPUT_ROOT"] = str(INPUT_ROOT)
os.environ["V10_WORKING_ROOT"] = str(WORKING_DIR)
print(f"[v10-lab-setup] INPUT_ROOT   = {INPUT_ROOT} ({_root_note})")
print(f"[v10-lab-setup] WORKING_ROOT = {WORKING_DIR}")
TRAIN_DEST = INPUT_ROOT / V10_COMPETITION / "train"


def v10_run_kaggle(args, check=True, timeout=3600):
    cmd = [sys.executable, "-m", "kaggle", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if check and r.returncode != 0:
        print((r.stdout or "")[-2000:])
        print((r.stderr or "")[-2000:], file=sys.stderr)
        raise RuntimeError(f"kaggle {' '.join(args[:3])} thất bại (exit {r.returncode})")
    return r


for _p in (INPUT_ROOT, WORKING_DIR):
    try:
        _p.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
print(f"[v10-lab-setup] roots sẵn sàng: input={INPUT_ROOT} · working={WORKING_DIR} (Colab)")

# --- 1) tải 9 dataset ver-9 -------------------------------------------------------------------
_t0 = time.time()
for _full in V10_DATASETS:
    _slug = _full.split("/", 1)[1]
    _dest = INPUT_ROOT / _slug
    if (_dest / ".v10_ok").exists() or (not _v10_writable(INPUT_ROOT) and _dest.exists()):
        print(f"[v10-lab-setup] dataset {_slug} đã có — bỏ qua")
        continue
    _dest.mkdir(parents=True, exist_ok=True)
    v10_run_kaggle(["datasets", "download", _full, "-p", str(_dest), "--unzip", "-q"])
    (_dest / ".v10_ok").write_text("ok")
    _mb = sum(f.stat().st_size for f in _dest.rglob("*") if f.is_file()) / 1e6
    print(f"[v10-lab-setup] dataset {_slug} OK ({_mb:.0f} MB)")
print(f"[v10-lab-setup] 9 dataset xong trong {time.time() - _t0:.0f}s")

# --- 2) dependency install command từ support pack --------------------------------------------
_dep_file = INPUT_ROOT / "biohub-tracking-support-pack-50ep-v1" / "kaggle_dependency_install_command.txt"
if _dep_file.is_file():
    _cmd_txt = _dep_file.read_text().strip()
    for _full in V10_DATASETS:  # path mount Kaggle dạng datasets/<owner>/<slug> → /kaggle/input/<slug>
        _owner, _slug = _full.split("/", 1)
        _cmd_txt = _cmd_txt.replace(f"/kaggle/input/datasets/{_owner}/{_slug}", str(INPUT_ROOT / _slug))
        _cmd_txt = _cmd_txt.replace(f"/kaggle/input/{_slug}", str(INPUT_ROOT / _slug))
    print("[v10-lab-setup] kaggle_dependency_install_command.txt:", _cmd_txt[:300])
    _r = subprocess.run(_cmd_txt, shell=True, capture_output=True, text=True)
    print(f"[v10-lab-setup] dependency install exit={_r.returncode} ({(_r.stdout or '')[-400:]})")
    if _r.returncode != 0:
        print("[v10-lab-setup] CẢNH BÁO: lệnh cài deps trả exit != 0 — monolith sẽ tự cài từ wheels (Cell 3)")
else:
    print("[v10-lab-setup] (không có kaggle_dependency_install_command.txt — monolith sẽ tự cài từ wheels)")

# --- 3) HOCT wheels (dataset sjlee101) ---------------------------------------------------------
_hoct_wheels = sorted((INPUT_ROOT / "biohub-hoct-020-wheels").rglob("*.whl"))
if _hoct_wheels:
    _r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--no-deps",
                         *[str(w) for w in _hoct_wheels]], capture_output=True, text=True)
    print(f"[v10-lab-setup] HOCT wheels {[w.name for w in _hoct_wheels]} → exit {_r.returncode}")
else:
    print("[v10-lab-setup] CẢNH BÁO: không tìm thấy .whl HOCT trong biohub-hoct-020-wheels")


# --- 4) tải competition train files CHO 8 STEMS validator --------------------------------------
def _v10_list_comp_files():
    rows = []
    token = None
    while True:
        args = ["competitions", "files", V10_COMPETITION, "-v", "--page-size", "500"]
        if token:
            args += ["--page-token", token]
        r = v10_run_kaggle(args, timeout=300)
        next_token = None
        body = []
        for ln in r.stdout.splitlines():
            if ln.startswith("Next Page Token ="):
                next_token = ln.split("=", 1)[1].strip()
            else:
                body.append(ln)
        rows.extend(list(csv.DictReader(io.StringIO("\n".join(body)))))
        print(f"[v10-lab-setup] competitions files: tổng {len(rows):,} dòng{' · next page...' if next_token else ' · HẾT'}")
        if not next_token:
            return rows
        token = next_token


_t0 = time.time()
_all_rows = _v10_list_comp_files()
_wanted = [r for r in _all_rows if any(r["name"].startswith(f"train/{s}.") for s in V10_STEMS)]
_wanted_names = [r["name"] for r in _wanted]
_total_bytes = sum(int(r.get("totalBytes") or 0) for r in _wanted)
print(f"[v10-lab-setup] cần tải {len(_wanted_names):,} file cho {len(V10_STEMS)} stems — tổng {_total_bytes / 1e9:.2f} GB")


def _v10_fetch_comp_file(name):
    tmp = Path(tempfile.mkdtemp(prefix="v10dl_"))
    try:
        v10_run_kaggle(["competitions", "download", V10_COMPETITION, "-f", name, "-p", str(tmp), "-q"], timeout=1800)
        _arts = [p for p in tmp.rglob("*") if p.is_file()]
        if not _arts:
            raise RuntimeError(f"không tải được file nào cho {name}")
        _zips = [p for p in _arts if p.suffix == ".zip"]
        _art = _zips[0] if _zips else _arts[0]
        dest = TRAIN_DEST / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(_art):
            with zipfile.ZipFile(_art) as zf:
                members = [m for m in zf.namelist() if not m.endswith("/")]
                target = None
                if name in members:
                    target = name
                elif len(members) == 1:
                    target = members[0]
                else:
                    _cand = [m for m in members if m.endswith("/" + name)]
                    if len(_cand) == 1:
                        target = _cand[0]
                if target is None:
                    raise RuntimeError(f"zip cho {name} không chứa file mong đợi: {members[:5]}")
                dest.write_bytes(zf.read(target))
        else:
            shutil.copyfile(_art, dest)
        return name, dest.stat().st_size
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_done = 0
_done_bytes = 0
_errors = []
with ThreadPoolExecutor(max_workers=4) as _pool:
    _futures = {_pool.submit(_v10_fetch_comp_file, n): n for n in _wanted_names}
    for _fut in as_completed(_futures):
        _n = _futures[_fut]
        try:
            _name, _sz = _fut.result()
            _done += 1
            _done_bytes += _sz
        except Exception as _e:
            _errors.append((_n, f"{type(_e).__name__}: {_e}"))
        if _done % 200 == 0 or _done == len(_wanted_names):
            print(f"[v10-lab-setup] tiến độ {_done}/{len(_wanted_names)} file · {_done_bytes / 1e9:.2f} GB · {time.time() - _t0:.0f}s")
if _errors:
    print(f"[v10-lab-setup] {len(_errors)} file LỖI:")
    for _n, _e in _errors[:10]:
        print("   ", _n, "→", _e)
    raise RuntimeError(f"tải competition files thất bại {len(_errors)}/{len(_wanted_names)} — xem log trên (chạy lại cell để retry)")

# --- 5) verify 8 stems mỗi stem có .zarr + .geff ------------------------------------------------
_bad = []
for _s in V10_STEMS:
    _zarr = TRAIN_DEST / f"{_s}.zarr"
    _geff = TRAIN_DEST / f"{_s}.geff"
    _zarr_ok = _zarr.is_dir() and ((_zarr / "0" / "zarr.json").is_file() or (_zarr / "zarr.json").is_file() or any(_zarr.rglob("zarr.json")))
    _geff_ok = _geff.exists()
    if not (_zarr_ok and _geff_ok):
        _bad.append((_s, f"zarr={_zarr_ok} geff={_geff_ok}"))
    else:
        print(f"[v10-lab-setup] stem {_s} OK (.zarr {sum(1 for _ in _zarr.rglob('*') if _.is_file()):,} file · .geff {'dir' if _geff.is_dir() else 'file'})")
if _bad:
    for _s, _why in _bad:
        print(f"[v10-lab-setup] LỖI stem {_s}: {_why}")
    raise RuntimeError(f"verify 8 stems thất bại: {[s for s, _ in _bad]} — chạy lại Cell 2 để retry")
print(f"[v10-lab-setup] SETUP HOÀN TẤT ({time.time() - _t0:.0f}s) — chuyển Cell 3")
'''

LAB_CELL_TEMPLATE = r"""# @@CELL_TAG@@ — env + exec monolith v10lab (validator 8 stems + grid sweep)
import os
import json
from pathlib import Path

V10_DEFAULT_GRID_JSON = @@GRID_JSON_PY@@
@@ROOTS_BLOCK@@
@@ENV_LINES@@
print("[v10-lab] env xong — grid:", [c["label"] for c in json.loads(V10_DEFAULT_GRID_JSON)])

_MONOLITH_V10LAB = r'''
@@MONOLITH@@
'''
exec(compile(_MONOLITH_V10LAB, "cell-monolith-v10lab.py", "exec"))
print("[v10-lab] monolith v10lab exec xong")
"""

COLAB_ENV_LINES = """os.environ["BIOHUB_LAB_MODE"] = "1"                 # lab: bỏ predict-test + submission + audit
os.environ["BIOHUB_HOCT_DEADLINE_H"] = "9"          # ~9h (Colab session ~12h, chừa dư upload)
os.environ["BIOHUB_HOCT_MAX_VIDEO_S"] = "900"
os.environ["BIOHUB_VALIDATOR_ENABLE"] = "1"
os.environ["BIOHUB_HOCT_VETO"] = "2"                # hook armed nhưng lab không ghi submission → không áp
os.environ["BIOHUB_RLF_ENABLE"] = "1"               # RLF áp ở mức graph trong [v10-lab-grid]
os.environ["BIOHUB_ALLOW_PIP_INSTALL"] = "1"        # Colab có internet — fallback PyPI nếu wheels thiếu
os.environ["BIOHUB_V10_GRID"] = V10_DEFAULT_GRID_JSON"""

CPU_ENV_LINES = """os.environ["BIOHUB_LAB_MODE"] = "1"
os.environ["BIOHUB_LAB_NO_CUDA"] = "1"             # bỏ hard-require CUDA (replay CPU)
os.environ["BIOHUB_VAL_CACHE_DIR"] = "/kaggle/input/biohub-v10-lab-cache/v10_lab_cache"
os.environ["BIOHUB_V10_SKIP_VETO"] = "1"           # HOCT load_model cần cuda → skip config veto
os.environ["BIOHUB_VALIDATOR_ENABLE"] = "1"
os.environ["BIOHUB_HOCT_VETO"] = "2"               # hook armed nhưng lab không ghi submission → không áp
os.environ["BIOHUB_RLF_ENABLE"] = "1"
os.environ["BIOHUB_V10_GRID"] = V10_DEFAULT_GRID_JSON"""

COLAB_ROOTS_BLOCK = '''# --- [v10-lab-roots] roots: kế thừa env từ Cell 2 (INPUT_ROOT/WORKING_ROOT); restart runtime thì dò lại ---
def _v10_writable(p):
    try:
        _probe = p / ".v10_write_probe"
        _probe.write_text("ok")
        _probe.unlink()
        return True
    except OSError:
        return False


if "V10_INPUT_ROOT" not in os.environ:
    _inp = Path("/kaggle/input")
    try:
        _inp.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    os.environ["V10_INPUT_ROOT"] = str(_inp) if _v10_writable(_inp) else "/content/kaggle/input"
if "V10_WORKING_ROOT" not in os.environ:
    _wrk = Path("/kaggle/working")
    try:
        _wrk.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    os.environ["V10_WORKING_ROOT"] = str(_wrk) if _v10_writable(_wrk) else "/content/kaggle/working"
for _p in (os.environ["V10_INPUT_ROOT"], os.environ["V10_WORKING_ROOT"]):
    Path(_p).mkdir(parents=True, exist_ok=True)
print("[v10-lab] roots:", os.environ["V10_INPUT_ROOT"], "·", os.environ["V10_WORKING_ROOT"])'''

CPU_ROOTS_BLOCK = '''# [v10-lab-roots] kernel Kaggle CPU: /kaggle/input gắn sẵn dataset cache — KHÔNG override root (mặc định ver-9).'''

RESULTS_TEMPLATE = r'''# @@CELL_TAG@@ — bảng + bootstrap CI 95% paired@@UPLOAD_SUFFIX@@
import json
import os
import time
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import display

_v10_wrk_env = (os.environ.get("V10_WORKING_ROOT") or "").strip()
if _v10_wrk_env and Path(_v10_wrk_env).is_dir():
    WORKING_DIR = Path(_v10_wrk_env)
elif Path("/kaggle/working").exists():
    WORKING_DIR = Path("/kaggle/working")
else:
    WORKING_DIR = Path(".")
if not (WORKING_DIR / "v10_lab_report.json").is_file():  # restart runtime giữa chừng → dò nơi có report
    for _alt in (Path("/content/kaggle/working"), Path(".")):
        if (_alt / "v10_lab_report.json").is_file():
            print(f"[v10-lab-result] report tìm thấy tại {_alt} (khác root mặc định)")
            WORKING_DIR = _alt
            break
REPORT_PATH = WORKING_DIR / "v10_lab_report.json"
ROWS_PATH = WORKING_DIR / "v10_lab_rows.csv"
assert REPORT_PATH.is_file(), f"thiếu {REPORT_PATH} — cell lab chưa chạy xong?"
assert ROWS_PATH.is_file(), f"thiếu {ROWS_PATH} — cell lab chưa chạy xong?"
REPORT = json.loads(REPORT_PATH.read_text())
ROWS = pd.read_csv(ROWS_PATH)
REF_LABEL = REPORT["meta"].get("ref_label")
print(f"[v10-lab-result] ref = {REF_LABEL!r} · {len(REPORT['meta']['stems'])} stems · "
      f"cache_loaded={REPORT['meta'].get('cache_loaded')} · cuda={REPORT['meta'].get('cuda')}")

# --- bảng tổng hợp mỗi config -------------------------------------------------------------------
_tbl = []
for _label, _e in REPORT["configs"].items():
    if _e.get("skipped"):
        _tbl.append({"config": _label, "adjEJ": np.nan, "d_adjEJ_vs_ref": np.nan, "proxy": np.nan,
                     "div_tp": np.nan, "div_fp": np.nan, "div_fn": np.nan,
                     "veto_edges_dropped": np.nan, "rlf_edges_dropped": np.nan,
                     "note": "SKIP: " + str(_e.get("skip_reason"))})
    else:
        _s = _e["summary"]
        _tbl.append({"config": _label, "adjEJ": round(_s["adjusted_edge_jaccard"], 6),
                     "d_adjEJ_vs_ref": round(_e["deltas_vs_ref"].get("adjusted_edge_jaccard", 0.0), 6),
                     "proxy": round(_s["proxy_score"], 6), "div_tp": _s["div_tp"], "div_fp": _s["div_fp"],
                     "div_fn": _s["div_fn"], "veto_edges_dropped": _e["veto_edges_dropped"],
                     "rlf_edges_dropped": _e["rlf_edges_dropped"], "note": ""})
SUMMARY_TABLE = pd.DataFrame(_tbl)
print("[v10-lab-result] BẢNG TỔNG HỢP:")
display(SUMMARY_TABLE)

# --- bootstrap CI 95% paired theo stem (10_000 resample, seed cố định) ---------------------------
N_BOOT = 10_000
BOOT_SEED = 20260916
_piv_adj = ROWS.pivot_table(index="stem", columns="config", values="adjusted_edge_jaccard")
_piv_proxy = ROWS.pivot_table(index="stem", columns="config", values="proxy_score")
_boot_rows = []
if REF_LABEL in _piv_adj.columns:
    _rng = np.random.default_rng(BOOT_SEED)
    _n = len(_piv_adj)
    _idx = _rng.integers(0, _n, size=(N_BOOT, _n))
    for _col in _piv_adj.columns:
        if _col == REF_LABEL:
            continue
        _d_adj = (_piv_adj[_col] - _piv_adj[REF_LABEL]).to_numpy()
        _d_prx = (_piv_proxy[_col] - _piv_proxy[REF_LABEL]).to_numpy()
        _m_adj = _d_adj[_idx].mean(axis=1)
        _m_prx = _d_prx[_idx].mean(axis=1)
        _boot_rows.append({"config": _col, "mean_d_adjEJ": float(_d_adj.mean()),
                           "ci95_d_adjEJ_lo": float(np.percentile(_m_adj, 2.5)),
                           "ci95_d_adjEJ_hi": float(np.percentile(_m_adj, 97.5)),
                           "mean_d_proxy": float(_d_prx.mean()),
                           "ci95_d_proxy_lo": float(np.percentile(_m_prx, 2.5)),
                           "ci95_d_proxy_hi": float(np.percentile(_m_prx, 97.5)),
                           "ci95_d_adjEJ_duong": bool(np.percentile(_m_adj, 2.5) > 0),
                           "ci95_d_adjEJ_am": bool(np.percentile(_m_adj, 97.5) < 0)})
BOOTSTRAP_TABLE = pd.DataFrame(_boot_rows)
print(f"[v10-lab-result] BOOTSTRAP CI 95% paired per-stem ({N_BOOT:,} resample, seed {BOOT_SEED}):")
display(BOOTSTRAP_TABLE if not BOOTSTRAP_TABLE.empty else pd.DataFrame([{"note": "chỉ có 1 config (ref) — không có cặp nào"}]))
@@UPLOAD_PART@@
print("[v10-lab-result] XONG.")
'''

UPLOAD_PART = '''
# --- upload cache + kết quả về Kaggle dataset vietnguyen130593/biohub-v10-lab-cache ----------
UPLOAD_RESULTS = True
if UPLOAD_RESULTS:
    if not (os.environ.get("KAGGLE_API_TOKEN") or "").startswith("KGAT_"):
        print("[v10-lab-upload] CẢNH BÁO: thiếu KAGGLE_API_TOKEN (restart runtime?) — chạy lại Cell 2 để set token rồi upload")
    try:
        import subprocess as _sp
        import sys as _sys
        _up = Path("/content/v10_lab_upload")
        shutil.rmtree(_up, ignore_errors=True)
        _up.mkdir(parents=True, exist_ok=True)
        if (WORKING_DIR / "v10_lab_cache").is_dir():
            shutil.copytree(WORKING_DIR / "v10_lab_cache", _up / "v10_lab_cache")
        for _f in ("v10_lab_report.json", "v10_lab_rows.csv", "validator_results.csv"):
            if (WORKING_DIR / _f).is_file():
                shutil.copy2(WORKING_DIR / _f, _up / _f)
        (_up / "dataset-metadata.json").write_text(json.dumps({
            "title": "biohub-v10-lab-cache",
            "id": "vietnguyen130593/biohub-v10-lab-cache",
            "licenses": [{"name": "CC0-1.0"}],
        }, indent=2))
        _r = _sp.run([_sys.executable, "-m", "kaggle", "datasets", "create", "-p", str(_up)],
                     capture_output=True, text=True)
        _blob = (_r.stdout or "") + (_r.stderr or "")
        if _r.returncode == 0:
            print("[v10-lab-upload] ĐÃ TẠO dataset vietnguyen130593/biohub-v10-lab-cache (create OK)")
        elif "409" in _blob or "already exists" in _blob.lower() or "conflict" in _blob.lower():
            _iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _r2 = _sp.run([_sys.executable, "-m", "kaggle", "datasets", "version",
                           "-p", str(_up), "-m", f"lab run {_iso}", "-r", "skip"],
                          capture_output=True, text=True)
            print(f"[v10-lab-upload] version -m 'lab run {_iso}' exit={_r2.returncode}")
            if _r2.returncode != 0:
                print((_r2.stdout or "")[-1500:])
                print((_r2.stderr or "")[-1500:])
                raise RuntimeError("kaggle datasets version thất bại")
            print("[v10-lab-upload] ĐÃ VERSION dataset biohub-v10-lab-cache")
        else:
            print(_blob[-1500:])
            raise RuntimeError(f"kaggle datasets create thất bại (exit {_r.returncode})")
    except Exception as _e:
        print(f"[v10-lab-upload] UPLOAD LỖI ({type(_e).__name__}: {_e}) — KHÔNG crash notebook.")
        print("[v10-lab-upload] TẢI MANUAL: bấm thư mục Files bên trái → chuột phải thư mục")
        print("                    /content/v10_lab_upload → Download → gửi file zip cho agent chính.")
else:
    print("[v10-lab-upload] UPLOAD_RESULTS = False — bỏ qua upload")'''


# ---------------------------------------------------------------------------
# 3. Kiểm thử tĩnh
# ---------------------------------------------------------------------------

def static_checks(monolith_src: str, colab_nb: dict, cpu_nb: dict) -> None:
    py_compile.compile(str(OUT_MONOLITH), doraise=True)
    print("[check] py_compile cell-monolith-v10lab.py PASS")
    mon_required = [
        "[v10-lab-env] V10 LAB",
        "LAB_MODE = os.environ.get('BIOHUB_LAB_MODE', '0') == '1'",
        "LAB_NO_CUDA = os.environ.get('BIOHUB_LAB_NO_CUDA', '0') == '1'",
        "LAB_VAL_CACHE_DIR = os.environ.get('BIOHUB_VAL_CACHE_DIR', '')",
        "LAB_SKIP_VETO = os.environ.get('BIOHUB_V10_SKIP_VETO', '0') == '1'",
        "LAB_DUMP_DIR = WORKING_DIR / 'v10_lab_cache'",
        "BIOHUB_V10_GRID",
        "[v10-lab-cache-load] nạp val_stems",
        "_V10_LAB_CACHE_LOADED",
        "[v10-lab-dump] Ghi cache raw graphs",
        "raw_graphs.json",
        "gt_bundle.json",
        "meta.json",
        "BIOHUB_LAB_FORCE_DUMP",
        "[v10-lab-grid] Grid sweep",
        "def v10_score_config",
        "def ver9_rlf_edges",
        "v10_lab_rows.csv",
        "v10_lab_report.json",
        "deltas_vs_ref",
        "skip_reason",
        "test_stems: list[str] = []",
        "if not LAB_MODE:",
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_v10lab_grid'",
        "os.environ['BIOHUB_HOCT_DEADLINE_H'] = os.environ.get('BIOHUB_HOCT_DEADLINE_H') or '9'",
        "[v10-lab-roots]",
        "def _v10_p",
        "V10_INPUT_ROOT = os.environ.get('V10_INPUT_ROOT', '/kaggle/input')",
        "V10_WORKING_ROOT = os.environ.get('V10_WORKING_ROOT', '/kaggle/working')",
    ]
    for token in mon_required:
        if token not in monolith_src:
            sys.exit(f"[check] THIẾU mấu [v10-lab] trong monolith: {token!r}")
    for removed in ("# ==== [ver9-hoct-finalize]", "# ==== [ver9-rlf]", "# ==== [ver9-gate]", "VER9_GATE_PATH", "RLF_REPORT_PATH", "def ver9_score_final", "\n_hv_finalize()", "RLF_ENABLE = os.environ"):
        if removed in monolith_src:
            sys.exit(f"[check] THẤT BẠI: block production {removed!r} còn trong bản lab")
    for kept in ("def _hv_veto_video", "def filter_output_graph", "def score_sample", "def aggregate_official", "def write_test_submission", "PP_CANDIDATES: dict[str, dict] = {}", "def _hv_install_hook"):
        if kept not in monolith_src:
            sys.exit(f"[check] THẤT BẠI: thiếu hàm production {kept!r}")
    print(f"[check] {len(mon_required)} mấu [v10-lab] đủ + block [ver9] submission-level đã bỏ + hàm production giữ nguyên")

    # ---- [v10-lab-roots] — wrap count + không sót literal /kaggle/* ngoài header roots ----
    _n_wrapped = monolith_src.count("_v10_p(") - 1  # trừ dòng `def _v10_p(`
    if _n_wrapped != V10_PATH_WRAP_COUNT:
        sys.exit(f"[check] THẤT BẠI: literal /kaggle/* đã wrap = {_n_wrapped} ≠ transform {V10_PATH_WRAP_COUNT}")
    _roots_i0 = monolith_src.index("# ==== [v10-lab-roots]")
    _roots_i1 = monolith_src.index("os.environ['BIOHUB_MODEL_ARTIFACTS']")
    _literal_re = re.compile(r"[fF]{0,2}['\"](/kaggle/(?:input|working)[^'\"]*)['\"]")
    _header_n = len(_literal_re.findall(monolith_src[_roots_i0:_roots_i1]))
    _total_n = len(_literal_re.findall(monolith_src))
    if _total_n - _header_n != V10_PATH_WRAP_COUNT:
        sys.exit(f"[check] THẤT BẠI: literal /kaggle/* ngoài header roots = {_total_n - _header_n} ≠ wrap {V10_PATH_WRAP_COUNT} — có literal chưa wrap")
    print(f"[check] [v10-lab-roots] {V10_PATH_WRAP_COUNT} literal /kaggle/* wrap trong _v10_p + header roots {_header_n} literal khóa mặc định")

    # ---- notebook checks
    for name, nb, n_cells in (("colab", colab_nb, 4), ("cpu", cpu_nb, 3)):
        json.loads(json.dumps(nb))
        if len(nb["cells"]) != n_cells:
            sys.exit(f"[check] notebook {name} có {len(nb['cells'])} cell (cần {n_cells})")
        _srcs = {c["id"]: "".join(c["source"]) for c in nb["cells"]}
        _lab = _srcs[f"v10-lab-{name}-lab"]
        for marker in ("def v10_score_config", "[v10-lab-dump]", "[v10-lab-grid]", "[v10-lab-env]"):
            if marker not in _lab:
                sys.exit(f"[check] notebook {name}: cell lab thiếu marker {marker!r}")
        if "_MONOLITH_V10LAB = r'''\n" + monolith_src + "\n'''" not in _lab:
            sys.exit(f"[check] notebook {name}: nguồn monolith nhúng không khớp nguyên văn")
        if "exec(compile(_MONOLITH_V10LAB" not in _lab:
            sys.exit(f"[check] notebook {name}: thiếu exec monolith")
        print(f"[check] notebook {name}: {n_cells} cell · monolith nhúng nguyên văn ({len(_lab.splitlines())} dòng) · exec OK")
    _setup = "".join(colab_nb["cells"][1]["source"])
    for slug in V10_DATASETS:
        if slug not in _setup:
            sys.exit(f"[check] cell setup Colab thiếu dataset {slug}")
    for stem in V10_STEMS:
        if stem not in _setup:
            sys.exit(f"[check] cell setup Colab thiếu stem {stem}")
    for token in ("--page-token", "ThreadPoolExecutor(max_workers=4)", "kaggle_dependency_install_command.txt", "biohub-hoct-020-wheels",
                  'os.environ["V10_INPUT_ROOT"]', 'os.environ["V10_WORKING_ROOT"]', "/content/kaggle/input", "_v10_writable"):
        if token not in _setup:
            sys.exit(f"[check] cell setup Colab thiếu {token!r}")
    _cpu_lab = "".join(cpu_nb["cells"][1]["source"])
    if "/kaggle/input/biohub-v10-lab-cache/v10_lab_cache" not in _cpu_lab or "BIOHUB_LAB_NO_CUDA" not in _cpu_lab:
        sys.exit("[check] cell lab CPU thiếu BIOHUB_VAL_CACHE_DIR / BIOHUB_LAB_NO_CUDA")
    _colab_lab_src = "".join(colab_nb["cells"][2]["source"])
    for token in ('os.environ["V10_INPUT_ROOT"]', "/content/kaggle/input", "_v10_writable"):
        if token not in _colab_lab_src:
            sys.exit(f"[check] cell lab Colab thiếu roots block {token!r}")
    _cpu_lab_src2 = "".join(cpu_nb["cells"][1]["source"])
    if 'os.environ["V10_INPUT_ROOT"]' in _cpu_lab_src2:
        sys.exit("[check] THẤT BẠI: cell lab CPU KHÔNG được set V10_INPUT_ROOT (Kaggle dùng /kaggle/input mặc định)")
    _colab_res = "".join(colab_nb["cells"][3]["source"])
    for token in ("N_BOOT = 10_000", "default_rng", "percentile", "vietnguyen130593/biohub-v10-lab-cache", "datasets", "version"):
        if token not in _colab_res:
            sys.exit(f"[check] cell kết quả Colab thiếu {token!r}")
    if 'os.environ.get("V10_WORKING_ROOT")' not in _colab_res or "/content/kaggle/working" not in _colab_res:
        sys.exit("[check] cell kết quả Colab thiếu resolve WORKING_ROOT từ env + fallback /content")
    _cpu_res = "".join(cpu_nb["cells"][2]["source"])
    if "N_BOOT = 10_000" not in _cpu_res or "biohub-v10-lab-cache" in _cpu_res:
        sys.exit("[check] cell kết quả CPU: phải có bootstrap, KHÔNG có upload")
    print("[check] setup Colab: 9 dataset + 8 stems + phân trang + 4 luồng + deps + HOCT wheels OK")
    print("[check] cell CPU cache env OK · bootstrap cả 2 · upload chỉ ở Colab")


# ---------------------------------------------------------------------------
# 4. main
# ---------------------------------------------------------------------------

def build_notebook(cells: list) -> dict:
    return {"cells": cells,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python", "version": "3.11"}},
            "nbformat": 4, "nbformat_minor": 5}


def main() -> int:
    monolith_src = build_monolith()
    if "'''" in monolith_src:
        sys.exit("[build] THẤT BẠI: monolith chứa ''' — không nhúng cell r''' được")
    OUT_MONOLITH.write_text(monolith_src)
    print(f"[build] ĐÃ GHI {OUT_MONOLITH} ({len(monolith_src.splitlines())} dòng; ver-9 gốc {len(VER9_MONOLITH.read_text().splitlines())} dòng)")

    header_md = fill(COLAB_HEADER_MD_TEMPLATE, {"STEMS": ", ".join(V10_STEMS)})
    setup_src = fill(COLAB_SETUP_TEMPLATE, {
        "COMPETITION": V10_COMPETITION,
        "DATASETS": json.dumps(V10_DATASETS, indent=4),
        "STEMS": json.dumps(V10_STEMS),
    })
    colab_lab_src = fill(LAB_CELL_TEMPLATE, {
        "CELL_TAG": "v10-lab-colab S3 LAB",
        "GRID_JSON_PY": json.dumps(V10_DEFAULT_GRID_JSON),
        "ROOTS_BLOCK": COLAB_ROOTS_BLOCK,
        "ENV_LINES": COLAB_ENV_LINES,
        "MONOLITH": monolith_src,
    })
    cpu_lab_src = fill(LAB_CELL_TEMPLATE, {
        "CELL_TAG": "v10-lab-cpu S2 LAB CPU",
        "GRID_JSON_PY": json.dumps(V10_DEFAULT_GRID_JSON),
        "ROOTS_BLOCK": CPU_ROOTS_BLOCK,
        "ENV_LINES": CPU_ENV_LINES,
        "MONOLITH": monolith_src,
    })
    colab_results_src = fill(RESULTS_TEMPLATE, {
        "CELL_TAG": "v10-lab-colab S4 KẾT QUẢ",
        "UPLOAD_SUFFIX": " + upload Kaggle",
        "UPLOAD_PART": UPLOAD_PART,
    })
    cpu_results_src = fill(RESULTS_TEMPLATE, {
        "CELL_TAG": "v10-lab-cpu S3 KẾT QUẢ",
        "UPLOAD_SUFFIX": "",
        "UPLOAD_PART": "print('[v10-lab-result] (kernel CPU — không upload; đọc report trực tiếp từ output kernel)')",
    })

    colab_nb = build_notebook([
        {"cell_type": "markdown", "id": "v10-lab-colab-header", "metadata": {}, "source": to_source_lines(header_md)},
        {"cell_type": "code", "id": "v10-lab-colab-setup", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source_lines(setup_src)},
        {"cell_type": "code", "id": "v10-lab-colab-lab", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source_lines(colab_lab_src)},
        {"cell_type": "code", "id": "v10-lab-colab-results", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source_lines(colab_results_src)},
    ])
    cpu_nb = build_notebook([
        {"cell_type": "markdown", "id": "v10-lab-cpu-header", "metadata": {}, "source": to_source_lines(CPU_HEADER_MD)},
        {"cell_type": "code", "id": "v10-lab-cpu-lab", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source_lines(cpu_lab_src)},
        {"cell_type": "code", "id": "v10-lab-cpu-results", "metadata": {}, "execution_count": None, "outputs": [], "source": to_source_lines(cpu_results_src)},
    ])

    static_checks(monolith_src, colab_nb, cpu_nb)

    DOWNLOAD.mkdir(parents=True, exist_ok=True)
    OUT_COLAB.write_text(json.dumps(colab_nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT_CPU.write_text(json.dumps(cpu_nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n[build] ĐÃ GHI {OUT_COLAB} ({OUT_COLAB.stat().st_size / 1024:.0f} KB)")
    print(f"[build] ĐÃ GHI {OUT_CPU} ({OUT_CPU.stat().st_size / 1024:.0f} KB)")
    print("[build] KHÔNG push gì lên Kaggle — chỉ ghi file local. Unit test: python3 test-v10-lab.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
