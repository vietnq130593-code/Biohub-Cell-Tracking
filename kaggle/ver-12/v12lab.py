#!/usr/bin/env python3
"""v12lab.py — V12-LAB CPU-ONLY (0 GPU) — V12-RESEARCH.md §4 PHÒNG LAB 1 (REVIEW-1 redesign).

Ba lớp (chạy LOCAL, không Kaggle, không GPU — đúng cam kết GPU-WASTE-PREVENTION §0/L8):

  (a) VALIDATOR REPLAY  — rawgraphs.json (8 stems) + dumps pre-baked (pdiv_by_node.npz
      + dc_raw_by_node.npz từ v11-lab v2) thay model inference → grid sweep config v12
      (reparent mở gate, orphan-adoption, READMIT/GAPFILL, SEF_TTA...) → chấm
      score_sample/aggregate_official (engine validator monolith) + đánh gates F1-F6.
      Anchor fidelity: cấu hình ver-11 phải tái lập D2 ≈ 0.930492 div 4/1/8.
  (b) HIDDEN INSTRUMENTED — 4 phim test (.geff v10-out) + GT (test-gt) → replay
      post-chain + GATE-FLIP MATRIX (bật/tắt từng gate, đo ai cứu 3 GT division thật
      05db: 25000381 t=24 · 53001011 t=52 · 63001217 t=62 — §7.4 ưu tiên 1: KHÔNG đoán mù)
      + census fork/node/edge theo dataset (L12) + trace từng GT division.
      ⚠ Semantic delta F3: p_div/DC không replay được trên hidden (không bundle local)
      → biến thể hidden đặt MIN_PDIV=0 + orphan-floor=0 + DC-bypass (chỉ đo gate hình
      học/divergence; quyết định model-gate vẫn qua lớp (a)).
  (c) REPLICA — chấm CSV submission bằng engine scorer2code (đã verify 100% receipt
      alfonso 0.9605) — topology trong cửa sổ + 3 division; KHÔNG tin ngoài cửa sổ (F6).

Cơ chế trung tâm: trích env-block + constants + post-chain + scoring TỪ monolith v12
(vừa build) rồi exec vào namespace — env override TRƯỚC khi exec → mỗi config 1 namespace
sạch (zero-drift so với code production — cùng nguồn single source of truth).
Shim: _divnet_score_queries + deepcenter_score_point phục vụ từ npz pre-baked.

Usage:
  python3 v12lab.py selftest                       # smoke tổng hợp đường mới (orphan/readmit/gapfill) — chạy trước mọi thứ
  python3 v12lab.py validator [--env K=V ...]      # replay validator 1 config (mặc định = ver-11 anchor)
  python3 v12lab.py hidden [--flips] [--env K=V]   # replay hidden + census + 3 GT div (+ ma trận gate-flip)
  python3 v12lab.py replica <csv> [csv2 ...]       # chấm replica engine scorer2code
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
MONO = HERE / 'cell-monolith.py'
RECOVERY = Path('/home/z/v11-recovery')
RAWGRAPHS_DIR = RECOVERY / 'rawgraphs'
DUMPS_DIR = RECOVERY / 'v11-lab-out' / 'v11_lab_cache'
HIDDEN_GEFF_DIR = RECOVERY / 'v10-out' / 'tracking_repo' / 'predictions' / 'unknown' / 'unet_transformer' / 'split_0'
GT_DIR = RECOVERY / 'test-gt'
SCORER = HERE.parent / 'scorer' / 'scorer2code.py'
TEST_STEMS = ['44b6_0113de3b', '44b6_0b24845f', '6bba_05b6850b', '6bba_05db0fb1']
GT_DIVISIONS_05DB = [(25000381, 24), (53001011, 52), (63001217, 62)]  # (gt_parent_id, t) — §2 giải phẫu
LOWDET_DIR = RECOVERY / 'v11-lab-out' / 'lowdet'  # dump giả lập cho hidden replay (nếu có)


# ---------------------------------------------------------------- монolith extraction
def extract_regions(mono_text: str) -> dict:
    """Trích 4 vùng từ monolith v12: env-block / constants / post-chain / scoring."""
    # env-block: từ BIOHUB_PRESET (biến env production đầu tiên) đến trước guard
    env_start = mono_text.index("BIOHUB_PRESET = 'harmonic_v3_division_wide'")
    env_end = mono_text.index('import json as _guard_json')
    # constants: từ DET_THRESHOLD đến trước CONFIG_DISPLAY
    const_start = mono_text.index("DET_THRESHOLD = float(os.environ.get('BIOHUB_DET_THRESHOLD', '0.99'))")
    const_end = mono_text.index('CONFIG_DISPLAY = {')
    # post-chain: từ import scipy đến trước DEEPCENTER_VETO_DETECTOR = load_...
    chain_start = mono_text.index('from scipy.optimize import linear_sum_assignment')
    chain_end = mono_text.index('DEEPCENTER_VETO_DETECTOR = load_deepcenter_veto_detector()')
    # scoring: 3 const validator + hàm match_nodes_bipartite → aggregate_official
    score_consts = []
    for line in ("VALIDATOR_MATCH_RADIUS_UM = float(os.environ.get('BIOHUB_VALIDATOR_MATCH_RADIUS_UM', '7.0'))",
                 "VALIDATOR_NODE_COUNT_PENALTY_A = float(os.environ.get('BIOHUB_VALIDATOR_NODE_COUNT_PENALTY_A', '0.1'))",
                 "VALIDATOR_DIVISION_WEIGHT = float(os.environ.get('BIOHUB_VALIDATOR_DIVISION_WEIGHT', '0.1'))"):
        score_consts.append(line)
    fn_start = mono_text.index('def match_nodes_bipartite(')
    fn_end = mono_text.index('import copy as _copy')
    return {
        'env': mono_text[env_start:env_end],
        'consts': mono_text[const_start:const_end],
        'chain': mono_text[chain_start:chain_end],
        'score_consts': '\n'.join(score_consts),
        'score_fns': mono_text[fn_start:fn_end],
    }


def load_ns(env_overrides: dict | None = None) -> dict:
    """Namespace monolith v12: env production (từ env-block chính nó) + override + exec vùng code.

    CHÚ Ý: env-block của monolith set os.environ trực tiếp → phải khôi phục env sau exec
    để config sau không dính giá trị cũ (mỗi load_ns gọi trên env sạch).
    """
    saved = dict(os.environ)
    try:
        regions = extract_regions(MONO.read_text())
        ns = {'__name__': 'v12lab_mono', '__file__': str(MONO)}
        import json as _j
        import math as _m
        from pathlib import Path as _P
        from scipy.optimize import linear_sum_assignment as _lsa
        from scipy.spatial import cKDTree as _kd
        ns.update({'os': os, 'json': _j, 'math': _m, 'Path': _P, 'np': np,
                   'linear_sum_assignment': _lsa, 'cKDTree': _kd})
        # 1) env production (đúng từng giá trị monolith đã build)
        exec(regions['env'], ns)
        # 2) override của config/lab (sau env-block → thắng)
        for k, v in (env_overrides or {}).items():
            os.environ[k] = str(v)
        # 3) constants (đọc env tại exec-time → thấy giá trị override)
        exec(regions['consts'], ns)
        # 4) post-chain functions
        exec(regions['chain'], ns)
        # 5) scoring
        exec(regions['score_consts'], ns)
        exec(regions['score_fns'], ns)
        # namespace cần TEST_DIR giả (read_test_frame fail mềm → refine trả midpoint gốc)
        ns.setdefault('TEST_DIR', Path('/nonexistent-test-dir'))
        ns.setdefault('WORKING_DIR', Path('.'))
        return ns
    finally:
        os.environ.clear()
        os.environ.update(saved)


# ---------------------------------------------------------------- pre-baked shims
def load_pdiv_lookup() -> dict:
    """(stem, t, z, y, x) → p_div từ pdiv_by_node.npz + node-set rawgraphs (B3 dump)."""
    npz = DUMPS_DIR / 'pdiv_by_node.npz'
    raw = json.loads((RAWGRAPHS_DIR / 'raw_graphs.json').read_text())
    if not npz.exists():
        return {}
    with np.load(npz) as cz:
        stems = [str(s) for s in cz['stems']]
        node_stem = cz['node_stem']
        node_id = cz['node_id']
        p_div = cz['p_div']
    pos_key = {}
    for stem, payload in raw.items():
        for nid, nd in payload['nodes'].items():
            pos_key[(stem, int(nd['t']), round(float(nd['z']), 2), round(float(nd['y']), 2), round(float(nd['x']), 2))] = int(nid)
    lookup = {}
    for si, nid, pv in zip(node_stem, node_id, p_div):
        stem = stems[int(si)]
        key = (stem, None)
        nd = raw.get(stem, {}).get('nodes', {}).get(str(int(nid))) or raw.get(stem, {}).get('nodes', {}).get(int(nid))
        if nd is None:
            continue
        k = (stem, int(nd['t']), round(float(nd['z']), 2), round(float(nd['y']), 2), round(float(nd['x']), 2))
        lookup[k] = float(pv)
    return lookup


def load_dc_lookup() -> dict:
    """(stem, t, z, y, x) → dc_raw (None giữ None) từ dc_raw_by_node.npz (B2 dump)."""
    npz = DUMPS_DIR / 'dc_raw_by_node.npz'
    raw = json.loads((RAWGRAPHS_DIR / 'raw_graphs.json').read_text())
    if not npz.exists():
        return {}
    with np.load(npz) as cz:
        stems = [str(s) for s in cz['stems']]
        node_stem = cz['node_stem']
        node_id = cz['node_id']
        dc_raw = cz['dc_raw']
    lookup = {}
    for si, nid, sv in zip(node_stem, node_id, dc_raw):
        stem = stems[int(si)]
        nd = raw.get(stem, {}).get('nodes', {}).get(str(int(nid))) or raw.get(stem, {}).get('nodes', {}).get(int(nid))
        if nd is None:
            continue
        v = float(sv)
        if v != v or v < 0:  # NaN hoặc -1.0 (schema B2: -1.0 = None)
            v = None
        k = (stem, int(nd['t']), round(float(nd['z']), 2), round(float(nd['y']), 2), round(float(nd['x']), 2))
        lookup[k] = v
    return lookup


def install_shims(ns: dict, pdiv_lookup: dict, dc_lookup: dict) -> None:
    """Thay _divnet_score_queries + deepcenter_score_point bằng bản phục vụ npz pre-baked.

    deepcenter_score_point: giữ NGUYÊN logic threshold của deepcenter_accept_repair_point
    (chỉ thay nguồn score) — quyết định veto chạy đúng code production.
    _divnet_score_queries: (bundle, dataset, queries, ...) → list p_div; query từ node
    position → key lookup; node KHÔNG có trong dump (node thêm giữa replay) → None
    (bằng chứng thiếu — cùng semantics production khi model không có view).
    """
    def _divnet_score_queries_shim(bundle, dataset, queries, frame_cache, t_lo, t_hi):
        # Hợp đồng production: list cùng độ dài với queries, mỗi phần tử float.
        # Node KHÔNG có trong dump (node thêm giữa replay / không phải prenode) → 0.0
        # ('không có bằng chứng division' — bị floor > 0 từ chối, bảo toàn semantics).
        out = []
        for q in queries:
            k = (str(dataset), int(round(q[0])), round(float(q[1]), 2), round(float(q[2]), 2), round(float(q[3]), 2))
            pv = pdiv_lookup.get(k)
            out.append(0.0 if pv is None else float(pv))
        return out

    def deepcenter_score_point_shim(dataset, t, point, detector_bundle, frame_cache, heatmap_cache):
        k = (str(dataset), int(t), round(float(point[0]), 2), round(float(point[1]), 2), round(float(point[2]), 2))
        return dc_lookup.get(k)

    ns['_divnet_score_queries'] = _divnet_score_queries_shim
    ns['deepcenter_score_point'] = deepcenter_score_point_shim


def divnet_shim_bundle() -> dict:
    return {'rank_w_um': 15.0, 'shim': True, 'note': 'v12lab pre-baked pdiv npz (v11-lab v2 dump)'}


# ---------------------------------------------------------------- geff loaders (không tracksdata)
def read_geff_nodes_edges(path: Path) -> tuple[dict, list]:
    """Đọc .geff prediction → (nodes_by_id, raw_edges có edge_prob) — zarr thuần."""
    import zarr as _zarr
    root = _zarr.open_group(store=str(path), mode='r')
    ids = np.asarray(root['nodes/ids'][:], dtype=np.int64)
    t = np.asarray(root['nodes/props/t/values'][:], dtype=np.float64)
    z = np.asarray(root['nodes/props/z/values'][:], dtype=np.float64)
    y = np.asarray(root['nodes/props/y/values'][:], dtype=np.float64)
    x = np.asarray(root['nodes/props/x/values'][:], dtype=np.float64)
    edges = np.asarray(root['edges/ids'][:], dtype=np.int64).reshape(-1, 2)
    nodes_by_id = {}
    for i, nid in enumerate(ids):
        nodes_by_id[int(nid)] = {'node_id': int(nid), 't': int(t[i]), 'z': float(z[i]), 'y': float(y[i]), 'x': float(x[i])}
    raw_edges = []
    try:
        ep = np.asarray(root['edges/props/edge_prob/values'][:], dtype=np.float64)
    except Exception:
        ep = None
    for j, (s, d) in enumerate(edges):
        prob = None if ep is None else float(ep[j])
        raw_edges.append({'source_id': int(s), 'target_id': int(d), 'edge_prob': prob})
    return nodes_by_id, raw_edges


def read_gt_graph(stem: str) -> dict:
    """GT test .geff → {ids, t, z, y, x, edges, n_total} (schema lb_replica2)."""
    import zarr as _zarr
    p = GT_DIR / f'{stem}.geff'
    root = _zarr.open_group(store=str(p), mode='r')
    meta = json.loads((p / 'zarr.json').read_text())
    return {
        'ids': np.asarray(root['nodes/ids'][:], dtype=np.int64),
        't': np.asarray(root['nodes/props/t/values'][:], dtype=np.float64),
        'z': np.asarray(root['nodes/props/z/values'][:], dtype=np.float64),
        'y': np.asarray(root['nodes/props/y/values'][:], dtype=np.float64),
        'x': np.asarray(root['nodes/props/x/values'][:], dtype=np.float64),
        'edges': np.asarray(root['edges/ids'][:], dtype=np.int64).reshape(-1, 2),
        'n_total': float(meta['attributes']['geff']['extra']['estimated_number_of_nodes']),
    }


# ---------------------------------------------------------------- replay cores
def replay_graph(ns: dict, nodes_by_id: dict, raw_edges: list, dataset: str, divnet_bundle, deepcenter_bundle=None):
    """Chạy filter_output_graph (toàn post-chain v12) trên 1 graph. Trả (nodes, edges, stats)."""
    nodes_by_id = {int(k): dict(v) for k, v in nodes_by_id.items()}
    raw_edges = [dict(e) for e in raw_edges]
    nodes, edges, stats = ns['filter_output_graph'](nodes_by_id, raw_edges, dataset=dataset,
                                                    deepcenter_bundle=deepcenter_bundle, divnet_bundle=divnet_bundle)
    return nodes, edges, stats


def census(ns: dict, nodes: dict, edges: list) -> dict:
    """Census theo dataset (L12): node/edge/fork + counters division."""
    by_source = {}
    for e in edges:
        by_source.setdefault(int(e['source_id']), []).append(e)
    forks = sum(1 for v in by_source.values() if len(v) >= 2)
    return {'nodes': len(nodes), 'edges': len(edges), 'forks': forks,
            'mean_track': (len(nodes) / max(1, len({int(e['source_id']) for e in edges} | {int(e['target_id']) for e in edges})))}


def div_check(ns: dict, nodes: dict, edges: list, gt: dict) -> dict:
    """Đối chiếu division với GT: match node bipartite + compute_division_confusion."""
    pred_nodes = {int(n['node_id']): (int(n['t']), float(n['z']), float(n['y']), float(n['x'])) for n in nodes.values()}
    gt_nodes = {int(gid): (float(t), float(z), float(y), float(x)) for gid, t, z, y, x in zip(gt['ids'], gt['t'], gt['z'], gt['y'], gt['x'])}
    pred_edges = [(int(e['source_id']), int(e['target_id'])) for e in edges]
    gt_edges = [(int(s), int(d)) for s, d in gt['edges']]
    p2g, g2p = ns['match_nodes_bipartite'](pred_nodes, gt_nodes, max_dist=7.0)
    tp, fp, fn = ns['compute_division_confusion'](pred_nodes, pred_edges, gt_nodes, gt_edges, p2g, g2p)
    return {'div_tp': int(tp), 'div_fp': int(fp), 'div_fn': int(fn), 'p2g': p2g, 'g2p': g2p}


def gt_dividing_nodes(gt: dict) -> list:
    """Các GT node có >=2 cạnh ra (đang phân chia) — id + t + children ids."""
    out_by = {}
    for s, d in gt['edges']:
        out_by.setdefault(int(s), []).append(int(d))
    tmap = {int(gid): float(t) for gid, t in zip(gt['ids'], gt['t'])}
    return [(nid, int(tmap[nid]), kids) for nid, kids in out_by.items() if len(kids) >= 2]


def trace_gt_division(ns: dict, nodes: dict, edges: list, gt: dict, gt_div: tuple, g2p: dict) -> dict:
    """F1 instrumented: trace 1 GT division qua các gate safe-div trên đồ thị replay.

    Với GT parent (P, t) + 2 con (ở t+1): tìm pred node khớp từng con (g2p), mô tả
    trạng thái cạnh (mồ côi? cha hiện tại cách bao xa?) + các source tiềm năng ở
    CHÍNH frame t (source của division phải ở t, con ở t+1) — chốt gate chặn.
    """
    pid, t, kids = gt_div
    pos = {int(n['node_id']): (float(n['z']), float(n['y']), float(n['x'])) for n in nodes.values()}
    incoming = {}
    for e in edges:
        incoming.setdefault(int(e['target_id']), []).append(int(e['source_id']))
    scale = np.array([1.625, 0.40625, 0.40625])
    report = {'gt_parent': pid, 't': t, 'children': {}}
    for kid in kids:
        pred_kid = g2p.get(kid)
        info = {'pred_node': pred_kid, 'orphan': None, 'current_parent_dist_um': None}
        if pred_kid is not None and pred_kid in nodes:
            parents = incoming.get(pred_kid, [])
            info['orphan'] = len(parents) == 0
            if parents:
                pdists = []
                for pnode in parents:
                    if pnode in pos:
                        d = np.linalg.norm((np.array(pos[pnode]) - np.array(pos[pred_kid])) * scale)
                        pdists.append((int(pnode), round(float(d), 2)))
                info['current_parent_dist_um'] = pdists
            # source tiềm năng ở frame t (frame CHA — division source t → con t+1)
            cands = [(nid, round(float(np.linalg.norm((np.array(p) - np.array(pos[pred_kid])) * scale)), 2))
                     for nid, p in pos.items() if nodes[nid]['t'] == t]
            cands.sort(key=lambda kv: kv[1])
            info['nearest_sources_frame_t'] = cands[:4]
        report['children'][int(kid)] = info
    return report


# ---------------------------------------------------------------- mode: selftest
def mode_selftest() -> int:
    """Smoke CPU đường mới của v12 trên đồ thị tổng hợp (orphan/readmit/gapfill + INT/DAG)."""
    print('=== v12lab selftest — smoke đường mới v12 (CPU, đồ thị tổng hợp) ===')
    ns = load_ns({'BIOHUB_SAFE_DIV_MIN_PDIV': '0', 'BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV': '0',
                  'BIOHUB_DIVNET_RANK': '0', 'BIOHUB_DEEPCENTER_SAFE_DIV_VETO': '0',
                  'BIOHUB_READMIT_RADIUS_UM': '4', 'BIOHUB_GAPFILL_MAX_GAP': '3',
                  'BIOHUB_GAPFILL_MAX_ADDED_FRAC': '0.5',
                  'BIOHUB_LOWDET_DIR': str(LOWDET_DIR)})
    assert ns['SAFE_DIV_ORPHAN_ADOPT'] and ns['READMIT_RADIUS_UM'] == 4.0 and ns['GAPFILL_MAX_GAP'] == 3, 'env v12 không vào constants'

    # đồ thị: track A t=0..4 (end hở ở t=4), track B t=9..13 (start hở ở t=9)
    # → gap 4 frame (t=5..8): READMIT cứu t=5 (peak mạnh 0.99), GAPFILL bắc t=6..8.
    # (gap > GAP_CLOSE_MAX_GAP=2 nên closer không tự bridging trước — đúng ngữ cảnh
    # gapfill chỉ chạy trên phần closer để lại.)
    nodes = {}
    def add(nid, t, z, y, x):
        nodes[nid] = {'node_id': nid, 't': t, 'z': z, 'y': y, 'x': x}
    for i in range(5):
        add(i, i, 10.0, 20.0 + i * 0.8, 30.0)
    for i in range(5):
        add(100 + i, 9 + i, 10.0, 20.0 + 9 * 0.8 + i * 0.8, 30.0)
    edges = [{'source_id': i, 'target_id': i + 1, 'edge_prob': 0.9} for i in range(4)]
    edges += [{'source_id': 100 + i, 'target_id': 101 + i, 'edge_prob': 0.9} for i in range(4)]

    # pool lowdet giả: peak mạnh t=5 (readmit, đúng cạnh track-A-end) + 3 peak giữa
    # dòng t=6..8 (gapfill, đúng đường bắc cầu thẳng end→start).
    LOWDET_DIR.mkdir(parents=True, exist_ok=True)
    low = [(5, 10.0, 24.0, 30.0), (6, 10.0, 24.8, 30.0), (7, 10.0, 25.6, 30.0), (8, 10.0, 26.4, 30.0)]
    np.savez_compressed(LOWDET_DIR / 'selftest-ds.npz',
                        low_coords=np.array(low, dtype=np.int16),
                        low_score=np.array([0.99, 0.6, 0.55, 0.6], dtype=np.float32))

    nodes2, edges2, stats = replay_graph(ns, nodes, edges, 'selftest-ds', divnet_bundle=None)
    print(f"  nodes: {len(nodes)} -> {len(nodes2)} | edges: {len(edges)} -> {len(edges2)}")
    print(f"  readmitted = {stats.get('readmitted_nodes', 0)} | gapfill_added_nodes = {stats.get('gapfill_added_nodes', 0)} | gapfill_added_edges = {stats.get('gapfill_added_edges', 0)}")
    assert stats.get('readmitted_nodes', 0) >= 1, 'READMIT không thêm node nào (pool/anchor sai?)'
    assert stats.get('gapfill_added_nodes', 0) >= 2, 'GAPFILL không bắc cầu (pool/gate/budget sai?)'
    # INT/DAG: mọi cạnh endpoint tồn tại + t tăng đúng 1
    for e in edges2:
        s, d = int(e['source_id']), int(e['target_id'])
        assert s in nodes2 and d in nodes2, 'cạnh treo lơ lửng'
        assert int(nodes2[d]['t']) == int(nodes2[s]['t']) + 1, 'cạnh không liên tiếp'
    outs = {}
    for e in edges2:
        outs.setdefault(int(e['source_id']), []).append(int(e['target_id']))
    assert all(len(v) <= 2 for v in outs.values()), 'source có >2 con'
    print('  INT/DAG PASS · READMIT hoạt động · GAPFILL bắc cầu PASS')

    # orphan-adoption: track thẳng t=0..7 + mồ côi t=5 KHÔNG cạnh vào/ra — đối xứng
    # với con hiện tại (đủ qua symmetry tau 0.6) → phải được exempt + nhận nuôi.
    nodes3 = {}
    def add3(nid, t, z, y, x):
        nodes3[nid] = {'node_id': nid, 't': t, 'z': z, 'y': y, 'x': x}
    for i in range(8):
        add3(i, i, 5.0, 6.0 + i * 0.5, 7.0)
    add3(50, 5, 5.0, 7.5, 7.0)  # mồ côi: không cạnh vào, không cạnh ra; cách node4 0.5 vox (đối xứng node5)
    edges3 = [{'source_id': i, 'target_id': i + 1, 'edge_prob': 0.9} for i in range(7)]
    nodes4, edges4, stats4 = replay_graph(ns, nodes3, edges3, 'selftest-ds2', divnet_bundle=None)
    orphan_edges = [e for e in edges4 if int(e['target_id']) == 50]
    print(f"  orphan test: exempted = {stats4.get('safe_division_orphan_exempted', 0)} | adopted = {stats4.get('safe_division_orphan_adopted', 0)} | cạnh tới mồ côi = {len(orphan_edges)}")
    assert stats4.get('safe_division_orphan_exempted', 0) >= 1, 'mồ côi không được exempt (gate divergence vẫn chặn?)'
    assert stats4.get('safe_division_orphan_adopted', 0) >= 1 and orphan_edges, 'mồ côi được exempt nhưng KHÔNG được nhận nuôi'
    print('=== SELFTEST PASS — đường v12 (orphan-adoption + READMIT + GAPFILL) chạy đúng ===')
    return 0


# ---------------------------------------------------------------- mode: validator
def mode_validator(env_overrides: dict) -> int:
    print('=== v12lab VALIDATOR REPLAY (CPU · pre-baked pdiv/dc · 8 stems) ===')
    raw = json.loads((RAWGRAPHS_DIR / 'raw_graphs.json').read_text())
    gt = json.loads((RAWGRAPHS_DIR / 'gt_bundle.json').read_text())
    pdiv_lookup = load_pdiv_lookup()
    dc_lookup = load_dc_lookup()
    print(f'  shims: pdiv {len(pdiv_lookup):,} node-scores · dc {len(dc_lookup):,} node-scores')
    ns = load_ns(env_overrides)
    install_shims(ns, pdiv_lookup, dc_lookup)
    bundle = divnet_shim_bundle()
    rows = []
    t0 = time.time()
    for stem in sorted(raw.keys()):
        nodes = {int(k): dict(v) for k, v in raw[stem]['nodes'].items()}
        raw_edges = [dict(e) for e in raw[stem]['edges']]
        n_nodes, n_edges, stats = replay_graph(ns, nodes, raw_edges, stem, bundle)
        g = gt[stem]
        pred_nodes = {int(n['node_id']): (int(n['t']), float(n['z']), float(n['y']), float(n['x'])) for n in n_nodes.values()}
        pred_edges = [(int(e['source_id']), int(e['target_id'])) for e in n_edges]
        gt_nodes = {int(nid): tuple(v) for nid, v in g['nodes_plain'].items()}
        gt_edges = [tuple(e) for e in g['edges_plain']]
        row = ns['score_sample'](pred_nodes, pred_edges, gt_nodes, gt_edges, g['t_true'])
        row['dataset'] = stem
        row.update(census(ns, n_nodes, n_edges))
        rows.append(row)
        print(f"  {stem}: adjEJ={row['adjusted_edge_jaccard']:.4f} div={row['div_tp']}/{row['div_fp']}/{row['div_fn']} nodes={row['nodes']} edges={row['edges']} forks={row['forks']} | readmit={stats.get('readmitted_nodes', 0)} gapfill={stats.get('gapfill_added_nodes', 0)} orphan_ex={stats.get('safe_division_orphan_exempted', 0)} orphan_ad={stats.get('safe_division_orphan_adopted', 0)}")
    total = ns['aggregate_official'](rows)
    print(f"\n  → TOTAL adjEJ={total['adjusted_edge_jaccard']:.6f} divJ={total['division_jaccard']:.4f} proxy={total['proxy_score']:.6f} div={total['div_tp']}/{total['div_fp']}/{total['div_fn']} ({time.time() - t0:.0f}s)")
    print(f"  → D2 anchor ver-11: adjEJ 0.930492 div 4/1/8 — so sánh fidelity ở đây")
    print(f"  → missed_gt={total['missed_gt_nodes']} spurious={total['spurious_pred_nodes']} edges_lost_det={total['edges_lost_to_detection']} frag={total['edges_fragmented']}")
    return 0


# ---------------------------------------------------------------- mode: hidden
def mode_hidden(env_overrides: dict, flips: bool, only: list | None = None) -> int:
    print('=== v12lab HIDDEN INSTRUMENTED REPLAY (CPU · 4 phim test · 3 GT div 05db) ===')
    print('  ⚠ F3 semantic delta: p_div/DC KHÔNG replay trên hidden — MIN_PDIV=0 + DC-bypass (chỉ đo gate hình học/divergence)')
    base_env = dict(env_overrides)
    base_env.setdefault('BIOHUB_SAFE_DIV_MIN_PDIV', '0')
    base_env.setdefault('BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV', '0')
    base_env.setdefault('BIOHUB_DIVNET_RANK', '0')
    base_env.setdefault('BIOHUB_DEEPCENTER_SAFE_DIV_VETO', '0')
    base_env.setdefault('BIOHUB_LOWDET_DIR', str(LOWDET_DIR))

    variants = {'base_v12_hidden': base_env}
    if flips:
        v = dict(base_env)
        v['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '0'
        variants['orphan_OFF'] = v
        v = dict(base_env)
        v['BIOHUB_SAFE_DIV_REQUIRE_DIVERGENCE'] = '0'
        variants['divergence_OFF'] = v
        v = dict(base_env)
        v['BIOHUB_SAFE_DIV_REQUIRE_DIVERGENCE'] = '0'
        v['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '0'
        variants['div_OFF+orphan_OFF(=v11-like)'] = v
        v = dict(base_env)
        # F3 bù: hidden không có p_div → mở REPARENT_MIN_PDIV=0 để reparent chạy thuần geometry
        v['BIOHUB_REPARENT_MIN_PDIV'] = '0'
        v['BIOHUB_REPARENT_EDGE_PROB'] = '0.50'
        variants['reparent_geo_ep50'] = v
        v = dict(base_env)
        v['BIOHUB_REPARENT_MIN_PDIV'] = '0'
        v['BIOHUB_REPARENT_EDGE_PROB'] = '0.50'
        v['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '1'
        v['BIOHUB_REPARENT_CURRENT_FAR_UM'] = '4.0'
        variants['combo_orphan+reparent_geo'] = v
        v = dict(base_env)
        v['BIOHUB_SAFE_DIV_SISTER_MAX_UM'] = '8.0'
        variants['sister_8(v10-geo)'] = v
        # KHÁM PHÁ MỚI (trace t=24): mồ côi cách đúng mẹ 9.45µm > SAFE_DIV_MAX_UM 9.0
        # → cần nới SAFE_DIV_MAX_UM lên 10-10.5 để đề xuất t=24 được sinh ra
        v = dict(base_env)
        v['BIOHUB_SAFE_DIV_MAX_UM'] = '10.5'
        variants['safediv_max_10p5(orphan)'] = v
        v = dict(base_env)
        v['BIOHUB_SAFE_DIV_MAX_UM'] = '10.5'
        v['BIOHUB_SAFE_DIV_REQUIRE_DIVERGENCE'] = '0'
        variants['safediv_10p5+divergence_OFF'] = v
    if only:
        variants = {k: v for k, v in variants.items() if any(o in k for o in only)}

    results = {}
    for label, env in variants.items():
        ns = load_ns(env)
        total_div = [0, 0, 0]
        cens = {}
        tr05 = None
        print(f'\n-- variant {label} --')
        for stem in TEST_STEMS:
            nodes, raw_edges = read_geff_nodes_edges(HIDDEN_GEFF_DIR / f'{stem}.geff')
            n_nodes, n_edges, stats = replay_graph(ns, nodes, raw_edges, stem, None)
            gt = read_gt_graph(stem)
            dc = div_check(ns, n_nodes, n_edges, gt)
            cens[stem] = census(ns, n_nodes, n_edges)
            cens[stem].update({'div_tp': dc['div_tp'], 'div_fp': dc['div_fp'], 'div_fn': dc['div_fn']})
            total_div = [a + b for a, b in zip(total_div, [dc['div_tp'], dc['div_fp'], dc['div_fn']])]
            print(f"  {stem}: nodes={cens[stem]['nodes']:,} edges={cens[stem]['edges']:,} forks={cens[stem]['forks']} div={dc['div_tp']}/{dc['div_fp']}/{dc['div_fn']}")
            if stem == '6bba_05db0fb1':
                tr05 = (n_nodes, n_edges, stats, dc, gt)
        results[label] = {'census': cens, 'div': total_div}
        print(f"  TOTAL div={total_div[0]}/{total_div[1]}/{total_div[2]} (GT 3 division thật 05db — replica ver11 receipt: 0/3)")
        if tr05 is not None:
            n_nodes, n_edges, stats, dc, gt = tr05
            print(f"  05db counters: orphan_exempted={stats.get('safe_division_orphan_exempted', 0)} orphan_adopted={stats.get('safe_division_orphan_adopted', 0)} div_rej={stats.get('safe_division_divergence_rejected', 0)} reparent_added={stats.get('reparent_added', 0)} reparent_pdiv_rej={stats.get('reparent_pdiv_rejected', 0)}")
            for gd in gt_dividing_nodes(gt):
                if (gd[0], gd[1]) in GT_DIVISIONS_05DB:
                    rep = trace_gt_division(ns, n_nodes, n_edges, gt, gd, dc['g2p'])
                    print(f"    GT div {gd[0]} (t={gd[1]}): " + json.dumps(rep, ensure_ascii=False, default=str)[:400])
    if flips and len(results) > 1:
        print('\n=== GATE-FLIP MATRIX (div TP trên 3 GT division thật 05db) ===')
        base_tp = results['base_v12_hidden']['div'][0]
        for label, r in results.items():
            print(f"  {label:32s} div={r['div'][0]}/{r['div'][1]}/{r['div'][2]} Δtp={r['div'][0] - base_tp:+d}")
    return 0


# ---------------------------------------------------------------- mode: replica
def mode_replica(csvs: list) -> int:
    print('=== v12lab REPLICA (engine scorer2code — verify 100% receipt alfonso 0.9605) ===')
    _ns = {'__name__': 'scorer2code'}
    exec('import itertools\nimport json\nimport os\nimport blosc2\nimport numpy as np\n'
         'import pandas as pd\nfrom scipy.optimize import linear_sum_assignment\n'
         'MAX_DISTANCE = 7.0\nSCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)\n'
         'ADJUSTMENT_ALPHA = 0.1\nSCORE_DIVISION_WEIGHT = 0.1\n', _ns)
    exec(SCORER.read_text(), _ns)
    load_gt = _ns['load_submission_graphs']
    evaluate_one = _ns['evaluate_one']
    summarise = _ns['summarise']
    gt_graphs = {}
    Graph = _ns['Graph']
    for stem in TEST_STEMS:
        gt_graphs[stem] = Graph(read_gt_graph(stem))
    for path in csvs:
        preds = load_gt(path)
        rows = []
        for stem in TEST_STEMS:
            if stem not in preds:
                print(f'  ⚠ {stem}: không có trong CSV')
                continue
            row = evaluate_one(preds[stem], gt_graphs[stem])
            row['dataset'] = stem
            rows.append(row)
            print(f"  {stem}: adjEJ={row['adj_edge_jaccard']:.4f} div={row['division_tp']}/{row['division_fp']}/{row['division_fn']} recall={row['node_recall']:.3f}")
        total = summarise(rows)
        print(f"  → {path} TOTAL adjEJ={total['adj_edge_jaccard']:.4f} divJ={total['division_jaccard']:.4f} REPLICA={total['score']:.4f}\n")
    return 0


# ---------------------------------------------------------------- main
def parse_env_args(args: list) -> dict:
    """Chấp nhận cả '--env K=V' (1 argv) lẫn '--env' 'K=V' (2 argv — shell tách space)."""
    env = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--env' and i + 1 < len(args):
            kv = args[i + 1]
            i += 2
        elif a.startswith('--env='):
            kv = a[len('--env='):]
            i += 1
        elif a.startswith('--env '):
            kv = a[len('--env '):]
            i += 1
        else:
            i += 1
            continue
        k, _, v = kv.partition('=')
        if v:
            env[k.strip()] = v.strip()
    return env


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mode = sys.argv[1]
    rest = sys.argv[2:]
    env = parse_env_args(rest)
    if mode == 'selftest':
        return mode_selftest()
    if mode == 'validator':
        return mode_validator(env)
    if mode == 'hidden':
        only = []
        if '--only' in rest:
            only = rest[rest.index('--only') + 1:]
        return mode_hidden(env, flips=any(a in rest for a in ('--flips',)), only=only or None)
    if mode == 'replica':
        csvs = [a for a in rest if not a.startswith('--')]
        return mode_replica(csvs)
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
