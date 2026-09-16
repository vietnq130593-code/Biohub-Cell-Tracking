# ============================================================================
# CELL — EVAL BASELINE VER-6 (official scorer) — mini-kernel CPU
# ----------------------------------------------------------------------------
# Mục đích: bù đắp eval_report_official_v6.json thiếu trong run ver-7 v1
# (bug path dataset: kernel mount user-dataset dưới /kaggle/input/datasets/<owner>/<slug>
#  — đã vá trong cell-eval-official.py; cell này dùng cho run độc lập CPU).
#
# Chấm 4 .geff ver-6 (dataset biohub-v6-heldout-preds — raw, deterministic v2=v3,
# LB 0.945) bằng official scorer 075fc5f (dataset dalloliogm/biohub-official-scorer-patched)
# trên GT train → ghi /kaggle/working/eval_report_official_v6.json (schema biohub-eval-report/1).
# Stems truyền qua env BIOHUB_EVAL_STEMS (8 stems của ver-7 — chỉ những stem có
# prediction v6 mới được chấm, còn lại bỏ qua).
#
# Input kernel (CPU, Internet OFF, ~10-15 phút):
#   - dalloliogm/biohub-official-scorer-patched
#   - vietnguyen130593/biohub-v6-heldout-preds
#   - competition biohub-cell-tracking-during-development (GT train)
# ============================================================================
import os as _os
import sys as _sys
import json as _json
import time as _time
import traceback as _tb
from pathlib import Path as _Path

_EVAL_T0 = _time.time()
_EVAL_OUT_DIR = _Path(_os.environ.get("BIOHUB_EVAL_OUT", "/kaggle/working"))
_EVAL_MAX_STEMS = int(_os.environ.get("BIOHUB_EVAL_MAX_STEMS", "16"))
_EVAL_SCHEMA = "biohub-eval-report/1"
_EVAL_SCALE = (1.625, 0.40625, 0.40625)
_EVAL_MAX_DIST = 7.0
# 8 stems held-out của ver-7 (VALIDATOR_N_PER_TYPE=4 × 2 prefix) — truyền cứng cho deterministic
_EVAL_STEMS_DEFAULT = ("44b6_12dfb391,44b6_267148e4,44b6_2a2eff9f,44b6_341df25f,"
                      "6bba_062c8d37,6bba_07e24132,6bba_085bf656,6bba_09961292")


def _eval_find_scorer_root():
    """Tìm thư mục chứa package tracking_cellmot (scorer 075fc5f) — loại support-pack."""
    import os
    from pathlib import Path
    best = None
    for dp, dn, fn in os.walk("/kaggle/input"):
        if "support-pack" in dp:
            continue
        if "tracking_cellmot" in dn and (Path(dp) / "tracking_cellmot" / "metrics.py").is_file():
            if best is None or len(dp) < len(str(best)):
                best = Path(dp)
    return best


def _eval_find_train_dir():
    import os
    from pathlib import Path
    for dp, dn, fn in os.walk("/kaggle/input"):
        if "train" in dn and "test" in dn:
            return Path(dp) / "train"
    return None


def _eval_graph(path):
    import tracksdata as td
    g = td.graph.IndexedRXGraph.from_geff(path)
    return g[0] if isinstance(g, tuple) else g


def _eval_find_key_recursive(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _eval_find_key_recursive(v, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _eval_find_key_recursive(item, key)
            if found is not None:
                return found
    return None


def _eval_estimated_true_count(geff_path):
    for candidate in (_Path(geff_path) / "zarr.json", _Path(geff_path) / ".zattrs"):
        if not candidate.exists():
            continue
        try:
            payload = _json.loads(candidate.read_text())
        except Exception:
            continue
        found = _eval_find_key_recursive(payload, "estimated_number_of_nodes")
        if found is not None:
            try:
                return float(found)
            except (TypeError, ValueError):
                continue
    return None


def _eval_num_or_none(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _eval_score_one(pred_path, gt_path, td_metrics, td_div):
    evaluate, node_recall, per_sample_metrics = td_metrics
    score_divisions = td_div
    t_true = _eval_estimated_true_count(gt_path)
    pred = _eval_graph(pred_path)
    gt = _eval_graph(gt_path)
    er = evaluate(pred, gt, scale=_EVAL_SCALE, max_distance=_EVAL_MAX_DIST)
    rec = node_recall(pred, gt) if (pred.num_nodes() and pred.num_edges()) else 0.0
    m = per_sample_metrics(er, t_true if t_true is not None else float("nan"), rec)
    div = score_divisions(_eval_graph(pred_path), gt, scale=_EVAL_SCALE, max_distance=_EVAL_MAX_DIST)
    scores = div.scores
    div_tp = sum(int(v) for v in scores.values())
    div_fn = len(scores) - div_tp
    div_fp = len(div.fp_forks)
    events = [{"gt_div_node": int(k), "recovered": int(v)} for k, v in sorted(scores.items())]
    tp, fp, fn = int(m["edge_tp"]), int(m["edge_fp"]), int(m["edge_fn"])
    denom = tp + fp + fn
    ej = tp / denom if denom else None
    dj = div_tp / (div_tp + div_fp + div_fn) if (div_tp + div_fp + div_fn) else None
    ratio = _eval_num_or_none(m.get("total_node_ratio"))
    return {
        "stem": _Path(pred_path).stem,
        "rule": "official",
        "edge_tp": tp, "edge_fp": fp, "edge_fn": fn,
        "edge_jaccard": ej,
        "t_pred": int(m.get("num_pred_nodes") or 0),
        "t_true": t_true,
        "t_true_source": "estimated_number_of_nodes" if t_true is not None else "MISSING",
        "total_node_ratio": ratio,
        "node_multiplier_term": (0.1 * ratio) if ratio is not None else None,
        "adjusted_edge_jaccard": _eval_num_or_none(m.get("adj_edge_jaccard")),
        "node_recall": _eval_num_or_none(m.get("node_recall")),
        "div_tp": div_tp, "div_fp": div_fp, "div_fn": div_fn,
        "division_jaccard": dj,
        "weight": denom,
        "division_events": events,
    }


def _eval_micro(rows):
    tp = sum(r["edge_tp"] for r in rows)
    fp = sum(r["edge_fp"] for r in rows)
    fn = sum(r["edge_fn"] for r in rows)
    adj_rows = [r for r in rows if r.get("adjusted_edge_jaccard") is not None]
    adj = (sum(r["adjusted_edge_jaccard"] * r["weight"] for r in adj_rows)
           / sum(r["weight"] for r in adj_rows)) if adj_rows else None
    dtp = sum(r["div_tp"] for r in rows)
    dfp = sum(r["div_fp"] for r in rows)
    dfn = sum(r["div_fn"] for r in rows)
    dj = dtp / (dtp + dfp + dfn) if (dtp + dfp + dfn) else None
    return {"n": len(rows), "edge_tp": tp, "edge_fp": fp, "edge_fn": fn,
            "edge_jaccard": tp / (tp + fp + fn) if (tp + fp + fn) else None,
            "adjusted_edge_jaccard": adj,
            "div_tp": dtp, "div_fp": dfp, "div_fn": dfn, "division_jaccard": dj,
            "proxy_score": (adj if adj is not None else 0.0) + (0.1 * dj if dj is not None else 0.0),
            "division_events_total": dtp + dfp + dfn}


def _find_base_root():
    input_root = _Path("/kaggle/input")
    roots = [input_root / "biohub-v6-heldout-preds"]
    if input_root.exists():
        roots.extend(sorted(input_root.glob("datasets/*/biohub-v6-heldout-preds")))
        roots.extend(sorted(input_root.glob("*/biohub-v6-heldout-preds")))
    for root in roots:
        if not root.exists():
            continue
        if (root / "preds").exists() and [p for p in (root / "preds").glob("*.geff") if p.is_dir()]:
            return root / "preds"
        found = [p for p in root.rglob("*.geff") if p.is_dir()]
        if found:
            return found[0].parent
    return None


def _install_offline_wheels():
    """Cài tracksdata + phụ thuộc từ wheel offline trong /kaggle/input (internet OFF).

    Tái hiện đúng cách monolith ver-7 cài: pip install --no-index --no-deps --find-links
    <mọi thư mục chứa .whl> — tránh đụng numpy/scipy của Kaggle live kernel.
    (Bổ sung sau lần chạy 1 thất bại: ModuleNotFoundError tracksdata — kernel trần
    không có package; gắn thêm dataset support-pack pilkwang có wheel.)"""
    import importlib.util
    import subprocess
    import sys as _sys_local

    def _missing(mod):
        try:
            return importlib.util.find_spec(mod) is None
        except Exception:
            return True

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
    if not _missing("tracksdata"):
        print("[eval-v6] tracksdata sẵn có — bỏ qua cài đặt", flush=True)
        return
    wheel_dirs = []
    for dp, dn, fn in _os.walk("/kaggle/input"):
        if any(f.endswith(".whl") for f in fn):
            wheel_dirs.append(dp)
    if not wheel_dirs:
        raise RuntimeError("Không tìm thấy wheel .whl nào trong /kaggle/input — "
                           "gắn dataset pilkwang/biohub-tracking-support-pack-50ep-v1.")
    cmd = [_sys_local.executable, "-m", "pip", "install", "--no-index", "--no-deps",
           "--force-reinstall"]
    for d in wheel_dirs:
        cmd.extend(["--find-links", d])
    cmd.extend(specs)
    print(f"[eval-v6] cài offline từ {len(wheel_dirs)} thư mục wheel...", flush=True)
    r = subprocess.run(cmd, text=True, capture_output=True)
    if r.returncode != 0:
        print((r.stdout or "")[-1500:])
        print((r.stderr or "")[-1500:])
        raise RuntimeError("pip install offline thất bại — xem log trên.")
    print("[eval-v6] cài offline OK", flush=True)


def _eval_run():
    _install_offline_wheels()
    scorer_root = _eval_find_scorer_root()
    if scorer_root is None:
        raise RuntimeError("Không tìm thấy dataset scorer — gắn dalloliogm/biohub-official-scorer-patched.")
    _sys.path.insert(0, str(scorer_root))
    print(f"[eval-v6] scorer: {scorer_root}", flush=True)
    from tracking_cellmot.metrics import evaluate, node_recall, per_sample_metrics
    from tracking_cellmot.division_metrics import score_divisions
    td_metrics = (evaluate, node_recall, per_sample_metrics)

    train_dir = _eval_find_train_dir()
    if train_dir is None:
        raise RuntimeError("Không tìm thấy thư mục train/ (competition input thiếu?)")
    print(f"[eval-v6] TRAIN_DIR: {train_dir}", flush=True)

    env_stems = _os.environ.get("BIOHUB_EVAL_STEMS", "").strip() or _EVAL_STEMS_DEFAULT
    stems = [s.strip() for s in env_stems.split(",") if s.strip()]
    stems = [s for s in stems if (train_dir / f"{s}.geff").exists()][:_EVAL_MAX_STEMS]
    print(f"[eval-v6] stems GT tồn tại ({len(stems)}): {stems}", flush=True)

    base_dir = _find_base_root()
    if base_dir is None:
        raise RuntimeError("Không tìm thấy dataset biohub-v6-heldout-preds (đã thử mọi dạng mount).")
    print(f"[eval-v6] baseline dir: {base_dir}", flush=True)

    rows = []
    for stem in stems:
        pred_path = _Path(base_dir) / f"{stem}.geff"
        if not pred_path.exists():
            print(f"[eval-v6] {stem}: KHÔNG có prediction v6 — bỏ qua", flush=True)
            continue
        t0 = _time.time()
        row = _eval_score_one(pred_path, train_dir / f"{stem}.geff", td_metrics, score_divisions)
        rows.append(row)
        print(f"[eval-v6] {stem}: adjEJ={row['adjusted_edge_jaccard']:.4f} "
              f"div(tp/fp/fn)={row['div_tp']}/{row['div_fp']}/{row['div_fn']} "
              f"({_time.time() - t0:.0f}s)", flush=True)
    if not rows:
        raise RuntimeError("Không chấm được stem nào cho baseline v6.")

    report = {
        "schema": _EVAL_SCHEMA,
        "meta": {
            "version": "ver-6",
            "source": "kaggle-eval-baseline-cpu-kernel",
            "rule_note": "official-075fc5f (tracking_cellmot — divJ strict topology, "
                         "đúng luật chấm thật)",
            "created_utc": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            "kernel_note": "baseline ver-6 held-out predictions (raw .geff, deterministic v2=v3, "
                           "LB 0.945) — dataset biohub-v6-heldout-preds",
            "pred_root": str(base_dir),
        },
        "samples": rows,
        "aggregate": {"official": {"micro": _eval_micro(rows)}},
    }
    out = _EVAL_OUT_DIR / "eval_report_official_v6.json"
    out.write_text(_json.dumps(report, indent=2))
    print(f"[eval-v6] ĐÃ GHI {out}", flush=True)

    micro = _eval_micro(rows)
    print()
    print("=" * 74)
    print(f"BASELINE VER-6 (official rule, micro pooled): n={micro['n']} "
          f"adjEJ={micro['adjusted_edge_jaccard']:.4f} divJ={micro['division_jaccard'] if micro['division_jaccard'] is not None else float('nan'):.4f} "
          f"proxy={micro['proxy_score']:.4f}")
    print(f"  (tp/fp/fn {micro['edge_tp']}/{micro['edge_fp']}/{micro['edge_fn']}; "
          f"div {micro['div_tp']}/{micro['div_fp']}/{micro['div_fn']})")
    print(f"[eval-v6] tổng thời gian: {(_time.time() - _EVAL_T0) / 60:.1f} phút")


try:
    _eval_run()
except Exception:
    _tb.print_exc()
    try:
        _EVAL_OUT_DIR.mkdir(parents=True, exist_ok=True)
        (_EVAL_OUT_DIR / "eval_report_error.json").write_text(_json.dumps({
            "error": _tb.format_exc()[-4000:],
            "note": "Mini-kernel baseline eval thất bại.",
        }, indent=2))
    except Exception:
        pass
    print("[eval-v6] THẤT BẠI — xem eval_report_error.json")
