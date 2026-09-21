#!/usr/bin/env python3
"""build-ver12-monolith.py — Dựng ver-12 monolith từ ver-11 (đã submit ref 56403231).

Ver-12 = ver-11 + PORTFOLIO 4 TRỤC (V12-RESEARCH.md §4, mỗi trục env-gated — tắt
được từng cái cho A/B trên v12-lab):

  TRỤC 1b REPARENT MỞ GATE   : REPARENT_EDGE_PROB 0.25→cfg (F7: pool 05db 15.833
                                cands bị chặn 13.143 ở pdiv) + MIN_PDIV/FAR/DIVERGE
                                + DIV_PARENT_MAX_UM (F6 sweep) — đánh 2/3 FN thật
                                (sai-gán-cha, §2 giải phẫu).
  TRỤC 1c ORPHAN-ADOPTION     : SAFE_DIV_ORPHAN_ADOPT — sửa "tấm màn" gate divergence
                                đòi mồ côi có successor t+2 (F1: 05db divergence_rejected
                                1894) — mồ côi đúng-1-cha được miễn divergence, floor
                                p_div riêng SAFE_DIV_ORPHAN_MIN_PDIV.
  TRỤC 2a READMIT (port ~54dòng): tái nhập detection mạnh bị ILP vứt trong 4µm quanh
                                track end/start — receipt hidden +1.014 node/+1.002 cạnh
                                (thtennant batch-B, hiệu ứng đơn lẻ lớn nhất).
  TRỤC 2b GAPFILL (port ~200dòng): bắc cầu gap ≤3 frame bằng peak THẬT (0 synthetic mặc
                                định) + Hungarian + context-cos + budget 3% — receipt
                                hidden +167 node/+240 cạnh.
  TRỤC 2* LOWDET DUMP STAGE   : 3 patch vào predict_unet_transformer.py (F2: monolith
                                ver-11 KHÔNG có stage dump) — dump peaks ≥ threshold
                                trên logits ĐÃ blend dual-seed cho pool READMIT/GAPFILL.
  TRỤC 3  SEF_TTA_WEIGHT      : 0.75→cfg (1.0 sau A/B v12-lab; guard cập nhật theo).
  TRỤC 1c' DC_SAFE_DIV        : 0.20→cfg (0.25 hội tụ nguồn thứ 4; guard cập nhật theo).

Config đọc từ ver-12-config.json (cùng thư mục) — DRAFT-1 pre-lab; sau v12-lab grid
(21-22/9) ghi lại config thắng rồi build lại (cùng workflow ver-11: grid_winner.json →
ver-11-config.json → build → submit).

16 thay đổi trên ver-11/cell-monolith.py (mỗi thay đổi must_count/replace_once):
  1. EXPERIMENT_TAG v11 → v12 (2 chỗ: const + guard report)
  2. env block [ver12] (Phase H) — SAU CÙNG mọi block env legacy (sau
     BIOHUB_DIAGNOSTIC_ARM, trước guard) — REVIEW-2 FIX: chèn sau print [ver11]
     khiến block [ver8] reparent (chạy sau) GHI ĐÈ REPARENT_EDGE_PROB 0.4→0.25 —
     trục 1b bị vô hiệu âm thầm; giờ block v12 luôn là assignment CUỐI CÙNG nên
     config thắng mọi block cũ + builder assert final-env-value từng key
  3. hằng số [ver12] (orphan/readmit/gapfill/lowdet) — sau REPARENT_GLOBAL_FRAC_CAP
  4. 4 hàm READMIT/GAPFILL + _gapfill_bump — trước add_safe_divisions_postlink
  5. orphan-adoption trong gate divergence (add_safe_divisions_postlink)
  6. proposals tuple mang cờ mồ côi (7-tuple: ..., p_div, orphan)
  7. _divnet_rerank_proposals giữ tail *prop[6:]
  8. floor p_div riêng cho orphan trong vòng chọn
  9. counter safe_division_orphan_adopted khi thêm cạnh mồ côi
 10. READMIT call-site (trong block motion-relink, đúng vị trí thtennant: sau relink đầu)
 11. GAPFILL call-site (sau recover_strict_gap2) + print census
 12. stats dict init: keys mới (orphan/readmit/gapfill)
 13. LOWDET dump stage — 3 patch script predict (chèn sau EDGE_TTA patch print)
 14. guard _EXPECTED_NUMERIC: SEF_TTA_WEIGHT + DC_SAFE_DIV theo config
 15. guard report: status phase_h_v12_portfolio + phase_h dict + divnet_mode v12
 16. final print progression + ver-12

Lưu ý B-1 kế thừa: guard _EXPECTED_NUMERIC ver-11 chốt 9 hằng số — v12 CẬP NHẬT đúng
2 hằng số theo config (SEF_TTA/DC); 7 hằng còn lại phải NGUYÊN VẸN (verify cuối build).

Kiểm thử tĩnh (L2 smoke trước khi đụng GPU): must_count mọi anchor + AST parse +
py_compile + mấu tích hợp v12 + guard nguyên vẹn. CPU-only 0 GPU — build local.
"""
import ast
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VER11 = ROOT.parent / 'ver-11' / 'cell-monolith.py'
OUT = ROOT / 'cell-monolith.py'
CONFIG = ROOT / 'ver-12-config.json'


def must_count(text: str, needle: str, want: int, what: str) -> None:
    got = text.count(needle)
    if got != want:
        sys.exit(f'[build12] THẤT BẠI ở {what}: {needle[:60]!r} xuất hiện {got} lần (cần {want})')


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
    tag = f'secondary_deepcenter_tta_0947_reparent_hoct_v12_{label}'

    rep_ep = float(cfg.get('reparent_edge_prob', 0.40))
    rep_pdiv = float(cfg.get('reparent_min_pdiv', 0.50))
    rep_far = float(cfg.get('reparent_current_far_um', 7.5))
    rep_div = float(cfg.get('reparent_diverge_um', 2.25))
    div_parent = float(cfg.get('div_parent_max_um', 10.5))
    sd_diverge = cfg.get('safe_div_diverge_um')
    orphan = int(cfg.get('orphan_adopt', 1))
    orphan_pdiv = float(cfg.get('orphan_min_pdiv', 0.50))
    lowdet = float(cfg.get('lowdet_threshold', 0.5))
    radmit_r = float(cfg.get('readmit_radius_um', 4.0))
    radmit_s = float(cfg.get('readmit_min_score', 0.965))
    gf_gap = int(cfg.get('gapfill_max_gap', 3))
    gf_min = float(cfg.get('gapfill_min_score', 0.5))
    gf_step = float(cfg.get('gapfill_step_um', 5.0))
    gf_prad = float(cfg.get('gapfill_peak_radius_um', 3.5))
    gf_excl = float(cfg.get('gapfill_exclude_um', 2.0))
    gf_syn = int(cfg.get('gapfill_allow_synthetic', 0))
    gf_ctx = int(cfg.get('gapfill_context', 1))
    gf_frac = float(cfg.get('gapfill_max_added_frac', 0.03))
    sef_w = float(cfg.get('sef_tta_weight', 0.75))
    dc_thr = float(cfg.get('dc_safe_div_threshold', 0.20))
    # [23/9] VALIDATOR_ENABLE=0 — andnyu 0948-reproduction receipt (21m47s T4x2 end-to-end)
    # + thtennant family precedent. Trong monolith: PP_CANDIDATES = {} (rỗng) nên ppsweep
    # không bao giờ chọn được candidate nào (selected_config rỗng → KHÔNG rewrite
    # submission); write_test_submission("base") gọi ở dòng 4304/4339 ĐỘC LẬP với
    # validator → tắt validator = submission byte-identical, tiết kiệm ~90 phút GPU/run.
    val_en = int(cfg.get('validator_enable', 1))

    text = VER11.read_text()

    # ---- 0. tiền điều kiện: đúng là monolith ver-11 đã build ----
    must_count(text, "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v11_mn_p85_div05'", 1, 'EXPERIMENT_TAG v11')
    must_count(text, "os.environ['BIOHUB_HOCT_VETO'] = '1'", 1, 'veto mode 1')
    must_count(text, 'def add_safe_divisions_postlink', 1, 'add_safe_divisions')
    must_count(text, 'def add_reparent_divisions_postlink', 1, 'add_reparent_divisions')
    must_count(text, "'status': 'phase_g_v11_mutualnn_pdiv'", 1, 'guard status v11')

    # ---- 1. EXPERIMENT_TAG (const) ----
    text = replace_once(
        text,
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v11_mn_p85_div05'",
        f"EXPERIMENT_TAG = '{tag}'",
        'EXPERIMENT_TAG v12',
    )

    # ---- 2. env block [ver12] (Phase H) — SAU CÙNG mọi block env legacy ----
    # REVIEW-2 FIX (22/9): trước đây chèn sau print [ver11] → block [ver8] reparent
    # (dòng sau đó) ghi đè REPARENT_EDGE_PROB 0.4→0.25 — trục 1b tắt âm thầm. Chèn
    # sau env legacy CUỐI CÙNG (BIOHUB_DIAGNOSTIC_ARM) để mọi key v12 là assignment
    # cuối; guard (chạy sau đó) đọc đúng giá trị config; assert cuối build khóa lại.
    diverge_line = f"os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '{sd_diverge}'\n" if sd_diverge is not None else ''
    diverge_print = (" + ' | diverge=" + fmt(sd_diverge) + "'") if sd_diverge is not None else ''
    env_new = (
        '\n'
        "# [ver12] Phase H — PORTFOLIO 4 TRỤC (V12-RESEARCH.md §4, REVIEW-1 §7): mỗi trục\n"
        "# env-gated nên v12-lab A/B được từng cái (F3: stack tối đa 2 trục mới/lượt submit).\n"
        "# REVIEW-2: block này CHẠY SAU CÙNG mọi block env legacy (Phase D/E/F/G) để giá trị\n"
        "# config v12 thắng tuyệt đối — không bị [ver8] reparent hay block nào ghi đè.\n"
        f"os.environ['BIOHUB_REPARENT_EDGE_PROB'] = '{rep_ep}'\n"
        f"os.environ['BIOHUB_REPARENT_MIN_PDIV'] = '{rep_pdiv}'\n"
        f"os.environ['BIOHUB_REPARENT_CURRENT_FAR_UM'] = '{rep_far}'\n"
        f"os.environ['BIOHUB_REPARENT_DIVERGE_UM'] = '{rep_div}'\n"
        f"os.environ['BIOHUB_DIV_PARENT_MAX_UM'] = '{div_parent}'\n"
        f"{diverge_line}"
        f"os.environ['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '{orphan}'\n"
        f"os.environ['BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV'] = '{orphan_pdiv}'\n"
        f"os.environ['BIOHUB_LOWDET_THRESHOLD'] = '{lowdet}'\n"
        "os.environ['BIOHUB_LOWDET_DIR'] = '/kaggle/working/lowdet'\n"
        f"os.environ['BIOHUB_READMIT_RADIUS_UM'] = '{radmit_r}'\n"
        f"os.environ['BIOHUB_READMIT_MIN_SCORE'] = '{radmit_s}'\n"
        f"os.environ['BIOHUB_GAPFILL_MAX_GAP'] = '{gf_gap}'\n"
        f"os.environ['BIOHUB_GAPFILL_MIN_SCORE'] = '{gf_min}'\n"
        f"os.environ['BIOHUB_GAPFILL_STEP_UM'] = '{gf_step}'\n"
        f"os.environ['BIOHUB_GAPFILL_PEAK_RADIUS_UM'] = '{gf_prad}'\n"
        f"os.environ['BIOHUB_GAPFILL_EXCLUDE_UM'] = '{gf_excl}'\n"
        f"os.environ['BIOHUB_GAPFILL_ALLOW_SYNTHETIC'] = '{gf_syn}'\n"
        f"os.environ['BIOHUB_GAPFILL_CONTEXT'] = '{gf_ctx}'\n"
        f"os.environ['BIOHUB_GAPFILL_MAX_ADDED_FRAC'] = '{gf_frac}'\n"
        f"os.environ['BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT'] = '{sef_w}'\n"
        f"os.environ['BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD'] = '{dc_thr}'\n"
        f"os.environ['BIOHUB_VALIDATOR_ENABLE'] = '{val_en}'\n"
        "print('[ver12] Phase H portfolio: reparent EP=" + fmt(rep_ep) + " | orphan-adopt=" + fmt(bool(orphan)) + " floor=" + fmt(orphan_pdiv) + " | READMIT r=" + fmt(radmit_r) + "um s>=" + fmt(radmit_s) + " | GAPFILL gap<=" + fmt(gf_gap) + " | lowdet>=" + fmt(lowdet) + " | SEF_TTA w=" + fmt(sef_w) + " | DC=" + fmt(dc_thr) + " | validator=" + ('ON' if val_en else 'OFF (ppsweep no-op, save ~90min GPU)') + "'" + diverge_print + ")"
    )
    anchor2 = "os.environ['BIOHUB_DIAGNOSTIC_ARM'] = 'harmonic_association_production'"
    text = replace_once(text, anchor2, anchor2 + '\n' + env_new, 'env block [ver12] sau cùng')

    # ---- 3. hằng số [ver12] ----
    anchor3 = "REPARENT_GLOBAL_FRAC_CAP = float(os.environ.get('BIOHUB_REPARENT_GLOBAL_FRAC_CAP', '0.00375'))"
    consts_new = anchor3 + "\n" + (
        "# [ver12] Phase H hằng số — orphan-adoption (F1) + node-recall (READMIT/GAPFILL).\n"
        "# SAFE_DIV_ORPHAN_ADOPT: mồ côi đúng-1-cha được miễn gate divergence (tấm màn\n"
        "# chặn: mồ côi cuối track KHÔNG BAO GIỜ có successor t+2 — 05db ver11 bị chặn 1894).\n"
        "SAFE_DIV_ORPHAN_ADOPT = os.environ.get('BIOHUB_SAFE_DIV_ORPHAN_ADOPT', '0') != '0'\n"
        "SAFE_DIV_ORPHAN_MIN_PDIV = float(os.environ.get('BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV', '0.5'))\n"
        "# [ver12] READMIT (thtennant batch-B): đòi pool lowdet từ dump stage predict.\n"
        "READMIT_RADIUS_UM = float(os.environ.get('BIOHUB_READMIT_RADIUS_UM', '0'))\n"
        "READMIT_MIN_SCORE = float(os.environ.get('BIOHUB_READMIT_MIN_SCORE', '0.965'))\n"
        "# [ver12] GAPFILL (thtennant batch-B): bắc cầu bằng peak thật, budget 3% node.\n"
        "GAPFILL_MAX_GAP = int(os.environ.get('BIOHUB_GAPFILL_MAX_GAP', '0'))\n"
        "GAPFILL_MIN_SCORE = float(os.environ.get('BIOHUB_GAPFILL_MIN_SCORE', '0.5'))\n"
        "GAPFILL_STEP_UM = float(os.environ.get('BIOHUB_GAPFILL_STEP_UM', '5.0'))\n"
        "GAPFILL_PEAK_RADIUS_UM = float(os.environ.get('BIOHUB_GAPFILL_PEAK_RADIUS_UM', '3.5'))\n"
        "GAPFILL_EXCLUDE_UM = float(os.environ.get('BIOHUB_GAPFILL_EXCLUDE_UM', '2.0'))\n"
        "GAPFILL_ALLOW_SYNTHETIC = int(os.environ.get('BIOHUB_GAPFILL_ALLOW_SYNTHETIC', '0'))\n"
        "GAPFILL_CONTEXT = os.environ.get('BIOHUB_GAPFILL_CONTEXT', '1') != '0'\n"
        "GAPFILL_MAX_ADDED_FRAC = float(os.environ.get('BIOHUB_GAPFILL_MAX_ADDED_FRAC', '0.03'))\n"
        "LOWDET_DIR = os.environ.get('BIOHUB_LOWDET_DIR', '').strip()"
    )
    text = replace_once(text, anchor3, consts_new, 'hằng số [ver12]')

    # ---- 4. 5 hàm READMIT/GAPFILL — trước add_safe_divisions_postlink ----
    funcs = '''# [ver12] ==== NODE-RECALL: READMIT + GAPFILL (port thtennant batch-B — V12-RESEARCH §3.1-3.2) ====
# Pool: lowdet dump từ [ver12] patch predict script (peaks sub-threshold trên logits ĐÃ
# blend dual-seed — cùng nguồn với detection được admit). READMIT: tái nhập detection mạnh
# (>= READMIT_MIN_SCORE) bị ILP vứt trong READMIT_RADIUS_UM quanh track end/start — receipt
# hidden +1.014 node/+1.002 cạnh (hiệu ứng đơn lẻ lớn nhất batch B). GAPFILL: bắc cầu gap
# <= GAPFILL_MAX_GAP frame bằng peak THẬT (0 synthetic mặc định) — receipt +167/+240.
# Cả hai non-fatal khi thiếu dump (resume/hidden không có pool → idle, không đổi đồ thị).
def _gapfill_bump(stats: dict[str, int], key: str, n: int = 1) -> None:
    stats[key] = int(stats.get(key, 0)) + n


def load_low_detections(nodes_by_id: dict[int, dict[str, object]], dataset: str | None, stats: dict[str, int]) -> dict[int, dict[str, np.ndarray]] | None:
    # Pool per-frame các peak sub-threshold từ dump lowdet của prediction stage.
    # Peak < GAPFILL_MIN_SCORE và peak trong GAPFILL_EXCLUDE_UM quanh node cùng frame bị
    # drop (peak của chính node set cũ nằm trong đó). None khi dump thiếu/không đọc được.
    if (GAPFILL_MAX_GAP < 1 and READMIT_RADIUS_UM <= 0) or (not LOWDET_DIR) or (not dataset):
        return None
    cache_path = Path(LOWDET_DIR) / f'{dataset}.npz'
    if not cache_path.exists():
        print(f'  [{dataset}] no low-detection dump at {cache_path}; READMIT/GAPFILL idle')
        return None
    try:
        with np.load(cache_path) as cz:
            if 'low_coords' not in cz.files:
                print(f'  [{dataset}] dump has no low_coords; READMIT/GAPFILL idle')
                return None
            low = np.asarray(cz['low_coords'], dtype=np.float64).reshape(-1, 4)
            score = np.asarray(cz['low_score'], dtype=np.float64).reshape(-1)
    except Exception as exc:
        print(f'  [{dataset}] low-detection dump unreadable ({type(exc).__name__}: {exc}); READMIT/GAPFILL idle')
        return None
    return build_low_detection_pool(nodes_by_id, low, score, stats, dataset)


def build_low_detection_pool(nodes_by_id: dict[int, dict[str, object]], low: np.ndarray, score: np.ndarray, stats: dict[str, int], dataset: str | None = None) -> dict[int, dict[str, np.ndarray]]:
    keep = score >= GAPFILL_MIN_SCORE
    low, score = low[keep], score[keep]
    scale = np.array(VOXEL_SCALE_UM, dtype=np.float64)
    node_um_by_t: dict[int, list] = {}
    for node in nodes_by_id.values():
        node_um_by_t.setdefault(int(node['t']), []).append(np.array(node_point(node), dtype=np.float64) * scale)
    pool: dict[int, dict[str, np.ndarray]] = {}
    excluded = 0
    for t in (np.unique(low[:, 0]).astype(int).tolist() if len(low) else []):
        sel = low[:, 0] == t
        vox = low[sel, 1:]
        um = vox * scale
        sc = score[sel]
        existing = node_um_by_t.get(t)
        if existing:
            d, _ = cKDTree(np.stack(existing)).query(um, k=1)
            free = d > GAPFILL_EXCLUDE_UM
            excluded += int((~free).sum())
            vox, um, sc = vox[free], um[free], sc[free]
        if len(vox):
            pool[t] = {'vox': vox, 'um': um, 'score': sc}
    n_free = int(sum((len(p['vox']) for p in pool.values())))
    _gapfill_bump(stats, 'gapfill_pool_peaks', n_free)
    _gapfill_bump(stats, 'gapfill_pool_excluded', excluded)
    if dataset is not None:
        print(f'  [{dataset}] low-detection pool: {len(low)} peaks >= {GAPFILL_MIN_SCORE}, {excluded} on existing nodes, {n_free} free')
    return pool


def readmit_discarded_detections(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]], stats: dict[str, int], dataset: str | None = None) -> dict[int, dict[str, object]]:
    # [ver12] READMIT: thêm detector peak mạnh bị ILP vứt khi nó nằm trong
    # READMIT_RADIUS_UM quanh track end/start. node t không có cạnh ra → anchor t+1;
    # node t không có cạnh vào → anchor t-1 (cạnh lấy từ motion-relink đầu — đúng vị
    # trí ngữ nghĩa 'đang hở'). Node mới re-link lại bởi caller; nếu vẫn isolated thì
    # bị prune như thường (non-fatal toàn bộ).
    if READMIT_RADIUS_UM <= 0:
        return nodes_by_id
    try:
        pool = load_low_detections(nodes_by_id, dataset, stats)
        if not pool:
            return nodes_by_id
        has_out = {int(e['source_id']) for e in edges}
        has_in = {int(e['target_id']) for e in edges}
        scale = np.array(VOXEL_SCALE_UM, dtype=np.float64)
        anchors: dict[int, list] = {}
        for nid, node in nodes_by_id.items():
            t = int(node['t'])
            um = np.array(node_point(node), dtype=np.float64) * scale
            if nid not in has_out:
                anchors.setdefault(t + 1, []).append(um)
            if nid not in has_in:
                anchors.setdefault(t - 1, []).append(um)
        next_id = _next_node_id(nodes_by_id)
        added = 0
        for t in sorted(pool):
            near = anchors.get(int(t))
            if not near:
                continue
            peaks = pool[t]
            d, _ = cKDTree(np.stack(near)).query(peaks['um'], k=1)
            keep = (d <= READMIT_RADIUS_UM) & (peaks['score'] >= READMIT_MIN_SCORE)
            for vox in peaks['vox'][keep]:
                nodes_by_id[next_id] = {'node_id': next_id, 't': int(t), 'z': float(vox[0]), 'y': float(vox[1]), 'x': float(vox[2]), 'readmitted': 1}
                next_id += 1
                added += 1
        _gapfill_bump(stats, 'readmitted_nodes', added)
        if dataset is not None:
            print(f'  [{dataset}] readmitted {added} discarded detections within {READMIT_RADIUS_UM} um of an open end/start')
    except Exception as exc:
        print(f'  [{dataset}] readmit skipped (non-fatal): {type(exc).__name__}: {exc}')
    return nodes_by_id


def fill_gaps_from_low_detections(nodes_by_id: dict[int, dict[str, object]], edges: list[dict[str, object]], stats: dict[str, int], dataset: str | None = None, frame_cache: dict[int, np.ndarray] | None = None) -> tuple[dict[int, dict[str, object]], list[dict[str, object]]]:
    # [ver12] GAPFILL: bắc cầu track end (t) → track start (t+g+1) qua sub-threshold
    # peaks. Chạy SAU single-frame closer + gap2 trên phần còn hở. Mỗi cặp: span trong
    # GAPFILL_STEP_UM/frame + context-cos (đảo chiều cấm) + đường thẳng end→start được
    # sample từng frame thiếu, lấy peak thật gần nhất trong GAPFILL_PEAK_RADIUS_UM;
    # cần peak ở MỌI frame trừ tối đa GAPFILL_ALLOW_SYNTHETIC frame (nội suy + refine).
    # Cặp của một (t, g) gán bằng Hungarian trên span/(g+1) + lệch peak trung bình,
    # gap ngắn trước. Node thêm cap GAPFILL_MAX_ADDED_FRAC tập node.
    if GAPFILL_MAX_GAP < 1 or (not edges) or (not nodes_by_id):
        return nodes_by_id, edges
    pool = load_low_detections(nodes_by_id, dataset, stats)
    if not pool:
        return nodes_by_id, edges
    scale = np.array(VOXEL_SCALE_UM, dtype=np.float64)
    outgoing: dict[int, list[int]] = {}
    incoming: dict[int, list[int]] = {}
    for edge in edges:
        outgoing.setdefault(int(edge['source_id']), []).append(int(edge['target_id']))
        incoming.setdefault(int(edge['target_id']), []).append(int(edge['source_id']))
    pos = {nid: np.array(node_point(node), dtype=np.float64) * scale for nid, node in nodes_by_id.items()}
    ends_by_t: dict[int, list[int]] = {}
    starts_by_t: dict[int, list[int]] = {}
    for nid, node in nodes_by_id.items():
        t = int(node['t'])
        if nid not in outgoing:
            ends_by_t.setdefault(t, []).append(nid)
        if nid not in incoming:
            starts_by_t.setdefault(t, []).append(nid)
    trees = {t: cKDTree(p['um']) for t, p in pool.items()}
    used_peak = {t: np.zeros(len(p['um']), dtype=bool) for t, p in pool.items()}
    budget = int(round(len(nodes_by_id) * GAPFILL_MAX_ADDED_FRAC))
    frame_cache = frame_cache if frame_cache is not None else {}
    next_id = _next_node_id(nodes_by_id)
    used_end: set[int] = set()
    used_start: set[int] = set()
    added_nodes = 0
    new_edges: list[dict[str, object]] = []

    def context_ok(end_id: int, start_id: int) -> bool:
        if not GAPFILL_CONTEXT:
            return True
        step = pos[start_id] - pos[end_id]
        sn = float(np.linalg.norm(step))
        if sn <= 0.01:
            return True
        prev = incoming.get(end_id)
        if prev:
            other = pos[end_id] - pos[prev[0]]
            on = float(np.linalg.norm(other))
            if on > 0.01 and float(np.dot(other, step)) / (on * sn) <= -0.25:
                return False
        nxt = outgoing.get(start_id)
        if nxt:
            other = pos[nxt[0]] - pos[start_id]
            on = float(np.linalg.norm(other))
            if on > 0.01 and float(np.dot(other, step)) / (on * sn) <= -0.25:
                return False
        return True

    def chain_for(end_id: int, start_id: int, g: int):
        span = pos[start_id] - pos[end_id]
        t0 = int(nodes_by_id[end_id]['t'])
        items, dev, synthetic = [], [], 0
        for k in range(1, g + 1):
            q = pos[end_id] + span * (k / (g + 1))
            tk = t0 + k
            tree = trees.get(tk)
            j = None
            if tree is not None:
                cand = [c for c in tree.query_ball_point(q, r=GAPFILL_PEAK_RADIUS_UM) if not used_peak[tk][c]]
                if cand:
                    dists = np.linalg.norm(pool[tk]['um'][cand] - q, axis=1)
                    best = int(np.argmin(dists))
                    j = cand[best]
                    dev.append(float(dists[best]))
            if j is None:
                synthetic += 1
                if synthetic > GAPFILL_ALLOW_SYNTHETIC:
                    return None
                dev.append(GAPFILL_PEAK_RADIUS_UM)
            items.append((tk, j, q))
        cost = float(np.linalg.norm(span)) / (g + 1) + (sum(dev) / len(dev) if dev else 0.0)
        return cost, items

    for g in range(1, GAPFILL_MAX_GAP + 1):
        gate = GAPFILL_STEP_UM * (g + 1)
        for t in sorted(ends_by_t):
            if added_nodes + g > budget:
                _gapfill_bump(stats, 'gapfill_budget_hit')
                break
            ends = [e for e in ends_by_t[t] if e not in used_end]
            starts = [s for s in starts_by_t.get(t + g + 1, []) if s not in used_start]
            if not ends or not starts:
                continue
            end_pts = np.stack([pos[e] for e in ends])
            start_pts = np.stack([pos[s] for s in starts])
            start_tree = cKDTree(start_pts)
            cost = np.full((len(ends), len(starts)), np.inf)
            n_chains = 0
            for i, js in enumerate(start_tree.query_ball_point(end_pts, r=gate)):
                for j in js:
                    if not context_ok(ends[i], starts[j]):
                        continue
                    chain = chain_for(ends[i], starts[j], g)
                    if chain is None:
                        continue
                    cost[i, j] = chain[0]
                    n_chains += 1
            if n_chains == 0:
                continue
            _gapfill_bump(stats, 'gapfill_candidates', n_chains)
            finite = np.isfinite(cost)
            big = float(np.max(cost[finite])) * 1000.0 + 1.0
            row_ind, col_ind = linear_sum_assignment(np.where(finite, cost, big))
            picks = sorted((float(cost[i, j]), int(i), int(j)) for i, j in zip(row_ind, col_ind) if finite[i, j])
            for _, i, j in picks:
                if added_nodes + g > budget:
                    _gapfill_bump(stats, 'gapfill_budget_hit')
                    break
                chain = chain_for(ends[i], starts[j], g)
                if chain is None:
                    continue
                prev = ends[i]
                for tk, pk, q in chain[1]:
                    nid = next_id
                    next_id += 1
                    if pk is not None:
                        vox = pool[tk]['vox'][pk]
                        used_peak[tk][pk] = True
                        node = {'node_id': nid, 't': tk, 'z': float(vox[0]), 'y': float(vox[1]), 'x': float(vox[2]), 'gapfill_peak': 1}
                        _gapfill_bump(stats, 'gapfill_peak_nodes')
                    else:
                        p = q / scale
                        refined = refine_synthetic_midpoint(dataset, tk, (float(p[0]), float(p[1]), float(p[2])), frame_cache, stats)
                        node = {'node_id': nid, 't': tk, 'z': float(refined[0]), 'y': float(refined[1]), 'x': float(refined[2]), 'gap_synthetic': 1}
                        _gapfill_bump(stats, 'gapfill_synthetic_nodes')
                    nodes_by_id[nid] = node
                    new_edges.append({'source_id': prev, 'target_id': nid, 'edge_prob': None, 'distance_um': edge_distance_um(nodes_by_id[prev], node), 'gap_filled': 1})
                    prev = nid
                    added_nodes += 1
                new_edges.append({'source_id': prev, 'target_id': starts[j], 'edge_prob': None, 'distance_um': edge_distance_um(nodes_by_id[prev], nodes_by_id[starts[j]]), 'gap_filled': 1})
                used_end.add(ends[i])
                used_start.add(starts[j])
                _gapfill_bump(stats, f'gapfill_pairs_g{g}')
    _gapfill_bump(stats, 'gapfill_added_nodes', added_nodes)
    _gapfill_bump(stats, 'gapfill_added_edges', len(new_edges))
    if dataset is not None and new_edges:
        print(f'  [{dataset}] gap filler: +{added_nodes} nodes, +{len(new_edges)} edges')
    return nodes_by_id, [*edges, *new_edges]


# Add conservative division edges after ordinary temporal linking is complete'''
    anchor4 = '# Add conservative division edges after ordinary temporal linking is complete'
    text = replace_once(text, anchor4, funcs, 'hàm READMIT/GAPFILL')

    # ---- 5. orphan-adoption trong gate divergence ----
    old_div = """                if SAFE_DIV_REQUIRE_DIVERGENCE:
                    c1_succ = out_by_source.get(existing_child_id, [])
                    q_succ = out_by_source.get(candidate_id, [])

                    if len(c1_succ) != 1 or len(q_succ) != 1:
                        stats['safe_division_divergence_rejected'] += 1
                        continue
                    c1_grandchild = nodes_by_id.get(int(c1_succ[0]['target_id']))
                    q_grandchild = nodes_by_id.get(int(q_succ[0]['target_id']))

                    if c1_grandchild is None or q_grandchild is None or int(c1_grandchild['t']) != t + 2 or (int(q_grandchild['t']) != t + 2):
                        stats['safe_division_divergence_rejected'] += 1
                        continue
                    grandchild_dist = edge_distance_um(c1_grandchild, q_grandchild)

                    if grandchild_dist - sister_dist < SAFE_DIV_DIVERGE_UM:
                        stats['safe_division_divergence_rejected'] += 1
                        continue"""
    new_div = """                _v12_orphan = False
                if SAFE_DIV_REQUIRE_DIVERGENCE:
                    c1_succ = out_by_source.get(existing_child_id, [])
                    q_succ = out_by_source.get(candidate_id, [])

                    # [ver12-F1] orphan-adoption exception: mồ côi cuối track (KHÔNG có
                    # successor t+2) không bao giờ qua được gate divergence theo thiết kế
                    # cũ (05db ver11: divergence_rejected 1894 — tấm màn chặn nhận nuôi).
                    # Bật exception: miễn phép đo divergence cho mồ côi khi con hiện tại
                    # đúng 1 successor; tin floor p_div riêng (SAFE_DIV_ORPHAN_MIN_PDIV,
                    # chọn ở vòng đề xuất) + geometry (parent/sister đã qua ở trên) +
                    # DC-veto (sau geometric_candidates). Đếm riêng để receipt.
                    if len(q_succ) == 0 and len(c1_succ) == 1 and SAFE_DIV_ORPHAN_ADOPT:
                        stats['safe_division_orphan_exempted'] += 1
                        _v12_orphan = True
                    elif len(c1_succ) != 1 or len(q_succ) != 1:
                        stats['safe_division_divergence_rejected'] += 1
                        continue

                    if not _v12_orphan:
                        c1_grandchild = nodes_by_id.get(int(c1_succ[0]['target_id']))
                        q_grandchild = nodes_by_id.get(int(q_succ[0]['target_id']))

                        if c1_grandchild is None or q_grandchild is None or int(c1_grandchild['t']) != t + 2 or (int(q_grandchild['t']) != t + 2):
                            stats['safe_division_divergence_rejected'] += 1
                            continue
                        grandchild_dist = edge_distance_um(c1_grandchild, q_grandchild)

                        if grandchild_dist - sister_dist < SAFE_DIV_DIVERGE_UM:
                            stats['safe_division_divergence_rejected'] += 1
                            continue"""
    text = replace_once(text, old_div, new_div, 'orphan-adoption divergence gate')

    # ---- 6. proposals tuple mang cờ mồ côi ----
    old_app = """                score = parent_dist + 0.15 * sister_dist
                proposals.append((score, source_id, candidate_id, parent_dist, sister_dist))"""
    new_app = """                score = parent_dist + 0.15 * sister_dist
                # [ver12] tuple 7-phần: (score, src, cand, p_dist, s_dist, p_div=None, orphan)
                # — p_div luôn ở index 5 (DivNet rerank thay None bằng xác suất), cờ mồ côi
                # ở index 6 để vòng chọn dùng floor riêng.
                proposals.append((score, source_id, candidate_id, parent_dist, sister_dist, None, _v12_orphan))"""
    text = replace_once(text, old_app, new_app, 'proposals tuple orphan flag')

    # ---- 7. _divnet_rerank_proposals giữ tail ----
    old_rerank = "        out.append((parent_dist + 0.15 * sister_dist - w * float(p_div), source_id, candidate_id, parent_dist, sister_dist, float(p_div)))"
    new_rerank = "        out.append((parent_dist + 0.15 * sister_dist - w * float(p_div), source_id, candidate_id, parent_dist, sister_dist, float(p_div), *prop[6:]))"
    text = replace_once(text, old_rerank, new_rerank, 'divnet rerank tail')

    # ---- 8. floor p_div riêng cho orphan trong vòng chọn ----
    old_floor = """        for _score, source_id, candidate_id, parent_dist, _sister, *rest in proposals:
            p_div = rest[0] if rest else None
            # [ver11] floor P(division) — chỉ áp khi SAFE_DIV_MIN_PDIV > 0; không có
            # bằng chứng DivNet (p_div None) thì TỪ CHỐI (an toàn: không thêm division mù).
            if SAFE_DIV_MIN_PDIV > 0.0 and (p_div is None or float(p_div) < SAFE_DIV_MIN_PDIV):
                stats['safe_division_min_pdiv_rejected'] = stats.get('safe_division_min_pdiv_rejected', 0) + 1
                continue"""
    new_floor = """        for _score, source_id, candidate_id, parent_dist, _sister, *rest in proposals:
            p_div = rest[0] if rest else None
            # [ver12] cờ mồ côi đi sau p_div trong tuple (rerank giữ tail *prop[6:]).
            _v12_orphan = bool(rest[1]) if len(rest) > 1 else False
            # [ver11] floor P(division) — chỉ áp khi floor > 0; không có bằng chứng DivNet
            # (p_div None) thì TỪ CHỐI (an toàn: không thêm division mù).
            # [ver12-F1] đề xuất mồ côi (orphan-exempted) dùng floor riêng.
            _v12_floor = SAFE_DIV_ORPHAN_MIN_PDIV if _v12_orphan else SAFE_DIV_MIN_PDIV

            if _v12_floor > 0.0 and (p_div is None or float(p_div) < _v12_floor):
                stats['safe_division_min_pdiv_rejected'] = stats.get('safe_division_min_pdiv_rejected', 0) + 1
                continue"""
    text = replace_once(text, old_floor, new_floor, 'floor orphan riêng')

    # ---- 9. counter orphan_adopted khi thêm cạnh ----
    old_add = """            candidate = nodes_by_id[candidate_id]
            added.append({'source_id': source_id, 'target_id': candidate_id, 'edge_prob': None, 'distance_um': parent_dist, 'safe_division': 1})"""
    new_add = """            candidate = nodes_by_id[candidate_id]
            added.append({'source_id': source_id, 'target_id': candidate_id, 'edge_prob': None, 'distance_um': parent_dist, 'safe_division': 1})

            if _v12_orphan:
                stats['safe_division_orphan_adopted'] += 1"""
    text = replace_once(text, old_add, new_add, 'counter orphan adopted')

    # ---- 10. READMIT call-site (trong motion-relink, đúng vị trí thtennant) ----
    old_relink = """        motion_edges = motion_relink_edges(nodes_by_id, stats, learned_edge_probs, tight_gate_um=_pp_tight_gate)

        if motion_edges:"""
    new_relink = """        motion_edges = motion_relink_edges(nodes_by_id, stats, learned_edge_probs, tight_gate_um=_pp_tight_gate)
        # [ver12] READMIT — tái nhập detection mạnh bị ILP vứt quanh track end/start.
        # Anchor = cạnh motion-relink ĐẦU (trước gap-close/safe-div — đúng vị trí ngữ
        # nghĩa 'đang hở' của thtennant; đối chiếu ANALYSIS §4 khi port chuỗi có
        # HOCT/reparent/retention-guard). Sau khi thêm node: re-link trên tập mở rộng.
        if motion_edges and READMIT_RADIUS_UM > 0:
            _readmit_before = len(nodes_by_id)
            nodes_by_id = readmit_discarded_detections(nodes_by_id, motion_edges, stats, dataset=dataset)

            if len(nodes_by_id) > _readmit_before:
                motion_edges = motion_relink_edges(nodes_by_id, stats, learned_edge_probs, tight_gate_um=_pp_tight_gate) or motion_edges

        if motion_edges:"""
    text = replace_once(text, old_relink, new_relink, 'READMIT call-site')

    # ---- 11. GAPFILL call-site (sau gap2) + print census ----
    old_gap = """    nodes_by_id, edges = recover_strict_gap2(nodes_by_id, edges, stats, dataset = dataset)
    print(f'[{dataset}] after gap-closing (single-frame + gap2): {len(nodes_by_id)} nodes, {len(edges)} edges')"""
    new_gap = """    nodes_by_id, edges = recover_strict_gap2(nodes_by_id, edges, stats, dataset = dataset)
    # [ver12] GAPFILL — bắc cầu gap <= GAPFILL_MAX_GAP frame bằng peak THẬT từ pool
    # lowdet (mặc định 0 synthetic); chạy sau closer + gap2 trên phần còn hở — đúng
    # vị trí thtennant. Non-fatal khi thiếu dump.
    nodes_by_id, edges = fill_gaps_from_low_detections(nodes_by_id, edges, stats, dataset = dataset, frame_cache = repair_frame_cache)
    print(f'[{dataset}] after gap-closing (single-frame + gap2 + lowdet filler): {len(nodes_by_id)} nodes, {len(edges)} edges | readmitted = {stats.get('readmitted_nodes', 0)}, gapfill_nodes = {stats.get('gapfill_added_nodes', 0)}, gapfill_edges = {stats.get('gapfill_added_edges', 0)}')"""
    text = replace_once(text, old_gap, new_gap, 'GAPFILL call-site')

    # ---- 12. stats dict init: keys mới ----
    old_stats = "'reparent_pdiv_rejected': 0, 'deepcenter_reparent_checked': 0,"
    new_stats = "'reparent_pdiv_rejected': 0, 'safe_division_orphan_exempted': 0, 'safe_division_orphan_adopted': 0, 'readmitted_nodes': 0, 'gapfill_pool_peaks': 0, 'gapfill_pool_excluded': 0, 'gapfill_candidates': 0, 'gapfill_budget_hit': 0, 'gapfill_peak_nodes': 0, 'gapfill_synthetic_nodes': 0, 'gapfill_added_nodes': 0, 'gapfill_added_edges': 0, 'deepcenter_reparent_checked': 0,"
    text = replace_once(text, old_stats, new_stats, 'stats init keys v12')

    # ---- 13. LOWDET dump stage — 3 patch script predict (sau EDGE_TTA print) ----
    lowdet_block = '''
# [ver12] LOWDET dump stage — pool sub-threshold peaks cho READMIT/GAPFILL.
# V12-RESEARCH §7.3-F2: monolith ver-11 KHÔNG có stage dump low-detection; port
# dump-stage của thtennant batch-B (receipt +1.014 node/+1.002 cạnh hidden).
# 3 patch áp SAU các patch cũ (anchor từ script đã build xong — xác minh count):
#   (1) module globals _LOWDET_THRESHOLD/_LOWDET_DIR/_LOWDET
#   (2) frame-loop: dump peaks >= threshold trên logits ĐÃ blend dual-seed (cùng
#       nguồn với detection được admit — đúng ngữ nghĩa 'bị vứt bởi ILP/edge-filter')
#   (3) module-loop sau predict_video: save npz per-dataset (non-fatal khi thiếu)
# Shard subprocess nhận env qua {**os.environ} (block [ver12] chạy trước khi launch).
_ld_s = _ps.read_text()
_ld_globals_old = '    return tuple(kernel)\\n\\n\\ndef _detect_cells_pooled(\\n'
_ld_globals_new = (
    '    return tuple(kernel)\\n\\n\\n'
    '# [ver12] LOWDET dump stage globals (pool READMIT/GAPFILL) — port thtennant batch-B\\n'
    "_LOWDET_THRESHOLD = float(os.environ.get('BIOHUB_LOWDET_THRESHOLD', '0') or 0)\\n"
    "_LOWDET_DIR = os.environ.get('BIOHUB_LOWDET_DIR', '').strip()\\n"
    '_LOWDET: list = []\\n\\n\\n'
    'def _detect_cells_pooled(\\n'
)
_ld_globals_count = _ld_s.count(_ld_globals_old)

if _ld_globals_count != 1:
    raise RuntimeError(f'[ver12] LOWDET globals anchor expected one match, found {_ld_globals_count}')
_ld_s = _ld_s.replace(_ld_globals_old, _ld_globals_new, 1)
_ld_frame_old = (
    '        # --- Detect cells in each frame (dedup across windows) ---\\n'
    '        for f_idx, t in enumerate(frame_indices):\\n'
    '            if t not in seen_frames:\\n'
    '                arr = _detect_cells_pooled(\\n'
    '                    det_logits[f_idx][0], t, cfg.det_threshold, pool_k,\\n'
    '                )\\n'
    '                coord_offset[t] = (global_node_count, global_node_count + len(arr))\\n'
)
_ld_frame_new = (
    '        # --- Detect cells in each frame (dedup across windows) ---\\n'
    '        for f_idx, t in enumerate(frame_indices):\\n'
    '            if t not in seen_frames:\\n'
    '                arr = _detect_cells_pooled(\\n'
    '                    det_logits[f_idx][0], t, cfg.det_threshold, pool_k,\\n'
    '                )\\n'
    '\\n'
    '                # [ver12] LOWDET: dump peaks >= _LOWDET_THRESHOLD trên logits ĐÃ blend\\n'
    '                # dual-seed (cùng nguồn với detection được admit) — pool cho READMIT/GAPFILL.\\n'
    '                if _LOWDET_THRESHOLD > 0:\\n'
    '                    _low = _detect_cells_pooled(det_logits[f_idx][0], t, _LOWDET_THRESHOLD, pool_k)\\n'
    '\\n'
    '                    if len(_low):\\n'
    '                        _lg = det_logits[f_idx][0][0]\\n'
    '                        _lz = torch.as_tensor(_low[:, 1:].astype(np.int64), device=_lg.device)\\n'
    '                        _lsc = torch.sigmoid(_lg[_lz[:, 0], _lz[:, 1], _lz[:, 2]]).float().cpu().numpy()\\n'
    '                        _LOWDET.append((_low.astype(np.float32), _lsc.astype(np.float32)))\\n'
    '                coord_offset[t] = (global_node_count, global_node_count + len(arr))\\n'
)
_ld_frame_count = _ld_s.count(_ld_frame_old)

if _ld_frame_count != 1:
    raise RuntimeError(f'[ver12] LOWDET frame-loop anchor expected one match, found {_ld_frame_count}')
_ld_s = _ld_s.replace(_ld_frame_old, _ld_frame_new, 1)
_ld_save_old = '        graph = build_graph(coords, edges)\\n'
_ld_save_new = (
    '        # [ver12] LOWDET save — per-dataset npz (non-fatal; READMIT/GAPFILL idle khi thiếu)\\n'
    '        if _LOWDET_THRESHOLD > 0 and _LOWDET_DIR:\\n'
    '            _lowdet_dir = Path(_LOWDET_DIR)\\n'
    '            _lowdet_dir.mkdir(parents=True, exist_ok=True)\\n'
    '\\n'
    '            if _LOWDET:\\n'
    "                _lc = np.concatenate([e[0] for e in _LOWDET]).astype(np.float32)\\n"
    '                _lc[:, 1:] *= np.array(downsample, dtype=np.float32)\\n'
    '                _lc = _lc.astype(np.int16)\\n'
    "                _lsc = np.concatenate([e[1] for e in _LOWDET]).astype(np.float32)\\n"
    '            else:\\n'
    '                _lc = np.empty((0, 4), np.int16)\\n'
    '                _lsc = np.empty(0, np.float32)\\n'
    '            _LOWDET.clear()\\n'
    "            print(f'LOWDET {name}: {len(_lc)} peaks above {_LOWDET_THRESHOLD}', flush=True)\\n"
    "            np.savez_compressed(_lowdet_dir / f'{name}.npz', low_coords=_lc, low_score=_lsc)\\n"
    '        graph = build_graph(coords, edges)\\n'
)
_ld_save_count = _ld_s.count(_ld_save_old)

if _ld_save_count != 1:
    raise RuntimeError(f'[ver12] LOWDET save anchor expected one match, found {_ld_save_count}')
_ld_s = _ld_s.replace(_ld_save_old, _ld_save_new, 1)
compile(_ld_s, str(_ps), 'exec')
_ps.write_text(_ld_s)

if 'LOWDET' not in _ps.read_text():
    raise RuntimeError('[ver12] LOWDET dump stage did not persist')
print('[ver12] LOWDET dump stage installed (READMIT/GAPFILL pool from prediction subprocess)')
'''
    anchor13 = "print('Edge-feature TTA patch installed and enabled')"
    text = replace_once(text, anchor13, anchor13 + '\n' + lowdet_block, 'LOWDET dump stage block')

    # ---- 14. guard _EXPECTED_NUMERIC: SEF_TTA + DC theo config ----
    old_guard = "'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': 0.20, 'BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT': 0.15, 'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': 0.75}"
    new_guard = f"'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': {dc_thr}, 'BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT': 0.15, 'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': {sef_w}}}"
    text = replace_once(text, old_guard, new_guard, 'guard numeric v12')

    # ---- 15. guard report: status + phase_h + divnet_mode ----
    old_report = "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v11_mn_p85_div05', 'status': 'phase_g_v11_mutualnn_pdiv', 'phase_g': {'mutual_nn_required': False, 'safe_div_min_pdiv': 0.85, 'safe_div_diverge_um': 0.5, 'div_sister_max_um': 14.0, 'grid_label': 'mn_p85_div05', 'source': 'v11-lab v3 grid (kernel v4, 2026-09-20)'}, "
    new_report = (
        f"'experiment': '{tag}', 'status': 'phase_h_v12_portfolio', "
        "'phase_h': {'reparent_edge_prob': REPARENT_EDGE_PROB, 'reparent_min_pdiv': REPARENT_MIN_PDIV, 'reparent_current_far_um': REPARENT_CURRENT_FAR_UM, "
        "'orphan_adopt': SAFE_DIV_ORPHAN_ADOPT, 'orphan_min_pdiv': SAFE_DIV_ORPHAN_MIN_PDIV, "
        "'readmit_radius_um': READMIT_RADIUS_UM, 'readmit_min_score': READMIT_MIN_SCORE, "
        "'gapfill_max_gap': GAPFILL_MAX_GAP, 'gapfill_max_added_frac': GAPFILL_MAX_ADDED_FRAC, 'lowdet_threshold': float(os.environ.get('BIOHUB_LOWDET_THRESHOLD', '0')), "
        "'sef_tta_weight': float(os.environ.get('BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT', '0.75')), 'dc_safe_div_threshold': DEEPCENTER_SAFE_DIV_THRESHOLD, "
        f"'config_label': '{label}', 'source': 'V12-RESEARCH.md 4-truc portfolio (build-ver12-monolith.py, 2026-09-21)'}}, "
        "'phase_g': {'mutual_nn_required': False, 'safe_div_min_pdiv': 0.85, 'safe_div_diverge_um': 0.5, 'div_sister_max_um': 14.0, 'grid_label': 'mn_p85_div05', 'source': 'v11-lab v3 grid (kernel v4, 2026-09-20)'}, "
    )
    text = replace_once(text, old_report, new_report, 'guard report v12')

    gates_desc = f"reparent EP={rep_ep} · orphan-adopt={'ON' if orphan else 'OFF'} floor={orphan_pdiv} · READMIT r={radmit_r} · GAPFILL gap<={gf_gap} · SEF_TTA w={sef_w} · DC={dc_thr}"
    text = replace_once(
        text,
        "'divnet_mode': 'RANK-ONLY (v11 gates: mutual_nn=OFF · MIN_PDIV=0.85 · diverge=0.5 · div_sister=14.0)'",
        f"'divnet_mode': 'RANK-ONLY (v12 gates: {gates_desc})'",
        'divnet_mode audit v12',
    )

    # ---- 16. final print progression ----
    text = replace_once(
        text,
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-10 hoct-veto mode1 -> ver-11 mutual_nn-off + MIN_PDIV floor')",
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-10 hoct-veto mode1 -> ver-11 mutual_nn-off + MIN_PDIV floor -> ver-12 4-truc portfolio (reparent+orphan+readmit+gapfill)')",
        'final print v12',
    )

    # ---- 17. kiểm tra sau xây ----
    required = (
        f"EXPERIMENT_TAG = '{tag}'",
        'os.environ[\'BIOHUB_REPARENT_EDGE_PROB\']',
        'os.environ[\'BIOHUB_SAFE_DIV_ORPHAN_ADOPT\']',
        'os.environ[\'BIOHUB_READMIT_RADIUS_UM\']',
        'os.environ[\'BIOHUB_GAPFILL_MAX_GAP\']',
        'os.environ[\'BIOHUB_LOWDET_THRESHOLD\']',
        'os.environ[\'BIOHUB_LOWDET_DIR\']',
        'os.environ[\'BIOHUB_VALIDATOR_ENABLE\']',
        'SAFE_DIV_ORPHAN_ADOPT = os.environ.get(',
        'READMIT_RADIUS_UM = float(os.environ.get(',
        'GAPFILL_MAX_GAP = int(os.environ.get(',
        'LOWDET_DIR = os.environ.get(',
        'def readmit_discarded_detections',
        'def fill_gaps_from_low_detections',
        'def load_low_detections',
        'def build_low_detection_pool',
        'nodes_by_id = readmit_discarded_detections(nodes_by_id, motion_edges, stats, dataset=dataset)',
        'nodes_by_id, edges = fill_gaps_from_low_detections(nodes_by_id, edges, stats, dataset = dataset, frame_cache = repair_frame_cache)',
        'safe_division_orphan_exempted',
        'safe_division_orphan_adopted',
        'readmitted_nodes',
        'gapfill_added_nodes',
        '*prop[6:]',
        '_v12_floor = SAFE_DIV_ORPHAN_MIN_PDIV if _v12_orphan else SAFE_DIV_MIN_PDIV',
        'phase_h_v12_portfolio',
        '[ver12] Phase H portfolio',
        '[ver12] LOWDET dump stage installed',
        'LOWDET {name}: {len(_lc)} peaks above {_LOWDET_THRESHOLD}',
        'os.environ[\'BIOHUB_HOCT_VETO\'] = \'1\'',
        'def add_safe_divisions_postlink',
        'def add_reparent_divisions_postlink',
        '_hv_finalize()',
    )
    for req in required:
        if req not in text:
            sys.exit(f'[build12] THẤT BẠI: thiếu {req!r}')
    if sd_diverge is not None and f"os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '{sd_diverge}'" not in text:
        sys.exit(f'[build12] THẤT BẠI: thiếu env SAFE_DIV_DIVERGE_UM={sd_diverge}')
    for forbidden in ("'status': 'phase_g_v11_mutualnn_pdiv'", "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v11_mn_p85_div05'"):
        if forbidden in text:
            sys.exit(f'[build12] THẤT BẠI: còn sót {forbidden!r}')
    # guard _EXPECTED_NUMERIC: 7 hằng số gốc NGUYÊN VẸN + 2 hằng cập nhật đúng config
    for guard_pair in (
        "'BIOHUB_DET_THRESHOLD': 0.965",
        "'BIOHUB_ILP_APPEARANCE_WEIGHT': 0.0",
        "'BIOHUB_ILP_DISAPPEARANCE_WEIGHT': 2",
        "'BIOHUB_GAP_CLOSE_UM': 5.0",
        "'BIOHUB_OUTPUT_MIN_TRACK_LEN': 6.0",
        "'BIOHUB_SAFE_DIV_MAX_UM': 9.0",
        "'BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT': 0.15",
        f"'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': {dc_thr}",
        f"'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': {sef_w}",
    ):
        must_count(text, guard_pair, 1, f'guard {guard_pair}')

    # ---- 17-bis. REVIEW-2: final-env-value assertion (chống ghi đè thứ tự env) ----
    # Mọi key v12: assignment os.environ[KEY] = 'V' CUỐI CÙNG trong file phải là
    # giá trị config (block [ver12] chạy sau cùng mọi block legacy). Bài học: lần
    # build đầu chèn sau print [ver11] → [ver8] reparent ghi đè EP 0.4→0.25 âm thầm.
    import re as _re

    def _final_env(src: str, key: str) -> str | None:
        vals = _re.findall(rf"os\.environ\['{key}'\] = '([^']*)'", src)
        return vals[-1] if vals else None

    _expected_final_env = {
        'BIOHUB_REPARENT_EDGE_PROB': rep_ep,
        'BIOHUB_REPARENT_MIN_PDIV': rep_pdiv,
        'BIOHUB_REPARENT_CURRENT_FAR_UM': rep_far,
        'BIOHUB_REPARENT_DIVERGE_UM': rep_div,
        'BIOHUB_DIV_PARENT_MAX_UM': div_parent,
        'BIOHUB_SAFE_DIV_ORPHAN_ADOPT': orphan,
        'BIOHUB_SAFE_DIV_ORPHAN_MIN_PDIV': orphan_pdiv,
        'BIOHUB_LOWDET_THRESHOLD': lowdet,
        'BIOHUB_READMIT_RADIUS_UM': radmit_r,
        'BIOHUB_READMIT_MIN_SCORE': radmit_s,
        'BIOHUB_GAPFILL_MAX_GAP': gf_gap,
        'BIOHUB_GAPFILL_MIN_SCORE': gf_min,
        'BIOHUB_GAPFILL_STEP_UM': gf_step,
        'BIOHUB_GAPFILL_PEAK_RADIUS_UM': gf_prad,
        'BIOHUB_GAPFILL_EXCLUDE_UM': gf_excl,
        'BIOHUB_GAPFILL_ALLOW_SYNTHETIC': gf_syn,
        'BIOHUB_GAPFILL_CONTEXT': gf_ctx,
        'BIOHUB_GAPFILL_MAX_ADDED_FRAC': gf_frac,
        'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': sef_w,
        'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': dc_thr,
        'BIOHUB_VALIDATOR_ENABLE': val_en,
    }
    if sd_diverge is not None:
        _expected_final_env['BIOHUB_SAFE_DIV_DIVERGE_UM'] = sd_diverge

    for _key, _want in _expected_final_env.items():
        _got = _final_env(text, _key)
        _want_str = str(_want)
        if _got != _want_str:
            sys.exit(f'[build12] THẤT BẠI final-env: {_key} cuối cùng = {_got!r} (cần {_want_str!r}) — có block legacy ghi đè SAU block [ver12]')
    print(f'[build12] final-env-value PASS: {len(_expected_final_env)} key v12 đều là assignment cuối cùng (không bị legacy ghi đè)')

    # ---- 18. AST + py_compile ----
    ast.parse(text)
    OUT.write_text(text)
    py_compile.compile(str(OUT), doraise=True)
    print(f'[build12] ĐÃ GHI {OUT} ({len(text.splitlines())} dòng; ver-11 gốc {len(VER11.read_text().splitlines())} dòng)')
    print(f'[build12] config: label={label} reparent_ep={rep_ep} orphan={orphan}/{orphan_pdiv} readmit={radmit_r}/{radmit_s} gapfill<={gf_gap} sef={sef_w} dc={dc_thr} lowdet={lowdet} diverge={sd_diverge}')
    print('[build12] 4 trục: 1b reparent mở gate · 1c orphan-adoption + DC · 2 READMIT+GAPFILL+LOWDET-dump · 3 SEF_TTA — mỗi trục env-gated cho A/B v12-lab')
    return 0


if __name__ == '__main__':
    sys.exit(main())
