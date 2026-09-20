#!/usr/bin/env python3
"""build-ver11-monolith.py — Dựng ver-11 monolith từ ver-10 (đã chạy thật Kaggle, LB 0.947).

Ver-11 = ver-10 + mở gate division THEO GRID v11-lab v3 (kernel biohub-v11-lab version 4,
20/9): SAFE_DIV_REQUIRE_MUTUAL_NN=0 + SAFE_DIV_MIN_PDIV=<floor> (+ tuỳ chọn
SAFE_DIV_DIVERGE_UM / DIV_SISTER_MAX_UM nếu config thắng đòi).

Config đọc từ ver-11-config.json (cùng thư mục) — ghi từ kết quả grid khi chọn config thắng.

8 thay đổi trên ver-10/cell-monolith.py:
  1. EXPERIMENT_TAG → ..._v11_<label>
  2. env block [ver10] → thêm block [ver11]
  3. hằng số SAFE_DIV_MIN_PDIV (mới — B-7 van FP)
  4. floor check trong vòng chọn add_safe_divisions_postlink
  5. guard report: status phase_g_v11 + phase_g dict + chuỗi divnet_mode cập nhật gate thật
  6. final print progression + ver-11
  7. kiểm tra sau xây
  8. AST parse + py_compile

Lưu ý B-1 (đã kiểm tra): guard _EXPECTED_NUMERIC của ver-10 chỉ chốt 8 hằng số
(DET/ILP/GAP/MIN_TRACK_LEN/SAFE_DIV_MAX_UM/DC/BIDIR/SEF_TTA_WEIGHT) — KHÔNG dính
mutual_nn/min_pdiv/diverge/div_sister → không cần vá guard (build verify chốt 2 mấu).
"""
import ast
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VER10 = ROOT.parent / "ver-10" / "cell-monolith.py"
OUT = ROOT / "cell-monolith.py"
CONFIG = ROOT / "ver-11-config.json"


def must_count(text: str, needle: str, want: int, what: str) -> None:
    got = text.count(needle)
    if got != want:
        sys.exit(f"[build11] THẤT BẠI ở {what}: {needle[:60]!r} xuất hiện {got} lần (cần {want})")


def replace_once(text: str, old: str, new: str, what: str) -> str:
    must_count(text, old, 1, what)
    return text.replace(old, new, 1)


def main() -> int:
    cfg = json.loads(CONFIG.read_text())
    label = cfg["label"]
    mutual_nn = bool(cfg.get("mutual_nn", True))
    min_pdiv = float(cfg.get("min_pdiv") or 0.0)
    diverge = cfg.get("diverge_um")
    div_sister = cfg.get("div_sister_max_um")

    text = VER10.read_text()

    # ---- 0. tiền điều kiện: đúng là monolith ver-10 đã build ----
    must_count(text, "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v10'", 1, "EXPERIMENT_TAG v10")
    must_count(text, "os.environ['BIOHUB_HOCT_VETO'] = '1'", 1, "veto mode 1")
    must_count(text, "SAFE_DIV_REQUIRE_MUTUAL_NN = os.environ.get('BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN', '1') != '0'", 1, "mutual_nn const")
    must_count(text, "def add_safe_divisions_postlink", 1, "add_safe_divisions")
    must_count(text, "'status': 'phase_f_hoct_veto1_v10'", 1, "guard status v10")

    # ---- 1. EXPERIMENT_TAG ----
    tag = f"secondary_deepcenter_tta_0947_reparent_hoct_v11_{label}"
    text = replace_once(
        text,
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v10'",
        f"EXPERIMENT_TAG = '{tag}'",
        "EXPERIMENT_TAG v11",
    )

    # ---- 2. env block [ver11] ----
    extra_env = ""
    if diverge is not None:
        extra_env += f"os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '{float(diverge)}'\n"
    if div_sister is not None:
        extra_env += f"os.environ['BIOHUB_DIV_SISTER_MAX_UM'] = '{float(div_sister)}'\n"
    receipt_short = json.dumps(cfg.get("grid_receipt", {}), ensure_ascii=False)
    if len(receipt_short) > 380:
        receipt_short = receipt_short[:377] + "..."
    env_new = (
        "# [ver11] Phase G — mở gate division theo GRID v11-lab v3 (kernel biohub-v11-lab v4, 20/9).\n"
        "# Funnel B-6 (dump v2): 9 FN = 7 no_proposal (không hồi phục) + 2 mutual_nn (hồi phục được)\n"
        "# → mở trục mutual_nn + van FP SAFE_DIV_MIN_PDIV (B-7: pool 319 → 46/39 theo floor 0.5/0.85).\n"
        f"# Grid receipt: {receipt_short}\n"
        f"os.environ['BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN'] = '{'0' if not mutual_nn else '1'}'\n"
        f"os.environ['BIOHUB_SAFE_DIV_MIN_PDIV'] = '{min_pdiv}'\n"
        + extra_env
        + f"print('[ver11] mutual_nn={mutual_nn} · MIN_PDIV={min_pdiv}' + ('' if {diverge is None} else ' · diverge={diverge}') + ('' if {div_sister is None} else ' · div_sister={div_sister}'))"
    )
    anchor = "print('[ver10] HOCT veto MODE 1 (division edges protected) · deadline 7.5h · cap 300s/video · density-aware guard · tight hardcode 5.5/6.5 · no sweep · no RLF')"
    text = replace_once(text, anchor, anchor + "\n\n" + env_new, "env block [ver11]")

    # ---- 3. hằng số SAFE_DIV_MIN_PDIV ----
    text = replace_once(
        text,
        "SAFE_DIV_REQUIRE_MUTUAL_NN = os.environ.get('BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN', '1') != '0'",
        "SAFE_DIV_REQUIRE_MUTUAL_NN = os.environ.get('BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN', '1') != '0'\n"
        "# [ver11] B-7: van FP phẫu thuật khi mở gate — floor P(division) của node mẹ.\n"
        "SAFE_DIV_MIN_PDIV = float(os.environ.get('BIOHUB_SAFE_DIV_MIN_PDIV', '0.0'))",
        "const SAFE_DIV_MIN_PDIV",
    )

    # ---- 4. floor check trong vòng chọn ----
    old_loop = """        for _score, source_id, candidate_id, parent_dist, _sister, *rest in proposals:
            p_div = rest[0] if rest else None
"""
    new_loop = """        for _score, source_id, candidate_id, parent_dist, _sister, *rest in proposals:
            p_div = rest[0] if rest else None
            # [ver11] floor P(division) — chỉ áp khi SAFE_DIV_MIN_PDIV > 0; không có
            # bằng chứng DivNet (p_div None) thì TỪ CHỐI (an toàn: không thêm division mù).
            if SAFE_DIV_MIN_PDIV > 0.0 and (p_div is None or float(p_div) < SAFE_DIV_MIN_PDIV):
                stats['safe_division_min_pdiv_rejected'] = stats.get('safe_division_min_pdiv_rejected', 0) + 1
                continue
"""
    text = replace_once(text, old_loop, new_loop, "floor check")

    # ---- 5. guard report ----
    gates_desc = f"mutual_nn={'ON' if mutual_nn else 'OFF'} · MIN_PDIV={min_pdiv}"
    if diverge is not None:
        gates_desc += f" · diverge={float(diverge)}"
    if div_sister is not None:
        gates_desc += f" · div_sister={float(div_sister)}"
    text = replace_once(
        text,
        "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v10', 'status': 'phase_f_hoct_veto1_v10', ",
        f"'experiment': '{tag}', 'status': 'phase_g_v11_mutualnn_pdiv', "
        f"'phase_g': {{'mutual_nn_required': {mutual_nn}, 'safe_div_min_pdiv': {min_pdiv}, "
        f"'safe_div_diverge_um': {'None' if diverge is None else float(diverge)}, "
        f"'div_sister_max_um': {'None' if div_sister is None else float(div_sister)}, "
        f"'grid_label': '{label}', 'source': 'v11-lab v3 grid (kernel v4, 2026-09-20)'}}, ",
        "guard report v11",
    )
    text = replace_once(
        text,
        "'divnet_mode': 'RANK-ONLY (gate production giữ nguyên tau 0.6 / diverge 2.25)'",
        f"'divnet_mode': 'RANK-ONLY (v11 gates: {gates_desc})'",
        "divnet_mode audit",
    )

    # ---- 6. final print ----
    text = replace_once(
        text,
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-10 hoct-veto mode1 (division-safe, density-guarded)')",
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-10 hoct-veto mode1 -> ver-11 mutual_nn-off + MIN_PDIV floor')",
        "final print v11",
    )

    # ---- 7. kiểm tra sau xây ----
    for required in (f"EXPERIMENT_TAG = '{tag}'", "os.environ['BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN']",
                     "os.environ['BIOHUB_SAFE_DIV_MIN_PDIV']", "SAFE_DIV_MIN_PDIV = float(",
                     "safe_division_min_pdiv_rejected", "phase_g_v11_mutualnn_pdiv",
                     "[ver11] Phase G", "def add_safe_divisions_postlink",
                     "os.environ['BIOHUB_HOCT_VETO'] = '1'"):
        if required not in text:
            sys.exit(f"[build11] THẤT BẠI: thiếu {required!r}")
    for forbidden in ("'status': 'phase_f_hoct_veto1_v10'",):
        if forbidden in text:
            sys.exit(f"[build11] THẤT BẠI: còn sót {forbidden!r}")
    # guard _EXPECTED_NUMERIC nguyên vẹn (B-1): 2 mấu chốt không đổi
    must_count(text, "'BIOHUB_SAFE_DIV_MAX_UM': 9.0", 1, "guard SAFE_DIV_MAX_UM 9.0")
    must_count(text, "'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': 0.20", 1, "guard DC 0.20")

    # ---- 8. AST + py_compile ----
    ast.parse(text)
    OUT.write_text(text)
    py_compile.compile(str(OUT), doraise=True)
    print(f"[build11] ĐÃ GHI {OUT} ({len(text.splitlines())} dòng; ver-10 gốc {len(VER10.read_text().splitlines())} dòng)")
    print(f"[build11] config: label={label} mutual_nn={mutual_nn} min_pdiv={min_pdiv} diverge={diverge} div_sister={div_sister}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
