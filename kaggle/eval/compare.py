#!/usr/bin/env python3
"""compare.py — A/B comparator cho eval reports (biohub-eval-report/1).

(Bản tái tạo 13/9 sau sandbox rollback — tương đương chức năng bản gốc đã mất:
paired theo stem CHUNG, micro-pooled, bootstrap CI95 10k seed cố định, 5 guard,
gate tuyệt đối, verdict UPGRADE/LIKELY-UPGRADE/INCONCLUSIVE/REGRESSION/IDENTICAL.)

Trả lời: "phiên bản sau có tốt hơn phiên bản trước không?" — bằng bằng chứng paired:
  1. Ghép cặp theo stem CHUNG (cùng video, cùng GT) — bỏ qua video chỉ có 1 bên.
  2. Δmicro official: ΔadjEJ (weighted), ΔdivJ, Δproxy = Δadj + 0.1×ΔdivJ.
  3. Bootstrap paired theo stem (10k, seed 314159) → CI95 của ΔadjEJ.
  4. 5 guard: G1 div_fn không tăng mạnh; G2 div_fp có kiểm soát; G3 node budget
     (t_pred trong ±10%); G4 không video nào sụt > 0.01; G5 t_true khớp giữa 2 report.
  5. Gate tuyệt đối (tuỳ chọn, từ VER7-PLAN Phase B): --gate adj:0.942 --gate proxy:0.945
     — áp cho micro TOÀN BỘ stems của candidate (không chỉ phần chung).

Dùng:
  python3 compare.py baseline.json candidate.json \
      --gate adj:0.942 --gate proxy:0.945 --out report.md
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path

PRACTICAL_DEFAULT = 0.0015   # ≈ +0.002 LB — ngưỡng delta có ý nghĩa thực tiễn
BOOT_N = 10_000
BOOT_SEED = 314159


def load_report(path: Path) -> dict:
    data = json.loads(Path(path).read_text())
    assert data.get("schema") == "biohub-eval-report/1", f"{path}: schema lạ {data.get('schema')}"
    assert "samples" in data, f"{path}: thiếu samples"
    return data


def micro(rows: list[dict]) -> dict:
    tp = sum(r["edge_tp"] for r in rows)
    fp = sum(r["edge_fp"] for r in rows)
    fn = sum(r["edge_fn"] for r in rows)
    adj_rows = [r for r in rows if r.get("adjusted_edge_jaccard") is not None]
    wsum = sum(r["weight"] for r in adj_rows) or 1
    adj = (sum(r["adjusted_edge_jaccard"] * r["weight"] for r in adj_rows) / wsum) if adj_rows else None
    dtp = sum(r["div_tp"] for r in rows)
    dfp = sum(r["div_fp"] for r in rows)
    dfn = sum(r["div_fn"] for r in rows)
    dj = dtp / (dtp + dfp + dfn) if (dtp + dfp + dfn) else None
    ej = tp / (tp + fp + fn) if (tp + fp + fn) else None
    return {"n": len(rows), "edge_tp": tp, "edge_fp": fp, "edge_fn": fn, "edge_jaccard": ej,
            "adjusted_edge_jaccard": adj, "div_tp": dtp, "div_fp": dfp, "div_fn": dfn,
            "division_jaccard": dj,
            "proxy_score": (adj if adj is not None else 0.0) + (0.1 * dj if dj is not None else 0.0),
            "t_pred": sum(r.get("t_pred") or 0 for r in rows)}


def bootstrap_paired_delta(base_rows: list[dict], cand_rows: list[dict], n: int = BOOT_N,
                            seed: int = BOOT_SEED) -> dict:
    """Resample stem theo cặp (cùng stem cùng lần resample) → phân phối ΔadjEJ micro."""
    m = len(base_rows)
    rng = random.Random(seed)
    deltas = []
    for _ in range(n):
        idx = [rng.randrange(m) for _ in range(m)]
        d = micro([cand_rows[i] for i in idx])["adjusted_edge_jaccard"] - \
            micro([base_rows[i] for i in idx])["adjusted_edge_jaccard"]
        deltas.append(d)
    deltas.sort()

    def q(p):
        return deltas[min(n - 1, max(0, int(p * n)))]

    return {"seed": seed, "n_boot": n, "mean": sum(deltas) / n,
            "ci95_lo": q(0.025), "ci95_hi": q(0.975)}


def fmt(v, digits=4):
    return f"{v:.{digits}f}" if isinstance(v, (int, float)) and v is not None and v == v else "  n/a"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("baseline", help="eval report JSON của bản nền (vd ver-6)")
    ap.add_argument("candidate", help="eval report JSON của bản mới (vd ver-7)")
    ap.add_argument("--label", default=None, help="nhãn phiên bản mới")
    ap.add_argument("--practical", type=float, default=PRACTICAL_DEFAULT,
                    help="ngưỡng delta có ý nghĩa thực tiễn (mặc định 0.0015 ≈ +0.002 LB)")
    ap.add_argument("--gate", action="append", default=[],
                    help="gate tuyệt đối, dạng adj:0.942 hoặc proxy:0.945 (lặp được)")
    ap.add_argument("--out", default=None, help="ghi báo cáo markdown ra file này")
    args = ap.parse_args()

    base = load_report(Path(args.baseline))
    cand = load_report(Path(args.candidate))
    label = args.label or cand.get("meta", {}).get("version") or "candidate"

    base_rows_all = base["samples"]
    cand_rows_all = cand["samples"]
    base_by = {r["stem"]: r for r in base_rows_all}
    cand_by = {r["stem"]: r for r in cand_rows_all}
    common = sorted(set(base_by) & set(cand_by))
    only_b = sorted(set(base_by) - set(cand_by))
    only_c = sorted(set(cand_by) - set(base_by))

    if not common:
        print("VERDICT: NO-COMMON-STEMS — không so sánh được (không có video chung)")
        return 2

    base_rows = [base_by[s] for s in common]
    cand_rows = [cand_by[s] for s in common]
    mb, mc = micro(base_rows), micro(cand_rows)
    mc_all = micro(cand_rows_all)   # gate áp trên TOÀN BỘ stems của candidate
    boot = bootstrap_paired_delta(base_rows, cand_rows)

    d_adj = mc["adjusted_edge_jaccard"] - mb["adjusted_edge_jaccard"]
    d_prx = mc["proxy_score"] - mb["proxy_score"]
    d_ej = (mc["edge_jaccard"] - mb["edge_jaccard"]) if (mc["edge_jaccard"] is not None and mb["edge_jaccard"] is not None) else None
    d_divfn = mc["div_fn"] - mb["div_fn"]
    d_divfp = mc["div_fp"] - mb["div_fp"]
    d_divtp = mc["div_tp"] - mb["div_tp"]
    d_nodes = mc_all["t_pred"] - micro(base_rows_all)["t_pred"]

    # ---- guards G1-G5 ------------------------------------------------------
    guards = []
    div_total_b = mb["div_tp"] + mb["div_fn"]
    guards.append({"id": "G1", "name": "div_fn không tăng mạnh",
                   "ok": d_divfn <= max(1, math.ceil(0.25 * max(div_total_b, 1))),
                   "detail": f"Δdiv_fn={d_divfn:+d} (baseline fn={mb['div_fn']}/{div_total_b} events)"})
    guards.append({"id": "G2", "name": "div_fp có kiểm soát",
                   "ok": d_divfp <= max(5, int(0.5 * max(mb['div_fp'], 1))),
                   "detail": f"Δdiv_fp={d_divfp:+d} (baseline fp={mb['div_fp']})"})
    t_b_common = sum(r.get("t_pred") or 0 for r in base_rows) or 1
    d_nodes_common = sum((cand_by[s].get("t_pred") or 0) - (base_by[s].get("t_pred") or 0) for s in common)
    guards.append({"id": "G3", "name": "node budget ±10% (stem CHUNG)",
                   "ok": abs(d_nodes_common) <= 0.10 * t_b_common,
                   "detail": f"Δnodes={d_nodes_common:+d} ({100 * d_nodes_common / t_b_common:+.1f}% trên {len(common)} video chung)"})
    worst = 0.0
    for br, cr in zip(base_rows, cand_rows):
        if br.get("adjusted_edge_jaccard") is not None and cr.get("adjusted_edge_jaccard") is not None:
            worst = min(worst, cr["adjusted_edge_jaccard"] - br["adjusted_edge_jaccard"])
    guards.append({"id": "G4", "name": "không video nào sụt > 0.010",
                   "ok": worst >= -0.010,
                   "detail": f"per-video ΔadjEJ xấu nhất = {worst:+.4f}"})
    tt_ok = all(
        (base_by[s].get("t_true") is None) or (cand_by[s].get("t_true") is None)
        or abs(base_by[s]["t_true"] - cand_by[s]["t_true"]) < 1e-6
        for s in common
    )
    guards.append({"id": "G5", "name": "t_true khớp giữa 2 report",
                   "ok": tt_ok, "detail": "paired integrity" if tt_ok else "T_TRUE LỆCH NHAU!"})
    all_guards_ok = all(g["ok"] for g in guards)

    # ---- gate tuyệt đối -----------------------------------------------------
    gates = []
    for g in args.gate:
        try:
            k, v = g.split(":")
            v = float(v)
        except ValueError:
            ap.error(f"--gate sai định dạng: {g}")
        key = "adjusted_edge_jaccard" if k.startswith("adj") else "proxy_score"
        got = mc_all.get(key)
        ok = got is not None and got >= v
        gates.append({"name": f"{k}:{v:.4f}", "value": got, "ok": ok})

    # ---- verdict -------------------------------------------------------------
    lo, hi = boot["ci95_lo"], boot["ci95_hi"]
    if abs(d_adj) < 1e-12 and abs(d_prx) < 1e-12:
        verdict = "IDENTICAL"
    elif hi < -args.practical:
        verdict = "REGRESSION"
    elif lo > args.practical:
        verdict = "UPGRADE"
    elif d_adj >= args.practical and lo > 0:
        verdict = "LIKELY-UPGRADE"
    else:
        verdict = "INCONCLUSIVE"

    # ---- in báo cáo ----------------------------------------------------------
    L = []
    A = L.append
    A(f"# A/B so sánh (official rule) — {label}")
    A("")
    A(f"- Baseline: `{args.baseline}` ({base.get('meta', {}).get('version', '?')}, {len(base_rows_all)} video)")
    A(f"- Candidate: `{args.candidate}` ({label}, {len(cand_rows_all)} video)")
    A(f"- Video paired: **{len(common)}** | chỉ baseline: {only_b or '—'} | chỉ candidate: {only_c or '—'}")
    A(f"- Bootstrap paired: n={boot['n_boot']}, seed={boot['seed']}")
    A("")
    A("## Micro pooled (trên video CHUNG)")
    A("")
    A("| metric | baseline | candidate | Δ |")
    A("|---|---|---|---|")
    A(f"| adjEJ (weighted) | {fmt(mb['adjusted_edge_jaccard'])} | {fmt(mc['adjusted_edge_jaccard'])} | {d_adj:+.4f} |")
    A(f"| EJ raw | {fmt(mb['edge_jaccard'])} | {fmt(mc['edge_jaccard'])} | {fmt(d_ej) if d_ej is not None else 'n/a'} |")
    A(f"| divJ | {fmt(mb['division_jaccard'])} | {fmt(mc['division_jaccard'])} | {fmt(mc['division_jaccard'] - mb['division_jaccard']) if (mb['division_jaccard'] is not None and mc['division_jaccard'] is not None) else 'n/a'} |")
    A(f"| proxy = adj + 0.1×divJ | {fmt(mb['proxy_score'])} | {fmt(mc['proxy_score'])} | {d_prx:+.4f} |")
    A(f"| div tp/fp/fn | {mb['div_tp']}/{mb['div_fp']}/{mb['div_fn']} | {mc['div_tp']}/{mc['div_fp']}/{mc['div_fn']} | {d_divtp:+d}/{d_divfp:+d}/{d_divfn:+d} |")
    A(f"| cạnh tp/fp/fn | {mb['edge_tp']}/{mb['edge_fp']}/{mb['edge_fn']} | {mc['edge_tp']}/{mc['edge_fp']}/{mc['edge_fn']} | "
      f"{mc['edge_tp'] - mb['edge_tp']:+d}/{mc['edge_fp'] - mb['edge_fp']:+d}/{mc['edge_fn'] - mb['edge_fn']:+d} |")
    A("")
    A(f"**ΔadjEJ bootstrap CI95: [{lo:+.4f}, {hi:+.4f}]** (mean {boot['mean']:+.4f}) — ngưỡng thực tiễn ±{args.practical}")
    A("")
    A("## Guards")
    A("")
    for g in guards:
        A(f"- {'✅' if g['ok'] else '❌'} **{g['id']}** {g['name']}: {g['detail']}")
    A("")
    if gates:
        A("## Absolute gates (VER7-PLAN Phase B — áp trên TOÀN BỘ video của candidate)")
        A("")
        for g in gates:
            A(f"- {'✅' if g['ok'] else '❌'} **{g['name']}**: candidate = {fmt(g['value'])}")
        A("")
    A("## Per-video (paired)")
    A("")
    A("| stem | adjEJ base | adjEJ cand | ΔadjEJ | divJ base | divJ cand |")
    A("|---|---|---|---|---|---|")
    for s in common:
        br, cr = base_by[s], cand_by[s]
        if cr.get("adjusted_edge_jaccard") is not None and br.get("adjusted_edge_jaccard") is not None:
            d_txt = f"{cr['adjusted_edge_jaccard'] - br['adjusted_edge_jaccard']:+.4f}"
        else:
            d_txt = "n/a"
        A(f"| `{s}` | {fmt(br.get('adjusted_edge_jaccard'))} | {fmt(cr.get('adjusted_edge_jaccard'))} | "
          f"{d_txt} | {fmt(br.get('division_jaccard'))} | {fmt(cr.get('division_jaccard'))} |")
    A("")
    gates_ok = all(g["ok"] for g in gates) if gates else None
    A("## VERDICT")
    A("")
    A(f"### **{verdict}**" + (f" — guards {'ĐẠT' if all_guards_ok else 'LỖI'}"
                              + (f", gate {'ĐẠT' if gates_ok else 'KHÔNG ĐẠT'}" if gates_ok is not None else "")))
    A("")
    if verdict in ("UPGRADE", "LIKELY-UPGRADE") and all_guards_ok and (gates_ok is not False):
        A("→ **ĐỦ ĐIỀU KIỆN submit** theo VER7-PLAN Phase B (verdict ≥ LIKELY-UPGRADE + guard + gate).")
    else:
        A("→ **CHƯA đủ điều kiện submit** — xem guards/gate ở trên trước khi quyết định.")

    text = "\n".join(L)
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")
        print(f"\n[ghi] {args.out}")
    return 0 if (verdict in ("UPGRADE", "IDENTICAL")) else (1 if verdict == "REGRESSION" else 0)


if __name__ == "__main__":
    sys.exit(main())
