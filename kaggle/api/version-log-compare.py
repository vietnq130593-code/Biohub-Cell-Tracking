#!/usr/bin/env python3
"""version-log-compare.py — So sánh chất lượng các phiên bản TỪ LOGS (không cần GPU).

Trả lời: "logs của các phiên bản khác nhau có giúp đánh giá/so sánh chất lượng không?"
→ CÓ, qua 3 họ tín hiệu độc lập:

  1. SUBMISSION LOG (Kaggle API)  — điểm LB = chân lý chất lượng cuối cùng.
  2. KERNEL RUN LOG (run_stats.csv = receipts) — "máy móc fingerprint": tầng nào
     đang chạy, tầng nào chết. v13.1 chết 0 ở 5 tầng division → đọc receipt là biết.
  3. OUTPUT LOG (submission.csv = census) — cấu trúc: nodes/edges/forks/DAG.
     LUẬT FORK: forks∈[144,188]→0.946-0.947, forks=0→0.911 (×2 độc lập).

Dùng:
  python3 version-log-compare.py                     # dùng các dir mặc định
  python3 version-log-compare.py --add v14=/path/to/output
  python3 version-log-compare.py --pull              # refresh LB qua Kaggle API
  python3 version-log-compare.py -o report.md
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# LB map (nguồn: Kaggle submissions API, pull 23/9 — dùng --pull để refresh)
LB_MAP = {
    "v6": 0.945, "v7": 0.947, "v8-fallback": 0.947, "v10": 0.947,
    "v11": 0.947, "v12.1": 0.946, "variantA": 0.911, "v13.1": 0.911,
}
REF_MAP = {
    "v6": "56210873", "v7": "56217216", "v8-fallback": "56261360",
    "v10": "56348119", "v11": "56403231", "v12.1": "56442903",
    "variantA": "56373784", "v13.1": "56473159",
}

DEFAULT_DIRS = [
    ("v11", HERE.parent / "v11-recovery" / "ver11-output"),
    ("v11", Path("/home/z/v11-recovery/ver11-output")),
    ("v12.1", HERE / "output" / "latest"),
    ("v13.1", HERE.parent / "ver-13-1" / "output-pull"),
    ("v8-v3fast", HERE / "output" / "ver8-v3fast"),
    ("v8-v1", HERE / "output" / "ver8-v1"),
]

RECEIPT_KEYS = [
    "safe_divisions_added", "reparent_added", "safe_division_divergence_rejected",
    "divnet_proposals_scored", "hoct_veto_divisions_before", "hoct_veto_divisions_after",
    "gap_added_nodes", "gap2_added_nodes", "leaf_prune_nodes",
    "readmitted_nodes", "gapfill_added_nodes",
]


def read_version_dir(d: Path) -> dict | None:
    rs, sc = d / "run_stats.csv", d / "submission.csv"
    if not rs.is_file() or not sc.is_file():
        return None
    rows = list(csv.DictReader(open(rs)))
    sums: dict[str, float] = {}
    for k in rows[0]:
        try:
            sums[k] = sum(float(r[k] or 0) for r in rows)
        except ValueError:
            pass
    tag = rows[0].get("experiment_tag", "?") if rows else "?"

    children: dict[tuple, set] = defaultdict(set)
    parents: dict[tuple, set] = defaultdict(set)
    nodes: set = set()
    datasets: set = set()
    edges = 0
    for row in csv.DictReader(open(sc)):
        ds = row.get("dataset", "")
        datasets.add(ds)
        if row.get("row_type") == "node":
            nodes.add((ds, row.get("node_id")))
        elif row.get("row_type") == "edge":
            edges += 1
            children[(ds, row.get("source_id"))].add(row.get("target_id"))
            parents[(ds, row.get("target_id"))].add(row.get("source_id"))
    forks = sum(1 for ks in children.values() if len(ks) > 1)
    mp = sum(1 for ps in parents.values() if len(ps) > 1)
    return {
        "tag": tag[:60], "datasets": len(rows),
        "census": {"nodes": len(nodes), "edges": edges, "forks": forks,
                    "multi_parent": mp, "n_datasets": len(datasets)},
        "receipts": {k: int(sums.get(k, 0)) for k in RECEIPT_KEYS},
    }


def pull_lb() -> dict[str, str]:
    """Refresh publicScore theo description-marker qua Kaggle API."""
    try:
        out = subprocess.run(
            ["kaggle", "competitions", "submissions",
             "-c", "biohub-cell-tracking-during-development", "--csv"],
            capture_output=True, text=True, timeout=90)
        if out.returncode != 0:
            print(f"(--pull bỏ qua: {out.stderr.strip()[:100]})", file=sys.stderr)
            return LB_MAP
        lb: dict[str, str] = {}
        for row in csv.DictReader(out.stdout.splitlines()):
            desc, score = row.get("description", ""), row.get("publicScore", "")
            if not score:
                continue
            low = desc.lower()
            if "ver-13.1" in low or "sr0gc3" in low:
                lb["v13.1"] = score
            elif "ver-12.1" in low:
                lb["v12.1"] = score
            elif "ver-11 " in low or low.startswith("ver-11"):
                lb["v11"] = score
            elif "linear-gpu variant a proven" in low:
                lb["variantA"] = score
            elif "ver-10 v3-fast" in low:
                lb["v10"] = score
        return {**LB_MAP, **lb}
    except Exception as e:  # noqa: BLE001
        print(f"(--pull bỏ qua: {e})", file=sys.stderr)
        return LB_MAP


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--add", action="append", default=[],
                    help="thêm label=dir (có thể lặp lại)")
    ap.add_argument("--pull", action="append_const", const=1, dest="extra",
                    help="refresh LB từ Kaggle API")
    ap.add_argument("-o", "--out", help="ghi báo cáo ra file markdown")
    args = ap.parse_args()
    ap.set_defaults(extra=[])
    lb = pull_lb() if getattr(args, "extra", None) else LB_MAP

    seen: set[str] = set()
    versions: list[tuple[str, dict]] = []
    for label, d in DEFAULT_DIRS + [tuple(a.split("=", 1)) for a in args.add]:
        if label in seen or not Path(d).is_dir():
            continue
        v = read_version_dir(Path(d))
        if v:
            versions.append((label, v))
            seen.add(label)

    L: list[str] = []
    L.append("# CROSS-VERSION LOG COMPARISON — chất lượng từ logs\n")
    L.append("> Sinh bởi `version-log-compare.py`. Nguồn: run_stats.csv (receipts) "
             "+ submission.csv (census) + Kaggle submissions (LB).\n")

    L.append("\n## 1. Bảng chính — LB × census × máy division\n")
    L.append("| Bản | LB | nodes | edges | **forks** | safe_div | reparent | div_rej | divnet | HOCT | verdict |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for label, v in versions:
        c, r = v["census"], v["receipts"]
        lbv = lb.get(label, "—")
        forks, sd = c["forks"], r["safe_divisions_added"]
        if forks == 0 or sd == 0:
            verdict = "🔴 MÁY DIVISION CHẾT (L13)"
        elif 100 <= forks <= 200:
            verdict = "🟢 vùng ổn định (luật fork)"
        else:
            verdict = "🟡 forks ngoài dải — kiểm tra"
        L.append(f"| {label} | {lbv} | {c['nodes']:,} | {c['edges']:,} | **{forks}** | "
                 f"{sd} | {r['reparent_added']} | {r['safe_division_divergence_rejected']:,} | "
                 f"{r['divnet_proposals_scored']:,} | {r['hoct_veto_divisions_before']} | {verdict} |")

    L.append("\n## 2. Luật fork (định luật thực nghiệm từ LB)\n")
    L.append("| forks | LB | mẫu |")
    L.append("|---|---|---|")
    L.append("| 188 | 0.947 | v10 |")
    L.append("| 144 | 0.947 | v11 (banked) |")
    L.append("| 184 | 0.946 | v12.1 |")
    L.append("| **0** | **0.911** | **variant A + v13.1 (2 mẫu độc lập)** |")
    L.append("\n→ Đọc receipt `safe_divisions_added` + census `forks` là **đoán được LB trước khi nộp**.")

    L.append("\n## 3. Fingerprint đầy đủ (receipts)\n")
    L.append("| receipt | " + " | ".join(l for l, _ in versions) + " |")
    L.append("|---" * (len(versions) + 1) + "|")
    for k in RECEIPT_KEYS:
        L.append(f"| {k} | " + " | ".join(f"{v['receipts'][k]:,}" for _, v in versions) + " |")
    L.append(f"| experiment_tag | " + " | ".join(v["tag"] for _, v in versions) + " |")

    L.append("\n## 4. Tín hiệu log nào nói gì (hướng dẫn đọc)\n")
    L.append("""
| Họ log | File | Chất lượng đo được | Độ tin cậy |
|---|---|---|---|
| Submission log | Kaggle API `submissions` | Điểm LB cuối cùng — chân lý | ★★★ tuyệt đối (nhưng đã muộn) |
| Run receipts | `run_stats.csv` per kernel | Máy nào FIRED bao nhiêu lần → phát hiện máy chết (v13.1: 5 tầng = 0) | ★★★ (trước submit!) |
| Output census | `submission.csv` | forks/nodes/edges/DAG → đoán LB qua luật fork | ★★☆ (vùng ổn định, không phải điểm chính xác) |
| Kernel stdout log | `biohub-*.log` | config dump + guard + timeline run | ★★★ (audit độc lập — md5, env) |
| Replica-gate log | GT 84-file local | delta adjEJ giữa build CÙNG máy BẬT | ★☆☆ adjEJ-only, mù divJ/fork (L13b) |
| GPU sổ | quota | chi phí/tháng — tránh L2/L8 | ★★★ |

**Kết luận cho câu hỏi "logs có giúp so sánh chất lượng không?": CÓ.**
Nhận diện version tốt/xấu mà không tốn submission: (1) receipts cho biết máy sống hay chết;
(2) census fork → khoảng LB; (3) LB lịch sử cho version đã nộp. Công cụ này gộp cả 3.
""")

    report = "\n".join(L)
    print(report)
    if args.out:
        Path(args.out).write_text(report + "\n")
        print(f"\n(ghi {args.out})")


if __name__ == "__main__":
    main()
