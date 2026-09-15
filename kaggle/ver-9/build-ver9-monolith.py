"""build-ver9-monolith.py — Dựng ver-9 monolith từ ver-8 v3-fast + 3 block mới.

Ver-9 = v3-fast + HOCT consensus veto mode 2 (port sjlee101 cell 6/12)
      + repeat-lineage filter (port pawanmali cell 10.5) + cổng đánh giá §6 rev-2.

6 thay đổi (theo VER9-RESEARCH.md rev-2 A3 / rev-3):
  1. EXPERIMENT_TAG → secondary_deepcenter_tta_0947_reparent_hoct_v9
  2. env block [ver9]: BIOHUB_HOCT_VETO=2 · deadline 10.5h · RLF=1 · hardcode tight
     per-prefix 5.5/6.5 (bỏ PPSWEEP — v1 fail hidden-test runtime vì sweep 6.9h)
  3. [ver9-hoct] arming block cắm TRƯỚC lần ghi submission đầu (hook intercept write)
  4. PP_CANDIDATES = {} (không sweep — cấu hình thắng đã hardcode)
  5. [ver9-hoct-finalize] + [ver9-rlf] + [ver9-gate] cắm sau final-write section
  6. guard report: experiment/status/final print cập nhật ver-9
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VER8 = ROOT.parent / "ver-8" / "cell-monolith.py"
HOCT_BLOCK = (ROOT / "hoct-veto-block.py").read_text()
RLF_GATE_BLOCK = (ROOT / "rlf-gate-block.py").read_text()
OUT = ROOT / "cell-monolith.py"


def must_replace(text: str, old: str, new: str, what: str) -> str:
    if text.count(old) != 1:
        sys.exit(f"[build] THẤT BẠI ở {what}: anchor xuất hiện {text.count(old)} lần (cần 1)")
    return text.replace(old, new)


def main() -> int:
    text = VER8.read_text()

    # 1. EXPERIMENT_TAG
    text = must_replace(
        text,
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_v8_3fast'",
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v9'",
        "EXPERIMENT_TAG",
    )

    # 2. env block [ver9] — cắm sau print DivNet (cuối env block ver-7b)
    env_anchor = "print('DivNet: RANK-ONLY integration, W =', os.environ['BIOHUB_DIVNET_RANK_W_UM'], 'um')"
    env_new = env_anchor + """

# [ver9] Phase E — HOCT consensus veto (mode 2) + repeat-lineage division filter (RLF).
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
    text = must_replace(text, env_anchor, env_new, "env block [ver9]")

    # 3. [ver9-hoct] arming block — cắm sau display() cuối của write_test_submission,
    #    TRƯỚC _base_postprocess_signature (hook có mặt trước lần ghi base đầu tiên)
    hoct_anchor = """    display(pd.read_csv(SUBMISSION_PATH, nrows = 8))

_base_postprocess_signature = _postprocess_resume_signature()"""
    hoct_new = """    display(pd.read_csv(SUBMISSION_PATH, nrows = 8))

""" + HOCT_BLOCK + """

_base_postprocess_signature = _postprocess_resume_signature()"""
    text = must_replace(text, hoct_anchor, hoct_new, "arming block [ver9-hoct]")

    # 4. PP_CANDIDATES = {} — bỏ sweep (cấu hình thắng đã hardcode qua env)
    text = must_replace(
        text,
        "PP_CANDIDATES: dict[str, dict] = {'ppTight5565fb': {'MOTION_RELINK_TIGHT_UM': 5.5, 'MOTION_RELINK_TIGHT_PER_PREFIX': {'44b6': 5.5, '6bba': 6.5}}}",
        "PP_CANDIDATES: dict[str, dict] = {}",
        "PP_CANDIDATES rỗng",
    )
    # 4b. cập nhật comment [ver8.3-fast] trước PP_CANDIDATES
    text = must_replace(
        text,
        "# [ver8.3-fast] Submission 56242181 (v1, tight55) FAILED trên hidden test vì rerun vượt\n# runtime limit (kernel public 6,2h × hidden ~2× > 12h; sweep 16-19 candidates = 86%\n# runtime). v3 rút sweep về 1 candidate duy nhất (ppTight5565fb — per-prefix theo E2\n# wave1 + fallback global 5.5 cho prefix lạ trên hidden test) → public ~1,3-1,8h,\n# hidden ~2,5-3,6h — an toàn trong hạn. Cấu hình re-parent giữ nguyên v1/v2:\n# REPARENT_EDGE_PROB 0.25 (v2 chứng minh mở 0.50/0.75 chỉ thêm FP không thêm tp).\n# Retain the narrow post-process candidate set used by the 0.946 pipeline",
        "# [ver9] BỎ PPSWEEP hoàn toàn (A3.3 rev-2): cấu hình thắng ppTight5565fb (per-prefix\n# 44b6→5.5 / 6bba→6.5 + fallback global 5.5) đã HARDCODE qua env block [ver9] — E2\n# wave1, v2 (19 candidates) và v3-fast cùng chọn nó; v1 (56242181) fail hidden-test\n# runtime chính vì sweep chiếm 86% kernel. Base validator eval (gate REF của [ver9-gate])\n# vẫn chạy. Cấu hình re-parent giữ nguyên v1/v2: REPARENT_EDGE_PROB 0.25 (v2 chứng minh\n# mở 0.50/0.75 chỉ thêm FP không thêm tp).\n# Retain the narrow post-process candidate set used by the 0.946 pipeline",
        "comment [ver8.3-fast] → [ver9]",
    )

    # 5. [ver9-hoct-finalize] + [ver9-rlf] + [ver9-gate] — cắm sau final-write section,
    #    TRƯỚC "# Audit the final submission" (audit đọc submission SAU veto+RLF)
    gate_anchor = """        _write_resume_json(FINAL_SUBMISSION_STATE_PATH, {'resume_schema': RESUME_SCHEMA_VERSION, 'status': 'complete', 'signature': _final_submission_signature, 'test_prediction_signature': _test_prediction_signature, 'base_postprocess_signature': _base_postprocess_signature, 'selected_label': selected_label, 'selected_config': selected_config, 'sha256': _resume_file_sha256(SUBMISSION_PATH), 'rows': _resume_csv_row_count(SUBMISSION_PATH), 'preview_records': _final_preview.to_dict(orient = 'records')})

# Audit the final submission after validator-driven post-process selection"""
    gate_new = """        _write_resume_json(FINAL_SUBMISSION_STATE_PATH, {'resume_schema': RESUME_SCHEMA_VERSION, 'status': 'complete', 'signature': _final_submission_signature, 'test_prediction_signature': _test_prediction_signature, 'base_postprocess_signature': _base_postprocess_signature, 'selected_label': selected_label, 'selected_config': selected_config, 'sha256': _resume_file_sha256(SUBMISSION_PATH), 'rows': _resume_csv_row_count(SUBMISSION_PATH), 'preview_records': _final_preview.to_dict(orient = 'records')})

""" + RLF_GATE_BLOCK + """

# Audit the final submission after validator-driven post-process selection"""
    text = must_replace(text, gate_anchor, gate_new, "block [ver9-rlf+gate]")

    # 6. guard report + final print
    text = must_replace(
        text,
        "'experiment': 'secondary_deepcenter_tta_0947_v1_reparent_v8', 'status': 'phase_d_reparent_division_recovery', 'phase_d':",
        "'experiment': 'secondary_deepcenter_tta_0947_reparent_hoct_v9', 'status': 'phase_e_hoct_veto_rlf_v9', 'phase_e': {'hoct_veto_mode': int(os.environ.get('BIOHUB_HOCT_VETO', '0')), 'rlf_enabled': os.environ.get('BIOHUB_RLF_ENABLE', '0') != '0', 'tight_hardcode': {'44b6': 5.5, '6bba': 6.5, 'fallback_um': 5.5}}, 'phase_d':",
        "guard report experiment ver-9",
    )
    text = must_replace(
        text,
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent')",
        "print('Verified progression preserved: 0.933 -> 0.934 -> 0.939 -> 0.941 -> 0.946 -> 0.947 -> ver-8 reparent -> ver-9 hoct-veto mode2 + rlf')",
        "final print ver-9",
    )

    OUT.write_text(text)
    print(f"[build] ĐÃ GHI {OUT} ({len(text.splitlines())} dòng; ver-8 gốc {len(VER8.read_text().splitlines())} dòng)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
