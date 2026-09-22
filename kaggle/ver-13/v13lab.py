#!/usr/bin/env python3
"""v13lab.py — V13-LAB CPU-ONLY (0 GPU) — V13-ADJEJ-RESEARCH.md §6 kế hoạch sweep offline.

Hai lớp (chạy LOCAL, không Kaggle, không GPU — kỉ luật GPU-WASTE-PREVENTION):

  (a) SELFTEST      — smoke đường mới v13 (LEAF-PRUNE port amanatar) + hồi quy
                      đường v12 (orphan/readmit/gapfill env-gated) + INT/DAG trên
                      đồ thị tổng hợp. Chạy trước mọi thứ, mỗi lần build lại.
  (b) SWEEP OFFLINE — 6 arm replay post-chain trên .geff RAW 4 phim test (từ output
                      v12.1 — cùng prediction stage, knockout không đổi predict) →
                      CSV (định dạng production mirror: INT + max(0, round)) → chấm
                      replica engine scorer2code (đã verify v11 0.9010 EXACT) →
                      bảng Δ giữa các arm + CỔNG quyết định lên GPU.

Cơ chế trung tâm (kế thừa v12lab): trích env-block + constants + post-chain +
scoring TỪ monolith v13 (vừa build) rồi exec vào namespace — env override TRƯỚC
khi exec → mỗi arm 1 namespace sạch (zero-drift so với code production — cùng
nguồn single source of truth).

⚠ F3 SEMANTIC DELTA (giống v12lab hidden): p_div/DC KHÔNG replay được local
   (bundle v11-lab đã mất theo sandbox; model cần image volumes) → sweep đặt
   MIN_PDIV=0 + DC-VETO=0 + REPARENT pdiv=0 CHO MỌI ARM như nhau. Hệ quả:
   * fork-count replay CAO hơn production (production DC 0.2 giết ~89% fork hình học)
     → census tuyệt đối KHÔNG so thẳng với production 144f — chỉ so Δ GIỮA CÁC ARM.
   * arm A (v11-geo) là neo hiệu chuẩn: Δ(B−A) phải ÂM hướng (production −0.0012).
   * P4b dcsd015 (DC 0.2→0.15) TẢI HIỆN trong replay (DC đã bypass) — chỉ đo được
     P4a divwide (hình học); P4b dựa vào sweep amanatar (adj nguyên vẹn) + cổng
     replica production sau GPU.
   * Cổng quyết định THẬT vẫn là replica-gate trên output GPU (engine exact).

ARM (V13-ADJEJ-RESEARCH.md §5 P1-P4 + đính chính P1 diverge=0.5):
   A v11geo    : diverge 0.5 · orphan 0 · vel 0.5 · leaf 0 · geo 9/14/10   (đối chứng baseline)
   B v121geo   : diverge −2.0 · orphan 1 · vel 0.5 · leaf 0 · geo 9/14/10  (hiệu chuẩn hướng −0.0012)
   C v13full   : diverge 0.5 · orphan 0 · vel 0.25 · leaf 0.3 · geo 11/16/12 (ỨNG VIÊN GPU)
   D v13noP4   : = C nhưng geo 9/14/10                                     (cách ly P4)
   E v13vel    : diverge 0.5 · orphan 0 · vel 0.25 · leaf 0 · geo 9/14/10   (cách ly P2)
   F v13div225 : = C nhưng diverge 2.25 (giá trị amanatar — đo riêng)      (so 0.5 vs 2.25)

CỔNG LÊN GPU (sau sweep, trước khi đụng 0.71h):
   G1: Δadj(C−A) ≥ +0.0008  (kỳ vọng P2+P3 = +0.0018 theo amanatar — chặn nửa cho an toàn)
   G2: Δadj(B−A) < 0        (hiệu chuẩn hướng: replay thấy đúng dấu thất bại v12.1)
   G3: census C node ∈ [120.000, 126.000] · không purge (node A − node C ≤ 3.000)
   G4: nếu G1 fail nhưng Δadj(D−A) ≥ +0.0008 → lên GPU với v13-noP4 (P4 gây hại → bỏ)
   G5: leaf_prune receipts C: tổng 4 phim ∈ [30, 400] (amanatar 71 — ngoài khoảng = suspect)

Usage:
  python3 v13lab.py selftest                    # smoke leaf-prune + hồi quy v12 (chạy đầu tiên)
  python3 v13lab.py sweep                       # 6 arm replay → CSV → replica → bảng + cổng
  python3 v13lab.py sweep --only C v13full      # chỉ 1 arm (debug)
  python3 v13lab.py replica <csv> [csv2 ...]    # chấm replica engine scorer2code
Điều kiện: GT tại /home/z/v11-recovery/test-gt (khôi phục: python3 kaggle/api/replica-gate.py --restore-gt)
           .geff RAW tại kaggle/api/output/latest/tracking_repo/predictions/.../split_0/ (có sẵn repo)
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
GT_DIR = RECOVERY / 'test-gt'
HIDDEN_GEFF_DIR = HERE.parent / 'api' / 'output' / 'latest' / 'tracking_repo' / 'predictions' / 'unknown' / 'unet_transformer' / 'split_0'
SWEEP_OUT = HERE / 'sweep-out'
SCORER = HERE.parent / 'scorer' / 'scorer2code.py'
TEST_STEMS = ['44b6_0113de3b', '44b6_0b24845f', '6bba_05b6850b', '6bba_05db0fb1']
LOWDET_DIR = HERE / 'lowdet-selftest'  # dump giả lập cho selftest readmit/gapfill

# F3 semantic delta — áp CHO MỌI ARM như nhau (xem docstring)
BASE_SWEEP_ENV = {
    'BIOHUB_SAFE_DIV_MIN_PDIV': '0',
    'BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV': '0',
    'BIOHUB_DIVNET_RANK': '0',
    'BIOHUB_DEEPCENTER_SAFE_DIV_VETO': '0',
    'BIOHUB_REPARENT_MIN_PDIV': '0',
    'BIOHUB_LOWDET_DIR': '',
    'BIOHUB_READMIT_RADIUS_UM': '0',
    'BIOHUB_GAPFILL_MAX_GAP': '0',
}

ARMS = {
    'A_v11geo':   {'BIOHUB_SAFE_DIV_DIVERGE_UM': '0.5',  'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': '0', 'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': '0.5',  'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': '0', 'BIOHUB_SAFE_DIV_MAX_UM': '9.0',  'BIOHUB_SAFE_DIV_SISTER_MAX_UM': '14.0', 'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': '10.0'},
    'B_v121geo':  {'BIOHUB_SAFE_DIV_DIVERGE_UM': '-2.0', 'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': '1', 'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': '0.5',  'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': '0', 'BIOHUB_SAFE_DIV_MAX_UM': '9.0',  'BIOHUB_SAFE_DIV_SISTER_MAX_UM': '14.0', 'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': '10.0'},
    'C_v13full':  {'BIOHUB_SAFE_DIV_DIVERGE_UM': '0.5',  'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': '0', 'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': '0.25', 'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': '0.3', 'BIOHUB_SAFE_DIV_MAX_UM': '11.0', 'BIOHUB_SAFE_DIV_SISTER_MAX_UM': '16.0', 'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': '12.0'},
    'D_v13noP4':  {'BIOHUB_SAFE_DIV_DIVERGE_UM': '0.5',  'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': '0', 'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': '0.25', 'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': '0.3', 'BIOHUB_SAFE_DIV_MAX_UM': '9.0',  'BIOHUB_SAFE_DIV_SISTER_MAX_UM': '14.0', 'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': '10.0'},
    'E_v13vel':   {'BIOHUB_SAFE_DIV_DIVERGE_UM': '0.5',  'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': '0', 'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': '0.25', 'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': '0', 'BIOHUB_SAFE_DIV_MAX_UM': '9.0',  'BIOHUB_SAFE_DIV_SISTER_MAX_UM': '14.0', 'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': '10.0'},
    'F_v13div225': {'BIOHUB_SAFE_DIV_DIVERGE_UM': '2.25', 'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': '0', 'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': '0.25', 'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': '0.3', 'BIOHUB_SAFE_DIV_MAX_UM': '11.0', 'BIOHUB_SAFE_DIV_SISTER_MAX_UM': '16.0', 'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': '12.0'},
}

V11_PROD_CENSUS = {'nodes': 122787, 'edges': 118332, 'forks': 144}      # ref 56403231 LB 0.947
V121_PROD_CENSUS = {'nodes': 122808, 'edges': 118393, 'forks': 184}     # ref 56442903 LB 0.946
V121_PROD_REPLICA = {'adj': 0.8998, 'divJ': 0.1429, 'composite': 0.9141}


# ---------------------------------------------------------------- monolith extraction
def extract_regions(mono_text: str) -> dict:
    """Trích 4 vùng từ monolith v13: env-block / constants / post-chain / scoring."""
    env_start = mono_text.index("BIOHUB_PRESET = 'harmonic_v3_division_wide'")
    env_end = mono_text.index('import json as _guard_json')
    const_start = mono_text.index("DET_THRESHOLD = float(os.environ.get('BIOHUB_DET_THRESHOLD', '0.99'))")
    const_end = mono_text.index('CONFIG_DISPLAY = {')
    chain_start = mono_text.index('from scipy.optimize import linear_sum_assignment')
    chain_end = mono_text.index('DEEPCENTER_VETO_DETECTOR = load_deepcenter_veto_detector()')
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
    """Namespace monolith v13: env production + override + exec vùng code (kế thừa v12lab).

    CHÚ Ý: env-block monolith set os.environ trực tiếp → khôi phục env sau exec
    để arm sau không dính giá trị cũ (mỗi load_ns gọi trên env sạch).
    """
    saved = dict(os.environ)
    try:
        regions = extract_regions(MONO.read_text())
        ns = {'__name__': 'v13lab_mono', '__file__': str(MONO)}
        import json as _j
        import math as _m
        from pathlib import Path as _P
        from scipy.optimize import linear_sum_assignment as _lsa
        from scipy.spatial import cKDTree as _kd
        ns.update({'os': os, 'json': _j, 'math': _m, 'Path': _P, 'np': np,
                   'linear_sum_assignment': _lsa, 'cKDTree': _kd})
        exec(regions['env'], ns)
        for k, v in (env_overrides or {}).items():
            os.environ[k] = str(v)
        exec(regions['consts'], ns)
        exec(regions['chain'], ns)
        exec(regions['score_consts'], ns)
        exec(regions['score_fns'], ns)
        ns.setdefault('TEST_DIR', Path('/nonexistent-test-dir'))
        ns.setdefault('WORKING_DIR', Path('.'))
        return ns
    finally:
        os.environ.clear()
        os.environ.update(saved)


# ---------------------------------------------------------------- geff loaders
def read_geff_nodes_edges(path: Path) -> tuple[dict, list]:
    """Đọc .geff prediction RAW → (nodes_by_id, raw_edges có edge_prob) — zarr thuần."""
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
def replay_graph(ns: dict, nodes_by_id: dict, raw_edges: list, dataset: str, divnet_bundle=None, deepcenter_bundle=None):
    """Chạy filter_output_graph (toàn post-chain v13) trên 1 graph RAW. Trả (nodes, edges, stats)."""
    nodes_by_id = {int(k): dict(v) for k, v in nodes_by_id.items()}
    raw_edges = [dict(e) for e in raw_edges]
    nodes, edges, stats = ns['filter_output_graph'](nodes_by_id, raw_edges, dataset=dataset,
                                                    deepcenter_bundle=deepcenter_bundle, divnet_bundle=divnet_bundle)
    return nodes, edges, stats


def census(ns: dict, nodes: dict, edges: list) -> dict:
    """Census theo dataset (L12): node/edge/fork."""
    by_source = {}
    for e in edges:
        by_source.setdefault(int(e['source_id']), []).append(e)
    forks = sum(1 for v in by_source.values() if len(v) >= 2)
    return {'nodes': len(nodes), 'edges': len(edges), 'forks': forks}


def div_check(ns: dict, nodes: dict, edges: list, gt: dict) -> dict:
    """Đối chiếu division với GT: match node bipartite + compute_division_confusion."""
    pred_nodes = {int(n['node_id']): (int(n['t']), float(n['z']), float(n['y']), float(n['x'])) for n in nodes.values()}
    gt_nodes = {int(gid): (float(t), float(z), float(y), float(x)) for gid, t, z, y, x in zip(gt['ids'], gt['t'], gt['z'], gt['y'], gt['x'])}
    pred_edges = [(int(e['source_id']), int(e['target_id'])) for e in edges]
    gt_edges = [(int(s), int(d)) for s, d in gt['edges']]
    p2g, g2p = ns['match_nodes_bipartite'](pred_nodes, gt_nodes, max_dist=7.0)
    tp, fp, fn = ns['compute_division_confusion'](pred_nodes, pred_edges, gt_nodes, gt_edges, p2g, g2p)
    return {'div_tp': int(tp), 'div_fp': int(fp), 'div_fn': int(fn)}


# ---------------------------------------------------------------- CSV writer (mirror production)
CSV_COLUMNS = ['id', 'dataset', 'row_type', 'node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id']


def write_submission_csv(graphs: dict[str, tuple[dict, list]], path: Path) -> int:
    """Viết CSV đúng production format (write_test_submission mirror):
    node theo sorted(node_id) · z/y/x = max(0, int(round())) · INT toàn bộ (L5) ·
    node rows trước edge rows mỗi dataset · thứ tự dataset = TEST_STEMS trước,
    stem ngoài danh sách giữ cuối (cho selftest)."""
    import csv as _csv
    row_id = 0
    order = [s for s in TEST_STEMS if s in graphs] + [s for s in graphs if s not in TEST_STEMS]
    with path.open('w', newline='') as fh:
        writer = _csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for stem in order:
            nodes_by_id, edges = graphs[stem]
            for node_id in sorted(nodes_by_id):
                node = nodes_by_id[node_id]
                writer.writerow({'id': row_id, 'dataset': stem, 'row_type': 'node',
                                 'node_id': int(node['node_id']), 't': int(node['t']),
                                 'z': max(0, int(round(float(node['z'])))),
                                 'y': max(0, int(round(float(node['y'])))),
                                 'x': max(0, int(round(float(node['x'])))),
                                 'source_id': -1, 'target_id': -1})
                row_id += 1
            for edge in edges:
                source_id = int(edge['source_id'])
                target_id = int(edge['target_id'])
                if source_id not in nodes_by_id or target_id not in nodes_by_id:
                    raise AssertionError(f'{stem}: dangling edge sau replay ({source_id}->{target_id})')
                writer.writerow({'id': row_id, 'dataset': stem, 'row_type': 'edge',
                                 'node_id': -1, 't': -1, 'z': -1, 'y': -1, 'x': -1,
                                 'source_id': source_id, 'target_id': target_id})
                row_id += 1
    return row_id


# ---------------------------------------------------------------- mode: selftest
def mode_selftest() -> int:
    """Smoke CPU: (1) LEAF-PRUNE đường mới v13 · (2) hồi quy v12 machinery · (3) INT/DAG."""
    print('=== v13lab selftest — smoke LEAF-PRUNE (v13) + hồi quy v12 (CPU, đồ thị tổng hợp) ===')

    # ---- (1) LEAF-PRUNE — env v13 mặc định đã bật leaf 0.3 qua env-block monolith ----
    ns = load_ns()  # KHÔNG override — namespace chính là config v13 (leaf 0.3, vel 0.25, divwide)
    assert ns['LEAF_PRUNE_MIN_EDGE_PROB'] == 0.30, f"env v13 chưa vào hằng số LEAF ({ns['LEAF_PRUNE_MIN_EDGE_PROB']})"
    assert ns['MOTION_RELINK_VELOCITY_WEIGHT'] == 0.25, 'env v13 chưa vào VELOCITY'
    assert ns['SAFE_DIV_MAX_UM'] == 11.0 and ns['SAFE_DIV_SISTER_MAX_UM'] == 16.0, 'env v13 chưa vào DIVWIDE'
    assert ns['SAFE_DIV_DIVERGE_UM'] == 0.5 and not ns['SAFE_DIV_ORPHAN_ADOPT'], 'env v13 chưa vào P1 revert'
    print(f"  namespace v13: leaf={ns['LEAF_PRUNE_MIN_EDGE_PROB']} vel={ns['MOTION_RELINK_VELOCITY_WEIGHT']} "
          f"divwide={ns['SAFE_DIV_MAX_UM']}/{ns['SAFE_DIV_SISTER_MAX_UM']}/{ns['SAFE_DIV_EXISTING_CHILD_MAX_UM']} "
          f"diverge={ns['SAFE_DIV_DIVERGE_UM']} orphan={ns['SAFE_DIV_ORPHAN_ADOPT']} DC={ns['DEEPCENTER_SAFE_DIV_THRESHOLD']}")

    # Đồ thị tổng hợp cho UNIT test (gọi hàm TRỰC TIẾP — không qua post-chain nên
    # 100% deterministic): track chính t=0..4 cạnh mạnh + 4 node kiểm thử:
    #   L(t=5): node lá, cạnh vào YẾU 0.10                          → PHẢI bị prune
    #   D(t=3): node lá 1 cạnh vào edge_prob None (con safe-div)    → KHÔNG prune
    #   F(t=6): node lá ở frame CUỐI (max_t=6), cạnh yếu            → KHÔNG prune
    #   M(t=4): node lá 1 cạnh vào prob None                        → KHÔNG prune
    # (track chính t=0..6 để L(t=5) KHÔNG phải max_t — F t=6 mới là max_t)
    nodes = {}
    def add(nid, t, z, y, x):
        nodes[nid] = {'node_id': nid, 't': t, 'z': z, 'y': y, 'x': x}
    for i in range(7):
        add(i, i, 10.0, 20.0 + i * 0.8, 30.0)
    add(50, 5, 10.0, 24.6, 30.0)   # L — lá yếu (t=5 < max_t=6)
    add(51, 3, 10.0, 22.4, 31.0)   # D — con division style (prob None)
    add(52, 6, 10.0, 24.8, 29.0)   # F — lá frame cuối (max_t=6)
    add(53, 4, 10.0, 23.2, 31.0)   # M — lá prob None
    edges = [{'source_id': i, 'target_id': i + 1, 'edge_prob': 0.9} for i in range(6)]
    edges.append({'source_id': 4, 'target_id': 50, 'edge_prob': 0.10})          # cạnh vào L — yếu
    edges.append({'source_id': 2, 'target_id': 51, 'edge_prob': None})          # D: prob None
    edges.append({'source_id': 5, 'target_id': 52, 'edge_prob': 0.10})          # F: lá frame cuối
    edges.append({'source_id': 3, 'target_id': 53, 'edge_prob': None})          # M: prob None

    stats_u = {}
    nodes_u, edges_u = ns['prune_weak_leaf_nodes'](nodes, edges, stats_u)
    lp_n, lp_e = stats_u.get('leaf_prune_nodes', 0), stats_u.get('leaf_prune_edges', 0)
    print(f"  UNIT leaf-prune: pruned={lp_n}/{lp_e} | nodes {len(nodes)}→{len(nodes_u)} | edges {len(edges)}→{len(edges_u)}")
    assert lp_n == 1 and lp_e == 1, f'UNIT leaf-prune phải cắt đúng 1 node/1 cạnh (thực tế {lp_n}/{lp_e})'
    assert 50 not in nodes_u, 'node L (lá yếu 0.10) KHÔNG bị prune — sai logic'
    assert 51 in nodes_u and 53 in nodes_u, 'node prob-None bị prune — VI PHẠM miễn trừ edge_prob None!'
    assert 52 in nodes_u, 'node F (lá frame cuối max_t) bị prune — VI PHẠM miễn trừ terminal!'
    print('  UNIT LEAF-PRUNE PASS — prune đúng L; miễn trừ (prob-None ×2 + terminal) đúng')

    # ---- (1b) INTEGRATION: leaf-prune gọi ĐÚNG VỊ TRÍ trong post-chain ----
    # Track dài t=0..9 (≥ min_track_len 6, 1 component, không fork — tránh can
    # thiệp division-geometry/reparent) + node lá yếu t=5 đặt SÁT track (motion
    # relink giữ cạnh tight). Điều kiện prune: t=5 < max_t=9 ✓ prob 0.10 < 0.3 ✓.
    nodes_i = {}
    def addi(nid, t, z, y, x):
        nodes_i[nid] = {'node_id': nid, 't': t, 'z': z, 'y': y, 'x': x}
    for i in range(10):
        addi(i, i, 10.0, 20.0 + i * 0.8, 30.0)
    addi(60, 5, 10.0, 24.6, 30.0)  # lá yếu sát node 5 (y=24.0) — 0.6 vox
    edges_i = [{'source_id': i, 'target_id': i + 1, 'edge_prob': 0.9} for i in range(9)]
    edges_i.append({'source_id': 5, 'target_id': 60, 'edge_prob': 0.10})
    nodes2, edges2, stats = replay_graph(ns, nodes_i, edges_i, 'selftest-leaf')
    lp_n = stats.get('leaf_prune_nodes', 0)
    gone = 60 not in nodes2
    print(f"  INTEGRATION: leaf_pruned={lp_n} | node60 còn? {'CÒN' if not gone else 'đã mất'} | nodes {len(nodes_i)}→{len(nodes2)}")
    assert lp_n >= 1 or gone, 'INTEGRATION: đường leaf-prune trong post-chain không hoạt động (stats=0 và node yếu vẫn còn)'
    for e in edges2:
        s, d = int(e['source_id']), int(e['target_id'])
        assert s in nodes2 and d in nodes2, 'cạnh treo lơ lửng'
        assert int(nodes2[d]['t']) == int(nodes2[s]['t']) + 1, 'cạnh không liên tiếp'
    print('  INTEGRATION LEAF-PRUNE PASS · INT/DAG PASS')

    # ---- (2) hồi quy v12 machinery: readmit/gapfill vẫn chạy khi env override bật ----
    ns12 = load_ns({'BIOHUB_SAFE_DIV_MIN_PDIV': '0', 'BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV': '0',
                    'BIOHUB_DIVNET_RANK': '0', 'BIOHUB_DEEPCENTER_SAFE_DIV_VETO': '0',
                    'BIOHUB_READMIT_RADIUS_UM': '4', 'BIOHUB_GAPFILL_MAX_GAP': '3',
                    'BIOHUB_GAPFILL_MAX_ADDED_FRAC': '0.5', 'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': '0',
                    'BIOHUB_LOWDET_DIR': str(LOWDET_DIR)})
    assert ns12['READMIT_RADIUS_UM'] == 4.0 and ns12['GAPFILL_MAX_GAP'] == 3, 'env v12 override không vào constants'
    nodesA = {}
    def addA(nid, t, z, y, x):
        nodesA[nid] = {'node_id': nid, 't': t, 'z': z, 'y': y, 'x': x}
    for i in range(5):
        addA(i, i, 10.0, 20.0 + i * 0.8, 30.0)
    for i in range(5):
        addA(100 + i, 9 + i, 10.0, 20.0 + 9 * 0.8 + i * 0.8, 30.0)
    edgesA = [{'source_id': i, 'target_id': i + 1, 'edge_prob': 0.9} for i in range(4)]
    edgesA += [{'source_id': 100 + i, 'target_id': 101 + i, 'edge_prob': 0.9} for i in range(4)]
    LOWDET_DIR.mkdir(parents=True, exist_ok=True)
    low = [(5, 10.0, 24.0, 30.0), (6, 10.0, 24.8, 30.0), (7, 10.0, 25.6, 30.0), (8, 10.0, 26.4, 30.0)]
    np.savez_compressed(LOWDET_DIR / 'selftest-ds.npz',
                        low_coords=np.array(low, dtype=np.int16),
                        low_score=np.array([0.99, 0.6, 0.55, 0.6], dtype=np.float32))
    nodesA2, edgesA2, statsA = replay_graph(ns12, nodesA, edgesA, 'selftest-ds')
    assert statsA.get('readmitted_nodes', 0) >= 1, 'READMIT hồi quy (không thêm node)'
    assert statsA.get('gapfill_added_nodes', 0) >= 2, 'GAPFILL hồi quy (không bắc cầu)'
    print(f"  hồi quy v12: readmitted={statsA.get('readmitted_nodes', 0)} gapfill={statsA.get('gapfill_added_nodes', 0)} PASS")

    # ---- (3) CSV writer: INT + DAG trên đồ thị vừa replay ----
    SWEEP_OUT.mkdir(parents=True, exist_ok=True)
    csv_path = SWEEP_OUT / 'selftest-submission.csv'
    n_rows = write_submission_csv({'selftest-leaf': (nodes2, edges2)}, csv_path)
    import csv as _csv2
    with csv_path.open(newline='') as fh:
        rows = list(_csv2.DictReader(fh))
    assert n_rows > 0 and rows, 'CSV writer ghi 0 dòng'
    for r in rows:
        for c in ('id', 'node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id'):
            v = r[c]
            assert str(int(v)) == str(v), f'CSV không INT: {c}={v!r}'
    print(f'  CSV writer: {n_rows} dòng toàn INT — {csv_path.name}')
    print('=== SELFTEST PASS — v13 (leaf-prune + hồi quy v12 + CSV INT/DAG) chạy đúng ===')
    return 0


# ---------------------------------------------------------------- mode: sweep
def score_csvs_replica(csvs: list[Path]) -> dict[str, dict]:
    """Chấm list CSV bằng replica engine scorer2code — trả {path: totals}."""
    _ns = {'__name__': 'scorer2code'}
    exec('import itertools\nimport json\nimport os\nimport blosc2\nimport numpy as np\n'
         'import pandas as pd\nfrom scipy.optimize import linear_sum_assignment\n'
         'MAX_DISTANCE = 7.0\nSCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)\n'
         'ADJUSTMENT_ALPHA = 0.1\nSCORE_DIVISION_WEIGHT = 0.1\n', _ns)
    exec(SCORER.read_text(), _ns)
    load_gt = _ns['load_submission_graphs']
    evaluate_one = _ns['evaluate_one']
    summarise = _ns['summarise']
    Graph = _ns['Graph']
    gt_graphs = {}
    for stem in TEST_STEMS:
        gt_graphs[stem] = Graph(read_gt_graph(stem))
    out = {}
    for path in csvs:
        preds = load_gt(path)
        rows = []
        for stem in TEST_STEMS:
            if stem not in preds:
                print(f'  ⚠ {stem}: không có trong CSV {path.name}')
                continue
            row = evaluate_one(preds[stem], gt_graphs[stem])
            row['dataset'] = stem
            rows.append(row)
        total = summarise(rows)
        out[str(path)] = total
    return out


def mode_sweep(only: list | None = None) -> int:
    print('=== v13lab SWEEP OFFLINE (CPU · 0 GPU · 4 phim RAW .geff output v12.1) ===')
    print('  ⚠ F3 semantic delta: MIN_PDIV=0 + DC-VETO=0 + reparent-pdiv=0 cho MỌI arm —')
    print('    census tuyệt đối KHÔNG so thẳng production; chỉ Δ GIỮA ARM là đáng tin.')
    have_gt = GT_DIR.is_dir() and all((GT_DIR / f'{s}.geff').exists() for s in TEST_STEMS)
    if not have_gt:
        print('  ⚠ GT thiếu — chế độ CENSUS-ONLY (không div_check/không chấm replica/không cổng Δ).')
        print('    Khôi phục GT một lần để mở đầy đủ: python3 kaggle/api/replica-gate.py --restore-gt')
    missing_geff = [s for s in TEST_STEMS if not (HIDDEN_GEFF_DIR / f'{s}.geff').exists()]
    if missing_geff:
        print(f'❌ RAW .geff thiếu: {missing_geff} tại {HIDDEN_GEFF_DIR}')
        return 1

    arms = ARMS
    if only:
        arms = {k: v for k, v in ARMS.items() if any(o in k for o in only)}
    SWEEP_OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    summary = {}
    for label, arm_env in arms.items():
        env = {**BASE_SWEEP_ENV, **arm_env}
        ns = load_ns(env)
        graphs = {}
        cens = {}
        divs = [0, 0, 0]
        leaf_total = 0
        print(f'\n-- arm {label} --')
        for stem in TEST_STEMS:
            nodes, raw_edges = read_geff_nodes_edges(HIDDEN_GEFF_DIR / f'{stem}.geff')
            n_nodes, n_edges, stats = replay_graph(ns, nodes, raw_edges, stem)
            graphs[stem] = (n_nodes, n_edges)
            cens[stem] = census(ns, n_nodes, n_edges)
            if have_gt:
                gt = read_gt_graph(stem)
                dc = div_check(ns, n_nodes, n_edges, gt)
                cens[stem].update(dc)
                divs = [a + b for a, b in zip(divs, [dc['div_tp'], dc['div_fp'], dc['div_fn']])]
                div_s = f" div={dc['div_tp']}/{dc['div_fp']}/{dc['div_fn']}"
            else:
                div_s = ''
            leaf_total += int(stats.get('leaf_prune_nodes', 0))
            print(f"  {stem}: {cens[stem]['nodes']:,}n/{cens[stem]['edges']:,}e/{cens[stem]['forks']}f"
                  f"{div_s} leaf_pruned={stats.get('leaf_prune_nodes', 0)}")
        csv_path = SWEEP_OUT / f'sub-{label}.csv'
        n_rows = write_submission_csv(graphs, csv_path)
        tot_n = sum(c['nodes'] for c in cens.values())
        tot_e = sum(c['edges'] for c in cens.values())
        tot_f = sum(c['forks'] for c in cens.values())
        summary[label] = {'csv': str(csv_path), 'rows': n_rows, 'nodes': tot_n, 'edges': tot_e,
                          'forks': tot_f, 'div': divs, 'leaf': leaf_total, 'census': cens}
        print(f"  TOTAL: {tot_n:,}n/{tot_e:,}e/{tot_f}f div={divs[0]}/{divs[1]}/{divs[2]} leaf={leaf_total} → {csv_path.name}")

    # ---- chấm replica toàn bộ arm (chỉ khi có GT) ----
    scores = {}
    if have_gt:
        print('\n=== REPLICA SCORE (engine scorer2code — cùng engine replica-gate production) ===')
        scores = score_csvs_replica([Path(v['csv']) for v in summary.values()])
        for label, s in scores.items():
            print(f"  {Path(label).name:28s} adjEJ={s['adj_edge_jaccard']:.4f} divJ={s['division_jaccard']:.4f} "
                  f"REPLICA={s['score']:.4f} div={s['division_tp']}/{s['division_fp']}/{s['division_fn']}")
    else:
        print('\n=== CENSUS-ONLY (chưa có GT) — bảng census Δ giữa arm vẫn đáng tin ===')

    # ---- bảng Δ + cổng ----
    base = None
    for k in ('A_v11geo',):
        if k in scores:
            base = scores[k]
    if base is None:
        print('\n⚠ thiếu GT hoặc thiếu arm A_v11geo — không tính Δ điểm (census-only).')
        # bảng census-only
        print(f"\n{'arm':28s} {'nodes':>9s} {'edges':>9s} {'forks':>6s} {'leaf':>5s} {'Δnodes vs A':>12s} {'Δedges':>9s} {'Δforks':>7s}")
        a = summary.get('A_v11geo')
        for label, r in summary.items():
            dn = (r['nodes'] - a['nodes']) if a else 0
            de = (r['edges'] - a['edges']) if a else 0
            df = (r['forks'] - a['forks']) if a else 0
            print(f"{label:28s} {r['nodes']:>9,} {r['edges']:>9,} {r['forks']:>6} {r['leaf']:>5} {dn:>+12,} {de:>+9,} {df:>+7}")
        out_json = {'summary': {k: {kk: vv for kk, vv in v.items() if kk != 'census'} for k, v in summary.items()},
                    'mode': 'census-only'}
        (SWEEP_OUT / 'sweep-summary.json').write_text(json.dumps(out_json, indent=2, default=str))
        print(f"\n→ sweep-summary.json (census-only) đã lưu tại {SWEEP_OUT}/ · {time.time() - t0:.0f}s")
        return 0
    print(f"\n{'arm':28s} {'Δadj vs A':>10s} {'ΔdivJ':>8s} {'ΔREPLICA':>9s} {'nodes':>9s} {'edges':>9s} {'forks':>6s} {'leaf':>5s}")
    deltas = {}
    for label, r in summary.items():
        s = scores.get(r['csv'])
        if s is None:
            continue
        d_adj = s['adj_edge_jaccard'] - base['adj_edge_jaccard']
        d_div = s['division_jaccard'] - base['division_jaccard']
        d_rep = s['score'] - base['score']
        deltas[label] = {'d_adj': d_adj, 'd_div': d_div, 'd_rep': d_rep}
        print(f"{label:28s} {d_adj:+10.4f} {d_div:+8.4f} {d_rep:+9.4f} {r['nodes']:>9,} {r['edges']:>9,} {r['forks']:>6} {r['leaf']:>5}")

    # ---- CỔNG LÊN GPU ----
    print('\n=== CỔNG LÊN GPU (V13-ADJEJ-RESEARCH.md §6 + đính chính P1) ===')
    checks = []
    def gate(name, ok, detail):
        checks.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    c = deltas.get('C_v13full')
    b = deltas.get('B_v121geo')
    if c is not None:
        gate('G1 Δadj(C−A) ≥ +0.0008', c['d_adj'] >= 0.0008, f"Δ={c['d_adj']:+.4f} (kỳ vọng P2+P3 +0.0018, chặn nửa an toàn)")
    if b is not None:
        gate('G2 Δadj(B−A) < 0 (hiệu chuẩn hướng v12.1 −0.0012)', b['d_adj'] < 0, f"Δ={b['d_adj']:+.4f}")
    if 'C_v13full' in summary:
        r = summary['C_v13full']
        gate('G3 census C node ∈ [120000, 126000]', 120000 <= r['nodes'] <= 126000, f"nodes={r['nodes']:,}")
        purge = summary['A_v11geo']['nodes'] - r['nodes'] if 'A_v11geo' in summary else 0
        gate('G3b không purge (A.nodes − C.nodes ≤ 3000)', purge <= 3000, f"chênh={purge:,}")
        gate('G5 leaf receipts C ∈ [30, 400]', 30 <= r['leaf'] <= 400, f"leaf={r['leaf']} (amanatar 71)")
    if c is not None and c['d_adj'] < 0.0008:
        d = deltas.get('D_v13noP4')
        if d is not None:
            gate('G4 fallback Δadj(D−A) ≥ +0.0008 (v13-noP4)', d['d_adj'] >= 0.0008, f"Δ={d['d_adj']:+.4f}")
    n_pass = sum(1 for x in checks if x)
    print(f"\n→ {n_pass}/{len(checks)} cổng PASS · {time.time() - t0:.0f}s · CSV arm tại {SWEEP_OUT}/")
    print('→ QUYẾT ĐỊNH: mọi cổng chính PASS → đề xuất user duyệt GPU 0.71h (push biohub-ver13 v1).')
    print('→ Cổng THẬT sau GPU: replica-gate trên output (adjEJ > 0.9010 v11) trước khi đề xuất submit.')
    # lưu json tổng hợp
    out_json = {'deltas': deltas, 'summary': {k: {kk: vv for kk, vv in v.items() if kk != 'census'} for k, v in summary.items()},
                'scores': {Path(k).name: v for k, v in scores.items()}, 'base': 'A_v11geo'}
    (SWEEP_OUT / 'sweep-summary.json').write_text(json.dumps(out_json, indent=2, default=str))
    print(f"→ sweep-summary.json đã lưu tại {SWEEP_OUT}/")
    return 0


# ---------------------------------------------------------------- mode: replica
def mode_replica(csvs: list) -> int:
    print('=== v13lab REPLICA (engine scorer2code — verify v11 0.9010 EXACT) ===')
    if not GT_DIR.is_dir():
        print(f'❌ GT thiếu tại {GT_DIR} — khôi phục: python3 kaggle/api/replica-gate.py --restore-gt')
        return 1
    if not csvs:
        print('Usage: python3 v13lab.py replica <csv> [csv2 ...]')
        return 1
    scores = score_csvs_replica([Path(c) for c in csvs])
    for k, s in scores.items():
        print(f"  → {k} TOTAL adjEJ={s['adj_edge_jaccard']:.4f} divJ={s['division_jaccard']:.4f} REPLICA={s['score']:.4f}\n")
    return 0


# ---------------------------------------------------------------- main
def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    mode = sys.argv[1]
    rest = sys.argv[2:]
    if mode == 'selftest':
        return mode_selftest()
    if mode == 'sweep':
        only = []
        if '--only' in rest:
            only = rest[rest.index('--only') + 1:]
        return mode_sweep(only=only or None)
    if mode == 'replica':
        return mode_replica([a for a in rest if not a.startswith('--')])
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
