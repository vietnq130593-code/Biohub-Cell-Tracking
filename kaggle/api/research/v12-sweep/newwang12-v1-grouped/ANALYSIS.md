# newwang12-v1-grouped — "v1-grouped" (12 votes)

**Nguồn:** /home/z/v11-recovery/research/newwang12-v1-grouped/biohub-v1-grouped.ipynb (13 cell; cell 2 = shared runtime ZIP base64 "identical to the Optuna package")
**Nhãn: THEO DÕI (grouping infra) + PORT nhẹ (2 patch đơn lẻ)**

## Kiến trúc 1 câu
Cùng base ver-8/v3-fast của mình (DET 0.965, ILP -1/0/2/1.2, SAFE_DIV 9/14/τ0.6/mutualNN, tight 5.5/relaxed 10, linefit w0.8, gap2) + hạ tầng "packet grouping": đo 4 feature trực tiếp từ test zarr (light_radius_halfmax bằng cách đọc pixel thật + NN distance + motion disagreement) → QuantileTransformer (quantiles dựng sẵn) → softmax logits → severity = P(mid)+2·P(high) → chia clip thành low/middle/high → GROUP_OVERRIDES 65 tham số mỗi nhóm; v1 này override TRỐNG (infra chạy nhưng no-op).

## Delta so stack mình
- OUTPUT_MIN_TRACK_LEN **4** (mình 6) + ADAPTIVE_SHORT_TRACK_RESCUE=True (min len 4, prob 0.88, dist 3.0µm, cap 1.2%/120 — giống hệt howonkang-short5 → lớp này đang lan trong family)
- DEEPCENTER_SAFE_DIV_THRESHOLD **0.25** (mình 0.20; alfonso cũng 0.25 — nguồn thứ 3 hội tụ về giá trị này)
- MOTION_RELINK_LEARNED_BONUS 1.0; DC GAP 0.25
- **R3_zero patch** (EXPERIMENT_ZERO_MAX_UM=0.0): trong motion_relink_edges, candidate có learned_prob == 0.0 bị LOẠI hoàn toàn khỏi cost matrix Hungarian (bình thường zero-prob vẫn được match thuần bằng motion cost) → relink bảo thủ hơn
- Grouping infra: cell 9 ~50K chars — grouper_4feat_v7, classify_packets (QuantileTransformer + linear + softmax + cut thresholds), measure_packet_groups đọc frame test thật để đo light radius; grouped_postprocess áp override theo nhóm

## Đánh giá port
- **Grouping (packet-level param selection):** ý tưởng thật — hidden test có clip dày (05db) khác regime hẳn, và mình đã có GAP_DENSITY_ADAPTIVE như một mini-version. Nhưng để có giá trị cần tune GROUP_OVERRIDES trên train theo nhóm (Optuna) — công suất lớn, deadline 29/9 không kịp, và v1 chưa có override nào = chưa có receipt giá trị. THEO DÕI cho mùa sau.
- **R3 zero-prob purge:** patch 1 dòng trong motion relink — A/B khô được ngay trên output v10 (CPU). Giá trị dự kiến nhỏ nhưng chi phí ~0.
- **minlen4 + DC 0.25:** minlen4 (mình 6) và DC SAFE_DIV 0.25 (mình 0.20, alfonso 0.25) là 2 delta thật; short-track rescue thì ver-10 mình ĐÃ CÓ identical params (verify monolith dòng 112-118) — không tính.

## Receipts điểm
- Không có output/receipt trong folder; 12 votes Kaggle nhưng không claim điểm cụ thể. Base params khớp family 0.947 → có thể đoán ~0.947-0.948 nhưng KHÔNG kiểm chứng.
