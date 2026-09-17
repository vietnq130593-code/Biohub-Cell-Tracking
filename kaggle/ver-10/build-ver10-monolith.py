"""build-ver10-monolith.py — Dựng ver-10 monolith từ ver-9 (đã build & chạy thật trên Kaggle).

Ver-10 = v3-fast + HOCT consensus veto MODE 1 (division-safe) + guard mật độ chống TLE
        − RLF (chết hoàn toàn: Δ 0.000000) − gate/validator replay (bài học TLE ver-9).

Theo V10-RESULTS.md §6 khuyến nghị (17/9): kernel production = v3-fast + veto mode 1 +
BIOHUB_HOCT_MAX_VIDEO_S 300 (từ 900) + DEADLINE 7.5h (từ 10.5) + ước lượng theo n × d_max
(mật độ node/frame) + abort giữa video ở biên chunk. KHÔNG RLF, KHÔNG [ver9-gate],
KHÔNG S2 eval cell (strip validator replay → public ~2.0–2.2h).

7 thay đổi trên ver-9/cell-monolith.py (chính là notebook biohub-ver9 v1 đã chạy Kaggle):
  1. EXPERIMENT_TAG → secondary_deepcenter_tta_0947_reparent_hoct_v10
  2. env block [ver9] → [ver10]: VETO=1 · deadline 7.5 · cap 300 · bỏ RLF · giữ tight hardcode
  3. block [ver9-hoct] → [ver10-hoct] (hoct-veto-block-v10.py: density-aware estimator
     k·n·d_max + fixed 50s, ×3 khi d_max>550, _hvDeadlineAbort giữa chunk)
  4. [ver9-hoct-finalize] → [ver10-hoct-finalize]
  5. XÓA block [ver9-rlf] + [ver9-gate] (giữ _hv_finalize)
  6. guard report: phase_f_hoct_veto1_v10
  7. final print + comment PPSWEEP cập nhật ver-10
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VER9 = ROOT.parent / "ver-9" / "cell-monolith.py"
HOCT_BLOCK_V10 = (ROOT / "hoct-veto-block-v10.py").read_text()
OUT = ROOT / "cell-monolith.py"


def must_count(text: str, needle: str, want: int, what: str) -> None:
    got = text.count(needle)
    if got != want:
        sys.exit(f"[build] THẤT BẠI ở {what}: {needle[:60]!r} xuất hiện {got} lần (cần {want})")


def replace_once(text: str, old: str, new: str, what: str) -> str:
    must_count(text, old, 1, what)
    return text.replace(old, new, 1)


def main() -> int:
    text = VER9.read_text()

    # ---- 0. kiểm tra tiền điều kiện: đúng là monolith ver-9 đã build ----
    must_count(text, "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v9'", 1, "EXPERIMENT_TAG v9")
    must_count(text, "os.environ['BIOHUB_HOCT_VETO'] = '2'", 1, "mode 2")
    must_count(text, "# ==== [ver9-hoct] HOCT consensus veto", 1, "block hoct v9")
    must_count(text, "# ==== [ver9-rlf] Repeat-lineage division filter", 1, "block rlf")
    must_count(text, "# ==== [ver9-gate] System-view official eval", 1, "block gate")
    must_count(text, "_hv_finalize()", 2, "finalize (def + call)")

    # ---- 1. EXPERIMENT_TAG ----
    text = replace_once(
        text,
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v9'",
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v10'",
        "EXPERIMENT_TAG",
    )

    # ---- 2. env block [ver9] → [ver10] ----
    env_old = """# [ver9] Phase E — HOCT consensus veto (mode 2) + repeat-lineage division filter (RLF).
# Veto áp bên trong lần ghi submission.csv (hook write_test_submission / filter_output_graph,
# port nguyên văn cell 6 sjlee101/biohub-lf-hoctveto-div-b — biến thể fielded "-div-b",
# +0.0040 CI dương trên 20 video honest). Mode 2 = veto cả cạnh division. Deadline 10.5h
# + cap 900s/video + fail-safe pass-through giữ graph gốc khi HOCT hỏng (nguyên tắc 10).
os.environ['BIOHUB_HOCT_VETO'] = '2'
os.environ['BIOHUB_HOCT_DEADLINE_H'] = '10.5'
os.environ['BIOHUB_HOCT_MAX_VIDEO_S'] = '900'
# [ver9] RLF (pawanmali divfix cell 10.5): fork có tổ tiên cũng fork → bỏ cạnh con xa hơn
# (GT thật 0/132 divisions lặp lineage). Guard ≤ 0.5% cạnh, vượt thì hoàn tác.
os.environ['BIOHUB_RLF_ENABLE'] = '1'
# [ver9] Hardcode cấu hình thắng (rev-2 E6): E2 wave1 + v2 + v3-fast cùng chọn ppTight5565fb
# (per-prefix 44b6→5.5 / 6bba→6.5, fallback global 5.5 cho prefix lạ trên hidden test).
# BỎ PPSWEEP hoàn toàn (A3.3): v1 (56242181) fail hidden-test runtime vì sweep chiếm 86%;
# submission CÓ rerun trên hidden test ~2× public → kernel phải lean.
os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'
os.environ['BIOHUB_MOTION_RELINK_TIGHT_PER_PREFIX'] = '{"44b6": 5.5, "6bba": 6.5}'
print('[ver9] HOCT veto mode', os.environ['BIOHUB_HOCT_VETO'], '· RLF on · tight hardcode 5.5/6.5 · no sweep')"""
    env_new = """# [ver10] Phase F — HOCT consensus veto MODE 1 (division-safe) + guard mật độ chống TLE.
# V10-LAB 17/9 (kernel v10-lab-gpu-t4, 8 stems T4×2): veto1 là cấu hình DUY NHẤT thắng cả
# adjEJ (+0.001828) LẪN proxy (+0.001828) mà KHÔNG đụng division (4/1/8 nguyên vẹn);
# mode 2 (ver-9 đã nộp) mất 1 div_tp (4→3) làm proxy −0.0060 → gate FALLBACK. RLF chết
# hoàn toàn (Δ 0.000000, 21 cạnh) → BỎ. Guard thắt theo V10-RESULTS §6: cap 300s/video
# (từ 900), deadline 7.5h (từ 10.5), ước lượng density-aware (xem [ver10-hoct] block).
os.environ['BIOHUB_HOCT_VETO'] = '1'
os.environ['BIOHUB_HOCT_DEADLINE_H'] = '7.5'
os.environ['BIOHUB_HOCT_MAX_VIDEO_S'] = '300'
# [ver10] Hardcode cấu hình thắng (giữ nguyên v3-fast): ppTight5565fb per-prefix
# 44b6→5.5 / 6bba→6.5, fallback global 5.5 cho prefix lạ trên hidden test. Không sweep.
os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'
os.environ['BIOHUB_MOTION_RELINK_TIGHT_PER_PREFIX'] = '{"44b6": 5.5, "6bba": 6.5}'
print('[ver10] HOCT veto MODE 1 (division edges protected) · deadline 7.5h · cap 300s/video · density-aware guard · tight hardcode 5.5/6.5 · no sweep · no RLF')"""
    text = replace_once(text, env_old, env_new, "env block [ver10]")

    # ---- 3. block [ver9-hoct] → [ver10-hoct] (vùng: đầu block → _base_postprocess...) ----
    h_start = text.index("# ==== [ver9-hoct] HOCT consensus veto")
    h_tail = "_base_postprocess_signature = _postprocess_resume_signature()"
    h_end = text.index(h_tail, h_start)
    block = HOCT_BLOCK_V10 if HOCT_BLOCK_V10.endswith("\n") else HOCT_BLOCK_V10 + "\n"
    text = text[:h_start] + block + "\n" + text[h_end:]

    # ---- 4. [ver9-hoct-finalize] → [ver10-hoct-finalize] ----
    text = replace_once(
        text,
        "# ==== [ver9-hoct-finalize] Đảm bảo veto áp đúng 1 lần vào submission cuối =================\n"
        "# Port cell 12 sjlee101: nếu lần ghi nào đó đã wrap (applied_writes > 0) → chỉ in summary;\n"
        "# nếu resume skip hết các lần ghi → re-write 1 lần với veto. Không bao giờ raise.",
        "# ==== [ver10-hoct-finalize] Đảm bảo veto áp đúng 1 lần vào submission cuối ================\n"
        "# Port cell 12 sjlee101: nếu lần ghi nào đó đã wrap (applied_writes > 0) → chỉ in summary;\n"
        "# nếu resume skip hết các lần ghi → re-write 1 lần với veto. Không bao giờ raise.",
        "finalize header",
    )

    # ---- 5. XÓA [ver9-rlf] + [ver9-gate] (giữ _hv_finalize) ----
    r_start = text.index("# ==== [ver9-rlf] Repeat-lineage division filter")
    a_marker = "# Audit the final submission after validator-driven post-process selection"
    a_start = text.index(a_marker, r_start)
    removed = text[r_start:a_start]
    for forbidden in ("ver9_rlf_edges", "ver9_score_final", "VER9_GATE_RESULT", "RLF_GUARD_REVERT"):
        if forbidden not in removed:
            sys.exit(f"[build] THẤT BẠI: vùng xóa không chứa {forbidden}")
    text = text[:r_start] + text[a_start:]
    # chuẩn hoá 2 dòng trắng giữa _hv_finalize() và # Audit (PEP8 top-level)
    text = replace_once(
        text,
        "_hv_finalize()\n\n# Audit the final submission",
        "_hv_finalize()\n\n\n# Audit the final submission",
        "khoảng trắng sau finalize",
    )

    # ---- 6. guard report → v10 ----
    text = replace_once(
        text,
        "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v9', 'status': 'phase_e_hoct_veto_rlf_v9', "
        "'phase_e': {'hoct_veto_mode': int(os.environ.get('BIOHUB_HOCT_VETO', '0')), "
        "'rlf_enabled': os.environ.get('BIOHUB_RLF_ENABLE', '0') != '0', "
        "'tight_hardcode': {'44b6': 5.5, '6bba': 6.5, 'fallback_um': 5.5}}, 'phase_d':",
        "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v10', 'status': 'phase_f_hoct_veto1_v10', "
        "'phase_f': {'hoct_veto_mode': 1, 'hoct_deadline_h': 7.5, 'hoct_max_video_s': 300.0, "
        "'hoct_est_model': 'k*n*d_max + 50s, 3x above 550 nodes/frame (V10-LAB 17/9)', "
        "'no_rlf': True, 'no_gate_replay': True, "
        "'tight_hardcode': {'44b6': 5.5, '6bba': 6.5, 'fallback_um': 5.5}}, 'phase_d':",
        "guard report ver-10",
    )

    # ---- 7. final print + comment PPSWEEP ----
    text = replace_once(
        text,
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-9 hoct-veto mode2 + rlf')",
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-10 hoct-veto mode1 (division-safe, density-guarded)')",
        "final print ver-10",
    )
    text = replace_once(
        text,
        "# [ver9] BỎ PPSWEEP hoàn toàn (A3.3 rev-2): cấu hình thắng ppTight5565fb (per-prefix\n# 44b6→5.5 / 6bba→6.5 + fallback global 5.5) đã HARDCODE qua env block [ver9] — E2\n# wave1, v2 (19 candidates) và v3-fast cùng chọn nó; v1 (56242181) fail hidden-test\n# runtime chính vì sweep chiếm 86% kernel. Base validator eval (gate REF của [ver9-gate])\n# vẫn chạy.",
        "# [ver10] BỎ PPSWEEP (giữ nguyên v3-fast): cấu hình thắng ppTight5565fb (per-prefix\n# 44b6→5.5 / 6bba→6.5 + fallback global 5.5) đã HARDCODE qua env block [ver10] — E2\n# wave1, v2 (19 candidates) và v3-fast cùng chọn nó; v1 (56242181) fail hidden-test\n# runtime chính vì sweep chiếm 86% kernel. Base validator eval giữ nguyên (một phần\n# runtime 1.74h của v3-fast đã pass hidden).",
        "comment PPSWEEP",
    )

    # ---- kiểm tra sau xây ----
    for forbidden in ("[ver9-rlf]", "[ver9-gate]", "ver9_rlf_edges", "ver9_score_final",
                      "VER9_GATE", "BIOHUB_RLF_ENABLE", "phase_e_hoct_veto_rlf_v9"):
        if forbidden in text:
            sys.exit(f"[build] THẤT BẠI: còn sót {forbidden!r} sau khi build")
    for required in ("[ver10-hoct] HOCT consensus veto", "class _hvDeadlineAbort",
                     "_HV_K_ND", "_HV_DENSITY_CAL", "aborted_deadline",
                     "os.environ['BIOHUB_HOCT_VETO'] = '1'",
                     "os.environ['BIOHUB_HOCT_DEADLINE_H'] = '7.5'",
                     "os.environ['BIOHUB_HOCT_MAX_VIDEO_S'] = '300'",
                     "phase_f_hoct_veto1_v10", "_hv_finalize()"):
        if required not in text:
            sys.exit(f"[build] THẤT BẠI: thiếu {required!r}")

    OUT.write_text(text)
    print(f"[build] ĐÃ GHI {OUT} ({len(text.splitlines())} dòng; ver-9 gốc {len(VER9.read_text().splitlines())} dòng)")
    print(f"[build] xóa {removed.count(chr(10))} dòng RLF+gate; block [ver10-hoct] {len(HOCT_BLOCK_V10.splitlines())} dòng")
    return 0


if __name__ == "__main__":
    sys.exit(main())
