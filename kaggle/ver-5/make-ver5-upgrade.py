# -*- coding: utf-8 -*-
"""Lắp ráp cell5code.py (ver 5.1 — bản nâng cấp) từ cell5-foundation-verbatim.py.

Nguyên tắc: TOÀN BỘ payload vá (các cặp old/new của 6 patch) và toàn bộ section 8
(run inference) được trích XÁC EXACT từng byte từ bản nền bằng AST — không gõ lại
tay. File này chỉ thay đổi phần ĐIỀU PHỐI quanh payload (hai pha verify-then-write,
re-run an toàn, preflight, tổng hợp retention guard).

Chạy:  python3 make-ver5-upgrade.py   (từ thư mục kaggle/ver-5)
"""
from __future__ import annotations

import ast
import py_compile
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOUNDATION = HERE / "cell5-foundation-verbatim.py"
OUTPUT = HERE / "cell5code.py"

# Các phép gán payload cần trích (tên biến trong file nền, theo thứ tự xuất hiện)
SEGMENT_NAMES = [
    "_old",                          # (1) detection TTA 8 hướng — old
    "_new",                          # (1) — new
    "_ensemble_replacements",        # (2) dual-seed — 6 phép thay
    "_guard_old",                    # (3) retention guard — old
    "_guard_new",                    # (3) — new
    "_bi_old",                       # (4) bidirectional — old
    "_bi_new",                       # (4) — new
    "_coordinate_manifest_old",      # (4b) coordinate manifest — old
    "_coordinate_manifest_new",      # (4b) — new
    "_et_old",                       # (5) EDGE_FEATURE_TTA — old
    "_et_new",                       # (5) — new
    "_secondary_tta_old",            # (6) SECONDARY_EDGE_TTA — old
    "_secondary_tta_new",            # (6) — new
]

TEMPLATE = r'''# ver 5.1 · cell 5 — PATCH SUY LUẬN HAI PHA + CHẠY DỰ ĐOÁN SONG SONG (2 GPU)
# ============================================================================
# BẢN NÂNG CẤP của section 5 notebook 0.945 (pawanmali/biohub-942proxy-fork-v1).
# Nền nguyên văn được lưu tại kaggle/ver-5/cell5-foundation-verbatim.py; tài liệu
# đầy đủ: kaggle/ver-5/CELL5-TRIEN-KHAI.md (mục 9 mô tả đúng file này).
#
# NÂNG CẤP so với nền — CHỈ phần điều phối; TOÀN BỘ payload của 6 bản vá giữ
# nguyên TỪNG BYTE (trích bằng AST khỏi file nền, kiểm chứng đẳng thức output
# bằng test-ver5-cell5.py — test T7 vá mock bằng cả hai bản rồi diff byte):
#   (1) HAI PHA: xác minh lần lượt từng anchor (đúng 1 match) + áp trong bộ nhớ,
#       compile một lần, ghi MỘT lần — anchor hỏng thì DỪNG TRƯỚC KHI GHI,
#       file trên đĩa không bao giờ rơi vào trạng thái vá dở.
#       (Nền: patch 1 chỉ in warning khi không tìm thấy anchor, replace mọi
#       match, không compile; các patch ghi đĩa tuần tự nên hỏng giữa chừng
#       để lại file vá dở.)
#   (2) RE-RUN AN TOÀN: script đã vá đủ 6 patch (kiểm marker) thì bỏ qua khối
#       vá, chạy thẳng dự đoán — không cần chạy lại section 4 để tái tạo repo.
#   (3) TÔN TRỌNG S1/S4: 4 env mà nền ghi đè cứng giờ dùng setdefault — S1 đặt
#       giá trị nào thì dùng giá trị đó; không đặt thì dùng đúng giá trị 0.945.
#       (Trước đây sửa BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION trong S1 bị
#       cell 5 ghi đè im lặng — bẫy tune.)
#   (4) PREFLIGHT: in khối cấu hình hiệu dụng trước khi chạy (chống drift).
#   (5) TỔNG HỢP RETENTION GUARD sau khi chạy: đếm khung rơi về detection gốc
#       theo dataset + retention xấu nhất (đọc retention_guard_*.jsonl).
#
# CÁCH DÙNG (Kaggle): Copy & Edit notebook gốc → THAY THẾ cell "## 5." bằng
# file này → Save & Run All. Cell tiêu thụ đúng biến của section 3 như bản nền
# (REPO_DIR, TEST_DIR, METHOD, WEIGHTS_RELATIVE, UNET_BATCH_SIZE, DET_THRESHOLD,
# ILP_*, USE_ILP, SLICE, WORKING_DIR) — không thêm phụ thuộc mới.
# ============================================================================

# ============================================================
# 0) Fail-fast GPU + preflight
# ============================================================
import torch as _torch

if not _torch.cuda.is_available():
    raise RuntimeError(
        "CUDA GPU is required for this notebook. Enable a Kaggle GPU accelerator and commit again."
    )
print("CUDA device:", _torch.cuda.get_device_name(0))

_ps = REPO_DIR / "scripts" / "predict_unet_transformer.py"
if not _ps.exists():
    raise FileNotFoundError(
        "Prediction script not found (run section 4 first): %s" % _ps
    )

# Tôn trọng S1/S4: chỉ đặt mặc định khi chưa ai đặt. Giá trị mặc định trùng
# đúng bản 0.945 nên hành vi không đổi khi S1/S4 giữ nguyên.
os.environ.setdefault("BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION", "0.90")
os.environ.setdefault("BIOHUB_EDGE_FEATURE_TTA", "1")
os.environ.setdefault("BIOHUB_SECONDARY_EDGE_FEATURE_TTA", "1")
os.environ.setdefault("BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT", "0.75")

for _guard_old_log in WORKING_DIR.glob("retention_guard_*.jsonl"):
    _guard_old_log.unlink()

_secondary_weights = os.environ.get("BIOHUB_SECONDARY_WEIGHTS", "").strip()
print("== Cell 5 preflight ==")
print("  patch target      : %s" % _ps)
print("  method / slice    : %s / %r" % (METHOD, SLICE))
print("  det threshold     : %s | unet batch %s | use_ilp=%s" % (
    DET_THRESHOLD, UNET_BATCH_SIZE, USE_ILP))
print("  ilp w (e/a/d/div) : %s / %s / %s / %s" % (
    ILP_EDGE_WEIGHT, ILP_APPEARANCE_WEIGHT, ILP_DISAPPEARANCE_WEIGHT,
    ILP_DIVISION_WEIGHT))
if _secondary_weights:
    print("  secondary         : %s" % _secondary_weights)
    print("    edge_w=%s det_w=%s mode=%s low_margin=%s mix_T=%s" % (
        os.environ.get("BIOHUB_SECONDARY_EDGE_WEIGHT"),
        os.environ.get("BIOHUB_SECONDARY_DETECTION_WEIGHT"),
        os.environ.get("BIOHUB_SECONDARY_LINK_MODE"),
        os.environ.get("BIOHUB_SECONDARY_LOW_MARGIN_MAX"),
        os.environ.get("BIOHUB_SECONDARY_MIX_TEMPERATURE")))
else:
    print("  secondary         : <disabled>")
print("  retention floor   : %s" % os.environ["BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION"])
print("  bidirectional w   : %s" % os.environ.get("BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT", "<unset>"))
print("  feature TTA       : primary=%s secondary=%s (w=%s)" % (
    os.environ["BIOHUB_EDGE_FEATURE_TTA"],
    os.environ["BIOHUB_SECONDARY_EDGE_FEATURE_TTA"],
    os.environ["BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT"]))
print("  CUDA devices      : %d" % _torch.cuda.device_count())

# ============================================================
# 1-6) SÁU BẢN VÁ — payload giữ nguyên từng byte của bản nền 0.945
#      (điều phối hai pha: verify-then-write, ghi một lần)
# ============================================================
_s = _ps.read_text()

# 6 marker — mỗi marker CHỈ tồn tại sau khi patch tương ứng đã áp dụng.
_ALREADY_PATCHED_MARKERS = (
    "imgs_at = torch.rot90(imgs, 1, dims=(-2, -1)).transpose(-1, -2)",  # (1) TTA 8 view
    "secondary_link_mode",                                               # (2) dual-seed
    "BIOHUB_RETENTION_GUARD",                                            # (3) retention guard
    "_bidirectional_weight",                                              # (4) bidirectional
    "EDGE_TTA_ACTIVE",                                                   # (5) edge feature TTA
    "SECONDARY_EDGE_TTA_ACTIVE",                                         # (6) secondary edge TTA
)

# ---- (1) Detection TTA 8 hướng (D4, không lật trục z) ----
@@SEG:_old@@

@@SEG:_new@@

# ---- (2) Dual-seed ensemble "calibrated" — 6 phép thay ----
@@SEG:_ensemble_replacements@@

# ---- (3) Retention guard — blend không được làm mất >10% ứng viên ----
@@SEG:_guard_old@@

@@SEG:_guard_new@@

# ---- (4) Bidirectional harmonic fusion + coordinate manifest ----
@@SEG:_bi_old@@

@@SEG:_bi_new@@

@@SEG:_coordinate_manifest_old@@

@@SEG:_coordinate_manifest_new@@

# ---- (5) EDGE_FEATURE_TTA (model chính) ----
@@SEG:_et_old@@

@@SEG:_et_new@@

# ---- (6) SECONDARY_EDGE_TTA (model phụ, w=0.75) ----
@@SEG:_secondary_tta_old@@

@@SEG:_secondary_tta_new@@

# Chuẩn hoá chuỗi patch theo đúng thứ tự bản nền áp lên đĩa.
_patches = [
    ("1/1 detection-TTA-8views", _old, _new),
]
_patches += [
    ("2/%d dual-seed-calibrated" % _i, _pair_old, _pair_new)
    for _i, (_pair_old, _pair_new) in enumerate(_ensemble_replacements, start=1)
]
_patches += [
    ("3/1 retention-guard", _guard_old, _guard_new),
    ("4/1 bidirectional-fusion", _bi_old, _bi_new),
    ("4/2 coordinate-manifest", _coordinate_manifest_old, _coordinate_manifest_new),
    ("5/1 edge-feature-tta", _et_old, _et_new),
    ("6/1 secondary-edge-tta", _secondary_tta_old, _secondary_tta_new),
]

if all(_marker in _s for _marker in _ALREADY_PATCHED_MARKERS):
    print("Patch phase skipped: prediction script already carries all six patches.")
    print("(To re-patch from scratch, re-run section 4 to re-materialize the repo.)")
else:
    # ---- PHA 1+2: xác minh TỪNG anchor rồi áp ngay trong bộ nhớ
    # (anchor của patch N khớp trên văn bản sau patch N-1 — như bản nền
    #  đọc-ghi đĩa tuần tự; ở đây tất cả diễn ra trong bộ nhớ).
    _work = _s
    print("Verifying and applying %d patch anchors (nothing hits disk until all pass)..." % len(_patches))
    for _patch_name, _patch_old, _patch_new in _patches:
        _found = _work.count(_patch_old)
        if _found != 1:
            raise RuntimeError(
                "Patch %s: expected exactly one anchor match, found %d. "
                "The repository is not in the expected pristine state — "
                "re-run section 4 (materialize repository) then section 5."
                % (_patch_name, _found)
            )
        _work = _work.replace(_patch_old, _patch_new, 1)
        print("  anchor ok + applied in memory: %s" % _patch_name)
    # ---- PHA 3: compile một lần rồi GHI MỘT LẦN ----
    compile(_work, str(_ps), "exec")
    _ps.write_text(_work)
    _persisted = _ps.read_text()
    for _marker in ("EDGE_TTA_ACTIVE", "SECONDARY_EDGE_TTA_ACTIVE", "BIOHUB_RETENTION_GUARD"):
        if _marker not in _persisted:
            raise RuntimeError("Patch did not persist: %s missing after write" % _marker)
    print("Applied %d patch operations (single atomic write) to %s" % (len(_patches), _ps))

# ============================================================
# 8) Run inference
# ============================================================
@@TAIL@@

# ============================================================
# 9) Tổng hợp retention guard + tốc độ chạy
# ============================================================
print(
    "Throughput: %d videos in %.2f minutes (%.1f videos/h)"
    % (len(test_stems), predict_seconds / 60.0,
       len(test_stems) / max(predict_seconds, 1e-9) * 3600.0)
)

_guard_files = sorted(WORKING_DIR.glob("retention_guard_*.jsonl"))
if not _guard_files:
    print("Retention guard: no logs (secondary detection blending inactive).")
else:
    _frames = 0
    _guarded = 0
    _worst_retention = 1.1
    _worst_where = None
    _by_dataset = {}
    for _guard_file in _guard_files:
        for _guard_line in _guard_file.read_text().splitlines():
            if not _guard_line.strip():
                continue
            try:
                _record = json.loads(_guard_line)
            except json.JSONDecodeError:
                continue
            _frames += 1
            _dataset = str(_record.get("dataset", "?"))
            _counts = _by_dataset.setdefault(_dataset, [0, 0])
            _counts[1] += 1
            _retention = float(_record.get("retention", 1.0))
            if _retention < _worst_retention:
                _worst_retention = _retention
                _worst_where = "%s frame %s" % (_dataset, _record.get("frame"))
            if _record.get("use_primary"):
                _guarded += 1
                _counts[0] += 1
    print(
        "Retention guard: %d/%d logged frames fell back to primary detection"
        % (_guarded, _frames)
    )
    for _dataset, (_g, _t) in sorted(_by_dataset.items()):
        print("    %s: %d/%d guarded" % (_dataset, _g, _t))
    if _worst_where is not None:
        print("    worst retention %.3f at %s" % (_worst_retention, _worst_where))
'''


def extract_segments(source: str) -> dict[str, str]:
    """Trích đúng source của các phép gán payload theo tên (dựa vào AST)."""
    tree = ast.parse(source)
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            for name in names:
                if name in SEGMENT_NAMES and name not in found:
                    seg = ast.get_source_segment(source, node)
                    assert seg is not None, name
                    found[name] = seg
    missing = [n for n in SEGMENT_NAMES if n not in found]
    assert not missing, "Thiếu payload trong file nền: %s" % missing
    return found


def main() -> None:
    source = FOUNDATION.read_text()

    segments = extract_segments(source)

    tail_marker = "def list_test_stems"
    tail_idx = source.index(tail_marker)
    tail = source[tail_idx:].rstrip("\n") + "\n"

    out = TEMPLATE
    for name, seg in segments.items():
        seg = seg.rstrip("\n")
        out = out.replace("@@SEG:%s@@" % name, seg)
    out = out.replace("@@TAIL@@", tail)

    assert "@@SEG:" not in out and "@@TAIL@@" not in out

    # Đối chiếu: mọi payload cũ (anchor) phải xuất hiện đúng 1 lần trong file mới
    # (chúng là chuỗi literal trong các phép gán).
    for name in SEGMENT_NAMES:
        assert out.count(segments[name]) == 1, "payload %s không xuất hiện đúng 1 lần" % name

    OUTPUT.write_text(out)
    py_compile.compile(str(OUTPUT), doraise=True)
    print("Đã ghi %s (%d bytes)" % (OUTPUT, len(out)))
    print("Payload byte-đúng từ: %s" % FOUNDATION)
    print("Section 8 trích nguyên văn từ ký tự %d đến hết." % tail_idx)


if __name__ == "__main__":
    sys.exit(main())
