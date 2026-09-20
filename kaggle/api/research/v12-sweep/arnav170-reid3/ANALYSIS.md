# arnav170-reid3 — "reid3"

**Nguồn:** /home/z/v11-recovery/research/arnav170-reid3/biohub-reid3.ipynb (12 cell; base harmonic_v3_division_wide + PP sweep như howonkang)
**Nhãn: THEO DÕI (kỹ thuật) — cơ chế association MỚI THẬT duy nhất của batch C; chưa có receipt điểm**

## Kiến trúc 1 câu
Base harmonic_v3 (0.939 + holdout-PP-sweep, bidir 0.15, DC safe-div 0.25) + **hệ re-identification**: descriptor 28 chiều thủ công từng node (cube 7×25×25 voxel: block intensity/shape/boundary + đỉnh tâm) → pair features (khoảng cách block + cosine + raw/motion/tf_prob + dlog_vol/peak + density/rank/gap) → HistGradientBoosting (300 iter) học trên GT validator leave-one-volume-out → `cost -= REID_WEIGHT × p(reid)` trong cost matrix Hungarian của motion_relink (đánh MỌI cặp trong gate, không chỉ cặp transformer đề xuất).

## Điểm mạnh thiết kế (đáng học)
- Đào tạo trên chính GT validator (labels từ match_nodes_bipartite giữa pred↔GT, chỉ lấy cặp kế frame), OOF AUC + top-1 so 3 chiều: model vs nearest-node vs transformer-prob; permutation importance từng feature — self-diagnostics đầy đủ (reid_report.json)
- REID_WEIGHT mặc định 0 (tắt) — chỉ bật khi PP sweep chọn (8 candidate: w4/8/12, tight-only, tight50, relaxed9, bonus125)
- Chi phí CPU: descriptor toàn node ~100K × cube nhỏ — khả thi

## Delta so stack mình
- Cùng base knob family 0.939 + short rescue + tight 6.0→sweep; DC SAFE_DIV 0.25 (mình 0.20)
- Lớp REID = trục association-appearance hoàn toàn mới so mình (mình chỉ có geometry + transformer prob + motion)
- Không receipt điểm trong folder (reid3 = lần thử thứ 3 của series; sweep tự chọn trong notebook)

## Đánh giá port
- Đây là ứng viên "mở gate association" cạnh SECONDARY_EDGE_FEATURE_TTA A/B (E-7): cùng nhắm keep-rate edge. Nhưng effort port trung bình (descriptor extraction cần đọc frame test + training GBDT in-kernel + tích hợp cost) và rủi ro overfit validator (12 GT div nhưng edge GT dồi dào hơn).
- Nếu v12-lab mở trục association: ưu tiên A/B SEF_TTA (đã có infrastructure) TRƯỚC, REID sau. Giữ card này làm blueprint.
