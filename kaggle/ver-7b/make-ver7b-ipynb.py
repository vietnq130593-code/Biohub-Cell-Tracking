"""make-ver7b-ipynb.py — Đóng gói notebook ver-7b (Phase C: divnet RANK-ONLY + nới gate).

(Bản tái tạo sau sandbox rollback 13/9 — logic giống hệt bản trước mất file.)

Cấu trúc notebook (3 cell):
  [md]  header — settings T4×2, Internet OFF, 8 nguồn input (thêm giorgosi/biohub-divnet-v2)
  [code] S1 monolith  — ver-7 port 0.947 + [ver7b] divnet ranker + gate widening
  [code] S2 eval cell — Phase B official-rule A/B (giống ver-7, exception-safe)

Kiểm thử tĩnh: py_compile + grep 'reyhanksatria' = 0 + source khớp nguyên văn file.
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # <project>/kaggle/ver-7b/
KAGGLE = ROOT.parent                               # <project>/kaggle/
DOWNLOAD = ROOT.parents[1] / "download"
MONOLITH = ROOT / "cell-monolith.py"
EVAL_CELL = KAGGLE / "eval" / "cell-eval-official.py"
OUT = DOWNLOAD / "ver7b-cell-tracking.ipynb"

HEADER_MARKDOWN = """# ver 7b — Biohub Cell Tracking (Phase C: DivNet division ranker)

**ver-7 (port 0.947) + Phase C**: gắn DivNet division-event ranker (biohub-divnet-v2, **RANK-ONLY**,
W = 15 µm-equivalent) xếp lại đề xuất phân bào theo P(division) của node mẹ + **nới gate có kiểm soát**
(symmetry tau 0.6→1.2, diverge 2.25→1.0). Cơ sở: VER7-PLAN §Phase C + tích hợp chuẩn của tác giả divnet
+ bằng chứng megayak (gate-only = −0.017; rank-only với gate chặt = 65% division không reachable).
Mọi thay đổi so với ver-7 đánh dấu `[ver7b]` trong code.

**Settings trước khi Run All**

| Thiết lập | Giá trị |
|---|---|
| Accelerator | **GPU T4 × 2** |
| Internet | **OFF** |

**8 nguồn input (Add Input):**

| # | Input | Slug | Dùng cho |
|---|---|---|---|
| 1 | Competition | `biohub-cell-tracking-during-development` | dữ liệu train/test |
| 2 | Biohub Tracking Support Pack (pilkwang) | `biohub-tracking-support-pack-50ep-v1` | weights chính + repo inference |
| 3 | Biohub DeepCenterUNet3D Center Prior V1 (pilkwang) | `biohub-deepcenter-unet3d-center-prior-v1` | DeepCenter veto |
| 4 | Biohub TemporalUNet3D Seed 314159 V1 (pilkwang) | `biohub-temporal-unet3d-seed314159-v1` | secondary seed |
| 5 | Biohub Official Scorer Patched (dalloliogm) | `biohub-official-scorer-patched` | Phase B — scorer 075fc5f đúng luật thật |
| 6 | Biohub Local CV Pack (dariushafshar) | `biohub-local-cv-pack` | Phase B — folds/ground-truth stats đối chiếu |
| 7 | Biohub V6 Heldout Preds (vietnguyen130593) | `biohub-v6-heldout-preds` | Phase B — baseline ver-6 (4 .geff raw deterministic) |
| 8 | **Biohub DivNet V2 (giorgosi)** | `biohub-divnet-v2` | **Phase C — division ranker (best_overall.pt)** |

**2 code cell:**
- **S1 — monolith pipeline + divnet** (~45–60 phút T4×2): như ver-7 + rerank đề xuất phân bào
  `score = parent + 0.15×sister − 15×P_div(mẹ)`; nới gate tau/diverge; giữ nguyên toàn bộ PPSWEEP
  (chọn hậu xử lý trên held-out với MAX_ADJ_LOSS=0.0005 — lớp kiểm soát adjEJ).
- **S2 — Phase B official eval** (exception-safe): official scorer cho self + baseline ver-6
  → `eval_report_official_self.json` / `eval_report_official_v6.json` + preview A/B trong log.

Sau run: local `compare.py --gate adj:0.942 --gate proxy:0.945`. Chỉ submit khi verdict ≥ LIKELY-UPGRADE.
"""


def to_source_lines(text: str) -> list[str]:
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
    cells = [
        {
            "cell_type": "markdown",
            "id": "ver7b-header",
            "metadata": {},
            "source": to_source_lines(HEADER_MARKDOWN),
        }
    ]
    for cell_id, path in (("ver7b-s1-monolith", MONOLITH),
                          ("ver7b-s2-eval", EVAL_CELL)):
        cells.append(
            {
                "cell_type": "code",
                "id": cell_id,
                "metadata": {},
                "execution_count": None,
                "outputs": [],
                "source": to_source_lines(path.read_text()),
            }
        )
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def static_checks() -> None:
    for path in (MONOLITH, EVAL_CELL):
        py_compile.compile(str(path), doraise=True)
    print("[check] py_compile PASS (monolith 7b + eval cell)")

    text = MONOLITH.read_text()
    hits = [ln for ln in text.splitlines() if "reyhanksatria" in ln]
    if hits:
        sys.exit(f"[check] THẤT BẠI: còn {len(hits)} dòng chứa 'reyhanksatria'")
    print("[check] grep 'reyhanksatria' = 0")

    # các mấu tích hợp [ver7b] phải đủ mặt
    required = [
        "BIOHUB_DIVNET_RANK_W_UM'] = '15.0'",
        "BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU'] = '1.2'",
        "BIOHUB_SAFE_DIV_DIVERGE_UM'] = '1.0'",
        "def load_divnet_ranker",
        "def _divnet_rerank_proposals",
        "divnet_bundle = divnet_bundle",
        "DIVNET_RANKER = load_divnet_ranker()",
        "'DIVNET_'",
    ]
    for token in required:
        if token not in text:
            sys.exit(f"[check] THIẾU mấu tích hợp: {token}")
    print(f"[check] {len(required)} mấu tích hợp [ver7b] đủ mặt")
    n_marks = text.count("[ver7b]")
    print(f"[check] số điểm đánh dấu [ver7b] trong code: {n_marks}")


def verify_notebook(nb: dict) -> None:
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    for cell_id, path in (("ver7b-s1-monolith", MONOLITH), ("ver7b-s2-eval", EVAL_CELL)):
        if sources[cell_id] != path.read_text():
            sys.exit(f"[verify] cell {cell_id} KHÁC file nguồn {path}")
        print(f"[verify] cell {cell_id} == {path.name} ({len(sources[cell_id].splitlines())} dòng)")
    json.loads(json.dumps(nb))
    print("[verify] JSON notebook hợp lệ —", OUT.name, f"({len(nb['cells'])} cell)")


def main() -> int:
    static_checks()
    nb = build_notebook()
    verify_notebook(nb)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nĐÃ GHI {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Push: cd kaggle/api && python3 ktool.py push --ver 7b")
    return 0


if __name__ == "__main__":
    sys.exit(main())
