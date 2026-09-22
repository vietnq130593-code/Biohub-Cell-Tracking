# V13-DEPLOY — Runbook vận hành (chờ lệnh trực tiếp user cho mọi bước Kaggle/GPU)

> Đồng bộ V12-DEPLOY discipline · GPU-WASTE-PREVENTION §0/L8 · 22/9/2026
> Kiến trúc chi tiết: `ver-13-planning/V13-ARCHITECTURE.md` (READ FIRST).

## Trạng thái hiện tại (22/9)

| Mục | Trạng thái |
|---|---|
| Code port P1-P4 | ✅ build PASS · determinism PASS (md5 f35ae16f) · selftest v13lab PASS |
| Notebook | ✅ download/ver13-cell-tracking.ipynb 362KB (cell == monolith byte-exact) |
| ktool / submit-v13 | ✅ resolve ver-13 (9 dataset · slug biohub-ver13) · py_compile PASS |
| Sweep census-only 6 arm | ✅ G3/G5 PASS (bảng dưới) — Δ điểm CHƯA có (GT chưa restore) |
| Kaggle action | ❌ 0 push · 0 submit (luật đứng) |
| GPU sổ | 15.85h/30h còn |

## Bước 2 (chờ duyệt) — restore GT (1 lần, read-only)

```bash
python3 kaggle/api/replica-gate.py --restore-gt   # 84 file GT → /home/z/v11-recovery/test-gt
```

## Bước 3 (0 GPU) — sweep full (Δ điểm + cổng G1/G2)

```bash
cd kaggle/ver-13 && python3 v13lab.py sweep        # ~20' CPU: 6 arm replay + chấm replica
```
Cổng lên GPU: G1 Δadj(C−A) ≥ +0.0008 · G2 Δadj(B−A) < 0 · G3 census · G5 leaf ∈ [30,400].
Fallback G4: nếu G1 fail nhưng D (V13−P4) đạt → đổi config build D.

## Bước 5 (khi có lệnh) — GPU production 0.71h

```bash
python3 kaggle/api/ktool.py verify --ver 13        # token · quota GPU · 9 dataset
python3 kaggle/api/ktool.py push   --ver 13        # Save & Run All (T4×2, OFF) ~35-55'
python3 kaggle/api/ktool.py watch  --ver 13        # poll → tự tải output
```

## Bước 6 (auto sau GPU) — replica-gate CỔNG THẬT

```bash
python3 kaggle/api/replica-gate.py --csv kaggle/api/output/latest/submission.csv --baseline 0.9010
```
- **adjEJ > 0.9010 (v11)** → đề xuất submit (kèm composite/divJ so v12.1 0.9141/0.1429)
- adjEJ ≤ 0.9010 → HOLD · đọc census + run_stats (leaf_prune/divwide receipts) · cây quyết định §8 architecture

## Bước 7 (chỉ khi user ra lệnh) — submit

```bash
python3 kaggle/api/submit-v13.py --dry-run         # xem cổng INT/DAG/CENS/TAG
python3 kaggle/api/submit-v13.py                   # NỘP THẬT — chỉ theo lệnh trực tiếp
```

## Receipt sweep census-only 22/9 (GT chưa có — Δ điểm chờ bước 3)

| arm | nodes | edges | forks | leaf | Δn vs A | Δe vs A | Δf vs A |
|---|---|---|---|---|---|---|---|
| A v11geo (neo) | 123,041 | 119,050 | 591 | 0 | — | — | — |
| B v121geo | 123,104 | 119,173 | 669 | 0 | +63 | +123 | +78 |
| **C v13full** | **122,988** | **119,002** | **598** | **72** | −53 | −48 | +7 |
| D v13noP4 | 122,977 | 118,991 | 595 | 72 | −64 | −59 | +4 |
| E v13vel | 123,049 | 119,063 | 595 | 0 | +8 | +13 | +4 |
| F v13div225 | 122,950 | 118,855 | 481 | 72 | −91 | −195 | −110 |

- ★ leaf_pruned = 72 ≈ **amanatar 71** — port P3 hoạt động đúng trên dữ liệu mình.
- P4a divwide (C−D): +11e/+3f (replay DC-off; production DC 0.15 sẽ veto phần lớn fork thêm).
- diverge 2.25 (F) vs 0.5 (C): −117f — 0.5 nhận được nhiều ứng viên division hơn hẳn.
- ⚠ F3: fork replay inflated ~4× so production (591f vs 144f) — DC-off + MIN_PDIV=0 cho mọi arm; node/edges tin cậy ±0.2-1.5%.
- G3 PASS (node ∈ [120k, 126k] mọi arm) · G5 PASS (leaf 72 ∈ [30, 400]).
