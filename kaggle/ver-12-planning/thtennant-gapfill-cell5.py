import tracksdata as td
import numpy as np
import blosc2
from scipy.optimize import linear_sum_assignment
from scipy.spatial import cKDTree

SUBMISSION_COLUMNS = ["dataset", "row_type", "node_id", "t", "z", "y", "x", "source_id", "target_id"]
CSV_COLUMNS = ["id", *SUBMISSION_COLUMNS]
VOXEL_SCALE_UM = (1.625, 0.40625, 0.40625)

import time as _time
import traceback as _traceback

# Runtime guard. Kaggle reruns this notebook on a hidden test set larger than
# the visible one, so the repair loop watches the wall clock: once the kernel
# has run for REPAIR_DEADLINE_S the remaining datasets are processed with the
# optional repair stages switched off, and a dataset whose repair raises is
# written from its ILP graph instead of failing the whole kernel.
KERNEL_START_TS = float(os.environ.get("BIOHUB_KERNEL_START_TS", str(_time.time())))
REPAIR_DEADLINE_S = float(os.environ.get("BIOHUB_REPAIR_DEADLINE_S", "27000"))
FRAME_CACHE_MAX_FRAMES = int(os.environ.get("BIOHUB_FRAME_CACHE_MAX_FRAMES", "48"))
_deadline_degraded = False


def _frame_cache_trim(frame_cache: dict[int, np.ndarray]) -> None:
    while len(frame_cache) > max(1, FRAME_CACHE_MAX_FRAMES):
        frame_cache.pop(next(iter(frame_cache)))


def _deadline_degrade() -> None:
    global _deadline_degraded, OUTPUT_MOTION_RELINK, OUTPUT_GAP_CLOSE, OUTPUT_GAP2_RECOVERY
    global OUTPUT_SAFE_DIVISIONS, OUTPUT_LINEFIT_SMOOTH
    _deadline_degraded = True
    OUTPUT_MOTION_RELINK = False
    OUTPUT_GAP_CLOSE = False
    OUTPUT_GAP2_RECOVERY = False
    OUTPUT_SAFE_DIVISIONS = False
    OUTPUT_LINEFIT_SMOOTH = False
    print(
        f"DEADLINE: {_time.time() - KERNEL_START_TS:.0f}s since kernel start exceeds"
        f" {REPAIR_DEADLINE_S:.0f}s; remaining datasets get edge filtering and"
        " short-track filtering only",
        flush=True,
    )


def fallback_output_graph(
    nodes_by_id: dict[int, dict[str, object]],
    raw_edges: list[dict[str, object]],
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]], dict[str, int]]:
    """Cheapest valid graph from the ILP output: consecutive-frame edges within
    OUTPUT_EDGE_MAX_UM, one parent per node, at most two children per node."""
    stats: dict[str, int] = {"raw_edges": len(raw_edges), "repair_fallback": 1}
    edges: list[dict[str, object]] = []
    for edge in raw_edges:
        source = nodes_by_id.get(int(edge["source_id"]))
        target = nodes_by_id.get(int(edge["target_id"]))
        if source is None or target is None:
            continue
        if int(target["t"]) != int(source["t"]) + 1:
            continue
        edge["distance_um"] = edge_distance_um(source, target)
        if OUTPUT_EDGE_MAX_UM > 0 and float(edge["distance_um"]) > OUTPUT_EDGE_MAX_UM:
            continue
        edges.append(edge)
    best_by_target: dict[int, dict[str, object]] = {}
    for edge in edges:
        target_id = int(edge["target_id"])
        prev = best_by_target.get(target_id)
        if prev is None or edge_sort_key(edge) > edge_sort_key(prev):
            best_by_target[target_id] = edge
    by_source: dict[int, list[dict[str, object]]] = {}
    for edge in best_by_target.values():
        by_source.setdefault(int(edge["source_id"]), []).append(edge)
    edges = []
    for source_edges in by_source.values():
        edges.extend(sorted(source_edges, key=edge_sort_key, reverse=True)[:2])
    incident = {int(e["source_id"]) for e in edges} | {int(e["target_id"]) for e in edges}
    kept = {node_id: node for node_id, node in nodes_by_id.items() if node_id in incident}
    return (kept or nodes_by_id), edges, stats


def graph_from_geff(path: Path):
    graph = td.graph.IndexedRXGraph.from_geff(path)
    return graph[0] if isinstance(graph, tuple) else graph


def edge_distance_um(source: dict[str, object], target: dict[str, object]) -> float:
    dz = (float(source["z"]) - float(target["z"])) * VOXEL_SCALE_UM[0]
    dy = (float(source["y"]) - float(target["y"])) * VOXEL_SCALE_UM[1]
    dx = (float(source["x"]) - float(target["x"])) * VOXEL_SCALE_UM[2]
    return math.sqrt(dz * dz + dy * dy + dx * dx)


def point_distance_um(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    dz = (a[0] - b[0]) * VOXEL_SCALE_UM[0]
    dy = (a[1] - b[1]) * VOXEL_SCALE_UM[1]
    dx = (a[2] - b[2]) * VOXEL_SCALE_UM[2]
    return math.sqrt(dz * dz + dy * dy + dx * dx)


def node_point(node: dict[str, object]) -> tuple[float, float, float]:
    return (float(node["z"]), float(node["y"]), float(node["x"]))


def edge_sort_key(edge: dict[str, object]) -> tuple[float, float]:
    prob = edge.get("edge_prob")
    prob_value = float(prob) if prob is not None else 0.0
    return prob_value, -float(edge["distance_um"])


def _next_node_id(nodes_by_id: dict[int, dict[str, object]]) -> int:
    return max(nodes_by_id) + 1 if nodes_by_id else 1



def read_test_frame(dataset: str, t: int, frame_cache: dict[int, np.ndarray]) -> np.ndarray:
    if t in frame_cache:
        return frame_cache[t]
    zarr_path = TEST_DIR / f"{dataset}.zarr"
    meta = json.loads((zarr_path / "0" / "zarr.json").read_text())
    shape = tuple(int(v) for v in meta["shape"])
    dtype = np.dtype(meta["data_type"])
    frame_shape = shape[1:]
    chunk_path = zarr_path / "0" / "c" / str(t) / "0" / "0" / "0"
    try:
        raw = chunk_path.read_bytes()
        arr = np.frombuffer(blosc2.decompress(raw), dtype=dtype)
        if arr.size == int(np.prod(frame_shape)):
            frame = arr.reshape(frame_shape).copy()
            frame_cache[t] = frame
            _frame_cache_trim(frame_cache)
            return frame
    except Exception:
        pass
    import zarr
    frame = np.asarray(zarr.open(zarr_path / "0", mode="r")[t])
    frame_cache[t] = frame
    _frame_cache_trim(frame_cache)
    return frame


def refine_synthetic_midpoint(
    dataset: str | None,
    t: int,
    midpoint: tuple[float, float, float],
    frame_cache: dict[int, np.ndarray],
    stats: dict[str, int],
) -> tuple[float, float, float]:
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
            stats["gap_refine_failed"] += 1
            return midpoint
        baseline = float(np.percentile(patch, 20.0))
        weights = np.maximum(patch - baseline, 0.0)
        total = float(weights.sum())
        if total <= 0:
            stats["gap_refine_failed"] += 1
            return midpoint
        zz = np.arange(z0, z1, dtype=np.float64)[:, None, None]
        yy = np.arange(y0, y1, dtype=np.float64)[None, :, None]
        xx = np.arange(x0, x1, dtype=np.float64)[None, None, :]
        refined = (
            float((weights * zz).sum() / total),
            float((weights * yy).sum() / total),
            float((weights * xx).sum() / total),
        )
        if point_distance_um(refined, midpoint) > GAP_REFINE_MAX_SHIFT_UM:
            stats["gap_refine_rejected_shift"] += 1
            return midpoint
        stats["gap_refined_synthetic"] += 1
        return refined
    except Exception:
        stats["gap_refine_failed"] += 1
        return midpoint



def _dc_pool_frame_xy(volume: np.ndarray, factor: int) -> np.ndarray:
    if factor <= 1:
        return volume.astype(np.float32, copy=False)
    z, y, x = volume.shape
    y2 = (y // factor) * factor
    x2 = (x // factor) * factor
    cropped = volume[:, :y2, :x2].astype(np.float32, copy=False)
    return cropped.reshape(z, y2 // factor, factor, x2 // factor, factor).mean(axis=(2, 4))


def _dc_normalize_dynamic_range(volume: np.ndarray, cfg: object) -> np.ndarray:
    vol = np.asarray(volume, dtype=np.float32)
    lo = float(np.percentile(vol, float(getattr(cfg, "norm_lo_pct", 50.0))))
    hi = float(np.percentile(vol, float(getattr(cfg, "norm_hi_pct", 99.5))))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        return np.zeros_like(vol, dtype=np.float32)
    ratio = (vol - lo) / (hi - lo)
    return np.clip(
        ratio,
        float(getattr(cfg, "norm_clip_lo", -0.5)),
        float(getattr(cfg, "norm_clip_hi", 6.0)),
    ).astype(np.float32)


def _dc_manifest_weight_paths(manifest_path: Path) -> list[Path]:
    if not manifest_path.exists():
        return []
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:
        print("Could not read DeepCenter manifest:", manifest_path, type(exc).__name__, exc)
        return []
    root = manifest_path.parent
    sections: list[dict[str, object]] = []
    for section in [
        manifest.get("model", {}),
        manifest.get("models", {}).get("full_frame_center", {}) if isinstance(manifest.get("models", {}), dict) else {},
        manifest.get("full_frame_center", {}),
    ]:
        if isinstance(section, dict):
            sections.append(section)
    candidates: list[Path] = []
    for section in sections:
        for key in ("weight_path", "path"):
            rel = section.get(key)
            if isinstance(rel, str) and rel:
                candidates.append(root / rel)
        for key in ("last_checkpoint", "best_checkpoint"):
            item = section.get(key)
            if isinstance(item, dict):
                rel = item.get("path")
                if isinstance(rel, str) and rel:
                    candidates.append(root / rel)
    for name in ("checkpoint_last.pt", "best.pt", "last.pt"):
        candidates.append(root / "weights" / "full_frame_center" / name)
        candidates.append(root / name)
    candidates.append(root / DEEPCENTER_RELATIVE)
    return candidates


def _dc_checkpoint_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("BIOHUB_DEEPCENTER_CHECKPOINT", DEEPCENTER_CHECKPOINT_DEFAULT).strip()
    if explicit:
        candidates.append(Path(explicit))
    manifest_explicit = os.environ.get("BIOHUB_DEEPCENTER_MANIFEST", DEEPCENTER_MANIFEST_DEFAULT).strip()
    if manifest_explicit:
        candidates.extend(_dc_manifest_weight_paths(Path(manifest_explicit)))

    input_root = Path("/kaggle/input")
    preferred_dirs = [
        Path("/kaggle/input/biohub-deepcenter-unet3d-center-prior-v1"),
        Path("/kaggle/input/datasets/pilkwang/biohub-deepcenter-unet3d-center-prior-v1"),
    ]
    for directory in preferred_dirs:
        candidates.extend(_dc_manifest_weight_paths(directory / "ARTIFACT_MANIFEST.json"))
        for name in ("checkpoint_last.pt", "best.pt", "last.pt"):
            candidates.append(directory / "weights" / "full_frame_center" / name)
            candidates.append(directory / name)
    if input_root.exists() and not any(path.is_file() for path in candidates):
        # Three recursive walks of /kaggle/input cost ~370 s on the visible
        # run. The explicit checkpoint path is checksum-pinned by the setup
        # cell, so only walk when none of the known paths exist.
        for name in ("checkpoint_last.pt", "best.pt", "last.pt"):
            candidates.extend(sorted(input_root.glob(f"**/full_frame_center/**/{name}")))

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
    class _DCConvBlock3d(torch.nn.Module):
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

        def forward(self, x):
            return self.block(x)


    class _DCDeepCenterUNet3D(torch.nn.Module):
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

        def forward(self, x):
            e1 = self.enc1(x)
            e2 = self.enc2(self.down1(e1))
            e3 = self.enc3(self.down2(e2))
            b = self.bottleneck(self.down3(e3))
            d3 = self.dec3(torch.cat([self.up3(b), e3], dim=1))
            d2 = self.dec2(torch.cat([self.up2(d3), e2], dim=1))
            d1 = self.dec1(torch.cat([self.up1(d2), e1], dim=1))
            return self.head(d1)
else:
    _DCConvBlock3d = None
    _DCDeepCenterUNet3D = None

def load_deepcenter_veto_detector() -> dict[str, object] | None:
    if not USE_DEEPCENTER_VETO:
        print("DeepCenter add-only repair gate disabled by configuration.")
        return None
    if torch is None:
        if REQUIRE_DEEPCENTER_VETO:
            raise ImportError("torch is required for DeepCenter add-only repair gate")
        print("DeepCenter add-only repair gate skipped because torch is unavailable.")
        return None
    from types import SimpleNamespace

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    load_errors: list[str] = []
    for checkpoint_path in _dc_checkpoint_candidates():
        if not checkpoint_path.exists():
            continue
        try:
            print("Trying DeepCenter add-only gate checkpoint:", checkpoint_path)
            checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
            if not isinstance(checkpoint, dict) or "model_state" not in checkpoint:
                raise ValueError("checkpoint has no model_state")
            checkpoint_epoch = int(checkpoint.get("epoch", -1))
            if DEEPCENTER_EXPECTED_EPOCH > 0 and checkpoint_epoch != DEEPCENTER_EXPECTED_EPOCH:
                raise ValueError(
                    f"expected DeepCenter epoch {DEEPCENTER_EXPECTED_EPOCH}, got {checkpoint_epoch}"
                )
            cfg = SimpleNamespace(**checkpoint.get("config", {}))
            model = _DCDeepCenterUNet3D(base_channels=int(getattr(cfg, "base_channels", 24)))
            model.load_state_dict(checkpoint["model_state"])
            model.to(device)
            model.eval()
            print("Loaded DeepCenter add-only gate checkpoint:", checkpoint_path)
            print("DeepCenter checkpoint epoch:", checkpoint.get("epoch"), "best_score:", checkpoint.get("best_score"))
            return {
                "model": model,
                "cfg": cfg,
                "device": device,
                "path": checkpoint_path,
                "torch": torch,
            }
        except Exception as exc:
            load_errors.append(f"{checkpoint_path}: {type(exc).__name__}: {exc}")
            print("Skipping incompatible DeepCenter checkpoint:", checkpoint_path, "|", type(exc).__name__, exc)
    message = "No usable DeepCenter checkpoint found for add-only repair gate."
    if REQUIRE_DEEPCENTER_VETO:
        checked = "\n".join(str(p) for p in _dc_checkpoint_candidates()[:80])
        errors = "\n".join(load_errors[-20:])
        raise FileNotFoundError(message + "\nChecked:\n" + checked + ("\nLoad errors:\n" + errors if errors else ""))
    print(message)
    return None


def _dc_cache_trim(cache: dict[tuple[str, int], np.ndarray]) -> None:
    limit = max(1, int(DEEPCENTER_SCORE_CACHE_MAX_FRAMES))
    while len(cache) > limit:
        cache.pop(next(iter(cache)))


def deepcenter_heatmap_for_frame(
    dataset: str,
    t: int,
    detector_bundle: dict[str, object] | None,
    frame_cache: dict[int, np.ndarray],
    heatmap_cache: dict[tuple[str, int], np.ndarray],
) -> np.ndarray | None:
    if detector_bundle is None:
        return None
    key = (dataset, int(t))
    cached = heatmap_cache.get(key)
    if cached is not None:
        return cached
    model = detector_bundle["model"]
    cfg = detector_bundle["cfg"]
    device = detector_bundle["device"]
    torch_mod = detector_bundle["torch"]
    pool_factor = int(getattr(cfg, "pool_factor", 4))
    volume = read_test_frame(dataset, int(t), frame_cache)
    pooled = _dc_pool_frame_xy(volume, pool_factor)
    image = _dc_normalize_dynamic_range(pooled, cfg)
    with torch_mod.no_grad():
        tensor = torch_mod.from_numpy(image[None, None, ...]).to(device=device, dtype=torch_mod.float32)
        logits = model(tensor)
        
        
        
        
        
        if os.environ.get("BIOHUB_DEEPCENTER_TTA", "0") != "0":
            acc = logits.clone(); nv = 1
            for dims in [(-1,), (-2,), (-2, -1)]:
                acc = acc + model(tensor.flip(dims)).flip(dims); nv += 1
            if tensor.shape[-1] == tensor.shape[-2]:
                for k in (1, 3):
                    acc = acc + torch_mod.rot90(model(torch_mod.rot90(tensor, k, dims=(-2, -1))), -k, dims=(-2, -1)); nv += 1
                acc = acc + model(tensor.transpose(-1, -2)).transpose(-1, -2); nv += 1
                at = torch_mod.rot90(tensor, 1, dims=(-2, -1)).transpose(-1, -2)
                acc = acc + torch_mod.rot90(model(at).transpose(-1, -2), -1, dims=(-2, -1)); nv += 1
            delta = float((acc / nv - logits).abs().mean())
            if delta == 0.0:
                raise RuntimeError("DEEPCENTER_TTA_NO_OP: averaged veto logits identical to the single view")
            if not getattr(deepcenter_heatmap_for_frame, "_tta_announced", False):
                print("DEEPCENTER_TTA_ACTIVE views=", nv, "mean_abs_logit_delta=", round(delta, 6), flush=True)
                deepcenter_heatmap_for_frame._tta_announced = True
            logits = acc / nv
        heatmap = torch_mod.sigmoid(logits)[0, 0].detach().cpu().numpy().astype(np.float32, copy=False)
    heatmap_cache[key] = heatmap
    _dc_cache_trim(heatmap_cache)
    return heatmap


def deepcenter_score_point(
    dataset: str | None,
    t: int,
    point: tuple[float, float, float],
    detector_bundle: dict[str, object] | None,
    frame_cache: dict[int, np.ndarray],
    heatmap_cache: dict[tuple[str, int], np.ndarray],
) -> float | None:
    if not USE_DEEPCENTER_VETO or detector_bundle is None or dataset is None:
        return None
    heatmap = deepcenter_heatmap_for_frame(dataset, int(t), detector_bundle, frame_cache, heatmap_cache)
    if heatmap is None or heatmap.size == 0:
        return None
    cfg = detector_bundle["cfg"]
    pool_factor = int(getattr(cfg, "pool_factor", 4))
    z = int(round(float(point[0])))
    y = int(round(float(point[1]) / max(pool_factor, 1)))
    x = int(round(float(point[2]) / max(pool_factor, 1)))
    z0, z1 = max(0, z - DEEPCENTER_SCORE_WIN_Z), min(heatmap.shape[0], z + DEEPCENTER_SCORE_WIN_Z + 1)
    y0, y1 = max(0, y - DEEPCENTER_SCORE_WIN_YX), min(heatmap.shape[1], y + DEEPCENTER_SCORE_WIN_YX + 1)
    x0, x1 = max(0, x - DEEPCENTER_SCORE_WIN_YX), min(heatmap.shape[2], x + DEEPCENTER_SCORE_WIN_YX + 1)
    patch = heatmap[z0:z1, y0:y1, x0:x1]
    if patch.size == 0:
        return None
    score = float(np.max(patch))
    return score if np.isfinite(score) else None


def deepcenter_accept_repair_point(
    dataset: str | None,
    t: int,
    point: tuple[float, float, float],
    detector_bundle: dict[str, object] | None,
    frame_cache: dict[int, np.ndarray],
    heatmap_cache: dict[tuple[str, int], np.ndarray],
    stats: dict[str, int],
    prefix: str,
    threshold: float,
) -> bool:
    if not USE_DEEPCENTER_VETO:
        return True
    if detector_bundle is None or dataset is None:
        stats[f"deepcenter_{prefix}_missing"] += 1
        return True
    stats[f"deepcenter_{prefix}_checked"] += 1
    score = deepcenter_score_point(dataset, int(t), point, detector_bundle, frame_cache, heatmap_cache)
    if score is None:
        stats[f"deepcenter_{prefix}_missing"] += 1
        return True
    if score < float(threshold):
        stats[f"deepcenter_{prefix}_rejected"] += 1
        return False
    stats[f"deepcenter_{prefix}_accepted"] += 1
    return True

def _position_um(node: dict[str, object]) -> np.ndarray:
    return np.array(
        [float(node["z"]) * VOXEL_SCALE_UM[0], float(node["y"]) * VOXEL_SCALE_UM[1], float(node["x"]) * VOXEL_SCALE_UM[2]],
        dtype=np.float64,
    )


def motion_relink_edges(
    nodes_by_id: dict[int, dict[str, object]],
    stats: dict[str, int],
    learned_edge_probs: dict[tuple[int, int], float] | None = None,
) -> list[dict[str, object]]:
    if not OUTPUT_MOTION_RELINK or not nodes_by_id:
        return []

    learned_edge_probs = learned_edge_probs or {}

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
        ids_by_t.setdefault(int(node["t"]), []).append(node_id)
    for ids in ids_by_t.values():
        ids.sort()

    frame_sizes = [len(ids) for ids in ids_by_t.values()]
    if frame_sizes and max(frame_sizes) > MOTION_RELINK_MAX_FRAME_NODES:
        stats["motion_relink_skipped_large_frame"] = 1
        return []

    position_um = {node_id: _position_um(node) for node_id, node in nodes_by_id.items()}
    predecessor_position_um: dict[int, np.ndarray] = {}
    selected_edges: list[dict[str, object]] = []

    def _flow_predictor(flow_src, flow_disp):
        """Median displacement of the nearest flow samples, or None.

        Cells move with their neighbours, so a displacement field sampled
        from confident links predicts a source's next position better than
        its own last step (experiments/motion_model_audit.py).
        """
        if len(flow_src) < MOTION_RELINK_FLOW_MIN_SAMPLES:
            return None
        flow_src = np.asarray(flow_src, dtype=np.float64)
        flow_disp = np.asarray(flow_disp, dtype=np.float64)
        tree = cKDTree(flow_src)
        k_query = min(MOTION_RELINK_FLOW_K + 1, len(flow_src))

        def predict(source_pos, exclude_um):
            dist, idx = tree.query(source_pos, k=k_query, distance_upper_bound=MOTION_RELINK_FLOW_RADIUS_UM)
            dist = np.atleast_1d(dist)
            idx = np.atleast_1d(idx)
            keep = np.isfinite(dist) & (dist >= exclude_um)
            idx = idx[keep][:MOTION_RELINK_FLOW_K]
            if idx.size == 0:
                return None
            return np.median(flow_disp[idx], axis=0)

        return predict

    # The flow residual is weighted along z when asked; the raw distance never is.
    flow_weight = np.array([MOTION_RELINK_FLOW_Z_WEIGHT, 1.0, 1.0], dtype=np.float64)
    flow_anisotropic = MOTION_RELINK_FLOW_Z_WEIGHT != 1.0

    def assign_pass(
        source_ids: list[int],
        target_ids: list[int],
        gate_um: float,
        flow=None,
        flow_exclude_um: float = 0.0,
    ) -> list[tuple[int, int, float, float, float]]:
        if not source_ids or not target_ids:
            return []
        big = gate_um * 1000.0 + 1.0
        cost = np.full((len(source_ids), len(target_ids)), big, dtype=np.float64)
        raw_dist = np.full_like(cost, np.inf)
        motion_dist = np.full_like(cost, np.inf)
        prob_matrix = np.zeros_like(cost)
        target_arr = np.stack([position_um[target_id] for target_id in target_ids])
        source_arr = np.stack([position_um[source_id] for source_id in source_ids])
        predicted_arr = np.empty_like(source_arr)
        flow_hit = np.zeros(len(source_ids), dtype=bool)
        for i, source_id in enumerate(source_ids):
            source_pos = position_um[source_id]
            prev_pos = predecessor_position_um.get(source_id)
            flow_step = flow(source_pos, flow_exclude_um) if flow is not None else None
            if flow_step is not None:
                predicted_arr[i] = source_pos + flow_step
                flow_hit[i] = True
                stats["motion_relink_flow_predicted"] = stats.get("motion_relink_flow_predicted", 0) + 1
            elif prev_pos is None:
                predicted_arr[i] = source_pos
            else:
                predicted_arr[i] = source_pos + MOTION_RELINK_VELOCITY_WEIGHT * (source_pos - prev_pos)
        target_tree = cKDTree(target_arr)
        gate_radius = gate_um * (1.0 + 1e-9) + 1e-9
        gate_neighbours = target_tree.query_ball_point(source_arr, r=gate_radius)
        # With a flow prior, a pair is also admitted when the target sits
        # within the gate of the *predicted* position: a cell moving 8 um with
        # its neighbours can then compete in the tight pass instead of waiting
        # for the relaxed one where slower cells have already taken its target.
        # With RAW_ADMIT off, that is the only admission for flow-predicted
        # sources; sources without a field sample keep the raw gate.
        flow_gated = flow is not None and MOTION_RELINK_FLOW_GATE
        if flow_gated:
            predicted_radius = gate_radius / MOTION_RELINK_FLOW_Z_WEIGHT if flow_anisotropic else gate_radius
            around_predicted = target_tree.query_ball_point(predicted_arr, r=predicted_radius)
            gate_neighbours = [
                sorted(set(near_source) | set(near_predicted))
                for near_source, near_predicted in zip(gate_neighbours, around_predicted)
            ]
        for i, source_id in enumerate(source_ids):
            source_pos = position_um[source_id]
            predicted = predicted_arr[i]
            raw_admits = MOTION_RELINK_FLOW_RAW_ADMIT or not (flow_gated and flow_hit[i])
            for j in sorted(gate_neighbours[i]):
                target_id = target_ids[j]
                target_pos = position_um[target_id]
                raw = float(np.linalg.norm(target_pos - source_pos))
                if flow_anisotropic:
                    motion = float(np.linalg.norm((target_pos - predicted) * flow_weight))
                else:
                    motion = float(np.linalg.norm(target_pos - predicted))
                if not ((raw_admits and raw <= gate_um) or (flow_gated and motion <= gate_um)):
                    continue
                prob = learned_prob(source_id, target_id)
                raw_dist[i, j] = raw
                motion_dist[i, j] = motion
                prob_matrix[i, j] = prob
                cost[i, j] = motion + MOTION_RELINK_FLOW_RAW_COST * raw - MOTION_RELINK_LEARNED_BONUS * prob
        row_ind, col_ind = linear_sum_assignment(cost)
        matches: list[tuple[int, int, float, float, float]] = []
        for r, c in zip(row_ind, col_ind):
            if cost[r, c] >= big:
                continue
            matches.append((
                source_ids[int(r)],
                target_ids[int(c)],
                float(raw_dist[r, c]),
                float(motion_dist[r, c]),
                float(prob_matrix[r, c]),
            ))
        return matches

    def _field_from(matches):
        return _flow_predictor(
            [position_um[m[0]] for m in matches],
            [position_um[m[1]] - position_um[m[0]] for m in matches],
        )

    seed_gate_um = MOTION_RELINK_FLOW_SEED_GATE_UM if MOTION_RELINK_FLOW_SEED_GATE_UM > 0 else MOTION_RELINK_TIGHT_UM
    flow_tight_um = MOTION_RELINK_FLOW_TIGHT_UM if MOTION_RELINK_FLOW_TIGHT_UM > 0 else MOTION_RELINK_TIGHT_UM
    flow_relaxed_um = MOTION_RELINK_FLOW_RELAXED_UM if MOTION_RELINK_FLOW_RELAXED_UM > 0 else MOTION_RELINK_RELAXED_UM

    times = sorted(ids_by_t)
    previous_flow = None
    for t in times:
        source_ids = ids_by_t.get(t, [])
        target_ids = ids_by_t.get(t + 1, [])
        if not source_ids or not target_ids:
            continue
        flow = None
        flow_exclude_um = 0.0
        if MOTION_RELINK_FLOW_MODE == "prev":
            flow = previous_flow
        elif MOTION_RELINK_FLOW_MODE == "seed":
            # Confident tight matches first, then everything is assigned
            # against the field they define. A source's own seed match is
            # excluded from its sample so a wrong seed cannot vote for itself.
            seed = assign_pass(source_ids, target_ids, seed_gate_um, previous_flow)
            flow = _field_from(seed)
            flow_exclude_um = MOTION_RELINK_FLOW_EXCLUDE_UM
            if flow is not None:
                stats["motion_relink_flow_frames"] = stats.get("motion_relink_flow_frames", 0) + 1
        rounds = MOTION_RELINK_FLOW_ITER if MOTION_RELINK_FLOW_MODE != "off" else 1
        frame_matches: list[tuple[int, int, float, float, str, float]] = []
        for round_index in range(max(1, rounds)):
            if round_index > 0:
                # Refine: the field from the previous round's final matches,
                # then assign every source again against it.
                refined = _field_from([(s, g) for s, g, _r, _m, _n, _p in frame_matches])
                if refined is None:
                    break
                flow = refined
                flow_exclude_um = MOTION_RELINK_FLOW_EXCLUDE_UM
            unmatched_sources = set(source_ids)
            unmatched_targets = set(target_ids)
            frame_matches = []
            passes = (("tight", flow_tight_um), ("relaxed", flow_relaxed_um)) if flow is not None else (
                ("tight", MOTION_RELINK_TIGHT_UM), ("relaxed", MOTION_RELINK_RELAXED_UM))
            for pass_name, gate_um in passes:
                pass_sources = [node_id for node_id in source_ids if node_id in unmatched_sources]
                pass_targets = [node_id for node_id in target_ids if node_id in unmatched_targets]
                matches = assign_pass(pass_sources, pass_targets, gate_um, flow, flow_exclude_um)
                for source_id, target_id, raw, motion, prob in matches:
                    if source_id not in unmatched_sources or target_id not in unmatched_targets:
                        continue
                    unmatched_sources.remove(source_id)
                    unmatched_targets.remove(target_id)
                    frame_matches.append((source_id, target_id, raw, motion, pass_name, prob))
        for source_id, target_id, raw, motion, pass_name, prob in frame_matches:
            if pass_name == "tight":
                stats["motion_relink_tight_edges"] += 1
            else:
                stats["motion_relink_relaxed_edges"] += 1
            selected_edges.append({
                "source_id": source_id,
                "target_id": target_id,
                "edge_prob": prob,
                "distance_um": raw,
                "motion_distance_um": motion,
                "motion_relinked": 1,
                "motion_pass": pass_name,
            })
            predecessor_position_um[target_id] = position_um[source_id]
        if MOTION_RELINK_FLOW_MODE != "off":
            previous_flow = _field_from([(s, g) for s, g, _r, _m, _n, _p in frame_matches])
        stats["motion_relink_frames"] += 1

    stats["motion_relink_edges"] = len(selected_edges)
    return selected_edges

def close_single_frame_gaps(
    nodes_by_id: dict[int, dict[str, object]],
    edges: list[dict[str, object]],
    stats: dict[str, int],
    dataset: str | None = None,
    deepcenter_bundle: dict[str, object] | None = None,
    frame_cache: dict[int, np.ndarray] | None = None,
    deepcenter_cache: dict[tuple[str, int], np.ndarray] | None = None,
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    if not OUTPUT_GAP_CLOSE or GAP_CLOSE_MAX_GAP < 1 or not edges:
        return nodes_by_id, edges

    outgoing = {int(edge["source_id"]) for edge in edges}
    incoming = {int(edge["target_id"]) for edge in edges}
    incident = outgoing | incoming

    ends_by_t: dict[int, list[int]] = {}
    starts_by_t: dict[int, list[int]] = {}
    isolated_by_t: dict[int, list[int]] = {}
    all_ids_by_t: dict[int, list[int]] = {}
    for node_id, node in nodes_by_id.items():
        t = int(node["t"])
        all_ids_by_t.setdefault(t, []).append(node_id)
        if node_id not in outgoing:
            ends_by_t.setdefault(t, []).append(node_id)
        if node_id not in incoming:
            starts_by_t.setdefault(t, []).append(node_id)
        if node_id not in incident:
            isolated_by_t.setdefault(t, []).append(node_id)

    max_synthetic = min(
        GAP_CLOSE_MAX_ADDED_ABS,
        max(1, int(round(len(nodes_by_id) * GAP_CLOSE_MAX_ADDED_FRAC))) if GAP_CLOSE_MAX_ADDED_FRAC > 0 else 0,
    )
    next_id = _next_node_id(nodes_by_id)
    frame_cache = frame_cache if frame_cache is not None else {}
    deepcenter_cache = deepcenter_cache if deepcenter_cache is not None else {}
    used_starts: set[int] = set()
    used_isolated: set[int] = set()
    synthetic_added = 0
    new_edges: list[dict[str, object]] = []

    density_cache: dict[int, dict[int, float]] = {}

    def frame_local_spacing(t: int) -> dict[int, float]:
        cached = density_cache.get(t)
        if cached is not None:
            return cached

        frame_ids = all_ids_by_t.get(t, [])
        if len(frame_ids) <= 1:
            result = {
                node_id: GAP_DENSITY_REFERENCE_UM
                for node_id in frame_ids
            }
            density_cache[t] = result
            return result

        positions = np.stack(
            [_position_um(nodes_by_id[node_id]) for node_id in frame_ids]
        )
        tree = cKDTree(positions)
        query_k = min(
            len(frame_ids),
            max(2, GAP_DENSITY_NEIGHBORS + 1),
        )
        distances, _ = tree.query(positions, k=query_k)
        if distances.ndim == 1:
            distances = distances[:, None]

        result: dict[int, float] = {}
        for idx, node_id in enumerate(frame_ids):
            neighbour_distances = distances[idx, 1:]
            neighbour_distances = neighbour_distances[
                np.isfinite(neighbour_distances)
            ]
            spacing = (
                float(np.median(neighbour_distances))
                if neighbour_distances.size
                else GAP_DENSITY_REFERENCE_UM
            )
            result[node_id] = spacing

        density_cache[t] = result
        stats["gap_density_nodes_scored"] += len(result)
        return result

    effective_gap_max = min(GAP_CLOSE_MAX_GAP, 1)
    stats["gap_close_effective_max_gap"] = effective_gap_max
    for gap in range(1, effective_gap_max + 1):
        for t, end_ids in sorted(ends_by_t.items()):
            start_ids = [sid for sid in starts_by_t.get(t + gap + 1, []) if sid not in used_starts]
            if not end_ids or not start_ids:
                continue

            end_points = [node_point(nodes_by_id[eid]) for eid in end_ids]
            start_points = [node_point(nodes_by_id[sid]) for sid in start_ids]
            threshold_um = GAP_CLOSE_UM * (gap + 1)
            d = np.zeros(
                (len(end_ids), len(start_ids)),
                dtype=np.float64,
            )
            adaptive_threshold = np.full_like(d, threshold_um)

            source_spacing = frame_local_spacing(t)
            target_spacing = frame_local_spacing(t + gap + 1)

            for i, ep in enumerate(end_points):
                for j, sp in enumerate(start_points):
                    d[i, j] = point_distance_um(ep, sp)

                    if GAP_DENSITY_ADAPTIVE:
                        local_spacing = 0.5 * (
                            source_spacing.get(
                                end_ids[i],
                                GAP_DENSITY_REFERENCE_UM,
                            )
                            + target_spacing.get(
                                start_ids[j],
                                GAP_DENSITY_REFERENCE_UM,
                            )
                        )
                        step_delta = float(
                            np.clip(
                                GAP_DENSITY_GAIN
                                * (
                                    local_spacing
                                    - GAP_DENSITY_REFERENCE_UM
                                ),
                                -GAP_DENSITY_MAX_STEP_DELTA_UM,
                                GAP_DENSITY_MAX_STEP_DELTA_UM,
                            )
                        )
                        adaptive_threshold[i, j] = (
                            threshold_um + step_delta * (gap + 1)
                        )
                        stats[
                            "gap_density_step_delta_milli_sum"
                        ] += int(round(1000.0 * step_delta))

            base_allowed = d <= threshold_um
            adaptive_allowed = d <= adaptive_threshold

            stats["gap_density_candidates_expanded"] += int(
                (adaptive_allowed & ~base_allowed).sum()
            )
            stats["gap_density_candidates_restricted"] += int(
                (base_allowed & ~adaptive_allowed).sum()
            )
            stats["gap_candidates"] += int(adaptive_allowed.sum())

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
                    stats[
                        "gap_density_selected_outside_base"
                    ] += 1
                source_id = end_ids[int(r)]
                target_id = start_ids[int(c)]
                if source_id in outgoing or target_id in used_starts:
                    continue

                source = nodes_by_id[source_id]
                target = nodes_by_id[target_id]
                mid_t = int(source["t"]) + gap
                mid_point = (
                    (float(source["z"]) + float(target["z"])) / 2.0,
                    (float(source["y"]) + float(target["y"])) / 2.0,
                    (float(source["x"]) + float(target["x"])) / 2.0,
                )

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
                        stats["gap_skipped_node_cap"] += 1
                        continue
                    middle_id = next_id
                    next_id += 1
                    refined_point = refine_synthetic_midpoint(dataset, mid_t, mid_point, frame_cache, stats)
                    nodes_by_id[middle_id] = {
                        "node_id": middle_id,
                        "t": mid_t,
                        "z": refined_point[0],
                        "y": refined_point[1],
                        "x": refined_point[2],
                        "gap_synthetic": 1,
                    }
                    synthetic_added += 1
                    stats["gap_inserted_synthetic"] += 1

                middle = nodes_by_id[middle_id]
                gap_span_um = float(d[r, c])
                marginal_gap = gap_span_um >= DEEPCENTER_GAP_CONFIRM_MIN_SPAN_UM
                synthetic_middle = int(middle.get("gap_synthetic", 0)) == 1
                requires_center_confirmation = (
                    DEEPCENTER_GAP_VETO and marginal_gap and synthetic_middle
                )
                if DEEPCENTER_GAP_VETO and not marginal_gap:
                    stats["deepcenter_gap_bypassed_strong_motion"] += 1
                elif DEEPCENTER_GAP_VETO and not synthetic_middle:
                    stats["deepcenter_gap_bypassed_observed_node"] += 1
                if requires_center_confirmation and not deepcenter_accept_repair_point(
                    dataset,
                    mid_t,
                    node_point(middle),
                    deepcenter_bundle,
                    frame_cache,
                    deepcenter_cache,
                    stats,
                    "gap",
                    DEEPCENTER_GAP_THRESHOLD,
                ):
                    if int(middle.get("gap_synthetic", 0)) == 1:
                        nodes_by_id.pop(middle_id, None)
                        synthetic_added = max(0, synthetic_added - 1)
                        stats["gap_inserted_synthetic"] = max(0, stats["gap_inserted_synthetic"] - 1)
                    continue
                if middle_reused:
                    used_isolated.add(middle_id)
                    stats["gap_reused_existing"] += 1

                e1 = {
                    "source_id": source_id,
                    "target_id": middle_id,
                    "edge_prob": None,
                    "distance_um": edge_distance_um(source, middle),
                    "gap_closed": 1,
                }
                e2 = {
                    "source_id": middle_id,
                    "target_id": target_id,
                    "edge_prob": None,
                    "distance_um": edge_distance_um(middle, target),
                    "gap_closed": 1,
                }
                new_edges.extend([e1, e2])
                outgoing.add(source_id)
                incoming.add(middle_id)
                outgoing.add(middle_id)
                incoming.add(target_id)
                used_starts.add(target_id)
                stats["gap_pairs_selected"] += 1
                stats["gap_added_edges"] += 2

    if new_edges:
        edges = [*edges, *new_edges]
    stats["gap_added_nodes"] = stats["gap_inserted_synthetic"]
    return nodes_by_id, edges


def _single_successor_map(edges: list[dict[str, object]]) -> dict[int, int]:
    by_source: dict[int, list[int]] = {}
    for edge in edges:
        by_source.setdefault(int(edge["source_id"]), []).append(int(edge["target_id"]))
    return {source: targets[0] for source, targets in by_source.items() if len(targets) == 1}


def _single_predecessor_map(edges: list[dict[str, object]]) -> dict[int, int]:
    by_target: dict[int, list[int]] = {}
    for edge in edges:
        by_target.setdefault(int(edge["target_id"]), []).append(int(edge["source_id"]))
    return {target: sources[0] for target, sources in by_target.items() if len(sources) == 1}


def recover_strict_gap2(
    nodes_by_id: dict[int, dict[str, object]],
    edges: list[dict[str, object]],
    stats: dict[str, int],
    dataset: str | None = None,
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    if not OUTPUT_GAP2_RECOVERY or not edges or not nodes_by_id:
        return nodes_by_id, edges

    outgoing = {int(edge["source_id"]) for edge in edges}
    incoming = {int(edge["target_id"]) for edge in edges}
    predecessor = _single_predecessor_map(edges)
    successor = _single_successor_map(edges)

    ends_by_t: dict[int, list[int]] = {}
    starts_by_t: dict[int, list[int]] = {}
    for node_id, node in nodes_by_id.items():
        t = int(node["t"])
        if node_id not in outgoing:
            ends_by_t.setdefault(t, []).append(node_id)
        if node_id not in incoming:
            starts_by_t.setdefault(t, []).append(node_id)

    cap = min(GAP2_MAX_LINKS_ABS, max(1, int(round(len(edges) * GAP2_MAX_LINKS_FRAC))))
    proposals: list[tuple[float, int, int, int, float]] = []

    def pos_um(node_id: int) -> np.ndarray:
        node = nodes_by_id[node_id]
        return np.array([float(node["z"]), float(node["y"]), float(node["x"])], dtype=np.float64) * np.array(VOXEL_SCALE_UM)

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
                            cos = float(np.dot(prev_step, step) / (prev_norm * step_norm + 1e-9))
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
                            cos = float(np.dot(next_step, step) / (next_norm * step_norm + 1e-9))
                            if cos > -0.25 and np.linalg.norm(next_step - step) <= 6.0:
                                ok_context = True
                            context_penalty += max(0.0, 0.25 - cos)
                    if not ok_context:
                        continue
                proposals.append((dist + 2.0 * context_penalty, end_id, start_id, t, dist))

    proposals.sort(key=lambda item: item[0])
    stats["gap2_candidates"] = len(proposals)
    if not proposals:
        return nodes_by_id, edges

    selected: list[tuple[float, int, int, int, float]] = []
    used_ends: set[int] = set()
    used_starts: set[int] = set()
    per_frame_count: dict[int, int] = {}
    for proposal in proposals:
        if len(selected) >= cap:
            stats["gap2_skipped_cap"] += 1
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
        return nodes_by_id, edges

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
            mid_t = int(source["t"]) + k
            midpoint = (
                float(source["z"]) + (float(target["z"]) - float(source["z"])) * frac,
                float(source["y"]) + (float(target["y"]) - float(source["y"])) * frac,
                float(source["x"]) + (float(target["x"]) - float(source["x"])) * frac,
            )
            refined_point = refine_synthetic_midpoint(dataset, mid_t, midpoint, frame_cache, stats)
            node_id = next_node_id
            next_node_id += 1
            nodes_by_id[node_id] = {
                "node_id": node_id,
                "t": mid_t,
                "z": refined_point[0],
                "y": refined_point[1],
                "x": refined_point[2],
            }
            inserted_ids.append(node_id)
            current = nodes_by_id[node_id]
            new_edges.append({
                "source_id": previous_id,
                "target_id": node_id,
                "edge_prob": None,
                "distance_um": edge_distance_um(nodes_by_id[previous_id], current),
                "gap2_recovered": 1,
            })
            previous_id = node_id
        new_edges.append({
            "source_id": previous_id,
            "target_id": start_id,
            "edge_prob": None,
            "distance_um": edge_distance_um(nodes_by_id[previous_id], target),
            "gap2_recovered": 1,
        })
        stats["gap2_pairs_selected"] += 1
        stats["gap2_added_nodes"] += len(inserted_ids)
        stats["gap2_added_edges"] += 3

    return nodes_by_id, [*edges, *new_edges]


def _gapfill_bump(stats: dict[str, int], key: str, n: int = 1) -> None:
    stats[key] = int(stats.get(key, 0)) + n


def load_low_detections(
    nodes_by_id: dict[int, dict[str, object]],
    dataset: str | None,
    stats: dict[str, int],
) -> dict[int, dict[str, np.ndarray]] | None:
    """Per-frame pool of the detector's sub-threshold peaks from the prediction cell's dump.

    Peaks below GAPFILL_MIN_SCORE and peaks within GAPFILL_EXCLUDE_UM of a node
    of their frame (the node set's own peaks among them) are dropped. None when
    the dump is missing or unreadable, and the filler then does nothing.
    """
    cache_dir = os.environ.get("BIOHUB_CACHE_DIR", "").strip()
    if GAPFILL_MAX_GAP < 1 or not cache_dir or not dataset:
        return None
    cache_path = Path(cache_dir) / f"{dataset}.npz"
    if not cache_path.exists():
        print(f"  [{dataset}] no low-detection dump at {cache_path}; gap filler idle")
        return None
    try:
        with np.load(cache_path) as cz:
            if "low_coords" not in cz.files:
                print(f"  [{dataset}] dump has no low_coords; gap filler idle")
                return None
            low = np.asarray(cz["low_coords"], dtype=np.float64).reshape(-1, 4)
            score = np.asarray(cz["low_score"], dtype=np.float64).reshape(-1)
    except Exception as exc:
        print(f"  [{dataset}] low-detection dump unreadable ({type(exc).__name__}: {exc}); gap filler idle")
        return None
    return build_low_detection_pool(nodes_by_id, low, score, stats, dataset)


def build_low_detection_pool(
    nodes_by_id: dict[int, dict[str, object]],
    low: np.ndarray,
    score: np.ndarray,
    stats: dict[str, int],
    dataset: str | None = None,
) -> dict[int, dict[str, np.ndarray]]:
    keep = score >= GAPFILL_MIN_SCORE
    low, score = low[keep], score[keep]
    scale = np.array(VOXEL_SCALE_UM, dtype=np.float64)
    node_um_by_t: dict[int, list] = {}
    for node in nodes_by_id.values():
        node_um_by_t.setdefault(int(node["t"]), []).append(np.array(node_point(node), dtype=np.float64) * scale)
    pool: dict[int, dict[str, np.ndarray]] = {}
    excluded = 0
    for t in np.unique(low[:, 0]).astype(int).tolist() if len(low) else []:
        sel = low[:, 0] == t
        vox = low[sel, 1:]
        um = vox * scale
        sc = score[sel]
        existing = node_um_by_t.get(t)
        if existing:
            d, _ = cKDTree(np.stack(existing)).query(um, k=1)
            free = d > GAPFILL_EXCLUDE_UM
            excluded += int((~free).sum())
            vox, um, sc = vox[free], um[free], sc[free]
        if len(vox):
            pool[t] = {"vox": vox, "um": um, "score": sc}
    n_free = int(sum(len(p["vox"]) for p in pool.values()))
    _gapfill_bump(stats, "gapfill_pool_peaks", n_free)
    _gapfill_bump(stats, "gapfill_pool_excluded", excluded)
    if dataset is not None:
        print(f"  [{dataset}] low-detection pool: {len(low)} peaks >= {GAPFILL_MIN_SCORE}, "
              f"{excluded} on existing nodes, {n_free} free")
    return pool


def fill_gaps_from_low_detections(
    nodes_by_id: dict[int, dict[str, object]],
    edges: list[dict[str, object]],
    stats: dict[str, int],
    dataset: str | None = None,
    frame_cache: dict[int, np.ndarray] | None = None,
    pool: dict[int, dict[str, np.ndarray]] | None = None,
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    """Bridge a track end at t to a track start at t+g+1 through sub-threshold peaks.

    Runs after the single-frame closer and gap2, on what they left open. For
    each candidate pair (span within GAPFILL_STEP_UM per frame, gap2's
    direction test when a neighbour exists) the straight line from end to
    start is sampled at each missing frame and the nearest free peak within
    GAPFILL_PEAK_RADIUS_UM of the sample is taken; a bridge needs a peak at
    every frame except at most GAPFILL_ALLOW_SYNTHETIC of them, which get an
    interpolated node refined against the frame like the closer's midpoints.
    The pairs of one (t, g) are assigned by Hungarian on span/(g+1) plus the
    mean peak deviation, shorter gaps first. Added nodes are capped at
    GAPFILL_MAX_ADDED_FRAC of the node set.
    """
    if GAPFILL_MAX_GAP < 1 or not edges or not nodes_by_id:
        return nodes_by_id, edges
    if pool is None:
        pool = load_low_detections(nodes_by_id, dataset, stats)
    if not pool:
        return nodes_by_id, edges
    scale = np.array(VOXEL_SCALE_UM, dtype=np.float64)
    outgoing: dict[int, list[int]] = {}
    incoming: dict[int, list[int]] = {}
    for edge in edges:
        outgoing.setdefault(int(edge["source_id"]), []).append(int(edge["target_id"]))
        incoming.setdefault(int(edge["target_id"]), []).append(int(edge["source_id"]))
    pos = {nid: np.array(node_point(node), dtype=np.float64) * scale for nid, node in nodes_by_id.items()}
    ends_by_t: dict[int, list[int]] = {}
    starts_by_t: dict[int, list[int]] = {}
    for nid, node in nodes_by_id.items():
        t = int(node["t"])
        if nid not in outgoing:
            ends_by_t.setdefault(t, []).append(nid)
        if nid not in incoming:
            starts_by_t.setdefault(t, []).append(nid)
    trees = {t: cKDTree(p["um"]) for t, p in pool.items()}
    used_peak = {t: np.zeros(len(p["um"]), dtype=bool) for t, p in pool.items()}
    budget = int(round(len(nodes_by_id) * GAPFILL_MAX_ADDED_FRAC))
    frame_cache = frame_cache if frame_cache is not None else {}
    next_id = _next_node_id(nodes_by_id)
    used_end: set[int] = set()
    used_start: set[int] = set()
    added_nodes = 0
    new_edges: list[dict[str, object]] = []

    def context_ok(end_id: int, start_id: int) -> bool:
        if not GAPFILL_CONTEXT:
            return True
        step = pos[start_id] - pos[end_id]
        sn = float(np.linalg.norm(step))
        if sn <= 0.01:
            return True
        prev = incoming.get(end_id)
        if prev:
            other = pos[end_id] - pos[prev[0]]
            on = float(np.linalg.norm(other))
            if on > 0.01 and float(np.dot(other, step)) / (on * sn) <= -0.25:
                return False
        nxt = outgoing.get(start_id)
        if nxt:
            other = pos[nxt[0]] - pos[start_id]
            on = float(np.linalg.norm(other))
            if on > 0.01 and float(np.dot(other, step)) / (on * sn) <= -0.25:
                return False
        return True

    def chain_for(end_id: int, start_id: int, g: int):
        span = pos[start_id] - pos[end_id]
        t0 = int(nodes_by_id[end_id]["t"])
        items, dev, synthetic = [], [], 0
        for k in range(1, g + 1):
            q = pos[end_id] + span * (k / (g + 1))
            tk = t0 + k
            tree = trees.get(tk)
            j = None
            if tree is not None:
                cand = [c for c in tree.query_ball_point(q, r=GAPFILL_PEAK_RADIUS_UM) if not used_peak[tk][c]]
                if cand:
                    dists = np.linalg.norm(pool[tk]["um"][cand] - q, axis=1)
                    best = int(np.argmin(dists))
                    j = cand[best]
                    dev.append(float(dists[best]))
            if j is None:
                synthetic += 1
                if synthetic > GAPFILL_ALLOW_SYNTHETIC:
                    return None
                dev.append(GAPFILL_PEAK_RADIUS_UM)
            items.append((tk, j, q))
        cost = float(np.linalg.norm(span)) / (g + 1) + (sum(dev) / len(dev) if dev else 0.0)
        return cost, items

    for g in range(1, GAPFILL_MAX_GAP + 1):
        gate = GAPFILL_STEP_UM * (g + 1)
        for t in sorted(ends_by_t):
            if added_nodes + g > budget:
                _gapfill_bump(stats, "gapfill_budget_hit")
                break
            ends = [e for e in ends_by_t[t] if e not in used_end]
            starts = [s for s in starts_by_t.get(t + g + 1, []) if s not in used_start]
            if not ends or not starts:
                continue
            end_pts = np.stack([pos[e] for e in ends])
            start_pts = np.stack([pos[s] for s in starts])
            start_tree = cKDTree(start_pts)
            cost = np.full((len(ends), len(starts)), np.inf)
            n_chains = 0
            for i, js in enumerate(start_tree.query_ball_point(end_pts, r=gate)):
                for j in js:
                    if not context_ok(ends[i], starts[j]):
                        continue
                    chain = chain_for(ends[i], starts[j], g)
                    if chain is None:
                        continue
                    cost[i, j] = chain[0]
                    n_chains += 1
            if n_chains == 0:
                continue
            _gapfill_bump(stats, "gapfill_candidates", n_chains)
            finite = np.isfinite(cost)
            big = float(np.max(cost[finite])) * 1000.0 + 1.0
            row_ind, col_ind = linear_sum_assignment(np.where(finite, cost, big))
            picks = sorted((float(cost[i, j]), int(i), int(j)) for i, j in zip(row_ind, col_ind) if finite[i, j])
            for _, i, j in picks:
                if added_nodes + g > budget:
                    _gapfill_bump(stats, "gapfill_budget_hit")
                    break
                chain = chain_for(ends[i], starts[j], g)  # an earlier pick may have taken a peak
                if chain is None:
                    continue
                prev = ends[i]
                for tk, pk, q in chain[1]:
                    nid = next_id
                    next_id += 1
                    if pk is not None:
                        vox = pool[tk]["vox"][pk]
                        used_peak[tk][pk] = True
                        node = {"node_id": nid, "t": tk, "z": float(vox[0]), "y": float(vox[1]), "x": float(vox[2]), "gapfill_peak": 1}
                        _gapfill_bump(stats, "gapfill_peak_nodes")
                    else:
                        p = q / scale
                        refined = refine_synthetic_midpoint(dataset, tk, (float(p[0]), float(p[1]), float(p[2])), frame_cache, stats)
                        node = {"node_id": nid, "t": tk, "z": float(refined[0]), "y": float(refined[1]), "x": float(refined[2]), "gap_synthetic": 1}
                        _gapfill_bump(stats, "gapfill_synthetic_nodes")
                    nodes_by_id[nid] = node
                    new_edges.append({
                        "source_id": prev, "target_id": nid, "edge_prob": None,
                        "distance_um": edge_distance_um(nodes_by_id[prev], node), "gap_filled": 1,
                    })
                    prev = nid
                    added_nodes += 1
                new_edges.append({
                    "source_id": prev, "target_id": starts[j], "edge_prob": None,
                    "distance_um": edge_distance_um(nodes_by_id[prev], nodes_by_id[starts[j]]), "gap_filled": 1,
                })
                used_end.add(ends[i])
                used_start.add(starts[j])
                _gapfill_bump(stats, f"gapfill_pairs_g{g}")
    _gapfill_bump(stats, "gapfill_added_nodes", added_nodes)
    _gapfill_bump(stats, "gapfill_added_edges", len(new_edges))
    if dataset is not None and new_edges:
        print(f"  [{dataset}] gap filler: +{added_nodes} nodes, +{len(new_edges)} edges")
    return nodes_by_id, [*edges, *new_edges]


def add_safe_divisions_postlink(
    nodes_by_id: dict[int, dict[str, object]],
    edges: list[dict[str, object]],
    stats: dict[str, int],
    dataset: str | None = None,
    deepcenter_bundle: dict[str, object] | None = None,
    frame_cache: dict[int, np.ndarray] | None = None,
    deepcenter_cache: dict[tuple[str, int], np.ndarray] | None = None,
) -> list[dict[str, object]]:
    if not OUTPUT_SAFE_DIVISIONS or not edges or not nodes_by_id:
        return edges
    frame_cache = frame_cache if frame_cache is not None else {}
    deepcenter_cache = deepcenter_cache if deepcenter_cache is not None else {}
 
    out_by_source: dict[int, list[dict[str, object]]] = {}
    incoming: set[int] = set()
    for edge in edges:
        out_by_source.setdefault(int(edge["source_id"]), []).append(edge)
        incoming.add(int(edge["target_id"]))
 
    ids_by_t: dict[int, list[int]] = {}
    for node_id, node in nodes_by_id.items():
        ids_by_t.setdefault(int(node["t"]), []).append(node_id)
 
    existing_edges = {(int(edge["source_id"]), int(edge["target_id"])) for edge in edges}
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
            existing_child_id = int(existing_child_edge["target_id"])
            existing_child = nodes_by_id.get(existing_child_id)
            if existing_child is None or int(existing_child["t"]) != t + 1:
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
                    stats["safe_division_mutual_nn_rejected"] += 1
                    continue
 
                
                
                
                
                if SAFE_DIV_REQUIRE_DIVERGENCE:
                    c1_succ = out_by_source.get(existing_child_id, [])
                    q_succ = out_by_source.get(candidate_id, [])
                    if len(c1_succ) != 1 or len(q_succ) != 1:
                        stats["safe_division_divergence_rejected"] += 1
                        continue
                    c1_grandchild = nodes_by_id.get(int(c1_succ[0]["target_id"]))
                    q_grandchild = nodes_by_id.get(int(q_succ[0]["target_id"]))
                    if (
                        c1_grandchild is None or q_grandchild is None
                        or int(c1_grandchild["t"]) != t + 2
                        or int(q_grandchild["t"]) != t + 2
                    ):
                        stats["safe_division_divergence_rejected"] += 1
                        continue
                    grandchild_dist = edge_distance_um(c1_grandchild, q_grandchild)
                    if grandchild_dist - sister_dist < SAFE_DIV_DIVERGE_UM:
                        stats["safe_division_divergence_rejected"] += 1
                        continue
 
                stats["safe_division_geometric_candidates"] += 1
                if DEEPCENTER_SAFE_DIV_VETO and not deepcenter_accept_repair_point(
                    dataset,
                    int(candidate["t"]),
                    node_point(candidate),
                    deepcenter_bundle,
                    frame_cache,
                    deepcenter_cache,
                    stats,
                    "safe_div",
                    DEEPCENTER_SAFE_DIV_THRESHOLD,
                ):
                    continue
                
                
                
                
                
                
                if SAFE_DIV_SISTER_SYMMETRY_TAU > 0.0:
                    _sym_denom = max((child_dist + parent_dist) / 2.0, 1e-6)
                    if abs(child_dist - parent_dist) / _sym_denom > SAFE_DIV_SISTER_SYMMETRY_TAU:
                        stats["safe_division_symmetry_rejected"] += 1
                        continue
                score = parent_dist + 0.15 * sister_dist
                proposals.append((score, source_id, candidate_id, parent_dist, sister_dist))
 
        stats["safe_division_candidates"] += len(proposals)
        if not proposals:
            continue
        proposals.sort(key=lambda item: item[0])
        added_this_frame = 0
        for _, source_id, candidate_id, parent_dist, _ in proposals:
            if len(added) >= global_cap:
                stats["safe_division_skipped_cap"] += 1
                break
            if added_this_frame >= frame_cap:
                break
            if candidate_id in used_targets or candidate_id in incoming:
                continue
            if source_id in used_sources:
                continue
            candidate = nodes_by_id[candidate_id]
            added.append({
                "source_id": source_id,
                "target_id": candidate_id,
                "edge_prob": None,
                "distance_um": parent_dist,
                "safe_division": 1,
            })
            used_targets.add(candidate_id)
            used_sources.add(source_id)
            added_this_frame += 1
 
    if added:
        stats["safe_divisions_added"] = len(added)
        return [*edges, *added]
    return edges


def filter_short_track_components(
    nodes_by_id: dict[int, dict[str, object]],
    edges: list[dict[str, object]],
    stats: dict[str, int],
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    if not OUTPUT_FILTER_SHORT_TRACKS or OUTPUT_MIN_TRACK_LEN <= 1 or not edges:
        return nodes_by_id, edges

    parent = {node_id: node_id for node_id in nodes_by_id}

    def find(node_id: int) -> int:
        while parent[node_id] != node_id:
            parent[node_id] = parent[parent[node_id]]
            node_id = parent[node_id]
        return node_id

    def union(a: int, b: int) -> None:
        if a not in parent or b not in parent:
            return
        ra = find(a)
        rb = find(b)
        if ra != rb:
            parent[ra] = rb

    out_count: dict[int, int] = {}
    for edge in edges:
        source_id = int(edge["source_id"])
        target_id = int(edge["target_id"])
        union(source_id, target_id)
        out_count[source_id] = out_count.get(source_id, 0) + 1

    components: dict[int, list[int]] = {}
    for node_id in nodes_by_id:
        components.setdefault(find(node_id), []).append(node_id)

    component_edges: dict[int, list[dict[str, object]]] = {root: [] for root in components}
    for edge in edges:
        source_id = int(edge["source_id"])
        target_id = int(edge["target_id"])
        if source_id in parent and target_id in parent:
            component_edges.setdefault(find(source_id), []).append(edge)

    keep: set[int] = set()
    for root, members in components.items():
        has_division = any(out_count.get(node_id, 0) >= 2 for node_id in members)
        if len(members) >= OUTPUT_MIN_TRACK_LEN or (OUTPUT_KEEP_DIVISION_COMPONENTS and has_division):
            keep.update(members)

    if not keep:
        stats["short_track_filter_skipped_all"] += 1
        return nodes_by_id, edges

    removed_before_rescue = len(nodes_by_id) - len(keep)
    if removed_before_rescue <= 0:
        return nodes_by_id, edges

    if ADAPTIVE_SHORT_TRACK_RESCUE:
        removed_frac = removed_before_rescue / max(len(nodes_by_id), 1)
        if removed_frac >= SHORT_TRACK_RESCUE_TRIGGER_REMOVED_FRAC:
            budget = min(
                SHORT_TRACK_RESCUE_MAX_NODES_ABS,
                max(0, int(round(len(nodes_by_id) * SHORT_TRACK_RESCUE_MAX_NODES_FRAC))),
            )
            stats["short_track_rescue_triggered"] = 1
            stats["short_track_rescue_budget"] = budget
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
                        prob = float(edge.get("edge_prob", 0.0))
                    except (TypeError, ValueError):
                        prob = 0.0
                    if np.isfinite(prob):
                        probs.append(prob)
                    try:
                        dist = float(edge.get("distance_um", np.nan))
                    except (TypeError, ValueError):
                        dist = np.nan
                    if np.isfinite(dist):
                        dists.append(dist)
                mean_prob = float(np.mean(probs)) if probs else 0.0
                mean_dist = float(np.mean(dists)) if dists else float("inf")
                if mean_prob < SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB:
                    continue
                if mean_dist > SHORT_TRACK_RESCUE_MAX_MEAN_EDGE_DIST_UM:
                    continue
                score = mean_prob - 0.02 * mean_dist + 0.004 * len(members)
                proposals.append((score, len(members), mean_prob, root, members))
            proposals.sort(reverse=True)
            rescued_nodes = 0
            rescued_components = 0
            for _, size, _, _, members in proposals:
                if budget <= 0 or rescued_nodes + size > budget:
                    continue
                keep.update(members)
                rescued_nodes += size
                rescued_components += 1
            stats["short_track_rescue_components"] = rescued_components
            stats["short_track_rescue_nodes"] = rescued_nodes

    removed_nodes = len(nodes_by_id) - len(keep)
    if removed_nodes <= 0:
        return nodes_by_id, edges

    kept_nodes = {node_id: node for node_id, node in nodes_by_id.items() if node_id in keep}
    kept_edges = [
        edge for edge in edges
        if int(edge["source_id"]) in kept_nodes and int(edge["target_id"]) in kept_nodes
    ]
    stats["short_track_components_removed"] = sum(1 for members in components.values() if not (set(members) & keep))
    stats["short_track_nodes_removed"] = removed_nodes
    stats["short_track_edges_removed"] = len(edges) - len(kept_edges)
    return kept_nodes, kept_edges


def linefit_smooth_output_graph(
    nodes_by_id: dict[int, dict[str, object]],
    edges: list[dict[str, object]],
    stats: dict[str, int],
) -> dict[int, dict[str, object]]:
    """Smooth linear track interiors without changing graph topology."""
    if not OUTPUT_LINEFIT_SMOOTH or OUTPUT_LINEFIT_WEIGHT <= 0 or OUTPUT_LINEFIT_WINDOW <= 0 or not edges:
        return nodes_by_id

    predecessor: dict[int, list[int]] = {}
    successor: dict[int, list[int]] = {}
    for edge in edges:
        source_id = int(edge["source_id"])
        target_id = int(edge["target_id"])
        source = nodes_by_id.get(source_id)
        target = nodes_by_id.get(target_id)
        if source is None or target is None:
            continue
        if int(target["t"]) != int(source["t"]) + 1:
            continue
        successor.setdefault(source_id, []).append(target_id)
        predecessor.setdefault(target_id, []).append(source_id)

    original_pos = {
        node_id: np.array([float(node["z"]), float(node["y"]), float(node["x"])], dtype=np.float64)
        for node_id, node in nodes_by_id.items()
    }
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
            stats["linefit_skipped_nodes"] += 1
            continue

        dts = np.array([delta for delta, _ in neighbourhood], dtype=np.float64)
        coords = np.stack([original_pos[nid] for _, nid in neighbourhood])
        fitted = np.array([np.polyval(np.polyfit(dts, coords[:, axis], 1), 0.0) for axis in range(3)], dtype=np.float64)
        if not np.isfinite(fitted).all():
            stats["linefit_skipped_nodes"] += 1
            continue
        updated_pos[node_id] = (1.0 - weight) * original_pos[node_id] + weight * fitted

    for node_id, pos in updated_pos.items():
        nodes_by_id[node_id]["z"] = float(pos[0])
        nodes_by_id[node_id]["y"] = float(pos[1])
        nodes_by_id[node_id]["x"] = float(pos[2])

    stats["linefit_smoothed_nodes"] = len(updated_pos)
    return nodes_by_id


def filter_output_graph(
    nodes_by_id: dict[int, dict[str, object]],
    raw_edges: list[dict[str, object]],
    dataset: str | None = None,
    deepcenter_bundle: dict[str, object] | None = None,
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]], dict[str, int]]:
    _stage_t0 = _time.time()
    stats = {
        "raw_edges": len(raw_edges),
        "dropped_nonconsecutive_edges": 0,
        "dropped_long_edges": 0,
        "dropped_multi_parent_edges": 0,
        "dropped_multi_child_edges": 0,
        "dropped_division_edges": 0,
        "gap_candidates": 0,
        "gap_pairs_selected": 0,
        "gap_reused_existing": 0,
        "gap_inserted_synthetic": 0,
        "gap_added_nodes": 0,
        "gap_added_edges": 0,
        "gap_skipped_node_cap": 0,
        "gap_density_nodes_scored": 0,
        "gap_density_candidates_expanded": 0,
        "gap_density_candidates_restricted": 0,
        "gap_density_selected_outside_base": 0,
        "gap_density_step_delta_milli_sum": 0,
        "gap_refined_synthetic": 0,
        "gap_refine_failed": 0,
        "gap_refine_rejected_shift": 0,
        "pruned_isolated_nodes": 0,
        "motion_relink_edges": 0,
        "motion_relink_tight_edges": 0,
        "motion_relink_relaxed_edges": 0,
        "motion_relink_frames": 0,
        "motion_relink_replaced_raw_edges": 0,
        "motion_relink_fallback_raw": 0,
        "motion_relink_skipped_large_frame": 0,
        "gap2_candidates": 0,
        "gap2_pairs_selected": 0,
        "gap2_added_nodes": 0,
        "gap2_added_edges": 0,
        "gap2_skipped_cap": 0,
        "safe_division_candidates": 0,
        "safe_division_geometric_candidates": 0,  
        "safe_divisions_added": 0,
        "safe_division_skipped_cap": 0,
        "safe_division_mutual_nn_rejected": 0,
        "safe_division_divergence_rejected": 0,
        "safe_division_symmetry_rejected": 0,  
        "deepcenter_gap_checked": 0,
        "deepcenter_gap_bypassed_strong_motion": 0,
        "deepcenter_gap_bypassed_observed_node": 0,
        "deepcenter_gap_accepted": 0,
        "deepcenter_gap_rejected": 0,
        "deepcenter_gap_missing": 0,
        "deepcenter_safe_div_checked": 0,
        "deepcenter_safe_div_accepted": 0,
        "deepcenter_safe_div_rejected": 0,
        "deepcenter_safe_div_missing": 0,
        "short_track_components_removed": 0,
        "short_track_nodes_removed": 0,
        "short_track_edges_removed": 0,
        "short_track_filter_skipped_all": 0,
        "short_track_rescue_triggered": 0,
        "short_track_rescue_components": 0,
        "short_track_rescue_nodes": 0,
        "short_track_rescue_budget": 0,
        "linefit_smoothed_nodes": 0,
        "linefit_skipped_nodes": 0,
    }

    edges: list[dict[str, object]] = []
    for edge in raw_edges:
        source = nodes_by_id.get(int(edge["source_id"]))
        target = nodes_by_id.get(int(edge["target_id"]))
        if source is None or target is None:
            continue
        if OUTPUT_ENFORCE_NEXT_FRAME and int(target["t"]) != int(source["t"]) + 1:
            stats["dropped_nonconsecutive_edges"] += 1
            continue
        distance_um = edge_distance_um(source, target)
        edge["distance_um"] = distance_um
        if OUTPUT_EDGE_MAX_UM > 0 and distance_um > OUTPUT_EDGE_MAX_UM:
            stats["dropped_long_edges"] += 1
            continue
        edges.append(edge)

    if OUTPUT_MOTION_RELINK:
        learned_edge_probs: dict[tuple[int, int], float] = {}
        for edge in edges:
            prob = edge.get("edge_prob")
            if prob is None:
                continue
            try:
                prob = float(prob)
            except (TypeError, ValueError):
                continue
            if np.isfinite(prob):
                key = (int(edge["source_id"]), int(edge["target_id"]))
                learned_edge_probs[key] = max(learned_edge_probs.get(key, float("-inf")), prob)
        motion_edges = motion_relink_edges(nodes_by_id, stats, learned_edge_probs)
        if motion_edges:
            stats["motion_relink_replaced_raw_edges"] = len(edges)
            edges = motion_edges
        else:
            stats["motion_relink_fallback_raw"] = 1

    if OUTPUT_SINGLE_PARENT_REPAIR and edges:
        best_by_target: dict[int, dict[str, object]] = {}
        for edge in edges:
            target_id = int(edge["target_id"])
            prev = best_by_target.get(target_id)
            if prev is None or edge_sort_key(edge) > edge_sort_key(prev):
                best_by_target[target_id] = edge
        kept_ids = {id(edge) for edge in best_by_target.values()}
        stats["dropped_multi_parent_edges"] = sum(1 for edge in edges if id(edge) not in kept_ids)
        edges = [edge for edge in edges if id(edge) in kept_ids]

    if OUTPUT_SINGLE_CHILD_REPAIR and edges:
        best_by_source: dict[int, dict[str, object]] = {}
        for edge in edges:
            source_id = int(edge["source_id"])
            prev = best_by_source.get(source_id)
            if prev is None or edge_sort_key(edge) > edge_sort_key(prev):
                best_by_source[source_id] = edge
        kept_ids = {id(edge) for edge in best_by_source.values()}
        stats["dropped_multi_child_edges"] = sum(1 for edge in edges if id(edge) not in kept_ids)
        edges = [edge for edge in edges if id(edge) in kept_ids]

    print(f"  [{dataset}] after edge-filter+motion-relink: {len(nodes_by_id)} nodes, {len(edges)} edges | {_time.time() - _stage_t0:.1f}s")
    repair_frame_cache: dict[int, np.ndarray] = {}
    deepcenter_heatmap_cache: dict[tuple[str, int], np.ndarray] = {}
    nodes_by_id, edges = close_single_frame_gaps(
        nodes_by_id,
        edges,
        stats,
        dataset=dataset,
        deepcenter_bundle=deepcenter_bundle,
        frame_cache=repair_frame_cache,
        deepcenter_cache=deepcenter_heatmap_cache,
    )
    nodes_by_id, edges = recover_strict_gap2(nodes_by_id, edges, stats, dataset=dataset)
    nodes_by_id, edges = fill_gaps_from_low_detections(
        nodes_by_id, edges, stats, dataset=dataset, frame_cache=repair_frame_cache,
    )
    print(f"  [{dataset}] after gap-closing (single-frame + gap2 + low-detection filler): {len(nodes_by_id)} nodes, {len(edges)} edges | {_time.time() - _stage_t0:.1f}s")
    edges = add_safe_divisions_postlink(
        nodes_by_id,
        edges,
        stats,
        dataset=dataset,
        deepcenter_bundle=deepcenter_bundle,
        frame_cache=repair_frame_cache,
        deepcenter_cache=deepcenter_heatmap_cache,
    )

    _geo_cands = stats['safe_division_geometric_candidates']
    _post_veto_cands = stats['safe_division_candidates']
    _rejected_by_dc = _geo_cands - _post_veto_cands
    print(
        f"  [{dataset}] after safe-division repair: {len(nodes_by_id)} nodes, {len(edges)} edges | {_time.time() - _stage_t0:.1f}s"
        f" (geometric_candidates={_geo_cands}, deepcenter_rejected={_rejected_by_dc},"
        f" post_veto_candidates={_post_veto_cands}, added={stats['safe_divisions_added']},"
        f" cap_skipped={stats['safe_division_skipped_cap']},"
        f" mutual_nn_rejected={stats['safe_division_mutual_nn_rejected']},"
        f" divergence_rejected={stats['safe_division_divergence_rejected']})"
    )
    if OUTPUT_DIVISION_GEOMETRY_FILTER and edges:
        by_source: dict[int, list[dict[str, object]]] = {}
        for edge in edges:
            by_source.setdefault(int(edge["source_id"]), []).append(edge)

        filtered: list[dict[str, object]] = []
        for source_id, source_edges in by_source.items():
            if len(source_edges) <= 1:
                filtered.extend(source_edges)
                continue

            ranked = sorted(source_edges, key=edge_sort_key, reverse=True)
            source = nodes_by_id[source_id]
            top1 = ranked[0]
            top2 = ranked[1]
            d1 = float(top1["distance_um"])
            d2 = float(top2["distance_um"])
            sister = edge_distance_um(nodes_by_id[int(top1["target_id"])], nodes_by_id[int(top2["target_id"])])
            valid_division = (
                max(d1, d2) <= DIV_PARENT_MAX_UM
                and sister <= DIV_SISTER_MAX_UM
                and int(nodes_by_id[int(top1["target_id"])] ["t"]) == int(source["t"]) + 1
                and int(nodes_by_id[int(top2["target_id"])] ["t"]) == int(source["t"]) + 1
            )
            if valid_division:
                filtered.extend([top1, top2])
                stats["dropped_division_edges"] += max(0, len(ranked) - 2)
            elif DIV_DROP_TO_SINGLE_IF_BAD:
                filtered.append(top1)
                stats["dropped_division_edges"] += len(ranked) - 1
            else:
                filtered.extend(ranked)
        edges = filtered

    if OUTPUT_PRUNE_ISOLATED:
        incident = {int(edge["source_id"]) for edge in edges} | {int(edge["target_id"]) for edge in edges}
        if incident:
            kept_nodes = {node_id: node for node_id, node in nodes_by_id.items() if node_id in incident}
            stats["pruned_isolated_nodes"] = len(nodes_by_id) - len(kept_nodes)
            nodes_by_id = kept_nodes
            edges = [edge for edge in edges if int(edge["source_id"]) in nodes_by_id and int(edge["target_id"]) in nodes_by_id]

    print(f"  [{dataset}] after division-geometry-filter+prune-isolated: {len(nodes_by_id)} nodes, {len(edges)} edges | {_time.time() - _stage_t0:.1f}s")
    nodes_by_id, edges = filter_short_track_components(nodes_by_id, edges, stats)
    print(f"  [{dataset}] after short-track filtering: {len(nodes_by_id)} nodes, {len(edges)} edges"
          f" (components_removed={stats['short_track_components_removed']})")
    nodes_by_id = linefit_smooth_output_graph(nodes_by_id, edges, stats)
    print(f"  [{dataset}] FINAL: {len(nodes_by_id)} nodes, {len(edges)} edges | {_time.time() - _stage_t0:.1f}s")

    return nodes_by_id, edges, stats


DEEPCENTER_VETO_DETECTOR = load_deepcenter_veto_detector()

def write_test_submission(tag: str = "base") -> None:
    
    
    geffs = sorted((REPO_DIR / "predictions").glob(f"*/{METHOD}/split_0/*.geff"))
    print(f"Found {len(geffs)} prediction graphs")
    if len(geffs) != len(test_stems):
        found = {path.stem for path in geffs}
        missing = sorted(set(test_stems) - found)
        raise RuntimeError(f"Expected {len(test_stems)} graphs, found {len(geffs)}. Missing: {missing[:10]}")

    stats_rows: list[dict[str, object]] = []
    seen_datasets: set[str] = set()
    row_id = 0
    total_nodes = 0
    total_edges = 0

    with SUBMISSION_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()

        for geff_path in geffs:
            dataset = geff_path.stem
            seen_datasets.add(dataset)
            graph = graph_from_geff(geff_path)

            nodes_by_id: dict[int, dict[str, object]] = {}
            for row in graph.node_attrs().iter_rows(named=True):
                node_id = int(row["node_id"])
                nodes_by_id[node_id] = {
                    "node_id": node_id,
                    "t": int(row["t"]),
                    "z": float(row["z"]),
                    "y": float(row["y"]),
                    "x": float(row["x"]),
                }

            raw_edges: list[dict[str, object]] = []
            for row in graph.edge_attrs().iter_rows(named=True):
                edge_prob = row.get("edge_prob") if hasattr(row, "get") else None
                raw_edges.append({
                    "source_id": int(row["source_id"]),
                    "target_id": int(row["target_id"]),
                    "edge_prob": None if edge_prob is None else float(edge_prob),
                })

            raw_node_count = len(nodes_by_id)
            _dataset_t0 = _time.time()
            if not _deadline_degraded and _dataset_t0 - KERNEL_START_TS > REPAIR_DEADLINE_S:
                _deadline_degrade()
            _nodes_snapshot = {node_id: dict(node) for node_id, node in nodes_by_id.items()}
            _edges_snapshot = [dict(edge) for edge in raw_edges]
            try:
                nodes_by_id, edges, filter_stats = filter_output_graph(nodes_by_id, raw_edges, dataset=dataset, deepcenter_bundle=DEEPCENTER_VETO_DETECTOR)
                filter_stats["repair_fallback"] = 0
                if not nodes_by_id:
                    raise AssertionError(f"{dataset}: post-processing removed every node")
            except Exception as _repair_exc:
                _traceback.print_exc()
                print(
                    f"  [{dataset}] REPAIR FAILED ({type(_repair_exc).__name__}: {_repair_exc});"
                    " writing the ILP graph with basic filtering instead",
                    flush=True,
                )
                nodes_by_id, edges, filter_stats = fallback_output_graph(_nodes_snapshot, _edges_snapshot)
            filter_stats["deadline_degraded"] = int(_deadline_degraded)
            filter_stats["repair_seconds"] = round(_time.time() - _dataset_t0, 1)
            filter_stats["kernel_elapsed_seconds"] = round(_time.time() - KERNEL_START_TS, 1)
            print(
                f"  [{dataset}] repair {_time.time() - _dataset_t0:.1f}s"
                f" | kernel elapsed {_time.time() - KERNEL_START_TS:.0f}s",
                flush=True,
            )
            if not nodes_by_id:
                raise AssertionError(f"{dataset}: post-processing removed every node")

            for node_id in sorted(nodes_by_id):
                node = nodes_by_id[node_id]
                writer.writerow({
                    "id": row_id,
                    "dataset": dataset,
                    "row_type": "node",
                    "node_id": int(node["node_id"]),
                    "t": int(node["t"]),
                    "z": max(0, int(round(float(node["z"])))),
                    "y": max(0, int(round(float(node["y"])))),
                    "x": max(0, int(round(float(node["x"])))),
                    "source_id": -1,
                    "target_id": -1,
                })
                row_id += 1

            division_sources: dict[int, int] = {}
            for edge in edges:
                source_id = int(edge["source_id"])
                target_id = int(edge["target_id"])
                if source_id not in nodes_by_id or target_id not in nodes_by_id:
                    raise AssertionError(f"{dataset}: dangling edge after filtering")
                writer.writerow({
                    "id": row_id,
                    "dataset": dataset,
                    "row_type": "edge",
                    "node_id": -1,
                    "t": -1,
                    "z": -1,
                    "y": -1,
                    "x": -1,
                    "source_id": source_id,
                    "target_id": target_id,
                })
                row_id += 1
                division_sources[source_id] = division_sources.get(source_id, 0) + 1

            node_count = len(nodes_by_id)
            edge_count = len(edges)
            total_nodes += node_count
            total_edges += edge_count
            stats_rows.append({
                "dataset": dataset,
                "raw_nodes": raw_node_count,
                "nodes": node_count,
                "raw_edges": filter_stats["raw_edges"],
                "edges": edge_count,
                "division_like_sources": sum(1 for count in division_sources.values() if count >= 2),
                "edge_to_node_ratio": edge_count / max(node_count, 1),
                "gap_added_nodes_frac": filter_stats.get("gap_added_nodes", 0) / max(raw_node_count, 1),
                **filter_stats,
            })

    expected_datasets = set(test_stems)
    missing_datasets = sorted(expected_datasets - seen_datasets)
    extra_datasets = sorted(seen_datasets - expected_datasets)
    if missing_datasets or extra_datasets:
        raise AssertionError({"missing": missing_datasets[:10], "extra": extra_datasets[:10]})
    assert row_id == total_nodes + total_edges, "Internal row counter mismatch"
    assert total_nodes > 0, "No node rows produced"

    header = SUBMISSION_PATH.open().readline().strip().split(",")
    assert header == CSV_COLUMNS, f"Bad CSV header: {header}"

    stats = pd.DataFrame(stats_rows).sort_values("dataset").reset_index(drop=True)
    stats["predict_minutes_total"] = predict_seconds / 60.0
    stats["experiment_tag"] = f"{EXPERIMENT_TAG}:{tag}"
    stats.to_csv(RUN_STATS_PATH, index=False)

    print(f"Wrote {SUBMISSION_PATH} with {row_id:,} rows")
    print(f"Node rows: {total_nodes:,} | edge rows: {total_edges:,}")
    print(f"Wrote {RUN_STATS_PATH}")
    display(pd.read_csv(SUBMISSION_PATH, nrows=8))


write_test_submission("base")

