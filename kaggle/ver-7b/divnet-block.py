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
