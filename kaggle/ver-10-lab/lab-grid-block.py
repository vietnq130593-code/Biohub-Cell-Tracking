# ==== [v10-lab-grid] Grid sweep trên 8 stems validator: tight × veto × RLF ======================
# Thay thế [ver9-hoct-finalize] + [ver9-rlf] + [ver9-gate] của monolith production trong bản LAB:
# bản lab KHÔNG ghi submission.csv (LAB_MODE) nên RLF output-level + gate submit §6 không áp dụng.
# Thay vào đó, mỗi config của LAB_GRID replay riêng từ VAL_RAW_GRAPHS theo pattern ver9_score_final:
#   deepcopy raw graphs từng stem → filter_output_graph (tight_override đè global + per-prefix
#   qua globals MOTION_RELINK_TIGHT_UM / MOTION_RELINK_TIGHT_PER_PREFIX, restore sau) →
#   _hv_veto_video (mode 0/1/2 — đè globals _HV_MODE trước lời gọi, restore sau) →
#   ver9_rlf_edges → score_sample + aggregate_official → per-stem rows.
# ref = config ĐẦU TIÊN của LAB_GRID (mặc định 'ref' = tight hardcode 5.5/6.5, không veto, không RLF).
# Config needs_gpu:true + (LAB_SKIP_VETO hoặc không có cuda) → bỏ qua + ghi skip_reason.
# Kết quả: v10_lab_rows.csv (per-stem per-config) + v10_lab_report.json (summary + deltas vs ref).
V10_LAB_ROWS_PATH = globals().get('V10_LAB_ROWS_PATH') or (WORKING_DIR / 'v10_lab_rows.csv')   # tôn trọng path đã inject (test/harness), mặc định WORKING_DIR
V10_LAB_REPORT_PATH = globals().get('V10_LAB_REPORT_PATH') or (WORKING_DIR / 'v10_lab_report.json')

def ver9_rlf_edges(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, int]]:
    """RLF mức đồ thị (cho replay validator) — port nguyên văn từ block [ver9-rlf] của ver-9."""
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

def v10_score_config(tight_override = None, veto_mode: int = 0, apply_rlf: bool = False, label: str = 'cfg') -> tuple[dict, list]:
    """Replay 8 stems held-out theo 1 config (pattern ver9_score_final của [ver9-gate]).

    tight_override: đè global — đặt cả MOTION_RELINK_TIGHT_UM lẫn mọi giá trị per-prefix trong
    MOTION_RELINK_TIGHT_PER_PREFIX bằng cùng giá trị (global override), restore sau config.
    veto_mode: 0/1/2 — đè globals _HV_MODE trước lời gọi _hv_veto_video (mode đọc từ biến module
    lúc gọi, không phải env), restore sau. HOCT pairs cache theo (stem, node-set hash) trong
    _HV_STATE nên veto1/veto2/veto2rlf cùng node set sẽ tái dùng kết quả HOCT, không tốn GPU thêm.
    """
    rows = []
    veto_dropped = 0
    rlf_dropped = 0
    _real_test_dir = TEST_DIR
    _saved_tight_um = globals()['MOTION_RELINK_TIGHT_UM']
    _saved_tight_pp = globals()['MOTION_RELINK_TIGHT_PER_PREFIX']
    _saved_hv_mode = globals()['_HV_MODE']
    globals()['TEST_DIR'] = TRAIN_DIR
    try:
        if tight_override is not None:
            _ov = float(tight_override)
            globals()['MOTION_RELINK_TIGHT_UM'] = _ov
            globals()['MOTION_RELINK_TIGHT_PER_PREFIX'] = {str(k): _ov for k in _saved_tight_pp}
        globals()['_HV_MODE'] = int(veto_mode)
        for stem in val_stems:
            raw_nodes_by_id, raw_edges = VAL_RAW_GRAPHS[stem]
            nodes_copy = _copy.deepcopy(raw_nodes_by_id)
            edges_copy = _copy.deepcopy(raw_edges)
            processed_nodes, processed_edges, _stage_stats = filter_output_graph(nodes_copy, edges_copy, dataset = stem, deepcenter_bundle = globals().get('DEEPCENTER_VETO_DETECTOR'), divnet_bundle = globals().get('DIVNET_RANKER'))
            if veto_mode > 0:
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
            row['safe_divisions_added'] = _stage_stats.get('safe_divisions_added', 0)
            row['veto_mode'] = int(veto_mode)
            row['tight_override'] = None if tight_override is None else float(tight_override)
            row['apply_rlf'] = bool(apply_rlf)
            rows.append(row)
    finally:
        globals()['TEST_DIR'] = _real_test_dir
        globals()['MOTION_RELINK_TIGHT_UM'] = _saved_tight_um
        globals()['MOTION_RELINK_TIGHT_PER_PREFIX'] = _saved_tight_pp
        globals()['_HV_MODE'] = _saved_hv_mode
    summary = aggregate_official(rows)
    summary['n_samples'] = len(rows)
    summary['config'] = label
    summary['veto_edges_dropped'] = veto_dropped
    summary['rlf_edges_dropped'] = rlf_dropped
    return (summary, rows)

_v10_have_cuda = False
try:
    _v10_have_cuda = bool(torch.cuda.is_available())
except Exception:
    _v10_have_cuda = False

_v10_grid_rows: list[dict[str, object]] = []
_v10_grid_configs: dict[str, dict] = {}
_v10_grid_ref_label: str | None = None
_v10_grid_ref_summary: dict | None = None
_v10_grid_t0 = time.time()
_v10_keys = ('adjusted_edge_jaccard', 'division_jaccard', 'proxy_score', 'div_tp', 'div_fp', 'div_fn')
print(f"[v10-lab] GRID START: {len(LAB_GRID)} configs x {len(val_stems)} stems (cuda={_v10_have_cuda}, skip_veto={LAB_SKIP_VETO}, cache={_V10_LAB_CACHE_LOADED})", flush = True)

for _v10_cfg in LAB_GRID:
    if not isinstance(_v10_cfg, dict) or 'label' not in _v10_cfg:
        print(f"[v10-lab] SKIP config không hợp lệ (thiếu label): {json.dumps(_v10_cfg, sort_keys = True)}")
        continue
    _v10_label = str(_v10_cfg['label'])
    _v10_needs_gpu = bool(_v10_cfg.get('needs_gpu', False))
    _v10_veto_mode = int(_v10_cfg.get('veto_mode', 0) or 0)
    _v10_apply_rlf = bool(_v10_cfg.get('apply_rlf', False))
    _v10_tight = _v10_cfg.get('tight_override', None)
    _v10_skip_reason = None
    if _v10_needs_gpu and LAB_SKIP_VETO:
        _v10_skip_reason = 'LAB_SKIP_VETO=1'
    elif _v10_needs_gpu and not _v10_have_cuda:
        _v10_skip_reason = 'no cuda (needs_gpu)'
    if _v10_skip_reason is not None:
        _v10_grid_configs[_v10_label] = {'label': _v10_label, 'config': _v10_cfg, 'skipped': True, 'skip_reason': _v10_skip_reason}
        print(f"[v10-lab] SKIP {_v10_label}: {_v10_skip_reason}")
        continue
    _v10_cfg_t0 = time.time()
    _v10_summary, _v10_rows = v10_score_config(tight_override = _v10_tight, veto_mode = _v10_veto_mode, apply_rlf = _v10_apply_rlf, label = _v10_label)
    _v10_dt = time.time() - _v10_cfg_t0
    _v10_summary['seconds'] = _v10_dt
    _v10_grid_rows.extend(_v10_rows)
    if _v10_grid_ref_summary is None:
        _v10_grid_ref_label = _v10_label
        _v10_grid_ref_summary = _v10_summary
    if _v10_label == _v10_grid_ref_label:
        _v10_deltas: dict[str, float] = {}
    else:
        _v10_deltas = {k: float(_v10_summary[k] - _v10_grid_ref_summary[k]) for k in _v10_keys}
    _v10_grid_configs[_v10_label] = {'label': _v10_label, 'config': _v10_cfg, 'skipped': False, 'summary': dict(_v10_summary), 'deltas_vs_ref': _v10_deltas, 'ref_label': _v10_grid_ref_label, 'veto_edges_dropped': int(_v10_summary.get('veto_edges_dropped', 0)), 'rlf_edges_dropped': int(_v10_summary.get('rlf_edges_dropped', 0)), 'seconds': _v10_dt}
    print(f"[v10-lab] {_v10_label:<10s} adjEJ={_v10_summary['adjusted_edge_jaccard']:.6f} d_adjEJ={_v10_deltas.get('adjusted_edge_jaccard', 0.0):+.6f} proxy={_v10_summary['proxy_score']:.6f} div={_v10_summary['div_tp']}/{_v10_summary['div_fp']}/{_v10_summary['div_fn']} veto_drop={_v10_summary['veto_edges_dropped']} rlf_drop={_v10_summary['rlf_edges_dropped']} ({_v10_dt:.0f}s)", flush = True)

if _v10_grid_rows:
    _v10_fieldnames = sorted({k for _v10_row in _v10_grid_rows for k in _v10_row.keys()})
    with V10_LAB_ROWS_PATH.open('w', newline = '') as _v10_f:
        _v10_writer = csv.DictWriter(_v10_f, fieldnames = _v10_fieldnames)
        _v10_writer.writeheader()

        for _v10_row in _v10_grid_rows:
            _v10_writer.writerow(_v10_row)
    print(f"[v10-lab] wrote {V10_LAB_ROWS_PATH} ({len(_v10_grid_rows)} per-stem rows)")

_v10_lab_report: dict[str, object] = {'experiment_tag': EXPERIMENT_TAG, 'lab_env': {'LAB_MODE': LAB_MODE, 'LAB_NO_CUDA': LAB_NO_CUDA, 'LAB_SKIP_VETO': LAB_SKIP_VETO, 'LAB_VAL_CACHE_DIR': LAB_VAL_CACHE_DIR, 'LAB_FORCE_DUMP': LAB_FORCE_DUMP, 'LAB_DUMP_DIR': str(LAB_DUMP_DIR), 'BIOHUB_V10_GRID': LAB_GRID}, 'meta': {'stems': list(val_stems), 'n_stems': len(val_stems), 'cache_loaded': _V10_LAB_CACHE_LOADED, 'dump_dir': str(LAB_DUMP_DIR), 'cuda': _v10_have_cuda, 'ref_label': _v10_grid_ref_label, 'validator_base_summary': PP_RESULTS.get('base'), 'valid_validator_base': bool(PP_RESULTS.get('base')), 'validator_results_csv': str(VALIDATOR_STATS_PATH), 'finished_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'predict_val_seconds': predict_val_seconds}, 'configs': _v10_grid_configs, 'runtime_s': time.time() - _v10_grid_t0}
V10_LAB_REPORT_PATH.write_text(json.dumps(_resume_json_safe(_v10_lab_report), indent = 2, sort_keys = True) + '\n')
print(f"[v10-lab] wrote {V10_LAB_REPORT_PATH}")

print()
print('[v10-lab] ================ BẢNG SO SÁNH GRID (8 stems validator, official rule) ================')
print(f"[v10-lab] {'label':<10s} | {'adjEJ':>9s} | {'d_adjEJ':>10s} | {'proxy':>9s} | {'div tp/fp/fn':>13s} | {'edges dropped':>14s}")
for _v10_label, _v10_entry in _v10_grid_configs.items():
    if _v10_entry.get('skipped'):
        print(f"[v10-lab] {_v10_label:<10s} | {'SKIP':>9s} | {'--':>10s} | {'--':>9s} | {'--':>13s} | {_v10_entry.get('skip_reason')}")
        continue
    _v10_s = _v10_entry['summary']
    print(f"[v10-lab] {_v10_label:<10s} | {_v10_s['adjusted_edge_jaccard']:9.6f} | {_v10_entry['deltas_vs_ref'].get('adjusted_edge_jaccard', 0.0):+10.6f} | {_v10_s['proxy_score']:9.6f} | {str(_v10_s['div_tp']) + '/' + str(_v10_s['div_fp']) + '/' + str(_v10_s['div_fn']):>13s} | veto-{_v10_entry['veto_edges_dropped']}/rlf-{_v10_entry['rlf_edges_dropped']}")
print('[v10-lab] =============================================================================')
print(f'[v10-lab] LAB PIPELINE COMPLETE — rows: {V10_LAB_ROWS_PATH} · report: {V10_LAB_REPORT_PATH} · cache: {LAB_DUMP_DIR}')
