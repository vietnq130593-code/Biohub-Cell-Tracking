"""make-ver7-ipynb.py — Đóng gói notebook ver-7 (Phase A + Phase B).

Cấu trúc notebook (3 cell):
  [md]  header — settings T4×2, Internet OFF, 7 nguồn input
  [code] S1 monolith  — port Reyhan 0.947 (ver-7/cell-monolith.py, chỉ vá 5 dòng env path)
  [code] S2 eval cell  — Phase B official-rule A/B (eval/cell-eval-official.py, exception-safe)

Kiểm thử tĩnh kèm theo:
  1. py_compile cả 2 cell
  2. grep 'reyhanksatria' = 0 (không sót path dataset riêng)
  3. JSON notebook hợp lệ + source cell khớp NGUYÊN VĂN file nguồn

(Ghi chú 13/9: tái tạo sau sandbox rollback — monolith + eval cell đã khôi phục
byte-exact từ kernel vietnguyen130593/biohub-ver7 v1 qua `kernels pull`.)
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # <project>/kaggle/ver-7/
KAGGLE = ROOT.parent                               # <project>/kaggle/
DOWNLOAD = ROOT.parents[1] / "download"             # <project>/download/
MONOLITH = ROOT / "cell-monolith.py"
EVAL_CELL = KAGGLE / "eval" / "cell-eval-official.py"
OUT = DOWNLOAD / "ver7-cell-tracking.ipynb"

HEADER_MARKDOWN = """# ver 7 — Biohub Cell Tracking (port 0.947 + official-rule eval)

**Port nguyên văn notebook public LB 0.947** (monolith 1 cell, `EXPERIMENT_TAG='secondary_deepcenter_tta_0947'`)
— chỉ vá 5 dòng env path (dataset riêng của tác giả → pilkwang public, SHA256 đã đối chứng khớp 100%).

**Settings trước khi Run All**

| Thiết lập | Giá trị |
|---|---|
| Accelerator | **GPU T4 × 2** |
| Internet | **OFF** |

**7 nguồn input (Add Input):**

| # | Input | Slug | Dùng cho |
|---|---|---|---|
| 1 | Competition | `biohub-cell-tracking-during-development` | dữ liệu train/test |
| 2 | Biohub Tracking Support Pack (pilkwang) | `biohub-tracking-support-pack-50ep-v1` | weights chính + repo inference |
| 3 | Biohub DeepCenterUNet3D Center Prior V1 (pilkwang) | `biohub-deepcenter-unet3d-center-prior-v1` | DeepCenter veto |
| 4 | Biohub TemporalUNet3D Seed 314159 V1 (pilkwang) | `biohub-temporal-unet3d-seed314159-v1` | secondary seed |
| 5 | Biohub Official Scorer Patched (dalloliogm) | `biohub-official-scorer-patched` | Phase B — scorer 075fc5f đúng luật thật |
| 6 | Biohub Local CV Pack (dariushafshar) | `biohub-local-cv-pack` | Phase B — folds/ground-truth stats đối chiếu |
| 7 | Biohub V6 Heldout Preds (vietnguyen130593) | `biohub-v6-heldout-preds` | Phase B — baseline ver-6 (4 .geff raw deterministic) |

**2 code cell:**
- **S1 — monolith pipeline** (~40–50 phút T4×2): dual-seed + edge-feature TTA 8-view + secondary TTA +
  DeepCenter spatial TTA + safe-div 0.20 + PPSWEEP chọn hậu xử lý trên held-out → `submission.csv`.
- **S2 — Phase B official eval** (exception-safe, KHÔNG đụng pipeline): chấm predictions held-out bằng
  official scorer 075fc5f cho CẢ ver-7 (self) và baseline ver-6 → in preview A/B + ghi
  `eval_report_official_self.json` / `eval_report_official_v6.json`. Lỗi eval không làm run ERROR.

Sau run: kéo output về (`ktool output`), rồi local `compare.py --gate adj:0.942 --gate proxy:0.945`
xem README `kaggle/eval/`. Chỉ submit khi verdict ≥ LIKELY-UPGRADE và gate đạt.
"""


def to_source_lines(text: str) -> list[str]:
    """Chuyển text → list source chuẩn nbformat (mỗi dòng có \\n, trừ dòng cuối)."""
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
            "id": "ver7-header",
            "metadata": {},
            "source": to_source_lines(HEADER_MARKDOWN),
        }
    ]
    for cell_id, path in (("ver7-s1-monolith", MONOLITH),
                          ("ver7-s2-eval", EVAL_CELL)):
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
    # 1. py_compile cả 2 cell nguồn
    for path in (MONOLITH, EVAL_CELL):
        py_compile.compile(str(path), doraise=True)
    print("[check] py_compile PASS (monolith + eval cell)")

    # 2. không sót path dataset riêng của tác giả
    text = MONOLITH.read_text()
    hits = [ln for ln in text.splitlines() if "reyhanksatria" in ln]
    if hits:
        sys.exit(f"[check] THẤT BẠI: còn {len(hits)} dòng chứa 'reyhanksatria': {hits[:3]}")
    print("[check] grep 'reyhanksatria' = 0 — chỉ dùng path pilkwang public")

    # 3. không dùng Internet (không có URL ngoài trong code)
    for pat in ("http://", "https://"):
        if pat in text or pat in EVAL_CELL.read_text():
            bad = [ln for ln in text.splitlines() if pat in ln and not ln.strip().startswith("#")]
            if bad:
                sys.exit(f"[check] THẤT BẠI: cell code chứa URL {pat!r}: {bad[:3]}")
    print("[check] không URL ngoài trong code — an toàn Internet OFF")


def verify_notebook(nb: dict) -> None:
    # source cell khớp NGUYÊN VĂN file nguồn
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    pairs = [("ver7-s1-monolith", MONOLITH), ("ver7-s2-eval", EVAL_CELL)]
    for cell_id, path in pairs:
        expect = path.read_text()
        got = sources[cell_id]
        if got != expect:
            sys.exit(f"[verify] cell {cell_id} KHÁC file nguồn {path} — kiểm tra to_source_lines!")
        print(f"[verify] cell {cell_id} == {path.name} ({len(got.splitlines())} dòng, khớp nguyên văn)")

    # JSON round-trip
    json.loads(json.dumps(nb))
    print("[verify] JSON notebook hợp lệ —", OUT.name, f"({len(nb['cells'])} cell)")


def main() -> int:
    static_checks()
    nb = build_notebook()
    verify_notebook(nb)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nĐÃ GHI {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Push: cd kaggle/api && python3 ktool.py push --ver 7")
    return 0


if __name__ == "__main__":
    sys.exit(main())
