# ==== [ver9-hoct-finalize] Đảm bảo veto áp đúng 1 lần vào submission cuối =================
# Port cell 12 sjlee101: nếu lần ghi nào đó đã wrap (applied_writes > 0) → chỉ in summary;
# nếu resume skip hết các lần ghi → re-write 1 lần với veto. Không bao giờ raise.
_hv_finalize()

# ==== [ver9-rlf] Repeat-lineage division filter (output-level, SAU HOCT veto) =============
# Port nguyên văn logic cell 10.5 pawanmali/biohub-942tta-fork-divfix-v1: với mỗi fork
# (out-degree >= 2) mà TỔ TIÊN cũng là fork — GT thật 0/132 divisions lặp lineage (pawanmali
# đo trên pipeline riêng, +0.0021) — bỏ cạnh con XA hơn (µm), giữ cạnh gần nhất. Chỉ bỏ cạnh,
# không đụng node set (assert), topology audit lại sau lọc. Guard §6 rev-2: số cạnh bỏ
# <= 0.5% tổng cạnh — vượt thì HOÀN TÁC (fail-safe một chiều, giữ submission đã có veto).
# Chạy SAU veto vì RLF chỉ tác động cạnh division (rev-2 sửa E5: chạy trước veto làm cạnh con
# còn lại bị lộ ra diện veto, mất cạnh oan).
RLF_ENABLE = os.environ.get('BIOHUB_RLF_ENABLE', '1') != '0'
RLF_MAX_EDGE_FRAC = float(os.environ.get('BIOHUB_RLF_MAX_EDGE_FRAC', '0.005'))
RLF_REPORT_PATH = WORKING_DIR / 'ver9_rlf_report.json'
_rlf_report: dict[str, object] = {'enabled': RLF_ENABLE}

if RLF_ENABLE:
    _rlf_df = pd.read_csv(SUBMISSION_PATH)
    assert _rlf_df.columns.tolist() == CSV_COLUMNS, _rlf_df.columns.tolist()
    _rlf_backup_path = SUBMISSION_PATH.with_name('submission_before_rlf.csv')
    _rlf_backup_path.write_bytes(SUBMISSION_PATH.read_bytes())
    _rlf_out_rows: list[dict[str, object]] = []
    _rlf_total_dropped = 0
    _rlf_total_edges_before = 0
    _rlf_by_dataset: dict[str, dict[str, int]] = {}

    for _ds, _grp in _rlf_df.groupby('dataset', sort = True):
        _nodes = _grp[_grp.row_type.eq('node')]
        _edges = _grp[_grp.row_type.eq('edge')]
        _rlf_total_edges_before += len(_edges)
        _pos = {int(r.node_id): (float(r.z), float(r.y), float(r.x)) for r in _nodes.itertuples()}
        _edge_list = [{'source_id': int(r.source_id), 'target_id': int(r.target_id)} for r in _edges.itertuples()]
        _out_by_source: dict[int, list[dict]] = {}
        _pred_of: dict[int, int] = {}
        for _e in _edge_list:
            _out_by_source.setdefault(_e['source_id'], []).append(_e)
            _pred_of[_e['target_id']] = _e['source_id']
        _divider_nodes = {s for s, es in _out_by_source.items() if len(es) >= 2}

        def _rlf_already_divided(node_id: int, _pred_of = _pred_of, _divider_nodes = _divider_nodes) -> bool:
            cur = _pred_of.get(node_id)
            while cur is not None:
                if cur in _divider_nodes:
                    return True
                cur = _pred_of.get(cur)
            return False

        def _rlf_edge_dist(e: dict, _pos = _pos) -> float:
            sz, sy, sx = _pos[e['source_id']]
            tz, ty, tx = _pos[e['target_id']]
            dz = (sz - tz) * VOXEL_SCALE_UM[0]
            dy = (sy - ty) * VOXEL_SCALE_UM[1]
            dx = (sx - tx) * VOXEL_SCALE_UM[2]
            return (dz * dz + dy * dy + dx * dx) ** 0.5

        _dropped_ids: set[int] = set()
        for _s, _es in _out_by_source.items():
            if len(_es) < 2:
                continue
            if _rlf_already_divided(_s):
                _ranked = sorted(_es, key = _rlf_edge_dist)
                for _e in _ranked[1:]:
                    _dropped_ids.add(id(_e))
                _rlf_total_dropped += len(_ranked) - 1
        _kept_edges = [_e for _e in _edge_list if id(_e) not in _dropped_ids]
        _rlf_by_dataset[str(_ds)] = {'edges_before': len(_edge_list), 'edges_after': len(_kept_edges), 'dropped': len(_edge_list) - len(_kept_edges)}

        for _, _n in _nodes.iterrows():
            _rlf_out_rows.append(_n.to_dict())
        for _e in _kept_edges:
            _rlf_out_rows.append({'id': -1, 'dataset': _ds, 'row_type': 'edge', 'node_id': -1, 't': -1, 'z': -1, 'y': -1, 'x': -1, 'source_id': _e['source_id'], 'target_id': _e['target_id']})

    _rlf_frac = _rlf_total_dropped / max(_rlf_total_edges_before, 1)
    print(f"RLF: {_rlf_total_edges_before:,} edges -> {_rlf_total_edges_before - _rlf_total_dropped:,} edges (dropped {_rlf_total_dropped} repeat-lineage division edges, {_rlf_frac:.4%})", flush = True)

    if _rlf_total_dropped == 0:
        _rlf_report.update({'status': 'no_op', 'dropped': 0, 'edges_before': int(_rlf_total_edges_before), 'frac': 0.0})
        print('RLF_NO_OP: no repeat-lineage division edge found; submission.csv unchanged', flush = True)
    elif _rlf_total_dropped > RLF_MAX_EDGE_FRAC * _rlf_total_edges_before:
        print(f"RLF_GUARD_REVERT dropped={_rlf_total_dropped} frac={_rlf_frac:.4%} > {RLF_MAX_EDGE_FRAC:.2%}; submission restored (veto-only kept)", flush = True)
        _rlf_report.update({'status': 'reverted_guard', 'dropped': int(_rlf_total_dropped), 'edges_before': int(_rlf_total_edges_before), 'frac': float(_rlf_frac), 'by_dataset': _rlf_by_dataset})
    else:
        _rlf_final = pd.DataFrame(_rlf_out_rows, columns = CSV_COLUMNS)
        _rlf_final['id'] = range(len(_rlf_final))
        for _col in ('node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id'):
            _rlf_final[_col] = _rlf_final[_col].astype(int)
        assert len(_rlf_final) == len(_rlf_df) - _rlf_total_dropped, 'row count mismatch after RLF'
        _rlf_before_nodes = set(zip(_rlf_df[_rlf_df.row_type.eq('node')].dataset, _rlf_df[_rlf_df.row_type.eq('node')].node_id))
        _rlf_after_nodes = set(zip(_rlf_final[_rlf_final.row_type.eq('node')].dataset, _rlf_final[_rlf_final.row_type.eq('node')].node_id))
        assert _rlf_before_nodes == _rlf_after_nodes, 'RLF must only drop edges, node set changed'
        _rlf_final.to_csv(SUBMISSION_PATH, index = False)
        print(f"RLF: wrote {SUBMISSION_PATH} with {len(_rlf_final):,} rows (was {len(_rlf_df):,})", flush = True)
        _rlf_report.update({'status': 'applied', 'dropped': int(_rlf_total_dropped), 'edges_before': int(_rlf_total_edges_before), 'frac': float(_rlf_frac), 'by_dataset': _rlf_by_dataset})
else:
    _rlf_report['status'] = 'disabled'
RLF_REPORT_PATH.write_text(json.dumps(_rlf_report, indent = 2, sort_keys = True) + '\n')
print('RLF_REPORT:', json.dumps(_rlf_report, sort_keys = True), flush = True)

# ==== [ver9-gate] System-view official eval: ref vs veto2 vs veto2+rlf (8 stems) ===========
# Cổng submit §6 rev-2 (đo system-view official SAU veto+RLF — điều sjlee KHÔNG có):
#   g1: ΔadjEJ(veto2rlf vs ref) >= -0.0005     g2: div_tp(veto2) == div_tp(ref)
#   g3: div_fp(veto2) <= div_fp(ref)            g4: div_fp(veto2rlf) <= div_fp(ref) + 3
#   g5: RLF dropped <= 0.5% cạnh                g6: div_tp(veto2rlf) == div_tp(veto2)
#   ELEVEN: Δproxy(veto2rlf vs ref) >= +0.005 → submit tự tin.
# ref = base validator (cấu hình tight hardcode, KHÔNG veto/RLF) — chính là chất lượng
# submission v3-fast trên cùng hệ đo 8 stems → Δ chính là giá trị gia tăng của ver-9.
VER9_GATE_PATH = WORKING_DIR / 'ver9_gate_report.json'

def ver9_rlf_edges(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, int]]:
    """RLF mức đồ thị (cho replay validator) — cùng logic đã áp lên submission.csv."""
    pos = {int(nid): (float(n['z']), float(n['y']), float(n['x'])) for nid, n in nodes_by_id.items()}
    out_by_source: dict[int, list[dict[str, object]]] = {}
    pred_of: dict[int, int] = {}
    for e in edges:
        s, t = int(e['source_id']), int(e['target_id'])
        out_by_source.setdefault(s, []).append(e)
        pred_of[t] = s
    divider_nodes = {s for s, es in out_by_source.items() if len(es) >= 2}

    def _already_divided(node_id: int) -> bool:
        cur = pred_of.get(node_id)
        while cur is not None:
            if cur in divider_nodes:
                return True
            cur = pred_of.get(cur)
        return False

    def _edge_dist(e: dict) -> float:
        sz, sy, sx = pos[int(e['source_id'])]
        tz, ty, tx = pos[int(e['target_id'])]
        dz = (sz - tz) * VOXEL_SCALE_UM[0]
        dy = (sy - ty) * VOXEL_SCALE_UM[1]
        dx = (sx - tx) * VOXEL_SCALE_UM[2]
        return (dz * dz + dy * dy + dx * dx) ** 0.5

    dropped_ids: set[int] = set()
    for s, es in out_by_source.items():
        if len(es) < 2:
            continue
        if _already_divided(s):
            ranked = sorted(es, key = _edge_dist)
            for e in ranked[1:]:
                dropped_ids.add(id(e))
    kept = [e for e in edges if id(e) not in dropped_ids]
    kept_by_source: dict[int, int] = {}
    for e in kept:
        kept_by_source[int(e['source_id'])] = kept_by_source.get(int(e['source_id']), 0) + 1
    counters = {'edges_before': len(edges), 'edges_after': len(kept), 'dropped': len(edges) - len(kept), 'divisions_before': len(divider_nodes), 'divisions_after': sum((1 for c in kept_by_source.values() if c >= 2))}
    return (kept, counters)

def ver9_score_final(apply_veto: bool, apply_rlf: bool, label: str) -> tuple[dict, list]:
    """Replay 8 stems held-out qua đường final: postprocess (+ HOCT veto) (+ RLF) → official rule.
    HOCT pairs cache theo (stem, node-set hash) → replay thứ 2 tái dùng, không tốn GPU thêm."""
    _real_test_dir = TEST_DIR
    globals()['TEST_DIR'] = TRAIN_DIR
    rows = []
    rlf_dropped = 0
    veto_dropped = 0
    try:
        for stem in val_stems:
            raw_nodes_by_id, raw_edges = VAL_RAW_GRAPHS[stem]
            nodes_copy = _copy.deepcopy(raw_nodes_by_id)
            edges_copy = _copy.deepcopy(raw_edges)
            processed_nodes, processed_edges, _stage_stats = filter_output_graph(nodes_copy, edges_copy, dataset = stem, deepcenter_bundle = globals().get('DEEPCENTER_VETO_DETECTOR'), divnet_bundle = globals().get('DIVNET_RANKER'))
            if apply_veto:
                processed_edges, _vc = _hv_veto_video(stem, processed_nodes, processed_edges)
                veto_dropped += int(_vc.get('removed', 0))
            if apply_rlf:
                processed_edges, _rc = ver9_rlf_edges(processed_nodes, processed_edges)
                rlf_dropped += int(_rc['dropped'])
            gt_nodes_plain, gt_edges_plain, t_true = VAL_GT[stem]
            pred_nodes_plain = nodes_by_id_to_plain(processed_nodes)
            pred_edges_plain = [(int(e['source_id']), int(e['target_id'])) for e in processed_edges]
            row = score_sample(pred_nodes_plain, pred_edges_plain, gt_nodes_plain, gt_edges_plain, t_true)
            row['stem'] = stem
            row['config'] = label
            rows.append(row)
    finally:
        globals()['TEST_DIR'] = _real_test_dir
    summary = aggregate_official(rows)
    summary['n_samples'] = len(rows)
    summary['config'] = label
    summary['veto_edges_dropped'] = veto_dropped
    summary['rlf_edges_dropped'] = rlf_dropped
    return (summary, rows)

VER9_GATE: dict[str, object] = {'enabled': bool(VALIDATOR_ENABLE and val_stems and PP_RESULTS.get('base')), 'experiment': EXPERIMENT_TAG}
if VER9_GATE['enabled']:
    _ref = PP_RESULTS['base']
    _veto2_summary, _veto2_rows = ver9_score_final(True, False, 'veto2')
    _veto2rlf_summary, _veto2rlf_rows = ver9_score_final(True, True, 'veto2rlf')
    _keys = ('adjusted_edge_jaccard', 'division_jaccard', 'proxy_score', 'div_tp', 'div_fp', 'div_fn')
    _deltas = {'adj_ej_veto2_vs_ref': _veto2_summary['adjusted_edge_jaccard'] - _ref['adjusted_edge_jaccard'], 'adj_ej_veto2rlf_vs_ref': _veto2rlf_summary['adjusted_edge_jaccard'] - _ref['adjusted_edge_jaccard'], 'proxy_veto2_vs_ref': _veto2_summary['proxy_score'] - _ref['proxy_score'], 'proxy_veto2rlf_vs_ref': _veto2rlf_summary['proxy_score'] - _ref['proxy_score'], 'div_tp_veto2_vs_ref': _veto2_summary['div_tp'] - _ref['div_tp'], 'div_fp_veto2_vs_ref': _veto2_summary['div_fp'] - _ref['div_fp'], 'div_tp_veto2rlf_vs_ref': _veto2rlf_summary['div_tp'] - _ref['div_tp'], 'div_fp_veto2rlf_vs_ref': _veto2rlf_summary['div_fp'] - _ref['div_fp'], 'div_tp_veto2rlf_vs_veto2': _veto2rlf_summary['div_tp'] - _veto2_summary['div_tp']}
    _rlf_frac_gate = float(_rlf_report.get('frac', 0.0) or 0.0)
    _gates = {'g1_adj_ej_veto2rlf_ge_m0005': _deltas['adj_ej_veto2rlf_vs_ref'] >= -0.0005, 'g2_div_tp_veto2_eq_ref': _deltas['div_tp_veto2_vs_ref'] == 0, 'g3_div_fp_veto2_le_ref': _deltas['div_fp_veto2_vs_ref'] <= 0, 'g4_div_fp_veto2rlf_le_ref_plus3': _deltas['div_fp_veto2rlf_vs_ref'] <= 3, 'g5_rlf_edges_le_half_pct': _rlf_frac_gate <= 0.005, 'g6_div_tp_veto2rlf_eq_veto2': _deltas['div_tp_veto2rlf_vs_veto2'] == 0, 'eleven_delta_proxy_ge_p005': _deltas['proxy_veto2rlf_vs_ref'] >= 0.005}
    _safety = all((_gates[k] for k in ('g1_adj_ej_veto2rlf_ge_m0005', 'g2_div_tp_veto2_eq_ref', 'g3_div_fp_veto2_le_ref', 'g4_div_fp_veto2rlf_le_ref_plus3', 'g5_rlf_edges_le_half_pct', 'g6_div_tp_veto2rlf_eq_veto2')))
    _verdict = 'SUBMIT' if _safety and _gates['eleven_delta_proxy_ge_p005'] else 'SUBMIT_SAFE' if _safety else 'FALLBACK_V3FAST'
    VER9_GATE.update({'ref': {k: _ref.get(k) for k in _keys}, 'veto2': {k: _veto2_summary.get(k) for k in _keys}, 'veto2rlf': {k: _veto2rlf_summary.get(k) for k in _keys}, 'deltas': _deltas, 'rlf_frac': _rlf_frac_gate, 'gates': _gates, 'safety_all_pass': _safety, 'verdict': _verdict, 'hoct_counts': dict(_HV_STATE['counts']), 'hoct_seconds': float(_HV_STATE['hoct_seconds'])})
    VER9_GATE_PATH.write_text(json.dumps(VER9_GATE, indent = 2, sort_keys = True) + '\n')
    print(f"VER9_GATE ref      proxy={_ref['proxy_score']:.6f} adjEJ={_ref['adjusted_edge_jaccard']:.6f} div tp/fp/fn={_ref['div_tp']}/{_ref['div_fp']}/{_ref['div_fn']}", flush = True)
    print(f"VER9_GATE veto2    proxy={_veto2_summary['proxy_score']:.6f} adjEJ={_veto2_summary['adjusted_edge_jaccard']:.6f} div tp/fp/fn={_veto2_summary['div_tp']}/{_veto2_summary['div_fp']}/{_veto2_summary['div_fn']} veto_edges=-{_veto2_summary['veto_edges_dropped']}", flush = True)
    print(f"VER9_GATE veto2rlf proxy={_veto2rlf_summary['proxy_score']:.6f} adjEJ={_veto2rlf_summary['adjusted_edge_jaccard']:.6f} div tp/fp/fn={_veto2rlf_summary['div_tp']}/{_veto2rlf_summary['div_fp']}/{_veto2rlf_summary['div_fn']} rlf_edges=-{_veto2rlf_summary['rlf_edges_dropped']}", flush = True)
    print('VER9_GATE deltas:', json.dumps({k: round(v, 6) for k, v in _deltas.items()}, sort_keys = True), flush = True)
    print('VER9_GATE gates:', json.dumps(_gates, sort_keys = True), flush = True)
    print(f"VER9_GATE_RESULT {_verdict}", flush = True)
else:
    VER9_GATE_PATH.write_text(json.dumps(VER9_GATE, indent = 2, sort_keys = True) + '\n')
    print('VER9_GATE disabled (validator off or base missing)', flush = True)
