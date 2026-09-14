#!/usr/bin/env python3
"""wave1-report.py — đọc output kernel biohub-ver8-wave1 (đã tải về local) và
in báo cáo quyết định cho ver-8:
  1) E1 system-view official vs core view (đọc đôi đã sửa chưa)
  2) E0 grid: bảng 15 combo (internal + official) + self-check + đề xuất
  3) Div diagnostics: gate nào giết 12 GT division
  4) E2 ppsweep-2: bảng + winner đạt guards
  5) E3: 2 video xấu
  6) KẾT LUẬN: config ver-8 đề xuất + cổng submit đánh giá

Usage: python3 wave1-report.py [output_dir]
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / 'api' / 'output' / 'latest'


def load(name):
    p = OUT / name
    if not p.exists():
        return None
    return json.loads(p.read_text())


def fmt_micro(m, label=''):
    if not m:
        return f'{label}: (không có)'
    return (f"{label}: adjEJ={m['adjusted_edge_jaccard']:.4f} "
            f"EJ={m['edge_jaccard']:.4f} div={m['div_tp']}/{m['div_fp']}/{m['div_fn']} "
            f"divJ={(m['division_jaccard'] or 0):.4f} proxy={m['proxy_score']:.4f}")


def main() -> int:
    print('=' * 78)
    print('WAVE-1 REPORT — quyết định ver-8')
    print('=' * 78)
    summary = load('wave1_summary.json')
    e1 = load('wave1_e1_system_eval.json')
    e0 = load('wave1_e0_grid.json')
    e0off = load('wave1_e0_grid_official.json')
    e0diag = load('wave1_e0_div_diagnostics.json')
    e2 = load('wave1_e2_ppsweep2.json')
    e2off = load('wave1_e2_ppsweep2_official.json')
    e3 = load('wave1_e3_badvideos.json')

    if summary is None:
        print('THIẾU wave1_summary.json — kernel chưa xong hoặc lỗi. Xem các file có:')
        for p in sorted(OUT.glob('wave1_*')):
            print('  ', p.name)
        return 1

    print(f"\nruntime: {summary.get('runtime_seconds', 0) / 60:.0f} phút")
    print(f"selfcheck replay==verbatim: {summary['selfcheck_replay_vs_verbatim']}")

    print('\n--- 1) E1 — SYSTEM VIEW OFFICIAL (production + tight55+dcgap035) ---')
    print(fmt_micro(e1['micro'] if e1 else summary.get('e1_system_micro'), 'SYSTEM '))
    print('   (đối chiếu CORE view 0.9345 / div 0/0/12 — eval_report_official_self)')
    if e1:
        print(f"   per-stem:")
        for s in e1['samples']:
            print(f"     {s['stem']:22s} adjEJ={s['adjusted_edge_jaccard']:.4f} "
                  f"div={s['div_tp']}/{s['div_fp']}/{s['div_fn']} ratio={s['total_node_ratio']:+.3f}")

    print('\n--- 2) E0 GRID (internal rule; official = top) ---')
    off_map = {}
    if e0off:
        for r in e0off['official']:
            off_map[r['config']] = r.get('official_micro')
    print(f"{'config':26s} {'adjEJ':>7s} {'div':>9s} {'proxy':>8s} {'added':>6s} {'addGT':>6s} {'OFF proxy':>9s}")
    for r in (e0 or {}).get('grid', []):
        s = r['summary']
        st = r['replay_stats']
        o = off_map.get(r['config'])
        print(f"{r['config']:26s} {s['adjusted_edge_jaccard']:7.4f} "
              f"{s['div_tp']:2d}/{s['div_fp']:2d}/{s['div_fn']:2d} {s['proxy_score']:8.4f} "
              f"{st.get('added', 0):6d} {st.get('added_gt_edges', 0):6d} "
              f"{(o['proxy_score'] if o else float('nan')):9.4f}")
    if e0diag:
        print(f"\n--- 3) DIV DIAGNOSTICS — {e0diag.get('n', '?')} sự kiện được dump "
              f"(xem wave1_e0_div_diagnostics.json) ---")
        from collections import Counter
        reasons = Counter(reason for e in e0diag['events'] for reason in e['reject_reason'])
        for reason, n in reasons.most_common():
            print(f'     {reason}: {n}')

    print('\n--- 4) E2 PPSWEEP-2 ---')
    off2 = {}
    if e2off:
        for r in e2off['official']:
            off2[r['config']] = r.get('official_micro')
    base = next((r for r in (e2 or {}).get('rows', []) if r['config'] == 'base'), None)
    if base:
        print(fmt_micro(base['summary'], 'BASE  '))
    print(f"{'config':16s} {'adjEJ':>7s} {'div':>9s} {'proxy':>8s} {'Δproxy':>8s} {'OFF':>8s}")
    for r in (e2 or {}).get('rows', []):
        s = r['summary']
        if r['config'] == 'base':
            continue
        dp = s['proxy_score'] - (base['summary']['proxy_score'] if base else 0)
        o = off2.get(r['config'])
        print(f"{r['config']:16s} {s['adjusted_edge_jaccard']:7.4f} "
              f"{s['div_tp']:2d}/{s['div_fp']:2d}/{s['div_fn']:2d} {s['proxy_score']:8.4f} "
              f"{dp:+8.4f} {(o['proxy_score'] if o else float('nan')):8.4f}")

    print('\n--- 5) E3 — 2 video xấu ---')
    if e3:
        for stem, v in e3.get('videos', {}).items():
            row = v.get('official_row') or {}
            print(f"  {stem}: adjEJ={row.get('adjusted_edge_jaccard')} ratio={v.get('overprediction_ratio')} "
                  f"recall={v.get('node_recall')} fn_frames={len(v.get('fn_edges_by_frame', {}))} "
                  f"fp_frames={len(v.get('fp_edges_by_frame', {}))}")

    print('\n--- 6) ĐỀ XUẤT ---')
    best = summary.get('e0_best')
    if best:
        print(f"E0 tốt nhất: {best['config']} internal={best['summary']['proxy_score']:.4f} "
              f"official={(best.get('official_micro') or {}).get('proxy_score', float('nan')):.4f}")
    print('→ Xem E0/E2 bảng trên: combo đạt (div_tp tăng, div_fp ≤ +3, adjEJ không tụt, "
          'official đồng thuận) = ứng viên ver-8.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
