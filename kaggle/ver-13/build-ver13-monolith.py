#!/usr/bin/env python3
"""build-ver13-monolith.py — Dựng ver-13 monolith từ ver-12 (đã chạy RUN 2, LB 0.946).

Ver-13 = v12.1-knockout base + P1-P4 (V13-ADJEJ-RESEARCH.md §5 — trọng tâm adjEJ):

  P1 REVERT DIVERGE : SAFE_DIV_DIVERGE_UM −2.0 → 0.5 (đúng grid v11 mn_p85_div05 —
                       ĐÍNH CHÍNH research ghi 2.25: v11 production env dòng 102 ghi
                       đè dòng 64; guard phase_g + config label cùng xác nhận 0.5)
                       + SAFE_DIV_ORPHAN_ADOPT 1 → 0 (tắt nguồn +23 fork 05db).
                       → gate safe-div trở NGUYÊN VẸN hành xử v11 (baseline 0.947).
  P2 VELOCITY 0.25  : MOTION_RELINK_VELOCITY_WEIGHT 0.5 → 0.25 (knob có sẵn dòng
                       ~495/2442 monolith — sweep amanatar +0.0014 adj, dose-response
                       vel025 +0.0014 / vel075 −0.0007; combo thắng 0.948 gồm vel025).
  P3 LEAF-PRUNE     : port NGUYÊN VĂN prune_weak_leaf_nodes của amanatar v4 (~60 dòng,
                       notebook biohub-geometric-fusion cell 5 dòng 1365-1421) — cắt
                       node lá cuối track có cạnh vào yếu (< 0.30 learned prob); miễn
                       trừ con division (edge_prob None) + node frame cuối; single-pass
                       không cascade. Call-site: sau short-track filter, trước linefit
                       (đúng vị trí amanatar dòng 1635-1639).
  P4 DIVWIDE+DCSD   : SAFE_DIV_MAX_UM 9→11 · SISTER 14→16 · EXISTING_CHILD 10→12 ·
                       DEEPCENTER_SAFE_DIV 0.2→0.15 — recall division qua cổng hình
                       học rộng hơn + DC lỏng hơn, GIỮ divergence 0.5 nghiêm ngặt
                       (trục diverge-relax đã chết 2 nguồn độc lập: v12.1 LB −0.001 +
                       amanatar diverge150 FP 1→6).

Giữ nguyên từ v12.1-knockout: READMIT=0 · GAPFILL=0 · LOWDET=0 (E1+RUN2: node thêm
hại 2 stem thưa, TP division không phụ thuộc node thêm) · reparent EP=0.4 (no-op
production) · SEF_TTA 0.75 · VALIDATOR=0 (0.71h GPU/run).

9 thay đổi trên ver-12/cell-monolith.py (mỗi thay đổi must_count/replace_once):
  1. EXPERIMENT_TAG v12 → v13 (1 chỗ const — guard report 'experiment' đổi theo #8)
  2. env block [ver13] Phase I — NGAY SAU print [ver12] (assignment cuối cùng thắng;
     kỉ luật REVIEW-2: block mới luôn cuối, builder assert final-env từng key)
  3. hằng số LEAF_PRUNE_MIN_EDGE_PROB — sau LOWDET_DIR (nhóm hằng v12)
  4. hàm prune_weak_leaf_nodes — trước def filter_output_graph (nguyên văn amanatar)
  5. call-site leaf-prune — sau print short-track filtering, trước linefit
  6. stats init: keys leaf_prune_nodes/leaf_prune_edges
  7. guard _EXPECTED_NUMERIC: SAFE_DIV_MAX_UM 9→11 · DC 0.2→0.15 (2 hằng đổi) +
     THÊM 4 hằng v13 (VELOCITY 0.25 · LEAF 0.30 · SISTER 16 · EXISTING_CHILD 12) —
     5 hằng gốc còn lại NGUYÊN VẸN
  8. guard report: experiment tag + status phase_i_v13_adjEJ + phase_i dict (P1-P4) +
     divnet_mode audit v13
  9. final print progression + ver-13

Kiểm thử tĩnh: must_count mọi anchor + AST + py_compile + final-env-value assertion
(chống ghi đè thứ tự env — bài học REVIEW-2 v12). CPU-only 0 GPU — build local.
Determinism: build 2 lần → output identical (pure string ops, không thời gian/uuid).
"""
import ast
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VER12 = ROOT.parent / 'ver-12' / 'cell-monolith.py'
OUT = ROOT / 'cell-monolith.py'
CONFIG = ROOT / 'ver-13-config.json'


def must_count(text: str, needle: str, want: int, what: str) -> None:
    got = text.count(needle)
    if got != want:
        sys.exit(f'[build13] THẤT BẠI ở {what}: {needle[:60]!r} xuất hiện {got} lần (cần {want})')


def replace_once(text: str, old: str, new: str, what: str) -> str:
    must_count(text, old, 1, what)
    return text.replace(old, new, 1)


def fmt(v) -> str:
    if isinstance(v, bool):
        return '1' if v else '0'
    if isinstance(v, float):
        return repr(v)
    return str(v)


def main() -> int:
    cfg = json.loads(CONFIG.read_text())
    label = cfg['label']
    tag = f'secondary_deepcenter_tta_0947_reparent_hoct_v13_{label}'

    p1_div = float(cfg['p1_safe_div_diverge_um'])          # 0.5 (revert v11)
    p1_orphan = int(cfg['p1_orphan_adopt'])                 # 0
    p2_vel = float(cfg['p2_motion_relink_velocity_weight'])  # 0.25
    p3_leaf = float(cfg['p3_leaf_prune_min_edge_prob'])     # 0.3
    p4_sdmax = float(cfg['p4_safe_div_max_um'])             # 11.0
    p4_sister = float(cfg['p4_safe_div_sister_max_um'])     # 16.0
    p4_exist = float(cfg['p4_safe_div_existing_child_max_um'])  # 12.0
    p4_dc = float(cfg['p4_dc_safe_div_threshold'])          # 0.15
    # các key v12.1-knockout giữ nguyên — assert cuối build chống hồi quy
    rep_ep = float(cfg.get('reparent_edge_prob', 0.4))
    sef_w = float(cfg.get('sef_tta_weight', 0.75))
    val_en = int(cfg.get('validator_enable', 0))
    radmit_r = float(cfg.get('readmit_radius_um', 0))
    gf_gap = int(cfg.get('gapfill_max_gap', 0))
    lowdet = float(cfg.get('lowdet_threshold', 0))

    text = VER12.read_text()

    # ---- 0. tiền điều kiện: đúng là monolith ver-12 đã build (d2_divm2_ko) ----
    must_count(text, "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v12_portfolio_d2_divm2_ko'", 1, 'EXPERIMENT_TAG v12')
    must_count(text, "os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '-2.0'", 1, 'diverge âm v12')
    must_count(text, "os.environ['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '1'", 1, 'orphan ON v12')
    must_count(text, 'def filter_output_graph(', 1, 'filter_output_graph')
    must_count(text, 'def linefit_smooth_output_graph(', 1, 'linefit')
    must_count(text, 'def filter_short_track_components(', 1, 'short-track filter')
    must_count(text, "'status': 'phase_h_v12_portfolio'", 1, 'guard status v12')
    must_count(text, 'LEAF_PRUNE', 0, 'leaf-prune chưa tồn tại (chống double-build)')

    # ---- 1. EXPERIMENT_TAG (const) ----
    text = replace_once(
        text,
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v12_portfolio_d2_divm2_ko'",
        f"EXPERIMENT_TAG = '{tag}'",
        'EXPERIMENT_TAG v13',
    )

    # ---- 2. env block [ver13] Phase I — NGAY SAU print [ver12] (cuối cùng thắng) ----
    anchor_print12 = "print('[ver12] Phase H portfolio: reparent EP=0.4 | orphan-adopt=1 floor=0.5 | READMIT r=0.0um s>=0.965 | GAPFILL gap<=0 | lowdet>=0.0 | SEF_TTA w=0.75 | DC=0.2 | validator=OFF (ppsweep no-op, save ~90min GPU)' + ' | diverge=-2.0')"
    env13 = (
        '\n'
        "# [ver13] Phase I — TRỌNG TÂM adjEJ (V13-ADJEJ-RESEARCH.md §5; base v12.1-knockout LB 0.946).\n"
        "# Block chạy SAU [ver12] → assignment v13 là CUỐI CÙNG (kỉ luật REVIEW-2 v12;\n"
        "# builder assert final-env từng key — xem cuối build-ver13-monolith.py).\n"
        "# P1 REVERT: diverge −2.0→0.5 (đúng grid v11 mn_p85_div05 — research ghi 2.25 là\n"
        "#   nhầm: v11 production env dòng 102 GHI ĐÈ dòng 64; guard phase_g xác nhận 0.5)\n"
        "#   + orphan-adoption OFF → gate safe-div hành xử NGUYÊN VẸN như v11 (0.947).\n"
        "# P2 VELOCITY 0.25: sweep amanatar +0.0014 adj (dose-response rõ) — W cao làm\n"
        "#   predicted position OVERSHOOT → relink nối nhầm node láng giềng → FP cạnh.\n"
        "# P4 DIVWIDE+DCSD: cổng hình học rộng hơn + DC lỏng hơn, GIỮ divergence 0.5\n"
        "#   nghiêm ngặt — trục diverge-relax đã chết 2 nguồn độc lập (v12.1 LB −0.001,\n"
        "#   amanatar diverge150 FP nổ 1→6). P3 leaf-prune là HẰNG SỐ riêng (xem #3).\n"
        f"os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '{fmt(p1_div)}'\n"
        f"os.environ['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '{fmt(p1_orphan)}'\n"
        f"os.environ['BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT'] = '{fmt(p2_vel)}'\n"
        f"os.environ['BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB'] = '{fmt(p3_leaf)}'\n"
        f"os.environ['BIOHUB_SAFE_DIV_MAX_UM'] = '{fmt(p4_sdmax)}'\n"
        f"os.environ['BIOHUB_SAFE_DIV_SISTER_MAX_UM'] = '{fmt(p4_sister)}'\n"
        f"os.environ['BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM'] = '{fmt(p4_exist)}'\n"
        f"os.environ['BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD'] = '{fmt(p4_dc)}'\n"
        "print('[ver13] Phase I adjEJ: P1 diverge=" + fmt(p1_div) + " revert + orphan=" + fmt(bool(p1_orphan)) + " | P2 vel=" + fmt(p2_vel) + " | P3 leaf-prune>=" + fmt(p3_leaf) + " | P4 divwide " + fmt(p4_sdmax) + "/" + fmt(p4_sister) + "/" + fmt(p4_exist) + " + DC=" + fmt(p4_dc) + " | base v12.1 knockout: READMIT/GAPFILL/LOWDET off, reparent EP=" + fmt(rep_ep) + " (no-op), SEF_TTA " + fmt(sef_w) + ", validator " + ('ON' if val_en else 'OFF') + "')"
    )
    text = replace_once(text, anchor_print12, anchor_print12 + '\n' + env13, 'env block [ver13] sau print [ver12]')

    # ---- 3. hằng số LEAF_PRUNE — sau LOWDET_DIR (nhóm hằng [ver12]) ----
    # (neo mở rộng 2 dòng vì LOWDET_DIR xuất hiện 2 chỗ — dòng 581 là hằng số thật,
    # dòng 1673 nằm trong string patch script predict; neo kèm GAPFILL_MAX_ADDED_FRAC
    # phía trên để định danh duy nhất.)
    anchor_ld = ("GAPFILL_MAX_ADDED_FRAC = float(os.environ.get('BIOHUB_GAPFILL_MAX_ADDED_FRAC', '0.03'))\n"
                 "LOWDET_DIR = os.environ.get('BIOHUB_LOWDET_DIR', '').strip()")
    consts13 = anchor_ld + "\n" + (
        "# [ver13] Phase I — LEAF-PRUNE (port amanatar v4 nguyên văn; D3 research §3):\n"
        "# 0 = inert (không prune). Cắt node lá cuối track có cạnh vào yếu — 'đuôi rác'\n"
        "# nơi FP cạnh dồn dập. Miễn trừ: con division (edge_prob None), node frame\n"
        "# cuối (terminal hợp lệ), node >1 cạnh vào. Single-pass không cascade.\n"
        "LEAF_PRUNE_MIN_EDGE_PROB = float(os.environ.get('BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB', '0'))"
    )
    text = replace_once(text, anchor_ld, consts13, 'hằng số LEAF_PRUNE [ver13]')

    # ---- 4. hàm prune_weak_leaf_nodes — trước def filter_output_graph ----
    # NGUYÊN VĂN amanatar biohub-geometric-fusion.ipynb cell 5 dòng 1365-1421
    # (đã đối chiếu ppsweep_selected.json combo thắng leaf030=0.3) — chỉ thêm
    # comment nguồn [ver13]. Không đổi một dòng logic nào.
    leaf_fn = '''# [ver13] ==== P3 LEAF-PRUNE — port nguyên văn amanatar v4 (cell 5 dòng 1365-1421,
# notebook biohub-geometric-fusion LB 0.948; sweep leaf030 +0.0003/t55_leaf030
# +0.0004 adj; census họ −71 cạnh yếu). Receipt leaf_prune_nodes/leaf_prune_edges. ====
def prune_weak_leaf_nodes(
    nodes_by_id: dict[int, dict[str, object]],
    edges: list[dict[str, object]],
    stats: dict[str, int],
) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    """v4: remove terminal leaf nodes attached by a low-probability edge.

    A node is pruned only when ALL of the following hold:
      * it has no successor (out-degree 0) -- i.e. the tracker could not continue it;
      * it has exactly one incoming edge (never a division daughter ambiguity);
      * it does not sit on the final frame (terminal cells there are legitimate);
      * its single incoming edge HAS a learned probability and it is below
        LEAF_PRUNE_MIN_EDGE_PROB.
    Edges without a probability (edge_prob is None, e.g. safe-division additions)
    are exempt by construction, so division daughters added by add_safe_divisions_postlink
    can never be pruned here. Single pass, no cascade: conservative by design.
    """
    if LEAF_PRUNE_MIN_EDGE_PROB <= 0.0 or not nodes_by_id or not edges:
        return nodes_by_id, edges
    max_t = max(int(node["t"]) for node in nodes_by_id.values())
    out_degree: dict[int, int] = {}
    incoming: dict[int, list[dict[str, object]]] = {}
    for edge in edges:
        source_id = int(edge["source_id"])
        target_id = int(edge["target_id"])
        out_degree[source_id] = out_degree.get(source_id, 0) + 1
        incoming.setdefault(target_id, []).append(edge)
    drop: set[int] = set()
    for node_id, node in nodes_by_id.items():
        if out_degree.get(node_id, 0) != 0:
            continue
        if int(node["t"]) >= max_t:
            continue
        incoming_edges = incoming.get(node_id, [])
        if len(incoming_edges) != 1:
            continue
        prob = incoming_edges[0].get("edge_prob")
        if prob is None:
            continue
        try:
            prob = float(prob)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(prob):
            continue
        if prob < LEAF_PRUNE_MIN_EDGE_PROB:
            drop.add(node_id)
    if not drop:
        return nodes_by_id, edges
    kept_nodes = {node_id: node for node_id, node in nodes_by_id.items() if node_id not in drop}
    kept_edges = [
        edge for edge in edges
        if int(edge["source_id"]) not in drop and int(edge["target_id"]) not in drop
    ]
    stats["leaf_prune_nodes"] = len(drop)
    stats["leaf_prune_edges"] = len(edges) - len(kept_edges)
    return kept_nodes, kept_edges


def filter_output_graph('''
    text = replace_once(text, 'def filter_output_graph(', leaf_fn, 'hàm prune_weak_leaf_nodes')

    # ---- 5. call-site leaf-prune — sau short-track filter, trước linefit ----
    anchor_cs = '''    nodes_by_id, edges = filter_short_track_components(nodes_by_id, edges, stats)
    print(f"[{dataset}] after short-track filtering: {len(nodes_by_id)} nodes, {len(edges)} edges (components_removed = {stats['short_track_components_removed']})")
    nodes_by_id = linefit_smooth_output_graph(nodes_by_id, edges, stats)'''
    call13 = '''    nodes_by_id, edges = filter_short_track_components(nodes_by_id, edges, stats)
    print(f"[{dataset}] after short-track filtering: {len(nodes_by_id)} nodes, {len(edges)} edges (components_removed = {stats['short_track_components_removed']})")
    # [ver13] P3 LEAF-PRUNE — đúng vị trí amanatar (dòng 1635-1639 notebook): sau
    # short-track filter, TRƯỚC linefit (cắt đuôi rác trước khi làm mượt quỹ đạo).
    # Env-gated: LEAF_PRUNE_MIN_EDGE_PROB<=0 → inert (A/B được trên v13-lab).
    if LEAF_PRUNE_MIN_EDGE_PROB > 0.0:
        nodes_by_id, edges = prune_weak_leaf_nodes(nodes_by_id, edges, stats)
        if stats.get('leaf_prune_nodes'):
            print(f"[{dataset}] after weak-leaf pruning: {len(nodes_by_id)} nodes, {len(edges)} edges (leaf_pruned={stats['leaf_prune_nodes']})")
    nodes_by_id = linefit_smooth_output_graph(nodes_by_id, edges, stats)'''
    text = replace_once(text, anchor_cs, call13, 'call-site leaf-prune')

    # ---- 6. stats init: keys leaf_prune ----
    old_stats_tail = "'linefit_smoothed_nodes': 0, 'linefit_skipped_nodes': 0}"
    new_stats_tail = "'leaf_prune_nodes': 0, 'leaf_prune_edges': 0, 'linefit_smoothed_nodes': 0, 'linefit_skipped_nodes': 0}"
    text = replace_once(text, old_stats_tail, new_stats_tail, 'stats init leaf_prune')

    # ---- 7. guard _EXPECTED_NUMERIC: 2 hằng đổi + 4 hằng v13 thêm, 5 hằng gốc nguyên vẹn ----
    old_guard = "'BIOHUB_DET_THRESHOLD': 0.965, 'BIOHUB_ILP_APPEARANCE_WEIGHT': 0.0, 'BIOHUB_ILP_DISAPPEARANCE_WEIGHT': 2, 'BIOHUB_GAP_CLOSE_UM': 5.0, 'BIOHUB_OUTPUT_MIN_TRACK_LEN': 6.0, 'BIOHUB_SAFE_DIV_MAX_UM': 9.0, 'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': 0.2, 'BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT': 0.15, 'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': 0.75}"
    new_guard = (
        "'BIOHUB_DET_THRESHOLD': 0.965, 'BIOHUB_ILP_APPEARANCE_WEIGHT': 0.0, "
        "'BIOHUB_ILP_DISAPPEARANCE_WEIGHT': 2, 'BIOHUB_GAP_CLOSE_UM': 5.0, "
        "'BIOHUB_OUTPUT_MIN_TRACK_LEN': 6.0, "
        f"'BIOHUB_SAFE_DIV_MAX_UM': {p4_sdmax}, "
        f"'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': {p4_dc}, "
        "'BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT': 0.15, "
        f"'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': {sef_w}, "
        f"'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': {p2_vel}, "
        f"'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': {p3_leaf}, "
        f"'BIOHUB_SAFE_DIV_SISTER_MAX_UM': {p4_sister}, "
        f"'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': {p4_exist}}}"
    )
    text = replace_once(text, old_guard, new_guard, 'guard _EXPECTED_NUMERIC v13')

    # ---- 8. guard report: experiment + status + phase_i + divnet_mode ----
    old_report = "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v12_portfolio_d2_divm2_ko', 'status': 'phase_h_v12_portfolio', 'phase_h': {"
    new_report = (
        f"'experiment': '{tag}', 'status': 'phase_i_v13_adjEJ', "
        "'phase_i': {"
        f"'p1_safe_div_diverge_um': {p1_div}, 'p1_orphan_adopt': bool({p1_orphan}), "
        f"'p2_motion_relink_velocity_weight': {p2_vel}, "
        f"'p3_leaf_prune_min_edge_prob': {p3_leaf}, "
        f"'p4_safe_div_max_um': {p4_sdmax}, 'p4_safe_div_sister_max_um': {p4_sister}, "
        f"'p4_safe_div_existing_child_max_um': {p4_exist}, 'p4_dc_safe_div_threshold': {p4_dc}, "
        f"'knockout_kept': 'READMIT/GAPFILL/LOWDET off (v12.1)', "
        f"'config_label': '{label}', 'source': 'V13-ADJEJ-RESEARCH.md P1-P4 (build-ver13-monolith.py, 2026-09-22)'}}, "
        "'phase_h': {"
    )
    text = replace_once(text, old_report, new_report, 'guard report phase_i v13')

    old_dm = "'divnet_mode': 'RANK-ONLY (v12 gates: reparent EP=0.4 · orphan-adopt=ON floor=0.5 · READMIT r=0.0 · GAPFILL gap<=0 · SEF_TTA w=0.75 · DC=0.2)'"
    new_dm = (
        f"'divnet_mode': 'RANK-ONLY (v13 gates: P1 diverge={fmt(p1_div)} orphan={fmt(bool(p1_orphan))} · "
        f"P2 vel={fmt(p2_vel)} · P3 leaf>={fmt(p3_leaf)} · P4 divwide {fmt(p4_sdmax)}/{fmt(p4_sister)}/{fmt(p4_exist)} DC={fmt(p4_dc)} · "
        f"SEF_TTA w={fmt(sef_w)})'"
    )
    text = replace_once(text, old_dm, new_dm, 'divnet_mode audit v13')

    # ---- 9. final print progression ----
    text = replace_once(
        text,
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-10 hoct-veto mode1 -> ver-11 mutual_nn-off + MIN_PDIV floor -> ver-12 4-truc portfolio (reparent+orphan+readmit+gapfill)')",
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-10 hoct-veto mode1 -> ver-11 mutual_nn-off + MIN_PDIV floor -> ver-12 4-truc portfolio (reparent+orphan+readmit+gapfill) -> ver-13 adjEJ (P1 revert diverge 0.5 + P2 vel025 + P3 leaf-prune 0.30 + P4 divwide+dcsd015)')",
        'final print v13',
    )

    # ---- 10. kiểm tra sau xây ----
    required = (
        f"EXPERIMENT_TAG = '{tag}'",
        "os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '0.5'",
        "os.environ['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '0'",
        "os.environ['BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT'] = '0.25'",
        "os.environ['BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB'] = '0.3'",
        "os.environ['BIOHUB_SAFE_DIV_MAX_UM'] = '11.0'",
        "os.environ['BIOHUB_SAFE_DIV_SISTER_MAX_UM'] = '16.0'",
        "os.environ['BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM'] = '12.0'",
        "os.environ['BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD'] = '0.15'",
        'LEAF_PRUNE_MIN_EDGE_PROB = float(os.environ.get(',
        'def prune_weak_leaf_nodes',
        'nodes_by_id, edges = prune_weak_leaf_nodes(nodes_by_id, edges, stats)',
        "'leaf_prune_nodes': 0, 'leaf_prune_edges': 0",
        "stats[\"leaf_prune_nodes\"] = len(drop)",
        'phase_i_v13_adjEJ',
        '[ver13] Phase I adjEJ',
        'after weak-leaf pruning',
        'os.environ[\'BIOHUB_HOCT_VETO\'] = \'1\'',
        'def add_safe_divisions_postlink',
        'def add_reparent_divisions_postlink',
        'def readmit_discarded_detections',
        'def fill_gaps_from_low_detections',
        '_hv_finalize()',
    )
    for req in required:
        if req not in text:
            sys.exit(f'[build13] THẤT BẠI: thiếu {req!r}')
    for forbidden in (
        "'status': 'phase_h_v12_portfolio'",
        "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v12_portfolio_d2_divm2_ko'",
    ):
        if forbidden in text:
            sys.exit(f'[build13] THẤT BẠI: còn sót {forbidden!r}')
    # guard: 5 hằng gốc nguyên vẹn + 6 hằng v13 đúng config
    for guard_pair in (
        "'BIOHUB_DET_THRESHOLD': 0.965",
        "'BIOHUB_ILP_APPEARANCE_WEIGHT': 0.0",
        "'BIOHUB_ILP_DISAPPEARANCE_WEIGHT': 2",
        "'BIOHUB_GAP_CLOSE_UM': 5.0",
        "'BIOHUB_OUTPUT_MIN_TRACK_LEN': 6.0",
        "'BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT': 0.15",
        f"'BIOHUB_SAFE_DIV_MAX_UM': {p4_sdmax}",
        f"'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': {p4_dc}",
        f"'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': {sef_w}",
        f"'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': {p2_vel}",
        f"'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': {p3_leaf}",
        f"'BIOHUB_SAFE_DIV_SISTER_MAX_UM': {p4_sister}",
        f"'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': {p4_exist}",
    ):
        must_count(text, guard_pair, 1, f'guard {guard_pair}')

    # ---- 10-bis. final-env-value assertion (kỉ luật REVIEW-2 v12 — chống ghi đè) ----
    # Mọi key v13: assignment os.environ[KEY] = 'V' CUỐI CÙNG trong file phải là
    # giá trị config (block [ver13] chạy sau cùng). Cùng assert các key v12.1 giữ
    # nguyên (knockout) chống hồi quy im lặng.
    import re as _re

    def _final_env(src: str, key: str) -> str | None:
        vals = _re.findall(rf"os\.environ\['{key}'\] = '([^']*)'", src)
        return vals[-1] if vals else None

    _expected_final_env = {
        # P1-P4 (block [ver13] cuối cùng)
        'BIOHUB_SAFE_DIV_DIVERGE_UM': p1_div,
        'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': p1_orphan,
        'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': p2_vel,
        'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': p3_leaf,
        'BIOHUB_SAFE_DIV_MAX_UM': p4_sdmax,
        'BIOHUB_SAFE_DIV_SISTER_MAX_UM': p4_sister,
        'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': p4_exist,
        'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': p4_dc,
        # v12.1-knockout giữ nguyên (chống hồi quy)
        'BIOHUB_REPARENT_EDGE_PROB': rep_ep,
        'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': sef_w,
        'BIOHUB_VALIDATOR_ENABLE': val_en,
        'BIOHUB_READMIT_RADIUS_UM': radmit_r,
        'BIOHUB_GAPFILL_MAX_GAP': gf_gap,
        'BIOHUB_LOWDET_THRESHOLD': lowdet,
    }
    for _key, _want in _expected_final_env.items():
        _got = _final_env(text, _key)
        _want_str = str(_want)
        if _got != _want_str:
            sys.exit(f'[build13] THẤT BẠI final-env: {_key} cuối cùng = {_got!r} (cần {_want_str!r}) — có block legacy ghi đè SAU block [ver13]')
    print(f'[build13] final-env-value PASS: {len(_expected_final_env)} key (8 v13 + 6 v12.1-knockout) đều là assignment cuối cùng')

    # ---- 11. AST + py_compile ----
    ast.parse(text)
    OUT.write_text(text)
    py_compile.compile(str(OUT), doraise=True)
    print(f'[build13] ĐÃ GHI {OUT} ({len(text.splitlines())} dòng; ver-12 gốc {len(VER12.read_text().splitlines())} dòng)')
    print(f'[build13] config: label={label} | P1 diverge={p1_div} orphan={p1_orphan} | P2 vel={p2_vel} | P3 leaf>={p3_leaf} | P4 {p4_sdmax}/{p4_sister}/{p4_exist} DC={p4_dc}')
    print('[build13] 4 đề xuất: P1 revert diverge 0.5 + orphan OFF · P2 velocity 0.25 · P3 leaf-prune 0.30 (port amanatar) · P4 divwide+dcsd015 — mỗi lever env-gated cho A/B v13-lab')
    return 0


if __name__ == '__main__':
    sys.exit(main())
