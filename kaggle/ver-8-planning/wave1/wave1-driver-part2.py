# ============================================================================
# [wave1] PHẦN 2 — code MỚI (audit collector, replay grid, E1/E2/E3, official)
# Tất cả hàm postprocess/scoring ở trên là slice nguyên văn từ ver-7b monolith.
# ============================================================================

# --- hằng validator (slice từ monolith 3513-3517, đặt lại tại đây) ------------
VALIDATOR_MATCH_RADIUS_UM = float(os.environ.get('BIOHUB_VALIDATOR_MATCH_RADIUS_UM', '7.0'))
VALIDATOR_NODE_COUNT_PENALTY_A = float(os.environ.get('BIOHUB_VALIDATOR_NODE_COUNT_PENALTY_A', '0.1'))
VALIDATOR_DIVISION_WEIGHT = float(os.environ.get('BIOHUB_VALIDATOR_DIVISION_WEIGHT', '0.1'))

# --- bộ override "sweepable" (giống pp_apply/pp_restore của monolith) --------
WAVE1_PP_KEYS = ['SAFE_DIV_MAX_UM', 'SAFE_DIV_SISTER_MAX_UM', 'SAFE_DIV_DIVERGE_UM',
                'SAFE_DIV_SISTER_SYMMETRY_TAU', 'SAFE_DIV_EXISTING_CHILD_MAX_UM',
                'SAFE_DIV_FRAME_FRAC_CAP', 'SAFE_DIV_GLOBAL_FRAC_CAP',
                'DEEPCENTER_SAFE_DIV_THRESHOLD', 'DEEPCENTER_GAP_THRESHOLD',
                'GAP_CLOSE_UM', 'OUTPUT_MIN_TRACK_LEN',
                'SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB', 'MOTION_RELINK_TIGHT_UM',
                'MOTION_RELINK_RELAXED_UM', 'GAP2_MAX_STEP_UM', 'GAP2_MAX_TOTAL_UM',
                'MOTION_RELINK_LEARNED_BONUS', 'MOTION_RELINK_VELOCITY_WEIGHT',
                'GAP_CLOSE_REUSE_UM', 'OUTPUT_EDGE_MAX_UM']
WAVE1_BASE_CONFIG = {key: globals()[key] for key in WAVE1_PP_KEYS}


def wave1_pp_apply(config: dict) -> dict:
    saved = {key: globals()[key] for key in config}
    for key, value in config.items():
        if key not in WAVE1_PP_KEYS:
            raise KeyError(f'{key} is not sweepable')
        globals()[key] = type(WAVE1_BASE_CONFIG[key])(value)
    return saved


def wave1_pp_restore(saved: dict) -> None:
    for key, value in saved.items():
        globals()[key] = value


# ---------------------------------------------------------------------------
# [wave1] Ghi graph postprocess ra .geff — tái hiện NGUYÊN VĂN pattern
# build_graph + save_graph của repo (predict_unet_transformer.py dòng 118-145,
# 564): InMemoryGraph + add_node_attr_key z/y/x + bulk_add_nodes + edge keys
# edge_prob/edge_dist + to_geff.
# ---------------------------------------------------------------------------
def wave1_write_system_geff(nodes_by_id: dict, edges: list, out_path: Path) -> None:
    import polars as pl
    graph = td.graph.InMemoryGraph()
    for key in ['z', 'y', 'x']:
        graph.add_node_attr_key(key, pl.Float64, -999999.0)
    ordered = sorted(nodes_by_id.keys())
    new_ids = graph.bulk_add_nodes([
        {'t': int(nodes_by_id[nid]['t']), 'z': float(nodes_by_id[nid]['z']),
         'y': float(nodes_by_id[nid]['y']), 'x': float(nodes_by_id[nid]['x'])}
        for nid in ordered
    ])
    id_map = {old: new for old, new in zip(ordered, new_ids)}
    if edges:
        graph.add_edge_attr_key('edge_prob', pl.Float64, 0.0)
        graph.add_edge_attr_key('edge_dist', pl.Float64, 0.0)
        graph.bulk_add_edges([
            {'source_id': id_map[int(e['source_id'])], 'target_id': id_map[int(e['target_id'])],
             'edge_prob': float(e.get('edge_prob') if e.get('edge_prob') is not None else 0.0),
             'edge_dist': float(e.get('distance_um') if e.get('distance_um') is not None else 0.0)}
            for e in edges if int(e['source_id']) in id_map and int(e['target_id']) in id_map
        ])
    graph.to_geff(out_path)


# ---------------------------------------------------------------------------
# [wave1] E1 — system view: filter_output_graph (nguyên văn, config production
# + selected) → ghi .geff → chấm official scorer (đúng luật thật).
# ---------------------------------------------------------------------------
def wave1_official_score_geff(pred_path: Path, gt_path: Path, td_metrics, td_div) -> dict:
    evaluate, node_recall, per_sample_metrics = td_metrics
    score_divisions = td_div
    t_true = read_estimated_true_node_count(gt_path)
    pred = graph_from_geff(pred_path)
    gt = graph_from_geff(gt_path)
    er = evaluate(pred, gt, scale=VOXEL_SCALE_UM, max_distance=7.0)
    rec = node_recall(pred, gt) if (pred.num_nodes() and pred.num_edges()) else 0.0
    m = per_sample_metrics(er, t_true if t_true is not None else float('nan'), rec)
    div = score_divisions(graph_from_geff(pred_path), gt, scale=VOXEL_SCALE_UM, max_distance=7.0)
    scores = div.scores
    div_tp = sum(int(v) for v in scores.values())
    div_fn = len(scores) - div_tp
    div_fp = len(div.fp_forks)
    tp, fp, fn = int(m['edge_tp']), int(m['edge_fp']), int(m['edge_fn'])
    denom = tp + fp + fn
    ratio = float(m.get('total_node_ratio')) if m.get('total_node_ratio') is not None else None
    return {'stem': pred_path.stem, 'rule': 'official', 'edge_tp': tp, 'edge_fp': fp,
            'edge_fn': fn, 'edge_jaccard': (tp / denom if denom else None),
            't_pred': int(m.get('num_pred_nodes') or 0), 't_true': t_true,
            'total_node_ratio': ratio,
            'node_multiplier_term': (0.1 * ratio) if ratio is not None else None,
            'adjusted_edge_jaccard': m.get('adj_edge_jaccard'),
            'node_recall': m.get('node_recall'),
            'div_tp': div_tp, 'div_fp': div_fp, 'div_fn': div_fn,
            'division_jaccard': (div_tp / (div_tp + div_fp + div_fn)
                                 if (div_tp + div_fp + div_fn) else None),
            'weight': denom,
            'division_events': [{'gt_div_node': int(k), 'recovered': int(v)}
                                for k, v in sorted(scores.items())]}


def wave1_official_micro(rows: list) -> dict:
    tp = sum(r['edge_tp'] for r in rows)
    fp = sum(r['edge_fp'] for r in rows)
    fn = sum(r['edge_fn'] for r in rows)
    w = sum(r['weight'] for r in rows) or 1
    adj_rows = [r for r in rows if r.get('adjusted_edge_jaccard') is not None]
    adj = (sum(r['adjusted_edge_jaccard'] * r['weight'] for r in adj_rows)
           / sum(r['weight'] for r in adj_rows)) if adj_rows else None
    dtp = sum(r['div_tp'] for r in rows)
    dfp = sum(r['div_fp'] for r in rows)
    dfn = sum(r['div_fn'] for r in rows)
    dj = dtp / (dtp + dfp + dfn) if (dtp + dfp + dfn) else None
    return {'n': len(rows), 'edge_tp': tp, 'edge_fp': fp, 'edge_fn': fn,
            'edge_jaccard': tp / (tp + fp + fn) if (tp + fp + fn) else None,
            'adjusted_edge_jaccard': adj, 'div_tp': dtp, 'div_fp': dfp, 'div_fn': dfn,
            'division_jaccard': dj,
            'proxy_score': (adj if adj is not None else 0.0) + (0.1 * dj if dj is not None else 0.0)}


# --- chạy postprocess pipeline cho 1 stem (dùng hàm slice nguyên văn) --------
def wave1_run_pipeline(raw_nodes: dict, raw_edges: list, stem: str,
                       deepcenter_bundle, divnet_bundle=None):
    nodes_copy = {nid: dict(n) for nid, n in raw_nodes.items()}
    edges_copy = [dict(e) for e in raw_edges]
    processed_nodes, processed_edges, stage_stats = filter_output_graph(
        nodes_copy, edges_copy, dataset=stem,
        deepcenter_bundle=deepcenter_bundle, divnet_bundle=divnet_bundle)
    return processed_nodes, processed_edges, stage_stats


def wave1_internal_score(processed_nodes, processed_edges, gt_plain, t_true):
    pred_nodes_plain = nodes_by_id_to_plain(processed_nodes)
    pred_edges_plain = [(int(e['source_id']), int(e['target_id'])) for e in processed_edges]
    return score_sample(pred_nodes_plain, pred_edges_plain, gt_plain[0], gt_plain[1], t_true)


# ---------------------------------------------------------------------------
# [wave1] AUDIT COLLECTOR — đi qua cấu trúc add_safe_divisions_postlink với gate
# RỘNG NHẤT (MAX 14 / SISTER 18 / EXISTING_CHILD 12) để thu TOÀN BỘ đặc trưng
# của từng cặp (source, candidate). Đặc trưng KHÔNG phụ thuộc gate (đã phân tích
# kỹ: mutual-NN dùng candidate_ids cố định khung; divergence dùng pre-state;
# p_div theo node mẹ; dc_score theo điểm candidate) → grid E0 replay thuần số.
# ---------------------------------------------------------------------------
WAVE1_COLLECT_MAX_UM = 14.0
WAVE1_COLLECT_SISTER_MAX_UM = 18.0
WAVE1_COLLECT_EXISTING_CHILD_MAX_UM = 12.0


def wave1_collect_safe_div_features(stem, nodes_by_id, edges, deepcenter_bundle,
                                    divnet_bundle, frame_cache, deepcenter_cache,
                                    gt_plain):
    """Trả về dict đặc trưng + nhãn GT cho mọi cặp (source, candidate) trong tầm
    gate rộng nhất. Cấu trúc bám sát add_safe_divisions_postlink (monolith
    2908-3055) — chỉ THÊM ghi chép, KHÔNG đổi logic chọn."""
    gt_nodes, gt_edges = gt_plain
    p2g, g2p = match_nodes_bipartite(
        {nid: (int(n['t']), float(n['z']), float(n['y']), float(n['x']))
         for nid, n in nodes_by_id.items()}, gt_nodes, max_dist=7.0)
    gt_out_deg = Counter()
    gt_edge_set = set(gt_edges)
    for s, t in gt_edge_set:
        gt_out_deg[s] += 1

    out_by_source = {}
    incoming = set()
    for edge in edges:
        out_by_source.setdefault(int(edge['source_id']), []).append(edge)
        incoming.add(int(edge['target_id']))
    ids_by_t = {}
    for node_id, node in nodes_by_id.items():
        ids_by_t.setdefault(int(node['t']), []).append(node_id)
    existing_edges = {(int(e['source_id']), int(e['target_id'])) for e in edges}

    dc_scores = {}
    pdiv_cache = {}
    features = []  # từng dòng: dict đặc trưng đầy đủ

    def dc_score_of(candidate):
        cid = int(candidate['node_id'])
        if cid not in dc_scores:
            dc_scores[cid] = deepcenter_score_point(
                stem, int(candidate['t']), node_point(candidate), deepcenter_bundle,
                frame_cache, deepcenter_cache)
        return dc_scores[cid]

    def pdiv_of(source_id):
        if source_id not in pdiv_cache:
            if divnet_bundle is None:
                pdiv_cache[source_id] = None
            else:
                src = nodes_by_id[source_id]
                t_lo, t_hi = (min(ids_by_t), max(ids_by_t)) if ids_by_t else (0, 0)
                p = _divnet_score_queries(
                    divnet_bundle, stem,
                    [(int(src['t']), float(src['z']), float(src['y']), float(src['x']))],
                    frame_cache, t_lo, t_hi)
                pdiv_cache[source_id] = float(p[0]) if p else None
        return pdiv_cache[source_id]

    for t in sorted(ids_by_t):
        child_frame_ids = ids_by_t.get(t + 1, [])
        if not child_frame_ids:
            continue
        source_ids = [nid for nid in ids_by_t[t] if len(out_by_source.get(nid, [])) == 1]
        candidate_ids = [nid for nid in child_frame_ids if nid not in incoming]
        if not source_ids or not candidate_ids:
            continue
        candidate_positions = np.stack([_position_um(nodes_by_id[cid]) for cid in candidate_ids])
        candidate_tree = cKDTree(candidate_positions)
        for source_id in source_ids:
            source = nodes_by_id[source_id]
            existing_child_edge = out_by_source[source_id][0]
            existing_child_id = int(existing_child_edge['target_id'])
            existing_child = nodes_by_id.get(existing_child_id)
            if existing_child is None or int(existing_child['t']) != t + 1:
                continue
            child_dist = edge_distance_um(source, existing_child)
            if child_dist > WAVE1_COLLECT_EXISTING_CHILD_MAX_UM:
                continue
            _, nn_idx = candidate_tree.query(_position_um(existing_child))
            mutual_nn_id = candidate_ids[int(nn_idx)]
            c1_succ = out_by_source.get(existing_child_id, [])
            for candidate_id in candidate_ids:
                if (source_id, candidate_id) in existing_edges:
                    continue
                candidate = nodes_by_id[candidate_id]
                parent_dist = edge_distance_um(source, candidate)
                if parent_dist > WAVE1_COLLECT_MAX_UM:
                    continue
                sister_dist = edge_distance_um(existing_child, candidate)
                if sister_dist > WAVE1_COLLECT_SISTER_MAX_UM:
                    continue
                # divergence (đặc trưng)
                q_succ = out_by_source.get(candidate_id, [])
                diverge_margin = None
                if len(c1_succ) == 1 and len(q_succ) == 1:
                    c1g = nodes_by_id.get(int(c1_succ[0]['target_id']))
                    qg = nodes_by_id.get(int(q_succ[0]['target_id']))
                    if (c1g is not None and qg is not None
                            and int(c1g['t']) == t + 2 and int(qg['t']) == t + 2):
                        diverge_margin = edge_distance_um(c1g, qg) - sister_dist
                symmetry_ratio = abs(child_dist - parent_dist) / max((child_dist + parent_dist) / 2.0, 1e-6)
                dc_s = dc_score_of(candidate)
                p_d = pdiv_of(source_id)
                # nhãn GT
                g_s = p2g.get(int(source_id))
                g_c = p2g.get(int(candidate_id))
                gt_div_edge = bool(g_s is not None and g_c is not None
                                   and (g_s, g_c) in gt_edge_set and gt_out_deg.get(g_s, 0) >= 2)
                features.append({
                    'stem': stem, 't': int(t), 'source_id': int(source_id),
                    'candidate_id': int(candidate_id),
                    'existing_child_id': int(existing_child_id),
                    'parent_dist': float(parent_dist), 'sister_dist': float(sister_dist),
                    'child_dist': float(child_dist), 'mutual_nn': bool(candidate_id == mutual_nn_id),
                    'diverge_margin': (float(diverge_margin) if diverge_margin is not None else None),
                    'symmetry_ratio': float(symmetry_ratio),
                    'dc_score': (float(dc_s) if dc_s is not None else None),
                    'p_div': (float(p_d) if p_d is not None else None),
                    'gt_div_edge': gt_div_edge,
                    'gt_source': g_s, 'gt_candidate': g_c,
                })
    return {'features': features, 'gt_div_edges': sorted({(s, t) for s, t in gt_edge_set
                                                          if gt_out_deg.get(s, 0) >= 2})}


# ---------------------------------------------------------------------------
# [wave1] REPLAY — tái hiện chính xác chuỗi gate + xếp hạng + ngân sách của
# add_safe_divisions_postlink từ đặc trưng đã thu. Trả về (added_edges, stats).
# ---------------------------------------------------------------------------
def wave1_replay_safe_div(feats: list, edges: list, gates: dict, rank_mode, nodes_by_id):
    """gates: dict các giá trị SAFE_DIV_*; rank_mode: None | (W, pdiv_floor | None)."""
    g_max = float(gates['SAFE_DIV_MAX_UM'])
    g_sister = float(gates['SAFE_DIV_SISTER_MAX_UM'])
    g_tau = float(gates['SAFE_DIV_SISTER_SYMMETRY_TAU'])
    g_diverge = float(gates['SAFE_DIV_DIVERGE_UM'])
    g_exist = float(gates['SAFE_DIV_EXISTING_CHILD_MAX_UM'])
    g_frame_frac = float(gates['SAFE_DIV_FRAME_FRAC_CAP'])
    g_global_frac = float(gates['SAFE_DIV_GLOBAL_FRAC_CAP'])
    g_dc_thresh = float(gates['DEEPCENTER_SAFE_DIV_THRESHOLD'])
    W = float(rank_mode[0]) if rank_mode else 0.0
    pdiv_floor = float(rank_mode[1]) if (rank_mode and len(rank_mode) > 1 and rank_mode[1] is not None) else None

    out_by_source = {}
    incoming = set()
    for edge in edges:
        out_by_source.setdefault(int(edge['source_id']), []).append(edge)
        incoming.add(int(edge['target_id']))
    ids_by_t = {}
    for node_id in nodes_by_id:
        ids_by_t.setdefault(int(nodes_by_id[node_id]['t']), []).append(node_id)
    stats = {'geometric_candidates': 0, 'mutual_nn_rejected': 0, 'divergence_rejected': 0,
             'symmetry_rejected': 0, 'dc_rejected': 0, 'pdiv_floor_rejected': 0,
             'proposals': 0, 'added': 0, 'cap_skipped': 0,
             'added_gt_edges': 0, 'rank_flips': 0}
    global_cap = max(1, int(round(max(1, len(edges)) * g_global_frac)))
    added = []
    used_targets = set()
    used_sources = set()
    by_frame = {}
    for f in feats:
        by_frame.setdefault(f['t'], []).append(f)
    for t in sorted(by_frame):
        frame_feats = by_frame[t]
        source_ids = [nid for nid in ids_by_t.get(t, []) if len(out_by_source.get(nid, [])) == 1]
        frame_cap = max(1, int(round(len(source_ids) * g_frame_frac)))
        proposals = []
        for f in frame_feats:
            if f['child_dist'] > g_exist or f['parent_dist'] > g_max or f['sister_dist'] > g_sister:
                continue
            if not f['mutual_nn']:
                stats['mutual_nn_rejected'] += 1
                continue
            if g_diverge > 0:
                if f['diverge_margin'] is None or f['diverge_margin'] < g_diverge:
                    stats['divergence_rejected'] += 1
                    continue
            stats['geometric_candidates'] += 1
            if f['dc_score'] is not None and f['dc_score'] < g_dc_thresh:
                stats['dc_rejected'] += 1
                continue
            if g_tau > 0.0 and f['symmetry_ratio'] > g_tau:
                stats['symmetry_rejected'] += 1
                continue
            score = f['parent_dist'] + 0.15 * f['sister_dist']
            if W > 0.0 and f['p_div'] is not None:
                score = score - W * float(f['p_div'])
            if pdiv_floor is not None and (f['p_div'] is None or float(f['p_div']) < pdiv_floor):
                stats['pdiv_floor_rejected'] += 1
                continue
            proposals.append((score, f))
        stats['proposals'] += len(proposals)
        proposals.sort(key=lambda item: item[0])
        added_this_frame = 0
        for _score, f in proposals:
            if len(added) >= global_cap:
                stats['cap_skipped'] += 1
                break
            if added_this_frame >= frame_cap:
                break
            if f['candidate_id'] in used_targets or f['candidate_id'] in incoming:
                continue
            if f['source_id'] in used_sources:
                continue
            added.append({'source_id': f['source_id'], 'target_id': f['candidate_id'],
                          'edge_prob': None, 'distance_um': f['parent_dist'], 'safe_division': 1})
            if f['gt_div_edge']:
                stats['added_gt_edges'] += 1
            used_targets.add(f['candidate_id'])
            used_sources.add(f['source_id'])
            added_this_frame += 1
    stats['added'] = len(added)
    return added, stats


# ---------------------------------------------------------------------------
# [wave1] các giai đoạn sau safe-div (prune → short-track → linefit) — gọi đúng
# trình tự filter_output_graph (monolith 3373-3386).
# ---------------------------------------------------------------------------
def wave1_post_safediv_stages(nodes_by_id, edges):
    stats = {'short_track_components_removed': 0}
    incident = {int(e['source_id']) for e in edges} | {int(e['target_id']) for e in edges}
    if incident:
        kept = {nid: n for nid, n in nodes_by_id.items() if nid in incident}
        stats['pruned_isolated_nodes'] = len(nodes_by_id) - len(kept)
        nodes_by_id = kept
        edges = [e for e in edges if int(e['source_id']) in nodes_by_id
                 and int(e['target_id']) in nodes_by_id]
    nodes_by_id, edges = filter_short_track_components(nodes_by_id, edges, stats)
    nodes_by_id = linefit_smooth_output_graph(nodes_by_id, edges, stats)
    return nodes_by_id, edges


# ===========================================================================
# CHẠY CHÍNH
# ===========================================================================
def wave1_main():
    from tracking_cellmot.metrics import evaluate, node_recall, per_sample_metrics
    from tracking_cellmot.division_metrics import score_divisions
    td_metrics = (evaluate, node_recall, per_sample_metrics)
    td_div = score_divisions
    wave1_log('official scorer import OK')

    deepcenter_bundle = load_deepcenter_veto_detector()
    if deepcenter_bundle is None:
        raise RuntimeError('DeepCenter không nạp được (REQUIRE=1).')
    global DIVNET_ENABLE  # [wave1] env để 0 để add_safe_divisions_postlink nguyên văn không
    DIVNET_ENABLE = 1     # dùng divnet; ở đây bật TỪ TẪM để nạp ranker cho audit/E0.
    divnet_bundle = load_divnet_ranker()
    wave1_log(f'divnet_bundle: {"OK" if divnet_bundle else "None (E0 sẽ không có p_div)"}')

    # ---- nạp GT + raw preds (một lần) --------------------------------------
    GT_PLAIN = {}
    GT_TTRUE = {}
    RAW = {}
    for stem in WAVE1_STEMS:
        gt_path = TRAIN_DIR / f'{stem}.geff'
        gt_graph = graph_from_geff(gt_path)
        gt_nodes_plain, gt_edges_plain = graph_to_plain(gt_graph)
        GT_PLAIN[stem] = (gt_nodes_plain, gt_edges_plain)
        GT_TTRUE[stem] = read_estimated_true_node_count(gt_path)
        pred_graph = graph_from_geff(WAVE1_PRED_DIR / f'{stem}.geff')
        raw_nodes_by_id = {}
        for row in pred_graph.node_attrs().iter_rows(named=True):
            node_id = int(row['node_id'])
            raw_nodes_by_id[node_id] = {'node_id': node_id, 't': int(row['t']),
                                        'z': float(row['z']), 'y': float(row['y']),
                                        'x': float(row['x'])}
        raw_edges = []
        for row in pred_graph.edge_attrs().iter_rows(named=True):
            edge_prob = row.get('edge_prob') if hasattr(row, 'get') else None
            raw_edges.append({'source_id': int(row['source_id']),
                              'target_id': int(row['target_id']),
                              'edge_prob': None if edge_prob is None else float(edge_prob)})
        RAW[stem] = (raw_nodes_by_id, raw_edges)
        wave1_log(f'nạp {stem}: {len(raw_nodes_by_id)} nodes / {len(raw_edges)} edges')

    # ---- cache dùng chung (frame zarr + deepcenter heatmap) ----------------
    WAVE1_FRAME_CACHE = {}
    WAVE1_DC_CACHE = {}

    # =====================================================================
    # E1 — SYSTEM VIEW OFFICIAL (config production + selected tight55/dcgap035)
    # =====================================================================
    e1_rows = []
    e1_stage_stats = {}
    e1_internal_rows = []
    saved = wave1_pp_apply(E1_SELECTED)
    try:
        for stem in WAVE1_STEMS:
            t0 = time.time()
            raw_nodes, raw_edges = RAW[stem]
            pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem, deepcenter_bundle, None)
            e1_stage_stats[stem] = st
            irow = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
            irow['stem'] = stem
            irow['safe_divisions_added'] = st.get('safe_divisions_added', 0)
            e1_internal_rows.append(irow)
            out_geff = WAVE1_OUT / f'e1_system_{stem}.geff'
            wave1_write_system_geff(pn, pe, out_geff)
            row = wave1_official_score_geff(out_geff, TRAIN_DIR / f'{stem}.geff', td_metrics, td_div)
            e1_rows.append(row)
            wave1_log(f"E1 {stem}: adjEJ={row['adjusted_edge_jaccard']:.4f} "
                      f"div={row['div_tp']}/{row['div_fp']}/{row['div_fn']} "
                      f"({time.time() - t0:.0f}s)")
    finally:
        wave1_pp_restore(saved)
    e1_micro = wave1_official_micro(e1_rows)
    wave1_dump_json('wave1_e1_system_eval.json', {
        'schema': 'wave1-e1/1', 'tag': WAVE1_TAG,
        'config': 'ver-7 production + selected(tight55+dcgap035)',
        'samples': e1_rows, 'micro': e1_micro})
    wave1_log(f"E1 SYSTEM VIEW official: adjEJ={e1_micro['adjusted_edge_jaccard']:.4f} "
              f"div={e1_micro['div_tp']}/{e1_micro['div_fp']}/{e1_micro['div_fn']} "
              f"divJ={e1_micro['division_jaccard']} proxy={e1_micro['proxy_score']:.4f}")

    # =====================================================================
    # E0 — GATE AUDIT + GRID (pre-safe-div cache 1 lần, replay từng combo)
    # =====================================================================
    # pre-safe-div: chạy giai đoạn 1-6 của filter_output_graph với config
    # production + selected (đúng thứ tự monolith 3260-3335), rồi dừng trước
    # safe-div; cache kết quả cho mọi combo.
    saved = wave1_pp_apply(E1_SELECTED)
    PRE_STATE = {}
    PRE_STATS = {}

    def _full_stats() -> dict:
        # [wave1] copy nguyên văn dict khởi tạo stats của filter_output_graph
        # (monolith 3259) — motion_relink/gap dùng `+=` trên mọi key.
        return {'raw_edges': 0, 'dropped_nonconsecutive_edges': 0, 'dropped_long_edges': 0, 'dropped_multi_parent_edges': 0, 'dropped_multi_child_edges': 0, 'dropped_division_edges': 0, 'gap_candidates': 0, 'gap_pairs_selected': 0, 'gap_reused_existing': 0, 'gap_inserted_synthetic': 0, 'gap_added_nodes': 0, 'gap_added_edges': 0, 'gap_skipped_node_cap': 0, 'gap_density_nodes_scored': 0, 'gap_density_candidates_expanded': 0, 'gap_density_candidates_restricted': 0, 'gap_density_selected_outside_base': 0, 'gap_density_step_delta_milli_sum': 0, 'gap_refined_synthetic': 0, 'gap_refine_failed': 0, 'gap_refine_rejected_shift': 0, 'pruned_isolated_nodes': 0, 'motion_relink_edges': 0, 'motion_relink_tight_edges': 0, 'motion_relink_relaxed_edges': 0, 'motion_relink_frames': 0, 'motion_relink_replaced_raw_edges': 0, 'motion_relink_fallback_raw': 0, 'motion_relink_skipped_large_frame': 0, 'gap2_candidates': 0, 'gap2_pairs_selected': 0, 'gap2_added_nodes': 0, 'gap2_added_edges': 0, 'gap2_skipped_cap': 0, 'safe_division_candidates': 0, 'safe_division_geometric_candidates': 0, 'safe_divisions_added': 0, 'safe_division_skipped_cap': 0, 'safe_division_mutual_nn_rejected': 0, 'safe_division_divergence_rejected': 0, 'safe_division_symmetry_rejected': 0, 'divnet_proposals_scored': 0, 'divnet_rank_flips': 0, 'divnet_p_added_sum': 0.0, 'divnet_p_added_n': 0, 'deepcenter_gap_checked': 0, 'deepcenter_gap_bypassed_strong_motion': 0, 'deepcenter_gap_bypassed_observed_node': 0, 'deepcenter_gap_accepted': 0, 'deepcenter_gap_rejected': 0, 'deepcenter_gap_missing': 0, 'deepcenter_safe_div_checked': 0, 'deepcenter_safe_div_accepted': 0, 'deepcenter_safe_div_rejected': 0, 'deepcenter_safe_div_missing': 0, 'short_track_components_removed': 0, 'short_track_nodes_removed': 0, 'short_track_edges_removed': 0, 'short_track_filter_skipped_all': 0, 'short_track_rescue_triggered': 0, 'short_track_rescue_components': 0, 'short_track_rescue_nodes': 0, 'short_track_rescue_budget': 0, 'linefit_smoothed_nodes': 0, 'linefit_skipped_nodes': 0}

    try:
        for stem in WAVE1_STEMS:
            raw_nodes, raw_edges = RAW[stem]
            nodes_copy = {nid: dict(n) for nid, n in raw_nodes.items()}
            edges_copy = [dict(e) for e in raw_edges]
            nodes_by_id, edges = nodes_copy, edges_copy
            st = _full_stats()
            # (đối chiếu filter_output_graph 3260-3334 — giữ NGUYÊN VĂN logic)
            filtered_edges = []
            for edge in edges:
                source = nodes_by_id.get(int(edge['source_id']))
                target = nodes_by_id.get(int(edge['target_id']))
                if source is None or target is None:
                    continue
                if OUTPUT_ENFORCE_NEXT_FRAME and int(target['t']) != int(source['t']) + 1:
                    continue
                distance_um = edge_distance_um(source, target)
                edge['distance_um'] = distance_um
                if OUTPUT_EDGE_MAX_UM > 0 and distance_um > OUTPUT_EDGE_MAX_UM:
                    continue
                filtered_edges.append(edge)
            edges = filtered_edges
            if OUTPUT_MOTION_RELINK:
                learned_edge_probs = {}
                for edge in edges:
                    prob = edge.get('edge_prob')
                    if prob is None:
                        continue
                    try:
                        prob = float(prob)
                    except (TypeError, ValueError):
                        continue
                    if np.isfinite(prob):
                        learned_edge_probs[(int(edge['source_id']), int(edge['target_id']))] = \
                            max(learned_edge_probs.get((int(edge['source_id']), int(edge['target_id'])),
                                float('-inf')), prob)
                motion_edges = motion_relink_edges(nodes_by_id, st, learned_edge_probs)
                if motion_edges:
                    edges = motion_edges
            if OUTPUT_SINGLE_PARENT_REPAIR and edges:
                best_by_target = {}
                for edge in edges:
                    tid = int(edge['target_id'])
                    prev = best_by_target.get(tid)
                    if prev is None or edge_sort_key(edge) > edge_sort_key(prev):
                        best_by_target[tid] = edge
                kept = {id(e) for e in best_by_target.values()}
                edges = [e for e in edges if id(e) in kept]
            # (OUTPUT_SINGLE_CHILD_REPAIR = 0 trong production — bỏ qua như gốc)
            nodes_by_id, edges = close_single_frame_gaps(
                nodes_by_id, edges, st, dataset=stem,
                deepcenter_bundle=deepcenter_bundle,
                frame_cache=WAVE1_FRAME_CACHE, deepcenter_cache=WAVE1_DC_CACHE)
            nodes_by_id, edges = recover_strict_gap2(nodes_by_id, edges, st, dataset=stem)
            PRE_STATE[stem] = (nodes_by_id, edges)
            PRE_STATS[stem] = st
            wave1_log(f'pre-safe-div {stem}: {len(nodes_by_id)} nodes / {len(edges)} edges '
                      f"(gap_added={st['gap_added_nodes']}, motion_edges={st['motion_relink_edges']})")
    finally:
        wave1_pp_restore(saved)

    # thu đặc trưng (gate rộng nhất) — 1 lần/stem, chia sẻ cache
    FEATURES = {}
    for stem in WAVE1_STEMS:
        t0 = time.time()
        nodes_by_id, edges = PRE_STATE[stem]
        FEATURES[stem] = wave1_collect_safe_div_features(
            stem, nodes_by_id, edges, deepcenter_bundle, divnet_bundle,
            WAVE1_FRAME_CACHE, WAVE1_DC_CACHE, GT_PLAIN[stem])
        n_feats = len(FEATURES[stem]['features'])
        n_gt_div = len(FEATURES[stem]['gt_div_edges'])
        n_gt_hit = sum(1 for f in FEATURES[stem]['features'] if f['gt_div_edge'])
        wave1_log(f'audit {stem}: {n_feats} cặp / {n_gt_div} GT-div, trong tầm: {n_gt_hit} '
                  f'({time.time() - t0:.0f}s)')

    # ---- E0 SELF-CHECK: replay(production, không divnet) == E1 verbatim ------
    selfcheck = {'ok': True, 'diffs': [], 'row_diffs': []}
    prod_gates = {k: WAVE1_BASE_CONFIG[k] for k in
                  ['SAFE_DIV_MAX_UM', 'SAFE_DIV_SISTER_MAX_UM', 'SAFE_DIV_DIVERGE_UM',
                   'SAFE_DIV_SISTER_SYMMETRY_TAU', 'SAFE_DIV_EXISTING_CHILD_MAX_UM',
                   'SAFE_DIV_FRAME_FRAC_CAP', 'SAFE_DIV_GLOBAL_FRAC_CAP',
                   'DEEPCENTER_SAFE_DIV_THRESHOLD']}
    for stem in WAVE1_STEMS:
        nodes_by_id, edges = PRE_STATE[stem]
        replay_added, _rs = wave1_replay_safe_div(
            FEATURES[stem]['features'], edges, prod_gates, None, nodes_by_id)
        # đối chiếu gián tiếp qua số safe_divisions_added đã ghi trong stats E1
        verbatim_n = e1_stage_stats[stem].get('safe_divisions_added', 0)
        if verbatim_n != len(replay_added):
            selfcheck['ok'] = False
            selfcheck['diffs'].append({'stem': stem, 'verbatim_added': verbatim_n,
                                       'replay_added': len(replay_added)})
    wave1_log(f"SELF-CHECK replay vs verbatim: {'ĐẠT' if selfcheck['ok'] else 'LỆCH'} "
              f"{selfcheck['diffs'][:4]}")

    # ---- chẩn đoán 12 GT division: vì sao trượt (E3-div) --------------------
    div_diag = []
    for stem in WAVE1_STEMS:
        gt_nodes, gt_edges = GT_PLAIN[stem]
        feats = FEATURES[stem]['features']
        p2g, g2p = match_nodes_bipartite(
            {nid: (int(n['t']), float(n['z']), float(n['y']), float(n['x']))
             for nid, n in PRE_STATE[stem][0].items()}, gt_nodes, max_dist=7.0)
        gt_out = {}
        for s, t in gt_edges:
            gt_out.setdefault(s, set()).add(t)
        for g_src, children in gt_out.items():
            if len(children) < 2:
                continue
            ev = {'stem': stem, 'gt_div_node': int(g_src), 'children': sorted(children),
                  'parent_matched': bool(g_src in g2p)}
            c_match = [bool(c in g2p) for c in sorted(children)[:2]]
            ev['children_matched'] = c_match
            serving = [f for f in feats
                       if f['gt_source'] == g_src and f['gt_div_edge']]
            ev['n_serving_pairs'] = len(serving)
            if serving:
                best = min(serving, key=lambda f: f['parent_dist'])
                ev['best_pair'] = {k: best[k] for k in
                                   ('t', 'parent_dist', 'sister_dist', 'mutual_nn',
                                    'diverge_margin', 'symmetry_ratio', 'dc_score', 'p_div')}
                ev['reject_reason'] = []
                if not best['mutual_nn']:
                    ev['reject_reason'].append('mutual_nn')
                if best['diverge_margin'] is None:
                    ev['reject_reason'].append('divergence_no_grandchildren')
                elif best['diverge_margin'] < prod_gates['SAFE_DIV_DIVERGE_UM']:
                    ev['reject_reason'].append('divergence')
                if best['dc_score'] is not None and best['dc_score'] < prod_gates['DEEPCENTER_SAFE_DIV_THRESHOLD']:
                    ev['reject_reason'].append('deepcenter')
                if best['symmetry_ratio'] > prod_gates['SAFE_DIV_SISTER_SYMMETRY_TAU']:
                    ev['reject_reason'].append('symmetry')
                if best['parent_dist'] > prod_gates['SAFE_DIV_MAX_UM']:
                    ev['reject_reason'].append('parent_dist')
                if best['sister_dist'] > prod_gates['SAFE_DIV_SISTER_MAX_UM']:
                    ev['reject_reason'].append('sister_dist')
            else:
                ev['reject_reason'] = ['no_pair_in_range']
            div_diag.append(ev)
    wave1_dump_json('wave1_e0_div_diagnostics.json', {'schema': 'wave1-e0-diag/1',
                                                     'events': div_diag})
    n_no_pair = sum(1 for e in div_diag if 'no_pair_in_range' in e['reject_reason'])
    wave1_log(f'DIV DIAG: {len(div_diag)} sự kiện GT — {n_no_pair} không có cặp nào trong tầm')

    # ---- E0 GRID ------------------------------------------------------------
    E0_GRID = [
        ('base-v7', {}, None),
        ('dn-w15', {}, ('divnet', 15.0, None)),
        ('tau08-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8}, ('divnet', 15.0, None)),
        ('tau10-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0}, ('divnet', 15.0, None)),
        ('div15-dn15', {'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, None)),
        ('div10-dn15', {'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 15.0, None)),
        ('tau08-div15-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, None)),
        ('tau10-div10-dn15', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 15.0, None)),
        ('tau08-div15-dn25', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 25.0, None)),
        ('tau10-div10-dn25', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, None)),
        ('max12-tau08-div15-dn15', {'SAFE_DIV_MAX_UM': 12.0, 'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, None)),
        ('max12-tau10-div10-dn25', {'SAFE_DIV_MAX_UM': 12.0, 'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, None)),
        ('tau08-div15-dn15-pf50', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 0.8, 'SAFE_DIV_DIVERGE_UM': 1.5}, ('divnet', 15.0, 0.5)),
        ('tau10-div10-dn25-pf50', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, 0.5)),
        ('tau10-div10-dn25-pf30', {'SAFE_DIV_SISTER_SYMMETRY_TAU': 1.0, 'SAFE_DIV_DIVERGE_UM': 1.0}, ('divnet', 25.0, 0.3)),
    ]
    e0_rows = []
    for label, overrides, rank_mode in E0_GRID:
        if wave1_time_left() < 1800:
            wave1_log(f'E0 {label}: BỎ QUA (hết thời gian)')
            continue
        gates = dict(prod_gates)
        gates.update(overrides)
        t0 = time.time()
        agg_rows = []
        tot_stats = Counter()
        for stem in WAVE1_STEMS:
            nodes_by_id, edges = PRE_STATE[stem]
            import copy as _copy
            nodes_c = _copy.deepcopy(nodes_by_id)
            added, rstats = wave1_replay_safe_div(
                FEATURES[stem]['features'], edges, gates, rank_mode, nodes_c)
            tot_stats.update(rstats)
            new_edges = [dict(e) for e in edges] + added
            pn, pe = wave1_post_safediv_stages(nodes_c, new_edges)
            row = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
            row['stem'] = stem
            row['safe_divisions_added'] = rstats['added']
            row['added_gt_edges'] = rstats['added_gt_edges']
            agg_rows.append(row)
        summary = aggregate_official(agg_rows)
        e0_rows.append({'config': label, 'overrides': overrides, 'rank_mode': list(rank_mode) if rank_mode else None,
                        'summary': summary, 'replay_stats': dict(tot_stats),
                        'seconds': time.time() - t0, 'rows': agg_rows})
        if label == 'base-v7' and e1_internal_rows:
            for e0r, e1r in zip(agg_rows, e1_internal_rows):
                keys = ['edge_tp', 'edge_fp', 'edge_fn', 'edge_jaccard',
                        'adjusted_edge_jaccard', 'div_tp', 'div_fp', 'div_fn', 't_pred']
                bad = [k for k in keys
                       if abs(float(e0r[k] or 0) - float(e1r[k] or 0)) > 1e-9]
                if bad:
                    selfcheck['ok'] = False
                    selfcheck['row_diffs'].append({'stem': e0r['stem'], 'keys': bad,
                                                   'e0': {k: e0r[k] for k in bad},
                                                   'e1': {k: e1r[k] for k in bad}})
            wave1_log(f"SELF-CHECK end-to-end base-v7 vs E1: "
                      f"{'ĐẠT' if not selfcheck['row_diffs'] else 'LỆCH'} {selfcheck['row_diffs'][:2]}")
        wave1_log(f"E0 {label}: adjEJ={summary['adjusted_edge_jaccard']:.4f} "
                  f"div={summary['div_tp']}/{summary['div_fp']}/{summary['div_fn']} "
                  f"added={tot_stats['added']} added_gt={tot_stats['added_gt_edges']} "
                  f"({time.time() - t0:.0f}s)")
    # dump dạng CSV + JSON
    with (WAVE1_OUT / 'wave1_e0_grid.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['config', 'adjusted_edge_jaccard', 'division_jaccard', 'proxy_score',
                    'div_tp', 'div_fp', 'div_fn', 'added', 'added_gt_edges', 'seconds'])
        for r in e0_rows:
            s = r['summary']
            w.writerow([r['config'], s['adjusted_edge_jaccard'], s['division_jaccard'],
                        s['proxy_score'], s['div_tp'], s['div_fp'], s['div_fn'],
                        r['replay_stats'].get('added', 0),
                        r['replay_stats'].get('added_gt_edges', 0), round(r['seconds'], 1)])
    wave1_dump_json('wave1_e0_grid.json', {'schema': 'wave1-e0/1', 'selfcheck': selfcheck,
                                           'grid': [{k: v for k, v in r.items() if k != 'rows'}
                                                    for r in e0_rows]})

    # ---- E0: official cho top-5 theo (div_tp, -div_fp, proxy) ---------------
    ranked_e0 = sorted(e0_rows, key=lambda r: (r['summary']['div_tp'],
                                               -r['summary']['div_fp'],
                                               r['summary']['proxy_score']), reverse=True)
    e0_official_budget = 5
    for r in ranked_e0[:e0_official_budget]:
        if wave1_time_left() < 2400:
            wave1_log(f"E0-official {r['config']}: BỎ QUA (hết thời gian)")
            break
        t0 = time.time()
        rows_off = []
        for stem in WAVE1_STEMS:
            nodes_by_id, edges = PRE_STATE[stem]
            import copy as _copy
            nodes_c = _copy.deepcopy(nodes_by_id)
            gates = dict(prod_gates)
            gates.update(r['overrides'])
            added, _rs = wave1_replay_safe_div(
                FEATURES[stem]['features'], edges, gates,
                tuple(r['rank_mode']) if r['rank_mode'] else None, nodes_c)
            new_edges = [dict(e) for e in edges] + added
            pn, pe = wave1_post_safediv_stages(nodes_c, new_edges)
            out_geff = WAVE1_OUT / f"e0_{r['config']}_{stem}.geff"
            wave1_write_system_geff(pn, pe, out_geff)
            row = wave1_official_score_geff(out_geff, TRAIN_DIR / f'{stem}.geff',
                                            td_metrics, td_div)
            rows_off.append(row)
            out_geff.unlink()  # đỡ nặng output
        micro = wave1_official_micro(rows_off)
        r['official_micro'] = micro
        wave1_log(f"E0-OFFICIAL {r['config']}: adjEJ={micro['adjusted_edge_jaccard']:.4f} "
                  f"div={micro['div_tp']}/{micro['div_fp']}/{micro['div_fn']} "
                  f"divJ={micro['division_jaccard']} ({time.time() - t0:.0f}s)")
    wave1_dump_json('wave1_e0_grid_official.json',
                    {'schema': 'wave1-e0-official/1',
                     'official': [{'config': r['config'], 'official_micro': r.get('official_micro')}
                                  for r in e0_rows if r.get('official_micro')]})

    # =====================================================================
    # E2 — PPSWEEP-2 (config ngoài safe-div; chạy pipeline đầy đủ từng config)
    # =====================================================================
    PP2_GRID = [
        ('tight50', {'MOTION_RELINK_TIGHT_UM': 5.0}),
        ('tight55', {'MOTION_RELINK_TIGHT_UM': 5.5}),
        ('tight65', {'MOTION_RELINK_TIGHT_UM': 6.5}),
        ('relaxed8', {'MOTION_RELINK_RELAXED_UM': 8.0}),
        ('relaxed11', {'MOTION_RELINK_RELAXED_UM': 11.0}),
        ('bonus110', {'MOTION_RELINK_LEARNED_BONUS': 1.10}),
        ('bonus135', {'MOTION_RELINK_LEARNED_BONUS': 1.35}),
        ('vw040', {'MOTION_RELINK_VELOCITY_WEIGHT': 0.40}),
        ('vw060', {'MOTION_RELINK_VELOCITY_WEIGHT': 0.60}),
        ('gap55', {'GAP_CLOSE_UM': 5.5}),
        ('reuse36', {'GAP_CLOSE_REUSE_UM': 3.6}),
        ('gap2step48', {'GAP2_MAX_STEP_UM': 4.8}),
        ('minlen5', {'OUTPUT_MIN_TRACK_LEN': 5}),
        ('minlen7', {'OUTPUT_MIN_TRACK_LEN': 7}),
        ('rescue085', {'SHORT_TRACK_RESCUE_MIN_MEAN_EDGE_PROB': 0.85}),
        ('edgemax13', {'OUTPUT_EDGE_MAX_UM': 13.0}),
        ('dcgap030', {'DEEPCENTER_GAP_THRESHOLD': 0.30}),
        ('dcgap040', {'DEEPCENTER_GAP_THRESHOLD': 0.40}),
    ]
    # per-prefix (H4): 6bba disp_p99 7.9µm vs 44b6 4.9µm → tight khác nhau theo prefix
    PP2_PERPREFIX = [
        ('pp-tight-55-65', {'44b6': {'MOTION_RELINK_TIGHT_UM': 5.5},
                            '6bba': {'MOTION_RELINK_TIGHT_UM': 6.5}}),
        ('pp-tight-50-60', {'44b6': {'MOTION_RELINK_TIGHT_UM': 5.0},
                            '6bba': {'MOTION_RELINK_TIGHT_UM': 6.0}}),
    ]
    e2_rows = []
    base_summary = None
    for label, config in [('base', {})] + PP2_GRID:
        if wave1_time_left() < 1500:
            wave1_log(f'E2 {label}: BỎ QUA (hết thời gian)')
            continue
        t0 = time.time()
        saved = wave1_pp_apply(config)
        try:
            agg_rows = []
            for stem in WAVE1_STEMS:
                raw_nodes, raw_edges = RAW[stem]
                pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem,
                                               deepcenter_bundle, None)
                row = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
                row['stem'] = stem
                agg_rows.append(row)
        finally:
            wave1_pp_restore(saved)
        summary = aggregate_official(agg_rows)
        if label == 'base':
            base_summary = summary
        e2_rows.append({'config': label, 'overrides': config, 'summary': summary,
                        'seconds': time.time() - t0})
        wave1_log(f"E2 {label}: adjEJ={summary['adjusted_edge_jaccard']:.4f} "
                  f"div={summary['div_tp']}/{summary['div_fp']}/{summary['div_fn']} "
                  f"proxy={summary['proxy_score']:.4f} ({time.time() - t0:.0f}s)")
    for label, pp_config in PP2_PERPREFIX:
        if wave1_time_left() < 1500:
            wave1_log(f'E2 {label}: BỎ QUA (hết thời gian)')
            continue
        t0 = time.time()
        agg_rows = []
        try:
            for stem in WAVE1_STEMS:
                prefix = stem.split('_')[0]
                saved = wave1_pp_apply(pp_config.get(prefix, {}))
                try:
                    raw_nodes, raw_edges = RAW[stem]
                    pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem,
                                                   deepcenter_bundle, None)
                finally:
                    wave1_pp_restore(saved)
                row = wave1_internal_score(pn, pe, GT_PLAIN[stem], GT_TTRUE[stem])
                row['stem'] = stem
                agg_rows.append(row)
        except Exception as exc:
            wave1_log(f'E2 {label}: LỖI {exc}')
            continue
        summary = aggregate_official(agg_rows)
        e2_rows.append({'config': label, 'overrides': pp_config, 'per_prefix': True,
                        'summary': summary, 'seconds': time.time() - t0})
        wave1_log(f"E2 {label}: adjEJ={summary['adjusted_edge_jaccard']:.4f} "
                  f"div={summary['div_tp']}/{summary['div_fp']}/{summary['div_fn']} "
                  f"proxy={summary['proxy_score']:.4f} ({time.time() - t0:.0f}s)")
    with (WAVE1_OUT / 'wave1_e2_ppsweep2.csv').open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['config', 'adjusted_edge_jaccard', 'division_jaccard', 'proxy_score',
                    'div_tp', 'div_fp', 'div_fn', 'seconds'])
        for r in e2_rows:
            s = r['summary']
            w.writerow([r['config'], s['adjusted_edge_jaccard'], s['division_jaccard'],
                        s['proxy_score'], s['div_tp'], s['div_fp'], s['div_fn'],
                        round(r['seconds'], 1)])
    wave1_dump_json('wave1_e2_ppsweep2.json', {'schema': 'wave1-e2/1', 'rows': e2_rows})

    # ---- E2: official cho top-3 (khác base) + base -------------------------
    if base_summary is not None:
        cand = [r for r in e2_rows
                if r['config'] != 'base'
                and r['summary']['proxy_score'] >= base_summary['proxy_score'] + 0.0005
                and r['summary']['adjusted_edge_jaccard']
                >= base_summary['adjusted_edge_jaccard'] - 0.0005]
        cand.sort(key=lambda r: r['summary']['proxy_score'], reverse=True)
        for r in cand[:3]:
            if wave1_time_left() < 2400:
                wave1_log(f"E2-official {r['config']}: BỎ QUA (hết thời gian)")
                break
            t0 = time.time()
            rows_off = []
            for stem in WAVE1_STEMS:
                raw_nodes, raw_edges = RAW[stem]
                if r.get('per_prefix'):
                    prefix = stem.split('_')[0]
                    saved = wave1_pp_apply(r['overrides'].get(prefix, {}))
                else:
                    saved = wave1_pp_apply(r['overrides'])
                try:
                    pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem,
                                                   deepcenter_bundle, None)
                finally:
                    wave1_pp_restore(saved)
                out_geff = WAVE1_OUT / f"e2_{r['config']}_{stem}.geff"
                wave1_write_system_geff(pn, pe, out_geff)
                row = wave1_official_score_geff(out_geff, TRAIN_DIR / f'{stem}.geff',
                                                td_metrics, td_div)
                rows_off.append(row)
                out_geff.unlink()
            micro = wave1_official_micro(rows_off)
            r['official_micro'] = micro
            wave1_log(f"E2-OFFICIAL {r['config']}: adjEJ={micro['adjusted_edge_jaccard']:.4f} "
                      f"div={micro['div_tp']}/{micro['div_fp']}/{micro['div_fn']} "
                      f"({time.time() - t0:.0f}s)")
        wave1_dump_json('wave1_e2_ppsweep2_official.json',
                        {'schema': 'wave1-e2-official/1',
                         'official': [{'config': r['config'], 'official_micro': r.get('official_micro')}
                                      for r in e2_rows if r.get('official_micro')]})

    # =====================================================================
    # E3 — chẩn đoán 2 video xấu nhất (6bba_07e24132 / 44b6_267148e4)
    # =====================================================================
    e3 = {}
    for stem in ('6bba_07e24132', '44b6_267148e4'):
        if stem not in WAVE1_STEMS:
            continue
        row = next((r for r in e1_rows if r['stem'] == stem), None)
        gt_nodes, gt_edges = GT_PLAIN[stem]
        raw_nodes, raw_edges = RAW[stem]
        # chạy lại production để có đồ thị hệ (đã có trong E1 nhưng không giữ)
        saved = wave1_pp_apply(E1_SELECTED)
        try:
            pn, pe, st = wave1_run_pipeline(raw_nodes, raw_edges, stem, deepcenter_bundle, None)
        finally:
            wave1_pp_restore(saved)
        pred_plain = nodes_by_id_to_plain(pn)
        pred_edges_plain = [(int(e['source_id']), int(e['target_id'])) for e in pe]
        p2g, g2p = match_nodes_bipartite(pred_plain, gt_nodes, max_dist=7.0)
        fn_by_t = Counter()
        fp_by_t = Counter()
        gt_out = {}
        for s, t in gt_edges:
            gt_out.setdefault(s, set()).add(t)
        gt_edge_set = set(gt_edges)
        matched_gt = set()
        for s, t in pred_edges_plain:
            ms, mt = p2g.get(s), p2g.get(t)
            if ms is not None and mt is not None and mt in gt_out.get(ms, ()):
                matched_gt.add((ms, mt))
            else:
                fp_by_t[int(pred_plain[s][0])] += 1
        for gs, gt_ in gt_edge_set:
            if (gs, gt_) not in matched_gt:
                fn_by_t[int(gt_nodes[gs][0])] += 1
        t_true = GT_TTRUE[stem]
        nodes_by_t = Counter(int(n[0]) for n in pred_plain.values())
        e3[stem] = {
            'official_row': row,
            'fn_edges_by_frame': dict(sorted(fn_by_t.items())),
            'fp_edges_by_frame': dict(sorted(fp_by_t.items())),
            'pred_nodes_by_frame': dict(sorted(nodes_by_t.items())),
            't_true_estimated': t_true,
            'overprediction_ratio': row.get('total_node_ratio') if row else None,
            'node_recall': row.get('node_recall') if row else None,
        }
        wave1_log(f'E3 {stem}: fn_edges={dict(list(sorted(fn_by_t.items()))[:8])}...')
    wave1_dump_json('wave1_e3_badvideos.json', {'schema': 'wave1-e3/1', 'videos': e3})

    # =====================================================================
    # TỔNG KẾT
    # =====================================================================
    best_e0 = max((r for r in e0_rows), key=lambda r: (r['summary']['div_tp'],
                                                       -r['summary']['div_fp'],
                                                       r['summary']['proxy_score']),
                  default=None)
    summary = {
        'schema': 'wave1-summary/1', 'tag': WAVE1_TAG,
        'e1_system_micro': e1_micro,
        'selfcheck_replay_vs_verbatim': selfcheck,
        'div_diagnostics': {'n_events': len(div_diag),
                            'no_pair_in_range': n_no_pair,
                            'reject_reasons': dict(Counter(
                                reason for e in div_diag for reason in e['reject_reason']))},
        'e0_best': ({'config': best_e0['config'], 'summary': best_e0['summary'],
                     'replay_stats': best_e0['replay_stats'],
                     'official_micro': best_e0.get('official_micro')}
                    if best_e0 else None),
        'e0_all': [{'config': r['config'], 'div': f"{r['summary']['div_tp']}/{r['summary']['div_fp']}/{r['summary']['div_fn']}",
                    'proxy': round(r['summary']['proxy_score'], 6),
                    'adjEJ': round(r['summary']['adjusted_edge_jaccard'], 6),
                    'official': (round(r['official_micro']['proxy_score'], 6)
                                 if r.get('official_micro') else None)}
                   for r in e0_rows],
        'e2_all': [{'config': r['config'], 'div': f"{r['summary']['div_tp']}/{r['summary']['div_fp']}/{r['summary']['div_fn']}",
                    'proxy': round(r['summary']['proxy_score'], 6),
                    'adjEJ': round(r['summary']['adjusted_edge_jaccard'], 6),
                    'official': (round(r['official_micro']['proxy_score'], 6)
                                 if r.get('official_micro') else None)}
                   for r in e2_rows],
        'runtime_seconds': time.time() - WAVE1_T0,
    }
    wave1_dump_json('wave1_summary.json', summary)
    wave1_log('WAVE-1 HOÀN TẤT')


try:
    wave1_main()
except Exception:
    print('[wave1] LỖI CHÍNH — traceback:')
    _tb.print_exc()
    raise
