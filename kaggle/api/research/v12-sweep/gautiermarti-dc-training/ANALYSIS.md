# gautiermarti-dc-training — "deepcenter unet3d"

**Nguồn:** /home/z/v11-recovery/research/gautiermarti-dc-training/biohub-deepcenter-unet3d.ipynb (29 cell, ~243K chars; 7 markdown dài bằng tiếng Nga)
**Nhãn: THEO DÕI — kho receipt điểm phong phú nhất batch C; KHÔNG phải training code**

## Kiến trúc 1 câu
Preset `v29_edge_tta_tight55` (public 0.945): DET 0.965, SAFE_DIV 9/14/τ0.6, GAP_UM 5.8, tight 5.5, DC_SAFE_DIV 0.26 + DEEPCENTER_SAFE_DIV_VETO **OFF** (chỉ gap veto), bidir 0.15, EDGE_FEATURE_TTA, KHÔNG có SECONDARY_EDGE_FEATURE_TTA (kế hoạch v30) — kèm bộ tài liệu Nga mô tả toàn bộ lộ trình tiến hóa v2→v30 với bảng điểm LB.

## Trả lời câu hỏi "có đáng tự train DeepCenter?"
**Không có training code trong notebook này** (grep 0 kết quả: def train/optimizer/backward/AdamW). Kernel dùng cùng public checkpoint `biohub-deepcenter-unet3d-center-prior-v1/weights/full_frame_center/best.pt` như mình. Tên notebook gây hiểu lầm — "dc-training" chỉ là tên dataset checkpoint.

## Bảng receipt LB (từ markdown) — tài sản chính của notebook
| Ver | LB | Thay đổi chính |
|---|---|---|
| v2 | 0.808 | DoG+Hungarian baseline |
| v6 | 0.860 | ceiling heuristic |
| v10 | 0.923 | dual-seed + harmonic (copy công khai) |
| v15 | 0.928 | SEC_DET 0.70, GAP_UM 6.5 |
| v16 | 0.930 | **BIDIR 0.30→0.15** + DIV_WEIGHT 1.2 + GAP2+RESCUE |
| v20 | 0.933 | SEC_DET 0.80 |
| v22 | 0.930 | SEC_DET 0.85 (tệ hơn → 0.80 là đỉnh) |
| v27 | 0.934 | EDGE_WEIGHT 0.20, GAP_UM 5.8 |
| v28 | 0.942 | Division geometry 7/12→9/14 + SYMMETRY_TAU 0.6 + DC epoch 2 |
| v29 | 0.945 | EDGE_FEATURE_TTA + tight 5.5 + DC_SAFE_DIV 0.26 |
| v30 | mục tiêu 0.948 | TTA-fusion link logits + secondary edge TTA + DC TTA |

## Receipt có giá trị quy đổi cho v12
1. **BIDIR 0.30→0.15 = +0.002 LB** (v15→v16) — receipt LB trực tiếp xác nhận lựa chọn 0.15 của mình; mâu thuẫn với hướng probe 0.35 của ayodeji (trên base 0.915). Trục bidir đã khép với 0.15.
2. **GT division geometry** (trích từ biohub-div45-stack): sister separation median 10.4µm / p90 13.0 / max 13.7; parent-daughter max 10.4 → xác nhận SAFE_DIV 9/14 là đúng khung.
3. **EDGE_FEATURE_TTA** (từ rogerrogerroger3r/biohub-run79, 0.944): edge J trên 1 video 0.9115→0.9256 (+0.014), nodes 42700→45004.
4. **tight 5.5** (từ redoctopusk/biohub-942tta, 0.946, PPSWEEP receipt): proxy 0.9492→0.9512, adjEJ 0.9261→0.9282, divJ giữ 0.2308.
5. Public lineage map: rishabhr0y 0.938 → kunaldesale2408 0.940 → analyticaobscura 0.942 (PPSWEEP + validator N=8 + DC 0.25) → rogerrogerroger3r 0.944 → redoctopusk 0.946 → sjlee101 lf-dctta → v30.

## Đánh giá port
Không port code (mình đã vượt 0.945). Giữ: bảng receipt trên + thông tin DC_SAFE_DIV_VETO=0 vẫn đạt 0.945 (bằng chứng veto DC-safe-div không bắt buộc — cân nhắc khi tương tác với purge/rescue div v12).
