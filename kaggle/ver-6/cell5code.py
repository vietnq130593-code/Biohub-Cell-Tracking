# ver 5.1 · cell 5 — PATCH SUY LUẬN HAI PHA + CHẠY DỰ ĐOÁN SONG SONG (2 GPU)
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
_old = """        if cfg.det_tta:
            tta_flips = [(-1,), (-2,), (-2, -1)]
            for dims in tta_flips:
                imgs_flip = imgs.flip(dims)
                _, det_flip = model.encode(imgs_flip)
                for f in range(W):
                    det_logits[f] = det_logits[f] + det_flip[f].flip(dims)
                del imgs_flip, det_flip
            for f in range(W):
                det_logits[f] = det_logits[f] / 4"""

_new = """        if cfg.det_tta:
            _nv = 1
            for dims in [(-1,), (-2,), (-2, -1)]:
                imgs_flip = imgs.flip(dims)
                _, det_flip = model.encode(imgs_flip)
                for f in range(W):
                    det_logits[f] = det_logits[f] + det_flip[f].flip(dims)
                del imgs_flip, det_flip
                _nv += 1
            for _k in (1, 3):
                imgs_rot = torch.rot90(imgs, _k, dims=(-2, -1))
                _, det_rot = model.encode(imgs_rot)
                for f in range(W):
                    det_logits[f] = det_logits[f] + torch.rot90(det_rot[f], -_k, dims=(-2, -1))
                del imgs_rot, det_rot
                _nv += 1
            imgs_t = imgs.transpose(-1, -2)
            _, det_t = model.encode(imgs_t)
            for f in range(W):
                det_logits[f] = det_logits[f] + det_t[f].transpose(-1, -2)
            del imgs_t, det_t
            _nv += 1
            imgs_at = torch.rot90(imgs, 1, dims=(-2, -1)).transpose(-1, -2)
            _, det_at = model.encode(imgs_at)
            for f in range(W):
                det_logits[f] = det_logits[f] + torch.rot90(det_at[f].transpose(-1, -2), -1, dims=(-2, -1))
            del imgs_at, det_at
            _nv += 1
            for f in range(W):
                det_logits[f] = det_logits[f] / _nv"""

# ---- (2) Dual-seed ensemble "calibrated" — 6 phép thay ----
_ensemble_replacements = [
    ('    downsample: tuple[int, ...] = (1, 4, 4),\n) -> tuple[np.ndarray, list[tuple[int, int, float, float]]]:', '    downsample: tuple[int, ...] = (1, 4, 4),\n    secondary_model: UNetNodeTransformer | None = None,\n    secondary_edge_weight: float = 0.0,\n    secondary_detection_weight: float = 0.0,\n    secondary_link_mode: str = "raw",\n    secondary_mix_temperature: float = 1.0,\n    secondary_low_margin_max: float = 0.2,\n) -> tuple[np.ndarray, list[tuple[int, int, float, float]]]:'),
    ('            for f in range(W):\n                det_logits[f] = det_logits[f] / _nv\n\n        del imgs', '            for f in range(W):\n                det_logits[f] = det_logits[f] / _nv\n\n        secondary_unet_out = None\n        if secondary_model is not None:\n            secondary_unet_out, secondary_det_logits = secondary_model.encode(imgs)\n\n            if secondary_detection_weight > 0.0:\n                if cfg.det_tta:\n                    _secondary_nv = 1\n                    for dims in [(-1,), (-2,), (-2, -1)]:\n                        secondary_imgs_flip = imgs.flip(dims)\n                        _, secondary_det_flip = secondary_model.encode(secondary_imgs_flip)\n                        for f in range(W):\n                            secondary_det_logits[f] = (\n                                secondary_det_logits[f] + secondary_det_flip[f].flip(dims)\n                            )\n                        del secondary_imgs_flip, secondary_det_flip\n                        _secondary_nv += 1\n                    for _k in (1, 3):\n                        secondary_imgs_rot = torch.rot90(imgs, _k, dims=(-2, -1))\n                        _, secondary_det_rot = secondary_model.encode(secondary_imgs_rot)\n                        for f in range(W):\n                            secondary_det_logits[f] = secondary_det_logits[f] + torch.rot90(\n                                secondary_det_rot[f], -_k, dims=(-2, -1)\n                            )\n                        del secondary_imgs_rot, secondary_det_rot\n                        _secondary_nv += 1\n                    secondary_imgs_t = imgs.transpose(-1, -2)\n                    _, secondary_det_t = secondary_model.encode(secondary_imgs_t)\n                    for f in range(W):\n                        secondary_det_logits[f] = (\n                            secondary_det_logits[f] + secondary_det_t[f].transpose(-1, -2)\n                        )\n                    del secondary_imgs_t, secondary_det_t\n                    _secondary_nv += 1\n                    secondary_imgs_at = torch.rot90(\n                        imgs, 1, dims=(-2, -1)\n                    ).transpose(-1, -2)\n                    _, secondary_det_at = secondary_model.encode(secondary_imgs_at)\n                    for f in range(W):\n                        secondary_det_logits[f] = secondary_det_logits[f] + torch.rot90(\n                            secondary_det_at[f].transpose(-1, -2),\n                            -1,\n                            dims=(-2, -1),\n                        )\n                    del secondary_imgs_at, secondary_det_at\n                    _secondary_nv += 1\n                    for f in range(W):\n                        secondary_det_logits[f] = secondary_det_logits[f] / _secondary_nv\n\n                for f in range(W):\n                    primary_det = det_logits[f]\n                    secondary_det = secondary_det_logits[f]\n                    primary_mean = primary_det.mean()\n                    secondary_mean = secondary_det.mean()\n                    primary_scale = primary_det.float().std(unbiased=False).clamp_min(1e-4)\n                    secondary_scale = secondary_det.float().std(unbiased=False).clamp_min(1e-4)\n                    scale_ratio = (primary_scale / secondary_scale).clamp(0.5, 2.0)\n                    secondary_det_aligned = (\n                        (secondary_det - secondary_mean) * scale_ratio + primary_mean\n                    )\n                    det_logits[f] = (\n                        (1.0 - secondary_detection_weight) * primary_det\n                        + secondary_detection_weight * secondary_det_aligned\n                    )\n\n            del secondary_det_logits\n\n        del imgs'),
    ('            edge_logits_pair = model.predict_edges(\n                unet_feat_src, unet_feat_tgt,\n                p_coords_src * ds_arr_t, p_coords_tgt * ds_arr_t,\n                p_pos_src, p_pos_tgt,\n                p_mask_src, p_mask_tgt,\n            )  # (1, n_src, n_tgt)\n\n            raw = edge_logits_pair[0]', '            edge_logits_pair = model.predict_edges(\n                unet_feat_src, unet_feat_tgt,\n                p_coords_src * ds_arr_t, p_coords_tgt * ds_arr_t,\n                p_pos_src, p_pos_tgt,\n                p_mask_src, p_mask_tgt,\n            )  # (1, n_src, n_tgt)\n\n            if secondary_model is not None:\n                if secondary_unet_out is None:\n                    raise RuntimeError("Secondary model is loaded but its feature map is missing")\n                secondary_feat_src = secondary_model._index_features(\n                    secondary_unet_out[:, f_idx], p_coords_src, p_mask_src,\n                )\n                secondary_feat_tgt = secondary_model._index_features(\n                    secondary_unet_out[:, f_idx + 1], p_coords_tgt, p_mask_tgt,\n                )\n                secondary_logits_pair = secondary_model.predict_edges(\n                    secondary_feat_src, secondary_feat_tgt,\n                    p_coords_src * ds_arr_t, p_coords_tgt * ds_arr_t,\n                    p_pos_src, p_pos_tgt,\n                    p_mask_src, p_mask_tgt,\n                )\n\n                if secondary_link_mode == "raw":\n                    secondary_for_mix = secondary_logits_pair\n                    blend_weight = secondary_edge_weight\n                elif secondary_link_mode in {\n                    "calibrated", "adaptive", "low_margin_consensus"\n                }:\n                    primary_center = edge_logits_pair.mean(dim=1, keepdim=True)\n                    primary_scale = edge_logits_pair.float().std(\n                        dim=1, keepdim=True, unbiased=False\n                    ).clamp_min(1e-4)\n                    secondary_center = secondary_logits_pair.mean(dim=1, keepdim=True)\n                    secondary_scale = secondary_logits_pair.float().std(\n                        dim=1, keepdim=True, unbiased=False\n                    ).clamp_min(1e-4)\n                    secondary_scale_ratio = (primary_scale / secondary_scale).clamp(0.5, 2.0)\n                    secondary_for_mix = (\n                        (secondary_logits_pair - secondary_center) * secondary_scale_ratio\n                        + primary_center\n                    )\n                    if secondary_link_mode == "calibrated":\n                        blend_weight = secondary_edge_weight\n                    elif secondary_link_mode == "adaptive":\n                        if n_src >= 2:\n                            primary_probs = torch.softmax(edge_logits_pair[0], dim=0)\n                            secondary_probs = torch.softmax(secondary_for_mix[0], dim=0)\n                            primary_top2 = torch.topk(primary_probs, k=2, dim=0)\n                            secondary_top2 = torch.topk(secondary_probs, k=2, dim=0)\n                            primary_margin = primary_top2.values[0] - primary_top2.values[1]\n                            secondary_margin = secondary_top2.values[0] - secondary_top2.values[1]\n                            local_weight = (\n                                secondary_edge_weight + secondary_margin - primary_margin\n                            ).clamp(0.15, 0.75)\n                            same_parent = primary_top2.indices[0].eq(\n                                secondary_top2.indices[0]\n                            )\n                            local_weight = torch.where(\n                                same_parent,\n                                torch.maximum(\n                                    local_weight,\n                                    torch.full_like(local_weight, secondary_edge_weight),\n                                ),\n                                local_weight,\n                            )\n                            blend_weight = local_weight.view(1, 1, -1)\n                        else:\n                            blend_weight = secondary_edge_weight\n                    else:\n                        if n_src >= 2:\n                            primary_probs = torch.softmax(edge_logits_pair[0], dim=0)\n                            secondary_probs = torch.softmax(secondary_for_mix[0], dim=0)\n                            primary_top2 = torch.topk(primary_probs, k=2, dim=0)\n                            secondary_top2 = torch.topk(secondary_probs, k=2, dim=0)\n                            primary_margin = primary_top2.values[0] - primary_top2.values[1]\n                            same_parent = primary_top2.indices[0].eq(\n                                secondary_top2.indices[0]\n                            )\n                            uncertainty = (\n                                (secondary_low_margin_max - primary_margin)\n                                / secondary_low_margin_max\n                            ).clamp(0.0, 1.0)\n                            local_weight = secondary_edge_weight * uncertainty\n                            local_weight = torch.where(\n                                same_parent,\n                                local_weight,\n                                torch.zeros_like(local_weight),\n                            )\n                            blend_weight = local_weight.view(1, 1, -1)\n                        else:\n                            blend_weight = 0.0\n                else:\n                    raise ValueError(f"Unsupported secondary link mode: {secondary_link_mode}")\n\n                edge_logits_pair = (\n                    (1.0 - blend_weight) * edge_logits_pair\n                    + blend_weight * secondary_for_mix\n                )\n                if secondary_mix_temperature != 1.0:\n                    mixed_center = edge_logits_pair.mean(dim=1, keepdim=True)\n                    edge_logits_pair = mixed_center + (\n                        edge_logits_pair - mixed_center\n                    ) / secondary_mix_temperature\n\n            raw = edge_logits_pair[0]'),
    ('        del unet_out\n', '        del unet_out\n        if secondary_unet_out is not None:\n            del secondary_unet_out\n'),
    ('    model, window_size, downsample = load_model(weights_path, device)\n    print(', '    model, window_size, downsample = load_model(weights_path, device)\n\n    secondary_model = None\n    secondary_weights_text = os.environ.get("BIOHUB_SECONDARY_WEIGHTS", "").strip()\n    secondary_edge_weight = float(os.environ.get("BIOHUB_SECONDARY_EDGE_WEIGHT", "0"))\n    secondary_detection_weight = float(\n        os.environ.get("BIOHUB_SECONDARY_DETECTION_WEIGHT", "0")\n    )\n    secondary_link_mode = os.environ.get("BIOHUB_SECONDARY_LINK_MODE", "raw").strip()\n    secondary_mix_temperature = float(\n        os.environ.get("BIOHUB_SECONDARY_MIX_TEMPERATURE", "1")\n    )\n    secondary_low_margin_max = float(\n        os.environ.get("BIOHUB_SECONDARY_LOW_MARGIN_MAX", "0.2")\n    )\n    edge_candidate_threshold = float(\n        os.environ.get("BIOHUB_DUAL_SEED_EDGE_THRESHOLD", str(cfg.threshold))\n    )\n    if secondary_weights_text:\n        if not 0.0 < secondary_edge_weight < 1.0:\n            raise ValueError("BIOHUB_SECONDARY_EDGE_WEIGHT must be strictly between 0 and 1")\n        if not 0.0 <= secondary_detection_weight < 1.0:\n            raise ValueError(\n                "BIOHUB_SECONDARY_DETECTION_WEIGHT must be in the half-open interval [0, 1)"\n            )\n        if secondary_link_mode not in {\n            "raw", "calibrated", "adaptive", "low_margin_consensus"\n        }:\n            raise ValueError(\n                "BIOHUB_SECONDARY_LINK_MODE must be raw, calibrated, adaptive, "\n                "or low_margin_consensus"\n            )\n        if not 0.5 <= secondary_mix_temperature <= 2.0:\n            raise ValueError("BIOHUB_SECONDARY_MIX_TEMPERATURE must be in [0.5, 2.0]")\n        if not 0.0 < edge_candidate_threshold < 1.0:\n            raise ValueError("BIOHUB_DUAL_SEED_EDGE_THRESHOLD must be strictly between 0 and 1")\n        if not 0.0 < secondary_low_margin_max <= 1.0:\n            raise ValueError("BIOHUB_SECONDARY_LOW_MARGIN_MAX must be in (0, 1]")\n        secondary_model, secondary_window_size, secondary_downsample = load_model(\n            Path(secondary_weights_text), device,\n        )\n        if secondary_window_size != window_size or secondary_downsample != downsample:\n            raise ValueError(\n                "Primary and secondary models have incompatible inference grids: "\n                f"primary=(window={window_size}, downsample={downsample}), "\n                f"secondary=(window={secondary_window_size}, downsample={secondary_downsample})"\n            )\n        cfg.threshold = edge_candidate_threshold\n        print(\n            f"Secondary model: {secondary_weights_text} | "\n            f"edge weight={secondary_edge_weight:.3f} | "\n            f"detection weight={secondary_detection_weight:.3f} | "\n            f"link mode={secondary_link_mode} | "\n            f"temperature={secondary_mix_temperature:.3f} | "\n            f"low-margin max={secondary_low_margin_max:.3f} | "\n            f"edge threshold={cfg.threshold:.3f}",\n            flush=True,\n        )\n\n    print('),
    ('                unet_batch_size=unet_batch_size,\n                downsample=downsample,\n            )', '                unet_batch_size=unet_batch_size,\n                downsample=downsample,\n                secondary_model=secondary_model,\n                secondary_edge_weight=secondary_edge_weight,\n                secondary_detection_weight=secondary_detection_weight,\n                secondary_link_mode=secondary_link_mode,\n                secondary_mix_temperature=secondary_mix_temperature,\n                secondary_low_margin_max=secondary_low_margin_max,\n            )'),
]

# ---- (3) Retention guard — blend không được làm mất >10% ứng viên ----
_guard_old = """                    det_logits[f] = (
                        (1.0 - secondary_detection_weight) * primary_det
                        + secondary_detection_weight * secondary_det_aligned
                    )"""

_guard_new = """                    blended_det = (
                        (1.0 - secondary_detection_weight) * primary_det
                        + secondary_detection_weight * secondary_det_aligned
                    )
                    primary_candidates = len(_detect_cells_pooled(
                        primary_det[0],
                        int(frame_indices[f]),
                        cfg.det_threshold,
                        pool_k,
                    ))
                    blended_candidates = len(_detect_cells_pooled(
                        blended_det[0],
                        int(frame_indices[f]),
                        cfg.det_threshold,
                        pool_k,
                    ))
                    minimum_retention = float(os.environ.get(
                        "BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION",
                        "0.90",
                    ))
                    candidate_retention = (
                        blended_candidates / primary_candidates
                        if primary_candidates
                        else 1.0
                    )
                    use_primary_detection = bool(
                        primary_candidates > 0
                        and candidate_retention < minimum_retention
                    )
                    det_logits[f] = (
                        primary_det if use_primary_detection else blended_det
                    )
                    if int(frame_indices[f]) not in seen_frames:
                        shard = os.environ.get(
                            "BIOHUB_GPU_SHARD", "single"
                        ).replace("/", "_")
                        guard_log = (
                            Path("/kaggle/working")
                            / f"retention_guard_{shard}.jsonl"
                        )
                        guard_record = {
                            "dataset": ds_path.stem,
                            "frame": int(frame_indices[f]),
                            "primary_candidates": int(primary_candidates),
                            "blended_candidates": int(blended_candidates),
                            "retention": float(candidate_retention),
                            "minimum_retention": float(minimum_retention),
                            "use_primary": bool(use_primary_detection),
                        }
                        with guard_log.open("a") as guard_handle:
                            guard_handle.write(
                                json.dumps(guard_record, sort_keys=True)
                                + "\\n"
                            )
                        if use_primary_detection:
                            print(
                                "BIOHUB_RETENTION_GUARD "
                                + json.dumps(guard_record, sort_keys=True),
                                flush=True,
                            )"""

# ---- (4) Bidirectional harmonic fusion + coordinate manifest ----
_bi_old = '            edge_logits_pair = model.predict_edges(\n                unet_feat_src, unet_feat_tgt,\n                p_coords_src * ds_arr_t, p_coords_tgt * ds_arr_t,\n                p_pos_src, p_pos_tgt,\n                p_mask_src, p_mask_tgt,\n            )  # (1, n_src, n_tgt)\n\n            if secondary_model is not None:\n'

_bi_new = '            edge_logits_pair = model.predict_edges(\n                unet_feat_src, unet_feat_tgt,\n                p_coords_src * ds_arr_t, p_coords_tgt * ds_arr_t,\n                p_pos_src, p_pos_tgt,\n                p_mask_src, p_mask_tgt,\n            )  # (1, n_src, n_tgt)\n\n            _bidirectional_weight = float(\n                os.environ.get("BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT", "0")\n            )\n            if _bidirectional_weight > 0.0:\n                reverse_logits_native = model.predict_edges(\n                    unet_feat_tgt, unet_feat_src,\n                    p_coords_tgt * ds_arr_t, p_coords_src * ds_arr_t,\n                    p_pos_tgt, p_pos_src,\n                    p_mask_tgt, p_mask_src,\n                )  # (1, n_tgt, n_src)\n                reverse_logits_pair = reverse_logits_native.transpose(1, 2)\n\n                forward_center = edge_logits_pair.mean(dim=1, keepdim=True)\n                forward_scale = edge_logits_pair.float().std(\n                    dim=1, keepdim=True, unbiased=False\n                ).clamp_min(1e-4)\n                reverse_center = reverse_logits_pair.mean(dim=1, keepdim=True)\n                reverse_scale = reverse_logits_pair.float().std(\n                    dim=1, keepdim=True, unbiased=False\n                ).clamp_min(1e-4)\n                reverse_scale_ratio = (forward_scale / reverse_scale).clamp(0.5, 2.0)\n                reverse_scale_ratio = reverse_scale_ratio.to(reverse_logits_pair.dtype)\n                reverse_aligned = (\n                    (reverse_logits_pair - reverse_center) * reverse_scale_ratio\n                    + forward_center\n                )\n                forward_prob = torch.softmax(edge_logits_pair.float(), dim=1).clamp_min(1e-8)\n                reverse_prob = torch.softmax(reverse_aligned.float(), dim=1).clamp_min(1e-8)\n                harmonic_prob = 1.0 / (\n                    (1.0 - _bidirectional_weight) / forward_prob\n                    + _bidirectional_weight / reverse_prob\n                )\n                harmonic_prob = harmonic_prob / harmonic_prob.sum(\n                    dim=1, keepdim=True\n                ).clamp_min(1e-8)\n                harmonic_logits = torch.log(harmonic_prob.clamp_min(1e-8))\n                harmonic_center = harmonic_logits.mean(dim=1, keepdim=True)\n                harmonic_scale = harmonic_logits.std(\n                    dim=1, keepdim=True, unbiased=False\n                ).clamp_min(1e-4)\n                harmonic_scale_ratio = (forward_scale / harmonic_scale).clamp(0.5, 2.0)\n                edge_logits_pair = (\n                    (harmonic_logits - harmonic_center) * harmonic_scale_ratio\n                    + forward_center\n                ).to(reverse_aligned.dtype)\n                del (\n                    reverse_logits_native,\n                    reverse_logits_pair,\n                    reverse_aligned,\n                    forward_prob,\n                    reverse_prob,\n                    harmonic_prob,\n                    harmonic_logits,\n                )\n            if secondary_model is not None:\n'

_coordinate_manifest_old = '    coords = coords.astype(np.int16)\n    return coords, all_edges'

_coordinate_manifest_new = '    coords = coords.astype(np.int16)\n\n    _coordinate_manifest_arm = os.environ.get(\n        "BIOHUB_DIAGNOSTIC_ARM", ""\n    ).strip()\n    if _coordinate_manifest_arm:\n        import hashlib as _coordinate_hashlib\n\n        _coordinate_shard = os.environ.get(\n            "BIOHUB_GPU_SHARD", "single"\n        ).replace("/", "_")\n        _coordinate_array = np.ascontiguousarray(\n            coords.astype("<i2", copy=False)\n        )\n        _coordinate_frame_counts = [\n            [int(_coordinate_t), int((_coordinate_array[:, 0] == _coordinate_t).sum())]\n            for _coordinate_t in np.unique(_coordinate_array[:, 0])\n        ]\n        _coordinate_record = {\n            "columns": ["t", "z", "y", "x"],\n            "coordinate_sha256": _coordinate_hashlib.sha256(\n                _coordinate_array.tobytes(order="C")\n            ).hexdigest(),\n            "dataset": ds_path.stem,\n            "dtype": "<i2",\n            "frame_counts": _coordinate_frame_counts,\n            "rows": int(len(_coordinate_array)),\n            "stage": "post_detection_pre_graph_pre_ilp",\n        }\n        _coordinate_manifest_path = (\n            Path("/kaggle/working")\n            / f"detector_coordinates_{_coordinate_manifest_arm}_"\n            f"{_coordinate_shard}.jsonl"\n        )\n        with _coordinate_manifest_path.open("a") as _coordinate_handle:\n            _coordinate_handle.write(\n                json.dumps(_coordinate_record, sort_keys=True) + "\\n"\n            )\n\n    return coords, all_edges'

# ---- (5) EDGE_FEATURE_TTA (model chính) ----
_et_old = '        if cfg.det_tta:\n            _nv = 1\n            for dims in [(-1,), (-2,), (-2, -1)]:\n                imgs_flip = imgs.flip(dims)\n                _, det_flip = model.encode(imgs_flip)\n                for f in range(W):\n                    det_logits[f] = det_logits[f] + det_flip[f].flip(dims)\n                del imgs_flip, det_flip\n                _nv += 1\n            for _k in (1, 3):\n                imgs_rot = torch.rot90(imgs, _k, dims=(-2, -1))\n                _, det_rot = model.encode(imgs_rot)\n                for f in range(W):\n                    det_logits[f] = det_logits[f] + torch.rot90(det_rot[f], -_k, dims=(-2, -1))\n                del imgs_rot, det_rot\n                _nv += 1\n            imgs_t = imgs.transpose(-1, -2)\n            _, det_t = model.encode(imgs_t)\n            for f in range(W):\n                det_logits[f] = det_logits[f] + det_t[f].transpose(-1, -2)\n            del imgs_t, det_t\n            _nv += 1\n            imgs_at = torch.rot90(imgs, 1, dims=(-2, -1)).transpose(-1, -2)\n            _, det_at = model.encode(imgs_at)\n            for f in range(W):\n                det_logits[f] = det_logits[f] + torch.rot90(det_at[f].transpose(-1, -2), -1, dims=(-2, -1))\n            del imgs_at, det_at\n            _nv += 1\n            for f in range(W):\n                det_logits[f] = det_logits[f] / _nv\n'

_et_new = "        if cfg.det_tta:\n            _edge_tta = os.environ.get('BIOHUB_EDGE_FEATURE_TTA', '0') != '0'\n            _unet_acc = unet_out.clone() if _edge_tta else None\n            _nv = 1\n            for dims in [(-1,), (-2,), (-2, -1)]:\n                imgs_flip = imgs.flip(dims)\n                _u_flip, det_flip = model.encode(imgs_flip)\n                for f in range(W):\n                    det_logits[f] = det_logits[f] + det_flip[f].flip(dims)\n                if _edge_tta:\n                    _unet_acc = _unet_acc + _u_flip.flip(dims)\n                del imgs_flip, det_flip, _u_flip\n                _nv += 1\n            for _k in (1, 3):\n                imgs_rot = torch.rot90(imgs, _k, dims=(-2, -1))\n                _u_rot, det_rot = model.encode(imgs_rot)\n                for f in range(W):\n                    det_logits[f] = det_logits[f] + torch.rot90(det_rot[f], -_k, dims=(-2, -1))\n                if _edge_tta:\n                    _unet_acc = _unet_acc + torch.rot90(_u_rot, -_k, dims=(-2, -1))\n                del imgs_rot, det_rot, _u_rot\n                _nv += 1\n            imgs_t = imgs.transpose(-1, -2)\n            _u_t, det_t = model.encode(imgs_t)\n            for f in range(W):\n                det_logits[f] = det_logits[f] + det_t[f].transpose(-1, -2)\n            if _edge_tta:\n                _unet_acc = _unet_acc + _u_t.transpose(-1, -2)\n            del imgs_t, det_t, _u_t\n            _nv += 1\n            imgs_at = torch.rot90(imgs, 1, dims=(-2, -1)).transpose(-1, -2)\n            _u_at, det_at = model.encode(imgs_at)\n            for f in range(W):\n                det_logits[f] = det_logits[f] + torch.rot90(det_at[f].transpose(-1, -2), -1, dims=(-2, -1))\n            if _edge_tta:\n                _unet_acc = _unet_acc + torch.rot90(_u_at.transpose(-1, -2), -1, dims=(-2, -1))\n            del imgs_at, det_at, _u_at\n            _nv += 1\n            for f in range(W):\n                det_logits[f] = det_logits[f] / _nv\n            if _edge_tta:\n                if _unet_acc.shape != unet_out.shape:\n                    raise RuntimeError('EDGE-TTA SHAPE MISMATCH: %s vs %s'\n                                       % (tuple(_unet_acc.shape), tuple(unet_out.shape)))\n                _delta = float((_unet_acc / _nv - unet_out).abs().mean())\n                if _delta == 0.0:\n                    raise RuntimeError('EDGE-TTA NO-OP: averaged features bit-identical to the '\n                                       'single-pass features, so the augmented encodes '\n                                       'contributed nothing and this arm would read as a '\n                                       'false null')\n                unet_out = _unet_acc / _nv\n                print('EDGE_TTA_ACTIVE views=', _nv, 'mean_abs_feat_delta=', round(_delta, 6), flush=True)\n                del _unet_acc\n"

# ---- (6) SECONDARY_EDGE_TTA (model phụ, w=0.75) ----
_secondary_tta_old = '        secondary_unet_out, secondary_det_logits = secondary_model.encode(imgs)\n\n            if secondary_detection_weight > 0.0:\n                if cfg.det_tta:\n                    _secondary_nv = 1\n                    for dims in [(-1,), (-2,), (-2, -1)]:\n                        secondary_imgs_flip = imgs.flip(dims)\n                        _, secondary_det_flip = secondary_model.encode(secondary_imgs_flip)\n                        for f in range(W):\n                            secondary_det_logits[f] = (\n                                secondary_det_logits[f] + secondary_det_flip[f].flip(dims)\n                            )\n                        del secondary_imgs_flip, secondary_det_flip\n                        _secondary_nv += 1\n                    for _k in (1, 3):\n                        secondary_imgs_rot = torch.rot90(imgs, _k, dims=(-2, -1))\n                        _, secondary_det_rot = secondary_model.encode(secondary_imgs_rot)\n                        for f in range(W):\n                            secondary_det_logits[f] = secondary_det_logits[f] + torch.rot90(\n                                secondary_det_rot[f], -_k, dims=(-2, -1)\n                            )\n                        del secondary_imgs_rot, secondary_det_rot\n                        _secondary_nv += 1\n                    secondary_imgs_t = imgs.transpose(-1, -2)\n                    _, secondary_det_t = secondary_model.encode(secondary_imgs_t)\n                    for f in range(W):\n                        secondary_det_logits[f] = (\n                            secondary_det_logits[f] + secondary_det_t[f].transpose(-1, -2)\n                        )\n                    del secondary_imgs_t, secondary_det_t\n                    _secondary_nv += 1\n                    secondary_imgs_at = torch.rot90(\n                        imgs, 1, dims=(-2, -1)\n                    ).transpose(-1, -2)\n                    _, secondary_det_at = secondary_model.encode(secondary_imgs_at)\n                    for f in range(W):\n                        secondary_det_logits[f] = secondary_det_logits[f] + torch.rot90(\n                            secondary_det_at[f].transpose(-1, -2),\n                            -1,\n                            dims=(-2, -1),\n                        )\n                    del secondary_imgs_at, secondary_det_at\n                    _secondary_nv += 1\n                    for f in range(W):\n                        secondary_det_logits[f] = secondary_det_logits[f] / _secondary_nv\n\n                for f in range(W):'

_secondary_tta_new = '        secondary_unet_out, secondary_det_logits = secondary_model.encode(imgs)\n            _secondary_edge_tta = os.environ.get(\n                "BIOHUB_SECONDARY_EDGE_FEATURE_TTA", "0"\n            ) != "0"\n            _secondary_unet_acc = (\n                secondary_unet_out.clone() if _secondary_edge_tta else None\n            )\n\n            if secondary_detection_weight > 0.0:\n                if cfg.det_tta:\n                    _secondary_nv = 1\n                    for dims in [(-1,), (-2,), (-2, -1)]:\n                        secondary_imgs_flip = imgs.flip(dims)\n                        _secondary_u_flip, secondary_det_flip = secondary_model.encode(\n                            secondary_imgs_flip\n                        )\n                        for f in range(W):\n                            secondary_det_logits[f] = (\n                                secondary_det_logits[f] + secondary_det_flip[f].flip(dims)\n                            )\n                        if _secondary_edge_tta:\n                            _secondary_unet_acc = _secondary_unet_acc + _secondary_u_flip.flip(dims)\n                        del secondary_imgs_flip, secondary_det_flip, _secondary_u_flip\n                        _secondary_nv += 1\n                    for _k in (1, 3):\n                        secondary_imgs_rot = torch.rot90(imgs, _k, dims=(-2, -1))\n                        _secondary_u_rot, secondary_det_rot = secondary_model.encode(\n                            secondary_imgs_rot\n                        )\n                        for f in range(W):\n                            secondary_det_logits[f] = secondary_det_logits[f] + torch.rot90(\n                                secondary_det_rot[f], -_k, dims=(-2, -1)\n                            )\n                        if _secondary_edge_tta:\n                            _secondary_unet_acc = _secondary_unet_acc + torch.rot90(\n                                _secondary_u_rot, -_k, dims=(-2, -1)\n                            )\n                        del secondary_imgs_rot, secondary_det_rot, _secondary_u_rot\n                        _secondary_nv += 1\n                    secondary_imgs_t = imgs.transpose(-1, -2)\n                    _secondary_u_t, secondary_det_t = secondary_model.encode(secondary_imgs_t)\n                    for f in range(W):\n                        secondary_det_logits[f] = (\n                            secondary_det_logits[f] + secondary_det_t[f].transpose(-1, -2)\n                        )\n                    if _secondary_edge_tta:\n                        _secondary_unet_acc = _secondary_unet_acc + _secondary_u_t.transpose(-1, -2)\n                    del secondary_imgs_t, secondary_det_t, _secondary_u_t\n                    _secondary_nv += 1\n                    secondary_imgs_at = torch.rot90(\n                        imgs, 1, dims=(-2, -1)\n                    ).transpose(-1, -2)\n                    _secondary_u_at, secondary_det_at = secondary_model.encode(\n                        secondary_imgs_at\n                    )\n                    for f in range(W):\n                        secondary_det_logits[f] = secondary_det_logits[f] + torch.rot90(\n                            secondary_det_at[f].transpose(-1, -2),\n                            -1,\n                            dims=(-2, -1),\n                        )\n                    if _secondary_edge_tta:\n                        _secondary_unet_acc = _secondary_unet_acc + torch.rot90(\n                            _secondary_u_at.transpose(-1, -2), -1, dims=(-2, -1)\n                        )\n                    del secondary_imgs_at, secondary_det_at, _secondary_u_at\n                    _secondary_nv += 1\n                    for f in range(W):\n                        secondary_det_logits[f] = secondary_det_logits[f] / _secondary_nv\n                    if _secondary_edge_tta:\n                        if _secondary_unet_acc.shape != secondary_unet_out.shape:\n                            raise RuntimeError("SECONDARY_EDGE_TTA_SHAPE_MISMATCH")\n                        _secondary_delta = float(\n                            (_secondary_unet_acc / _secondary_nv - secondary_unet_out).abs().mean()\n                        )\n                        if _secondary_delta == 0.0:\n                            raise RuntimeError("SECONDARY_EDGE_TTA_NO_OP")\n                        _secondary_edge_tta_weight = float(os.environ.get(\n                            "BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT", "0.75"\n                        ))\n                        if not 0.0 < _secondary_edge_tta_weight <= 1.0:\n                            raise RuntimeError("SECONDARY_EDGE_TTA_BAD_WEIGHT")\n                        _secondary_tta_mean = _secondary_unet_acc / _secondary_nv\n                        secondary_unet_out = (\n                            (1.0 - _secondary_edge_tta_weight) * secondary_unet_out\n                            + _secondary_edge_tta_weight * _secondary_tta_mean\n                        )\n                        print(\n                            "SECONDARY_EDGE_TTA_ACTIVE views=",\n                            _secondary_nv,\n                            "weight=",\n                            _secondary_edge_tta_weight,\n                            "mean_abs_feat_delta=",\n                            round(_secondary_delta, 6),\n                            flush=True,\n                        )\n                        del _secondary_unet_acc\n\n                for f in range(W):'

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
def list_test_stems() -> list[str]:
    if not TEST_DIR.exists():
        raise FileNotFoundError(f"Test directory does not exist: {TEST_DIR}")
    stems = sorted(path.name[:-5] for path in TEST_DIR.iterdir() if path.name.endswith(".zarr"))
    if not stems:
        raise FileNotFoundError(f"No test .zarr files found in {TEST_DIR}")
    return stems


test_stems = list_test_stems()
print(f"Found {len(test_stems)} test videos")
print(test_stems[:10])

splits_path = REPO_DIR / "kaggle_test_splits_50ep.json"
splits_path.parent.mkdir(parents=True, exist_ok=True)
splits_path.write_text(json.dumps([{"split": 0, "train": [], "test": test_stems}], indent=2))

predict_cmd = [
    sys.executable,
    "scripts/predict_unet_transformer.py",
    "--data-dir",
    str(TEST_DIR),
    "--splits",
    str(splits_path.name),
    "--split",
    "0",
    "--weights",
    WEIGHTS_RELATIVE,
    "--unet-batch-size",
    str(UNET_BATCH_SIZE),
    "--det-threshold",
    str(DET_THRESHOLD),
    "--ilp-edge-weight",
    str(ILP_EDGE_WEIGHT),
    "--ilp-appearance-weight",
    str(ILP_APPEARANCE_WEIGHT),
    "--ilp-disappearance-weight",
    str(ILP_DISAPPEARANCE_WEIGHT),
    "--ilp-division-weight",
    str(ILP_DIVISION_WEIGHT),
]
if USE_ILP:
    predict_cmd.append("--use-ilp")
if SLICE:
    predict_cmd.extend(["--slice", SLICE])

def _visible_cuda_tokens(count: int) -> list[str]:
    raw = os.environ.get("CUDA_VISIBLE_DEVICES", "").strip()
    if raw and raw != "-1":
        tokens = [token.strip() for token in raw.split(",") if token.strip()]
        if len(tokens) < count:
            raise RuntimeError(
                f"torch reports {count} CUDA devices but CUDA_VISIBLE_DEVICES={raw!r}"
            )
        return tokens[:count]
    return [str(index) for index in range(count)]


def _prediction_dir_for_method(method: str) -> Path:
    matches = sorted((REPO_DIR / "predictions").glob(f"*/{method}/split_0"))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one prediction directory for {method!r}, found {matches}"
        )
    return matches[0]


def _wait_for_prediction_shards(
    processes: dict[int, subprocess.Popen],
    commands: dict[int, list[str]],
) -> None:
    while processes:
        failed: tuple[int, int] | None = None
        for shard_index, process in list(processes.items()):
            return_code = process.poll()
            if return_code is None:
                continue
            del processes[shard_index]
            if return_code != 0:
                failed = (shard_index, return_code)
                break
        if failed is None:
            if processes:
                time.sleep(1.0)
            continue

        failed_index, failed_code = failed
        for process in processes.values():
            if process.poll() is None:
                process.terminate()
        for process in processes.values():
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise subprocess.CalledProcessError(failed_code, commands[failed_index])


def _merge_prediction_shards(worker_count: int) -> Path:
    shard_dirs: list[Path] = []
    seen: set[str] = set()
    expected_all = set(test_stems)

    for shard_index in range(worker_count):
        shard_method = f"{METHOD}_gpu{shard_index}"
        shard_dir = _prediction_dir_for_method(shard_method)
        expected = set(test_stems[shard_index::worker_count])
        shard_paths = sorted(shard_dir.glob("*.geff"))
        found = {path.stem for path in shard_paths}
        if found != expected:
            raise RuntimeError(
                f"GPU shard {shard_index} output mismatch: "
                f"missing={sorted(expected - found)}, extra={sorted(found - expected)}"
            )
        overlap = seen & found
        if overlap:
            raise RuntimeError(f"Duplicate datasets across GPU shards: {sorted(overlap)}")
        seen.update(found)
        shard_dirs.append(shard_dir)

    if seen != expected_all:
        raise RuntimeError(
            f"Merged GPU shards do not cover the test set: "
            f"missing={sorted(expected_all - seen)}, extra={sorted(seen - expected_all)}"
        )

    username_roots = {shard_dir.parents[1] for shard_dir in shard_dirs}
    if len(username_roots) != 1:
        raise RuntimeError(f"GPU shards used inconsistent prediction roots: {username_roots}")
    import shutil as _shutil

    final_root = next(iter(username_roots)) / METHOD
    final_dir = final_root / "split_0"
    staging_dir = final_root / "split_0_dual_gpu_staging"
    if staging_dir.exists():
        if staging_dir.is_dir():
            _shutil.rmtree(staging_dir)
        else:
            staging_dir.unlink()
    staging_dir.mkdir(parents=True, exist_ok=False)

    for shard_dir in shard_dirs:
        for source in sorted(shard_dir.glob("*.geff")):
            destination = staging_dir / source.name
            if destination.exists():
                raise RuntimeError(f"Refusing to overwrite duplicate merged output: {destination}")
            _shutil.move(str(source), str(destination))

    merged = {path.stem for path in staging_dir.glob("*.geff")}
    if merged != expected_all:
        raise RuntimeError(
            f"Staged prediction directory failed verification: "
            f"missing={sorted(expected_all - merged)}, extra={sorted(merged - expected_all)}"
        )

    if final_dir.exists():
        if final_dir.is_dir():
            _shutil.rmtree(final_dir)
        else:
            final_dir.unlink()
    staging_dir.rename(final_dir)
    for shard_dir in shard_dirs:
        _shutil.rmtree(shard_dir.parent)
    print(f"Merged {len(merged)} prediction graphs into {final_dir}")
    return final_dir


start_time = time.time()
available_gpu_count = _torch.cuda.device_count()
worker_count = min(2, available_gpu_count, len(test_stems))

if worker_count >= 2 and not SLICE:
    cuda_tokens = _visible_cuda_tokens(worker_count)
    processes: dict[int, subprocess.Popen] = {}
    commands: dict[int, list[str]] = {}
    print(f"Launching {worker_count} independent video shards on CUDA devices {cuda_tokens}")
    for shard_index in range(worker_count):
        shard_method = f"{METHOD}_gpu{shard_index}"
        shard_cmd = [
            *predict_cmd,
            "--method",
            shard_method,
            "--slice",
            f"{shard_index}::{worker_count}",
        ]
        shard_env = {**os.environ, "PYTHONPATH": "src"}
        shard_env["CUDA_VISIBLE_DEVICES"] = cuda_tokens[shard_index]
        shard_env["BIOHUB_GPU_SHARD"] = f"{shard_index}/{worker_count}"
        print(
            f"GPU shard {shard_index}: CUDA_VISIBLE_DEVICES={cuda_tokens[shard_index]} | "
            + " ".join(shard_cmd),
            flush=True,
        )
        commands[shard_index] = shard_cmd
        processes[shard_index] = subprocess.Popen(
            shard_cmd,
            cwd=REPO_DIR,
            env=shard_env,
        )
    _wait_for_prediction_shards(processes, commands)
    _merge_prediction_shards(worker_count)
else:
    reason = "SLICE is active" if SLICE else f"only {available_gpu_count} CUDA device(s) available"
    print(f"Using single-process prediction because {reason}.")
    print(" ".join(predict_cmd))
    subprocess.run(
        predict_cmd,
        cwd=REPO_DIR,
        env={**os.environ, "PYTHONPATH": "src"},
        check=True,
    )

predict_seconds = time.time() - start_time
print(f"Prediction completed in {predict_seconds / 60:.2f} minutes")


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
