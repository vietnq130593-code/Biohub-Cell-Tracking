# howonkang-short5 — "0947 short5 prepp r1"

**Nguồn:** /home/z/v11-recovery/research/howonkang-short5/biohub-0947-short5-prepp-r1.ipynb (12 cell, ~210K chars code thuần, không monolith base64)
**Nhãn: PORT (chọn lọc) — 2 lớp CPU rẻ đáng A/B: SHORT5_PREPP + ADAPTIVE_SHORT_TRACK_RESCUE**

## Kiến trúc 1 câu
Fork đúng dòng dõi harmonic_v3 của mình (dual-seed harmonic, DET 0.965, ILP 0/2, SAFE_DIV 9/14/2.25/τ0.6, DC veto 0.20, bidir 0.15, SECONDARY_EDGE_FEATURE_TTA w0.75, EDGE_TTA=1) + 3 lớp mới: SHORT5 raw-gepp pre-clean, adaptive short-track rescue, và post-process sweep tự chọn trên holdout.

## Env so stack mình (ver-8/v3-fast)
- Trùng: DET 0.965 / ILP app 0 / dis 2 / GAP_CLOSE 5.0 (gap2 ON) / SAFE_DIV 9/14/2.25/τ0.6 / DC SAFE_DIV 0.20 / bidir 0.15 harmonic_probability / SECONDARY_EDGE_FEATURE_TTA=1 w0.75 / OUTPUT_MIN_TRACK_LEN=6 / ILP_DIVISION_WEIGHT=1.2
- Khác: MOTION_RELINK_TIGHT_UM 6.0 (mình 5.5); KHÔNG có HOCT veto, reparent Phase D, density guard (post-chain cũ hơn ver-8 mình — họ đi từ base 0.939 harmonic_v3); VALIDATOR_N_PER_TYPE=4
- Base tự nhận: "public 0.939 base + holdout-selected post-process configuration"; tiêu đề notebook claim 0.947 → Δ +0.008 không tách được thành phần (short5 vs PP-sweep vs rescue)

## 3 lớp mới (delta thật)
1. **SHORT5_PREPP** (`apply_short5_raw`, ~50 dòng): đọc raw geff → union-find KHÔNG định hướng → xóa mọi connected component ≤5 node (+cạnh phát sinh) TRƯỚC khi vào champion postprocess. Docstring "Proven semantics (SHORT5_PREPP VAL)". Chạy tại call site ngay trước `filter_output_graph`. Có runtime guard (không xóa component >5, không thêm node). **Lớp duy nhất mà ver-10 mình KHÔNG có** (đã verify: grep SHORT5 trong cell-monolith.py = 0).
2. **ADAPTIVE_SHORT_TRACK_RESCUE** (env 46-51): rescue ngược chiều — trả lại track ngắn len≥4 nếu mean_edge_prob ≥0.88, mean_edge_dist ≤3.0µm, cap 1.2% node / 120 node mỗi dataset. ⚠️ [sửa sau verify] Lớp này ver-10 mình **ĐÃ CÓ SẴN với tham số byte-giống hệt** (monolith dòng 112-118: min_len 4 / 0.88 / 3.0 / 1.2% / 120) → không phải port candidate, chỉ là di sản chung của family.
3. **PP_SWEEP** (cell 9-10): sweep 7 ứng viên đơn-knob (gap45, tight55, relaxed9, bonus125, gap2step40, reuse28, dcgap035) + greedy combo trên validator holdout; quy tắc chọn: proxy ≥ base +0.001 VÀ adjEJ không mất >0.0005 (guardrail chống đổi divJ lấy edge). Mình đã có ppsweep in-kernel tương đương (output/latest/ppsweep_results.csv) — pattern margin-rule tham khảo.

## Đánh giá port
- SHORT5_PREPP: CPU ~50 dòng, chạy trên raw geff trước post-chain → tương tác với 188-fork problem của mình CHƯA rõ (fork node thường thuộc component lớn nên ít bị ảnh hưởng). A/B khô được ngay trên output v10 (đọc raw geff từ cache predictions/*.geff). Gợi ý biến thể A/B v12: `v10 + short5` đo bằng LB.
- Short-track rescue: MÌNH ĐÃ CÓ (identical params) — bỏ khỏi kế hoạch port.
- PP_SWEEP meta-layer: BỎ port (mình đã có ppsweep in-kernel + offline), giữ ý tưởng margin-rule (proxy ≥ +0.001, adjEJ loss ≤ 0.0005).

## Receipts điểm
- Không có output/receipt LB trong folder; chỉ claim tự nhận 0.947 (tiêu đề) trên base 0.939. Không kiểm chứng được.
