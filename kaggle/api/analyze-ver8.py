#!/usr/bin/env python3
"""analyze-ver8.py — Phân tích output kernel biohub-ver8 (hoặc wave1) và áp cổng submit.

Cổng submit (VER8-REPARENT-DESIGN §5, so với baseline ver-7 system-view E1):
  - ΔadjEJ ≥ −0.0005 (adjEJ baseline 0.9280 trên 8 stems)
  - div_tp ≥ +2 (baseline 2 TP)
  - div_fp ≤ +3 (baseline 1 FP)
  - guards 5/5 (G1-G5 như compare.py: div_fn, div_fp, node budget, không video sụt > 0.010, t_true khớp)
  - ELEVEN rule: Δproxy ≥ +0.005 → submit tự tin
Dùng: python3 analyze-ver8.py <output_dir>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Baseline ver-7 system-view trên 8 stems (wave1 v1 E1, official rule)
BASE = {
    "adjEJ": 0.9280,
    "div_tp": 2, "div_fp": 1, "div_fn": 10,
    "proxy": 0.9434,
    # per-stem adjEJ từ eval_report_official_self.json của ver-7b output (cùng 8 stems)
    # sẽ nạp động nếu tìm thấy file baseline
}


def jload(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception as e:
        print(f"  ! không đọc được {p.name}: {e}")
        return None


def micro(rows: list[dict]) -> dict:
    adj_rows = [r for r in rows if r.get("adjusted_edge_jaccard") is not None]
    wsum = sum(r["weight"] for r in adj_rows) or 1
    adj = (sum(r["adjusted_edge_jaccard"] * r["weight"] for r in adj_rows) / wsum) if adj_rows else None
    dtp = sum(r.get("div_tp") or 0 for r in rows)
    dfp = sum(r.get("div_fp") or 0 for r in rows)
    dfn = sum(r.get("div_fn") or 0 for r in rows)
    dj = dtp / (dtp + dfp + dfn) if (dtp + dfp + dfn) else None
    tp = sum(r.get("edge_tp") or 0 for r in rows)
    fp = sum(r.get("edge_fp") or 0 for r in rows)
    fn = sum(r.get("edge_fn") or 0 for r in rows)
    return {"n": len(rows), "adjEJ": adj, "edge_tp": tp, "edge_fp": fp, "edge_fn": fn,
            "div_tp": dtp, "div_fp": dfp, "div_fn": dfn, "divJ": dj,
            "proxy": (adj if adj is not None else 0.0) + (0.1 * dj if dj is not None else 0.0),
            "t_pred": sum(r.get("t_pred") or 0 for r in rows),
            "rows": {r["stem"]: r for r in rows}}


def main() -> int:
    outdir = Path(sys.argv[1])
    print(f"=== PHÂN TÍCH OUTPUT: {outdir} ===\n")

    # ---- 1) Guard report (topology + retention) ----
    guard = jload(outdir / "dual_seed_frame_retention_guard_report.json")
    if guard:
        sub = guard.get("submission", {})
        topo = guard.get("topology", {})
        phd = guard.get("phase_d", {})
        print("[GUARD REPORT]")
        print(f"  experiment: {guard.get('experiment')}")
        print(f"  submission rows: {sub.get('rows')} | sha256: {str(sub.get('sha256'))[:16]}…")
        tot_nodes = sum(v["nodes"] for v in topo.values())
        tot_edges = sum(v["edges"] for v in topo.values())
        div_parents = sum(v["division_parents"] for v in topo.values())
        print(f"  topology: {len(topo)} videos | {tot_nodes:,} nodes | {tot_edges:,} edges | division_parents TỔNG: {div_parents}")
        print(f"  phase_d (reparent): {json.dumps(phd)}")
        diag = guard.get("diagnostics", {})
        print(f"  retention: fallback_frames {diag.get('fallback_frames')}/{diag.get('rows')}")
        worst = sorted(diag.get("by_movie", {}).items(), key=lambda kv: kv[1]["minimum_retention"])[:3]
        for m, v in worst:
            print(f"    worst retention: {m} min={v['minimum_retention']:.3f} median={v['median_retention']:.3f}")
        print()

    # ---- 2) PPSWEEP selected ----
    sel = jload(outdir / "ppsweep_selected.json")
    if sel:
        print("[PPSWEEP]")
        print(f"  selected_label: {sel.get('selected_label')}")
        print(f"  selected_config: {json.dumps(sel.get('selected_config'))}")
        print()

    # ---- 3) PPSWEEP full results ----
    import csv
    pps = outdir / "ppsweep_results.csv"
    if pps.exists():
        print("[PPSWEEP BẢNG ĐẦY ĐỦ]")
        rows = list(csv.DictReader(pps.open()))
        rows.sort(key=lambda r: -float(r.get("proxy_score") or 0))
        for r in rows[:10]:
            print(f"  {r.get('config','?'):16s} proxy={r.get('proxy_score','?')} adj={r.get('adjusted_edge_jaccard','?')} div={r.get('div_tp','?')}/{r.get('div_fp','?')}/{r.get('div_fn','?')} sec={r.get('seconds','?')}")
        print()

    # ---- 4) Self-eval official ----
    ev = jload(outdir / "eval_report_official_self.json")
    cand_micro = None
    if ev and "samples" in ev:
        cand_micro = micro(ev["samples"])
        print("[SELF-EVAL OFFICIAL (system view, 8 stems)]")
        m = cand_micro
        print(f"  adjEJ = {m['adjEJ']:.4f} | divJ = {m['divJ']:.4f} | proxy = {m['proxy']:.4f}")
        print(f"  edge tp/fp/fn = {m['edge_tp']}/{m['edge_fp']}/{m['edge_fn']}")
        print(f"  div  tp/fp/fn = {m['div_tp']}/{m['div_fp']}/{m['div_fn']}")
        print(f"  t_pred = {m['t_pred']:,}")
        print()

    # ---- 5) Baseline so sánh + CỔNG SUBMIT ----
    # tìm baseline eval report (ver-7b output cũ trong repo)
    base_path = Path("/home/z/my-project/kaggle/api/output/latest/eval_report_official_self.json")
    base_micro = None
    if outdir.resolve() != base_path.parent.resolve() and base_path.exists():
        bev = jload(base_path)
        if bev and "samples" in bev:
            base_micro = micro(bev["samples"])

    print("[CỔNG SUBMIT — so baseline]")
    ok = {}
    if cand_micro:
        if base_micro and base_micro["rows"]:
            common = set(cand_micro["rows"]) & set(base_micro["rows"])
            if common:
                cb = micro([base_micro["rows"][s] for s in common])
                cc = micro([cand_micro["rows"][s] for s in common])
                print(f"  (so trên {len(common)} stems chung với ver-7b baseline)")
                base_use, cand_use = cb, cc
            else:
                base_use, cand_use = base_micro, cand_micro
        else:
            base_use = {"adjEJ": BASE["adjEJ"], "div_tp": BASE["div_tp"], "div_fp": BASE["div_fp"],
                        "div_fn": BASE["div_fn"], "proxy": BASE["proxy"], "t_pred": None, "rows": {}}
            cand_use = cand_micro
            print("  (so với baseline E1 wave1: adjEJ 0.9280, div 2/1/10)")
        d_adj = cand_use["adjEJ"] - base_use["adjEJ"]
        d_tp = (cand_use["div_tp"] or 0) - (base_use["div_tp"] or 0)
        d_fp = (cand_use["div_fp"] or 0) - (base_use["div_fp"] or 0)
        d_fn = (cand_use["div_fn"] or 0) - (base_use["div_fn"] or 0)
        d_prx = cand_use["proxy"] - base_use["proxy"]
        print(f"  ΔadjEJ = {d_adj:+.4f}   (cổng ≥ −0.0005)")
        print(f"  Δdiv_tp = {d_tp:+d}      (cổng ≥ +2)")
        print(f"  Δdiv_fp = {d_fp:+d}      (cổng ≤ +3)")
        print(f"  Δdiv_fn = {d_fn:+d}")
        print(f"  Δproxy  = {d_prx:+.4f}   (ELEVEN ≥ +0.005 → tự tin)")
        ok["adj"] = d_adj >= -0.0005
        ok["div_tp"] = d_tp >= 2
        ok["div_fp"] = d_fp <= 3
        ok["proxy"] = d_prx >= 0.005
        # G4: per-stem sụt > 0.010
        if base_use["rows"]:
            drops = [(s, cand_use["rows"][s]["adjusted_edge_jaccard"] - base_use["rows"][s]["adjusted_edge_jaccard"])
                     for s in base_use["rows"] if s in cand_use["rows"]]
            bad = [(s, d) for s, d in drops if d < -0.010]
            ok["G4"] = not bad
            print(f"  G4 video sụt > 0.010: {'KHÔNG' if not bad else bad}")
        # G3: node budget ±10%
        if base_use.get("t_pred"):
            ratio = cand_use["t_pred"] / base_use["t_pred"]
            ok["G3"] = 0.9 <= ratio <= 1.1
            print(f"  G3 node budget: t_pred ratio = {ratio:.3f} (cổng 0.9–1.1)")
        print()
        print("== KẾT LUẬN CỔNG ==")
        for k, v in ok.items():
            print(f"  [{'ĐẠT' if v else 'LỖI'}] {k}")
        submit_ok = ok.get("adj") and ok.get("div_tp") and ok.get("div_fp")
        print(f"\n>>> SUBMIT: {'ĐỦ ĐIỀU KIỆN (cốt lõi)' if submit_ok else 'CHƯA ĐỦ — xem các cổng LỖI'}"
              f"{' — Δproxy ≥ +0.005: TỰ TIN' if ok.get('proxy') else ''}")
    else:
        print("  ! Không có eval_report_official_self.json — kernel có thể chưa chạy đến phần eval.")

    # ---- 6) run_stats ----
    rs = outdir / "run_stats.csv"
    if rs.exists():
        print("\n[RUN_STATS] (5 dòng cuối)")
        lines = rs.read_text().splitlines()
        for ln in lines[-5:]:
            print("  " + ln[:200])

    return 0


if __name__ == "__main__":
    sys.exit(main())
