# ============================================================================
# WAVE-1 DRIVER (phần 1: header + env + bootstrap) — file này được build-wave1.py
# ghép với các slice NGUYÊN VĂN từ kaggle/ver-7b/cell-monolith.py tại marker
# # (marker @@SLICES@@ nằm cuối file). Kết quả: wave1-sweep.py chạy trên Kaggle CPU kernel
# "biohub-ver8-wave1" — thực hiện E0 (gate-audit + grid), E1 (system-view
# official eval), E2 (PPSWEEP-2), E3 (chẩn đoán 2 video xấu) — 0 GPU quota.
#
# Nguyên tắc: MỌI logic postprocess/scoring là slice byte-exact từ monolith
# ver-7b (đã chạy 0.947/ver-7b) — chỉ code THÊM được đánh dấu [wave1].
# ============================================================================
from __future__ import annotations
import os as _os
import sys as _sys
import time as _time
import json as _json
import math as _math
import traceback as _tb
from pathlib import Path as _Path

WAVE1_T0 = _time.time()
WAVE1_TAG = 'wave1_e0e1e2e3_v1'
WAVE1_OUT = _Path(_os.environ.get('BIOHUB_WAVE1_OUT', '/kaggle/working'))
WAVE1_DEADLINE_SECONDS = float(_os.environ.get('BIOHUB_WAVE1_DEADLINE_SECONDS', '30600'))  # 8,5h
WAVE1_STEMS_DEFAULT = ('44b6_12dfb391,44b6_267148e4,44b6_2a2eff9f,44b6_341df25f,'
                       '6bba_062c8d37,6bba_07e24132,6bba_085bf656,6bba_09961292')


def wave1_log(msg: str) -> None:
    print(f'[wave1 +{_time.time() - WAVE1_T0:7.0f}s] {msg}', flush=True)


def wave1_time_left() -> float:
    return WAVE1_DEADLINE_SECONDS - (_time.time() - WAVE1_T0)


def wave1_dump_json(name: str, payload) -> None:
    path = WAVE1_OUT / name
    path.write_text(_json.dumps(payload, indent=2, sort_keys=False, default=str) + '\n')
    wave1_log(f'GHI {path} ({path.stat().st_size} bytes)')


# ---------------------------------------------------------------------------
# ENV — cấu hình production ver-7 (Reyhan port 0.947). Lưu ý quan trọng:
# đây là env của VER-7 (KHÔNG phải ver-7b): tau 0.6, diverge 2.25, KHÔNG divnet.
# [wave1] duy nhất khác production: DEEPCENTER_SCORE_CACHE_MAX_FRAMES 512 (knob
# cache thuần, không đổi kết quả) và DIVNET tắt ở tầng global (E0 nạp thủ công).
# ---------------------------------------------------------------------------
_env = _os.environ
_env['BIOHUB_DET_THRESHOLD'] = '0.965'
_env['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '6.0'
_env['BIOHUB_MOTION_RELINK_RELAXED_UM'] = '10.0'
_env['BIOHUB_MOTION_RELINK_LEARNED_BONUS'] = '1.0'
_env['BIOHUB_GAP2_MAX_STEP_UM'] = '4.4'
_env['BIOHUB_GAP_CLOSE_REUSE_UM'] = '3.2'
_env['BIOHUB_GAP_CLOSE_MAX_GAP'] = '2'
_env['BIOHUB_GAP_CLOSE_UM'] = '5.0'
_env['BIOHUB_GAP_DENSITY_ADAPTIVE'] = '1'
_env['BIOHUB_GAP_DENSITY_REFERENCE_UM'] = '6.5'
_env['BIOHUB_GAP_DENSITY_GAIN'] = '0.040'
_env['BIOHUB_GAP_DENSITY_MAX_STEP_DELTA_UM'] = '0.125'
_env['BIOHUB_GAP_DENSITY_NEIGHBORS'] = '3'
_env['BIOHUB_OUTPUT_MIN_TRACK_LEN'] = '6'
_env['BIOHUB_OUTPUT_KEEP_DIVISION_COMPONENTS'] = '1'
_env['BIOHUB_OUTPUT_GAP2_RECOVERY'] = '1'
_env['BIOHUB_SAFE_DIV_MAX_UM'] = '9.0'
_env['BIOHUB_SAFE_DIV_SISTER_MAX_UM'] = '14.0'
_env['BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU'] = '0.6'
_env['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '2.25'
_env['BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM'] = '10.0'
_env['BIOHUB_SAFE_DIV_FRAME_FRAC_CAP'] = '0.0076'
_env['BIOHUB_SAFE_DIV_GLOBAL_FRAC_CAP'] = '0.00375'
_env['BIOHUB_ADAPTIVE_SHORT_TRACK_RESCUE'] = '1'
_env['BIOHUB_SHORT_TRACK_RESCUE_MIN_LEN'] = '4'
_env['BIOHUB_SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB'] = '0.88'
_env['BIOHUB_SHORT_TRACK_RESCUE_MAX_MEAN_EDGE_DIST_UM'] = '3.0'
_env['BIOHUB_SHORT_TRACK_RESCUE_MAX_NODES_FRAC'] = '0.012'
_env['BIOHUB_SHORT_TRACK_RESCUE_MAX_NODES_ABS'] = '120'
_env['BIOHUB_USE_DEEPCENTER_VETO'] = '1'
_env['BIOHUB_REQUIRE_DEEPCENTER_VETO'] = '1'
_env['BIOHUB_DEEPCENTER_EXPECTED_EPOCH'] = '2'
_env['BIOHUB_DEEPCENTER_GAP_CONFIRM_MIN_SPAN_UM'] = '8.5'
_env['BIOHUB_DEEPCENTER_GAP_VETO'] = '1'
_env['BIOHUB_DEEPCENTER_GAP_THRESHOLD'] = '0.25'
_env['BIOHUB_DEEPCENTER_SAFE_DIV_VETO'] = '1'
_env['BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD'] = '0.20'
_env['BIOHUB_DEEPCENTER_SCORE_CACHE_MAX_FRAMES'] = '512'
_env['BIOHUB_DIVNET_ENABLE'] = '0'
_env['BIOHUB_DIVNET_REQUIRE'] = '0'
# E1 selected overrides của ver-7 (ppsweep đã chọn khi chạy 0.947):
E1_SELECTED = {'MOTION_RELINK_TIGHT_UM': 5.5, 'DEEPCENTER_GAP_THRESHOLD': 0.35}

# ---------------------------------------------------------------------------
# [wave1] BOOTSTRAP: wheel offline (tái hiện pattern biohub-eval-v6 v3) + tìm
# các input (scorer, train dir, preds, deepcenter ckpt, divnet ckpt).
# ---------------------------------------------------------------------------
import importlib.util
import subprocess


def _wave1_missing(mod: str) -> bool:
    try:
        return importlib.util.find_spec(mod) is None
    except Exception:
        return True


def _wave1_install_offline_wheels() -> None:
    if not _wave1_missing('tracksdata'):
        wave1_log('tracksdata sẵn có — bỏ qua cài wheel offline')
        return
    specs = ['tracksdata', 'zarr>=3.0.10,<4', 'geff>=1.1.3.1.1', 'geff-spec<1.2',
             'ilpy>=0.5.1', 'pyscipopt',
             'polars>=1.36', 'blosc2', 'dask', 'imagecodecs', 'scikit-image>=0.24',
             'pyarrow', 'rustworkx>=0.17.1', 'sqlalchemy>=2', 'numcodecs>=0.13,<0.16',
             'donfig>=0.8', 'google-crc32c>=1.5', 'bidict>=0.23.1', 'psygnal>=0.14',
             'rich', 'networkx>=3.2.1', 'pydantic>=2.11', 'pydantic-core',
             'annotated-types', 'typing-extensions>=4.13', 'typing-inspection',
             'polars-runtime-32', 'ndindex', 'msgpack', 'numexpr', 'deprecated',
             'wrapt', 'imageio', 'pillow', 'tifffile', 'lazy-loader', 'tqdm',
             'markdown-it-py', 'pygments', 'click', 'cloudpickle', 'fsspec', 'partd',
             'locket', 'toolz', 'pyyaml']
    wheel_dirs = []
    for dp, dn, fn in _os.walk('/kaggle/input'):
        if any(f.endswith('.whl') for f in fn):
            wheel_dirs.append(dp)
    if not wheel_dirs:
        raise RuntimeError('Không tìm thấy wheel .whl nào trong /kaggle/input — gắn '
                           'dataset pilkwang/biohub-tracking-support-pack-50ep-v1.')
    cmd = [_sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
           '--force-reinstall']
    for d in wheel_dirs:
        cmd.extend(['--find-links', d])
    cmd.extend(specs)
    wave1_log(f'cài offline từ {len(wheel_dirs)} thư mục wheel...')
    r = subprocess.run(cmd, text=True, capture_output=True)
    if r.returncode != 0:
        print((r.stdout or '')[-1500:])
        print((r.stderr or '')[-1500:])
        raise RuntimeError('pip install offline thất bại — xem log trên.')
    wave1_log('cài offline OK')


_wave1_install_offline_wheels()

# --- tìm các input -----------------------------------------------------------
_INPUT_ROOT = _Path('/kaggle/input')


def _wave1_find_scorer_root():
    best = None
    for dp, dn, fn in _os.walk('/kaggle/input'):
        if 'support-pack' in dp:
            continue
        if 'tracking_cellmot' in dn and (_Path(dp) / 'tracking_cellmot' / 'metrics.py').is_file():
            if best is None or len(dp) < len(str(best)):
                best = _Path(dp)
    return best


def _wave1_find_train_dir():
    for dp, dn, fn in _os.walk('/kaggle/input'):
        if 'train' in dn and 'test' in dn:
            return _Path(dp) / 'train'
    return None


def _wave1_find_first(pattern: str):
    hits = sorted(_INPUT_ROOT.rglob(pattern))
    return hits[0] if hits else None


WAVE1_SCORER_ROOT = _wave1_find_scorer_root()
if WAVE1_SCORER_ROOT is None:
    raise RuntimeError('Không tìm thấy scorer tracking_cellmot — gattach '
                       'dalloliogm/biohub-official-scorer-patched.')
_sys.path.insert(0, str(WAVE1_SCORER_ROOT))
wave1_log(f'scorer: {WAVE1_SCORER_ROOT}')

TRAIN_DIR = _wave1_find_train_dir()
if TRAIN_DIR is None:
    raise RuntimeError('Không tìm thấy TRAIN_DIR (thư mục train/ cạnh test/).')
TEST_DIR = TRAIN_DIR  # [wave1] validator đọc frame train — giống score_validator_config
WORKING_DIR = _Path('/kaggle/working') if _Path('/kaggle/working').exists() else _Path('.')
wave1_log(f'TRAIN_DIR=TEST_DIR: {TRAIN_DIR}')

# predictions held-out (8 stem, raw core view, từ output ver-7b = ver-7 core)
WAVE1_PRED_DIR = None
for cand in (_INPUT_ROOT.rglob('44b6_12dfb391.geff')):
    if cand.is_dir() and cand.parent.name == 'preds':
        WAVE1_PRED_DIR = cand.parent
        break
if WAVE1_PRED_DIR is None:
    raise RuntimeError('Không tìm thấy preds/44b6_12dfb391.geff — gắn dataset '
                       'vietnguyen130593/biohub-v7-heldout-preds.')
wave1_log(f'pred dir: {WAVE1_PRED_DIR}')

WAVE1_STEMS = [s.strip() for s in
               _os.environ.get('BIOHUB_WAVE1_STEMS', WAVE1_STEMS_DEFAULT).split(',')
               if s.strip()]
WAVE1_STEMS = [s for s in WAVE1_STEMS
               if (TRAIN_DIR / f'{s}.geff').exists() and (WAVE1_PRED_DIR / f'{s}.geff').exists()]
if not WAVE1_STEMS:
    raise RuntimeError('Không stem nào khả dụng (GT + pred).')
wave1_log(f'stems ({len(WAVE1_STEMS)}): {WAVE1_STEMS}')

# deepcenter checkpoint — ưu tiên path mount trực tiếp, rồi datasets/<owner>/...
_DC_CKPT = None
for pattern in ('**/full_frame_center/best.pt',):
    for hit in sorted(_INPUT_ROOT.rglob(pattern)):
        if 'deepcenter' in str(hit):
            _DC_CKPT = hit
            break
    if _DC_CKPT:
        break
if _DC_CKPT is None:
    raise RuntimeError('Không tìm thấy DeepCenter best.pt — gattach '
                       'pilkwang/biohub-deepcenter-unet3d-center-prior-v1.')
_env['BIOHUB_DEEPCENTER_CHECKPOINT'] = str(_DC_CKPT)
wave1_log(f'deepcenter ckpt: {_DC_CKPT}')

# divnet checkpoint (fold manifest) — dataset giorgosi/biohub-divnet-v2
_DIVNET_MANIFEST = None
for hit in sorted(_INPUT_ROOT.rglob('ARTIFACT_MANIFEST.json')):
    if 'divnet' in str(hit).lower():
        _DIVNET_MANIFEST = hit
        break
if _DIVNET_MANIFEST is None:
    for hit in sorted(_INPUT_ROOT.rglob('*.pt')):
        if 'divnet' in str(hit).lower():
            _DIVNET_MANIFEST = hit.parent
            break
wave1_log(f'divnet manifest: {_DIVNET_MANIFEST}')

import numpy as np  # noqa: E402  (đặt trước slices — slices dùng np/td/blosc2)
import blosc2  # noqa: E402
import tracksdata as td  # noqa: E402
from scipy.optimize import linear_sum_assignment  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402
import os  # noqa: E402  (slices + part2 dùng `os` trực tiếp)
import csv  # noqa: E402
import json  # noqa: E402
import math  # noqa: E402
import shutil  # noqa: E402
import time  # noqa: E402
from collections import Counter  # noqa: E402
from pathlib import Path  # noqa: E402

wave1_log('bootstrap xong — chèn các slice NGUYÊN VĂN từ monolith ver-7b...')


# ---- [wave1-slice:constants] monolith ver-7b L403-496 (NGUYÊN VĂN) ----

DET_THRESHOLD = float(os.environ.get('BIOHUB_DET_THRESHOLD', '0.99'))
UNET_BATCH_SIZE = int(os.environ.get('BIOHUB_UNET_BATCH_SIZE', '4'))
USE_ILP = os.environ.get('BIOHUB_USE_ILP', '1') != '0'
ILP_EDGE_WEIGHT = float(os.environ.get('BIOHUB_ILP_EDGE_WEIGHT', '-1.0'))
ILP_APPEARANCE_WEIGHT = float(os.environ.get('BIOHUB_ILP_APPEARANCE_WEIGHT', '0.1'))
ILP_DISAPPEARANCE_WEIGHT = float(os.environ.get('BIOHUB_ILP_DISAPPEARANCE_WEIGHT', '0.1'))
ILP_DIVISION_WEIGHT = float(os.environ.get('BIOHUB_ILP_DIVISION_WEIGHT', '1.0'))
SLICE = ''
ALLOW_PIP_INSTALL = os.environ.get('BIOHUB_ALLOW_PIP_INSTALL', '0') != '0'
RUN_OUTPUT_DIAGNOSTICS = os.environ.get('BIOHUB_RUN_OUTPUT_DIAGNOSTICS', '1') != '0'
OUTPUT_EDGE_MAX_UM = float(os.environ.get('BIOHUB_OUTPUT_EDGE_MAX_UM', '14.0'))
OUTPUT_ENFORCE_NEXT_FRAME = os.environ.get('BIOHUB_OUTPUT_ENFORCE_NEXT_FRAME', '1') != '0'
OUTPUT_SINGLE_PARENT_REPAIR = os.environ.get('BIOHUB_OUTPUT_SINGLE_PARENT_REPAIR', '1') != '0'
OUTPUT_SINGLE_CHILD_REPAIR = os.environ.get('BIOHUB_OUTPUT_SINGLE_CHILD_REPAIR', '0') != '0'
OUTPUT_PRUNE_ISOLATED = os.environ.get('BIOHUB_OUTPUT_PRUNE_ISOLATED', '1') != '0'
OUTPUT_MOTION_RELINK = os.environ.get('BIOHUB_OUTPUT_MOTION_RELINK', '1') != '0'
MOTION_RELINK_TIGHT_UM = float(os.environ.get('BIOHUB_MOTION_RELINK_TIGHT_UM', '6.0'))
MOTION_RELINK_RELAXED_UM = float(os.environ.get('BIOHUB_MOTION_RELINK_RELAXED_UM', '10.0'))
MOTION_RELINK_VELOCITY_WEIGHT = float(os.environ.get('BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT', '0.5'))
MOTION_RELINK_LEARNED_BONUS = float(os.environ.get('BIOHUB_MOTION_RELINK_LEARNED_BONUS', '0.75'))
MOTION_RELINK_MAX_FRAME_NODES = int(os.environ.get('BIOHUB_MOTION_RELINK_MAX_FRAME_NODES', '2600'))
OUTPUT_DIVISION_GEOMETRY_FILTER = os.environ.get('BIOHUB_OUTPUT_DIVISION_GEOMETRY_FILTER', '0') != '0'
DIV_PARENT_MAX_UM = float(os.environ.get('BIOHUB_DIV_PARENT_MAX_UM', '10.5'))
DIV_SISTER_MAX_UM = float(os.environ.get('BIOHUB_DIV_SISTER_MAX_UM', '8.0'))
DIV_DROP_TO_SINGLE_IF_BAD = os.environ.get('BIOHUB_DIV_DROP_TO_SINGLE_IF_BAD', '1') != '0'
OUTPUT_GAP_CLOSE = os.environ.get('BIOHUB_OUTPUT_GAP_CLOSE', '1') != '0'
GAP_CLOSE_MAX_GAP = int(os.environ.get('BIOHUB_GAP_CLOSE_MAX_GAP', '1'))
GAP_CLOSE_UM = float(os.environ.get('BIOHUB_GAP_CLOSE_UM', '6.0'))
GAP_DENSITY_ADAPTIVE = os.environ.get('BIOHUB_GAP_DENSITY_ADAPTIVE', '0') != '0'
GAP_DENSITY_REFERENCE_UM = float(os.environ.get('BIOHUB_GAP_DENSITY_REFERENCE_UM', '6.5'))
GAP_DENSITY_GAIN = float(os.environ.get('BIOHUB_GAP_DENSITY_GAIN', '0.040'))
GAP_DENSITY_MAX_STEP_DELTA_UM = float(os.environ.get('BIOHUB_GAP_DENSITY_MAX_STEP_DELTA_UM', '0.125'))
GAP_DENSITY_NEIGHBORS = int(os.environ.get('BIOHUB_GAP_DENSITY_NEIGHBORS', '3'))
GAP_CLOSE_REUSE_EXISTING = os.environ.get('BIOHUB_GAP_CLOSE_REUSE_EXISTING', '1') != '0'
GAP_CLOSE_REUSE_UM = float(os.environ.get('BIOHUB_GAP_CLOSE_REUSE_UM', '3.2'))
GAP_CLOSE_MAX_ADDED_FRAC = float(os.environ.get('BIOHUB_GAP_CLOSE_MAX_ADDED_FRAC', '0.05'))
GAP_CLOSE_MAX_ADDED_ABS = int(os.environ.get('BIOHUB_GAP_CLOSE_MAX_ADDED_ABS', '2000'))
GAP_REFINE_SYNTHETIC = os.environ.get('BIOHUB_GAP_REFINE_SYNTHETIC', '1') != '0'
GAP_REFINE_WIN_Z = int(os.environ.get('BIOHUB_GAP_REFINE_WIN_Z', '1'))
GAP_REFINE_WIN_YX = int(os.environ.get('BIOHUB_GAP_REFINE_WIN_YX', '3'))
GAP_REFINE_MAX_SHIFT_UM = float(os.environ.get('BIOHUB_GAP_REFINE_MAX_SHIFT_UM', '3.2'))
OUTPUT_FILTER_SHORT_TRACKS = os.environ.get('BIOHUB_OUTPUT_FILTER_SHORT_TRACKS', '1') != '0'
OUTPUT_MIN_TRACK_LEN = int(os.environ.get('BIOHUB_OUTPUT_MIN_TRACK_LEN', '6'))
OUTPUT_KEEP_DIVISION_COMPONENTS = os.environ.get('BIOHUB_OUTPUT_KEEP_DIVISION_COMPONENTS', '1') != '0'
ADAPTIVE_SHORT_TRACK_RESCUE = os.environ.get('BIOHUB_ADAPTIVE_SHORT_TRACK_RESCUE', '0') != '0'
SHORT_TRACK_RESCUE_TRIGGER_REMOVED_FRAC = float(os.environ.get('BIOHUB_SHORT_TRACK_RESCUE_TRIGGER_REMOVED_FRAC', '0.10'))
SHORT_TRACK_RESCUE_MIN_LEN = int(os.environ.get('BIOHUB_SHORT_TRACK_RESCUE_MIN_LEN', '4'))
SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB = float(os.environ.get('BIOHUB_SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB', '0.82'))
SHORT_TRACK_RESCUE_MAX_MEAN_EDGE_DIST_UM = float(os.environ.get('BIOHUB_SHORT_TRACK_RESCUE_MAX_MEAN_EDGE_DIST_UM', '3.25'))
SHORT_TRACK_RESCUE_MAX_NODES_FRAC = float(os.environ.get('BIOHUB_SHORT_TRACK_RESCUE_MAX_NODES_FRAC', '0.018'))
SHORT_TRACK_RESCUE_MAX_NODES_ABS = int(os.environ.get('BIOHUB_SHORT_TRACK_RESCUE_MAX_NODES_ABS', '180'))
OUTPUT_LINEFIT_SMOOTH = os.environ.get('BIOHUB_OUTPUT_LINEFIT_SMOOTH', '1') != '0'
OUTPUT_LINEFIT_WEIGHT = float(os.environ.get('BIOHUB_OUTPUT_LINEFIT_WEIGHT', '0.8'))
OUTPUT_LINEFIT_WINDOW = int(os.environ.get('BIOHUB_OUTPUT_LINEFIT_WINDOW', '2'))
OUTPUT_GAP2_RECOVERY = os.environ.get('BIOHUB_OUTPUT_GAP2_RECOVERY', '0') != '0'
GAP2_MAX_TOTAL_UM = float(os.environ.get('BIOHUB_GAP2_MAX_TOTAL_UM', '10.2'))
GAP2_MAX_STEP_UM = float(os.environ.get('BIOHUB_GAP2_MAX_STEP_UM', '4.4'))
GAP2_MAX_LINKS_FRAC = float(os.environ.get('BIOHUB_GAP2_MAX_LINKS_FRAC', '0.0045'))
GAP2_MAX_LINKS_ABS = int(os.environ.get('BIOHUB_GAP2_MAX_LINKS_ABS', '180'))
GAP2_REQUIRE_CONTEXT = os.environ.get('BIOHUB_GAP2_REQUIRE_CONTEXT', '1') != '0'
GAP2_FRAME_FRAC_CAP = float(os.environ.get('BIOHUB_GAP2_FRAME_FRAC_CAP', '0.006'))
OUTPUT_SAFE_DIVISIONS = os.environ.get('BIOHUB_OUTPUT_SAFE_DIVISIONS', '1') != '0'
SAFE_DIV_MAX_UM = float(os.environ.get('BIOHUB_SAFE_DIV_MAX_UM', '4.7'))
SAFE_DIV_SISTER_MAX_UM = float(os.environ.get('BIOHUB_SAFE_DIV_SISTER_MAX_UM', '7.2'))
SAFE_DIV_SISTER_SYMMETRY_TAU = float(os.environ.get('BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU', '0.0'))
SAFE_DIV_EXISTING_CHILD_MAX_UM = float(os.environ.get('BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM', '7.8'))
SAFE_DIV_FRAME_FRAC_CAP = float(os.environ.get('BIOHUB_SAFE_DIV_FRAME_FRAC_CAP', '0.008'))
SAFE_DIV_GLOBAL_FRAC_CAP = float(os.environ.get('BIOHUB_SAFE_DIV_GLOBAL_FRAC_CAP', '0.004'))
SAFE_DIV_DIVERGE_UM = float(os.environ.get('BIOHUB_SAFE_DIV_DIVERGE_UM', '2.25'))
SAFE_DIV_REQUIRE_DIVERGENCE = os.environ.get('BIOHUB_SAFE_DIV_REQUIRE_DIVERGENCE', '1') != '0'
SAFE_DIV_REQUIRE_MUTUAL_NN = os.environ.get('BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN', '1') != '0'

# [ver7b] DivNet division-event ranker — cấu hình module (RANK-ONLY: chỉ xếp lại đề xuất phân bào)
DIVNET_ENABLE = os.environ.get('BIOHUB_DIVNET_ENABLE', '1') != '0'
DIVNET_RANK = os.environ.get('BIOHUB_DIVNET_RANK', '1') != '0'
DIVNET_RANK_W_UM = float(os.environ.get('BIOHUB_DIVNET_RANK_W_UM', '15.0'))
DIVNET_REQUIRE = os.environ.get('BIOHUB_DIVNET_REQUIRE', '1') != '0'
DIVNET_BATCH = int(os.environ.get('BIOHUB_DIVNET_BATCH', '64'))
DIVNET_CHECKPOINT_EXPLICIT = os.environ.get('BIOHUB_DIVNET_CHECKPOINT', '').strip()
DIVNET_MANIFEST_EXPLICIT = os.environ.get('BIOHUB_DIVNET_MANIFEST', '').strip()
USE_DEEPCENTER_VETO = os.environ.get('BIOHUB_USE_DEEPCENTER_VETO', '1') != '0'
REQUIRE_DEEPCENTER_VETO = os.environ.get('BIOHUB_REQUIRE_DEEPCENTER_VETO', '1') != '0'
DEEPCENTER_MANIFEST_DEFAULT = os.environ.get('BIOHUB_DEEPCENTER_MANIFEST_DEFAULT', '/kaggle/input/datasets/pilkwang/biohub-deepcenter-unet3d-center-prior-v1/ARTIFACT_MANIFEST.json')
DEEPCENTER_CHECKPOINT_DEFAULT = os.environ.get('BIOHUB_DEEPCENTER_CHECKPOINT_DEFAULT', '/kaggle/input/biohub-deepcenter-unet3d-center-prior-v1/weights/full_frame_center/best.pt')
DEEPCENTER_RELATIVE = os.environ.get('BIOHUB_DEEPCENTER_RELATIVE', 'weights/full_frame_center/best.pt')
DEEPCENTER_GAP_VETO = os.environ.get('BIOHUB_DEEPCENTER_GAP_VETO', '1') != '0'
DEEPCENTER_SAFE_DIV_VETO = os.environ.get('BIOHUB_DEEPCENTER_SAFE_DIV_VETO', '1') != '0'
DEEPCENTER_GAP_THRESHOLD = float(os.environ.get('BIOHUB_DEEPCENTER_GAP_THRESHOLD', '0.10'))
DEEPCENTER_EXPECTED_EPOCH = int(os.environ.get('BIOHUB_DEEPCENTER_EXPECTED_EPOCH', '0'))
DEEPCENTER_GAP_CONFIRM_MIN_SPAN_UM = float(os.environ.get('BIOHUB_DEEPCENTER_GAP_CONFIRM_MIN_SPAN_UM', '0'))
DEEPCENTER_SAFE_DIV_THRESHOLD = float(os.environ.get('BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD', '0.12'))
DEEPCENTER_SCORE_WIN_Z = int(os.environ.get('BIOHUB_DEEPCENTER_SCORE_WIN_Z', '1'))
DEEPCENTER_SCORE_WIN_YX = int(os.environ.get('BIOHUB_DEEPCENTER_SCORE_WIN_YX', '2'))
DEEPCENTER_SCORE_CACHE_MAX_FRAMES = int(os.environ.get('BIOHUB_DEEPCENTER_SCORE_CACHE_MAX_FRAMES', '8'))


# ---- [wave1-slice:graph_geo] monolith ver-7b L1769-1802 (NGUYÊN VĂN) ----

VOXEL_SCALE_UM = (1.625, 0.40625, 0.40625)

# Load a geff tracking graph into the internal graph representation
def graph_from_geff(path: Path):
    graph = td.graph.IndexedRXGraph.from_geff(path)
    return graph[0] if isinstance(graph, tuple) else graph

# Measure the physical distance between two graph nodes connected by an edge
def edge_distance_um(source: dict[str, object], target: dict[str, object]) -> float:
    dz = (float(source['z']) - float(target['z'])) * VOXEL_SCALE_UM[0]
    dy = (float(source['y']) - float(target['y'])) * VOXEL_SCALE_UM[1]
    dx = (float(source['x']) - float(target['x'])) * VOXEL_SCALE_UM[2]
    return math.sqrt(dz * dz + dy * dy + dx * dx)

# Measure the physical distance between two 3d points
def point_distance_um(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dz = (a[0] - b[0]) * VOXEL_SCALE_UM[0]
    dy = (a[1] - b[1]) * VOXEL_SCALE_UM[1]
    dx = (a[2] - b[2]) * VOXEL_SCALE_UM[2]
    return math.sqrt(dz * dz + dy * dy + dx * dx)

# Extract a node position as a numeric 3d point
def node_point(node: dict[str, object]) -> tuple[float, float, float]:
    return (float(node['z']), float(node['y']), float(node['x']))

# Build a stable ordering key for graph edges
def edge_sort_key(edge: dict[str, object]) -> tuple[float, float]:
    prob = edge.get('edge_prob')
    prob_value = float(prob) if prob is not None else 0.0
    return (prob_value, -float(edge['distance_um']))

# Generate the next unused node identifier
def _next_node_id(nodes_by_id: dict[int, dict[str, object]]) -> int:
    return max(nodes_by_id) + 1 if nodes_by_id else 1


# ---- [wave1-slice:frames] monolith ver-7b L1804-1868 (NGUYÊN VĂN) ----

# Load one test frame from the source movie
def read_test_frame(dataset: str, t: int, frame_cache: dict[int, np.ndarray]) -> np.ndarray:
    if t in frame_cache:
        return frame_cache[t]
    zarr_path = TEST_DIR / f'{dataset}.zarr'
    meta = json.loads((zarr_path / '0' / 'zarr.json').read_text())
    shape = tuple((int(v) for v in meta['shape']))
    dtype = np.dtype(meta['data_type'])
    frame_shape = shape[1:]
    chunk_path = zarr_path / '0' / 'c' / str(t) / '0' / '0' / '0'

    try:
        raw = chunk_path.read_bytes()
        arr = np.frombuffer(blosc2.decompress(raw), dtype = dtype)

        if arr.size == int(np.prod(frame_shape)):
            frame = arr.reshape(frame_shape).copy()
            frame_cache[t] = frame
            return frame
    except Exception:
        pass
    import zarr
    frame = np.asarray(zarr.open(zarr_path / '0', mode = 'r')[t])
    frame_cache[t] = frame
    return frame

# Refine a synthetic gap midpoint using local image evidence
def refine_synthetic_midpoint(dataset: str | None, t: int, midpoint: tuple[float, float, float], frame_cache: dict[int, np.ndarray], stats: dict[str, int]) -> tuple[float, float, float]:
    if not GAP_REFINE_SYNTHETIC or dataset is None:
        return midpoint

    try:
        frame = read_test_frame(dataset, t, frame_cache)
        z, y, x = [int(round(v)) for v in midpoint]
        z0 = max(0, z - GAP_REFINE_WIN_Z)
        z1 = min(frame.shape[0], z + GAP_REFINE_WIN_Z + 1)
        y0 = max(0, y - GAP_REFINE_WIN_YX)
        y1 = min(frame.shape[1], y + GAP_REFINE_WIN_YX + 1)
        x0 = max(0, x - GAP_REFINE_WIN_YX)
        x1 = min(frame.shape[2], x + GAP_REFINE_WIN_YX + 1)
        patch = frame[z0:z1, y0:y1, x0:x1].astype(np.float64)

        if patch.size == 0:
            stats['gap_refine_failed'] += 1
            return midpoint
        baseline = float(np.percentile(patch, 20.0))
        weights = np.maximum(patch - baseline, 0.0)
        total = float(weights.sum())

        if total <= 0:
            stats['gap_refine_failed'] += 1
            return midpoint
        zz = np.arange(z0, z1, dtype = np.float64)[:, None, None]
        yy = np.arange(y0, y1, dtype = np.float64)[None, :, None]
        xx = np.arange(x0, x1, dtype = np.float64)[None, None, :]
        refined = (float((weights * zz).sum() / total), float((weights * yy).sum() / total), float((weights * xx).sum() / total))

        if point_distance_um(refined, midpoint) > GAP_REFINE_MAX_SHIFT_UM:
            stats['gap_refine_rejected_shift'] += 1
            return midpoint
        stats['gap_refined_synthetic'] += 1
        return refined
    except Exception:
        stats['gap_refine_failed'] += 1
        return midpoint


# ---- [wave1-slice:deepcenter] monolith ver-7b L1870-2181 (NGUYÊN VĂN) ----

# Pool a frame in the xy plane for deepcenter inference
def _dc_pool_frame_xy(volume: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return volume.astype(np.float32, copy = False)
    z, y, x = volume.shape
    y2 = y // factor * factor
    x2 = x // factor * factor
    cropped = volume[:, :y2, :x2].astype(np.float32, copy = False)
    return cropped.reshape(z, y2 // factor, factor, x2 // factor, factor).mean(axis = (2, 4))

# Normalize frame intensity before deepcenter scoring
def _dc_normalize_dynamic_range(volume: np.ndarray, cfg: object) -> np.ndarray:
    vol = np.asarray(volume, dtype = np.float32)
    lo = float(np.percentile(vol, float(getattr(cfg, 'norm_lo_pct', 50.0))))
    hi = float(np.percentile(vol, float(getattr(cfg, 'norm_hi_pct', 99.5))))

    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(vol, dtype = np.float32)
    ratio = (vol - lo) / (hi - lo)
    return np.clip(ratio, float(getattr(cfg, 'norm_clip_lo', -0.5)), float(getattr(cfg, 'norm_clip_hi', 6.0))).astype(np.float32)

# Extract candidate deepcenter checkpoint paths from an artifact manifest
def _dc_manifest_weight_paths(manifest_path: Path) -> list[Path]:
    if not manifest_path.exists():
        return []

    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:
        print('Could not read DeepCenter manifest:', manifest_path, type(exc).__name__, exc)
        return []
    root = manifest_path.parent
    sections: list[dict[str, object]] = []

    for section in [manifest.get('model', {}), manifest.get('models', {}).get('full_frame_center', {}) if isinstance(manifest.get('models', {}), dict) else {}, manifest.get('full_frame_center', {})]:
        if isinstance(section, dict):
            sections.append(section)
    candidates: list[Path] = []

    for section in sections:
        for key in ('weight_path', 'path'):
            rel = section.get(key)

            if isinstance(rel, str) and rel:
                candidates.append(root / rel)

        for key in ('last_checkpoint', 'best_checkpoint'):
            item = section.get(key)

            if isinstance(item, dict):
                rel = item.get('path')

                if isinstance(rel, str) and rel:
                    candidates.append(root / rel)

    for name in ('checkpoint_last.pt', 'best.pt', 'last.pt'):
        candidates.append(root / 'weights' / 'full_frame_center' / name)
        candidates.append(root / name)
    candidates.append(root / DEEPCENTER_RELATIVE)
    return candidates

# Build the ordered list of deepcenter checkpoint candidates
def _dc_checkpoint_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get('BIOHUB_DEEPCENTER_CHECKPOINT', DEEPCENTER_CHECKPOINT_DEFAULT).strip()

    if explicit:
        candidates.append(Path(explicit))
    manifest_explicit = os.environ.get('BIOHUB_DEEPCENTER_MANIFEST', DEEPCENTER_MANIFEST_DEFAULT).strip()

    if manifest_explicit:
        candidates.extend(_dc_manifest_weight_paths(Path(manifest_explicit)))
    input_root = Path('/kaggle/input')
    preferred_dirs = [Path('/kaggle/input/biohub-deepcenter-unet3d-center-prior-v1'), Path('/kaggle/input/datasets/pilkwang/biohub-deepcenter-unet3d-center-prior-v1')]

    for directory in preferred_dirs:
        candidates.extend(_dc_manifest_weight_paths(directory / 'ARTIFACT_MANIFEST.json'))

        for name in ('checkpoint_last.pt', 'best.pt', 'last.pt'):
            candidates.append(directory / 'weights' / 'full_frame_center' / name)
            candidates.append(directory / name)

    if input_root.exists():
        for name in ('checkpoint_last.pt', 'best.pt', 'last.pt'):
            candidates.extend(sorted(input_root.glob(f'**/full_frame_center/**/{name}')))
    seen: set[Path] = set()
    out: list[Path] = []

    for path in candidates:
        path = path.expanduser()

        try:
            key = path.resolve() if path.exists() else path
        except Exception:
            key = path

        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out

try:
    import torch

except Exception as _dc_torch_error:
    torch = None

if torch is not None:

    # Build the reusable 3d convolution block for the deepcenter network
    class _DCConvBlock3d(torch.nn.Module):

        # Initialize the model layers and configuration
        def __init__(self, in_channels: int, out_channels: int) -> None:
            super().__init__()
            groups = min(8, out_channels)
            self.block = torch.nn.Sequential(torch.nn.Conv3d(in_channels, out_channels, 3, padding = 1, bias = False), torch.nn.GroupNorm(groups, out_channels), torch.nn.SiLU(inplace = True), torch.nn.Conv3d(out_channels, out_channels, 3, padding = 1, bias = False), torch.nn.GroupNorm(groups, out_channels), torch.nn.SiLU(inplace = True))

        # Run the forward pass through the model
        def forward(self, x):
            return self.block(x)

    # Build the 3d deepcenter u-net used as a repair confidence gate
    class _DCDeepCenterUNet3D(torch.nn.Module):

        # Initialize the model layers and configuration
        def __init__(self, in_channels: int = 1, base_channels: int = 24) -> None:
            super().__init__()
            c = int(base_channels)
            self.enc1 = _DCConvBlock3d(in_channels, c)
            self.down1 = torch.nn.MaxPool3d(2, 2)
            self.enc2 = _DCConvBlock3d(c, c * 2)
            self.down2 = torch.nn.MaxPool3d(2, 2)
            self.enc3 = _DCConvBlock3d(c * 2, c * 4)
            self.down3 = torch.nn.MaxPool3d(2, 2)
            self.bottleneck = _DCConvBlock3d(c * 4, c * 8)
            self.up3 = torch.nn.ConvTranspose3d(c * 8, c * 4, 2, 2)
            self.dec3 = _DCConvBlock3d(c * 8, c * 4)
            self.up2 = torch.nn.ConvTranspose3d(c * 4, c * 2, 2, 2)
            self.dec2 = _DCConvBlock3d(c * 4, c * 2)
            self.up1 = torch.nn.ConvTranspose3d(c * 2, c, 2, 2)
            self.dec1 = _DCConvBlock3d(c * 2, c)
            self.head = torch.nn.Conv3d(c, 1, 1)

        # Run the forward pass through the model
        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(self.down1(e1))
            e3 = self.enc3(self.down2(e2))
            b = self.bottleneck(self.down3(e3))
            d3 = self.dec3(torch.cat([self.up3(b), e3], dim = 1))
            d2 = self.dec2(torch.cat([self.up2(d3), e2], dim = 1))
            d1 = self.dec1(torch.cat([self.up1(d2), e1], dim = 1))
            return self.head(d1)

else:
    _DCConvBlock3d = None
    _DCDeepCenterUNet3D = None

# Load and validate the deepcenter repair-gating model
def load_deepcenter_veto_detector() -> dict[str, object] | None:
    if not USE_DEEPCENTER_VETO:
        print('DeepCenter add-only repair gate disabled by configuration.')
        return None

    if torch is None:
        if REQUIRE_DEEPCENTER_VETO:
            raise ImportError('torch is required for DeepCenter add-only repair gate')
        print('DeepCenter add-only repair gate skipped because torch is unavailable.')
        return None
    from types import SimpleNamespace
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    load_errors: list[str] = []

    for checkpoint_path in _dc_checkpoint_candidates():
        if not checkpoint_path.exists():
            continue

        try:
            print('Trying DeepCenter add-only gate checkpoint:', checkpoint_path)
            checkpoint = torch.load(checkpoint_path, map_location = device, weights_only = False)

            if not isinstance(checkpoint, dict) or 'model_state' not in checkpoint:
                raise ValueError('checkpoint has no model_state')
            checkpoint_epoch = int(checkpoint.get('epoch', -1))

            if DEEPCENTER_EXPECTED_EPOCH > 0 and checkpoint_epoch != DEEPCENTER_EXPECTED_EPOCH:
                raise ValueError(f'expected DeepCenter epoch {DEEPCENTER_EXPECTED_EPOCH}, got {checkpoint_epoch}')
            cfg = SimpleNamespace(**checkpoint.get('config', {}))
            model = _DCDeepCenterUNet3D(base_channels = int(getattr(cfg, 'base_channels', 24)))
            model.load_state_dict(checkpoint['model_state'])
            model.to(device)
            model.eval()
            print('Loaded DeepCenter add-only gate checkpoint:', checkpoint_path)
            print('DeepCenter checkpoint epoch:', checkpoint.get('epoch'), 'best_score:', checkpoint.get('best_score'))
            return {'model': model, 'cfg': cfg, 'device': device, 'path': checkpoint_path, 'torch': torch}
        except Exception as exc:
            load_errors.append(f'{checkpoint_path}: {type(exc).__name__}: {exc}')
            print('Skipping incompatible DeepCenter checkpoint:', checkpoint_path, '|', type(exc).__name__, exc)
    message = 'No usable DeepCenter checkpoint found for add-only repair gate.'

    if REQUIRE_DEEPCENTER_VETO:
        checked = '\n'.join((str(p) for p in _dc_checkpoint_candidates()[:80]))
        errors = '\n'.join(load_errors[-20:])
        raise FileNotFoundError(message + '\nChecked:\n' + checked + ('\nLoad errors:\n' + errors if errors else ''))
    print(message)
    return None

# Trim cached deepcenter heatmaps to the configured frame limit
def _dc_cache_trim(cache: dict[tuple[str, int], np.ndarray]) -> None:
    limit = max(1, int(DEEPCENTER_SCORE_CACHE_MAX_FRAMES))

    while len(cache) > limit:
        cache.pop(next(iter(cache)))

# Generate or reuse the deepcenter heatmap for a requested frame
def deepcenter_heatmap_for_frame(dataset: str, t: int, detector_bundle: dict[str, object] | None, frame_cache: dict[int, np.ndarray], heatmap_cache: dict[tuple[str, int], np.ndarray]) -> np.ndarray | None:
    if detector_bundle is None:
        return None
    key = (dataset, int(t))
    cached = heatmap_cache.get(key)

    if cached is not None:
        return cached
    model = detector_bundle['model']
    cfg = detector_bundle['cfg']
    device = detector_bundle['device']
    torch_mod = detector_bundle['torch']
    pool_factor = int(getattr(cfg, 'pool_factor', 4))
    volume = read_test_frame(dataset, int(t), frame_cache)
    pooled = _dc_pool_frame_xy(volume, pool_factor)
    image = _dc_normalize_dynamic_range(pooled, cfg)

    with torch_mod.no_grad():
        tensor = torch_mod.from_numpy(image[None, None, ...]).to(device = device, dtype = torch_mod.float32)
        logits = model(tensor)

        if os.environ.get('BIOHUB_DEEPCENTER_TTA', '0') != '0':
            acc = logits.clone()
            nv = 1

            for dims in [(-1,), (-2,), (-2, -1)]:
                acc = acc + model(tensor.flip(dims)).flip(dims)
                nv += 1

            if tensor.shape[-1] == tensor.shape[-2]:
                for k in (1, 3):
                    acc = acc + torch_mod.rot90(model(torch_mod.rot90(tensor, k, dims = (-2, -1))), -k, dims = (-2, -1))
                    nv += 1
                acc = acc + model(tensor.transpose(-1, -2)).transpose(-1, -2)
                nv += 1
                at = torch_mod.rot90(tensor, 1, dims = (-2, -1)).transpose(-1, -2)
                acc = acc + torch_mod.rot90(model(at).transpose(-1, -2), -1, dims = (-2, -1))
                nv += 1
            delta = float((acc / nv - logits).abs().mean())

            if delta == 0.0:
                raise RuntimeError('DeepCenter TTA produced no logit change')

            if not getattr(deepcenter_heatmap_for_frame, '_tta_announced', False):
                print('DEEPCENTER_TTA_ACTIVE views =', nv, 'mean_abs_logit_delta =', round(delta, 6), flush = True)
                deepcenter_heatmap_for_frame._tta_announced = True
            logits = acc / nv
        heatmap = torch_mod.sigmoid(logits)[0, 0].detach().cpu().numpy().astype(np.float32, copy = False)
    heatmap_cache[key] = heatmap
    _dc_cache_trim(heatmap_cache)
    return heatmap

# Score a candidate 3d point using the deepcenter heatmap
def deepcenter_score_point(dataset: str | None, t: int, point: tuple[float, float, float], detector_bundle: dict[str, object] | None, frame_cache: dict[int, np.ndarray], heatmap_cache: dict[tuple[str, int], np.ndarray]) -> float | None:
    if not USE_DEEPCENTER_VETO or detector_bundle is None or dataset is None:
        return None
    heatmap = deepcenter_heatmap_for_frame(dataset, int(t), detector_bundle, frame_cache, heatmap_cache)

    if heatmap is None or heatmap.size == 0:
        return None
    cfg = detector_bundle['cfg']
    pool_factor = int(getattr(cfg, 'pool_factor', 4))
    z = int(round(float(point[0])))
    y = int(round(float(point[1]) / max(pool_factor, 1)))
    x = int(round(float(point[2]) / max(pool_factor, 1)))
    z0, z1 = (max(0, z - DEEPCENTER_SCORE_WIN_Z), min(heatmap.shape[0], z + DEEPCENTER_SCORE_WIN_Z + 1))
    y0, y1 = (max(0, y - DEEPCENTER_SCORE_WIN_YX), min(heatmap.shape[1], y + DEEPCENTER_SCORE_WIN_YX + 1))
    x0, x1 = (max(0, x - DEEPCENTER_SCORE_WIN_YX), min(heatmap.shape[2], x + DEEPCENTER_SCORE_WIN_YX + 1))
    patch = heatmap[z0:z1, y0:y1, x0:x1]

    if patch.size == 0:
        return None
    score = float(np.max(patch))
    return score if np.isfinite(score) else None

# Decide whether deepcenter evidence is strong enough to accept a repair
def deepcenter_accept_repair_point(dataset: str | None, t: int, point: tuple[float, float, float], detector_bundle: dict[str, object] | None, frame_cache: dict[int, np.ndarray], heatmap_cache: dict[tuple[str, int], np.ndarray], stats: dict[str, int], prefix: str, threshold: float) -> bool:
    if not USE_DEEPCENTER_VETO:
        return True

    if detector_bundle is None or dataset is None:
        stats[f'deepcenter_{prefix}_missing'] += 1
        return True
    stats[f'deepcenter_{prefix}_checked'] += 1
    score = deepcenter_score_point(dataset, int(t), point, detector_bundle, frame_cache, heatmap_cache)

    if score is None:
        stats[f'deepcenter_{prefix}_missing'] += 1
        return True

    if score < float(threshold):
        stats[f'deepcenter_{prefix}_rejected'] += 1
        return False
    stats[f'deepcenter_{prefix}_accepted'] += 1
    return True


# ---- [wave1-slice:relink] monolith ver-7b L2183-2298 (NGUYÊN VĂN) ----

# Convert a graph node position from voxel coordinates to micrometers
def _position_um(node: dict[str, object]) -> np.ndarray:
    return np.array([float(node['z']) * VOXEL_SCALE_UM[0], float(node['y']) * VOXEL_SCALE_UM[1], float(node['x']) * VOXEL_SCALE_UM[2]], dtype = np.float64)

# Recover plausible missing edges using motion consistency and learned edge evidence
def motion_relink_edges(nodes_by_id: dict[int, dict[str, object]], stats: dict[str, int], learned_edge_probs: dict[tuple[int, int], float] | None = None) -> list[dict[str, object]]:
    if not OUTPUT_MOTION_RELINK or not nodes_by_id:
        return []
    learned_edge_probs = learned_edge_probs or {}

    # Read the learned association probability for a candidate edge
    def learned_prob(source_id: int, target_id: int) -> float:
        value = learned_edge_probs.get((source_id, target_id), 0.0)

        try:
            value = float(value)
        except (TypeError, ValueError):
            return 0.0

        if not np.isfinite(value):
            return 0.0

        if value < 0.0 or value > 1.0:
            value = 1.0 / (1.0 + math.exp(-max(-20.0, min(20.0, value))))
        return float(np.clip(value, 0.0, 1.0))
    ids_by_t: dict[int, list[int]] = {}

    for node_id, node in nodes_by_id.items():
        ids_by_t.setdefault(int(node['t']), []).append(node_id)

    for ids in ids_by_t.values():
        ids.sort()
    frame_sizes = [len(ids) for ids in ids_by_t.values()]

    if frame_sizes and max(frame_sizes) > MOTION_RELINK_MAX_FRAME_NODES:
        stats['motion_relink_skipped_large_frame'] = 1
        return []
    position_um = {node_id: _position_um(node) for node_id, node in nodes_by_id.items()}
    predecessor_position_um: dict[int, np.ndarray] = {}
    selected_edges: list[dict[str, object]] = []

    # Assign unmatched source and target nodes under the current relinking constraints
    def assign_pass(source_ids: list[int], target_ids: list[int], gate_um: float) -> list[tuple[int, int, float, float, float]]:
        if not source_ids or not target_ids:
            return []
        big = gate_um * 1000.0 + 1.0
        cost = np.full((len(source_ids), len(target_ids)), big, dtype = np.float64)
        raw_dist = np.full_like(cost, np.inf)
        motion_dist = np.full_like(cost, np.inf)
        prob_matrix = np.zeros_like(cost)

        for i, source_id in enumerate(source_ids):
            source_pos = position_um[source_id]
            prev_pos = predecessor_position_um.get(source_id)

            if prev_pos is None:
                predicted = source_pos
            else:
                predicted = source_pos + MOTION_RELINK_VELOCITY_WEIGHT * (source_pos - prev_pos)

            for j, target_id in enumerate(target_ids):
                target_pos = position_um[target_id]
                raw = float(np.linalg.norm(target_pos - source_pos))

                if raw > gate_um:
                    continue
                motion = float(np.linalg.norm(target_pos - predicted))
                prob = learned_prob(source_id, target_id)
                raw_dist[i, j] = raw
                motion_dist[i, j] = motion
                prob_matrix[i, j] = prob
                cost[i, j] = motion + 0.05 * raw - MOTION_RELINK_LEARNED_BONUS * prob
        row_ind, col_ind = linear_sum_assignment(cost)
        matches: list[tuple[int, int, float, float, float]] = []

        for r, c in zip(row_ind, col_ind):
            if cost[r, c] >= big:
                continue
            matches.append((source_ids[int(r)], target_ids[int(c)], float(raw_dist[r, c]), float(motion_dist[r, c]), float(prob_matrix[r, c])))
        return matches
    times = sorted(ids_by_t)

    for t in times:
        source_ids = ids_by_t.get(t, [])
        target_ids = ids_by_t.get(t + 1, [])

        if not source_ids or not target_ids:
            continue
        unmatched_sources = set(source_ids)
        unmatched_targets = set(target_ids)
        frame_matches: list[tuple[int, int, float, float, str, float]] = []

        for pass_name, gate_um in (('tight', MOTION_RELINK_TIGHT_UM), ('relaxed', MOTION_RELINK_RELAXED_UM)):
            pass_sources = [node_id for node_id in source_ids if node_id in unmatched_sources]
            pass_targets = [node_id for node_id in target_ids if node_id in unmatched_targets]
            matches = assign_pass(pass_sources, pass_targets, gate_um)

            for source_id, target_id, raw, motion, prob in matches:
                if source_id not in unmatched_sources or target_id not in unmatched_targets:
                    continue
                unmatched_sources.remove(source_id)
                unmatched_targets.remove(target_id)
                frame_matches.append((source_id, target_id, raw, motion, pass_name, prob))

                if pass_name == 'tight':
                    stats['motion_relink_tight_edges'] += 1
                else:
                    stats['motion_relink_relaxed_edges'] += 1

        for source_id, target_id, raw, motion, pass_name, prob in frame_matches:
            selected_edges.append({'source_id': source_id, 'target_id': target_id, 'edge_prob': prob, 'distance_um': raw, 'motion_distance_um': motion, 'motion_relinked': 1, 'motion_pass': pass_name})
            predecessor_position_um[target_id] = position_um[source_id]
        stats['motion_relink_frames'] += 1
    stats['motion_relink_edges'] = len(selected_edges)
    return selected_edges


# ---- [wave1-slice:gaps] monolith ver-7b L2299-2476 (NGUYÊN VĂN) ----

# Close eligible one-frame tracking gaps while respecting geometric safeguards
def close_single_frame_gaps(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]], stats: dict[str, int], dataset: str | None = None, deepcenter_bundle: dict[str, object] | None = None, frame_cache: dict[int, np.ndarray] | None = None, deepcenter_cache: dict[tuple[str, int], np.ndarray] | None = None) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    if not OUTPUT_GAP_CLOSE or GAP_CLOSE_MAX_GAP < 1 or (not edges):
        return (nodes_by_id, edges)
    outgoing = {int(edge['source_id']) for edge in edges}
    incoming = {int(edge['target_id']) for edge in edges}
    incident = outgoing | incoming
    ends_by_t: dict[int, list[int]] = {}
    starts_by_t: dict[int, list[int]] = {}
    isolated_by_t: dict[int, list[int]] = {}
    all_ids_by_t: dict[int, list[int]] = {}

    for node_id, node in nodes_by_id.items():
        t = int(node['t'])
        all_ids_by_t.setdefault(t, []).append(node_id)

        if node_id not in outgoing:
            ends_by_t.setdefault(t, []).append(node_id)

        if node_id not in incoming:
            starts_by_t.setdefault(t, []).append(node_id)

        if node_id not in incident:
            isolated_by_t.setdefault(t, []).append(node_id)
    max_synthetic = min(GAP_CLOSE_MAX_ADDED_ABS, max(1, int(round(len(nodes_by_id) * GAP_CLOSE_MAX_ADDED_FRAC))) if GAP_CLOSE_MAX_ADDED_FRAC > 0 else 0)
    next_id = _next_node_id(nodes_by_id)
    frame_cache = frame_cache if frame_cache is not None else {}
    deepcenter_cache = deepcenter_cache if deepcenter_cache is not None else {}
    used_starts: set[int] = set()
    used_isolated: set[int] = set()
    synthetic_added = 0
    new_edges: list[dict[str, object]] = []
    density_cache: dict[int, dict[int, float]] = {}

    # Estimate local inter-cell spacing around a frame position
    def frame_local_spacing(t: int) -> dict[int, float]:
        cached = density_cache.get(t)

        if cached is not None:
            return cached
        frame_ids = all_ids_by_t.get(t, [])

        if len(frame_ids) <= 1:
            result = {node_id: GAP_DENSITY_REFERENCE_UM for node_id in frame_ids}
            density_cache[t] = result
            return result
        positions = np.stack([_position_um(nodes_by_id[node_id]) for node_id in frame_ids])
        tree = cKDTree(positions)
        query_k = min(len(frame_ids), max(2, GAP_DENSITY_NEIGHBORS + 1))
        distances, _ = tree.query(positions, k = query_k)

        if distances.ndim == 1:
            distances = distances[:, None]
        result: dict[int, float] = {}

        for idx, node_id in enumerate(frame_ids):
            neighbour_distances = distances[idx, 1:]
            neighbour_distances = neighbour_distances[np.isfinite(neighbour_distances)]
            spacing = float(np.median(neighbour_distances)) if neighbour_distances.size else GAP_DENSITY_REFERENCE_UM
            result[node_id] = spacing
        density_cache[t] = result
        stats['gap_density_nodes_scored'] += len(result)
        return result
    effective_gap_max = min(GAP_CLOSE_MAX_GAP, 1)
    stats['gap_close_effective_max_gap'] = effective_gap_max

    for gap in range(1, effective_gap_max + 1):
        for t, end_ids in sorted(ends_by_t.items()):
            start_ids = [sid for sid in starts_by_t.get(t + gap + 1, []) if sid not in used_starts]

            if not end_ids or not start_ids:
                continue
            end_points = [node_point(nodes_by_id[eid]) for eid in end_ids]
            start_points = [node_point(nodes_by_id[sid]) for sid in start_ids]
            threshold_um = GAP_CLOSE_UM * (gap + 1)
            d = np.zeros((len(end_ids), len(start_ids)), dtype = np.float64)
            adaptive_threshold = np.full_like(d, threshold_um)
            source_spacing = frame_local_spacing(t)
            target_spacing = frame_local_spacing(t + gap + 1)

            for i, ep in enumerate(end_points):
                for j, sp in enumerate(start_points):
                    d[i, j] = point_distance_um(ep, sp)

                    if GAP_DENSITY_ADAPTIVE:
                        local_spacing = 0.5 * (source_spacing.get(end_ids[i], GAP_DENSITY_REFERENCE_UM) + target_spacing.get(start_ids[j], GAP_DENSITY_REFERENCE_UM))
                        step_delta = float(np.clip(GAP_DENSITY_GAIN * (local_spacing - GAP_DENSITY_REFERENCE_UM), -GAP_DENSITY_MAX_STEP_DELTA_UM, GAP_DENSITY_MAX_STEP_DELTA_UM))
                        adaptive_threshold[i, j] = threshold_um + step_delta * (gap + 1)
                        stats['gap_density_step_delta_milli_sum'] += int(round(1000.0 * step_delta))
            base_allowed = d <= threshold_um
            adaptive_allowed = d <= adaptive_threshold
            stats['gap_density_candidates_expanded'] += int((adaptive_allowed & ~base_allowed).sum())
            stats['gap_density_candidates_restricted'] += int((base_allowed & ~adaptive_allowed).sum())
            stats['gap_candidates'] += int(adaptive_allowed.sum())

            if not np.isfinite(d).any():
                continue
            max_threshold = float(np.max(adaptive_threshold))
            big = max_threshold * 1000.0 + 1.0
            cost = np.where(adaptive_allowed, d, big)
            row_ind, col_ind = linear_sum_assignment(cost)

            for r, c in zip(row_ind, col_ind):
                if not adaptive_allowed[r, c]:
                    continue

                if not base_allowed[r, c]:
                    stats['gap_density_selected_outside_base'] += 1
                source_id = end_ids[int(r)]
                target_id = start_ids[int(c)]

                if source_id in outgoing or target_id in used_starts:
                    continue
                source = nodes_by_id[source_id]
                target = nodes_by_id[target_id]
                mid_t = int(source['t']) + gap
                mid_point = ((float(source['z']) + float(target['z'])) / 2.0, (float(source['y']) + float(target['y'])) / 2.0, (float(source['x']) + float(target['x'])) / 2.0)
                middle_id: int | None = None
                middle_reused = False

                if GAP_CLOSE_REUSE_EXISTING:
                    candidates = [nid for nid in isolated_by_t.get(mid_t, []) if nid not in used_isolated]

                    if candidates:
                        distances = [point_distance_um(node_point(nodes_by_id[nid]), mid_point) for nid in candidates]
                        best_idx = int(np.argmin(distances))

                        if distances[best_idx] <= GAP_CLOSE_REUSE_UM:
                            middle_id = candidates[best_idx]
                            middle_reused = True

                if middle_id is None:
                    if synthetic_added >= max_synthetic:
                        stats['gap_skipped_node_cap'] += 1
                        continue
                    middle_id = next_id
                    next_id += 1
                    refined_point = refine_synthetic_midpoint(dataset, mid_t, mid_point, frame_cache, stats)
                    nodes_by_id[middle_id] = {'node_id': middle_id, 't': mid_t, 'z': refined_point[0], 'y': refined_point[1], 'x': refined_point[2], 'gap_synthetic': 1}
                    synthetic_added += 1
                    stats['gap_inserted_synthetic'] += 1
                middle = nodes_by_id[middle_id]
                gap_span_um = float(d[r, c])
                marginal_gap = gap_span_um >= DEEPCENTER_GAP_CONFIRM_MIN_SPAN_UM
                synthetic_middle = int(middle.get('gap_synthetic', 0)) == 1
                requires_center_confirmation = DEEPCENTER_GAP_VETO and marginal_gap and synthetic_middle

                if DEEPCENTER_GAP_VETO and (not marginal_gap):
                    stats['deepcenter_gap_bypassed_strong_motion'] += 1
                elif DEEPCENTER_GAP_VETO and (not synthetic_middle):
                    stats['deepcenter_gap_bypassed_observed_node'] += 1

                if requires_center_confirmation and (not deepcenter_accept_repair_point(dataset, mid_t, node_point(middle), deepcenter_bundle, frame_cache, deepcenter_cache, stats, 'gap', DEEPCENTER_GAP_THRESHOLD)):
                    if int(middle.get('gap_synthetic', 0)) == 1:
                        nodes_by_id.pop(middle_id, None)
                        synthetic_added = max(0, synthetic_added - 1)
                        stats['gap_inserted_synthetic'] = max(0, stats['gap_inserted_synthetic'] - 1)
                    continue

                if middle_reused:
                    used_isolated.add(middle_id)
                    stats['gap_reused_existing'] += 1
                e1 = {'source_id': source_id, 'target_id': middle_id, 'edge_prob': None, 'distance_um': edge_distance_um(source, middle), 'gap_closed': 1}
                e2 = {'source_id': middle_id, 'target_id': target_id, 'edge_prob': None, 'distance_um': edge_distance_um(middle, target), 'gap_closed': 1}
                new_edges.extend([e1, e2])
                outgoing.add(source_id)
                incoming.add(middle_id)
                outgoing.add(middle_id)
                incoming.add(target_id)
                used_starts.add(target_id)
                stats['gap_pairs_selected'] += 1
                stats['gap_added_edges'] += 2

    if new_edges:
        edges = [*edges, *new_edges]
    stats['gap_added_nodes'] = stats['gap_inserted_synthetic']
    return (nodes_by_id, edges)


# ---- [wave1-slice:maps_gap2] monolith ver-7b L2477-2629 (NGUYÊN VĂN) ----

# Build a node-to-successor map for nodes with exactly one outgoing edge
def _single_successor_map(edges: list[dict[str, object]]) -> dict[int, int]:
    by_source: dict[int, list[int]] = {}

    for edge in edges:
        by_source.setdefault(int(edge['source_id']), []).append(int(edge['target_id']))
    return {source: targets[0] for source, targets in by_source.items() if len(targets) == 1}

# Build a node-to-predecessor map for nodes with exactly one incoming edge
def _single_predecessor_map(edges: list[dict[str, object]]) -> dict[int, int]:
    by_target: dict[int, list[int]] = {}

    for edge in edges:
        by_target.setdefault(int(edge['target_id']), []).append(int(edge['source_id']))
    return {target: sources[0] for target, sources in by_target.items() if len(sources) == 1}

# Recover strict two-frame gaps only when temporal context supports the repair
def recover_strict_gap2(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]], stats: dict[str, int], dataset: str | None = None) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    if not OUTPUT_GAP2_RECOVERY or not edges or (not nodes_by_id):
        return (nodes_by_id, edges)
    outgoing = {int(edge['source_id']) for edge in edges}
    incoming = {int(edge['target_id']) for edge in edges}
    predecessor = _single_predecessor_map(edges)
    successor = _single_successor_map(edges)
    ends_by_t: dict[int, list[int]] = {}
    starts_by_t: dict[int, list[int]] = {}

    for node_id, node in nodes_by_id.items():
        t = int(node['t'])

        if node_id not in outgoing:
            ends_by_t.setdefault(t, []).append(node_id)

        if node_id not in incoming:
            starts_by_t.setdefault(t, []).append(node_id)
    cap = min(GAP2_MAX_LINKS_ABS, max(1, int(round(len(edges) * GAP2_MAX_LINKS_FRAC))))
    proposals: list[tuple[float, int, int, int, float]] = []

    # Convert a node identifier into its physical 3d position
    def pos_um(node_id: int) -> np.ndarray:
        node = nodes_by_id[node_id]
        return np.array([float(node['z']), float(node['y']), float(node['x'])], dtype = np.float64) * np.array(VOXEL_SCALE_UM)

    for t, end_ids in sorted(ends_by_t.items()):
        start_ids = starts_by_t.get(t + 3, [])

        if not end_ids or not start_ids:
            continue

        for end_id in end_ids:
            end_pos = pos_um(end_id)

            for start_id in start_ids:
                start_pos = pos_um(start_id)
                dist = float(np.linalg.norm(start_pos - end_pos))

                if dist > GAP2_MAX_TOTAL_UM or dist / 3.0 > GAP2_MAX_STEP_UM:
                    continue
                step = (start_pos - end_pos) / 3.0
                context_penalty = 0.0

                if GAP2_REQUIRE_CONTEXT:
                    ok_context = False
                    prev_id = predecessor.get(end_id)

                    if prev_id is not None:
                        prev_step = end_pos - pos_um(prev_id)
                        prev_norm = float(np.linalg.norm(prev_step))
                        step_norm = float(np.linalg.norm(step))

                        if prev_norm <= 0.01 or step_norm <= 0.01:
                            ok_context = True
                        else:
                            cos = float(np.dot(prev_step, step) / (prev_norm * step_norm + 1e-09))

                            if cos > -0.25 and np.linalg.norm(prev_step - step) <= 6.0:
                                ok_context = True
                            context_penalty += max(0.0, 0.25 - cos)
                    next_id = successor.get(start_id)

                    if next_id is not None:
                        next_step = pos_um(next_id) - start_pos
                        next_norm = float(np.linalg.norm(next_step))
                        step_norm = float(np.linalg.norm(step))

                        if next_norm <= 0.01 or step_norm <= 0.01:
                            ok_context = True
                        else:
                            cos = float(np.dot(next_step, step) / (next_norm * step_norm + 1e-09))

                            if cos > -0.25 and np.linalg.norm(next_step - step) <= 6.0:
                                ok_context = True
                            context_penalty += max(0.0, 0.25 - cos)

                    if not ok_context:
                        continue
                proposals.append((dist + 2.0 * context_penalty, end_id, start_id, t, dist))
    proposals.sort(key = lambda item: item[0])
    stats['gap2_candidates'] = len(proposals)

    if not proposals:
        return (nodes_by_id, edges)
    selected: list[tuple[float, int, int, int, float]] = []
    used_ends: set[int] = set()
    used_starts: set[int] = set()
    per_frame_count: dict[int, int] = {}

    for proposal in proposals:
        if len(selected) >= cap:
            stats['gap2_skipped_cap'] += 1
            break
        _, end_id, start_id, t, _ = proposal

        if end_id in used_ends or start_id in used_starts:
            continue
        frame_cap = max(1, int(round(len(ends_by_t.get(t, [])) * GAP2_FRAME_FRAC_CAP)))

        if per_frame_count.get(t, 0) >= frame_cap:
            continue
        selected.append(proposal)
        used_ends.add(end_id)
        used_starts.add(start_id)
        per_frame_count[t] = per_frame_count.get(t, 0) + 1

    if not selected:
        return (nodes_by_id, edges)
    next_node_id = _next_node_id(nodes_by_id)
    frame_cache: dict[int, np.ndarray] = {}
    new_edges: list[dict[str, object]] = []

    for _, end_id, start_id, t, _ in selected:
        source = nodes_by_id[end_id]
        target = nodes_by_id[start_id]
        previous_id = end_id
        inserted_ids: list[int] = []

        for k in (1, 2):
            frac = k / 3.0
            mid_t = int(source['t']) + k
            midpoint = (float(source['z']) + (float(target['z']) - float(source['z'])) * frac, float(source['y']) + (float(target['y']) - float(source['y'])) * frac, float(source['x']) + (float(target['x']) - float(source['x'])) * frac)
            refined_point = refine_synthetic_midpoint(dataset, mid_t, midpoint, frame_cache, stats)
            node_id = next_node_id
            next_node_id += 1
            nodes_by_id[node_id] = {'node_id': node_id, 't': mid_t, 'z': refined_point[0], 'y': refined_point[1], 'x': refined_point[2]}
            inserted_ids.append(node_id)
            current = nodes_by_id[node_id]
            new_edges.append({'source_id': previous_id, 'target_id': node_id, 'edge_prob': None, 'distance_um': edge_distance_um(nodes_by_id[previous_id], current), 'gap2_recovered': 1})
            previous_id = node_id
        new_edges.append({'source_id': previous_id, 'target_id': start_id, 'edge_prob': None, 'distance_um': edge_distance_um(nodes_by_id[previous_id], target), 'gap2_recovered': 1})
        stats['gap2_pairs_selected'] += 1
        stats['gap2_added_nodes'] += len(inserted_ids)
        stats['gap2_added_edges'] += 3
    return (nodes_by_id, [*edges, *new_edges])


# ---- [wave1-slice:divnet] monolith ver-7b L2631-2906 (NGUYÊN VĂN) ----

# [ver7b] ---------------------------------------------------------------------
# DivNet division-event ranker (biohub-divnet) -- RANK-ONLY mode.
# Port nguyên văn từ tích hợp chuẩn của tác giả divnet (RANK-ONLY, W um-equivalent).
# Chỉ ĐẶT LẠI THỨ TỰ đề xuất phân bào: score = parent + 0.15*sister - W*P_div.
# KHÔNG thêm/xoá gate theo xác suất (threshold/topk để 0/0.5 và KHÔNG dùng).
# (Ghi chú 13/9: tái tạo sau sandbox rollback — đã qua test-ver7b-divnet.py 7/7 PASS
#  với checkpoint thật api/research/divnet/v2/best_overall.pt trước khi mất file.)
# ---------------------------------------------------------------------
try:
    import torch
except Exception:
    torch = None

if torch is not None:
    class _DivNetConvBlock3d(torch.nn.Module):
        def __init__(self, in_channels: int, out_channels: int) -> None:
            super().__init__()
            groups = min(8, out_channels)
            self.block = torch.nn.Sequential(
                torch.nn.Conv3d(in_channels, out_channels, 3, padding=1, bias=False),
                torch.nn.GroupNorm(groups, out_channels),
                torch.nn.SiLU(inplace=True),
                torch.nn.Conv3d(out_channels, out_channels, 3, padding=1, bias=False),
                torch.nn.GroupNorm(groups, out_channels),
                torch.nn.SiLU(inplace=True),
            )
        def forward(self, x): return self.block(x)

    class _DivNetUNet3D(torch.nn.Module):
        def __init__(self, in_channels: int = 5, base_channels: int = 16) -> None:
            super().__init__()
            c = int(base_channels)
            self.enc1 = _DivNetConvBlock3d(in_channels, c)
            self.down1 = torch.nn.MaxPool3d(2, 2)
            self.enc2 = _DivNetConvBlock3d(c, c * 2)
            self.down2 = torch.nn.MaxPool3d(2, 2)
            self.enc3 = _DivNetConvBlock3d(c * 2, c * 4)
            self.down3 = torch.nn.MaxPool3d(2, 2)
            self.bottleneck = _DivNetConvBlock3d(c * 4, c * 8)
            self.up3 = torch.nn.ConvTranspose3d(c * 8, c * 4, 2, 2)
            self.dec3 = _DivNetConvBlock3d(c * 8, c * 4)
            self.up2 = torch.nn.ConvTranspose3d(c * 4, c * 2, 2, 2)
            self.dec2 = _DivNetConvBlock3d(c * 4, c * 2)
            self.up1 = torch.nn.ConvTranspose3d(c * 2, c, 2, 2)
            self.dec1 = _DivNetConvBlock3d(c * 2, c)
            self.dropout = torch.nn.Dropout(0.1)
            self.head = torch.nn.Linear(c, 1)
        def forward(self, x):
            e1 = self.enc1(x); e2 = self.enc2(self.down1(e1)); e3 = self.enc3(self.down2(e2))
            b = self.bottleneck(self.down3(e3))
            d3 = self.dec3(torch.cat([self.up3(b), e3], dim=1))
            d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
            d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
            pooled = d1.mean(dim=(2, 3, 4))
            return self.head(self.dropout(pooled)).squeeze(-1)
else:
    _DivNetConvBlock3d = None; _DivNetUNet3D = None


def _divnet_manifest_fold_paths(manifest_path: Path) -> list[Path]:
    if not manifest_path.exists(): return []
    try: manifest = json.loads(manifest_path.read_text())
    except Exception: return []
    root = manifest_path.parent
    model_meta = manifest.get("model", {}) if isinstance(manifest.get("model", {}), dict) else {}
    out: list[Path] = []
    rels = model_meta.get("folds")
    if isinstance(rels, list): out.extend(root / rel for rel in rels if isinstance(rel, str) and rel)
    best = model_meta.get("best_overall")
    if isinstance(best, str) and best: out.append(root / best)
    if not out:
        for pattern in ("weights/divnet/fold*/best.pt", "DivNet/weights/divnet/fold*/best.pt"):
            out.extend(sorted(root.glob(pattern)))
    return out


def _divnet_checkpoint_candidates() -> list[Path]:
    candidates: list[Path] = []
    if DIVNET_CHECKPOINT_EXPLICIT:
        candidates.append(Path(DIVNET_CHECKPOINT_EXPLICIT))

    input_root = Path("/kaggle/input")
    # Kaggle gắn dataset hoặc ngay dưới /kaggle/input hoặc /kaggle/input/datasets/<owner>/<slug>.
    dataset_dirs: list[Path] = []
    for canonical in (input_root / "biohub-divnet-v2", input_root / "biohub-divnet-v1"):
        if canonical.exists():
            dataset_dirs.append(canonical)
    if input_root.exists():
        dataset_dirs.extend(sorted(input_root.glob("datasets/*/biohub-divnet-v*")))
        dataset_dirs.extend(sorted(input_root.glob("biohub-divnet*")))

    manifest_candidates: list[Path] = []
    if DIVNET_MANIFEST_EXPLICIT:
        manifest_candidates.append(Path(DIVNET_MANIFEST_EXPLICIT))
    for directory in dataset_dirs:
        manifest_candidates.extend([
            directory / "ARTIFACT_MANIFEST.json",
            directory / "DivNet" / "ARTIFACT_MANIFEST.json",
        ])
    if input_root.exists():
        manifest_candidates.extend(sorted(input_root.glob("biohub-divnet*/ARTIFACT_MANIFEST.json")))
        manifest_candidates.extend(sorted(input_root.glob("datasets/*/biohub-divnet*/ARTIFACT_MANIFEST.json")))

    seen_m: set[Path] = set()
    for manifest_path in manifest_candidates:
        try:
            key = manifest_path.resolve()
        except Exception:
            key = manifest_path
        if key in seen_m or not manifest_path.exists():
            continue
        seen_m.add(key)
        try:
            data = json.loads(manifest_path.read_text())
        except Exception:
            continue
        model_meta = data.get("model", {}) if isinstance(data.get("model", {}), dict) else {}
        looks_divnet = (
            str(data.get("artifact_name", "")).startswith("biohub-divnet")
            or model_meta.get("type") == "divnet_unet3d_gap"
            or "divnet" in str(model_meta.get("path", "")).lower()
        )
        if looks_divnet:
            candidates.extend(_divnet_manifest_fold_paths(manifest_path))

    # Layout best_overall.pt ở root của dataset (giorgosi/biohub-divnet-v2) -- quan trọng
    # vì manifest chỉ khai báo đường dẫn fold dạng weights/... không tồn tại trong dataset.
    for directory in dataset_dirs:
        candidates.extend([
            directory / "weights" / "divnet" / "fold0" / "best.pt",
            directory / "weights" / "divnet" / "best_overall.pt",
            directory / "best_overall.pt",
        ])
        candidates.extend(sorted((directory / "weights" / "divnet").glob("fold*/best.pt")))

    if input_root.exists():
        candidates.extend(sorted(input_root.glob("*/best_overall.pt")))
        candidates.extend(sorted(input_root.glob("datasets/*/biohub-divnet*/best_overall.pt")))
        candidates.extend(sorted(input_root.glob("biohub-divnet*/weights/divnet/fold*/best.pt")))
        candidates.extend(sorted(input_root.glob("biohub-divnet*/best_overall.pt")))
        candidates.extend(sorted(input_root.glob("datasets/*/biohub-divnet*/weights/divnet/fold*/best.pt")))

    seen: set[Path] = set()
    out: list[Path] = []
    for path in candidates:
        path = path.expanduser()
        try:
            key = path.resolve() if path.exists() else path
        except Exception:
            key = path
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def load_divnet_ranker() -> dict[str, object] | None:
    if not DIVNET_ENABLE:
        print("DivNet division ranker disabled by configuration."); return None
    if torch is None or _DivNetUNet3D is None:
        if DIVNET_REQUIRE: raise ImportError("torch is required for the DivNet division ranker")
        print("DivNet division ranker skipped because torch is unavailable."); return None
    from types import SimpleNamespace
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    load_errors: list[str] = []; models: list = []; geom = None
    for checkpoint_path in _divnet_checkpoint_candidates():
        if not checkpoint_path.exists(): continue
        try:
            print("Trying DivNet checkpoint:", checkpoint_path)
            checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
            if not isinstance(checkpoint, dict) or "model_state" not in checkpoint: raise ValueError("no model_state")
            cfg = checkpoint.get("config", {}) if isinstance(checkpoint.get("config", {}), dict) else {}
            inp = cfg.get("input", {}) if isinstance(cfg.get("input", {}), dict) else {}
            model_cfg = cfg.get("model", {}) if isinstance(cfg.get("model", {}), dict) else {}
            norm = cfg.get("normalization", {}) if isinstance(cfg.get("normalization", {}), dict) else {}
            if not inp: raise ValueError("missing input section")
            channels = int(inp.get("channels", 5)); base_channels = int(model_cfg.get("base_channels", 16))
            model = _DivNetUNet3D(in_channels=channels, base_channels=base_channels)
            model.load_state_dict(checkpoint["model_state"]); model.to(device); model.eval()
            marker_sigma = inp.get("marker_sigma", [1.5, 2.0, 2.0]); clip = norm.get("clip", [-0.5, 6.0])
            cand_geom = SimpleNamespace(channels=channels, crop_z=int(inp.get("crop_z", 16)),
                crop_yx=int(inp.get("crop_yx", 32)), pool_xy=int(inp.get("pool_xy", 4)),
                image_lags=[int(v) for v in inp.get("image_lags", [-1, 0, 1, 2])],
                marker_sigma=[float(v) for v in marker_sigma], lo_pct=float(norm.get("lo_pct", 50.0)),
                hi_pct=float(norm.get("hi_pct", 99.5)), clip_lo=float(clip[0]), clip_hi=float(clip[1]))
            if geom is None: geom = cand_geom
            else:
                for attr in ("channels", "crop_z", "crop_yx", "pool_xy", "image_lags", "marker_sigma"):
                    if getattr(geom, attr) != getattr(cand_geom, attr): raise ValueError(f"inconsistent {attr}")
            models.append(model)
            print("Loaded DivNet fold:", checkpoint_path, "| epoch", checkpoint.get("epoch"), "| best_score", checkpoint.get("best_score"))
        except Exception as exc:
            load_errors.append(f"{checkpoint_path}: {type(exc).__name__}: {exc}")
            print("Skipping incompatible DivNet checkpoint:", checkpoint_path, "|", type(exc).__name__, exc)
    if not models:
        message = "No usable DivNet checkpoint found. Attach giorgosi/biohub-divnet-v2."
        if DIVNET_REQUIRE: raise FileNotFoundError(message)
        print(message); return None
    with torch.no_grad():
        probe = torch.randn(2, geom.channels, geom.crop_z, geom.crop_yx, geom.crop_yx, device=device)
        out = torch.cat([torch.sigmoid(m(probe)) for m in models])
        if not torch.isfinite(out).all(): raise RuntimeError("DivNet ensemble non-finite")
    print(f"DivNet ranker ready: {len(models)} model(s), device {device}")
    return {"models": models, "geom": geom, "device": device, "torch": torch, "batch": max(1, DIVNET_BATCH), "rank_w_um": DIVNET_RANK_W_UM}


def _divnet_crop_with_valid(frame: np.ndarray, z0: int, y0: int, x0: int, ry: int, crop_z: int):
    crop = np.zeros((crop_z, ry, ry), dtype=np.float32); valid = np.zeros((crop_z, ry, ry), dtype=bool)
    Z, Y, X = frame.shape
    vz0, vz1 = max(0, z0), min(Z, z0 + crop_z); vy0, vy1 = max(0, y0), min(Y, y0 + ry); vx0, vx1 = max(0, x0), min(X, x0 + ry)
    if vz1 > vz0 and vy1 > vy0 and vx1 > vx0:
        sub = np.nan_to_num(frame[vz0:vz1, vy0:vy1, vx0:vx1]).astype(np.float32)
        crop[vz0 - z0:vz1 - z0, vy0 - y0:vy1 - y0, vx0 - x0:vx1 - x0] = sub
        valid[vz0 - z0:vz1 - z0, vy0 - y0:vy1 - y0, vx0 - x0:vx1 - x0] = True
    return crop, valid


def _divnet_marker_channel(z_off: float, y_off: float, x_off: float, geom) -> np.ndarray:
    zz = np.arange(geom.crop_z, dtype=np.float32)[:, None, None]; yy = np.arange(geom.crop_yx, dtype=np.float32)[None, :, None]; xx = np.arange(geom.crop_yx, dtype=np.float32)[None, None, :]
    sz, sy, sx = geom.marker_sigma
    g = ((zz - z_off)**2/(2.0*sz*sz) + (yy - y_off/geom.pool_xy)**2/(2.0*sy*sy) + (xx - x_off/geom.pool_xy)**2/(2.0*sx*sx))
    return np.exp(-g).astype(np.float32)


def _divnet_extract_crop(frames: list, query_zyx, geom) -> np.ndarray:
    qz, qy, qx = float(query_zyx[0]), float(query_zyx[1]), float(query_zyx[2]); ry = geom.crop_yx * geom.pool_xy
    z0 = int(math.floor(qz)) - geom.crop_z // 2; y0 = int(math.floor(qy)) - ry // 2; x0 = int(math.floor(qx)) - ry // 2
    channels = []
    for frame in frames:
        crop, valid = _divnet_crop_with_valid(frame, z0, y0, x0, ry, geom.crop_z)
        if int(valid.sum()) >= 64:
            vv = crop[valid]; lo = float(np.percentile(vv, geom.lo_pct)); hi = float(np.percentile(vv, geom.hi_pct))
        else: lo, hi = 0.0, 1.0
        if not (hi > lo): hi = lo + 1.0
        norm = np.clip((crop - lo) / (hi - lo), geom.clip_lo, geom.clip_hi); norm[~valid] = 0.0
        pooled = norm.reshape(geom.crop_z, geom.crop_yx, geom.pool_xy, geom.crop_yx, geom.pool_xy).mean(axis=(2, 4))
        channels.append(pooled.astype(np.float32))
    marker = _divnet_marker_channel(qz - z0, qy - y0, qx - x0, geom)
    return np.concatenate([np.stack(channels, axis=0), marker[None]], axis=0)


def _divnet_score_queries(bundle: dict, dataset, queries: list, frame_cache: dict, t_lo: int, t_hi: int) -> list:
    if not queries: return []
    geom = bundle["geom"]; models = bundle["models"]; device = bundle["device"]; torch_mod = bundle["torch"]
    crops = []
    for anchor_t, qz, qy, qx in queries:
        frames = [read_test_frame(dataset, int(min(max(anchor_t + lag, t_lo), t_hi)), frame_cache) for lag in geom.image_lags]
        crops.append(_divnet_extract_crop(frames, (qz, qy, qx), geom))
    x = torch_mod.from_numpy(np.stack(crops)).to(device=device, dtype=torch_mod.float32)
    probs = np.zeros(len(queries), dtype=np.float64)
    with torch_mod.no_grad():
        for s in range(0, len(x), bundle["batch"]):
            chunk = x[s:s + bundle["batch"]]; mean_sig = None
            for model in models:
                p_model = torch_mod.sigmoid(model(chunk) * 2.5); mean_sig = p_model if mean_sig is None else mean_sig + p_model
            probs[s:s + len(chunk)] = (mean_sig / len(models)).detach().cpu().numpy()
    return probs.tolist()


def _divnet_rerank_proposals(bundle: dict, dataset, t: int, proposals: list, nodes_by_id: dict,
                             frame_cache: dict, t_lo: int, t_hi: int, stats: dict) -> list:
    queries = [(int(t), float(nodes_by_id[int(p[1])]["z"]), float(nodes_by_id[int(p[1])]["y"]), float(nodes_by_id[int(p[1])]["x"])) for p in proposals]
    p_divs = _divnet_score_queries(bundle, dataset, queries, frame_cache, t_lo, t_hi); w = float(bundle["rank_w_um"])
    out = []
    for prop, p_div in zip(proposals, p_divs):
        _old_score, source_id, candidate_id, parent_dist, sister_dist = prop[0], prop[1], prop[2], prop[3], prop[4]
        out.append((parent_dist + 0.15 * sister_dist - w * float(p_div), source_id, candidate_id, parent_dist, sister_dist, float(p_div)))
    stats["divnet_proposals_scored"] += len(out)
    old_order = [p[1] for p in sorted(proposals, key=lambda item: item[0])]
    new_order = [p[1] for p in sorted(out, key=lambda item: item[0])]
    stats["divnet_rank_flips"] += sum(1 for a, b in zip(old_order, new_order) if a != b)
    return out
# [ver7b] ---------------- kết thúc khối DivNet ----------------


# ---- [wave1-slice:safediv] monolith ver-7b L2907-3055 (NGUYÊN VĂN) ----

# Add conservative division edges after ordinary temporal linking is complete
def add_safe_divisions_postlink(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]], stats: dict[str, int], dataset: str | None = None, deepcenter_bundle: dict[str, object] | None = None, frame_cache: dict[int, np.ndarray] | None = None, deepcenter_cache: dict[tuple[str, int], np.ndarray] | None = None, divnet_bundle: dict[str, object] | None = None) -> list[dict[str, object]]:
    if not OUTPUT_SAFE_DIVISIONS or not edges or (not nodes_by_id):
        return edges
    frame_cache = frame_cache if frame_cache is not None else {}
    deepcenter_cache = deepcenter_cache if deepcenter_cache is not None else {}
    out_by_source: dict[int, list[dict[str, object]]] = {}
    incoming: set[int] = set()

    for edge in edges:
        out_by_source.setdefault(int(edge['source_id']), []).append(edge)
        incoming.add(int(edge['target_id']))
    ids_by_t: dict[int, list[int]] = {}

    for node_id, node in nodes_by_id.items():
        ids_by_t.setdefault(int(node['t']), []).append(node_id)
    existing_edges = {(int(edge['source_id']), int(edge['target_id'])) for edge in edges}
    global_cap = max(1, int(round(max(1, len(edges)) * SAFE_DIV_GLOBAL_FRAC_CAP)))
    added: list[dict[str, object]] = []
    used_targets: set[int] = set()
    used_sources: set[int] = set()

    for t in sorted(ids_by_t):
        child_frame_ids = ids_by_t.get(t + 1, [])

        if not child_frame_ids:
            continue
        source_ids = [node_id for node_id in ids_by_t[t] if len(out_by_source.get(node_id, [])) == 1]
        candidate_ids = [node_id for node_id in child_frame_ids if node_id not in incoming and node_id not in used_targets]

        if not source_ids or not candidate_ids:
            continue
        candidate_tree = None

        if SAFE_DIV_REQUIRE_MUTUAL_NN:
            candidate_positions = np.stack([_position_um(nodes_by_id[cid]) for cid in candidate_ids])
            candidate_tree = cKDTree(candidate_positions)
        frame_cap = max(1, int(round(len(source_ids) * SAFE_DIV_FRAME_FRAC_CAP)))
        proposals: list[tuple[float, int, int, float, float]] = []

        for source_id in source_ids:
            source = nodes_by_id[source_id]
            existing_child_edge = out_by_source[source_id][0]
            existing_child_id = int(existing_child_edge['target_id'])
            existing_child = nodes_by_id.get(existing_child_id)

            if existing_child is None or int(existing_child['t']) != t + 1:
                continue
            child_dist = edge_distance_um(source, existing_child)

            if child_dist > SAFE_DIV_EXISTING_CHILD_MAX_UM:
                continue
            mutual_nn_id = None

            if candidate_tree is not None:
                _, nn_idx = candidate_tree.query(_position_um(existing_child))
                mutual_nn_id = candidate_ids[int(nn_idx)]

            for candidate_id in candidate_ids:
                if (source_id, candidate_id) in existing_edges:
                    continue
                candidate = nodes_by_id[candidate_id]
                parent_dist = edge_distance_um(source, candidate)

                if parent_dist > SAFE_DIV_MAX_UM:
                    continue
                sister_dist = edge_distance_um(existing_child, candidate)

                if sister_dist > SAFE_DIV_SISTER_MAX_UM:
                    continue

                if SAFE_DIV_REQUIRE_MUTUAL_NN and candidate_id != mutual_nn_id:
                    stats['safe_division_mutual_nn_rejected'] += 1
                    continue

                if SAFE_DIV_REQUIRE_DIVERGENCE:
                    c1_succ = out_by_source.get(existing_child_id, [])
                    q_succ = out_by_source.get(candidate_id, [])

                    if len(c1_succ) != 1 or len(q_succ) != 1:
                        stats['safe_division_divergence_rejected'] += 1
                        continue
                    c1_grandchild = nodes_by_id.get(int(c1_succ[0]['target_id']))
                    q_grandchild = nodes_by_id.get(int(q_succ[0]['target_id']))

                    if c1_grandchild is None or q_grandchild is None or int(c1_grandchild['t']) != t + 2 or (int(q_grandchild['t']) != t + 2):
                        stats['safe_division_divergence_rejected'] += 1
                        continue
                    grandchild_dist = edge_distance_um(c1_grandchild, q_grandchild)

                    if grandchild_dist - sister_dist < SAFE_DIV_DIVERGE_UM:
                        stats['safe_division_divergence_rejected'] += 1
                        continue
                stats['safe_division_geometric_candidates'] += 1

                if DEEPCENTER_SAFE_DIV_VETO and (not deepcenter_accept_repair_point(dataset, int(candidate['t']), node_point(candidate), deepcenter_bundle, frame_cache, deepcenter_cache, stats, 'safe_div', DEEPCENTER_SAFE_DIV_THRESHOLD)):
                    continue

                if SAFE_DIV_SISTER_SYMMETRY_TAU > 0.0:
                    symmetry_denominator = max((child_dist + parent_dist) / 2.0, 1e-6)

                    if abs(child_dist - parent_dist) / symmetry_denominator > SAFE_DIV_SISTER_SYMMETRY_TAU:
                        stats['safe_division_symmetry_rejected'] += 1
                        continue
                score = parent_dist + 0.15 * sister_dist
                proposals.append((score, source_id, candidate_id, parent_dist, sister_dist))
        stats['safe_division_candidates'] += len(proposals)

        if not proposals:
            continue

        # [ver7b] DIVNET INJECTION — xếp lại đề xuất theo P(division) của node mẹ (RANK-ONLY)
        if DIVNET_RANK and divnet_bundle is not None:
            t_lo_b, t_hi_b = (min(ids_by_t), max(ids_by_t)) if ids_by_t else (t, t)
            proposals = _divnet_rerank_proposals(divnet_bundle, dataset, t, proposals, nodes_by_id, frame_cache, t_lo_b, t_hi_b, stats)

        proposals.sort(key = lambda item: item[0])
        added_this_frame = 0

        for _score, source_id, candidate_id, parent_dist, _sister, *rest in proposals:
            p_div = rest[0] if rest else None
            if len(added) >= global_cap:
                stats['safe_division_skipped_cap'] += 1
                break

            if added_this_frame >= frame_cap:
                break

            if candidate_id in used_targets or candidate_id in incoming:
                continue

            if source_id in used_sources:
                continue
            candidate = nodes_by_id[candidate_id]
            added.append({'source_id': source_id, 'target_id': candidate_id, 'edge_prob': None, 'distance_um': parent_dist, 'safe_division': 1})

            # [ver7b] ghi nhận P(division) cho cạnh được thêm (audit + thống kê)
            if p_div is not None:
                added[-1]['divnet_p'] = round(float(p_div), 4)
                stats['divnet_p_added_sum'] += float(p_div)
                stats['divnet_p_added_n'] += 1
            used_targets.add(candidate_id)
            used_sources.add(source_id)
            added_this_frame += 1

    if added:
        stats['safe_divisions_added'] = len(added)
        return [*edges, *added]
    return edges


# ---- [wave1-slice:shorttrack] monolith ver-7b L3057-3184 (NGUYÊN VĂN) ----

# Remove weak short-track components while preserving protected lineage structures
def filter_short_track_components(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]], stats: dict[str, int]) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    if not OUTPUT_FILTER_SHORT_TRACKS or OUTPUT_MIN_TRACK_LEN <= 1 or (not edges):
        return (nodes_by_id, edges)
    parent = {node_id: node_id for node_id in nodes_by_id}

    # Find the canonical disjoint-set representative for a node
    def find(node_id: int) -> int:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    # Merge two disjoint-set components during connectivity construction
    def union(a: int, b: int) -> None:
        if a not in parent or b not in parent:
            return
        ra = find(a)
        rb = find(b)

        if ra != rb:
            parent[ra] = rb
    out_count: dict[int, int] = {}

    for edge in edges:
        source_id = int(edge['source_id'])
        target_id = int(edge['target_id'])
        union(source_id, target_id)
        out_count[source_id] = out_count.get(source_id, 0) + 1
    components: dict[int, list[int]] = {}

    for node_id in nodes_by_id:
        components.setdefault(find(node_id), []).append(node_id)
    component_edges: dict[int, list[dict[str, object]]] = {root: [] for root in components}

    for edge in edges:
        source_id = int(edge['source_id'])
        target_id = int(edge['target_id'])

        if source_id in parent and target_id in parent:
            component_edges.setdefault(find(source_id), []).append(edge)
    keep: set[int] = set()

    for root, members in components.items():
        has_division = any((out_count.get(node_id, 0) >= 2 for node_id in members))

        if len(members) >= OUTPUT_MIN_TRACK_LEN or (OUTPUT_KEEP_DIVISION_COMPONENTS and has_division):
            keep.update(members)

    if not keep:
        stats['short_track_filter_skipped_all'] += 1
        return (nodes_by_id, edges)
    removed_before_rescue = len(nodes_by_id) - len(keep)

    if removed_before_rescue <= 0:
        return (nodes_by_id, edges)

    if ADAPTIVE_SHORT_TRACK_RESCUE:
        removed_frac = removed_before_rescue / max(len(nodes_by_id), 1)

        if removed_frac >= SHORT_TRACK_RESCUE_TRIGGER_REMOVED_FRAC:
            budget = min(SHORT_TRACK_RESCUE_MAX_NODES_ABS, max(0, int(round(len(nodes_by_id) * SHORT_TRACK_RESCUE_MAX_NODES_FRAC))))
            stats['short_track_rescue_triggered'] = 1
            stats['short_track_rescue_budget'] = budget
            proposals: list[tuple[float, int, float, int, list[int]]] = []

            for root, members in components.items():
                if set(members) & keep:
                    continue

                if len(members) < SHORT_TRACK_RESCUE_MIN_LEN or len(members) >= OUTPUT_MIN_TRACK_LEN:
                    continue
                c_edges = component_edges.get(root, [])

                if not c_edges:
                    continue
                probs: list[float] = []
                dists: list[float] = []

                for edge in c_edges:
                    try:
                        prob = float(edge.get('edge_prob', 0.0))
                    except (TypeError, ValueError):
                        prob = 0.0

                    if np.isfinite(prob):
                        probs.append(prob)

                    try:
                        dist = float(edge.get('distance_um', np.nan))
                    except (TypeError, ValueError):
                        dist = np.nan

                    if np.isfinite(dist):
                        dists.append(dist)
                mean_prob = float(np.mean(probs)) if probs else 0.0
                mean_dist = float(np.mean(dists)) if dists else float('inf')

                if mean_prob < SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB:
                    continue

                if mean_dist > SHORT_TRACK_RESCUE_MAX_MEAN_EDGE_DIST_UM:
                    continue
                score = mean_prob - 0.02 * mean_dist + 0.004 * len(members)
                proposals.append((score, len(members), mean_prob, root, members))
            proposals.sort(reverse = True)
            rescued_nodes = 0
            rescued_components = 0

            for _, size, _, _, members in proposals:
                if budget <= 0 or rescued_nodes + size > budget:
                    continue
                keep.update(members)
                rescued_nodes += size
                rescued_components += 1
            stats['short_track_rescue_components'] = rescued_components
            stats['short_track_rescue_nodes'] = rescued_nodes
    removed_nodes = len(nodes_by_id) - len(keep)

    if removed_nodes <= 0:
        return (nodes_by_id, edges)
    kept_nodes = {node_id: node for node_id, node in nodes_by_id.items() if node_id in keep}
    kept_edges = [edge for edge in edges if int(edge['source_id']) in kept_nodes and int(edge['target_id']) in kept_nodes]
    stats['short_track_components_removed'] = sum((1 for members in components.values() if not set(members) & keep))
    stats['short_track_nodes_removed'] = removed_nodes
    stats['short_track_edges_removed'] = len(edges) - len(kept_edges)
    return (kept_nodes, kept_edges)


# ---- [wave1-slice:linefit] monolith ver-7b L3185-3255 (NGUYÊN VĂN) ----

# Smooth eligible track coordinates with a local line fit before export
def linefit_smooth_output_graph(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]], stats: dict[str, int]) -> dict[int, dict[str, object]]:
    """Smooth linear track interiors without changing graph topology."""

    if not OUTPUT_LINEFIT_SMOOTH or OUTPUT_LINEFIT_WEIGHT <= 0 or OUTPUT_LINEFIT_WINDOW <= 0 or (not edges):
        return nodes_by_id
    predecessor: dict[int, list[int]] = {}
    successor: dict[int, list[int]] = {}

    for edge in edges:
        source_id = int(edge['source_id'])
        target_id = int(edge['target_id'])
        source = nodes_by_id.get(source_id)
        target = nodes_by_id.get(target_id)

        if source is None or target is None:
            continue

        if int(target['t']) != int(source['t']) + 1:
            continue
        successor.setdefault(source_id, []).append(target_id)
        predecessor.setdefault(target_id, []).append(source_id)
    original_pos = {node_id: np.array([float(node['z']), float(node['y']), float(node['x'])], dtype = np.float64) for node_id, node in nodes_by_id.items()}
    updated_pos: dict[int, np.ndarray] = {}
    weight = float(np.clip(OUTPUT_LINEFIT_WEIGHT, 0.0, 1.0))

    for node_id in sorted(nodes_by_id):
        neighbourhood: list[tuple[int, int]] = [(0, node_id)]
        current = node_id

        for step in range(1, OUTPUT_LINEFIT_WINDOW + 1):
            prev_ids = predecessor.get(current, [])

            if len(prev_ids) != 1:
                break
            current = prev_ids[0]

            if current not in original_pos:
                break
            neighbourhood.append((-step, current))
        current = node_id

        for step in range(1, OUTPUT_LINEFIT_WINDOW + 1):
            next_ids = successor.get(current, [])

            if len(next_ids) != 1:
                break
            current = next_ids[0]

            if current not in original_pos:
                break
            neighbourhood.append((step, current))

        if len(neighbourhood) < 3:
            stats['linefit_skipped_nodes'] += 1
            continue
        dts = np.array([delta for delta, _ in neighbourhood], dtype = np.float64)
        coords = np.stack([original_pos[nid] for _, nid in neighbourhood])
        fitted = np.array([np.polyval(np.polyfit(dts, coords[:, axis], 1), 0.0) for axis in range(3)], dtype = np.float64)

        if not np.isfinite(fitted).all():
            stats['linefit_skipped_nodes'] += 1
            continue
        updated_pos[node_id] = (1.0 - weight) * original_pos[node_id] + weight * fitted

    for node_id, pos in updated_pos.items():
        nodes_by_id[node_id]['z'] = float(pos[0])
        nodes_by_id[node_id]['y'] = float(pos[1])
        nodes_by_id[node_id]['x'] = float(pos[2])
    stats['linefit_smoothed_nodes'] = len(updated_pos)
    return nodes_by_id


# ---- [wave1-slice:fog] monolith ver-7b L3257-3386 (NGUYÊN VĂN) ----

# Apply final graph validity filters and conservative repair rules
def filter_output_graph(nodes_by_id: dict[int, dict[str, object]], raw_edges: list[dict[str, object]], dataset: str | None = None, deepcenter_bundle: dict[str, object] | None = None, divnet_bundle: dict[str, object] | None = None) -> tuple[dict[int, dict[str, object]], list[dict[str, object]], dict[str, int]]:
    stats = {'raw_edges': len(raw_edges), 'dropped_nonconsecutive_edges': 0, 'dropped_long_edges': 0, 'dropped_multi_parent_edges': 0, 'dropped_multi_child_edges': 0, 'dropped_division_edges': 0, 'gap_candidates': 0, 'gap_pairs_selected': 0, 'gap_reused_existing': 0, 'gap_inserted_synthetic': 0, 'gap_added_nodes': 0, 'gap_added_edges': 0, 'gap_skipped_node_cap': 0, 'gap_density_nodes_scored': 0, 'gap_density_candidates_expanded': 0, 'gap_density_candidates_restricted': 0, 'gap_density_selected_outside_base': 0, 'gap_density_step_delta_milli_sum': 0, 'gap_refined_synthetic': 0, 'gap_refine_failed': 0, 'gap_refine_rejected_shift': 0, 'pruned_isolated_nodes': 0, 'motion_relink_edges': 0, 'motion_relink_tight_edges': 0, 'motion_relink_relaxed_edges': 0, 'motion_relink_frames': 0, 'motion_relink_replaced_raw_edges': 0, 'motion_relink_fallback_raw': 0, 'motion_relink_skipped_large_frame': 0, 'gap2_candidates': 0, 'gap2_pairs_selected': 0, 'gap2_added_nodes': 0, 'gap2_added_edges': 0, 'gap2_skipped_cap': 0, 'safe_division_candidates': 0, 'safe_division_geometric_candidates': 0, 'safe_divisions_added': 0, 'safe_division_skipped_cap': 0, 'safe_division_mutual_nn_rejected': 0, 'safe_division_divergence_rejected': 0, 'safe_division_symmetry_rejected': 0, 'divnet_proposals_scored': 0, 'divnet_rank_flips': 0, 'divnet_p_added_sum': 0.0, 'divnet_p_added_n': 0, 'deepcenter_gap_checked': 0, 'deepcenter_gap_bypassed_strong_motion': 0, 'deepcenter_gap_bypassed_observed_node': 0, 'deepcenter_gap_accepted': 0, 'deepcenter_gap_rejected': 0, 'deepcenter_gap_missing': 0, 'deepcenter_safe_div_checked': 0, 'deepcenter_safe_div_accepted': 0, 'deepcenter_safe_div_rejected': 0, 'deepcenter_safe_div_missing': 0, 'short_track_components_removed': 0, 'short_track_nodes_removed': 0, 'short_track_edges_removed': 0, 'short_track_filter_skipped_all': 0, 'short_track_rescue_triggered': 0, 'short_track_rescue_components': 0, 'short_track_rescue_nodes': 0, 'short_track_rescue_budget': 0, 'linefit_smoothed_nodes': 0, 'linefit_skipped_nodes': 0}
    edges: list[dict[str, object]] = []

    for edge in raw_edges:
        source = nodes_by_id.get(int(edge['source_id']))
        target = nodes_by_id.get(int(edge['target_id']))

        if source is None or target is None:
            continue

        if OUTPUT_ENFORCE_NEXT_FRAME and int(target['t']) != int(source['t']) + 1:
            stats['dropped_nonconsecutive_edges'] += 1
            continue
        distance_um = edge_distance_um(source, target)
        edge['distance_um'] = distance_um

        if OUTPUT_EDGE_MAX_UM > 0 and distance_um > OUTPUT_EDGE_MAX_UM:
            stats['dropped_long_edges'] += 1
            continue
        edges.append(edge)

    if OUTPUT_MOTION_RELINK:
        learned_edge_probs: dict[tuple[int, int], float] = {}

        for edge in edges:
            prob = edge.get('edge_prob')

            if prob is None:
                continue

            try:
                prob = float(prob)
            except (TypeError, ValueError):
                continue

            if np.isfinite(prob):
                key = (int(edge['source_id']), int(edge['target_id']))
                learned_edge_probs[key] = max(learned_edge_probs.get(key, float('-inf')), prob)
        motion_edges = motion_relink_edges(nodes_by_id, stats, learned_edge_probs)

        if motion_edges:
            stats['motion_relink_replaced_raw_edges'] = len(edges)
            edges = motion_edges
        else:
            stats['motion_relink_fallback_raw'] = 1

    if OUTPUT_SINGLE_PARENT_REPAIR and edges:
        best_by_target: dict[int, dict[str, object]] = {}

        for edge in edges:
            target_id = int(edge['target_id'])
            prev = best_by_target.get(target_id)

            if prev is None or edge_sort_key(edge) > edge_sort_key(prev):
                best_by_target[target_id] = edge
        kept_ids = {id(edge) for edge in best_by_target.values()}
        stats['dropped_multi_parent_edges'] = sum((1 for edge in edges if id(edge) not in kept_ids))
        edges = [edge for edge in edges if id(edge) in kept_ids]

    if OUTPUT_SINGLE_CHILD_REPAIR and edges:
        best_by_source: dict[int, dict[str, object]] = {}

        for edge in edges:
            source_id = int(edge['source_id'])
            prev = best_by_source.get(source_id)

            if prev is None or edge_sort_key(edge) > edge_sort_key(prev):
                best_by_source[source_id] = edge
        kept_ids = {id(edge) for edge in best_by_source.values()}
        stats['dropped_multi_child_edges'] = sum((1 for edge in edges if id(edge) not in kept_ids))
        edges = [edge for edge in edges if id(edge) in kept_ids]
    print(f'[{dataset}] after edge-filter+motion-relink: {len(nodes_by_id)} nodes, {len(edges)} edges')
    repair_frame_cache: dict[int, np.ndarray] = {}
    deepcenter_heatmap_cache: dict[tuple[str, int], np.ndarray] = {}
    nodes_by_id, edges = close_single_frame_gaps(nodes_by_id, edges, stats, dataset = dataset, deepcenter_bundle = deepcenter_bundle, frame_cache = repair_frame_cache, deepcenter_cache = deepcenter_heatmap_cache)
    nodes_by_id, edges = recover_strict_gap2(nodes_by_id, edges, stats, dataset = dataset)
    print(f'[{dataset}] after gap-closing (single-frame + gap2): {len(nodes_by_id)} nodes, {len(edges)} edges')
    edges = add_safe_divisions_postlink(nodes_by_id, edges, stats, dataset = dataset, deepcenter_bundle = deepcenter_bundle, frame_cache = repair_frame_cache, deepcenter_cache = deepcenter_heatmap_cache, divnet_bundle = divnet_bundle)
    _geo_cands = stats['safe_division_geometric_candidates']
    _post_veto_cands = stats['safe_division_candidates']
    _rejected_by_dc = _geo_cands - _post_veto_cands
    _divnet_info = f", divnet_scored = {stats['divnet_proposals_scored']}, divnet_rank_flips = {stats['divnet_rank_flips']}, divnet_p_added_mean = {(stats['divnet_p_added_sum'] / stats['divnet_p_added_n']) if stats['divnet_p_added_n'] else 0.0:.3f}" if stats['divnet_p_added_n'] else ""
    print(f"[{dataset}] after safe-division repair: {len(nodes_by_id)} nodes, {len(edges)} edges (geometric_candidates = {_geo_cands}, deepcenter_rejected = {_rejected_by_dc}, post_veto_candidates = {_post_veto_cands}, added = {stats['safe_divisions_added']}, cap_skipped = {stats['safe_division_skipped_cap']}, mutual_nn_rejected = {stats['safe_division_mutual_nn_rejected']}, divergence_rejected = {stats['safe_division_divergence_rejected']}{_divnet_info})")

    if OUTPUT_DIVISION_GEOMETRY_FILTER and edges:
        by_source: dict[int, list[dict[str, object]]] = {}

        for edge in edges:
            by_source.setdefault(int(edge['source_id']), []).append(edge)
        filtered: list[dict[str, object]] = []

        for source_id, source_edges in by_source.items():
            if len(source_edges) <= 1:
                filtered.extend(source_edges)
                continue
            ranked = sorted(source_edges, key = edge_sort_key, reverse = True)
            source = nodes_by_id[source_id]
            top1 = ranked[0]
            top2 = ranked[1]
            d1 = float(top1['distance_um'])
            d2 = float(top2['distance_um'])
            sister = edge_distance_um(nodes_by_id[int(top1['target_id'])], nodes_by_id[int(top2['target_id'])])
            valid_division = max(d1, d2) <= DIV_PARENT_MAX_UM and sister <= DIV_SISTER_MAX_UM and (int(nodes_by_id[int(top1['target_id'])]['t']) == int(source['t']) + 1) and (int(nodes_by_id[int(top2['target_id'])]['t']) == int(source['t']) + 1)

            if valid_division:
                filtered.extend([top1, top2])
                stats['dropped_division_edges'] += max(0, len(ranked) - 2)
            elif DIV_DROP_TO_SINGLE_IF_BAD:
                filtered.append(top1)
                stats['dropped_division_edges'] += len(ranked) - 1
            else:
                filtered.extend(ranked)
        edges = filtered

    if OUTPUT_PRUNE_ISOLATED:
        incident = {int(edge['source_id']) for edge in edges} | {int(edge['target_id']) for edge in edges}

        if incident:
            kept_nodes = {node_id: node for node_id, node in nodes_by_id.items() if node_id in incident}
            stats['pruned_isolated_nodes'] = len(nodes_by_id) - len(kept_nodes)
            nodes_by_id = kept_nodes
            edges = [edge for edge in edges if int(edge['source_id']) in nodes_by_id and int(edge['target_id']) in nodes_by_id]
    print(f'[{dataset}] after division-geometry-filter+prune-isolated: {len(nodes_by_id)} nodes, {len(edges)} edges')
    nodes_by_id, edges = filter_short_track_components(nodes_by_id, edges, stats)
    print(f"[{dataset}] after short-track filtering: {len(nodes_by_id)} nodes, {len(edges)} edges (components_removed = {stats['short_track_components_removed']})")
    nodes_by_id = linefit_smooth_output_graph(nodes_by_id, edges, stats)
    print(f'[{dataset}] FINAL: {len(nodes_by_id)} nodes, {len(edges)} edges')
    return (nodes_by_id, edges, stats)


# ---- [wave1-slice:scoring] monolith ver-7b L3668-3919 (NGUYÊN VĂN) ----

# Match predicted and ground-truth nodes with one-to-one spatial assignment
def match_nodes_bipartite(pred_nodes: dict, gt_nodes: dict, max_dist: float = 7.0):
    pred_by_t: dict[int, list[int]] = {}
    for pid, (t, *_r) in pred_nodes.items():
        pred_by_t.setdefault(int(t), []).append(pid)
    gt_by_t: dict[int, list[int]] = {}
    for gid, (t, *_r) in gt_nodes.items():
        gt_by_t.setdefault(int(t), []).append(gid)
    pred_to_gt: dict[int, int] = {}
    gt_to_pred: dict[int, int] = {}
    for t, p_ids in pred_by_t.items():
        g_ids = gt_by_t.get(t, [])
        if not g_ids:
            continue
        voxel_scale = np.array(VOXEL_SCALE_UM, dtype = float)
        p_pos = np.array([pred_nodes[p][1:] for p in p_ids], dtype = float) * voxel_scale
        g_pos = np.array([gt_nodes[g][1:] for g in g_ids], dtype = float) * voxel_scale
        diff = p_pos[:, None, :] - g_pos[None, :, :]
        cost = np.sqrt((diff ** 2).sum(axis = -1))
        BIG = 1000000.0
        cost_gated = np.where(cost <= max_dist, cost, BIG)
        row_ind, col_ind = linear_sum_assignment(cost_gated)
        for r, c in zip(row_ind, col_ind):
            if cost_gated[r, c] >= BIG:
                continue
            pred_to_gt[p_ids[r]] = g_ids[c]
            gt_to_pred[g_ids[c]] = p_ids[r]
    return (pred_to_gt, gt_to_pred)

# Compute edge true positives, false positives, and false negatives after node matching
def compute_edge_confusion(pred_edges, gt_edges, pred_to_gt, gt_to_pred):
    gt_edge_set = set(gt_edges)
    gt_outgoing: dict[int, set[int]] = {}
    gt_incoming_source: dict[int, int] = {}
    for s, t in gt_edge_set:
        gt_outgoing.setdefault(s, set()).add(t)
        gt_incoming_source[t] = s
    tp = 0
    fp = 0
    matched_gt_edges = set()
    for s, t in pred_edges:
        ms = pred_to_gt.get(s)
        mt = pred_to_gt.get(t)
        is_tp = ms is not None and mt is not None and (mt in gt_outgoing.get(ms, ()))
        if is_tp:
            tp += 1
            matched_gt_edges.add((ms, mt))
            continue
        is_fp = mt is not None and mt in gt_incoming_source or (ms is not None and bool(gt_outgoing.get(ms)))
        if is_fp:
            fp += 1
    fn = len(gt_edge_set - matched_gt_edges)
    return (tp, fp, fn)

# Compute the edge jaccard component of the validator metric
def edge_jaccard(tp: int, fp: int, fn: int) -> float:
    denom = tp + fp + fn
    return tp / denom if denom else 0.0

# Apply the node-count penalty to the edge jaccard score
def adjusted_jaccard(jaccard: float, t_pred: int, t_true, a: float = 0.1) -> float:
    if not t_true or t_true <= 0:
        return jaccard
    return max(0.0, jaccard * (1.0 - a * (t_pred - t_true) / t_true))

# Build weakly connected components for patched division matching
def weakly_connected_components(node_ids, edges):
    parent = {n: n for n in node_ids}

    # Find the current disjoint-set representative
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    # Merge two disjoint-set components
    def union(a, b):
        ra, rb = (find(a), find(b))
        if ra != rb:
            parent[ra] = rb
    for s, t in edges:
        if s in parent and t in parent:
            union(s, t)
    return {n: find(n) for n in node_ids}

# Compute division true positives, false positives, and false negatives
def compute_division_confusion(pred_nodes, pred_edges, gt_nodes, gt_edges, pred_to_gt, gt_to_pred):
    gt_out: dict[int, set[int]] = {}
    gt_in: dict[int, int] = {}
    for s, t in gt_edges:
        gt_out.setdefault(s, set()).add(t)
        gt_in[t] = s
    pred_out: dict[int, set[int]] = {}
    for s, t in pred_edges:
        pred_out.setdefault(s, set()).add(t)
    pred_node_ids = list(pred_nodes.keys())
    pred_edge_list = list(pred_edges)
    components = weakly_connected_components(pred_node_ids, pred_edge_list)
    fork_components = {components[n] for n, outs in pred_out.items() if len(outs) >= 2 and n in components}
    gt_division_sources = [s for s, outs in gt_out.items() if len(outs) >= 2]

    # Collect lineage descendants used by patched division matching
    def lineage_descendants(root_child: int) -> set[int]:
        seen = {root_child}
        stack = [root_child]
        while stack:
            cur = stack.pop()
            for nxt in gt_out.get(cur, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen
    tp = 0
    fn = 0
    tp_gt_sources: set[int] = set()
    for gsrc in gt_division_sources:
        children = sorted(gt_out[gsrc])
        if len(children) < 2:
            continue
        anchor_candidates = [gsrc]
        if gsrc in gt_in:
            anchor_candidates.append(gt_in[gsrc])
        anchor_pred_nodes = [gt_to_pred[a] for a in anchor_candidates if a in gt_to_pred]
        lineage_hit_components: list[set[int]] = []
        ok = True
        for child in children[:2]:
            lineage = lineage_descendants(child)
            hit_comp_ids = {components[p_id] for gt_id in lineage if (p_id := gt_to_pred.get(gt_id)) is not None and p_id in components}
            if not hit_comp_ids:
                ok = False
                break
            lineage_hit_components.append(hit_comp_ids)
        if not ok or not anchor_pred_nodes:
            fn += 1
            continue
        anchor_comp_ids = {components[p] for p in anchor_pred_nodes if p in components}
        if not anchor_comp_ids:
            fn += 1
            continue
        found = any((comp_id in lineage_hit_components[0] and comp_id in lineage_hit_components[1] and (comp_id in fork_components) for comp_id in anchor_comp_ids))
        if found:
            tp += 1
            tp_gt_sources.add(gsrc)
        else:
            fn += 1
    fp = 0
    for n, outs in pred_out.items():
        if len(outs) < 2:
            continue
        g = pred_to_gt.get(n)
        if g is None or g not in gt_out or g in tp_gt_sources:
            continue
        fp += 1
    return (tp, fp, fn)

# Decompose validator errors into the official metric components
def decompose_errors(pred_nodes, gt_nodes, pred_edges, gt_edges, pred_to_gt, gt_to_pred):
    gt_edge_set = set(gt_edges)
    pred_edge_set = set(pred_edges)
    gt_outgoing: dict[int, set[int]] = {}
    for s, t in gt_edge_set:
        gt_outgoing.setdefault(s, set()).add(t)
    missed_gt_nodes = sum((1 for g in gt_nodes if g not in gt_to_pred))
    spurious_pred_nodes = sum((1 for p in pred_nodes if p not in pred_to_gt))
    recovered = fragmented = lost_to_detection = 0
    for gs, gtid in gt_edge_set:
        ps, pt = (gt_to_pred.get(gs), gt_to_pred.get(gtid))
        if ps is None or pt is None:
            lost_to_detection += 1
        elif (ps, pt) in pred_edge_set:
            recovered += 1
        else:
            fragmented += 1
    wrong_association = 0
    for ps, pt in pred_edge_set:
        ms, mt = (pred_to_gt.get(ps), pred_to_gt.get(pt))
        if ms is not None and mt is not None and (mt not in gt_outgoing.get(ms, ())):
            wrong_association += 1
    return {'missed_gt_nodes': missed_gt_nodes, 'spurious_pred_nodes': spurious_pred_nodes, 'edges_recovered': recovered, 'edges_fragmented': fragmented, 'edges_lost_to_detection': lost_to_detection, 'wrong_association_edges': wrong_association}

# Read a nested metadata key from the ground-truth geff payload
def _find_key_recursive(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _find_key_recursive(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_key_recursive(item, key)
            if found is not None:
                return found
    return None

# Read the estimated true node count used by the metric penalty
def read_estimated_true_node_count(geff_path: Path):
    for candidate in (geff_path / 'zarr.json', geff_path / '.zattrs'):
        if not candidate.exists():
            continue
        try:
            payload = json.loads(candidate.read_text())
        except Exception:
            continue
        found = _find_key_recursive(payload, 'estimated_number_of_nodes')
        if found is not None:
            try:
                return float(found)
            except (TypeError, ValueError):
                continue
    return None

# Convert a geff graph into plain node and edge structures
def graph_to_plain(graph):
    nodes: dict[int, tuple] = {}
    for row in graph.node_attrs().iter_rows(named = True):
        node_id = int(row['node_id'])
        nodes[node_id] = (int(row['t']), float(row['z']), float(row['y']), float(row['x']))
    edges: list[tuple[int, int]] = []
    for row in graph.edge_attrs().iter_rows(named = True):
        edges.append((int(row['source_id']), int(row['target_id'])))
    return (nodes, edges)

# Convert processed node dictionaries into validator node tuples
def nodes_by_id_to_plain(nodes_by_id):
    return {nid: (int(n['t']), float(n['z']), float(n['y']), float(n['x'])) for nid, n in nodes_by_id.items()}

# Score one held-out sample with the official metric components
def score_sample(pred_nodes_plain, pred_edges_plain, gt_nodes_plain, gt_edges_plain, t_true):
    p2g, g2p = match_nodes_bipartite(pred_nodes_plain, gt_nodes_plain, max_dist = VALIDATOR_MATCH_RADIUS_UM)
    tp, fp, fn = compute_edge_confusion(pred_edges_plain, gt_edges_plain, p2g, g2p)
    jac = edge_jaccard(tp, fp, fn)
    t_pred = len(pred_nodes_plain)
    adj = adjusted_jaccard(jac, t_pred, t_true, a = VALIDATOR_NODE_COUNT_PENALTY_A)
    div_tp, div_fp, div_fn = compute_division_confusion(pred_nodes_plain, pred_edges_plain, gt_nodes_plain, gt_edges_plain, p2g, g2p)
    errors = decompose_errors(pred_nodes_plain, gt_nodes_plain, pred_edges_plain, gt_edges_plain, p2g, g2p)
    div_jac = edge_jaccard(div_tp, div_fp, div_fn)
    row = {'edge_tp': tp, 'edge_fp': fp, 'edge_fn': fn, 'edge_jaccard': jac, 't_pred': t_pred, 't_true': t_true, 'adjusted_edge_jaccard': adj, 'div_tp': div_tp, 'div_fp': div_fp, 'div_fn': div_fn, 'div_jaccard': div_jac, 'weight': tp + fp + fn}
    row.update(errors)
    return row

# Aggregate held-out sample scores with the official competition formula
def aggregate_official(sample_rows):
    total_w = sum((r['weight'] for r in sample_rows)) or 1
    weighted_adj = sum((r['adjusted_edge_jaccard'] * r['weight'] for r in sample_rows)) / total_w
    div_tp = sum((r['div_tp'] for r in sample_rows))
    div_fp = sum((r['div_fp'] for r in sample_rows))
    div_fn = sum((r['div_fn'] for r in sample_rows))
    div_jac = edge_jaccard(div_tp, div_fp, div_fn)
    return {'adjusted_edge_jaccard': weighted_adj, 'division_jaccard': div_jac, 'proxy_score': weighted_adj + VALIDATOR_DIVISION_WEIGHT * div_jac, 'div_tp': div_tp, 'div_fp': div_fp, 'div_fn': div_fn, 'missed_gt_nodes': sum((r['missed_gt_nodes'] for r in sample_rows)), 'spurious_pred_nodes': sum((r['spurious_pred_nodes'] for r in sample_rows)), 'edges_recovered': sum((r['edges_recovered'] for r in sample_rows)), 'edges_fragmented': sum((r['edges_fragmented'] for r in sample_rows)), 'edges_lost_to_detection': sum((r['edges_lost_to_detection'] for r in sample_rows)), 'wrong_association_edges': sum((r['wrong_association_edges'] for r in sample_rows))}



# ============================================================================
# [wave1] PHẦN 2 — code MỚI (audit collector, replay grid, E1/E2/E3, official)
# Tất cả hàm postprocess/scoring ở trên là slice nguyên văn từ ver-7b monolith.
# ============================================================================

# --- hằng validator (slice từ monolith 3513-3517, đặt lại tại đây) ------------
VALIDATOR_MATCH_RADIUS_UM = float(os.environ.get('BIOHUB_VALIDATOR_MATCH_RADIUS_UM', '7.0'))
VALIDATOR_NODE_COUNT_PENALTY_A = float(os.environ.get('BIOHUB_VALIDATOR_NODE_COUNT_PENALTY_A', '0.1'))
VALIDATOR_DIVISION_WEIGHT = float(os.environ.get('BIOHUB_VALIDATOR_DIVISION_WEIGHT', '0.1'))

# --- bộ override "sweepable" (giống pp_apply/pp_restore của monolith) --------
WAVE1_PP_KEYS = ['SAFE_DIV_MAX_UM', 'SAFE_DIV_SISTER_MAX_UM', 'SAFE_DIV_DIVERGE_UM',
                'SAFE_DIV_SISTER_SYMMETRY_TAU', 'SAFE_DIV_EXISTING_CHILD_MAX_UM',
                'SAFE_DIV_FRAME_FRAC_CAP', 'SAFE_DIV_GLOBAL_FRAC_CAP',
                'DEEPCENTER_SAFE_DIV_THRESHOLD', 'DEEPCENTER_GAP_THRESHOLD',
                'GAP_CLOSE_UM', 'OUTPUT_MIN_TRACK_LEN',
                'SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB', 'MOTION_RELINK_TIGHT_UM',
                'MOTION_RELINK_RELAXED_UM', 'GAP2_MAX_STEP_UM', 'GAP2_MAX_TOTAL_UM',
                'MOTION_RELINK_LEARNED_BONUS', 'MOTION_RELINK_VELOCITY_WEIGHT',
                'GAP_CLOSE_REUSE_UM', 'OUTPUT_EDGE_MAX_UM']
WAVE1_BASE_CONFIG = {key: globals()[key] for key in WAVE1_PP_KEYS}


def wave1_pp_apply(config: dict) -> dict:
    saved = {key: globals()[key] for key in config}
    for key, value in config.items():
        if key not in WAVE1_PP_KEYS:
            raise KeyError(f'{key} is not sweepable')
        globals()[key] = type(WAVE1_BASE_CONFIG[key])(value)
    return saved


def wave1_pp_restore(saved: dict) -> None:
    for key, value in saved.items():
        globals()[key] = value


# ---------------------------------------------------------------------------
# [wave1] Ghi graph postprocess ra .geff — tái hiện NGUYÊN VĂN pattern
# build_graph + save_graph của repo (predict_unet_transformer.py dòng 118-145,
# 564): InMemoryGraph + add_node_attr_key z/y/x + bulk_add_nodes + edge keys
# edge_prob/edge_dist + to_geff.
# ---------------------------------------------------------------------------
def wave1_write_system_geff(nodes_by_id: dict, edges: list, out_path: Path) -> None:
    import polars as pl
    graph = td.graph.InMemoryGraph()
    for key in ['z', 'y', 'x']:
        graph.add_node_attr_key(key, pl.Float64, -999999.0)
    ordered = sorted(nodes_by_id.keys())
    new_ids = graph.bulk_add_nodes([
        {'t': int(nodes_by_id[nid]['t']), 'z': float(nodes_by_id[nid]['z']),
         'y': float(nodes_by_id[nid]['y']), 'x': float(nodes_by_id[nid]['x'])}
        for nid in ordered
    ])
    id_map = {old: new for old, new in zip(ordered, new_ids)}
    if edges:
        graph.add_edge_attr_key('edge_prob', pl.Float64, 0.0)
        graph.add_edge_attr_key('edge_dist', pl.Float64, 0.0)
        graph.bulk_add_edges([
            {'source_id': id_map[int(e['source_id'])], 'target_id': id_map[int(e['target_id'])],
             'edge_prob': float(e.get('edge_prob') if e.get('edge_prob') is not None else 0.0),
             'edge_dist': float(e.get('distance_um') if e.get('distance_um') is not None else 0.0)}
            for e in edges if int(e['source_id']) in id_map and int(e['target_id']) in id_map
        ])
    graph.to_geff(out_path)


# ---------------------------------------------------------------------------
# [wave1] E1 — system view: filter_output_graph (nguyên văn, config production
# + selected) → ghi .geff → chấm official scorer (đúng luật thật).
# ---------------------------------------------------------------------------
def wave1_official_score_geff(pred_path: Path, gt_path: Path, td_metrics, td_div) -> dict:
    evaluate, node_recall, per_sample_metrics = td_metrics
    score_divisions = td_div
    t_true = read_estimated_true_node_count(gt_path)
    pred = graph_from_geff(pred_path)
    gt = graph_from_geff(gt_path)
    er = evaluate(pred, gt, scale=VOXEL_SCALE_UM, max_distance=7.0)
    rec = node_recall(pred, gt) if (pred.num_nodes() and pred.num_edges()) else 0.0
    m = per_sample_metrics(er, t_true if t_true is not None else float('nan'), rec)
    div = score_divisions(graph_from_geff(pred_path), gt, scale=VOXEL_SCALE_UM, max_distance=7.0)
    scores = div.scores
    div_tp = sum(int(v) for v in scores.values())
    div_fn = len(scores) - div_tp
    div_fp = len(div.fp_forks)
    tp, fp, fn = int(m['edge_tp']), int(m['edge_fp']), int(m['edge_fn'])
    denom = tp + fp + fn
    ratio = float(m.get('total_node_ratio')) if m.get('total_node_ratio') is not None else None
    return {'stem': pred_path.stem, 'rule': 'official', 'edge_tp': tp, 'edge_fp': fp,
            'edge_fn': fn, 'edge_jaccard': (tp / denom if denom else None),
            't_pred': int(m.get('num_pred_nodes') or 0), 't_true': t_true,
            'total_node_ratio': ratio,
            'node_multiplier_term': (0.1 * ratio) if ratio is not None else None,
            'adjusted_edge_jaccard': m.get('adj_edge_jaccard'),
            'node_recall': m.get('node_recall'),
            'div_tp': div_tp, 'div_fp': div_fp, 'div_fn': div_fn,
            'division_jaccard': (div_tp / (div_tp + div_fp + div_fn)
                                 if (div_tp + div_fp + div_fn) else None),
            'weight': denom,
            'division_events': [{'gt_div_node': int(k), 'recovered': int(v)}
                                for k, v in sorted(scores.items())]}


def wave1_official_micro(rows: list) -> dict:
    tp = sum(r['edge_tp'] for r in rows)
    fp = sum(r['edge_fp'] for r in rows)
    fn = sum(r['edge_fn'] for r in rows)
    w = sum(r['weight'] for r in rows) or 1
    adj_rows = [r for r in rows if r.get('adjusted_edge_jaccard') is not None]
    adj = (sum(r['adjusted_edge_jaccard'] * r['weight'] for r in adj_rows)
           / sum(r['weight'] for r in adj_rows)) if adj_rows else None
    dtp = sum(r['div_tp'] for r in rows)
    dfp = sum(r['div_fp'] for r in rows)
    dfn = sum(r['div_fn'] for r in rows)
    dj = dtp / (dtp + dfp + dfn) if (dtp + dfp + dfn) else None
    return {'n': len(rows), 'edge_tp': tp, 'edge_fp': fp, 'edge_fn': fn,
            'edge_jaccard': tp / (tp + fp + fn) if (tp + fp + fn) else None,
            'adjusted_edge_jaccard': adj, 'div_tp': dtp, 'div_fp': dfp, 'div_fn': dfn,
            'division_jaccard': dj,
            'proxy_score': (adj if adj is not None else 0.0) + (0.1 * dj if dj is not None else 0.0)}


# --- chạy postprocess pipeline cho 1 stem (dùng hàm slice nguyên văn) --------
def wave1_run_pipeline(raw_nodes: dict, raw_edges: list, stem: str,
                       deepcenter_bundle, divnet_bundle=None):
    nodes_copy = {nid: dict(n) for nid, n in raw_nodes.items()}
    edges_copy = [dict(e) for e in raw_edges]
    processed_nodes, processed_edges, stage_stats = filter_output_graph(
        nodes_copy, edges_copy, dataset=stem,
        deepcenter_bundle=deepcenter_bundle, divnet_bundle=divnet_bundle)
    return processed_nodes, processed_edges, stage_stats


def wave1_internal_score(processed_nodes, processed_edges, gt_plain, t_true):
    pred_nodes_plain = nodes_by_id_to_plain(processed_nodes)
    pred_edges_plain = [(int(e['source_id']), int(e['target_id'])) for e in processed_edges]
    return score_sample(pred_nodes_plain, pred_edges_plain, gt_plain[0], gt_plain[1], t_true)


# ---------------------------------------------------------------------------
# [wave1] AUDIT COLLECTOR — đi qua cấu trúc add_safe_divisions_postlink với gate
# RỘNG NHẤT (MAX 14 / SISTER 18 / EXISTING_CHILD 12) để thu TOÀN BỘ đặc trưng
# của từng cặp (source, candidate). Đặc trưng KHÔNG phụ thuộc gate (đã phân tích
# kỹ: mutual-NN dùng candidate_ids cố định khung; divergence dùng pre-state;
# p_div theo node mẹ; dc_score theo điểm candidate) → grid E0 replay thuần số.
# ---------------------------------------------------------------------------
WAVE1_COLLECT_MAX_UM = 14.0
WAVE1_COLLECT_SISTER_MAX_UM = 18.0
WAVE1_COLLECT_EXISTING_CHILD_MAX_UM = 12.0


def wave1_collect_safe_div_features(stem, nodes_by_id, edges, deepcenter_bundle,
                                    divnet_bundle, frame_cache, deepcenter_cache,
                                    gt_plain):
    """Trả về dict đặc trưng + nhãn GT cho mọi cặp (source, candidate) trong tầm
    gate rộng nhất. Cấu trúc bám sát add_safe_divisions_postlink (monolith
    2908-3055) — chỉ THÊM ghi chép, KHÔNG đổi logic chọn."""
    gt_nodes, gt_edges = gt_plain
    p2g, g2p = match_nodes_bipartite(
        {nid: (int(n['t']), float(n['z']), float(n['y']), float(n['x']))
         for nid, n in nodes_by_id.items()}, gt_nodes, max_dist=7.0)
    gt_out_deg = Counter()
    gt_edge_set = set(gt_edges)
    for s, t in gt_edge_set:
        gt_out_deg[s] += 1

    out_by_source = {}
    incoming = set()
    for edge in edges:
        out_by_source.setdefault(int(edge['source_id']), []).append(edge)
        incoming.add(int(edge['target_id']))
    ids_by_t = {}
    for node_id, node in nodes_by_id.items():
        ids_by_t.setdefault(int(node['t']), []).append(node_id)
    existing_edges = {(int(e['source_id']), int(e['target_id'])) for e in edges}

    dc_scores = {}
    pdiv_cache = {}
    features = []  # từng dòng: dict đặc trưng đầy đủ

    def dc_score_of(candidate):
        cid = int(candidate['node_id'])
        if cid not in dc_scores:
            dc_scores[cid] = deepcenter_score_point(
                stem, int(candidate['t']), node_point(candidate), deepcenter_bundle,
                frame_cache, deepcenter_cache)
        return dc_scores[cid]

    def pdiv_of(source_id):
        if source_id not in pdiv_cache:
            if divnet_bundle is None:
                pdiv_cache[source_id] = None
            else:
                src = nodes_by_id[source_id]
                t_lo, t_hi = (min(ids_by_t), max(ids_by_t)) if ids_by_t else (0, 0)
                p = _divnet_score_queries(
                    divnet_bundle, stem,
                    [(int(src['t']), float(src['z']), float(src['y']), float(src['x']))],
                    frame_cache, t_lo, t_hi)
                pdiv_cache[source_id] = float(p[0]) if p else None
        return pdiv_cache[source_id]

    for t in sorted(ids_by_t):
        child_frame_ids = ids_by_t.get(t + 1, [])
        if not child_frame_ids:
            continue
        source_ids = [nid for nid in ids_by_t[t] if len(out_by_source.get(nid, [])) == 1]
        candidate_ids = [nid for nid in child_frame_ids if nid not in incoming]
        if not source_ids or not candidate_ids:
            continue
        candidate_positions = np.stack([_position_um(nodes_by_id[cid]) for cid in candidate_ids])
        candidate_tree = cKDTree(candidate_positions)
        for source_id in source_ids:
            source = nodes_by_id[source_id]
            existing_child_edge = out_by_source[source_id][0]
            existing_child_id = int(existing_child_edge['target_id'])
            existing_child = nodes_by_id.get(existing_child_id)
            if existing_child is None or int(existing_child['t']) != t + 1:
                continue
            child_dist = edge_distance_um(source, existing_child)
            if child_dist > WAVE1_COLLECT_EXISTING_CHILD_MAX_UM:
                continue
            _, nn_idx = candidate_tree.query(_position_um(existing_child))
            mutual_nn_id = candidate_ids[int(nn_idx)]
            c1_succ = out_by_source.get(existing_child_id, [])
            for candidate_id in candidate_ids:
                if (source_id, candidate_id) in existing_edges:
                    continue
                candidate = nodes_by_id[candidate_id]
                parent_dist = edge_distance_um(source, candidate)
                if parent_dist > WAVE1_COLLECT_MAX_UM:
                    continue
                sister_dist = edge_distance_um(existing_child, candidate)
                if sister_dist > WAVE1_COLLECT_SISTER_MAX_UM:
                    continue
                # divergence (đặc trưng)
                q_succ = out_by_source.get(candidate_id, [])
                diverge_margin = None
                if len(c1_succ) == 1 and len(q_succ) == 1:
                    c1g = nodes_by_id.get(int(c1_succ[0]['target_id']))
                    qg = nodes_by_id.get(int(q_succ[0]['target_id']))
                    if (c1g is not None and qg is not None
                            and int(c1g['t']) == t + 2 and int(qg['t']) == t + 2):
                        diverge_margin = edge_distance_um(c1g, qg) - sister_dist
                symmetry_ratio = abs(child_dist - parent_dist) / max((child_dist + parent_dist) / 2.0, 1e-6)
                dc_s = dc_score_of(candidate)
                p_d = pdiv_of(source_id)
                # nhãn GT
                g_s = p2g.get(int(source_id))
                g_c = p2g.get(int(candidate_id))
                gt_div_edge = bool(g_s is not None and g_c is not None
                                   and (g_s, g_c) in gt_edge_set and gt_out_deg.get(g_s, 0) >= 2)
                features.append({
                    'stem': stem, 't': int(t), 'source_id': int(source_id),
                    'candidate_id': int(candidate_id),
                    'existing_child_id': int(existing_child_id),
                    'parent_dist': float(parent_dist), 'sister_dist': float(sister_dist),
                    'child_dist': float(child_dist), 'mutual_nn': bool(candidate_id == mutual_nn_id),
                    'diverge_margin': (float(diverge_margin) if diverge_margin is not None else None),
                    'symmetry_ratio': float(symmetry_ratio),
                    'dc_score': (float(dc_s) if dc_s is not None else None),
                    'p_div': (float(p_d) if p_d is not None else None),
                    'gt_div_edge': gt_div_edge,
                    'gt_source': g_s, 'gt_candidate': g_c,
                })
    return {'features': features, 'gt_div_edges': sorted({(s, t) for s, t in gt_edge_set
                                                          if gt_out_deg.get(s, 0) >= 2})}


# ---------------------------------------------------------------------------
# [wave1] REPLAY — tái hiện chính xác chuỗi gate + xếp hạng + ngân sách của
# add_safe_divisions_postlink từ đặc trưng đã thu. Trả về (added_edges, stats).
# ---------------------------------------------------------------------------
def wave1_replay_safe_div(feats: list, edges: list, gates: dict, rank_mode, nodes_by_id):
    """gates: dict các giá trị SAFE_DIV_*; rank_mode: None | (W, pdiv_floor | None)."""
    g_max = float(gates['SAFE_DIV_MAX_UM'])
    g_sister = float(gates['SAFE_DIV_SISTER_MAX_UM'])
    g_tau = float(gates['SAFE_DIV_SISTER_SYMMETRY_TAU'])
    g_diverge = float(gates['SAFE_DIV_DIVERGE_UM'])
    g_exist = float(gates['SAFE_DIV_EXISTING_CHILD_MAX_UM'])
    g_frame_frac = float(gates['SAFE_DIV_FRAME_FRAC_CAP'])
    g_global_frac = float(gates['SAFE_DIV_GLOBAL_FRAC_CAP'])
    g_dc_thresh = float(gates['DEEPCENTER_SAFE_DIV_THRESHOLD'])
    W = float(rank_mode[0]) if rank_mode else 0.0
    pdiv_floor = float(rank_mode[1]) if (rank_mode and len(rank_mode) > 1 and rank_mode[1] is not None) else None

    out_by_source = {}
    incoming = set()
    for edge in edges:
        out_by_source.setdefault(int(edge['source_id']), []).append(edge)
        incoming.add(int(edge['target_id']))
    ids_by_t = {}
    for node_id in nodes_by_id:
        ids_by_t.setdefault(int(nodes_by_id[node_id]['t']), []).append(node_id)
    stats = {'geometric_candidates': 0, 'mutual_nn_rejected': 0, 'divergence_rejected': 0,
             'symmetry_rejected': 0, 'dc_rejected': 0, 'pdiv_floor_rejected': 0,
             'proposals': 0, 'added': 0, 'cap_skipped': 0,
             'added_gt_edges': 0, 'rank_flips': 0}
    global_cap = max(1, int(round(max(1, len(edges)) * g_global_frac)))
    added = []
    used_targets = set()
    used_sources = set()
    by_frame = {}
    for f in feats:
        by_frame.setdefault(f['t'], []).append(f)
    for t in sorted(by_frame):
        frame_feats = by_frame[t]
        source_ids = [nid for nid in ids_by_t.get(t, []) if len(out_by_source.get(nid, [])) == 1]
        frame_cap = max(1, int(round(len(source_ids) * g_frame_frac)))
        proposals = []
        for f in frame_feats:
            if f['child_dist'] > g_exist or f['parent_dist'] > g_max or f['sister_dist'] > g_sister:
                continue
            if not f['mutual_nn']:
                stats['mutual_nn_rejected'] += 1
                continue
            if g_diverge > 0:
                if f['diverge_margin'] is None or f['diverge_margin'] < g_diverge:
                    stats['divergence_rejected'] += 1
                    continue
            stats['geometric_candidates'] += 1
            if f['dc_score'] is not None and f['dc_score'] < g_dc_thresh:
                stats['dc_rejected'] += 1
                continue
            if g_tau > 0.0 and f['symmetry_ratio'] > g_tau:
                stats['symmetry_rejected'] += 1
                continue
            score = f['parent_dist'] + 0.15 * f['sister_dist']
            if W > 0.0 and f['p_div'] is not None:
                score = score - W * float(f['p_div'])
            if pdiv_floor is not None and (f['p_div'] is None or float(f['p_div']) < pdiv_floor):
                stats['pdiv_floor_rejected'] += 1
                continue
            proposals.append((score, f))
        stats['proposals'] += len(proposals)
        proposals.sort(key=lambda item: item[0])
        added_this_frame = 0
        for _score, f in proposals:
            if len(added) >= global_cap:
                stats['cap_skipped'] += 1
                break
            if added_this_frame >= frame_cap:
                break
            if f['candidate_id'] in used_targets or f['candidate_id'] in incoming:
                continue
            if f['source_id'] in used_sources:
                continue
            added.append({'source_id': f['source_id'], 'target_id': f['candidate_id'],
                          'edge_prob': None, 'distance_um': f['parent_dist'], 'safe_division': 1})
            if f['gt_div_edge']:
                stats['added_gt_edges'] += 1
            used_targets.add(f['candidate_id'])
            used_sources.add(f['source_id'])
            added_this_frame += 1
    stats['added'] = len(added)
    return added, stats


# ---------------------------------------------------------------------------
# [wave1] các giai đoạn sau safe-div (prune → short-track → linefit) — gọi đúng
# trình tự filter_output_graph (monolith 3373-3386).
# ---------------------------------------------------------------------------
def wave1_post_safediv_stages(nodes_by_id, edges):
    stats = {'short_track_components_removed': 0}
    incident = {int(e['source_id']) for e in edges} | {int(e['target_id']) for e in edges}
    if incident:
        kept = {nid: n for nid, n in nodes_by_id.items() if nid in incident}
        stats['pruned_isolated_nodes'] = len(nodes_by_id) - len(kept)
        nodes_by_id = kept
        edges = [e for e in edges if int(e['source_id']) in nodes_by_id
                 and int(e['target_id']) in nodes_by_id]
    nodes_by_id, edges = filter_short_track_components(nodes_by_id, edges, stats)
    nodes_by_id = linefit_smooth_output_graph(nodes_by_id, edges, stats)
    return nodes_by_id, edges


# ===========================================================================
# CHẠY CHÍNH
# ===========================================================================
def wave1_main():
    from tracking_cellmot.metrics import evaluate, node_recall, per_sample_metrics
    from tracking_cellmot.division_metrics import score_divisions
    td_metrics = (evaluate, node_recall, per_sample_metrics)
    td_div = score_divisions
    wave1_log('official scorer import OK')

    deepcenter_bundle = load_deepcenter_veto_detector()
    if deepcenter_bundle is None:
        raise RuntimeError('DeepCenter không nạp được (REQUIRE=1).')
    global DIVNET_ENABLE  # [wave1] env để 0 để add_safe_divisions_postlink nguyên văn không
    DIVNET_ENABLE = 1     # dùng divnet; ở đây bật TỪ TẪM để nạp ranker cho audit/E0.
    divnet_bundle = load_divnet_ranker()
    wave1_log(f'divnet_bundle: {"OK" if divnet_bundle else "None (E0 sẽ không có p_div)"}')

    # ---- nạp GT + raw preds (một lần) --------------------------------------
    GT_PLAIN = {}
    GT_TTRUE = {}
    RAW = {}
    for stem in WAVE1_STEMS:
        gt_path = TRAIN_DIR / f'{stem}.geff'
        gt_graph = graph_from_geff(gt_path)
        gt_nodes_plain, gt_edges_plain = graph_to_plain(gt_graph)
        GT_PLAIN[stem] = (gt_nodes_plain, gt_edges_plain)
        GT_TTRUE[stem] = read_estimated_true_node_count(gt_path)
        pred_graph = graph_from_geff(WAVE1_PRED_DIR / f'{stem}.geff')
        raw_nodes_by_id = {}
        for row in pred_graph.node_attrs().iter_rows(named=True):
            node_id = int(row['node_id'])
            raw_nodes_by_id[node_id] = {'node_id': node_id, 't': int(row['t']),
                                        'z': float(row['z']), 'y': float(row['y']),
                                        'x': float(row['x'])}
        raw_edges = []
        for row in pred_graph.edge_attrs().iter_rows(named=True):
            edge_prob = row.get('edge_prob') if hasattr(row, 'get') else None
            raw_edges.append({'source_id': int(row['source_id']),
                              'target_id': int(row['target_id']),
                              'edge_prob': None if edge_prob is None else float(edge_prob)})
        RAW[stem] = (raw_nodes_by_id, raw_edges)
        wave1_log(f'nạp {stem}: {len(raw_nodes_by_id)} nodes / {len(raw_edges)} edges')

    # ---- cache dùng chung (frame zarr + deepcenter heatmap) ----------------
    WAVE1_FRAME_CACHE = {}
    WAVE1_DC_CACHE = {}

    # =====================================================================
    # E1 — SYSTEM VIEW OFFICIAL (config production + selected tight55/dcgap035)
    # =====================================================================
    e1_rows = []
    e1_stage_stats = {}
    e1_internal_rows = []
    saved = wave1_pp_apply(E1_SELECTED)
    try:
        for stem in WAVE1_STEMS:
            t0 = time.time()
            raw_nodes, raw_edges = RAW[stem]
            pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem, deepcenter_bundle, None)
            e1_stage_stats[stem] = st
            irow = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
            irow['stem'] = stem
            irow['safe_divisions_added'] = st.get('safe_divisions_added', 0)
            e1_internal_rows.append(irow)
            out_geff = WAVE1_OUT / f'e1_system_{stem}.geff'
            wave1_write_system_geff(pn, pe, out_geff)
            row = wave1_official_score_geff(out_geff, TRAIN_DIR / f'{stem}.geff', td_metrics, td_div)
            e1_rows.append(row)
            wave1_log(f"E1 {stem}: adjEJ={row['adjusted_edge_jaccard']:.4f} "
                      f"div={row['div_tp']}/{row['div_fp']}/{row['div_fn']} "
                      f"({time.time() - t0:.0f}s)")
    finally:
        wave1_pp_restore(saved)
    e1_micro = wave1_official_micro(e1_rows)
    wave1_dump_json('wave1_e1_system_eval.json', {
        'schema': 'wave1-e1/1', 'tag': WAVE1_TAG,
        'config': 'ver-7 production + selected(tight55+dcgap035)',
        'samples': e1_rows, 'micro': e1_micro})
    wave1_log(f"E1 SYSTEM VIEW official: adjEJ={e1_micro['adjusted_edge_jaccard']:.4f} "
              f"div={e1_micro['div_tp']}/{e1_micro['div_fp']}/{e1_micro['div_fn']} "
              f"divJ={e1_micro['division_jaccard']} proxy={e1_micro['proxy_score']:.4f}")

    # =====================================================================
    # E0 — GATE AUDIT + GRID (pre-safe-div cache 1 lần, replay từng combo)
    # =====================================================================
    # pre-safe-div: chạy giai đoạn 1-6 của filter_output_graph với config
    # production + selected (đúng thứ tự monolith 3260-3335), rồi dừng trước
    # safe-div; cache kết quả cho mọi combo.
    saved = wave1_pp_apply(E1_SELECTED)
    PRE_STATE = {}
    PRE_STATS = {}

    def _full_stats() -> dict:
        # [wave1] copy nguyên văn dict khởi tạo stats của filter_output_graph
        # (monolith 3259) — motion_relink/gap dùng `+=` trên mọi key.
        return {'raw_edges': 0, 'dropped_nonconsecutive_edges': 0, 'dropped_long_edges': 0, 'dropped_multi_parent_edges': 0, 'dropped_multi_child_edges': 0, 'dropped_division_edges': 0, 'gap_candidates': 0, 'gap_pairs_selected': 0, 'gap_reused_existing': 0, 'gap_inserted_synthetic': 0, 'gap_added_nodes': 0, 'gap_added_edges': 0, 'gap_skipped_node_cap': 0, 'gap_density_nodes_scored': 0, 'gap_density_candidates_expanded': 0, 'gap_density_candidates_restricted': 0, 'gap_density_selected_outside_base': 0, 'gap_density_step_delta_milli_sum': 0, 'gap_refined_synthetic': 0, 'gap_refine_failed': 0, 'gap_refine_rejected_shift': 0, 'pruned_isolated_nodes': 0, 'motion_relink_edges': 0, 'motion_relink_tight_edges': 0, 'motion_relink_relaxed_edges': 0, 'motion_relink_frames': 0, 'motion_relink_replaced_raw_edges': 0, 'motion_relink_fallback_raw': 0, 'motion_relink_skipped_large_frame': 0, 'gap2_candidates': 0, 'gap2_pairs_selected': 0, 'gap2_added_nodes': 0, 'gap2_added_edges': 0, 'gap2_skipped_cap': 0, 'safe_division_candidates': 0, 'safe_division_geometric_candidates': 0, 'safe_divisions_added': 0, 'safe_division_skipped_cap': 0, 'safe_division_mutual_nn_rejected': 0, 'safe_division_divergence_rejected': 0, 'safe_division_symmetry_rejected': 0, 'divnet_proposals_scored': 0, 'divnet_rank_flips': 0, 'divnet_p_added_sum': 0.0, 'divnet_p_added_n': 0, 'deepcenter_gap_checked': 0, 'deepcenter_gap_bypassed_strong_motion': 0, 'deepcenter_gap_bypassed_observed_node': 0, 'deepcenter_gap_accepted': 0, 'deepcenter_gap_rejected': 0, 'deepcenter_gap_missing': 0, 'deepcenter_safe_div_checked': 0, 'deepcenter_safe_div_accepted': 0, 'deepcenter_safe_div_rejected': 0, 'deepcenter_safe_div_missing': 0, 'short_track_components_removed': 0, 'short_track_nodes_removed': 0, 'short_track_edges_removed': 0, 'short_track_filter_skipped_all': 0, 'short_track_rescue_triggered': 0, 'short_track_rescue_components': 0, 'short_track_rescue_nodes': 0, 'short_track_rescue_budget': 0, 'linefit_smoothed_nodes': 0, 'linefit_skipped_nodes': 0}

    try:
        for stem in WAVE1_STEMS:
            raw_nodes, raw_edges = RAW[stem]
            nodes_copy = {nid: dict(n) for nid, n in raw_nodes.items()}
            edges_copy = [dict(e) for e in raw_edges]
            nodes_by_id, edges = nodes_copy, edges_copy
            st = _full_stats()
            # (đối chiếu filter_output_graph 3260-3334 — giữ NGUYÊN VĂN logic)
            filtered_edges = []
            for edge in edges:
                source = nodes_by_id.get(int(edge['source_id']))
                target = nodes_by_id.get(int(edge['target_id']))
                if source is None or target is None:
                    continue
                if OUTPUT_ENFORCE_NEXT_FRAME and int(target['t']) != int(source['t']) + 1:
                    continue
                distance_um = edge_distance_um(source, target)
                edge['distance_um'] = distance_um
                if OUTPUT_EDGE_MAX_UM > 0 and distance_um > OUTPUT_EDGE_MAX_UM:
                    continue
                filtered_edges.append(edge)
            edges = filtered_edges
            if OUTPUT_MOTION_RELINK:
                learned_edge_probs = {}
                for edge in edges:
                    prob = edge.get('edge_prob')
                    if prob is None:
                        continue
                    try:
                        prob = float(prob)
                    except (TypeError, ValueError):
                        continue
                    if np.isfinite(prob):
                        learned_edge_probs[(int(edge['source_id']), int(edge['target_id']))] = \
                            max(learned_edge_probs.get((int(edge['source_id']), int(edge['target_id'])),
                                float('-inf')), prob)
                motion_edges = motion_relink_edges(nodes_by_id, st, learned_edge_probs)
                if motion_edges:
                    edges = motion_edges
            if OUTPUT_SINGLE_PARENT_REPAIR and edges:
                best_by_target = {}
                for edge in edges:
                    tid = int(edge['target_id'])
                    prev = best_by_target.get(tid)
                    if prev is None or edge_sort_key(edge) > edge_sort_key(prev):
                        best_by_target[tid] = edge
                kept = {id(e) for e in best_by_target.values()}
                edges = [e for e in edges if id(e) in kept]
            # (OUTPUT_SINGLE_CHILD_REPAIR = 0 trong production — bỏ qua như gốc)
            nodes_by_id, edges = close_single_frame_gaps(
                nodes_by_id, edges, st, dataset=stem,
                deepcenter_bundle=deepcenter_bundle,
                frame_cache=WAVE1_FRAME_CACHE, deepcenter_cache=WAVE1_DC_CACHE)
            nodes_by_id, edges = recover_strict_gap2(nodes_by_id, edges, st, dataset=stem)
            PRE_STATE[stem] = (nodes_by_id, edges)
            PRE_STATS[stem] = st
            wave1_log(f'pre-safe-div {stem}: {len(nodes_by_id)} nodes / {len(edges)} edges '
                      f"(gap_added={st['gap_added_nodes']}, motion_edges={st['motion_relink_edges']})")
    finally:
        wave1_pp_restore(saved)

    # thu đặc trưng (gate rộng nhất) — 1 lần/stem, chia sẻ cache
    FEATURES = {}
    for stem in WAVE1_STEMS:
        t0 = time.time()
        nodes_by_id, edges = PRE_STATE[stem]
        FEATURES[stem] = wave1_collect_safe_div_features(
            stem, nodes_by_id, edges, deepcenter_bundle, divnet_bundle,
            WAVE1_FRAME_CACHE, WAVE1_DC_CACHE, GT_PLAIN[stem])
        n_feats = len(FEATURES[stem]['features'])
        n_gt_div = len(FEATURES[stem]['gt_div_edges'])
        n_gt_hit = sum(1 for f in FEATURES[stem]['features'] if f['gt_div_edge'])
        wave1_log(f'audit {stem}: {n_feats} cặp / {n_gt_div} GT-div, trong tầm: {n_gt_hit} '
                  f'({time.time() - t0:.0f}s)')

    # ---- E0 SELF-CHECK: replay(production, không divnet) == E1 verbatim ------
    selfcheck = {'ok': True, 'diffs': [], 'row_diffs': []}
    prod_gates = {k: WAVE1_BASE_CONFIG[k] for k in
                  ['SAFE_DIV_MAX_UM', 'SAFE_DIV_SISTER_MAX_UM', 'SAFE_DIV_DIVERGE_UM',
                   'SAFE_DIV_SISTER_SYMMETRY_TAU', 'SAFE_DIV_EXISTING_CHILD_MAX_UM',
                   'SAFE_DIV_FRAME_FRAC_CAP', 'SAFE_DIV_GLOBAL_FRAC_CAP',
                   'DEEPCENTER_SAFE_DIV_THRESHOLD']}
    for stem in WAVE1_STEMS:
        nodes_by_id, edges = PRE_STATE[stem]
        replay_added, _rs = wave1_replay_safe_div(
            FEATURES[stem]['features'], edges, prod_gates, None, nodes_by_id)
        # đối chiếu gián tiếp qua số safe_divisions_added đã ghi trong stats E1
        verbatim_n = e1_stage_stats[stem].get('safe_divisions_added', 0)
        if verbatim_n != len(replay_added):
            selfcheck['ok'] = False
            selfcheck['diffs'].append({'stem': stem, 'verbatim_added': verbatim_n,
                                       'replay_added': len(replay_added)})
    wave1_log(f"SELF-CHECK replay vs verbatim: {'ĐẠT' if selfcheck['ok'] else 'LỆCH'} "
              f"{selfcheck['diffs'][:4]}")

    # ---- chẩn đoán 12 GT division: vì sao trượt (E3-div) --------------------
    div_diag = []
    for stem in WAVE1_STEMS:
        gt_nodes, gt_edges = GT_PLAIN[stem]
        feats = FEATURES[stem]['features']
        p2g, g2p = match_nodes_bipartite(
            {nid: (int(n['t']), float(n['z']), float(n['y']), float(n['x']))
             for nid, n in PRE_STATE[stem][0].items()}, gt_nodes, max_dist=7.0)
        gt_out = {}
        for s, t in gt_edges:
            gt_out.setdefault(s, set()).add(t)
        for g_src, children in gt_out.items():
            if len(children) < 2:
                continue
            ev = {'stem': stem, 'gt_div_node': int(g_src), 'children': sorted(children),
                  'parent_matched': bool(g_src in g2p)}
            c_match = [bool(c in g2p) for c in sorted(children)[:2]]
            ev['children_matched'] = c_match
            serving = [f for f in feats
                       if f['gt_source'] == g_src and f['gt_div_edge']]
            ev['n_serving_pairs'] = len(serving)
            if serving:
                best = min(serving, key=lambda f: f['parent_dist'])
                ev['best_pair'] = {k: best[k] for k in
                                   ('t', 'parent_dist', 'sister_dist', 'mutual_nn',
                                    'diverge_margin', 'symmetry_ratio', 'dc_score', 'p_div')}
                ev['reject_reason'] = []
                if not best['mutual_nn']:
                    ev['reject_reason'].append('mutual_nn')
                if best['diverge_margin'] is None:
                    ev['reject_reason'].append('divergence_no_grandchildren')
                elif best['diverge_margin'] < prod_gates['SAFE_DIV_DIVERGE_UM']:
                    ev['reject_reason'].append('divergence')
                if best['dc_score'] is not None and best['dc_score'] < prod_gates['DEEPCENTER_SAFE_DIV_THRESHOLD']:
                    ev['reject_reason'].append('deepcenter')
                if best['symmetry_ratio'] > prod_gates['SAFE_DIV_SISTER_SYMMETRY_TAU']:
                    ev['reject_reason'].append('symmetry')
                if best['parent_dist'] > prod_gates['SAFE_DIV_MAX_UM']:
                    ev['reject_reason'].append('parent_dist')
                if best['sister_dist'] > prod_gates['SAFE_DIV_SISTER_MAX_UM']:
                    ev['reject_reason'].append('sister_dist')
            else:
                ev['reject_reason'] = ['no_pair_in_range']
            div_diag.append(ev)
    wave1_dump_json('wave1_e0_div_diagnostics.json', {'schema': 'wave1-e0-diag/1',
                                                     'events': div_diag})
    n_no_pair = sum(1 for e in div_diag if 'no_pair_in_range' in e['reject_reason'])
    wave1_log(f'DIV DIAG: {len(div_diag)} sự kiện GT — {n_no_pair} không có cặp nào trong tầm')

    # ---- E0 GRID ------------------------------------------------------------
    E0_GRID = [
        ('base-v7', {}, None),
        ('dn-w15', {}, ('divnet', 15.0, None)),
        ('tau08-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8}, ('divnet', 15.0, None)),
        ('tau10-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0}, ('divnet', 15.0, None)),
        ('div15-dn15', {'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, None)),
        ('div10-dn15', {'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 15.0, None)),
        ('tau08-div15-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, None)),
        ('tau10-div10-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 15.0, None)),
        ('tau08-div15-dn25', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 25.0, None)),
        ('tau10-div10-dn25', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, None)),
        ('max12-tau08-div15-dn15', {'SAFE_DIV_MAX_UM': 12.0, 'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, None)),
        ('max12-tau10-div10-dn25', {'SAFE_DIV_MAX_UM': 12.0, 'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, None)),
        ('tau08-div15-dn15-pf50', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, 0.5)),
        ('tau10-div10-dn25-pf50', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, 0.5)),
        ('tau10-div10-dn25-pf30', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, 0.3)),
    ]
    e0_rows = []
    for label, overrides, rank_mode in E0_GRID:
        if wave1_time_left() < 1800:
            wave1_log(f'E0 {label}: BỎ QUA (hết thời gian)')
            continue
        gates = dict(prod_gates)
        gates.update(overrides)
        t0 = time.time()
        agg_rows = []
        tot_stats = Counter()
        for stem in WAVE1_STEMS:
            nodes_by_id, edges = PRE_STATE[stem]
            import copy as _copy
            nodes_c = _copy.deepcopy(nodes_by_id)
            added, rstats = wave1_replay_safe_div(
                FEATURES[stem]['features'], edges, gates, rank_mode, nodes_c)
            tot_stats.update(rstats)
            new_edges = [dict(e) for e in edges] + added
            pn, pe = wave1_post_safediv_stages(nodes_c, new_edges)
            row = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
            row['stem'] = stem
            row['safe_divisions_added'] = rstats['added']
            row['added_gt_edges'] = rstats['added_gt_edges']
            agg_rows.append(row)
        summary = aggregate_official(agg_rows)
        e0_rows.append({'config': label, 'overrides': overrides, 'rank_mode': list(rank_mode) if rank_mode else None,
                        'summary': summary, 'replay_stats': dict(tot_stats),
                        'seconds': time.time() - t0, 'rows': agg_rows})
        if label == 'base-v7' and e1_internal_rows:
            for e0r, e1r in zip(agg_rows, e1_internal_rows):
                keys = ['edge_tp', 'edge_fp', 'edge_fn', 'edge_jaccard',
                        'adjusted_edge_jaccard', 'div_tp', 'div_fp', 'div_fn', 't_pred']
                bad = [k for k in keys
                       if abs(float(e0r[k] or 0) - float(e1r[k] or 0)) > 1e-9]
                if bad:
                    selfcheck['ok'] = False
                    selfcheck['row_diffs'].append({'stem': e0r['stem'], 'keys': bad,
                                                   'e0': {k: e0r[k] for k in bad},
                                                   'e1': {k: e1r[k] for k in bad}})
            wave1_log(f"SELF-CHECK end-to-end base-v7 vs E1: "
                      f"{'ĐẠT' if not selfcheck['row_diffs'] else 'LỆCH'} {selfcheck['row_diffs'][:2]}")
        wave1_log(f"E0 {label}: adjEJ={summary['adjusted_edge_jaccard']:.4f} "
                  f"div={summary['div_tp']}/{summary['div_fp']}/{summary['div_fn']} "
                  f"added={tot_stats['added']} added_gt={tot_stats['added_gt_edges']} "
                  f"({time.time() - t0:.0f}s)")
    # dump dạng CSV + JSON
    with (WAVE1_OUT / 'wave1_e0_grid.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['config', 'adjusted_edge_jaccard', 'division_jaccard', 'proxy_score',
                    'div_tp', 'div_fp', 'div_fn', 'added', 'added_gt_edges', 'seconds'])
        for r in e0_rows:
            s = r['summary']
            w.writerow([r['config'], s['adjusted_edge_jaccard'], s['division_jaccard'],
                        s['proxy_score'], s['div_tp'], s['div_fp'], s['div_fn'],
                        r['replay_stats'].get('added', 0),
                        r['replay_stats'].get('added_gt_edges', 0), round(r['seconds'], 1)])
    wave1_dump_json('wave1_e0_grid.json', {'schema': 'wave1-e0/1', 'selfcheck': selfcheck,
                                           'grid': [{k: v for k, v in r.items() if k != 'rows'}
                                                    for r in e0_rows]})

    # ---- E0: official cho top-5 theo (div_tp, -div_fp, proxy) ---------------
    ranked_e0 = sorted(e0_rows, key=lambda r: (r['summary']['div_tp'],
                                               -r['summary']['div_fp'],
                                               r['summary']['proxy_score']), reverse=True)
    e0_official_budget = 5
    for r in ranked_e0[:e0_official_budget]:
        if wave1_time_left() < 2400:
            wave1_log(f"E0-official {r['config']}: BỎ QUA (hết thời gian)")
            break
        t0 = time.time()
        rows_off = []
        for stem in WAVE1_STEMS:
            nodes_by_id, edges = PRE_STATE[stem]
            import copy as _copy
            nodes_c = _copy.deepcopy(nodes_by_id)
            gates = dict(prod_gates)
            gates.update(r['overrides'])
            added, _rs = wave1_replay_safe_div(
                FEATURES[stem]['features'], edges, gates,
                tuple(r['rank_mode']) if r['rank_mode'] else None, nodes_c)
            new_edges = [dict(e) for e in edges] + added
            pn, pe = wave1_post_safediv_stages(nodes_c, new_edges)
            out_geff = WAVE1_OUT / f"e0_{r['config']}_{stem}.geff"
            wave1_write_system_geff(pn, pe, out_geff)
            row = wave1_official_score_geff(out_geff, TRAIN_DIR / f'{stem}.geff',
                                            td_metrics, td_div)
            rows_off.append(row)
            out_geff.unlink()  # đỡ nặng output
        micro = wave1_official_micro(rows_off)
        r['official_micro'] = micro
        wave1_log(f"E0-OFFICIAL {r['config']}: adjEJ={micro['adjusted_edge_jaccard']:.4f} "
                  f"div={micro['div_tp']}/{micro['div_fp']}/{micro['div_fn']} "
                  f"divJ={micro['division_jaccard']} ({time.time() - t0:.0f}s)")
    wave1_dump_json('wave1_e0_grid_official.json',
                    {'schema': 'wave1-e0-official/1',
                     'official': [{'config': r['config'], 'official_micro': r.get('official_micro')}
                                  for r in e0_rows if r.get('official_micro')]})

    # =====================================================================
    # E2 — PPSWEEP-2 (config ngoài safe-div; chạy pipeline đầy đủ từng config)
    # =====================================================================
    PP2_GRID = [
        ('tight50', {'MOTION_RELINK_TIGHT_UM': 5.0}),
        ('tight55', {'MOTION_RELINK_TIGHT_UM': 5.5}),
        ('tight65', {'MOTION_RELINK_TIGHT_UM': 6.5}),
        ('relaxed8', {'MOTION_RELINK_RELAXED_UM': 8.0}),
        ('relaxed11', {'MOTION_RELINK_RELAXED_UM': 11.0}),
        ('bonus110', {'MOTION_RELINK_LEARNED_BONUS': 1.10}),
        ('bonus135', {'MOTION_RELINK_LEARNED_BONUS': 1.35}),
        ('vw040', {'MOTION_RELINK_VELOCITY_WEIGHT': 0.40}),
        ('vw060', {'MOTION_RELINK_VELOCITY_WEIGHT': 0.60}),
        ('gap55', {'GAP_CLOSE_UM': 5.5}),
        ('reuse36', {'GAP_CLOSE_REUSE_UM': 3.6}),
        ('gap2step48', {'GAP2_MAX_STEP_UM': 4.8}),
        ('minlen5', {'OUTPUT_MIN_TRACK_LEN': 5}),
        ('minlen7', {'OUTPUT_MIN_TRACK_LEN': 7}),
        ('rescue085', {'SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB': 0.85}),
        ('edgemax13', {'OUTPUT_EDGE_MAX_UM': 13.0}),
        ('dcgap030', {'DEEPCENTER_GAP_THRESHOLD': 0.30}),
        ('dcgap040', {'DEEPCENTER_GAP_THRESHOLD': 0.40}),
    ]
    # per-prefix (H4): 6bba disp_p99 7.9µm vs 44b6 4.9µm → tight khác nhau theo prefix
    PP2_PERPREFIX = [
        ('pp-tight-55-65', {'44b6': {'MOTION_RELINK_TIGHT_UM': 5.5},
                            '6bba': {'MOTION_RELINK_TIGHT_UM': 6.5}}),
        ('pp-tight-50-60', {'44b6': {'MOTION_RELINK_TIGHT_UM': 5.0},
                            '6bba': {'MOTION_RELINK_TIGHT_UM': 6.0}}),
    ]
    e2_rows = []
    base_summary = None
    for label, config in [('base', {})] + PP2_GRID:
        if wave1_time_left() < 1500:
            wave1_log(f'E2 {label}: BỎ QUA (hết thời gian)')
            continue
        t0 = time.time()
        saved = wave1_pp_apply(config)
        try:
            agg_rows = []
            for stem in WAVE1_STEMS:
                raw_nodes, raw_edges = RAW[stem]
                pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem,
                                               deepcenter_bundle, None)
                row = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
                row['stem'] = stem
                agg_rows.append(row)
        finally:
            wave1_pp_restore(saved)
        summary = aggregate_official(agg_rows)
        if label == 'base':
            base_summary = summary
        e2_rows.append({'config': label, 'overrides': config, 'summary': summary,
                        'seconds': time.time() - t0})
        wave1_log(f"E2 {label}: adjEJ={summary['adjusted_edge_jaccard']:.4f} "
                  f"div={summary['div_tp']}/{summary['div_fp']}/{summary['div_fn']} "
                  f"proxy={summary['proxy_score']:.4f} ({time.time() - t0:.0f}s)")
    for label, pp_config in PP2_PERPREFIX:
        if wave1_time_left() < 1500:
            wave1_log(f'E2 {label}: BỎ QUA (hết thời gian)')
            continue
        t0 = time.time()
        agg_rows = []
        try:
            for stem in WAVE1_STEMS:
                prefix = stem.split('_')[0]
                saved = wave1_pp_apply(pp_config.get(prefix, {}))
                try:
                    raw_nodes, raw_edges = RAW[stem]
                    pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem,
                                                   deepcenter_bundle, None)
                finally:
                    wave1_pp_restore(saved)
                row = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
                row['stem'] = stem
                agg_rows.append(row)
        except Exception as exc:
            wave1_log(f'E2 {label}: LỖI {exc}')
            continue
        summary = aggregate_official(agg_rows)
        e2_rows.append({'config': label, 'overrides': pp_config, 'per_prefix': True,
                        'summary': summary, 'seconds': time.time() - t0})
        wave1_log(f"E2 {label}: adjEJ={summary['adjusted_edge_jaccard']:.4f} "
                  f"div={summary['div_tp']}/{summary['div_fp']}/{summary['div_fn']} "
                  f"proxy={summary['proxy_score']:.4f} ({time.time() - t0:.0f}s)")
    with (WAVE1_OUT / 'wave1_e2_ppsweep2.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['config', 'adjusted_edge_jaccard', 'division_jaccard', 'proxy_score',
                    'div_tp', 'div_fp', 'div_fn', 'seconds'])
        for r in e2_rows:
            s = r['summary']
            w.writerow([r['config'], s['adjusted_edge_jaccard'], s['division_jaccard'],
                        s['proxy_score'], s['div_tp'], s['div_fp'], s['div_fn'],
                        round(r['seconds'], 1)])
    wave1_dump_json('wave1_e2_ppsweep2.json', {'schema': 'wave1-e2/1', 'rows': e2_rows})

    # ---- E2: official cho top-3 (khác base) + base -------------------------
    if base_summary is not None:
        cand = [r for r in e2_rows
                if r['config'] != 'base'
                and r['summary']['proxy_score'] >= base_summary['proxy_score'] + 0.0005
                and r['summary']['adjusted_edge_jaccard']
                >= base_summary['adjusted_edge_jaccard'] - 0.0005]
        cand.sort(key=lambda r: r['summary']['proxy_score'], reverse=True)
        for r in cand[:3]:
            if wave1_time_left() < 2400:
                wave1_log(f"E2-official {r['config']}: BỎ QUA (hết thời gian)")
                break
            t0 = time.time()
            rows_off = []
            for stem in WAVE1_STEMS:
                raw_nodes, raw_edges = RAW[stem]
                if r.get('per_prefix'):
                    prefix = stem.split('_')[0]
                    saved = wave1_pp_apply(r['overrides'].get(prefix, {}))
                else:
                    saved = wave1_pp_apply(r['overrides'])
                try:
                    pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem,
                                                   deepcenter_bundle, None)
                finally:
                    wave1_pp_restore(saved)
                out_geff = WAVE1_OUT / f"e2_{r['config']}_{stem}.geff"
                wave1_write_system_geff(pn, pe, out_geff)
                row = wave1_official_score_geff(out_geff, TRAIN_DIR / f'{stem}.geff',
                                                td_metrics, td_div)
                rows_off.append(row)
                out_geff.unlink()
            micro = wave1_official_micro(rows_off)
            r['official_micro'] = micro
            wave1_log(f"E2-OFFICIAL {r['config']}: adjEJ={micro['adjusted_edge_jaccard']:.4f} "
                      f"div={micro['div_tp']}/{micro['div_fp']}/{micro['div_fn']} "
                      f"({time.time() - t0:.0f}s)")
        wave1_dump_json('wave1_e2_ppsweep2_official.json',
                        {'schema': 'wave1-e2-official/1',
                         'official': [{'config': r['config'], 'official_micro': r.get('official_micro')}
                                      for r in e2_rows if r.get('official_micro')]})

    # =====================================================================
    # E3 — chẩn đoán 2 video xấu nhất (6bba_07e24132 / 44b6_267148e4)
    # =====================================================================
    e3 = {}
    for stem in ('6bba_07e24132', '44b6_267148e4'):
        if stem not in WAVE1_STEMS:
            continue
        row = next((r for r in e1_rows if r['stem'] == stem), None)
        gt_nodes, gt_edges = GT_PLAIN[stem]
        raw_nodes, raw_edges = RAW[stem]
        # chạy lại production để có đồ thị hệ (đã có trong E1 nhưng không giữ)
        saved = wave1_pp_apply(E1_SELECTED)
        try:
            pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem, deepcenter_bundle, None)
        finally:
            wave1_pp_restore(saved)
        pred_plain = nodes_by_id_to_plain(pn)
        pred_edges_plain = [(int(e['source_id']), int(e['target_id'])) for e in pe]
        p2g, g2p = match_nodes_bipartite(pred_plain, gt_nodes, max_dist=7.0)
        fn_by_t = Counter()
        fp_by_t = Counter()
        gt_out = {}
        for s, t in gt_edges:
            gt_out.setdefault(s, set()).add(t)
        gt_edge_set = set(gt_edges)
        matched_gt = set()
        for s, t in pred_edges_plain:
            ms, mt = p2g.get(s), p2g.get(t)
            if ms is not None and mt is not None and mt in gt_out.get(ms, ()):
                matched_gt.add((ms, mt))
            else:
                fp_by_t[int(pred_plain[s][0])] += 1
        for gs, gt_ in gt_edge_set:
            if (gs, gt_) not in matched_gt:
                fn_by_t[int(gt_nodes[gs][0])] += 1
        t_true = GT_TTRUE[stem]
        nodes_by_t = Counter(int(n[0]) for n in pred_plain.values())
        e3[stem] = {
            'official_row': row,
            'fn_edges_by_frame': dict(sorted(fn_by_t.items())),
            'fp_edges_by_frame': dict(sorted(fp_by_t.items())),
            'pred_nodes_by_frame': dict(sorted(nodes_by_t.items())),
            't_true_estimated': t_true,
            'overprediction_ratio': row.get('total_node_ratio') if row else None,
            'node_recall': row.get('node_recall') if row else None,
        }
        wave1_log(f'E3 {stem}: fn_edges={dict(list(sorted(fn_by_t.items()))[:8])}...')
    wave1_dump_json('wave1_e3_badvideos.json', {'schema': 'wave1-e3/1', 'videos': e3})

    # =====================================================================
    # TỔNG KẾT
    # =====================================================================
    best_e0 = max((r for r in e0_rows), key=lambda r: (r['summary']['div_tp'],
                                                       -r['summary']['div_fp'],
                                                       r['summary']['proxy_score']),
                  default=None)
    summary = {
        'schema': 'wave1-summary/1', 'tag': WAVE1_TAG,
        'e1_system_micro': e1_micro,
        'selfcheck_replay_vs_verbatim': selfcheck,
        'div_diagnostics': {'n_events': len(div_diag),
                            'no_pair_in_range': n_no_pair,
                            'reject_reasons': dict(Counter(
                                reason for e in div_diag for reason in e['reject_reason']))},
        'e0_best': ({'config': best_e0['config'], 'summary': best_e0['summary'],
                     'replay_stats': best_e0['replay_stats'],
                     'official_micro': best_e0.get('official_micro')}
                    if best_e0 else None),
        'e0_all': [{'config': r['config'], 'div': f"{r['summary']['div_tp']}/{r['summary']['div_fp']}/{r['summary']['div_fn']}",
                    'proxy': round(r['summary']['proxy_score'], 6),
                    'adjEJ': round(r['summary']['adjusted_edge_jaccard'], 6),
                    'official': (round(r['official_micro']['proxy_score'], 6)
                                 if r.get('official_micro') else None)}
                   for r in e0_rows],
        'e2_all': [{'config': r['config'], 'div': f"{r['summary']['div_tp']}/{r['summary']['div_fp']}/{r['summary']['div_fn']}",
                    'proxy': round(r['summary']['proxy_score'], 6),
                    'adjEJ': round(r['summary']['adjusted_edge_jaccard'], 6),
                    'official': (round(r['official_micro']['proxy_score'], 6)
                                 if r.get('official_micro') else None)}
                   for r in e2_rows],
        'runtime_seconds': time.time() - WAVE1_T0,
    }
    wave1_dump_json('wave1_summary.json', summary)
    wave1_log('WAVE-1 HOÀN TẤT')


try:
    wave1_main()
except Exception:
    print('[wave1] LỖI CHÍNH — traceback:')
    _tb.print_exc()
    raise
