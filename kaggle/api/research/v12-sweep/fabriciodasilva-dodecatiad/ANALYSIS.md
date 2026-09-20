# fabriciodasilva-dodecatiad — "Dodecatiad Cell Tracking"

**Nguồn:** /home/z/v11-recovery/research/fabriciodasilva-dodecatiad/biohub-dodecatiad-cell-tracking.py (808 dòng, pure classical CV)
**Nhãn: BỎ**

## Kiến trúc 1 câu
Pipeline classical không deep learning: multi-scale DoG blob detection (2 cặp scale 1.5/4.0 + 2.2/5.5µm, XY downsample 4, local-max footprint 3.2µm) + refinement centroid background-subtract + Hungarian linking 8µm + gap-close chèn node nội suy + prune isolated.

## Delta so stack mình
- Không có model học nào (có detect_unetstub nhưng không dùng trong Config); không learned edge, không ILP, không post-chain
- allow_divisions=False mặc định → không dự đoán division nào (divJ=0)
- Ghi chú đáng giữ: "all GT edges are dt=1" (xác nhận lại nhận thức của mình) và gap-close chèn node nội suy midpoint — concept mình đã có bản tốt hơn (OUTPUT_GAP2_RECOVERY)

## Đánh giá
Baseline giáo khoa — điểm chắc chắn thấp hơn cụm 0.94 rất nhiều (detection không learned). Không có gì để port; chỉ giữ 2 ghi chú xác nhận (GT dt=1, gap interpolation hợp lệ format).
