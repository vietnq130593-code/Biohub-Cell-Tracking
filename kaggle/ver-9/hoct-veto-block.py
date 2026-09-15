# ==== [ver9-hoct] HOCT consensus veto (post-ILP stage): arming cell ====================
# [ver9] Port nguyên văn từ cell 6 của sjlee101/biohub-lf-hoctveto-div-b (fielded mode 2).
# BIOHUB_HOCT_VETO mặc định "2" (đặt trong env block đầu monolith) — mode 2 veto cả cạnh
# division (biến thể fielded sjlee, +0.0040 CI dương trên 20 video honest). Block này cài hook
# vào write_test_submission/filter_output_graph TRƯỚC lần ghi submission.csv đầu tiên của
# monolith → veto áp dụng đúng 1 lần vào graph FINAL mỗi video test. Fail-safe một chiều:
# HOCT hỏng → video pass-through giữ graph gốc; write hỏng → hoàn tác từ backup.
# Nhập liệu: 2 dataset /kaggle/input (sjlee101/biohub-hoct-020-wheels + musculer/
# biohub-hoct-general-v0-official) — wheels cài offline (Internet OFF), weights general_v0.pt.
# Controlled by BIOHUB_HOCT_VETO, set in the configuration cell:
#   "0"  disabled: nothing below runs; submission.csv stays exactly what the base notebook wrote.
#   "1"  arm lf-hoctveto: after the notebook's own post-processing (gap closing, safe-division
#        gates, short-track filtering, line-fit smoothing) has produced the FINAL track graph of a
#        test movie, HOCT general_v0 (royerlab, arXiv 2607.11754) is run over that same node set --
#        a 3-micrometre sphere is painted around every final node, intensity features come from the
#        raw frames -- and every NON-division edge that HOCT does not also propose is dropped.
#        Nodes are never changed. Both outgoing edges of a node with two children stay untouched.
#   "2"  arm lf-hoctveto-div: as "1", but division edges are vetoed too; a daughter whose edge HOCT
#        does not propose becomes a track start (its node is kept).
# Measured offline on the honest 20 videos with the converged linker (ec_ref50_hoct_img.json):
# keeping only edges proposed by BOTH linkers gains +0.0040 [+0.0006, +0.0058], positive on both
# prefixes, and cuts scorer-visible false divisions 55 -> 29; the edge UNION loses 0.004.
#
# How it hooks in (runtime-hardened 2026-09-11, after both arms exceeded Kaggle's 12-hour limit):
# this cell only ARMS the veto. `write_test_submission` (defined in the previous cell, which also
# wrote the base submission.csv) is re-bound to a wrapper that, only while it runs, swaps
# `filter_output_graph` for a version applying the veto to its output. Nothing is re-written here.
# The veto is applied inside the notebook's FINAL write of submission.csv, exactly once:
#   - when the post-process sweep cell selects a configuration it calls write_test_submission(...)
#     itself; that call now goes through the wrapper (no extra linker pass, no extra HOCT pass);
#   - otherwise the small finalize cell inserted after the sweep (hoct_veto_finalize_cell.py) sees
#     that no wrapped write has completed and re-writes the base submission.csv once with the veto.
# The 2026-09-11 arms ran HOCT twice per video (once here on the base write, once inside the
# sweep's re-write) because this cell re-wrote immediately AND hooked the sweep; that is removed.
# Validator scoring (score_validator_config) calls filter_output_graph directly and is untouched.
#
# Wall-clock budget (environment variables, read once when this cell runs):
#   BIOHUB_HOCT_DEADLINE_H   (default 10.0)  notebook hours after which no further video is vetoed;
#   BIOHUB_HOCT_MAX_VIDEO_S  (default 900)  a video whose predicted HOCT time exceeds this is skipped.
# Predicted HOCT time per video = 9 s per 1,000 final nodes + 10 s (fit on the 2026-09-11 public
# runs on a T4: 6,151 nodes 58 s, 20,727 nodes 119 s, 25,622 nodes 148 s, 70,251 nodes 640 s).
# A video is skipped -- its base graph is written unchanged -- when the prediction is above the
# per-video cap, when the deadline has passed, or when elapsed + prediction would pass it. The
# chunked retries after a solver failure re-check the deadline before each retry.
# Elapsed time = age of this Python process, read from /proc/self/stat (the IPython kernel process
# runs every cell, so its start is the session start); when PID 1 (the container's init) started at
# most one hour earlier its age is used instead, since it also covers the seconds before the kernel
# came up. Without /proc the time since this cell ran plus the detector's own timer is used and the
# summary says so (that fallback under-estimates).
# Fail-safe: a per-video HOCT failure keeps that video's base graph; when HOCT cannot be installed
# or loaded every video is passed through; when the wrapped write itself fails, submission.csv and
# run_stats.csv are restored from a backup taken before the write and the exception is swallowed, so
# the notebook completes with a valid file. The previous submission.csv is kept next to the final one
# as submission_before_hoct_veto.csv for inspection. One HOCT_VETO_SUMMARY line (videos vetoed /
# skipped for budget / failed, elapsed seconds, deadline) is printed by the finalize cell.
import glob as _hv_glob
import hashlib as _hv_hashlib
import math as _hv_math
import os as _hv_os
import shutil as _hv_shutil
import subprocess as _hv_subprocess
import sys as _hv_sys
import time as _hv_time
import traceback as _hv_traceback
from collections import Counter as _hv_Counter

import numpy as _hv_np

_HV_MODE = int(_hv_os.environ.get("BIOHUB_HOCT_VETO", "0"))
_HV_DEADLINE_H = float(_hv_os.environ.get("BIOHUB_HOCT_DEADLINE_H", "10.0"))
_HV_MAX_VIDEO_S = float(_hv_os.environ.get("BIOHUB_HOCT_MAX_VIDEO_S", "900"))
_HV_SEC_PER_1000_NODES = 9.0      # slope of the predicted HOCT time (see the header)
_HV_FIXED_S = 10.0                # intercept: sphere painting, volume read, graph conversion
_HV_SCALE_ZYX = (1.625, 0.40625, 0.40625)
_HV_RADIUS_UM = 3.0
_HV_TILE, _HV_OVERLAP = (5, 32, 128, 128), (1, 8, 16, 16)
_HV_MAX_DELTA_T = 1
_HV_BACKUP_SUFFIX = ".hoct_veto_backup"
_HV_KEEP_PREVIOUS_NAME = "submission_before_hoct_veto.csv"
_HV_STATE: dict = {
    "model": None, "cache": {}, "totals": None,
    "counts": {"vetoed": 0, "skipped_budget": 0, "failed": 0, "write_failures": 0},
    "applied_writes": 0,            # wrapped writes of submission.csv that completed
    "disabled_reason": None,        # set when HOCT cannot be installed/loaded: later videos fail fast
    "hoct_seconds": 0.0,            # wall time spent inside the HOCT stage (all videos)
    "t_import_monotonic": _hv_time.monotonic(),
    "clock": None,                  # elapsed-time source actually used (for the summary line)
}


def _hv_log(msg: str) -> None:
    print(f"[hoct_veto {_hv_time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------- pure graph logic (unit-tested offline)

def _hv_apply_veto(edges: list, hoct_pairs: set, mode: int) -> tuple[list, dict]:
    """Drop pipeline edges that HOCT does not propose.

    edges      : the notebook's edge dicts (source_id, target_id, ...).
    hoct_pairs : set of (source_id, target_id) in the pipeline's node ids.
    mode       : 1 keeps both edges of every node with >= 2 children untouched; 2 vetoes all edges.
    Returns (kept edges, counters).
    """
    out_deg = _hv_Counter(int(e["source_id"]) for e in edges)
    kept = []
    for e in edges:
        s, t = int(e["source_id"]), int(e["target_id"])
        if (s, t) in hoct_pairs or (mode == 1 and out_deg[s] >= 2):
            kept.append(e)
    out_deg_after = _hv_Counter(int(e["source_id"]) for e in kept)
    counters = {
        "edges_before": len(edges), "edges_after": len(kept), "removed": len(edges) - len(kept),
        "divisions_before": sum(1 for v in out_deg.values() if v >= 2),
        "divisions_after": sum(1 for v in out_deg_after.values() if v >= 2),
    }
    return kept, counters


def _hv_snap_to_nodes(t: _hv_np.ndarray, zyx: _hv_np.ndarray, det: _hv_np.ndarray) -> _hv_np.ndarray:
    """Index of the nearest node (same frame, micrometre distance) for every HOCT node; one-to-one."""
    from scipy.spatial import cKDTree
    scale = _hv_np.asarray(_HV_SCALE_ZYX)
    idx_out = _hv_np.full(len(t), -1, dtype=int)
    for tt in _hv_np.unique(t):
        sel = _hv_np.where(t == tt)[0]
        det_sel = _hv_np.where(det[:, 0].astype(int) == int(tt))[0]
        if len(det_sel) == 0:
            raise RuntimeError(f"HOCT node at frame {tt} but no pipeline node there")
        dist, k = cKDTree(det[det_sel, 1:] * scale).query(zyx[sel] * scale, k=1)
        idx_out[sel] = det_sel[k]
    if len(_hv_np.unique(idx_out)) != len(idx_out):
        raise RuntimeError("HOCT nodes do not map one-to-one onto pipeline nodes")
    return idx_out


# ---------------------------------------------------------------- wall-clock budget (unit-tested offline)

def _hv_proc_age_s(pid) -> "float | None":
    """Seconds since process `pid` started: /proc/<pid>/stat field 22 (start time in clock ticks after
    boot) against /proc/uptime. None when unreadable (no /proc, no such process)."""
    try:
        with open(f"/proc/{pid}/stat") as fh:
            stat = fh.read()
        start_ticks = int(stat[stat.rindex(")") + 2:].split()[19])
        with open("/proc/uptime") as fh:
            uptime = float(fh.read().split()[0])
        return uptime - start_ticks / _hv_os.sysconf("SC_CLK_TCK")
    except Exception:
        return None


def _hv_notebook_elapsed_s() -> float:
    """Seconds since the notebook session started (see the header for the reasoning)."""
    self_age = _hv_proc_age_s("self")
    if self_age is not None:
        init_age = _hv_proc_age_s(1)
        if init_age is not None and self_age <= init_age <= self_age + 3600.0:
            _HV_STATE["clock"] = "/proc/1/stat"
            return init_age
        _HV_STATE["clock"] = "/proc/self/stat"
        return self_age
    _HV_STATE["clock"] = "cell-relative+predict_seconds (no /proc; under-estimates)"
    detector = globals().get("predict_seconds", 0.0)
    return _hv_time.monotonic() - _HV_STATE["t_import_monotonic"] + float(detector or 0.0)


def _hv_estimate_s(n_nodes: int) -> float:
    """Predicted HOCT wall time for one video from its final node count."""
    return _HV_SEC_PER_1000_NODES * n_nodes / 1000.0 + _HV_FIXED_S


def _hv_budget_decision(n_nodes: int, elapsed_s: float, deadline_s: float, max_video_s: float) -> tuple[str, float]:
    """Pure budget rule. Returns (decision, predicted seconds); decision is "run", "skip_video_cap"
    (prediction above the per-video cap) or "skip_deadline" (deadline passed, or elapsed + prediction
    would pass it). Every video is judged on its own, so a small video can still run late."""
    est = _hv_estimate_s(n_nodes)
    if est > max_video_s:
        return "skip_video_cap", est
    if elapsed_s >= deadline_s or elapsed_s + est > deadline_s:
        return "skip_deadline", est
    return "run", est


# ---------------------------------------------------------------- HOCT plumbing (Kaggle only)

def _hv_find(pattern: str) -> str:
    hits = sorted(set(_hv_glob.glob(f"/kaggle/input/{pattern}") + _hv_glob.glob(f"/kaggle/input/*/{pattern}")
                      + _hv_glob.glob(f"/kaggle/input/*/*/{pattern}") + _hv_glob.glob(f"/kaggle/input/*/*/*/{pattern}")))
    if not hits:
        raise FileNotFoundError(f"HOCT veto: nothing matches /kaggle/input/**/{pattern}")
    return hits[0]


def _hv_install_and_load():
    if _HV_STATE["model"] is not None:
        return _HV_STATE["model"]
    wheel_dir = _hv_os.path.dirname(_hv_find("hoct-0.2.0-py3-none-any.whl"))
    weights = _hv_find("general_v0.pt")
    cmd = [_hv_sys.executable, "-m", "pip", "install", "--quiet", "--no-index", "--no-deps",
           "--find-links", wheel_dir, "hoct==0.2.0", "spatial-graph==0.1.1", "pooch==1.9.0"]
    _hv_log("installing offline wheels from " + wheel_dir)
    _hv_subprocess.run(cmd, check=True)
    import importlib
    importlib.invalidate_caches()
    import hoct  # noqa: E402
    import torch  # noqa: E402
    from hoct import load_model
    model = load_model(weights, device="cuda")
    _hv_log(f"hoct {hoct.__version__} loaded general_v0 from {weights} "
            f"({sum(p.numel() for p in model.parameters()) / 1e6:.2f} M params)")
    _HV_STATE["model"] = model
    return model


def _hv_release_gpu() -> None:
    """Return cached GPU memory after a failure so the notebook's own models are not squeezed."""
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _hv_rasterize_spheres(det: _hv_np.ndarray, shape: tuple) -> _hv_np.ndarray:
    """One 3-um anisotropic sphere per node; labels 1..K per frame; overlaps go to the nearest centre."""
    T, Z, Y, X = shape
    labels = _hv_np.zeros(shape, dtype=_hv_np.int16)
    sz, sy, sx = _HV_SCALE_ZYX
    rz, ry, rx = (int(_hv_math.ceil(_HV_RADIUS_UM / s)) for s in _HV_SCALE_ZYX)
    r2 = _HV_RADIUS_UM ** 2
    t_all = det[:, 0].astype(int)
    for t in range(T):
        rows = det[t_all == t]
        if len(rows) > 32000:
            raise RuntimeError(f"frame {t}: {len(rows)} nodes exceed the int16 label range")
        best = _hv_np.full((Z, Y, X), _hv_np.inf, dtype=_hv_np.float32)
        lab = labels[t]
        for k, (_, cz, cy, cx) in enumerate(rows, start=1):
            z0, z1 = max(0, int(_hv_math.floor(cz)) - rz), min(Z, int(_hv_math.ceil(cz)) + rz + 1)
            y0, y1 = max(0, int(_hv_math.floor(cy)) - ry), min(Y, int(_hv_math.ceil(cy)) + ry + 1)
            x0, x1 = max(0, int(_hv_math.floor(cx)) - rx), min(X, int(_hv_math.ceil(cx)) + rx + 1)
            if z0 >= z1 or y0 >= y1 or x0 >= x1:
                continue
            zz = (_hv_np.arange(z0, z1) - cz) * sz
            yy = (_hv_np.arange(y0, y1) - cy) * sy
            xx = (_hv_np.arange(x0, x1) - cx) * sx
            d2 = (zz[:, None, None] ** 2 + yy[None, :, None] ** 2 + xx[None, None, :] ** 2).astype(_hv_np.float32)
            sub_best = best[z0:z1, y0:y1, x0:x1]
            hit = (d2 <= r2) & (d2 < sub_best)
            sub_best[hit] = d2[hit]
            lab[z0:z1, y0:y1, x0:x1][hit] = k
    return labels


def _hv_read_volume(dataset: str) -> _hv_np.ndarray:
    """Raw (T, Z, Y, X) uint16 frames of a test movie via the notebook's own frame reader."""
    zarr_path = TEST_DIR / f"{dataset}.zarr"
    meta = json.loads((zarr_path / "0" / "zarr.json").read_text())
    T = int(meta["shape"][0])
    cache: dict = {}
    frames = [read_test_frame(dataset, t, cache) for t in range(T)]
    return _hv_np.stack(frames, axis=0)


def _hv_predict_pairs(model, labels, images, det, ids, n_chunks: int) -> set:
    """Run HOCT (whole movie, or n_chunks overlapping runs of frames stitched at the seams) and return
    its proposed edges as (source_id, target_id) pairs in the pipeline's node ids."""
    import torch
    from hoct import predict
    from tracksdata.functional import TilingScheme
    T = labels.shape[0]
    starts = [round(i * T / n_chunks) for i in range(n_chunks)] + [T]
    pairs: set = set()
    for i in range(n_chunks):
        s, e_own = starts[i], starts[i + 1]
        e_frames = min(T, e_own + 1)
        sub = _hv_np.where((det[:, 0] >= s) & (det[:, 0] < e_frames))[0]
        det_sub = det[sub].copy()
        det_sub[:, 0] -= s
        with torch.inference_mode():
            sol = predict(model, labels=labels[s:e_frames], images=None if images is None else images[s:e_frames],
                          scale=(1.0, *_HV_SCALE_ZYX), max_delta_t=_HV_MAX_DELTA_T,
                          tiling_scheme=TilingScheme(tile_shape=_HV_TILE, overlap_shape=_HV_OVERLAP))
        nodes = sol.node_attrs(attr_keys=["node_id", "t", "z", "y", "x"])
        edges = sol.edge_attrs(attr_keys=[])
        t_loc = nodes["t"].to_numpy().astype(int)
        zyx = _hv_np.stack([nodes[c].to_numpy() for c in ("z", "y", "x")], 1).astype(float)
        snap = _hv_snap_to_nodes(t_loc, zyx, det_sub)          # index into det_sub
        hoct_to_pid = {int(n): int(ids[sub[k]]) for n, k in zip(nodes["node_id"].to_list(), snap)}
        src_t = {int(n): int(tt) + s for n, tt in zip(nodes["node_id"].to_list(), t_loc)}
        for a, b in zip(edges["source_id"].to_list(), edges["target_id"].to_list()):
            if s <= src_t[int(a)] < e_own:                    # this run owns edges whose source is in [s, e_own)
                pairs.add((hoct_to_pid[int(a)], hoct_to_pid[int(b)]))
        del sol
        torch.cuda.empty_cache()
    return pairs


def _hv_hoct_pairs(dataset: str, nodes_by_id: dict) -> set:
    ids = _hv_np.array(sorted(nodes_by_id), dtype=int)
    det = _hv_np.array([[float(nodes_by_id[i]["t"]), float(nodes_by_id[i]["z"]),
                         float(nodes_by_id[i]["y"]), float(nodes_by_id[i]["x"])] for i in ids])
    key = (dataset, _hv_hashlib.sha256(det.tobytes()).hexdigest())
    if key in _HV_STATE["cache"]:
        _hv_log(f"[{dataset}] HOCT edges reused from cache (identical final node set)")
        return _HV_STATE["cache"][key]
    model = _hv_install_and_load()
    t0 = _hv_time.time()
    volume = _hv_read_volume(dataset)
    labels = _hv_rasterize_spheres(det, volume.shape)
    _hv_log(f"[{dataset}] {len(ids)} final nodes -> spheres r={_HV_RADIUS_UM} um, volume {volume.shape} read+painted in {_hv_time.time() - t0:.0f}s")
    pairs = None
    deadline_s = _HV_DEADLINE_H * 3600.0
    for n_chunks in (1, 2, 4):
        if n_chunks > 1:
            elapsed = _hv_notebook_elapsed_s()
            if elapsed + _hv_estimate_s(len(ids)) > deadline_s:
                raise RuntimeError(f"HOCT retry with {n_chunks} chunks refused: elapsed {elapsed:.0f}s plus "
                                   f"the predicted {_hv_estimate_s(len(ids)):.0f}s would pass the {deadline_s:.0f}s deadline")
        try:
            t1 = _hv_time.time()
            pairs = _hv_predict_pairs(model, labels, volume, det, ids, n_chunks)
            _hv_log(f"[{dataset}] HOCT proposed {len(pairs)} edges in {_hv_time.time() - t1:.0f}s (time chunks={n_chunks})")
            break
        except RuntimeError as exc:   # tracksdata raises RuntimeError when SCIP cannot solve the whole-movie ILP
            _hv_log(f"[{dataset}] HOCT with {n_chunks} chunk(s) failed: {str(exc)[:160]}; retrying with more chunks")
            _hv_release_gpu()
    if pairs is None:
        raise RuntimeError(f"HOCT_VETO_FAILED {dataset}: HOCT produced no solution")
    _HV_STATE["cache"][key] = pairs
    return pairs


# ---------------------------------------------------------------- one video: budget, veto, fail-safe

def _hv_veto_video(dataset: str, nodes_by_id: dict, edges: list) -> tuple[list, dict]:
    """Apply the veto to one video's FINAL graph, or leave it untouched. Never raises.

    Returns (edges, counters); counters carries "status" -- vetoed / skip_deadline / skip_video_cap /
    failed -- and the edge and division counts (unchanged counts when the graph passed through).
    """
    n_nodes = len(nodes_by_id)
    counts = _HV_STATE["counts"]
    out_deg = _hv_Counter(int(e["source_id"]) for e in edges)
    untouched = {"edges_before": len(edges), "edges_after": len(edges), "removed": 0,
                 "divisions_before": sum(1 for v in out_deg.values() if v >= 2)}
    untouched["divisions_after"] = untouched["divisions_before"]

    if n_nodes == 0 or not edges:            # nothing HOCT could veto; do not spend a run on it
        counts["vetoed"] += 1
        print(f"HOCT_VETO_DATASET mode={_HV_MODE} dataset={dataset} edges_before={len(edges)} edges_after={len(edges)} "
              f"removed=0 divisions_before={untouched['divisions_before']} divisions_after={untouched['divisions_after']}", flush=True)
        return edges, {**untouched, "status": "vetoed"}

    if _HV_STATE["disabled_reason"] is not None:
        counts["failed"] += 1
        print(f"HOCT_VETO_FAILED mode={_HV_MODE} dataset={dataset} nodes={n_nodes} reason=hoct_unavailable "
              f"({_HV_STATE['disabled_reason']}); base graph kept", flush=True)
        return edges, {**untouched, "status": "failed"}

    elapsed = _hv_notebook_elapsed_s()
    deadline_s = _HV_DEADLINE_H * 3600.0
    decision, est = _hv_budget_decision(n_nodes, elapsed, deadline_s, _HV_MAX_VIDEO_S)
    if decision != "run":
        counts["skipped_budget"] += 1
        print(f"HOCT_VETO_SKIPPED mode={_HV_MODE} dataset={dataset} reason={decision} nodes={n_nodes} predicted_s={est:.0f} "
              f"elapsed_s={elapsed:.0f} deadline_s={deadline_s:.0f} max_video_s={_HV_MAX_VIDEO_S:.0f}; base graph kept", flush=True)
        return edges, {**untouched, "status": decision}

    t0 = _hv_time.time()
    try:
        _hv_install_and_load()
    except Exception as exc:
        _HV_STATE["disabled_reason"] = f"{type(exc).__name__}: {str(exc)[:160]}"
        counts["failed"] += 1
        _hv_log("HOCT could not be installed or loaded; every video passes through unchanged\n" + _hv_traceback.format_exc())
        print(f"HOCT_VETO_FAILED mode={_HV_MODE} dataset={dataset} nodes={n_nodes} reason=install_or_load "
              f"({_HV_STATE['disabled_reason']}); base graph kept", flush=True)
        _hv_release_gpu()
        return edges, {**untouched, "status": "failed"}

    try:
        hoct_pairs = _hv_hoct_pairs(dataset, nodes_by_id)
        kept, c = _hv_apply_veto(edges, hoct_pairs, _HV_MODE)
    except Exception as exc:
        spent = _hv_time.time() - t0
        _HV_STATE["hoct_seconds"] += spent
        counts["failed"] += 1
        _hv_log(f"[{dataset}] HOCT veto FAILED after {spent:.0f}s; base graph kept\n" + _hv_traceback.format_exc())
        print(f"HOCT_VETO_FAILED mode={_HV_MODE} dataset={dataset} nodes={n_nodes} reason={type(exc).__name__} "
              f"seconds={spent:.0f}; base graph kept", flush=True)
        _hv_release_gpu()
        return edges, {**untouched, "status": "failed"}

    _HV_STATE["hoct_seconds"] += _hv_time.time() - t0
    counts["vetoed"] += 1
    print(f"HOCT_VETO_DATASET mode={_HV_MODE} dataset={dataset} edges_before={c['edges_before']} "
          f"edges_after={c['edges_after']} removed={c['removed']} divisions_before={c['divisions_before']} "
          f"divisions_after={c['divisions_after']}", flush=True)
    return kept, {**c, "status": "vetoed"}


# ---------------------------------------------------------------- backup of the previous outputs

def _hv_output_paths() -> list:
    """submission.csv and run_stats.csv as written by the notebook (globals from the paths cell)."""
    out = []
    for name in ("SUBMISSION_PATH", "RUN_STATS_PATH"):
        p = globals().get(name)
        if p is not None:
            out.append(str(p))
    return out


def _hv_backup_outputs() -> dict:
    """Copy the current outputs to <file>.hoct_veto_backup so a failed write can be undone.
    Returns {original path: backup path} for the files that existed."""
    backup: dict = {}
    for p in _hv_output_paths():
        try:
            if _hv_os.path.isfile(p):
                b = p + _HV_BACKUP_SUFFIX
                _hv_shutil.copy2(p, b)
                backup[p] = b
        except Exception as exc:
            _hv_log(f"could not back up {p}: {type(exc).__name__}: {exc}")
    return backup


def _hv_restore_outputs(backup: dict) -> bool:
    """Put the backed-up files back (os.replace is atomic on one filesystem). True when submission.csv
    was restored."""
    restored_submission = False
    submission = str(globals().get("SUBMISSION_PATH", ""))
    for p, b in backup.items():
        try:
            _hv_os.replace(b, p)
            if p == submission:
                restored_submission = True
        except Exception as exc:
            _hv_log(f"could not restore {p} from {b}: {type(exc).__name__}: {exc}")
    return restored_submission


def _hv_keep_previous_submission(backup: dict) -> None:
    """After a successful wrapped write: keep the previous submission.csv next to the final one for
    inspection (submission_before_hoct_veto.csv) and drop the other backups."""
    submission = str(globals().get("SUBMISSION_PATH", ""))
    for p, b in backup.items():
        try:
            if p == submission:
                _hv_os.replace(b, _hv_os.path.join(_hv_os.path.dirname(p), _HV_KEEP_PREVIOUS_NAME))
            else:
                _hv_os.remove(b)
        except Exception as exc:
            _hv_log(f"could not tidy backup {b}: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------- hook into write_test_submission

def _hv_install_hook() -> None:
    orig_write = write_test_submission
    orig_filter = filter_output_graph

    def veto_filter_output_graph(nodes_by_id, raw_edges, *args, **kwargs):
        nodes_by_id, edges, stats = orig_filter(nodes_by_id, raw_edges, *args, **kwargs)
        try:
            dataset = kwargs.get("dataset") if "dataset" in kwargs else (args[0] if args else None)
            edges, c = _hv_veto_video(str(dataset), nodes_by_id, edges)       # never raises
            stats["hoct_veto_status"] = c["status"]
            stats["hoct_veto_removed_edges"] = c["removed"]
            stats["hoct_veto_divisions_before"] = c["divisions_before"]
            stats["hoct_veto_divisions_after"] = c["divisions_after"]
            tot = _HV_STATE["totals"]
            for k in ("edges_before", "edges_after", "removed", "divisions_before", "divisions_after"):
                tot[k] = tot.get(k, 0) + c[k]
        except Exception:
            _hv_log("bookkeeping error in the veto hook; the graph is passed through as post-processed\n" + _hv_traceback.format_exc())
        return nodes_by_id, edges, stats

    def write_test_submission_with_veto(tag: str = "base"):
        _HV_STATE["totals"] = {}
        backup = _hv_backup_outputs()
        globals()["filter_output_graph"] = veto_filter_output_graph
        try:
            result = orig_write(tag)
        except Exception as exc:
            globals()["filter_output_graph"] = orig_filter
            _HV_STATE["counts"]["write_failures"] += 1
            restored = _hv_restore_outputs(backup)
            _hv_log(f"write_test_submission({tag!r}) FAILED with the veto hooked; previous outputs restored={restored}\n"
                    + _hv_traceback.format_exc())
            if not restored:
                _hv_log("no previous submission.csv to fall back on; re-running the notebook's own write without the veto")
                return orig_write(tag)
            print(f"HOCT_VETO_WRITE_FAILED mode={_HV_MODE} tag={tag} error={type(exc).__name__} "
                  f"restored_previous_submission=True", flush=True)
            return None
        finally:
            globals()["filter_output_graph"] = orig_filter
        _hv_keep_previous_submission(backup)
        _HV_STATE["applied_writes"] += 1
        c = _HV_STATE["totals"]
        cnt = _HV_STATE["counts"]
        print(f"HOCT_VETO_ACTIVE mode={_HV_MODE} edges_before={c.get('edges_before', 0)} edges_after={c.get('edges_after', 0)} "
              f"removed={c.get('removed', 0)} divisions_before={c.get('divisions_before', 0)} "
              f"divisions_after={c.get('divisions_after', 0)}", flush=True)
        if c.get("removed", 0) == 0:
            print(f"HOCT_VETO_NO_OP mode={_HV_MODE}: no edge removed (vetoed={cnt['vetoed']} skipped_budget={cnt['skipped_budget']} "
                  f"failed={cnt['failed']}); submission.csv equals the notebook's own write", flush=True)
        return result

    globals()["write_test_submission"] = write_test_submission_with_veto


# ---------------------------------------------------------------- finalize (called from the finalize cell)

def _hv_print_summary() -> None:
    c = _HV_STATE["counts"]
    elapsed = _hv_notebook_elapsed_s()
    print(f"HOCT_VETO_SUMMARY mode={_HV_MODE} vetoed={c['vetoed']} skipped_budget={c['skipped_budget']} failed={c['failed']} "
          f"write_failures={c['write_failures']} applied_writes={_HV_STATE['applied_writes']} "
          f"hoct_seconds={_HV_STATE['hoct_seconds']:.0f} elapsed_s={elapsed:.0f} deadline_h={_HV_DEADLINE_H} "
          f"max_video_s={_HV_MAX_VIDEO_S:.0f} clock={_HV_STATE['clock']}", flush=True)


def _hv_finalize() -> None:
    """Run after the post-process sweep. If the sweep re-wrote submission.csv the veto is already in
    it; if it kept the base file, re-write that file once with the veto. Never raises."""
    if _HV_MODE not in (1, 2):
        return
    try:
        if _HV_STATE["applied_writes"] > 0:
            _hv_log("the veto was applied inside the sweep's re-write of submission.csv; nothing to re-write")
        elif _HV_STATE["counts"]["write_failures"] > 0:
            _hv_log("a wrapped write failed earlier and the previous submission.csv was restored; not retrying")
        else:
            _hv_log("the sweep kept the base submission.csv: re-writing it once with the HOCT consensus veto")
            write_test_submission("base")
    except Exception:
        _HV_STATE["counts"]["write_failures"] += 1
        _hv_log("finalize failed; submission.csv is whatever the notebook wrote last\n" + _hv_traceback.format_exc())
    _hv_print_summary()


# ---------------------------------------------------------------- cell entry point
if _HV_MODE == 0:
    print("HOCT_VETO_DISABLED mode=0 (base behaviour; submission.csv unchanged)", flush=True)
elif _HV_MODE in (1, 2):
    _hv_install_hook()
    _hv_elapsed_at_arming = _hv_notebook_elapsed_s()
    print(f"HOCT_VETO_ARMED mode={_HV_MODE} ({'division edges protected' if _HV_MODE == 1 else 'division edges vetoed too'}) "
          f"elapsed_s={_hv_elapsed_at_arming:.0f} deadline_h={_HV_DEADLINE_H} max_video_s={_HV_MAX_VIDEO_S:.0f} "
          f"clock={_HV_STATE['clock']}; applied inside the notebook's final write of submission.csv", flush=True)
else:
    raise RuntimeError(f"BIOHUB_HOCT_VETO must be 0, 1 or 2, got {_HV_MODE!r}")
