#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test-ver5-cell5.py — bộ kiểm chứng ver 5.1 (cell 5 nâng cấp) so với nền nguyên văn.

Chạy:  python3 test-ver5-cell5.py   (từ kaggle/ver-5)

Không cần GPU/torch thật — tiêm module torch giả + subprocess giả vào namespace.

T1  : cú pháp mọi file (py_compile: cell5code.py, cell5-foundation-verbatim.py,
      make-ver5-upgrade.py, mock)
T2  : ĐẲNG THỨC PAYLOAD — vá mock bằng bản NỀN và bằng bản NÂNG CẤP (hai thư mục
      riêng) → file kết quả giống nhau TỪNG BYTE → chứng minh bản nâng cấp không
      đổi hành vi vá của pipeline 0.945
T3  : mock sau vá compile được + đủ 6 marker của 6 patch
T4  : re-run an toàn — chạy khối vá lần 2 thì "Patch phase skipped", file không đổi
T5  : anchor drift — mock bị hỏng 1 anchor → bản nâng cấp DỪNG TRƯỚC KHI GHI (file
      trên đĩa nguyên vẹn); đối chứng bản nền: patch 1 in warning rồi patch 2-4 VẪN
      GHI ĐĨA → hỏng ở patch 5, để lại FILE VÁ DỞ (đúng điểm yếu đã chẩn đoán)
T6  : luồng đầy đủ 1 GPU (subprocess.run giả) — .geff đủ 5 video, splits JSON đúng,
      nhánh "no logs" của tổng hợp retention
T7  : luồng đầy đủ 2 GPU (Popen giả) — env shard đúng (CUDA_VISIBLE_DEVICES,
      BIOHUB_GPU_SHARD, PYTHONPATH), merge đúng 5 .geff, dọn thư mục shard,
      tổng hợp retention guard đúng số (1/4 guarded, worst 0.830)
T8  : tôn trọng env của S1 — đã đặt thì KHÔNG ghi đè; chưa đặt thì dùng đúng mặc
      định 0.945 (0.90 / 1 / 1 / 0.75); đối chứng: bản nền GHI ĐÈ cứng (bẫy tune)
T9  : không có GPU → RuntimeError
T10 : thiếu scripts/predict_unet_transformer.py → FileNotFoundError (dẫn về section 4)
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPGRADED = HERE / "cell5code.py"
FOUNDATION = HERE / "cell5-foundation-verbatim.py"
MAKER = HERE / "make-ver5-upgrade.py"

STEMS = ["video_a", "video_b", "video_c", "video_d", "video_e"]

# Env mà S1/S4 của notebook gốc đã đặt trước khi cell 5 chạy (bản 0.945).
S1_S4_ENV = {
    "BIOHUB_DET_THRESHOLD": "0.965",
    "BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT": "0.15",
    "BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION": "0.90",
    "BIOHUB_SECONDARY_WEIGHTS": "/tmp/fake_secondary/edge_predictor_best.pth",
    "BIOHUB_SECONDARY_EDGE_WEIGHT": "0.20",
    "BIOHUB_SECONDARY_DETECTION_WEIGHT": "0.80",
    "BIOHUB_SECONDARY_LINK_MODE": "low_margin_consensus",
    "BIOHUB_SECONDARY_LOW_MARGIN_MAX": "0.35",
    "BIOHUB_SECONDARY_MIX_TEMPERATURE": "1",
}
RETENTION_RECORDS = [
    {"dataset": "video_a", "frame": 3, "primary_candidates": 10, "blended_candidates": 10,
     "retention": 1.0, "minimum_retention": 0.9, "use_primary": False},
    {"dataset": "video_a", "frame": 12, "primary_candidates": 12, "blended_candidates": 10,
     "retention": 0.83, "minimum_retention": 0.9, "use_primary": True},
    {"dataset": "video_c", "frame": 7, "primary_candidates": 8, "blended_candidates": 8,
     "retention": 1.0, "minimum_retention": 0.9, "use_primary": False},
    {"dataset": "video_d", "frame": 1, "primary_candidates": 9, "blended_candidates": 9,
     "retention": 1.0, "minimum_retention": 0.9, "use_primary": False},
]


# ----------------------------------------------------------------------------
# Fake torch
# ----------------------------------------------------------------------------
def make_fake_torch(cuda_available=True, device_count=2):
    torch = types.ModuleType("torch")
    cuda = types.ModuleType("torch.cuda")

    def _is_available():
        return cuda_available

    def _get_device_name(index=0):
        return "Fake-T4"

    def _device_count():
        return device_count

    cuda.is_available = staticmethod(_is_available)
    cuda.get_device_name = staticmethod(_get_device_name)
    cuda.device_count = staticmethod(_device_count)
    torch.cuda = cuda
    return torch


# ----------------------------------------------------------------------------
# Fake subprocess — mô phỏng worker thật: sinh .geff theo --method/--slice
# ----------------------------------------------------------------------------
class FakePopen:
    def __init__(self):
        self.returncode = 0

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = -15

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class FakeSubprocess:
    CalledProcessError = subprocess.CalledProcessError
    TimeoutExpired = subprocess.TimeoutExpired

    def __init__(self, repo: Path, working: Path, stems, retention_records=None):
        self._repo = repo
        self._working = working
        self._stems = list(stems)
        self._retention = list(retention_records or [])
        self.runs = []
        self.popens = []

    def _emit(self, method: str, stems, env: dict):
        outdir = self._repo / "predictions" / "mockuser" / method / "split_0"
        outdir.mkdir(parents=True, exist_ok=True)
        for stem in stems:
            (outdir / f"{stem}.geff").write_text("{}")
        if self._retention:
            # mỗi shard chỉ ghi record của dataset nó phụ trách (như worker thật)
            records = [r for r in self._retention if r.get("dataset") in set(stems)]
            shard = env.get("BIOHUB_GPU_SHARD", "single").replace("/", "_")
            log = self._working / f"retention_guard_{shard}.jsonl"
            with log.open("a") as handle:
                for record in records:
                    handle.write(json.dumps(record, sort_keys=True) + "\n")

    def run(self, cmd, cwd=None, env=None, check=False):
        env = dict(env or {})
        self.runs.append((list(cmd), env))
        self._emit("unet_transformer", self._stems, env)
        return types.SimpleNamespace(returncode=0)

    def Popen(self, cmd, cwd=None, env=None, **kwargs):
        env = dict(env or {})
        cmd = list(cmd)
        self.popens.append((cmd, env))
        method = cmd[cmd.index("--method") + 1]
        slice_value = cmd[cmd.index("--slice") + 1]
        start_text, _, step_text = slice_value.partition("::")
        start, step = int(start_text), int(step_text)
        self._emit(method, self._stems[start::step], env)
        return FakePopen()


# ----------------------------------------------------------------------------
# Mock predict script — dựng từ ĐÚNG anchor pristine trích khỏi file nền
# ----------------------------------------------------------------------------
MOCK_TEMPLATE = '''\
"""Pristine mock của scripts/predict_unet_transformer.py (chỉ để kiểm chứng chuỗi vá)."""
from __future__ import annotations

import numpy as np
import torch


class _Cfg:
    det_tta = True
    det_threshold = 0.965
    threshold = 0.5


cfg = _Cfg()


def _detect_cells_pooled(logits, frame, threshold, pool_k):
    return []


def load_model(path, device):
    return None, (2, 64, 64), (1, 4, 4)


class Runner:
    def predict(self, model, imgs, cfg, W, det_logits, unet_out):
@@P1_OLD@@

        del imgs
        return det_logits

    def score_edges(self, model, cfg, ds_path, pool_k, frame_indices, seen_frames, W,
                    secondary_model, f_idx, n_src):
        unet_feat_src = unet_feat_tgt = None
        p_coords_src = p_coords_tgt = None
        p_pos_src = p_pos_tgt = None
        p_mask_src = p_mask_tgt = None
        ds_arr_t = None
        for f_idx in range(1):
@@P2C_OLD@@
@@P2D_OLD@@        return raw


def predict_all(
    model,
    imgs,
    weights_path: str,
    device,
    unet_batch_size: int = 4,
@@P2A_OLD@@
    return [], []


def build_graph(coords, edges):
    all_edges = list(edges)
@@P4B_OLD@@


def main(weights_path, device, unet_batch_size, use_ilp):
    model, window_size, downsample = load_model(weights_path, device)
@@P2E_OLD@@        "mock ready",
        [
            predict_all(
                model,
@@P2F_OLD@@        ],
    )
'''


def load_payloads() -> dict:
    """Trích GIÁ TRỊ thật (ast.literal_eval) các payload khỏi file nền."""
    source = FOUNDATION.read_text()
    tree = ast.parse(source)
    wanted = {"_old", "_ensemble_replacements", "_coordinate_manifest_old"}
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    values[target.id] = ast.literal_eval(node.value)
    missing = wanted - set(values)
    assert not missing, f"thiếu payload: {missing}"
    return values


def build_mock_source(payloads: dict, corrupt: str | None = None) -> str:
    """corrupt: None | 'p1' | 'coord' — hỏng 1 anchor để thử hai pha."""
    ensemble = payloads["_ensemble_replacements"]
    p1_old = payloads["_old"]
    coord_old = payloads["_coordinate_manifest_old"]
    if corrupt == "p1":
        p1_old = p1_old.replace(
            "tta_flips = [(-1,), (-2,), (-2, -1)]",
            "tta_flips = [(-1,), (-2,)]",
        )
    if corrupt == "coord":
        coord_old = coord_old.replace("np.int16", "np.int32")
    mock = MOCK_TEMPLATE
    mock = mock.replace("@@P1_OLD@@", p1_old)
    mock = mock.replace("@@P2A_OLD@@", ensemble[0][0])
    mock = mock.replace("@@P2C_OLD@@", ensemble[2][0])
    mock = mock.replace("@@P2D_OLD@@", ensemble[3][0])
    mock = mock.replace("@@P2E_OLD@@", ensemble[4][0])
    mock = mock.replace("@@P2F_OLD@@", ensemble[5][0])
    mock = mock.replace("@@P4B_OLD@@", coord_old)
    return mock


def make_repo(base: Path, mock_source: str) -> Path:
    repo = base / "tracking_repo"
    scripts = repo / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "predict_unet_transformer.py").write_text(mock_source)
    (repo / "predictions").mkdir()
    return repo


def make_test_env(base: Path) -> Path:
    test_dir = base / "test"
    test_dir.mkdir()
    for stem in STEMS:
        (test_dir / f"{stem}.zarr").touch()
    return test_dir


def make_namespace(repo: Path, test_dir: Path, working: Path, fake_subprocess) -> dict:
    return {
        "__name__": "cell5_test",
        "__builtins__": __builtins__,
        "json": json,
        "os": os,
        "sys": sys,
        "time": time,
        "Path": Path,
        "subprocess": fake_subprocess,
        "REPO_DIR": repo,
        "TEST_DIR": test_dir,
        "WORKING_DIR": working,
        "METHOD": "unet_transformer",
        "WEIGHTS_RELATIVE": "weights/unet_transformer/split_0/edge_predictor_best.pth",
        "UNET_BATCH_SIZE": 4,
        "DET_THRESHOLD": 0.965,
        "ILP_EDGE_WEIGHT": -1.0,
        "ILP_APPEARANCE_WEIGHT": 0.0,
        "ILP_DISAPPEARANCE_WEIGHT": 2.0,
        "ILP_DIVISION_WEIGHT": 1.2,
        "USE_ILP": True,
        "SLICE": "",
    }


def split_before_section_8(source: str) -> str:
    marker = "# 8) Run inference"
    idx = source.index(marker)
    sep_idx = source.rfind("# ===", 0, idx)
    return source[:sep_idx]


class EnvGuard:
    def __enter__(self):
        self.snapshot = dict(os.environ)
        return self

    def __exit__(self, *exc):
        for key in list(os.environ):
            if key not in self.snapshot:
                del os.environ[key]
        os.environ.clear()
        os.environ.update(self.snapshot)
        return False


class TorchGuard:
    def __init__(self, fake_torch):
        self.fake = fake_torch

    def __enter__(self):
        self._original = sys.modules.get("torch")
        sys.modules["torch"] = self.fake

    def __exit__(self, *exc):
        if self._original is None:
            sys.modules.pop("torch", None)
        else:
            sys.modules["torch"] = self._original
        return False


def exec_cell(source: str, namespace: dict, fake_torch=None) -> str:
    buffer = io.StringIO()
    try:
        with TorchGuard(fake_torch or make_fake_torch(cuda_available=True, device_count=2)):
            with contextlib.redirect_stdout(buffer):
                exec(compile(source, "<cell5>", "exec"), namespace)
    except BaseException as error:  # noqa: BLE001 — gắn output rồi ném tiếp
        error.cell_output = buffer.getvalue()  # type: ignore[attr-defined]
        raise
    return buffer.getvalue()


# ----------------------------------------------------------------------------
# Tests
# ----------------------------------------------------------------------------
def test_t1_syntax(payloads):
    for path in (UPGRADED, FOUNDATION, MAKER):
        py_compile.compile(str(path), doraise=True)
    mock = build_mock_source(payloads)
    compile(mock, "<mock>", "exec")
    return [("py_compile 3 file + mock compile", True, "")]


def test_t2_payload_equivalence(payloads, base):
    results = []
    mock_src = build_mock_source(payloads)
    # Bản nền vá mockA
    repo_a = make_repo(base / "a_foundation", mock_src)
    out_a = exec_cell(
        split_before_section_8(FOUNDATION.read_text()),
        make_namespace(repo_a, make_test_env(base / "a_foundation"),
                       base / "a_foundation" / "working", None),
    )
    # Bản nâng cấp vá mockB
    repo_b = make_repo(base / "b_upgrade", mock_src)
    out_b = exec_cell(
        split_before_section_8(UPGRADED.read_text()),
        make_namespace(repo_b, make_test_env(base / "b_upgrade"),
                       base / "b_upgrade" / "working", None),
    )
    file_a = (repo_a / "scripts" / "predict_unet_transformer.py").read_bytes()
    file_b = (repo_b / "scripts" / "predict_unet_transformer.py").read_bytes()
    results.append(("file sau vá giống hệt từng byte (nền vs nâng cấp)",
                    file_a == file_b,
                    f"{len(file_a)} vs {len(file_b)} bytes"))
    results.append(("nền in đúng chuỗi xác nhận patch cuối",
                    "secondary edge-feature TTA patch installed and enabled" in out_a, ""))
    results.append(("nâng cấp in xác nhận single atomic write",
                    "Applied 12 patch operations (single atomic write)" in out_b, ""))
    return results, repo_b, out_b


def test_t3_compiles_and_markers(repo_b, payloads):
    results = []
    patched = (repo_b / "scripts" / "predict_unet_transformer.py").read_text()
    compile(patched, "<patched>", "exec")
    results.append(("script sau vá compile được", True, ""))
    markers = [
        ("imgs_at = torch.rot90(imgs, 1, dims=(-2, -1)).transpose(-1, -2)"),
        ("secondary_link_mode"),
        ("BIOHUB_RETENTION_GUARD"),
        ("_bidirectional_weight"),
        ("EDGE_TTA_ACTIVE"),
        ("SECONDARY_EDGE_TTA_ACTIVE"),
    ]
    for marker in markers:
        results.append((f"marker hiện diện: {marker[:44]}", marker in patched, ""))
    return results


def test_t4_rerun_safe(repo_b):
    results = []
    script_path = repo_b / "scripts" / "predict_unet_transformer.py"
    before = script_path.read_bytes()
    working = repo_b.parent / "b_upgrade" / "working"
    out = exec_cell(
        split_before_section_8(UPGRADED.read_text()),
        make_namespace(repo_b, repo_b.parent / "b_upgrade" / "test", working, None),
    )
    after = script_path.read_bytes()
    results.append(("lần 2: 'Patch phase skipped'", "Patch phase skipped" in out, ""))
    results.append(("lần 2: file KHÔNG đổi", before == after, ""))
    return results


def test_t5_anchor_drift(payloads, base):
    """Hỏng anchor CUỐI chuỗi (coordinate manifest, patch 4/2).

    Bản nâng cấp: verify-then-write → dừng TRƯỚC khi ghi, file nguyên vẹn.
    Đối chứng nền: patch 1..3 đã GHI ĐĨA tuần tự → patch 4 mới chết → file vá dở.
    (Hỏng anchor đầu chuỗi thì cả hai bản đều chết sớm — không phân biệt được.)
    """
    results = []
    mock_src = build_mock_source(payloads, corrupt="coord")
    # Bản nâng cấp: dừng trước khi ghi — file nguyên vẹn
    repo = make_repo(base / "c_drift_upgrade", mock_src)
    script_path = repo / "scripts" / "predict_unet_transformer.py"
    before = script_path.read_bytes()
    raised = None
    try:
        exec_cell(
            split_before_section_8(UPGRADED.read_text()),
            make_namespace(repo, make_test_env(base / "c_drift_upgrade"),
                           base / "c_drift_upgrade" / "working", None),
        )
    except RuntimeError as error:
        raised = error
    results.append(("anchor hỏng → RuntimeError", raised is not None, str(raised)[:80]))
    results.append(("thông điệp chỉ đúng patch hỏng (4/2 coordinate-manifest)",
                    raised is not None and "4/2 coordinate-manifest" in str(raised), ""))
    results.append(("file trên đĩa NGUYÊN VẸN (không ghi dở)",
                    script_path.read_bytes() == before, ""))
    # Đối chứng — bản nền: patch 1..3 ghi đĩa tuần tự, patch 4 mới chết → file vá dở
    repo_f = make_repo(base / "d_drift_foundation", mock_src)
    script_f = repo_f / "scripts" / "predict_unet_transformer.py"
    before_f = script_f.read_bytes()
    out_f = ""
    raised_f = None
    try:
        out_f = exec_cell(
            split_before_section_8(FOUNDATION.read_text()),
            make_namespace(repo_f, make_test_env(base / "d_drift_foundation"),
                           base / "d_drift_foundation" / "working", None),
        )
    except RuntimeError as error:
        raised_f = error
        out_f = getattr(error, "cell_output", "")
    results.append(("đối chứng nền: cũng raise (anchor 0 match)",
                    raised_f is not None, str(raised_f)[:80]))
    results.append(("đối chứng nền: patch 1..3 đã chạy (in xác nhận)",
                    "Calibrated dual-seed runtime patch applied" in out_f
                    and "Frozen frame retention guard applied" in out_f, ""))
    results.append(("đối chứng nền: file BỊ SỬA DỞ (điểm yếu đã chẩn đoán)",
                    script_f.read_bytes() != before_f, ""))
    return results


def test_t6_single_gpu(payloads, base):
    results = []
    mock_src = build_mock_source(payloads)
    root = base / "e_single"
    repo = make_repo(root, mock_src)
    test_dir = make_test_env(root)
    working = root / "working"
    working.mkdir()
    fake = FakeSubprocess(repo, working, STEMS, retention_records=None)
    ns = make_namespace(repo, test_dir, working, fake)
    out = exec_cell(UPGRADED.read_text(), ns,
                    fake_torch=make_fake_torch(cuda_available=True, device_count=1))
    results.append(("chọn nhánh single-process",
                    "Using single-process prediction" in out, ""))
    results.append(("subprocess.run gọi 1 lần", len(fake.runs) == 1, str(len(fake.runs))))
    if fake.runs:
        cmd, env = fake.runs[0]
        results.append(("env PYTHONPATH=src", env.get("PYTHONPATH") == "src", ""))
        results.append(("cmd có --use-ilp", "--use-ilp" in cmd, ""))
        results.append(("cmd có det-threshold 0.965",
                        "0.965" in [str(x) for x in cmd], ""))
    final_dir = repo / "predictions" / "mockuser" / "unet_transformer" / "split_0"
    geffs = sorted(p.stem for p in final_dir.glob("*.geff"))
    results.append(("đủ 5 .geff sau chạy", geffs == STEMS, str(geffs)))
    splits = json.loads((repo / "kaggle_test_splits_50ep.json").read_text())
    results.append(("splits JSON đúng 5 stem",
                    splits == [{"split": 0, "train": [], "test": STEMS}], ""))
    results.append(("tổng hợp retention: nhánh 'no logs'",
                    "Retention guard: no logs" in out, ""))
    results.append(("in Prediction completed", "Prediction completed in" in out, ""))
    results.append(("in Throughput", "Throughput: 5 videos" in out, ""))
    results.append(("preflight manifest in ra", "== Cell 5 preflight ==" in out, ""))
    return results


def test_t7_dual_gpu(payloads, base):
    results = []
    mock_src = build_mock_source(payloads)
    root = base / "f_dual"
    repo = make_repo(root, mock_src)
    test_dir = make_test_env(root)
    working = root / "working"
    working.mkdir()
    fake = FakeSubprocess(repo, working, STEMS, retention_records=RETENTION_RECORDS)
    ns = make_namespace(repo, test_dir, working, fake)
    out = exec_cell(UPGRADED.read_text(), ns,
                    fake_torch=make_fake_torch(cuda_available=True, device_count=2))
    results.append(("chạy 2 shard", "Launching 2 independent video shards" in out, ""))
    results.append(("2 Popen", len(fake.popens) == 2, str(len(fake.popens))))
    if len(fake.popens) == 2:
        (cmd0, env0), (cmd1, env1) = fake.popens
        results.append(("shard0: CUDA_VISIBLE_DEVICES=0", env0.get("CUDA_VISIBLE_DEVICES") == "0", ""))
        results.append(("shard1: CUDA_VISIBLE_DEVICES=1", env1.get("CUDA_VISIBLE_DEVICES") == "1", ""))
        results.append(("shard0: GPU_SHARD=0/2", env0.get("BIOHUB_GPU_SHARD") == "0/2", ""))
        results.append(("shard1: GPU_SHARD=1/2", env1.get("BIOHUB_GPU_SHARD") == "1/2", ""))
        results.append(("shard0 PYTHONPATH=src", env0.get("PYTHONPATH") == "src", ""))
        results.append(("shard0 --slice 0::2", "0::2" in cmd0, ""))
        results.append(("shard1 --slice 1::2", "1::2" in cmd1, ""))
        results.append(("shard0 method riêng _gpu0",
                        "unet_transformer_gpu0" in cmd0, ""))
    final_dir = repo / "predictions" / "mockuser" / "unet_transformer" / "split_0"
    geffs = sorted(p.stem for p in final_dir.glob("*.geff"))
    results.append(("merge đủ 5 .geff", geffs == STEMS, str(geffs)))
    results.append(("dọn thư mục shard 0",
                    not (repo / "predictions" / "mockuser" / "unet_transformer_gpu0").exists(), ""))
    results.append(("dọn thư mục shard 1",
                    not (repo / "predictions" / "mockuser" / "unet_transformer_gpu1").exists(), ""))
    results.append(("in 'Merged 5 prediction graphs'", "Merged 5 prediction graphs" in out, ""))
    results.append(("retention: 1/4 guarded",
                    "Retention guard: 1/4 logged frames fell back to primary detection" in out, ""))
    results.append(("retention: worst 0.830 tại video_a frame 12",
                    "worst retention 0.830 at video_a frame 12" in out, ""))
    results.append(("per-dataset: video_a 1/2 guarded",
                    "video_a: 1/2 guarded" in out, ""))
    return results


def test_t8_env_respect(payloads, base):
    results = []
    mock_src = build_mock_source(payloads)
    # (a) nâng cấp — có preset thì giữ nguyên
    root = base / "g_env_preset"
    repo = make_repo(root, mock_src)
    with EnvGuard():
        os.environ["BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION"] = "0.85"
        os.environ["BIOHUB_EDGE_FEATURE_TTA"] = "0"
        exec_cell(
            split_before_section_8(UPGRADED.read_text()),
            make_namespace(repo, make_test_env(root), root / "working", None),
        )
        results.append(("preset retention 0.85 được GIỮ NGUYÊN",
                        os.environ["BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION"] == "0.85", ""))
        results.append(("preset EDGE_FEATURE_TTA=0 được GIỮ NGUYÊN",
                        os.environ["BIOHUB_EDGE_FEATURE_TTA"] == "0", ""))
    # (b) nâng cấp — không preset thì dùng mặc định 0.945
    root = base / "h_env_default"
    repo = make_repo(root, mock_src)
    with EnvGuard():
        for key in ("BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION", "BIOHUB_EDGE_FEATURE_TTA",
                    "BIOHUB_SECONDARY_EDGE_FEATURE_TTA",
                    "BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT"):
            os.environ.pop(key, None)
        exec_cell(
            split_before_section_8(UPGRADED.read_text()),
            make_namespace(repo, make_test_env(root), root / "working", None),
        )
        results.append(("mặc định retention=0.90",
                        os.environ["BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION"] == "0.90", ""))
        results.append(("mặc định EDGE_FEATURE_TTA=1",
                        os.environ["BIOHUB_EDGE_FEATURE_TTA"] == "1", ""))
        results.append(("mặc định SECONDARY_EDGE_FEATURE_TTA=1",
                        os.environ["BIOHUB_SECONDARY_EDGE_FEATURE_TTA"] == "1", ""))
        results.append(("mặc định SECONDARY_EDGE_FEATURE_TTA_WEIGHT=0.75",
                        os.environ["BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT"] == "0.75", ""))
    # (c) đối chứng nền — GHI ĐÈ preset (bẫy tune đã chẩn đoán)
    root = base / "i_env_foundation"
    repo = make_repo(root, mock_src)
    with EnvGuard():
        os.environ["BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION"] = "0.85"
        os.environ["BIOHUB_EDGE_FEATURE_TTA"] = "0"
        exec_cell(
            split_before_section_8(FOUNDATION.read_text()),
            make_namespace(repo, make_test_env(root), root / "working", None),
        )
        results.append(("đối chứng nền: preset 0.85 BỊ GHI ĐÈ thành 0.90",
                        os.environ["BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION"] == "0.90", ""))
        results.append(("đối chứng nền: preset =0 BỊ GHI ĐÈ thành 1",
                        os.environ["BIOHUB_EDGE_FEATURE_TTA"] == "1", ""))
    return results


def test_t9_no_gpu(payloads, base):
    mock_src = build_mock_source(payloads)
    root = base / "j_nogpu"
    repo = make_repo(root, mock_src)
    raised = None
    with TorchGuard(make_fake_torch(cuda_available=False)):
        try:
            exec_cell(split_before_section_8(UPGRADED.read_text()),
                      make_namespace(repo, make_test_env(root), root / "working", None),
                      fake_torch=make_fake_torch(cuda_available=False))
        except RuntimeError as error:
            raised = error
    return [("không GPU → RuntimeError 'CUDA GPU is required'",
             raised is not None and "CUDA GPU is required" in str(raised), "")]


def test_t10_missing_script(base):
    root = base / "k_missing"
    repo = root / "tracking_repo"
    (repo / "scripts").mkdir(parents=True)
    raised = None
    fake_torch = make_fake_torch(cuda_available=True, device_count=2)
    try:
        exec_cell(split_before_section_8(UPGRADED.read_text()),
                  make_namespace(repo, make_test_env(root), root / "working", None),
                  fake_torch=fake_torch)
    except FileNotFoundError as error:
        raised = error
    return [("thiếu script → FileNotFoundError dẫn về section 4",
             raised is not None and "section 4" in str(raised), "")]


# ----------------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------------
def main() -> int:
    payloads = load_payloads()
    failures = 0
    total = 0
    with tempfile.TemporaryDirectory(prefix="ver5_cell5_") as tmp:
        base = Path(tmp)
        with EnvGuard():
            os.environ.update(S1_S4_ENV)
            groups = []
            groups.append(("T1 cú pháp", test_t1_syntax(payloads)))
            t2 = test_t2_payload_equivalence(payloads, base)
            groups.append(("T2 đẳng thức payload (nền vs nâng cấp)", t2[0]))
            groups.append(("T3 mock sau vá compile + marker",
                           test_t3_compiles_and_markers(t2[1], payloads)))
            groups.append(("T4 re-run an toàn", test_t4_rerun_safe(t2[1])))
            groups.append(("T5 anchor drift (hai pha vs nền)", test_t5_anchor_drift(payloads, base)))
            groups.append(("T6 luồng 1 GPU", test_t6_single_gpu(payloads, base)))
            groups.append(("T7 luồng 2 GPU + retention", test_t7_dual_gpu(payloads, base)))
            groups.append(("T8 tôn trọng env S1", test_t8_env_respect(payloads, base)))
            groups.append(("T9 không GPU", test_t9_no_gpu(payloads, base)))
            groups.append(("T10 thiếu script", test_t10_missing_script(base)))

        for group_name, results in groups:
            print(f"\n== {group_name}")
            for name, ok, detail in results:
                total += 1
                mark = "ĐẠT" if ok else "FAIL"
                if not ok:
                    failures += 1
                suffix = f"  [{detail}]" if detail and not ok else ""
                print(f"  {mark} · {name}{suffix}")
    print(f"\n================================")
    print(f"TỔNG: {total - failures}/{total} ĐẠT")
    if failures:
        print("CÓ FAIL — xem chi tiết ở trên.")
        return 1
    print("TẤT CẢ ĐẠT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
