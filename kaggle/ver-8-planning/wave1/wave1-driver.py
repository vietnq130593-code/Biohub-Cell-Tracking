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
# [v3] E1 đã chốt từ run v2 (adjEJ 0.9280, div 2/1/10, selfcheck ĐẠT) — skip để nhanh
_env['BIOHUB_WAVE1_SKIP_E1'] = '1'
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

# @@SLICES@@
