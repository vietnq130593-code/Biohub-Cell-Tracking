"""make-wave1-ipynb.py — Đóng gói notebook WAVE-1 (mini-kernel CPU, 0 GPU quota).

Cấu trúc notebook (2 cell):
  [markdown] header — settings CPU, Internet OFF, 6 nguồn input
  [code]      wave1-sweep.py (đã build bởi build-wave1.py — slices nguyên văn
              ver-7b + driver [wave1]) — E0 gate-audit/grid + E1 system-view
              official + E2 PPSWEEP-2 + E3 chẩn đoán 2 video xấu.

Kiểm thử tĩnh: py_compile file nguồn + đếm cell + source khớp nguyên văn.
"""
import json
import py_compile
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent            # <project>/kaggle/ver-8-planning/
KAGGLE = HERE.parent                               # <project>/kaggle/
DOWNLOAD = HERE.parents[1] / "download"
SWEEP = HERE / "wave1" / "wave1-sweep.py"
OUT = DOWNLOAD / "ver8-wave1.ipynb"

HEADER_MARKDOWN = """# ver-8 WAVE-1 — Gate-audit + PPSWEEP-2 + System-view eval (CPU, 0 GPU)

Mini-kernel CPU thực hiện 4 thí nghiệm E-series từ VER8-RESEARCH (không tốn GPU quota):

- **E1 — system-view official eval**: chạy postprocess production ver-7 (+ selected tight55/dcgap035)
  trên 8 .geff held-out raw → ghi .geff hệ → chấm bằng official scorer 075fc5f → la bàn không đọc đôi.
- **E0 — gate audit + grid DivNet v2**: thu TOÀN BỘ đặc trưng từng cặp (mẹ, con mồ côi) với gate
  rộng nhất (frame-cache + deepcenter-cache + divnet-cache dùng chung) → replay 15 tổ hợp gate ×
  rank (tau 0.6–1.0, diverge 2.25–1.0, MAX 9–12, W 15–25, P_div floor 0.3–0.5) + self-check
  replay == verbatim + chẩn đoán từng sự kiện GT division (gate nào giết nó).
- **E2 — PPSWEEP-2**: 18 config toàn cục + 2 per-prefix (6bba vs 44b6) × full pipeline,
  official cho top-3 đạt guards.
- **E3 — chẩn đoán 2 video xấu nhất** (6bba_07e24132 0.820 / 44b6_267148e4 0.851).

**Settings trước khi Run All**

| Thiết lập | Giá trị |
|---|---|
| Accelerator | **CPU** (không GPU) |
| Internet | **OFF** |

**6 nguồn input (Add Input):**

| # | Input | Slug | Dùng cho |
|---|---|---|---|
| 1 | Competition | `biohub-cell-tracking-during-development` | GT train .geff + zarr frames |
| 2 | Support Pack (pilkwang) | `biohub-tracking-support-pack-50ep-v1` | wheel offline (tracksdata/zarr/…) |
| 3 | Official Scorer Patched (dalloliogm) | `biohub-official-scorer-patched` | scorer 075fc5f đúng luật thật |
| 4 | V7 Heldout Preds (vietnguyen130593) | `biohub-v7-heldout-preds` | 8 .geff raw core view của ver-7 |
| 5 | DeepCenter (pilkwang) | `biohub-deepcenter-unet3d-center-prior-v1` | DeepCenter veto (CPU) |
| 6 | DivNet V2 (giorgosi) | `biohub-divnet-v2` | ranker P(division) (CPU) |

**Output**: `wave1_summary.json` + `wave1_e0_grid.csv` + `wave1_e0_grid_official.json`
+ `wave1_e1_system_eval.json` + `wave1_e0_div_diagnostics.json` + `wave1_e2_ppsweep2*.csv/json`
+ `wave1_e3_badvideos.json`.

> Code postprocess/scoring là **slice nguyên văn** từ monolith ver-7b (đã chạy 0.947);
> code mới đánh dấu `[wave1]`. Runtime ước tính 2,5–4 h CPU; deadline nội bộ 8,5 h tự bỏ qua
> phần còn lại.
"""


def main() -> int:
    py_compile.compile(str(SWEEP), doraise=True)
    code = SWEEP.read_text()
    nb = {
        "cells": [
            {"cell_type": "markdown", "metadata": {}, "source": HEADER_MARKDOWN},
            {"cell_type": "code", "execution_count": None, "metadata": {},
             "outputs": [], "source": code},
        ],
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4, "nbformat_minor": 5,
    }
    OUT.write_text(json.dumps(nb, indent=1) + "\n")
    print(f"ĐÃ GHI {OUT}")
    # kiểm tra: đọc lại + source cell 1 khớp nguyên văn
    nb2 = json.loads(OUT.read_text())
    assert len(nb2["cells"]) == 2
    assert nb2["cells"][1]["source"] == code, "source cell không khớp nguyên văn!"
    print(f"cells=2, code={len(code.splitlines())} dòng — khớp nguyên văn. OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
