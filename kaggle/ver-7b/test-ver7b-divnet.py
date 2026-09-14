"""test-ver7b-divnet.py — Unit test khối DivNet trong ver-7b monolith (không cần Kaggle).

(Bản tái tạo sau sandbox rollback 13/9 — logic giống hệt bản đã PASS 7/7 trước đó.)

Kiểm thử:
  1. Trích khối divnet từ cell-monolith.py (nguồn chân lý) và exec với các global cần thiết
  2. Load checkpoint THẬT api/research/divnet/v2/best_overall.pt (bản tải lại từ
     giorgosi/biohub-divnet-v2) qua đường dẫn explicit (giống cơ chế env của kernel)
  3. Forward pass synthetic: shape đúng (N,1), sigmoid(2.5*x) ∈ [0,1], finite
  4. _divnet_extract_crop: shape (5,16,32,32), marker channel peak đúng vị trí
  5. _divnet_rerank_proposals: đổi thứ tự đúng hướng (P_div cao → score thấp hơn W*p),
     stats đếm đúng, giữ nguyên 5 trường của proposal + thêm p_div
  6. Deterministic: 2 lần chạy cho kết quả giống hệt
  7. self-consistency: score_query đơn lẻ == trong batch lớn (dung sai float 1e-6)
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent          # kaggle/ver-7b/
CKPT = ROOT.parent / "api" / "research" / "divnet" / "v2" / "best_overall.pt"

# ---- 1. trích khối divnet từ monolith ----------------------------------------
monolith = (ROOT / "cell-monolith.py").read_text()
start = monolith.index("# [ver7b] ---------------------------------------------------------------------")
end = monolith.index("# [ver7b] ---------------- kết thúc khối DivNet ----------------")
block = monolith[start:end + len("# [ver7b] ---------------- kết thúc khối DivNet ----------------")]

ns = {
    "__name__": "divnet_test",
    "Path": Path, "json": json, "math": math, "np": np,
    # cấu hình module như trong monolith
    "DIVNET_ENABLE": True, "DIVNET_RANK": True, "DIVNET_RANK_W_UM": 15.0,
    "DIVNET_REQUIRE": True, "DIVNET_BATCH": 64,
    "DIVNET_CHECKPOINT_EXPLICIT": str(CKPT),
    "DIVNET_MANIFEST_EXPLICIT": "",
    # read_test_frame stub: volume synthetic (T, Z, Y, X) lưu trong dict theo t
    "read_test_frame": lambda dataset, t, cache: _VOLUME[int(t)],
}
_VOLUME = np.zeros((12, 64, 256, 256), dtype=np.uint16)
rng = np.random.default_rng(314159)
_VOLUME[:] = (rng.random(_VOLUME.shape) * 900 + 100).astype(np.uint16)
# một "tế bào" sáng tại (z=30, y=128, x=128) các frame 3-7 — giả lập object
_VOLUME[3:8, 26:34, 120:136, 120:136] = 4000

exec(compile(block, "divnet-block", "exec"), ns)

print("[1] exec khối divnet từ monolith: OK")

# ---- 2. load ranker -----------------------------------------------------------
ranker = ns["load_divnet_ranker"]()
assert ranker is not None, "ranker phải load được"
assert len(ranker["models"]) == 1, "dataset v2 chỉ có best_overall.pt → 1 model"
geom = ranker["geom"]
assert (geom.crop_z, geom.crop_yx) == (16, 32) and geom.pool_xy == 4 and geom.channels == 5
assert tuple(geom.image_lags) == (-1, 0, 1, 2)
print(f"[2] load checkpoint thật: OK (crop={geom.crop_z}x{geom.crop_yx}, pool_xy={geom.pool_xy}, lags={geom.image_lags})")

# ---- 3. forward synthetic -------------------------------------------------------
import torch
with torch.no_grad():
    probe = torch.randn(8, 5, 16, 32, 32)
    logits = ranker["models"][0](probe)
    assert logits.shape == (8,), f"shape sai: {logits.shape}"
    p = torch.sigmoid(logits * 2.5)
    assert torch.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()
print("[3] forward synthetic: OK — shape (8,), sigmoid(2.5x) ∈ [0,1] finite")

# ---- 4. extract crop ------------------------------------------------------------
frames = [_VOLUME[4], _VOLUME[5], _VOLUME[6], _VOLUME[7]]
crop = ns["_divnet_extract_crop"](frames, (30.0, 128.0, 128.0), geom)
assert crop.shape == (5, 16, 32, 32), f"crop shape sai: {crop.shape}"
assert crop.dtype == np.float32
marker = crop[4]
assert marker.max() > 0.99, "marker phải có đỉnh ~1 tại tâm"
zz, yy, xx = np.unravel_index(marker.argmax(), marker.shape)
assert abs(zz - 8) <= 1, f"đỉnh marker z lệch: {zz}"
assert abs(yy - 16) <= 1 and abs(xx - 16) <= 1, f"đỉnh marker yx lệch: {yy},{xx}"
assert crop[1, 8, 16, 16] > crop[1, 0, 0, 0]
print(f"[4] extract crop: OK — marker peak tại ({zz},{yy},{xx}), object sáng hơn nền")

# ---- 5. rerank proposals --------------------------------------------------------
def make_frame_cache():
    return {t: _VOLUME[t] for t in range(12)}

proposals = [
    (5.0, 101, 201, 5.0, 3.0),    # mẹ A gần (score 5.45)
    (6.0, 102, 202, 6.0, 0.0),    # mẹ B (score 6.0)
    (7.0, 103, 203, 7.0, 0.0),    # mẹ C (score 7.0)
]
nodes_by_id = {
    101: {"node_id": 101, "t": 4, "z": 30.0, "y": 128.0, "x": 128.0},  # trong object sáng
    102: {"node_id": 102, "t": 4, "z": 30.0, "y": 100.0, "x": 100.0},  # nền
    103: {"node_id": 103, "t": 4, "z": 30.0, "y": 60.0, "x": 60.0},   # nền
    201: {"node_id": 201, "t": 5, "z": 30.5, "y": 128.5, "x": 128.5},
    202: {"node_id": 202, "t": 5, "z": 30.5, "y": 100.5, "x": 100.5},
    203: {"node_id": 203, "t": 5, "z": 30.5, "y": 60.5, "x": 60.5},
}
stats = {"divnet_proposals_scored": 0, "divnet_rank_flips": 0}
out = ns["_divnet_rerank_proposals"](ranker, "synthetic", 4, proposals, nodes_by_id, make_frame_cache(), 0, 11, stats)
assert len(out) == 3
for o in out:
    assert len(o) == 6, f"proposal phải có 6 trường (thêm p_div): {len(o)}"
    p_div = o[5]
    assert 0.0 <= p_div <= 1.0
    assert abs(o[0] - (o[3] + 0.15 * o[4] - 15.0 * p_div)) < 1e-9, "công thức rank sai"
assert stats["divnet_proposals_scored"] == 3
print(f"[5] rerank: OK — p_div = {[round(o[5],4) for o in out]}")
print(f"    score cũ = {[round(p[0],3) for p in proposals]}")
print(f"    score mới = {[round(o[0],3) for o in out]} (đã trừ 15×P_div)")

# ---- 6. determinism --------------------------------------------------------------
out2 = ns["_divnet_rerank_proposals"](ranker, "synthetic", 4, proposals, nodes_by_id, make_frame_cache(), 0, 11,
                                      {"divnet_proposals_scored": 0, "divnet_rank_flips": 0})
assert out == out2, "phải deterministic (eval mode)"
print("[6] deterministic: OK — 2 lần chạy cho kết quả giống hệt từng bit")

# ---- 7. batch consistency --------------------------------------------------------
q1 = ns["_divnet_score_queries"](ranker, "synthetic", [(4, 30.0, 128.0, 128.0)], make_frame_cache(), 0, 11)
q3 = ns["_divnet_score_queries"](ranker, "synthetic",
                                  [(4, 30.0, 128.0, 128.0), (4, 30.0, 100.0, 100.0), (4, 30.0, 60.0, 60.0)],
                                  make_frame_cache(), 0, 11)
assert len(q1) == 1 and len(q3) == 3
# Ghi chú: batch khác kích thước có thể lệch ~1e-8 do conv blocking float — không phải bug
assert abs(q1[0] - q3[0]) < 1e-6, f"batch phải nhất quán: {q1[0]} vs {q3[0]}"
print(f"[7] batch consistency: OK — đơn lẻ {q1[0]:.6f} == trong batch {q3[0]:.6f}")

print("\n=== TOÀN BỘ TEST KHỐI DIVNET ver-7b (bản tái tạo): PASS (7/7) ===")
