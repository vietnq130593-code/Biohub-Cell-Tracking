#!/usr/bin/env python3
"""build-ver132-monolith.py — v13.2 = v13.1 + RESTORE MÁY DIVISION (vá lỗi SR0).

Bối cảnh (ERRORS-LEDGER.md L13): v13.1 tắt OUTPUT_SAFE_DIVISIONS + REPARENT_ENABLE
theo autopsy "0 TP mọi cấp" → LB 0.911 (mất ≈0.036). LB phán 2 lần độc lập:
forks=0 → 0.911; forks 144-188 → 0.946-0.947. v13.2 phục hồi v11-exact division
(giữ GC3 + leaf-prune + vel 0.5 + diverge 0.5 + orphan 0 của v13.1) — mọi thay đổi
khác so v13.1 CHỈ là 3 dòng env + tag/guard/report.

Input : cell-monolith-v131-base.py (copy byte-exact từ kernel pull biohub-ver131,
        md5 c21e82f232a8d61fce6c941e1345572c — đã verify 23/9).
Output: cell-monolith.py (determinism: build 2 lần cùng md5).

Kiểm tra sau build (BẮT BUỘC trước khi push):
  python3 ../api/machinery-audit.py --monolith cell-monolith.py --submit-gate
  → kỳ vọng: R1 PASS ×2 (division ON), WARN hypothesis = GC3 + leaf (ack khi submit).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "cell-monolith-v131-base.py"
OUT = HERE / "cell-monolith.py"

V131_TAG = "secondary_deepcenter_tta_0947_reparent_hoct_v131_sr0gc3_nodiv_gap3"
V132_TAG = "secondary_deepcenter_tta_0947_reparent_hoct_v132_restore_division_gc3_leaf"

RESTORE_BLOCK = """# [ver132] Phase J-bis — RESTORE MÁY DIVISION (ERRORS-LEDGER.md L13a/L13c, 23/9).
# SR0 của v13.1 là thiết kế SAI: autopsy cửa sổ replica 3 division (p(0/3)=6-26%)
# không đại diện public split. LB phán 2 lần độc lập: forks=0 → 0.911 (variant A
# ref 56373784 + v13.1 ref 56473159) vs forks 144-188 → 0.946-0.947. Máy division
# v11-class phải BẬT trong mọi build. Phục hồi v11-exact:
os.environ['BIOHUB_OUTPUT_SAFE_DIVISIONS'] = '1'
os.environ['BIOHUB_REPARENT_ENABLE'] = '1'
os.environ['BIOHUB_REPARENT_EDGE_PROB'] = '0.25'
print('[ver132] RESTORE division machinery (L13c): OUTPUT_SAFE_DIVISIONS=1 + REPARENT_ENABLE=1 + EP=0.25 (v11-exact: 82 div/77 reparent/144 forks) | giữ GC3 gap=3.0 + leaf>=0.3 + vel=0.5 + diverge=0.5 orphan=0 | fork census mục tiêu 144-188 (luật fork)')
"""

PATCHES: list[tuple[str, str]] = [
    # P1 — chèn env-block restore ngay sau print [ver131]
    (
        "print('[ver131] Phase J adjEJ-autopsy: SR0 divisions OFF (safe-div+reparent — 0 TP mọi cấp, chỉ FP) | GC3 gap-close=3.0um (TP-bridge 1.68 vs FP-bridge 2.13µm) | P1 diverge=0.5 orphan=0 | P2 vel=0.5 (đỉnh dose-response) | P3 leaf>=0.3 | base v12.1 knockout: READMIT/GAPFILL/LOWDET off, SEF_TTA 0.75, validator OFF')",
        "print('[ver131] Phase J adjEJ-autopsy: SR0 divisions OFF (safe-div+reparent — 0 TP mọi cấp, chỉ FP) | GC3 gap-close=3.0um (TP-bridge 1.68 vs FP-bridge 2.13µm) | P1 diverge=0.5 orphan=0 | P2 vel=0.5 (đỉnh dose-response) | P3 leaf>=0.3 | base v12.1 knockout: READMIT/GAPFILL/LOWDET off, SEF_TTA 0.75, validator OFF')\n" + RESTORE_BLOCK,
    ),
    # P2 — tag (EXPERIMENT_TAG + _guard_report.experiment)
    (V131_TAG, V132_TAG),
    # P3 — status
    ("'status': 'phase_j_v131_adjEJ_autopsy'", "'status': 'phase_j_bis_v132_restore_division'"),
    # P4 — guard report phase_j: sr0 → restore
    (
        "'phase_j': {'sr0_output_safe_divisions': bool(0), 'sr0_reparent_enable': bool(0), 'gc3_gap_close_um': 3.0,",
        "'phase_j': {'restore_output_safe_divisions': bool(1), 'restore_reparent_enable': bool(1), 'restore_reparent_edge_prob': 0.25, 'gc3_gap_close_um': 3.0,",
    ),
    # P5 — config label
    ("'config_label': 'sr0gc3_nodiv_gap3'", "'config_label': 'v132_restore_division_gc3_leaf'"),
    # P6 — divnet_mode text
    (
        "RANK-ONLY INERT (v131 SR0: safe-divisions + reparent OFF — máy division 0 TP mọi cấp; P1 diverge=0.5 orphan=0",
        "RANK-ONLY (v132 RESTORE: safe-divisions + reparent ON v11-exact; P1 diverge=0.5 orphan=0",
    ),
    # P7 — guard text: khóa must_on vào _EXPECTED_TEXT (in-kernel hard gate L13c)
    (
        "_EXPECTED_TEXT = {'BIOHUB_BIDIRECTIONAL_FUSION_MODE': 'harmonic_probability',",
        "_EXPECTED_TEXT = {'BIOHUB_OUTPUT_SAFE_DIVISIONS': '1', 'BIOHUB_REPARENT_ENABLE': '1', 'BIOHUB_BIDIRECTIONAL_FUSION_MODE': 'harmonic_probability',",
    ),
    # P8 — progression print
    (
        "ver-12 4-truc portfolio (reparent+orphan+readmit+gapfill) -> ver-13.1 adjEJ-autopsy (SR0 divisions OFF + GC3 gap-close 3.0 + P1 revert + leaf-prune hygiene)",
        "ver-12 4-truc portfolio (reparent+orphan+readmit+gapfill) -> ver-13.1 adjEJ-autopsy (SR0 — FAIL 0.911, L13) -> ver-13.2 restore-division (L13c: máy division BẬT v11-exact + GC3 + leaf)",
    ),
]


def main() -> None:
    src = BASE.read_text()
    for i, (old, new) in enumerate(PATCHES, 1):
        n = src.count(old)
        if n == 0:
            sys.exit(f"❌ P{i}: không tìm thấy anchor (build hủy)")
        if n > 1 and old != V131_TAG:
            sys.exit(f"❌ P{i}: anchor không duy nhất (n={n})")
        src = src.replace(old, new)
        print(f"P{i}: OK (×{n})")
    OUT.write_text(src)
    md5 = hashlib.md5(OUT.read_bytes()).hexdigest()
    print(f"\n✅ {OUT.name}: {src.count(chr(10)) + 1} dòng · md5 {md5}")
    # verify division-ON trong env cuối (env restore phải đứng SAU env SR0)
    i_sr0 = src.rindex("os.environ['BIOHUB_OUTPUT_SAFE_DIVISIONS'] = '0'")
    i_on = src.rindex("os.environ['BIOHUB_OUTPUT_SAFE_DIVISIONS'] = '1'")
    assert i_on > i_sr0, "env restore phải sau env SR0 (last-write-wins)"
    print("✅ env restore đứng SAU env SR0 (last-write-wins → division ON)")


if __name__ == "__main__":
    main()
