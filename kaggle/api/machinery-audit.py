#!/usr/bin/env python3
"""machinery-audit.py — CỔNG CỨNG PHÁT HIỆN LỖI TRƯỚC KHI SUBMIT (L13).

Ra đời sau thảm họa v13.1 = 0.911 (ref 56473159): SR0 tắt toàn bộ máy division,
replica-gate +0.0011 vẫn xanh, guard L6 🔴 in ra "forks=0 → HOLD" nhưng bị
con người override bằng lập luận. Công cụ này tồn tại để lỗi lớp đó KHÔNG THỂ
lọt tới Kaggle nữa:

  3 LỚP KIỂM (độc lập, chạy được riêng lẻ hay đủ cả 3):
   [CONFIG]  monolith .py/.ipynb → effective env → đối chiếu machinery-ledger.json
             (must_on / lb_proven_* / hypothesis-ack / reference / UNCLASSIFIED)
   [RECEIPT] run_stats.csv → máy có realmente FIRED? (safe_div, reparent, gate,
             divnet, HOCT — v13.1 chết 0 ở cả 5 tầng)
   [CENSUS]  submission.csv → fork law + DAG + INT + nodes/edges ±5%

  HARD RULES không thể ack: R1-R10. Mọi FAIL → exit 1 (script submit phải gọi
  tool này và abort). --ack chỉ dùng cho knob class "hypothesis".

Ví dụ:
  # audit đầy đủ bản run xong (trước submit):
  python3 machinery-audit.py --dir kaggle/ver-13-1/output-pull \
      --monolith kaggle/ver-13-1/kernel-pull/cell-monolith-pulled.py --submit-gate
  # audit config lúc build (chưa có run):
  python3 machinery-audit.py --monolith ver-13-2/cell-monolith.py
  # chấp nhận giả thuyết GC3+leaf một cách TƯỜNG MINH:
  ... --ack BIOHUB_GAP_CLOSE_UM,BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_LEDGER = HERE / "machinery-ledger.json"

ASSIGN_RE = re.compile(r"os\.environ\['(BIOHUB_[A-Z0-9_]+)'\]\s*=\s*'([^']*)'")
READ_RE = re.compile(r"os\.environ\.get\('(BIOHUB_[A-Z0-9_]+)',\s*'([^']*)'\)")
ASSIGN_JUPYTER_RE = re.compile(r"os\.environ\[\"(BIOHUB_[A-Z0-9_]+)\"\]\s*=\s*\"([^\"]*)\"")


def load_monolith_source(path: Path) -> str:
    if path.suffix == ".ipynb":
        nb = json.loads(path.read_text())
        cells = [c for c in nb["cells"] if c.get("cell_type") == "code"]
        if not cells:
            raise SystemExit(f"{path}: không có code cell")
        return "".join("".join(c.get("source", [])) for c in cells)
    return path.read_text()


def extract_env(src: str, defaults_map: dict[str, str]) -> dict[str, str]:
    effective: dict[str, str] = {}
    for k, v in ASSIGN_RE.findall(src):
        effective[k] = v
    for k, v in ASSIGN_JUPYTER_RE.findall(src):
        effective.setdefault(k, v)
    defaults: dict[str, str] = {}
    for k, v in READ_RE.findall(src):
        defaults.setdefault(k, v)
    full = dict(effective)
    for k, v in defaults_map.items():
        full.setdefault(k, v)
    for k, v in defaults.items():
        full.setdefault(k, v)
    return full


def norm(v: str):
    try:
        return float(v)
    except (TypeError, ValueError):
        return v


# ---------------------------------------------------------------- verdict helpers


class Audit:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, layer: str, rule: str, status: str, detail: str) -> None:
        self.rows.append({"layer": layer, "rule": rule, "status": status, "detail": detail})

    def fails(self) -> int:
        return sum(1 for r in self.rows if r["status"] == "FAIL")

    def warns(self) -> int:
        return sum(1 for r in self.rows if r["status"] == "WARN")


def audit_config(monolith: Path, ledger: dict, ack: set[str], audit: Audit) -> dict[str, str]:
    ref_env = ledger["banked_reference"]["env_effective"]
    defaults_map = ledger["banked_reference"]["env_read_defaults"]
    prov = ledger["knob_provenance"]
    src = load_monolith_source(monolith)
    env = extract_env(src, defaults_map)

    # R1 — máy division phải BẬT (L13c) — HARD, không ack
    for key in ("BIOHUB_OUTPUT_SAFE_DIVISIONS", "BIOHUB_REPARENT_ENABLE"):
        val = env.get(key, "?")
        if str(val) == "0":
            audit.add("CONFIG", f"R1 {key}", "FAIL",
                      f"=0 → TẮT MÁY (L13c). Bằng chứng: v13.1 làm vậy → 0.911 (ref 56473159), variant A → 0.911 (ref 56373784). KHÔNG THỂ ACK.")
        else:
            audit.add("CONFIG", f"R1 {key}", "PASS", f"={val}")

    # R2 — diff từng knob vs banked, phân loại theo provenance
    keys = sorted(set(ref_env) | set(env))
    unclassified: list[str] = []
    build_defaults: dict[str, str] = {}
    for k, v in READ_RE.findall(src):
        build_defaults.setdefault(k, v)
    for k in keys:
        a, b = ref_env.get(k), env.get(k)
        na, nb = norm(a) if a is not None else None, norm(b) if b is not None else None
        if na == nb:
            continue
        # Knob mới (v11 chưa có) nhưng build để nguyên default read-site → tương đương v11-absent
        if a is None and b is not None and norm(b) == norm(build_defaults.get(k, b)):
            continue
        p = prov.get(k)
        if p is None:
            unclassified.append(f"{k}: banked={a} → build={b}")
            continue
        cls = p["class"]
        allowed = p.get("allowed")
        in_allowed = allowed is None or any(norm(x) == nb for x in allowed)
        if cls == "hypothesis":
            if k in ack:
                audit.add("CONFIG", f"R2 {k}", "WARN",
                          f"banked={a} → build={b} [ACKED hypothesis: {p['evidence']}]")
            elif in_allowed:
                audit.add("CONFIG", f"R2 {k}", "WARN",
                          f"banked={a} → build={b} [hypothesis chưa ack — thêm --ack {k} nếu chấp nhận rủi ro: {p['evidence']}]")
            else:
                audit.add("CONFIG", f"R2 {k}", "WARN",
                          f"banked={a} → build={b} [hypothesis ngoài allowed {allowed}: {p['evidence']}]")
        elif cls == "lb_proven_noop":
            audit.add("CONFIG", f"R2 {k}", "PASS" if in_allowed else "WARN",
                      f"banked={a} → build={b} [lb_proven_noop: {p['evidence']}]")
        elif cls == "lb_proven_inert":
            audit.add("CONFIG", f"R2 {k}", "PASS", f"banked={a} → build={b} [inert 0-firing]")
        else:  # reference
            audit.add("CONFIG", f"R2 {k}", "FAIL",
                      f"banked={a} → build={b} [reference-class: phải bằng banked — {p['evidence']}]")
    if unclassified:
        for u in unclassified:
            audit.add("CONFIG", "R2 UNCLASSIFIED", "FAIL",
                      f"{u} — knob chưa phân loại trong ledger → cập nhật knob_provenance TRƯỚC khi submit (L13d)")
    else:
        audit.add("CONFIG", "R2 knob-classification", "PASS",
                  f"{len(keys)} khóa đối chiếu, 0 knob ngoài phân loại")
    return env


def audit_receipts(run_stats: Path, ledger: dict, audit: Audit) -> None:
    rows = list(csv.DictReader(open(run_stats)))
    sums: dict[str, float] = {}
    for key in rows[0]:
        try:
            sums[key] = sum(float(r[key] or 0) for r in rows)
        except ValueError:
            pass
    tag_col = "experiment_tag" if "experiment_tag" in rows[0] else None
    tag = rows[0].get(tag_col, "?") if tag_col else "?"
    audit.add("RECEIPT", "R0 tag", "PASS" if tag != "?" else "WARN", f"experiment_tag={tag}")
    audit.add("RECEIPT", "R0 datasets", "PASS" if len(rows) == 4 else "FAIL",
              f"{len(rows)} dataset (phải 4)")
    # R3-R8: máy phải FIRED ở mọi tầng
    for key, rule in ledger["receipt_rules"].items():
        val = sums.get(key)
        if val is None:
            audit.add("RECEIPT", f"R3 {key}", "FAIL", "không có cột này trong run_stats.csv")
            continue
        lo, hi = rule["min"], rule["max"]
        if lo <= val <= hi:
            audit.add("RECEIPT", f"R3 {key}", "PASS",
                      f"Σ={val:g} ∈ [{lo},{hi}] — {rule['why']}")
        elif val == 0:
            audit.add("RECEIPT", f"R3 {key}", "FAIL",
                      f"Σ=0 → TẦNG MÁY CHẾT HOÀN TOÀN ({rule['why']}) — KHÔNG THỂ ACK")
        elif val < lo:
            audit.add("RECEIPT", f"R3 {key}", "FAIL",
                      f"Σ={val:g} < {lo} — hoạt động yếu bất thường ({rule['why']})")
        else:
            audit.add("RECEIPT", f"R3 {key}", "FAIL",
                      f"Σ={val:g} > {hi} — hoạt động bùng nổ bất thường ({rule['why']})")
    # R9: veto không được tăng số division
    b, a = sums.get("hoct_veto_divisions_before"), sums.get("hoct_veto_divisions_after")
    if b is not None and a is not None and a > b:
        audit.add("RECEIPT", "R9 hoct-veto-monotone", "FAIL", f"after {a:g} > before {b:g}")
    else:
        audit.add("RECEIPT", "R9 hoct-veto-monotone", "PASS", f"before={b:g} after={a:g}")


def audit_census(submission: Path, ledger: dict, audit: Audit) -> None:
    children: dict[tuple, set] = defaultdict(set)
    parents: dict[tuple, set] = defaultdict(set)
    nodes: set = set()
    datasets: set = set()
    edges = 0
    bad_rows = 0
    bad_coord = 0
    for row in csv.DictReader(open(submission)):
        ds = row.get("dataset", "")
        datasets.add(ds)
        rt = row.get("row_type")
        if rt == "node":
            nodes.add((ds, row.get("node_id")))
            for col in ("t", "z", "y", "x"):
                try:
                    int(float(row.get(col, "nan")))
                except ValueError:
                    bad_coord += 1
        elif rt == "edge":
            edges += 1
            children[(ds, row.get("source_id"))].add(row.get("target_id"))
            parents[(ds, row.get("target_id"))].add(row.get("source_id"))
        else:
            bad_rows += 1
    forks = sum(1 for ks in children.values() if len(ks) > 1)
    multi_parent = sum(1 for ps in parents.values() if len(ps) > 1)
    ref = ledger["banked_reference"]["census"]
    cr = ledger["census_rules"]

    fr = cr["forks"]
    audit.add("CENSUS", "R4 forks (LUẬT FORK)",
              "PASS" if fr["min"] <= forks <= fr["max"] else "FAIL",
              f"forks={forks} ∈ [{fr['min']},{fr['max']}]? — {fr['why']}")
    for name, total, refv in (("nodes", len(nodes), ref["nodes"]), ("edges", edges, ref["edges"])):
        tol = refv * cr[name]["tol_pct"] / 100.0
        ok = abs(total - refv) <= tol
        audit.add("CENSUS", f"R5 {name}", "PASS" if ok else "FAIL",
                  f"{total} vs banked {refv} (±{cr[name]['tol_pct']}% = ±{tol:.0f}) — {cr[name]['why']}")
    audit.add("CENSUS", "R6 DAG", "PASS" if multi_parent == 0 else "FAIL",
              f"multi-parent={multi_parent} (phải 0)")
    audit.add("CENSUS", "R7 datasets", "PASS" if len(datasets) == 4 else "FAIL",
              f"{len(datasets)} dataset (phải 4)")
    audit.add("CENSUS", "R8 format", "PASS" if bad_rows == 0 and bad_coord == 0 else "FAIL",
              f"bad_rows={bad_rows} bad_coord={bad_coord} (phải 0/0)")


# ---------------------------------------------------------------- report


def report(audit: Audit, submit_gate: bool) -> int:
    icons = {"PASS": "✅", "WARN": "🟡", "FAIL": "🔴"}
    print("=" * 78)
    print("MACHINERY AUDIT — phát hiện lỗi trước submit (L13)")
    print("=" * 78)
    for r in audit.rows:
        print(f"{icons.get(r['status'], '?')} [{r['layer']:7}] {r['rule']}")
        print(f"          {r['detail']}")
    nf, nw = audit.fails(), audit.warns()
    print("-" * 78)
    if nf:
        verdict = "FAIL"
        print(f"KẾT LUẬN: 🔴 FAIL — {nf} HARD-rule vi phạm. KHÔNG SUBMIT.")
        print("   Hard-rule không thể ack. Sửa build rồi audit lại.")
    elif submit_gate and nw:
        verdict = "HOLD"
        print(f"KẾT LUẬN: 🟡 HOLD — {nw} cảnh báo chưa ack (--ack <KNOB,...>).")
    else:
        verdict = "PASS"
        print(f"KẾT LUẬN: ✅ PASS — {nw} cảnh báo đã ack/không dấu hiệu lỗi.")
    print(f"Chi tiết: PASS={len(audit.rows)-nf-nw} WARN={nw} FAIL={nf}")
    return 1 if (nf or (submit_gate and nw)) else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--monolith", help="monolith .py hoặc notebook .ipynb (lớp CONFIG)")
    ap.add_argument("--run-stats", help="run_stats.csv (lớp RECEIPT)")
    ap.add_argument("--submission", help="submission.csv (lớp CENSUS)")
    ap.add_argument("--dir", help="thư mục output kernel: tự tìm run_stats.csv + submission.csv")
    ap.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    ap.add_argument("--ack", default="", help="danh sách knob hypothesis chấp nhận, phân tách phẩy")
    ap.add_argument("--submit-gate", action="store_true",
                    help="exit ≠0 cả khi còn WARN chưa ack (dùng trong script submit)")
    ap.add_argument("--json", help="ghi kết quả JSON ra file")
    args = ap.parse_args()

    ledger = json.loads(Path(args.ledger).read_text())
    audit = Audit()
    ack = {k.strip() for k in args.ack.split(",") if k.strip()}

    run_stats = Path(args.run_stats) if args.run_stats else None
    submission = Path(args.submission) if args.submission else None
    if args.dir:
        d = Path(args.dir)
        if run_stats is None and (d / "run_stats.csv").is_file():
            run_stats = d / "run_stats.csv"
        if submission is None and (d / "submission.csv").is_file():
            submission = d / "submission.csv"

    ran = 0
    if args.monolith:
        audit_config(Path(args.monolith), ledger, ack, audit)
        ran += 1
    if run_stats and Path(run_stats).is_file():
        audit_receipts(Path(run_stats), ledger, audit)
        ran += 1
    else:
        audit.add("RECEIPT", "R0 skip", "WARN", "không có run_stats.csv (bỏ qua lớp RECEIPT)")
    if submission and Path(submission).is_file():
        audit_census(Path(submission), ledger, audit)
        ran += 1
    else:
        audit.add("CENSUS", "R0 skip", "WARN", "không có submission.csv (bỏ qua lớp CENSUS)")
    if ran == 0:
        raise SystemExit("Không có gì để audit — đưa --monolith / --dir / --run-stats / --submission")

    code = report(audit, args.submit_gate)
    if args.json:
        Path(args.json).write_text(json.dumps(
            {"verdict": "FAIL" if audit.fails() else ("HOLD" if (args.submit_gate and audit.warns()) else "PASS"),
             "fails": audit.fails(), "warns": audit.warns(), "rows": audit.rows}, indent=1))
    sys.exit(code)


if __name__ == "__main__":
    main()
