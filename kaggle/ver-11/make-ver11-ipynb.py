#!/usr/bin/env python3
"""make-ver11-ipynb.py — Đóng gói notebook ver-11 (Phase G: mutual_nn-off + MIN_PDIV floor).

Cấu trúc notebook (2 cell, giống ver-10):
  [markdown] header — settings T4×2, Internet OFF, 9 nguồn input (giữ nguyên ver-10)
  [code] S1 monolith — ver-11 (ver-10 + [ver11] gate division theo grid v11-lab v3)

Kiểm thử tĩnh: py_compile + mấu tích hợp ver-11 + source khớp nguyên văn.
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOAD = ROOT.parents[1] / "download"
MONOLITH = ROOT / "cell-monolith.py"
OUT = DOWNLOAD / "ver11-cell-tracking.ipynb"
CFG = json.loads((ROOT / "ver-11-config.json").read_text())


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
        "# ver 11 — Biohub Cell Tracking (Phase G: mutual_nn-off + SAFE_DIV_MIN_PDIV floor)\n\n"
        "**Nền ver-10** (LB 0.947: v3-fast + HOCT veto mode 1 + density guard) **+ mở gate\n"
        "division theo GRID v11-lab v3** (kernel `biohub-v11-lab` v4, 20/9 — replay 8 stems\n"
        "validator từ cache, config thắng theo D-gates):\n\n"
        f"- SAFE_DIV_REQUIRE_MUTUAL_NN = {'ON' if CFG.get('mutual_nn', True) else 'OFF'}\n"
        f"- SAFE_DIV_MIN_PDIV = {CFG.get('min_pdiv')}\n"
        f"- SAFE_DIV_DIVERGE_UM = {CFG.get('diverge_um') or '(giữ 2.25)'}\n"
        f"- DIV_SISTER_MAX_UM = {CFG.get('div_sister_max_um') or '(giữ 8.0)'}\n\n"
        "Cơ sở: funnel B-6 dump v2 — 9 FN = 7 no_proposal + 2 mutual_nn (trần div_tp +2);\n"
        "van FP B-7: pool mutual_nn-blocked 319 → 46 (floor 0.5) / 39 (floor 0.85).\n\n"
        "**Settings trước khi Run All**\n\n"
        "| Thiết lập | Giá trị |\n|---|---|\n| Accelerator | **GPU T4 × 2** |\n| Internet | **OFF** |\n\n"
        "**9 nguồn input (Add Input):** giữ nguyên ver-10 (7 ver-8 + 2 HOCT).\n\n"
        "**1 code cell:** S1 — monolith (~2.0–2.2h T4×2 public).\n"
    )
    cells = [{"cell_type": "markdown", "id": "ver11-header", "metadata": {},
             "source": to_source_lines(md)}]
    cells.append({"cell_type": "code", "id": "ver11-s1-monolith", "metadata": {},
                  "execution_count": None, "outputs": [],
                  "source": to_source_lines(MONOLITH.read_text())})
    return {"cells": cells,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                        "name": "python3"},
                         "language_info": {"name": "python", "version": "3.11"}},
            "nbformat": 4, "nbformat_minor": 5}


def static_checks() -> None:
    py_compile.compile(str(MONOLITH), doraise=True)
    print("[check] py_compile PASS (ver-11 monolith)")
    text = MONOLITH.read_text()
    required = [
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v11_",
        "os.environ['BIOHUB_SAFE_DIV_REQUIRE_MUTUAL_NN']",
        "os.environ['BIOHUB_SAFE_DIV_MIN_PDIV']",
        "SAFE_DIV_MIN_PDIV = float(",
        "safe_division_min_pdiv_rejected",
        "phase_g_v11_mutualnn_pdiv",
        "[ver11] Phase G",
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
            sys.exit(f"[check] THIẾU mấu [ver11]: {token}")
    # gate production khác phải giữ nguyên (B-1 guard không đổi)
    if "'BIOHUB_SAFE_DIV_MAX_UM': 9.0" not in text:
        sys.exit("[check] THẤT BẠI: guard SAFE_DIV_MAX_UM phải 9.0")
    if "'BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD': 0.20" not in text:
        sys.exit("[check] THẤT BẠI: guard DC phải 0.20")
    print(f"[check] {len(required)} mấu [ver11] đủ mặt + guard nguyên vẹn")


def verify_notebook(nb: dict) -> None:
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    if sources["ver11-s1-monolith"] != MONOLITH.read_text():
        sys.exit("[verify] cell ver11-s1-monolith KHÁC file nguồn")
    print(f"[verify] cell ver11-s1-monolith == cell-monolith.py ({len(sources['ver11-s1-monolith'].splitlines())} dòng)")
    json.dumps(nb)
    print("[verify] JSON notebook hợp lệ —", OUT.name, f"({len(nb['cells'])} cell)")


def main() -> int:
    static_checks()
    nb = build_notebook()
    verify_notebook(nb)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nĐÃ GHI {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Push: /home/z/.venv/bin/python kaggle/api/ktool.py push --ver 11")
    return 0


if __name__ == "__main__":
    sys.exit(main())
