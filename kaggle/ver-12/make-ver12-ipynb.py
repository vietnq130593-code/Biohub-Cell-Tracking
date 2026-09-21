#!/usr/bin/env python3
"""make-ver12-ipynb.py — Đóng gói notebook ver-12 (Phase H: portfolio 4 trục).

Cấu trúc notebook (2 cell, giống ver-10/ver-11):
  [markdown] header — settings T4×2, Internet OFF, 9 nguồn input (giữ nguyên ver-11)
  [code] S1 monolith — ver-12 (ver-11 + Phase H: reparent mở gate + orphan-adoption +
          READMIT/GAPFILL + LOWDET dump stage + SEF_TTA/DC config-driven)

Kiểm thử tĩnh: py_compile + mấu tích hợp ver-12 (selftest v12lab đã PASS riêng) +
source khớp nguyên văn + guard 9 hằng số nguyên vẹn theo config.
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOAD = ROOT.parents[1] / "download"
MONOLITH = ROOT / "cell-monolith.py"
OUT = DOWNLOAD / "ver12-cell-tracking.ipynb"
CFG = json.loads((ROOT / "ver-12-config.json").read_text())


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
        "# ver 12 — Biohub Cell Tracking (Phase H: portfolio 4 trục — V12-RESEARCH.md)\n\n"
        "**Nền ver-11** (ref 56403231, đang chấm) **+ 4 trục có receipt** (mỗi trục env-gated,\n"
        "A/B được trên v12-lab CPU-only):\n\n"
        f"- **1b Reparent mở gate**: REPARENT_EDGE_PROB 0.25→{CFG.get('reparent_edge_prob')} (F7: pool 05db 15.833 cands bị chặn 13.143 ở pdiv)\n"
        f"- **1c Orphan-adoption** (F1): SAFE_DIV_ORPHAN_ADOPT={CFG.get('orphan_adopt')} floor={CFG.get('orphan_min_pdiv')} — mồ côi đúng-1-cha được miễn divergence + floor p_div riêng\n"
        f"- **1c' Diverge âm**: SAFE_DIV_DIVERGE_UM 0.5→{CFG.get('safe_div_diverge_um')} (lab 21/9: GT div t=24 bị chặn vì hai con HỘI TỤ −1.79µm; replica +0.0067; ⚠ tension validator −0.0006/+4FP — xem ver-12-config.json lab_receipts)\n"
        f"- **2 READMIT + GAPFILL** (port thtennant batch-B): +{CFG.get('readmit_radius_um')}µm/{CFG.get('readmit_min_score')} + gap≤{CFG.get('gapfill_max_gap')} (receipt hidden +1.014 node/+1.002 cạnh) + LOWDET dump stage trong predict script\n"
        f"- **3 SEF_TTA w={CFG.get('sef_tta_weight')} · DC={CFG.get('dc_safe_div_threshold')}** config-driven (guard cập nhật)\n\n"
        "**Settings trước khi Run All**\n\n"
        "| Thiết lập | Giá trị |\n|---|---|\n| Accelerator | **GPU T4 × 2** |\n| Internet | **OFF** |\n\n"
        "**9 nguồn input (Add Input):** giữ nguyên ver-11 (7 ver-8 + 2 HOCT).\n\n"
        "**1 code cell:** S1 — monolith (~2.0–2.2h T4×2 public; READMIT/GAPFILL +CPU-phút vô hại trước guard 7.5h).\n\n"
        "**⚠ KHÔNG submit Kaggle khi chưa có lệnh trực tiếp** (luật đứng). v10 banked 0.947 luôn selectable."
    )
    cells = [{"cell_type": "markdown", "id": "ver12-header", "metadata": {},
             "source": to_source_lines(md)}]
    cells.append({"cell_type": "code", "id": "ver12-s1-monolith", "metadata": {},
                  "execution_count": None, "outputs": [],
                  "source": to_source_lines(MONOLITH.read_text())})
    return {"cells": cells,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                        "name": "python3"},
                         "language_info": {"name": "python", "version": "3.11"}},
            "nbformat": 4, "nbformat_minor": 5}


def static_checks() -> None:
    py_compile.compile(str(MONOLITH), doraise=True)
    print("[check] py_compile PASS (ver-12 monolith)")
    text = MONOLITH.read_text()
    required = [
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v12_",
        "os.environ['BIOHUB_SAFE_DIV_ORPHAN_ADOPT']",
        "SAFE_DIV_ORPHAN_ADOPT = os.environ.get(",
        "os.environ['BIOHUB_READMIT_RADIUS_UM']",
        "os.environ['BIOHUB_GAPFILL_MAX_GAP']",
        "os.environ['BIOHUB_LOWDET_THRESHOLD']",
        "os.environ['BIOHUB_LOWDET_DIR']",
        "def readmit_discarded_detections",
        "def fill_gaps_from_low_detections",
        "def load_low_detections",
        "safe_division_orphan_adopted",
        "readmitted_nodes",
        "gapfill_added_nodes",
        "*prop[6:]",
        "phase_h_v12_portfolio",
        "[ver12] LOWDET dump stage installed",
        "os.environ['BIOHUB_HOCT_VETO'] = '1'",
        "os.environ['BIOHUB_HOCT_DEADLINE_H'] = '7.5'",
        "os.environ['BIOHUB_HOCT_MAX_VIDEO_S'] = '300'",
        "os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'",
        "def add_safe_divisions_postlink",
        "def add_reparent_divisions_postlink",
        "_hv_finalize()",
    ]
    for token in required:
        if token not in text:
            sys.exit(f"[check] THIẾU mấu [ver12]: {token}")
    # guard 9 hằng số: 7 gốc nguyên vẹn + 2 theo config
    sef = CFG.get('sef_tta_weight', 0.75)
    dc = CFG.get('dc_safe_div_threshold', 0.20)
    for pair in ("'BIOHUB_DET_THRESHOLD': 0.965", "'BIOHUB_SAFE_DIV_MAX_UM': 9.0",
                 f"'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': {dc}",
                 f"'BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT': {sef}"):
        if pair not in text:
            sys.exit(f"[check] THẤT BẠI: guard {pair}")
    div = CFG.get('safe_div_diverge_um')
    if div is not None and f"os.environ['BIOHUB_SAFE_DIV_DIVERGE_UM'] = '{div}'" not in text:
        sys.exit(f"[check] THẤT BẠI: thiếu env diverge {div}")
    print(f"[check] {len(required)} mấu [ver12] đủ mặt + guard 9 hằng nguyên vẹn theo config")


def verify_notebook(nb: dict) -> None:
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    if sources["ver12-s1-monolith"] != MONOLITH.read_text():
        sys.exit("[verify] cell ver12-s1-monolith KHÁC file nguồn")
    print(f"[verify] cell ver12-s1-monolith == cell-monolith.py ({len(sources['ver12-s1-monolith'].splitlines())} dòng)")
    json.dumps(nb)
    print("[verify] JSON notebook hợp lệ —", OUT.name, f"({len(nb['cells'])} cell)")


def main() -> int:
    static_checks()
    nb = build_notebook()
    verify_notebook(nb)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nĐÃ GHI {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Push (khi được lệnh): /home/z/.venv/bin/python kaggle/api/ktool.py push --ver 12")
    return 0


if __name__ == "__main__":
    sys.exit(main())
