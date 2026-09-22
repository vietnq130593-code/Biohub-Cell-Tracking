#!/usr/bin/env python3
"""make-ver13-ipynb.py — Đóng gói notebook ver-13 (Phase I: trọng tâm adjEJ P1-P4).

Cấu trúc notebook (2 cell, giống ver-10/11/12):
  [markdown] header — settings T4×2, Internet OFF, 9 nguồn input (giữ nguyên ver-11/12)
  [code] S1 monolith — ver-13 (v12.1-knockout + Phase I: P1 revert diverge 0.5 +
          orphan OFF + P2 velocity 0.25 + P3 leaf-prune 0.30 port amanatar +
          P4 divwide 11/16/12 + dcsd 0.15)

Kiểm thử tĩnh: py_compile + mấu tích hợp ver-13 (selftest v13lab đã PASS riêng) +
source khớp nguyên văn + guard 13 hằng số nguyên vẹn theo config (5 gốc + 2 đổi +
4 thêm + SEF_TTA).
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOAD = ROOT.parents[1] / "download"
MONOLITH = ROOT / "cell-monolith.py"
OUT = DOWNLOAD / "ver13-cell-tracking.ipynb"
CFG = json.loads((ROOT / "ver-13-config.json").read_text())


def to_source_lines(text: str) -> list:
    lines = text.split("\n")
    out = []
    for i, line in enumerate(lines):
        if i < len(lines) - 1:
            out.append(line + "\n")
        else:
            if line != "":
                out.append(line)
    return out


def build_notebook() -> dict:
    md = (
        "# ver 13 — Biohub Cell Tracking (Phase I: trọng tâm adjEJ — V13-ADJEJ-RESEARCH.md)\n\n"
        "**Nền v12.1-knockout** (ref 56442903, LB 0.946 — READMIT/GAPFILL/LOWDET off) **+ 4 đề xuất P1-P4**\n"
        "(mỗi lever env-gated, A/B được trên v13-lab CPU-only):\n\n"
        f"- **P1 Revert diverge**: SAFE_DIV_DIVERGE_UM −2.0→{CFG.get('p1_safe_div_diverge_um')} (đúng grid v11 mn_p85_div05 — đính chính research ghi 2.25) + ORPHAN_ADOPT={CFG.get('p1_orphan_adopt')} → gate safe-div trở về hành xử v11 (baseline 0.947)\n"
        f"- **P2 Velocity**: MOTION_RELINK_VELOCITY_WEIGHT 0.5→{CFG.get('p2_motion_relink_velocity_weight')} (sweep amanatar +0.0014 adj — lever lớn nhất chưa dùng)\n"
        f"- **P3 Leaf-prune**: LEAF_PRUNE_MIN_EDGE_PROB={CFG.get('p3_leaf_prune_min_edge_prob')} — port nguyên văn amanatar v4 (~60 dòng; sweep +0.0004 adj; census −71 cạnh yếu)\n"
        f"- **P4 Divwide+DCSD**: SAFE_DIV_MAX 9→{CFG.get('p4_safe_div_max_um')} · SISTER 14→{CFG.get('p4_safe_div_sister_max_um')} · EXISTING_CHILD 10→{CFG.get('p4_safe_div_existing_child_max_um')} · DC 0.2→{CFG.get('p4_dc_safe_div_threshold')} (recall division không tốn adj — giữ divergence nghiêm ngặt)\n\n"
        "**Settings trước khi Run All**\n\n"
        "| Thiết lập | Giá trị |\n|---|---|\n| Accelerator | **GPU T4 × 2** |\n| Internet | **OFF** |\n\n"
        "**9 nguồn input (Add Input):** giữ nguyên ver-11/ver-12.\n\n"
        "**1 code cell:** S1 — monolith (~35-55' T4×2 như v12.1 RUN 2; validator OFF tiết kiệm ~90').\n\n"
        "**⚠ KHÔNG submit Kaggle khi chưa có lệnh trực tiếp** (luật đứng). v10/v11 banked 0.947 luôn selectable."
    )
    cells = [{"cell_type": "markdown", "id": "ver13-header", "metadata": {},
             "source": to_source_lines(md)}]
    cells.append({"cell_type": "code", "id": "ver13-s1-monolith", "metadata": {},
                  "execution_count": None, "outputs": [],
                  "source": to_source_lines(MONOLITH.read_text())})
    return {"cells": cells,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                        "name": "python3"},
                         "language_info": {"name": "python", "version": "3.11"}},
            "nbformat": 4, "nbformat_minor": 5}


def static_checks() -> None:
    py_compile.compile(str(MONOLITH), doraise=True)
    print("[check] py_compile PASS (ver-13 monolith)")
    text = MONOLITH.read_text()
    required = [
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v13_",
        "os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '0.5'",
        "os.environ['BIOHUB_SAFE_DIV_ORPHAN_ADOPT'] = '0'",
        "os.environ['BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT'] = '0.25'",
        "os.environ['BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB'] = '0.3'",
        "os.environ['BIOHUB_SAFE_DIV_MAX_UM'] = '11.0'",
        "os.environ['BIOHUB_SAFE_DIV_SISTER_MAX_UM'] = '16.0'",
        "os.environ['BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM'] = '12.0'",
        "os.environ['BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD'] = '0.15'",
        "LEAF_PRUNE_MIN_EDGE_PROB = float(os.environ.get(",
        "def prune_weak_leaf_nodes",
        "nodes_by_id, edges = prune_weak_leaf_nodes(nodes_by_id, edges, stats)",
        "'leaf_prune_nodes': 0, 'leaf_prune_edges': 0",
        "phase_i_v13_adjEJ",
        "[ver13] Phase I adjEJ",
        "after weak-leaf pruning",
        "os.environ['BIOHUB_HOCT_VETO'] = '1'",
        "os.environ['BIOHUB_HOCT_DEADLINE_H'] = '7.5'",
        "os.environ['BIOHUB_HOCT_MAX_VIDEO_S'] = '300'",
        "os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'",
        "def add_safe_divisions_postlink",
        "def add_reparent_divisions_postlink",
        "def readmit_discarded_detections",
        "def fill_gaps_from_low_detections",
        "_hv_finalize()",
    ]
    for token in required:
        if token not in text:
            sys.exit(f"[check] THIẾU mấu [ver13]: {token}")
    # guard 13 hằng: 5 gốc nguyên vẹn + 8 theo config v13
    for pair in ("'BIOHUB_DET_THRESHOLD': 0.965",
                 "'BIOHUB_ILP_APPEARANCE_WEIGHT': 0.0",
                 "'BIOHUB_ILP_DISAPPEARANCE_WEIGHT': 2",
                 "'BIOHUB_GAP_CLOSE_UM': 5.0",
                 "'BIOHUB_OUTPUT_MIN_TRACK_LEN': 6.0",
                 "'BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT': 0.15",
                 f"'BIOHUB_SAFE_DIV_MAX_UM': {CFG.get('p4_safe_div_max_um')}",
                 f"'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': {CFG.get('p4_dc_safe_div_threshold')}",
                 f"'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': {CFG.get('sef_tta_weight')}",
                 f"'BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT': {CFG.get('p2_motion_relink_velocity_weight')}",
                 f"'BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB': {CFG.get('p3_leaf_prune_min_edge_prob')}",
                 f"'BIOHUB_SAFE_DIV_SISTER_MAX_UM': {CFG.get('p4_safe_div_sister_max_um')}",
                 f"'BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM': {CFG.get('p4_safe_div_existing_child_max_um')}"):
        if pair not in text:
            sys.exit(f"[check] THẤT BẠI: guard {pair}")
    print(f"[check] {len(required)} mấu [ver13] đủ mặt + guard 13 hằng nguyên vẹn theo config")


def verify_notebook(nb: dict) -> None:
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    if sources["ver13-s1-monolith"] != MONOLITH.read_text():
        sys.exit("[verify] cell ver13-s1-monolith KHÁC file nguồn")
    print(f"[verify] cell ver13-s1-monolith == cell-monolith.py ({len(sources['ver13-s1-monolith'].splitlines())} dòng)")
    json.dumps(nb)
    print("[verify] JSON notebook hợp lệ —", OUT.name, f"({len(nb['cells'])} cell)")


def main() -> int:
    static_checks()
    nb = build_notebook()
    verify_notebook(nb)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1))
    print(f"[make13] ĐÃ GHI {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
