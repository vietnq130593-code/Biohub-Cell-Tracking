#!/usr/bin/env python3
"""build-machinery-ledger.py — Sinh machinery-ledger.json từ banked reference v11.

Nguyên tắc KHÔNG SAO CHÉP TAY: mọi số liệu lấy trực tiếp từ artifact thật
(monolith v11 + run_stats.csv + submission.csv của kernel biohub-ver11, LB 0.947,
ref 56473159... không, ref v11 = 56403231) → ledger là "ảnh chụp" máy đang chạy
đúng, không phải ghi nhớ con người.

Ledger phục vụ machinery-audit.py (gate cứng trước submit — xem ERRORS-LEDGER.md L13).

Chạy:
  python3 build-machinery-ledger.py \
    --monolith /home/z/v11-recovery/ver11-kernel/ver11-monolith.py \
    --run-stats /home/z/v11-recovery/ver11-output/run_stats.csv \
    --submission /home/z/v11-recovery/ver11-output/submission.csv \
    --out machinery-ledger.json
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- env extraction

ASSIGN_RE = re.compile(r"os\.environ\['(BIOHUB_[A-Z0-9_]+)'\]\s*=\s*'([^']*)'")
READ_RE = re.compile(r"os\.environ\.get\('(BIOHUB_[A-Z0-9_]+)',\s*'([^']*)'\)")


def extract_env(path: Path) -> tuple[dict, dict]:
    """Trả về (effective_env, read_defaults). Last-write-wins cho assignment."""
    src = path.read_text()
    effective: dict[str, str] = {}
    for k, v in ASSIGN_RE.findall(src):
        effective[k] = v
    defaults: dict[str, str] = {}
    for k, v in READ_RE.findall(src):
        defaults.setdefault(k, v)
    # áp default cho key chưa được set tường minh
    full = dict(effective)
    for k, v in defaults.items():
        full.setdefault(k, v)
    return full, defaults


def norm(v: str) -> float | str:
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


# ---------------------------------------------------------------- receipts + census


def receipts_sum(run_stats: Path) -> dict[str, float]:
    rows = list(csv.DictReader(open(run_stats)))
    out: dict[str, float] = {}
    for key in rows[0]:
        try:
            out[key] = sum(float(r[key] or 0) for r in rows)
        except ValueError:
            continue
    out["__datasets"] = len(rows)
    return out


def census(submission: Path) -> dict[str, int]:
    children: dict[tuple, set] = defaultdict(set)
    parents: dict[tuple, set] = defaultdict(set)
    nodes: set = set()
    datasets: set = set()
    edges = 0
    bad_rows = 0
    for row in csv.DictReader(open(submission)):
        ds = row.get("dataset", "")
        datasets.add(ds)
        if row.get("row_type") == "node":
            nodes.add((ds, row.get("node_id")))
        elif row.get("row_type") == "edge":
            edges += 1
            children[(ds, row.get("source_id"))].add(row.get("target_id"))
            parents[(ds, row.get("target_id"))].add(row.get("source_id"))
        else:
            bad_rows += 1
    forks = sum(1 for ks in children.values() if len(ks) > 1)
    multi_parent = sum(1 for ps in parents.values() if len(ps) > 1)
    return {
        "nodes": len(nodes),
        "edges": edges,
        "forks": forks,
        "multi_parent": multi_parent,
        "datasets": len(datasets),
        "bad_rows": bad_rows,
    }


# ---------------------------------------------------------------- knob provenance

# Phân loại knob theo bằng chứng LB (nguồn: ERRORS-LEDGER.md L13 + bảng env-diff 23/9).
# must_on      : tắt = mất kênh điểm (L13c) — HARD, không bao giờ ack.
# lb_proven_noop: đổi giá trị đã có receipts+bằng chứng LB không đổi điểm.
# lb_proven_inert: knockout 0-firing (receipts=0 mọi bản ≥0.946).
# hypothesis   : giả thuyết chưa từng đứng một mình trên LB — ack được (--ack).
# reference    : phải bằng giá trị banked; khác = UNCLASSIFIED (phải cập nhật ledger).
KNOB_PROVENANCE = {
    "BIOHUB_OUTPUT_SAFE_DIVISIONS": {
        "class": "must_on",
        "rule": "value != '0'",
        "evidence": "v11 82 safe-div/144 forks→0.947; v13.1 OFF/0 forks→0.911 (ref 56473159); variant A 0 forks→0.911 (ref 56373784). forks=0 mất ≈0.036.",
    },
    "BIOHUB_REPARENT_ENABLE": {
        "class": "must_on",
        "rule": "value != '0'",
        "evidence": "v11/v12.1 reparent_added=77/77 giữ 0.947/0.946; v13.1 OFF→0.911 (cặp SR0).",
    },
    "BIOHUB_REPARENT_EDGE_PROB": {
        "class": "lb_proven_noop",
        "allowed": ["0.25", "0.4"],
        "evidence": "EP 0.25 (v11) vs 0.4 (v12.1): reparent_added 77=77, LB 0.947 vs 0.946 (delta do knobs khác).",
    },
    "BIOHUB_GAP_CLOSE_UM": {
        "class": "hypothesis",
        "allowed": ["5.0", "3.0"],
        "evidence": "GC3 chưa từng đứng một mình trên LB (v13.1 confound SR0). Replica ước +0.0019 (giữ 19/21 TP-bridge).",
    },
    "BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB": {
        "class": "hypothesis",
        "allowed": ["0", "0.3"],
        "evidence": "leaf 0.3 prune 74n; replica trung tính; chưa từng đứng một mình trên LB.",
    },
    "BIOHUB_SAFE_DIV_ORPHAN_ADOPT": {
        "class": "hypothesis",
        "allowed": ["0", "1"],
        "evidence": "v11=0 → 0.947; v12.1=1 (cùng diverge −2.0) → 0.946. Chưa đứng một mình trên LB.",
    },
    "BIOHUB_SAFE_DIV_DIVERGE_UM": {
        "class": "hypothesis",
        "allowed": ["0.5", "-2.0"],
        "evidence": "v11=0.5 → 0.947 (144f/82 div); v12.1=−2.0 → 0.946 (184f/123 div, −0.001). Dose-response F: 2.25 → −0.0019 replica.",
    },
    "BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV": {
        "class": "reference",
        "evidence": "inert khi ORPHAN_ADOPT=0.",
    },
    "BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD": {"class": "reference", "evidence": "0.20 v11-exact."},
    "BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT": {
        "class": "reference",
        "evidence": "0.5 = đỉnh dose-response (0.25→−0.0028, 0.75→−0.0062 replica).",
    },
    "BIOHUB_DIV_PARENT_MAX_UM": {"class": "reference", "evidence": "10.5 default v11-exact."},
}
for k in (
    "BIOHUB_READMIT_MIN_SCORE", "BIOHUB_READMIT_RADIUS_UM", "BIOHUB_GAPFILL_STEP_UM",
    "BIOHUB_GAPFILL_PEAK_RADIUS_UM", "BIOHUB_GAPFILL_EXCLUDE_UM", "BIOHUB_GAPFILL_ALLOW_SYNTHETIC",
    "BIOHUB_GAPFILL_CONTEXT", "BIOHUB_GAPFILL_MAX_ADDED_FRAC", "BIOHUB_GAPFILL_MAX_GAP",
    "BIOHUB_GAPFILL_MIN_SCORE", "BIOHUB_LOWDET_DIR", "BIOHUB_LOWDET_THRESHOLD",
    "BIOHUB_VALIDATOR_ENABLE", "BIOHUB_VALIDATOR_N_PER_TYPE",
):
    KNOB_PROVENANCE[k] = {
        "class": "lb_proven_inert",
        "evidence": "knockout: receipts readmitted/gapfill=0 ở mọi bản LB ≥0.946 (v12.1+v13.1).",
    }

# Receipt rules — HARD (không ack được). Dải = min/max của 2 bản còn sống
# trên LB + biên an toàn; mọi vi phạm từng xảy ra đều đi kèm rớt điểm.
RECEIPT_RULES = {
    "safe_divisions_added": {"min": 40, "max": 160, "why": "v11=82→0.947, v12.1=123→0.946, v13.1=0→0.911"},
    "reparent_added": {"min": 40, "max": 120, "why": "v11=77→0.947, v12.1=77→0.946, v13.1=0→0.911"},
    "safe_division_divergence_rejected": {"min": 200, "max": 5000, "why": "gate phải sống: v11=2812, v12.1=365, v13.1=0"},
    "divnet_proposals_scored": {"min": 200, "max": 2000, "why": "kênh rank-only: v11=391, v12.1=769, v13.1=0"},
    "hoct_veto_divisions_before": {"min": 100, "max": 400, "why": "v11=144, v12.1=184, v13.1=0"},
    "hoct_veto_divisions_after": {"min": 100, "max": 400, "why": "sau veto vẫn còn (mode-1 division-safe)"},
}

CENSUS_RULES = {
    "forks": {"min": 100, "max": 200, "why": "LUẬT FORK: 144f→0.947, 184f→0.946, 0f→0.911 ×2 độc lập"},
    "nodes": {"tol_pct": 5.0, "why": "banked 122787 ±5%"},
    "edges": {"tol_pct": 5.0, "why": "banked 118332 ±5%"},
    "multi_parent": {"max": 0, "why": "DAG"},
    "datasets": {"min": 4, "max": 4, "why": "4 phim hidden test"},
    "bad_rows": {"max": 0, "why": "row_type phải node|edge"},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--monolith", required=True)
    ap.add_argument("--run-stats", required=True)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--out", default=str(HERE / "machinery-ledger.json"))
    args = ap.parse_args()

    mono = Path(args.monolith)
    eff, defaults = extract_env(mono)
    rec = receipts_sum(Path(args.run_stats))
    cens = census(Path(args.submission))
    md5 = hashlib.md5(mono.read_bytes()).hexdigest()

    datasets = int(rec.pop("__datasets"))
    ledger = {
        "ledger_version": 1,
        "generated": datetime.now(timezone.utc).isoformat(),
        "banked_reference": {
            "version": "v11",
            "submission_ref": 56403231,
            "public_lb": 0.947,
            "kernel_slug": "biohub-ver11",
            "monolith_md5": md5,
            "datasets": datasets,
            "census": cens,
            "receipts_sum": rec,
            "env_effective": eff,
            "env_read_defaults": defaults,
        },
        "lb_evidence_table": [
            {"version": "v10", "ref": 56348119, "lb": 0.947, "forks": 188, "safe_div_added": None, "note": "reparent có từ v8"},
            {"version": "v11", "ref": 56403231, "lb": 0.947, "forks": 144, "safe_div_added": 82, "note": "BANKED"},
            {"version": "v12.1", "ref": 56442903, "lb": 0.946, "forks": 184, "safe_div_added": 123, "note": "diverge −2.0 + orphan"},
            {"version": "variantA", "ref": 56373784, "lb": 0.911, "forks": 0, "safe_div_added": None, "note": "purge 188 forks — mất kênh division"},
            {"version": "v13.1", "ref": 56473159, "lb": 0.911, "forks": 0, "safe_div_added": 0, "note": "SR0 tắt máy division — CHỮ KÝ TRÙNG variantA"},
        ],
        "knob_provenance": KNOB_PROVENANCE,
        "receipt_rules": RECEIPT_RULES,
        "census_rules": CENSUS_RULES,
        "law_L13": [
            "Fork census 100-200 = HARD GATE mọi submission — không override bằng lập luận replica.",
            "Replica-gate = instrument adjEJ-ONLY (mù divJ + mù cấu trúc fork).",
            "Máy division v11-class phải BẬT trong mọi build (OUTPUT_SAFE_DIVISIONS=1, REPARENT_ENABLE=1).",
            "Mọi knob diff vs banked phải được phân loại trong knob_provenance trước khi submit.",
        ],
    }
    Path(args.out).write_text(json.dumps(ledger, indent=1, sort_keys=True) + "\n")
    print(f"Ledger ghi {args.out}")
    print(f"  banked v11: census {cens['nodes']}n/{cens['edges']}e/{cens['forks']}f · receipts safe_div={rec.get('safe_divisions_added')} reparent={rec.get('reparent_added')}")
    print(f"  env_effective {len(eff)} khóa · read_defaults {len(defaults)} khóa · md5 {md5[:8]}")


if __name__ == "__main__":
    main()
