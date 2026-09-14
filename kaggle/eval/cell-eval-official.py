# ============================================================================
# CELL (Phase B) — OFFICIAL-RULE EVAL: đo A/B ver-7 vs baseline ver-6
# ----------------------------------------------------------------------------
# Mục đích: sau khi monolith pipeline chạy xong, cell này chấm CÁC prediction
# .geff trên tập held-out bằng scorer OFFICIAL (tracking_cellmot 075fc5f — đúng
# luật chấm thật, khác rule divJ cũ của validator nội bộ) cho CẢ:
#   (a) chính ver-7 (self)   → /kaggle/working/eval_report_official_self.json
#   (b) baseline ver-6      → /kaggle/working/eval_report_official_v6.json
#       (predictions .geff gắn kèm qua dataset 'biohub-v6-heldout-preds')
# Hai file cùng schema biohub-eval-report/1 → so sánh tại local bằng compare.py.
#
# Cell KHÔNG thay đổi bất kỳ trạng thái nào của pipeline (chỉ ĐỌC predictions + GT,
# chỉ GHI 2 file JSON mới). Cell được bọc try/except toàn bộ — nếu eval lỗi, run
# vẫn COMPLETE và submission.csv vẫn hợp lệ (yêu cầu bắt buộc của code competition).
#
# Input cần gắn vào kernel:
#   - dalloliogm/biohub-official-scorer-patched  (scorer 075fc5f)
#   - vietnguyen130593/biohub-v6-heldout-preds   (4 .geff ver-6, raw, deterministic)
# Env (tuỳ chọn):
#   - BIOHUB_EVAL_STEMS         = "stem1,stem2" — ép tập stem (mặc định: val_stems
#                                  của pipeline, fallback: tự tìm mọi .geff có GT)
#   - BIOHUB_EVAL_BASELINE_DIR  = đường dẫn thư mục chứa *.geff ver-6
#                                  (mặc định: /kaggle/input/biohub-v6-heldout-preds/preds)
#   - BIOHUB_EVAL_VERSION       = nhãn version self (mặc định: ver-7)
#   - BIOHUB_EVAL_MAX_STEMS     = giới hạn số stem (mặc định 16)
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
_EVAL_VERSION = _os.environ.get("BIOHUB_EVAL_VERSION", "ver-7")
_EVAL_SCHEMA = "biohub-eval-report/1"
_EVAL_SCALE = globals().get("VOXEL_SCALE_UM") or (1.625, 0.40625, 0.40625)
_EVAL_MAX_DIST = 7.0


def _eval_find_scorer_root():
    """Tìm thư mục chứa package tracking_cellmot (scorer 075fc5f) — loại
    support-pack (bản cũ rule double-reading)."""
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
    d = globals().get("TRAIN_DIR")
    if d is not None and _Path(d).exists():
        return _Path(d)
    import os
    from pathlib import Path
    for dp, dn, fn in os.walk("/kaggle/input"):
        if "train" in dn and "test" in dn:
            return Path(dp) / "train"
    return None


def _eval_repo_dir():
    d = globals().get("REPO_DIR")
    if d is not None and _Path(d).exists():
        return _Path(d)
    return _Path("/kaggle/working/tracking_repo")


def _eval_graph(path):
    """Dùng graph_from_geff của notebook nếu có; fallback loader độc lập."""
    fn = globals().get("graph_from_geff")
    if fn is not None:
        return fn(_Path(path))
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


def _eval_find_prediction(stem):
    """Tìm .geff prediction cho stem dưới REPO_DIR/predictions (rglob)."""
    found = next((_eval_repo_dir() / "predictions").rglob(f"{stem}.geff"), None)
    return found


def _eval_num_or_none(x):
    """Chuyển giá trị số sang float; NaN/None/ko-đọc-được → None (JSON sạch)."""
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def _eval_score_one(pred_path, gt_path, td_metrics, td_div):
    """Chấm 1 (pred, gt) bằng official rule. Trả về sample row + events."""
    evaluate, node_recall, per_sample_metrics = td_metrics
    score_divisions = td_div
    t_true = _eval_estimated_true_count(gt_path)
    pred = _eval_graph(pred_path)
    gt = _eval_graph(gt_path)
    er = evaluate(pred, gt, scale=_EVAL_SCALE, max_distance=_EVAL_MAX_DIST)
    rec = node_recall(pred, gt) if (pred.num_nodes() and pred.num_edges()) else 0.0
    m = per_sample_metrics(er, t_true if t_true is not None else float("nan"), rec)

    # Division events (chi tiết per-event) — graph pred tươi để không dính match attrs
    div = score_divisions(_eval_graph(pred_path), gt,
                          scale=_EVAL_SCALE, max_distance=_EVAL_MAX_DIST)
    scores = div.scores
    div_tp = sum(int(v) for v in scores.values())
    div_fn = len(scores) - div_tp
    div_fp = len(div.fp_forks)
    events = [{"gt_div_node": int(k), "recovered": int(v)}
              for k, v in sorted(scores.items())]

    tp, fp, fn = int(m["edge_tp"]), int(m["edge_fp"]), int(m["edge_fn"])
    denom = tp + fp + fn
    ej = tp / denom if denom else None
    dj = div_tp / (div_tp + div_fp + div_fn) if (div_tp + div_fp + div_fn) else None
    ratio = _eval_num_or_none(m.get("total_node_ratio"))
    row = {
        "stem": pred_path.stem,
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
    # Kiểm chứng chéo: evaluate() đã tính division counts bên trong — báo nếu lệch
    if (int(er.division_tp), int(er.division_fp), int(er.division_fn)) != (div_tp, div_fp, div_fn):
        print(f"    [eval] NOTE division counts differ evaluate()={er.division_tp}/"
              f"{er.division_fp}/{er.division_fn} vs score_divisions()="
              f"{div_tp}/{div_fp}/{div_fn} (giữ score_divisions)")
    return row


def _eval_micro(rows):
    tp = sum(r["edge_tp"] for r in rows)
    fp = sum(r["edge_fp"] for r in rows)
    fn = sum(r["edge_fn"] for r in rows)
    w = sum(r["weight"] for r in rows) or 1
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


def _eval_report(version, rows, extra_meta):
    agg = {"official": {"micro": _eval_micro(rows)}}
    return {
        "schema": _EVAL_SCHEMA,
        "meta": {
            "version": version,
            "source": "kaggle-eval-cell",
            "rule_note": "official-075fc5f (tracking_cellmot — divJ strict topology, "
                         "đúng luật chấm thật)",
            "created_utc": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
            **extra_meta,
        },
        "samples": rows,
        "aggregate": agg,
    }


def _eval_run():
    scorer_root = _eval_find_scorer_root()
    if scorer_root is None:
        raise RuntimeError("Không tìm thấy dataset scorer (tracking_cellmot/metrics.py) "
                           "— gắn dalloliogm/biohub-official-scorer-patched vào kernel.")
    _sys.path.insert(0, str(scorer_root))
    print(f"[eval] scorer: {scorer_root}")
    from tracking_cellmot.metrics import evaluate, node_recall, per_sample_metrics
    from tracking_cellmot.division_metrics import score_divisions
    td_metrics = (evaluate, node_recall, per_sample_metrics)

    train_dir = _eval_find_train_dir()
    if train_dir is None:
        raise RuntimeError("Không tìm thấy TRAIN_DIR (thư mục train/ cạnh test/).")
    print(f"[eval] TRAIN_DIR: {train_dir}")

    # ---- tập stem --------------------------------------------------------
    env_stems = _os.environ.get("BIOHUB_EVAL_STEMS", "").strip()
    if env_stems:
        stems = [s.strip() for s in env_stems.split(",") if s.strip()]
    else:
        stems = list(globals().get("val_stems") or [])
    if not stems:
        repo_pred_root = _eval_repo_dir() / "predictions"
        if repo_pred_root.exists():
            stems = sorted({p.stem for p in repo_pred_root.rglob("*.geff")})
        else:
            stems = []
    stems = [s for s in stems if (train_dir / f"{s}.geff").exists()][:_EVAL_MAX_STEMS]
    if not stems:
        raise RuntimeError("Không có stem held-out nào (predictions chưa chạy / "
                           "VALIDATOR bị tắt?). Bỏ qua eval.")
    print(f"[eval] stems ({len(stems)}): {stems}")

    # ---- (a) self --------------------------------------------------------
    self_rows = []
    for stem in stems:
        pred_path = _eval_find_prediction(stem)
        if pred_path is None:
            print(f"[eval] THIẾU prediction cho {stem} — bỏ qua stem này")
            continue
        t0 = _time.time()
        row = _eval_score_one(pred_path, train_dir / f"{stem}.geff", td_metrics, score_divisions)
        self_rows.append(row)
        print(f"[eval] self {stem}: adjEJ={row['adjusted_edge_jaccard']:.4f} "
              f"div(tp/fp/fn)={row['div_tp']}/{row['div_fp']}/{row['div_fn']} "
              f"({_time.time() - t0:.0f}s)")
    if not self_rows:
        raise RuntimeError("Không chấm được stem nào cho self.")

    tag = globals().get("EXPERIMENT_TAG") or _EVAL_VERSION
    self_report = _eval_report(tag, self_rows, {
        "kernel_note": "ver-7 monolith (Reyhan port) — eval cell Phase B",
        "pred_root": str(_eval_repo_dir() / "predictions"),
    })
    self_path = _EVAL_OUT_DIR / "eval_report_official_self.json"
    self_path.write_text(_json.dumps(self_report, indent=2))
    print(f"[eval] ĐÃ GHI {self_path}")

    # ---- (b) baseline ver-6 ---------------------------------------------
    def _geff_dirs(d):
        return [p for p in d.glob("*.geff") if p.is_dir()]

    def _find_base_root():
        # Ưu tiên env → các dạng mount của dataset (root, datasets/<owner>/, preds/, preds.zip)
        # [FIX 13/9] kernel Kaggle có thể mount user-dataset dưới /kaggle/input/datasets/<owner>/<slug>
        # (đã thấy thực tế trong kernel ver-7: path pilkwang dạng datasets/pilkwang/...) — bổ sung
        # candidates + rglob sâu để không phụ thuộc dạng mount.
        env_dir = _os.environ.get("BIOHUB_EVAL_BASELINE_DIR", "").strip()
        if env_dir and _Path(env_dir).exists():
            return _Path(env_dir)
        roots = [_Path("/kaggle/input/biohub-v6-heldout-preds")]
        input_root = _Path("/kaggle/input")
        if input_root.exists():
            roots.extend(sorted(input_root.glob("datasets/*/biohub-v6-heldout-preds")))
            roots.extend(sorted(input_root.glob("*/biohub-v6-heldout-preds")))
        for root in roots:
            if not root.exists():
                continue
            if (root / "preds").exists() and _geff_dirs(root / "preds"):
                return root / "preds"
            z = root / "preds.zip"
            if z.exists():
                dest = _EVAL_OUT_DIR / "eval-v6-preds"
                if not dest.exists():
                    import shutil as _sh
                    dest.mkdir(parents=True, exist_ok=True)
                    _sh.unpack_archive(str(z), str(dest))
                    print(f"[eval] đã giải nén {z} → {dest}")
                return (dest / "preds") if _geff_dirs(dest / "preds") else dest
            if _geff_dirs(root):
                return root
            found = [p for p in root.rglob("*.geff") if p.is_dir()]
            if found:
                return found[0].parent
        return None

    base_dir = _find_base_root()
    base_rows = []
    if base_dir and _Path(base_dir).exists():
        for stem in stems:
            pred_path = _Path(base_dir) / f"{stem}.geff"
            if not pred_path.exists():
                continue
            t0 = _time.time()
            row = _eval_score_one(pred_path, train_dir / f"{stem}.geff",
                                  td_metrics, score_divisions)
            base_rows.append(row)
            print(f"[eval] v6   {stem}: adjEJ={row['adjusted_edge_jaccard']:.4f} "
                  f"div(tp/fp/fn)={row['div_tp']}/{row['div_fp']}/{row['div_fn']} "
                  f"({_time.time() - t0:.0f}s)")
        if base_rows:
            base_report = _eval_report("ver-6", base_rows, {
                "kernel_note": "baseline ver-6 held-out predictions (raw .geff, "
                               "deterministic v2=v3) — dataset biohub-v6-heldout-preds",
                "pred_root": str(base_dir),
            })
            base_path = _EVAL_OUT_DIR / "eval_report_official_v6.json"
            base_path.write_text(_json.dumps(base_report, indent=2))
            print(f"[eval] ĐÃ GHI {base_path}")
    else:
        print("[eval] baseline ver-6 KHÔNG gắn (thiếu dataset biohub-v6-heldout-preds) "
              "— chỉ ghi report self.")

    # ---- preview A/B ngay trong log ---------------------------------------
    print()
    print("=" * 74)
    print("EVAL PREVIEW — official rule (micro pooled) — chi tiết xem compare.py local")
    print("=" * 74)
    ms = _eval_micro(self_rows)
    _fmt = lambda v: f"{v:.4f}" if isinstance(v, (int, float)) else "  n/a"
    print(f"  self  : n={ms['n']} adjEJ={_fmt(ms['adjusted_edge_jaccard'])} "
          f"divJ={_fmt(ms['division_jaccard'])} proxy={_fmt(ms['proxy_score'])} "
          f"(tp/fp/fn {ms['edge_tp']}/{ms['edge_fp']}/{ms['edge_fn']}; "
          f"div {ms['div_tp']}/{ms['div_fp']}/{ms['div_fn']})")
    if base_rows:
        mb = _eval_micro(base_rows)
        print(f"  ver-6 : n={mb['n']} adjEJ={_fmt(mb['adjusted_edge_jaccard'])} "
              f"divJ={_fmt(mb['division_jaccard'])} proxy={_fmt(mb['proxy_score'])} "
              f"(tp/fp/fn {mb['edge_tp']}/{mb['edge_fp']}/{mb['edge_fn']}; "
              f"div {mb['div_tp']}/{mb['div_fp']}/{mb['div_fn']})")
        d_adj = (ms["adjusted_edge_jaccard"] - mb["adjusted_edge_jaccard"]) \
            if (ms["adjusted_edge_jaccard"] is not None and mb["adjusted_edge_jaccard"] is not None) else None
        d_prx = (ms["proxy_score"] - mb["proxy_score"]) \
            if (ms["proxy_score"] is not None and mb["proxy_score"] is not None) else None
        print(f"  Δ     : proxy={_fmt(d_prx)} adjEJ={_fmt(d_adj)} "
              f"div_fn={ms['div_fn'] - mb['div_fn']:+d} div_fp={ms['div_fp'] - mb['div_fp']:+d}")
        if d_adj is not None and d_adj >= 0.002:
            print("  → self TỐT HƠN baseline ≥ +0.002 trên micro official")
        elif d_adj is not None and d_adj <= -0.002:
            print("  → self KÉM baseline ≥ 0.002 — KIỂM TRA TRƯỚC KHI SUBMIT")
        else:
            print("  → chênh lệch trong dải nhiễu — xem CI bootstrap ở local (compare.py)")
    print(f"[eval] tổng thời gian eval: {(_time.time() - _EVAL_T0) / 60:.1f} phút")


try:
    _eval_run()
except Exception:
    _tb.print_exc()
    try:
        _EVAL_OUT_DIR.mkdir(parents=True, exist_ok=True)
        (_EVAL_OUT_DIR / "eval_report_error.json").write_text(_json.dumps({
            "error": _tb.format_exc()[-4000:],
            "note": "Eval cell Phase B thất bại — KHÔNG ảnh hưởng submission.csv; "
                    "run vẫn được coi là COMPLETE.",
        }, indent=2))
    except Exception:
        pass
    print("[eval] THẤT BẠI (đã nuốt lỗi — pipeline vẫn COMPLETE). Xem eval_report_error.json")
