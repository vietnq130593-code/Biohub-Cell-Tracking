"""make-ver8-ipynb.py — Đóng gói notebook ver-8 (Phase D: re-parenting + DivNet RANK-ONLY gate gốc).

Cấu trúc notebook (3 cell):
  [markdown] header — settings T4×2, Internet OFF, 8 nguồn input (như ver-7b)
  [code] S1 monolith — ver-8 (port 0.947 + divnet RANK-ONLY gate production + [ver8] re-parent)
  [code] S2 eval cell — Phase B official-rule A/B (bản đã vá path, exception-safe)

Kiểm thử tĩnh: py_compile + grep mấu tích hợp + source khớp nguyên văn.
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # <project>/kaggle/ver-8/
KAGGLE = ROOT.parent                               # <project>/kaggle/
DOWNLOAD = ROOT.parents[1] / "download"
MONOLITH = ROOT / "cell-monolith.py"
EVAL_CELL = KAGGLE / "eval" / "cell-eval-official.py"
OUT = DOWNLOAD / "ver8-cell-tracking.ipynb"

HEADER_MARKDOWN = """# ver 8 — Biohub Cell Tracking (Phase D: Re-parenting division recovery) — **v3-fast**

**ver-7 (port 0.947, LB đã xác nhận) + [ver8]**: hai cơ chế phân bào song song:

1. **DivNet RANK-ONLY** (giữ NGUYÊN gate production tau 0.6 / diverge 2.25 — khác ver-7b đã thất bại
   vì nới gate): chỉ xếp lại thứ tự đề xuất theo `P(division)` của node mẹ.
2. **RE-PARENTING** (VER8-REPARENT-DESIGN.md): 6/12 sự kiện phân bào GT held-out có CẢ HAI con
   đã detect nhưng con thứ 2 (D2) bị nối nhầm vào node Y. Cơ chế: tháo cạnh yếu `Y→D2` + nối
   `M→D2` khi DivNet + geometry + cạnh hiện tại yếu + DeepCenter đồng thuận.

**[ver8.3-fast] — SỬA LỖI RUNTIME HIDDEN TEST (15/9):** submission v1 (56242181) FAILED vì
rerun trên hidden test (lớn hơn public ~2×) vượt runtime limit — sweep 16-19 candidates chiếm
86% runtime kernel. v3 rút sweep về **1 candidate duy nhất** `ppTight5565fb` (per-prefix
44b6→5.5/6bba→6.5 + fallback global 5.5 cho prefix lạ) → kernel public ~1,3-1,8h → hidden
~2,5-3,6h, an toàn trong hạn. REPARENT_EDGE_PROB giữ 0.25 (v2: mở 0.50/0.75 chỉ thêm FP).

**Settings trước khi Run All**

| Thiết lập | Giá trị |
|---|---|
| Accelerator | **GPU T4 × 2** |
| Internet | **OFF** |

**8 nguồn input (Add Input):** như ver-7b — competition + support-pack + deepcenter + secondary-seed
+ official-scorer + local-cv-pack + v6-heldout-preds + **giorgosi/biohub-divnet-v2**.

**2 code cell:**
- **S1 — monolith** (~1,3-1,8h T4×2 public): ver-8 re-parent + sweep 1 candidate + eval trong run.
- **S2 — Phase B official eval** (exception-safe): self + baseline ver-6 → JSON schema chung.

**Cổng submit v3:** ΔadjEJ ≥ −0.0005 so replay không veto · div_tp ≥ 0 · div_fp ≤ +3 ·
guards 5/5 · runtime public ≤ 2h (BẮT BUỘC — hidden test ~2×).
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
    cells = [{"cell_type": "markdown", "id": "ver8-header", "metadata": {},
             "source": to_source_lines(HEADER_MARKDOWN)}]
    for cell_id, path in (("ver8-s1-monolith", MONOLITH), ("ver8-s2-eval", EVAL_CELL)):
        cells.append({"cell_type": "code", "id": cell_id, "metadata": {},
                      "execution_count": None, "outputs": [],
                      "source": to_source_lines(path.read_text())})
    return {"cells": cells,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                        "name": "python3"},
                         "language_info": {"name": "python", "version": "3.11"}},
            "nbformat": 4, "nbformat_minor": 5}


def static_checks() -> None:
    py_compile.compile(str(MONOLITH), doraise=True)
    py_compile.compile(str(EVAL_CELL), doraise=True)
    print("[check] py_compile PASS (ver-8 monolith + eval cell)")
    text = MONOLITH.read_text()
    hits = [ln for ln in text.splitlines() if "reyhanksatria" in ln]
    if hits:
        sys.exit(f"[check] THẤT BẠI: còn {len(hits)} dòng chứa 'reyhanksatria'")
    print("[check] grep 'reyhanksatria' = 0")
    required = [
        "BIOHUB_REPARENT_ENABLE'] = '1'",
        "def add_reparent_divisions_postlink",
        "edges = add_reparent_divisions_postlink(",
        "reparent_added",
        "REPARENT_MIN_PDIV",
        "def load_divnet_ranker",
        "DIVNET_RANKER = load_divnet_ranker()",
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_v8_3fast'",
        "'REPARENT_MAX_UM', 'REPARENT_SISTER_UM'",
        "phase_d_reparent_division_recovery",
        "ppTight5565fb",
        "[ver8.3-fast]",
    ]
    for token in required:
        if token not in text:
            sys.exit(f"[check] THIẾU mấu tích hợp [ver8]: {token}")
    # gate PHẢI giữ production (khác ver-7b)
    if "BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU'] = '1.2'" in text:
        sys.exit("[check] THẤT BẠI: tau còn 1.2 (phải 0.6 — gate production)")
    if "BIOHUB_SAFE_DIV_DIVERGE_UM'] = '1.0'" in text:
        sys.exit("[check] THẤT BẠI: diverge còn 1.0 (phải 2.25 — gate production)")
    print(f"[check] {len(required)} mấu [ver8/v8.3] đủ mặt + gate production (tau 0.6 / diverge 2.25) OK")
    print(f"[check] số điểm đánh dấu [ver8]: {text.count('[ver8]')} · [ver8.3-fast]: {text.count('[ver8.3-fast]')}")


def verify_notebook(nb: dict) -> None:
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    for cell_id, path in (("ver8-s1-monolith", MONOLITH), ("ver8-s2-eval", EVAL_CELL)):
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
    print("Push: cd kaggle/api && python3 ktool.py push --ver 8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
