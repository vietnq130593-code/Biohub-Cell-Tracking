# VER-7 — CHECKLIST PORT (kỹ thuật từng bước; cập nhật đợt 2 + ghi chú rollback 13/9)

> Nguồn: monolith 0.947 của Reyhan (LB best tác giả = 0.947 ✓, guard in-code verified_public_lb_0947).
> Nguyên tắc: **giữ nguyên văn tối đa** — chỉ vá 5 nhóm dòng env path (dataset riêng → pilkwang public).
> Mọi SHA256 checkpoint đã khớp pilkwang (đã đối chứng trước rollback).

## 1. Vá đường dẫn (5 nhóm vị trí, duy nhất bắt buộc)

| Vị trí gốc | Gốc (private) | Đổi thành (pilkwang public) |
|---|---|---|
| MODEL_ARTIFACTS | `…reyhanksatria/biohub-tracking-support-pack` | `…pilkwang/biohub-tracking-support-pack-50ep-v1` |
| TARGET_ARTIFACT_SLUG | `biohub-tracking-support-pack` | `biohub-tracking-support-pack-50ep-v1` |
| DEEPCENTER (3 chỗ: đầu + 2 set lại) | `…reyhanksatria/biohub-deepcenterunet3d-center-prior-v1/…` | `…pilkwang/biohub-deepcenter-unet3d-center-prior-v1/…` |
| SECONDARY_MANIFEST | `…reyhanksatria/biohub-temporalunet3d-seed-314159-v1/…` | `…pilkwang/biohub-temporal-unet3d-seed314159-v1/…` |

**Fallback nhiều tầng của code Reyhan** (đọc kỹ, an toàn ngay cả khi path sai):
- `find_artifacts_root()`: thử env → candidate_roots_for_slug() → quét toàn bộ /kaggle/input
  với ALLOW_ARTIFACT_FALLBACK=1; slug gốc là chuỗi con của slug -50ep-v1.
- DeepCenter: danh sách ứng viên đã chứa path pilkwang + kiểm SHA256 khớp.
- Secondary: rglob ARTIFACT_MANIFEST.json toàn input + SHA256 khớp.

## 2. Các bước triển khai (Phase A — trạng thái sau rollback)

1. [x] Kéo source 0.947 + phân tích (Task 31, trước rollback)
2. [x] `ver-7/cell-monolith.py` — vá 5 nhóm path + 3 dòng header comment (diff đã kiểm)
3. [x] `python3 -m py_compile` PASS; grep 'reyhanksatria' = 0
4. [x] Cell Phase B official eval (`eval/cell-eval-official.py`, 382 dòng, exception-safe)
5. [x] Notebook `download/ver7-cell-tracking.ipynb` = markdown + monolith + eval cell (static checks PASS)
6. [x] Push qua ktool `--ver 7` (7 nguồn input) → `vietnguyen130593/biohub-ver7` v1
7. [⏳] Watch COMPLETE → kiểm output (submission ~241k dòng; audit SHA256; ground_truth_accessed=false)
8. [ ] Phase B: compare.py + gate `adj:0.942` / `proxy:0.945`
9. [ ] Submit (chỉ khi bước 8 đạt) + chờ điểm (6–12h bình thường)
10. [ ] Ghi nhận: LB ≥ 0.946 → thành công; 0.943–0.945 → điều tra PPSWEEP; < 0.943 → revert ver-6

## 3. Điểm cần chú ý khi đọc log ver-7

- Tag kỳ vọng: `secondary_deepcenter_tta_0947`; `EDGE_TTA_ACTIVE views=8`;
  `SECONDARY_EDGE_TTA_ACTIVE views=8`; DeepCenter TTA có dòng announce riêng.
- Run-time dự kiến ~40–60 phút T4×2 (TTA nhiều lớp + validator 8 video + eval cell).
- PPSWEEP in kết quả chọn cấu hình hậu xử lý trên held-out (không có ở ver-6).
- `BIOHUB_VALIDATOR_N_PER_TYPE` = 4 (Reyhan set sẵn) → 8 video held-out (4/type × 2 prefix).

## 4. Rủi ro đã đóng gói

- **Không dùng metric-hack** (đã vá 17/7 + vi phạm tinh thần).
- Monolith 1 cell: lỗi cú pháp chết toàn bộ → py_compile + nguyên văn là lớp bảo vệ chính.
- PPSWEEP chọn sai trên public → Phase B (official scorer) phát hiện trước khi submit.
- Mọi kết luận division phải qua official scorer 075fc5f (validator nội bộ dùng rule cũ double-reading).
- Không tune node-count theo validator (zhincez: validator +0.013 → LB −0.004).
- Không tin claim điểm trong tiêu đề notebook (cloudssdut "0.948" = giả, best 0.939).
- **MỚI 13/9**: sau rollback sandbox — mọi artifact quan trọng phải sống trên Kaggle
  (notebook pushed + datasets + submissions); local chỉ là bản sao làm việc.
