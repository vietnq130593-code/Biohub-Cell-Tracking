"""make-ver10-ipynb.py — Đóng gói notebook ver-10 (Phase F: HOCT veto MODE 1 + guard mật độ).

Cấu trúc notebook (2 cell — KHÔNG S2 eval cell, strip validator replay theo V10-RESULTS §6):
  [markdown] header — settings T4×2, Internet OFF, 9 nguồn input (7 của ver-8 + 2 HOCT)
  [code] S1 monolith — ver-10 (v3-fast + [ver10-hoct] veto mode 1 + density guard)

Kiểm thử tĩnh: py_compile + mấu tích hợp ver-10 + source khớp nguyên văn.
"""
import json
import py_compile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent            # <project>/kaggle/ver-10/
DOWNLOAD = ROOT.parents[1] / "download"
MONOLITH = ROOT / "cell-monolith.py"
OUT = DOWNLOAD / "ver10-cell-tracking.ipynb"

HEADER_MARKDOWN = """# ver 10 — Biohub Cell Tracking (Phase F: HOCT consensus veto mode 1 — division-safe)

**Nền v3-fast** (ver-8 re-parent + DivNet RANK-ONLY + hardcode tight per-prefix 5.5/6.5,
KHÔNG sweep) **+ 1 đòn duy nhất theo V10-LAB 17/9** (kernel `v10-lab-gpu-t4`, 8 stems
T4×2, grid 9 configs):

**HOCT consensus veto MODE 1** (port sjlee101/biohub-lf-hoctveto): sau post-process, HOCT
general_v0 (royerlab, 6.25M params) chạy trên đúng node set FINAL mỗi video test — mọi
cạnh KHÔNG-phân-bào mà HOCT không đề xuất bị bỏ; **cả 2 cạnh của mọi node cha ≥ 2 con
(division) được giữ nguyên** (khác mode 2 của ver-9 đã mất 1 div_tp). Kết quả lab:
**adjEJ +0.001828 · proxy +0.001828 (duy nhất dương) · division 4/1/8 nguyên vẹn.**

**Guard chống TLE (bài học ver-9 fail hidden runtime)**: cap 300s/video (từ 900) ·
deadline 7.5h (từ 10.5) · ước lượng density-aware `k·n·d_max + 50s` (k = 2.2e-5, hiệu
chuẩn 8 stems T4×2; ×3 khi d_max > 550 nodes/frame — vùng ngoài hiệu chuẩn đã giết ver-9) ·
abort giữa video ở biên chunk khi qua deadline. Fail-safe một chiều: HOCT hỏng / vượt
guard → video pass-through giữ graph gốc → kernel LUÔN hoàn tất trong hạn.

**Đã strip theo khuyến nghị**: RLF (Δ 0.000000 trên lab — vô nghĩa) · gate/validator
replay của ver-9 (~45' public ×5-7 hidden) · S2 eval cell → public ~2.0–2.2h.

**Settings trước khi Run All**

| Thiết lập | Giá trị |
|---|---|
| Accelerator | **GPU T4 × 2** |
| Internet | **OFF** |

**9 nguồn input (Add Input):** 7 của ver-8 (competition + support-pack + deepcenter +
secondary-seed + official-scorer + local-cv-pack + v6-heldout-preds + giorgosi/biohub-divnet-v2)
**+ sjlee101/biohub-hoct-020-wheels + musculer/biohub-hoct-general-v0-official**.

**1 code cell:**
- **S1 — monolith** (~2.0–2.2h T4×2 public; hidden ~4–5h < 12h với guard): pipeline 0.947
  + re-parent + veto mode 1 + density guard trong run.

**Cơ sở quyết định:** V10-RESULTS.md (17/9) — gates D1-D3 PASS (replay deterministic khớp
ver-9 gate 6 chữ số; veto1 ΔadjEJ +0.0018 ≥ +0.0010; div_tp giữ nguyên), D4 vá bằng guard
mật độ, D5 FAIL (RLF/tight chết → bỏ). Kỳ vọng transfer: LB 0.949±0.001 nếu +0.0018 giữ
nguyên trên hidden → vượt cụm 0.948 → hạng ~89–143 (bạc chắc chắn + mở đường 0.949).
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
    cells = [{"cell_type": "markdown", "id": "ver10-header", "metadata": {},
             "source": to_source_lines(HEADER_MARKDOWN)}]
    cells.append({"cell_type": "code", "id": "ver10-s1-monolith", "metadata": {},
                  "execution_count": None, "outputs": [],
                  "source": to_source_lines(MONOLITH.read_text())})
    return {"cells": cells,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python",
                                        "name": "python3"},
                         "language_info": {"name": "python", "version": "3.11"}},
            "nbformat": 4, "nbformat_minor": 5}


def static_checks() -> None:
    py_compile.compile(str(MONOLITH), doraise=True)
    print("[check] py_compile PASS (ver-10 monolith)")
    text = MONOLITH.read_text()
    hits = [ln for ln in text.splitlines() if "reyhanksatria" in ln]
    if hits:
        sys.exit(f"[check] THẤT BẠI: còn {len(hits)} dòng chứa 'reyhanksatria'")
    print("[check] grep 'reyhanksatria' = 0")
    required = [
        "EXPERIMENT_TAG = 'secondary_deepcenter_tta_0947_reparent_hoct_v10'",
        "os.environ['BIOHUB_HOCT_VETO'] = '1'",
        "os.environ['BIOHUB_HOCT_DEADLINE_H'] = '7.5'",
        "os.environ['BIOHUB_HOCT_MAX_VIDEO_S'] = '300'",
        "os.environ['BIOHUB_MOTION_RELINK_TIGHT_UM'] = '5.5'",
        "PP_CANDIDATES: dict[str, dict] = {}",
        "[ver10-hoct] HOCT consensus veto",
        "class _hvDeadlineAbort",
        "def _hv_apply_veto",
        "def _hv_install_hook",
        "_hv_finalize()",
        "_HV_K_ND = 2.2e-5",
        "_HV_DENSITY_CAL = 550.0",
        "aborted_deadline",
        "phase_f_hoct_veto1_v10",
        "def add_reparent_divisions_postlink",
        "def load_divnet_ranker",
    ]
    for token in required:
        if token not in text:
            sys.exit(f"[check] THIẾU mấu tích hợp [ver10]: {token}")
    for forbidden in ("[ver9-rlf]", "[ver9-gate]", "ver9_rlf_edges", "ver9_score_final",
                      "VER9_GATE", "BIOHUB_RLF_ENABLE"):
        if forbidden in text:
            sys.exit(f"[check] CÒN SÓT của ver-9: {forbidden}")
    # gate PHẢI giữ production (khác ver-7b) + cấu hình re-parent giữ v1/v2
    if "BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU'] = '1.2'" in text:
        sys.exit("[check] THẤT BẠI: tau còn 1.2 (phải 0.6 — gate production)")
    if "BIOHUB_SAFE_DIV_DIVERGE_UM'] = '1.0'" in text:
        sys.exit("[check] THẤT BẠI: diverge còn 1.0 (phải 2.25 — gate production)")
    if "BIOHUB_REPARENT_EDGE_PROB'] = '0.5'" in text or "BIOHUB_REPARENT_EDGE_PROB'] = '0.75'" in text:
        sys.exit("[check] THẤT BẠI: REPARENT_EDGE_PROB phải giữ 0.25 (v2 chứng minh mở chỉ thêm FP)")
    print(f"[check] {len(required)} mấu [ver10] đủ mặt + strip ver-9 sạch + gate production (tau 0.6 / diverge 2.25 / ep 0.25) OK")
    print(f"[check] số điểm đánh dấu: [ver10] = {text.count('[ver10]')} · [ver9] = {text.count('[ver9]')} · [ver8] = {text.count('[ver8]')}")


def verify_notebook(nb: dict) -> None:
    sources = {c["id"]: "".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"}
    if sources["ver10-s1-monolith"] != MONOLITH.read_text():
        sys.exit("[verify] cell ver10-s1-monolith KHÁC file nguồn")
    print(f"[verify] cell ver10-s1-monolith == cell-monolith.py ({len(sources['ver10-s1-monolith'].splitlines())} dòng)")
    if any(c["id"] == "ver10-s2-eval" for c in nb["cells"]):
        sys.exit("[verify] THẤT BẠI: không được có S2 eval cell (strip validator replay)")
    json.loads(json.dumps(nb))
    print("[verify] JSON notebook hợp lệ —", OUT.name, f"({len(nb['cells'])} cell)")


def main() -> int:
    static_checks()
    nb = build_notebook()
    verify_notebook(nb)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nĐÃ GHI {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")
    print("Push: cd kaggle/api && python3 ktool.py push --ver 10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
