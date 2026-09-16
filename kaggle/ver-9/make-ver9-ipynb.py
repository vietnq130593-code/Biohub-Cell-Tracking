"""make-ver9-ipynb.py — Đóng gói notebook ver-9 (Phase E: HOCT veto mode 2 + RLF).

Cấu trúc notebook (3 cell):
  [markdown] header — settings T4×2, Internet OFF, 9 nguồn input (7 của ver-8 + 2 HOCT)
  [code] S1 monolith — ver-9 (v3-fast + [ver9-hoct] veto + [ver9-rlf] + [ver9-gate])
  [code] S2 eval cell — Phase B official-rule A/B (giữ nguyên ver-8, exception-safe)

Kiểm thử tĩnh: py_compile + mấu tích hợp ver-9 + source khớp nguyên văn.
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # <project>/kaggle/ver-9/
KAGGLE = ROOT.parent                               # <project>/kaggle/
DOWNLOAD = ROOT.parents[1] / "download"
MONOLITH = ROOT / "cell-monolith.py"
EVAL_CELL = KAGGLE / "eval" / "cell-eval-official.py"
OUT = DOWNLOAD / "ver9-cell-tracking.ipynb"

HEADER_MARKDOWN = """# ver 9 — Biohub Cell Tracking (Phase E: HOCT consensus veto + repeat-lineage filter)

**Nền v3-fast** (ver-8 re-parent + DivNet RANK-ONLY + hardcode tight per-prefix 5.5/6.5,
**KHÔNG sweep** — v1/56242181 fail hidden-test runtime vì sweep chiếm 86% kernel) **+ 2 đòn mới**:

1. **HOCT consensus veto mode 2** (port nguyên văn cell 6 sjlee101/biohub-lf-hoctveto-div-b):
   sau post-process, HOCT general_v0 (royerlab, 6.25M params) chạy trên đúng node set FINAL
   mỗi video test — mọi cạnh (kể cả cạnh division) mà HOCT không đề xuất bị bỏ. sjlee đo
   20 video honest: **+0.0040 [+0.0006, +0.0058]**, false divisions 55→29. Fail-safe một
   chiều: HOCT hỏng → video pass-through giữ graph gốc; deadline 10.5h; cap 900s/video.
2. **Repeat-lineage filter (RLF)** (port cell 10.5 pawanmali divfix): fork có tổ tiên cũng
   fork → bỏ cạnh con XA hơn. GT thật 0/132 divisions lặp lineage. Guard ≤ 0.5% cạnh,
   vượt thì hoàn tác. Chạy SAU veto.

**[ver9-gate]**: eval system-view official SAU veto+RLF trên 8 stems held-out (ref = v3-fast
không veto) → `ver9_gate_report.json` với 6 cổng an toàn + ELEVEN → verdict
SUBMIT / SUBMIT_SAFE / FALLBACK_V3FAST (cổng §6 rev-2 VER9-RESEARCH.md).

**Settings trước khi Run All**

| Thiết lập | Giá trị |
|---|---|
| Accelerator | **GPU T4 × 2** |
| Internet | **OFF** |

**9 nguồn input (Add Input):** 7 của ver-8 (competition + support-pack + deepcenter +
secondary-seed + official-scorer + local-cv-pack + v6-heldout-preds + giorgosi/biohub-divnet-v2)
**+ sjlee101/biohub-hoct-020-wheels + musculer/biohub-hoct-general-v0-official**.

**2 code cell:**
- **S1 — monolith** (~2,5-3h T4×2 public; hidden ~4-5h < 12h an toàn): pipeline 0.947 + re-parent
  + veto + RLF + gate report trong run.
- **S2 — Phase B official eval** (exception-safe): self (đã gồm veto+RLF) vs baseline ver-6.

**Cổng submit §6 rev-2:** ΔadjEJ ≥ −0.0005 · div_tp(veto2)==div_tp(ref) · div_fp(veto2) ≤ div_fp(ref)
· div_fp(veto2rlf) ≤ +3 · RLF ≤ 0.5% cạnh · ELEVEN Δproxy ≥ +0.005.
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
    cells = [{"cell_type": "markdown", "id": "ver9-header", "metadata": {},
             "source": to_source_lines(HEADER_MARKDOWN)}]
    for cell_id, path in (("ver9-s1-monolith", MONOLITH), ("ver9-s2-eval", EVAL_CELL)):
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
    print("[check] py_compile PASS (ver-9 monolith + eval cell)")
    text = MONOLITH.read_text()
    hits = [ln for ln in text.splitlines() if "reyhanksatria" in ln]
    if hits:
        sys.exit(f"[check] THẤT BẠI: còn {len(hits)} dòng chứa 'reyhanksatria'")
    print("[check] grep 'reyhanksatria' = 0")
    required = [
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v9'",
        "os.environ['BIOHUB_HOCT_VETO'] = '2'",
        "os.environ['BIOHUB_HOCT_DEADLINE_H'] = '10.5'",
        "os.environ['BIOHUB_RLF_ENABLE'] = '1'",
        "os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'",
        "PP_CANDIDATES: dict[str, dict] = {}",
        "def _hv_apply_veto",
        "def _hv_install_hook",
        "_hv_finalize()",
        "[ver9-rlf] Repeat-lineage division filter",
        "RLF_GUARD_REVERT",
        "[ver9-gate] System-view official eval",
        "ver9_gate_report.json",
        "def ver9_score_final",
        "VER9_GATE_RESULT",
        "phase_e_hoct_veto_rlf_v9",
        "def add_reparent_divisions_postlink",
        "def load_divnet_ranker",
    ]
    for token in required:
        if token not in text:
            sys.exit(f"[check] THIẾU mấu tích hợp [ver9]: {token}")
    # gate PHẢI giữ production (khác ver-7b) + cấu hình re-parent giữ v1
    if "BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU'] = '1.2'" in text:
        sys.exit("[check] THẤT BẠI: tau còn 1.2 (phải 0.6 — gate production)")
    if "BIOHUB_SAFE_DIV_DIVERGE_UM'] = '1.0'" in text:
        sys.exit("[check] THẤT BẠI: diverge còn 1.0 (phải 2.25 — gate production)")
    if "BIOHUB_REPARENT_EDGE_PROB'] = '0.5'" in text or "BIOHUB_REPARENT_EDGE_PROB'] = '0.75'" in text:
        sys.exit("[check] THẤT BẠI: REPARENT_EDGE_PROB phải giữ 0.25 (v2 chứng minh mở chỉ thêm FP)")
    print(f"[check] {len(required)} mấu [ver9] đủ mặt + gate production (tau 0.6 / diverge 2.25 / ep 0.25) OK")
    print(f"[check] số điểm đánh dấu: [ver9] = {text.count('[ver9]')} · [ver8] = {text.count('[ver8]')} · [ver8.3-fast] = {text.count('[ver8.3-fast]')}")


def verify_notebook(nb: dict) -> None:
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    for cell_id, path in (("ver9-s1-monolith", MONOLITH), ("ver9-s2-eval", EVAL_CELL)):
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
    print("Push: cd kaggle/api && python3 ktool.py push --ver 9")
    return 0


if __name__ == "__main__":
    sys.exit(main())
