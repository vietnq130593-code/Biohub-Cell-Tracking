# ghazaros-dae017 — "DAE alpha 0.17"

**Nguồn:** /home/z/v11-recovery/research/ghazaros-dae017/biohub-dae-alpha-0-17.ipynb (11 cell; self-patch mono bằng string-replace vào predictor)
**Nhãn: THEO DÕI — trục DAE prefilter (detection-axis) rẻ và mới, receipt mỏng**

## Kiến trúc 1 câu
"Verified 0.946 floor" của riêng họ (harmonic_v3_division_wide + trajectory-aware association: LEARNED_BONUS **1.35**, VELOCITY_WEIGHT **0.75**, bidir **0.30**, GAP_UM 5.8, KHÔNG edge-TTA, DC safe-div 0.12) + một knob duy nhất so với bản α=0.15: **DAE α 0.15→0.17**.

## Cơ chế DAE (điểm mới thật của notebook)
- `_BioDenoiseAE`: Conv3d 4 lớp (1→8→4→8→1), tự học trên CHÍNH video test (8 frame mẫu, 30 bước Adam lr=1e-3, noise σ=0.05 → reconstruct sạch, MSE)
- Pha trộn tại predict_video: `imgs = imgs + alpha * (dae_denoised - imgs)` — nướng vào ảnh TRƯỚC detector; edge model ăn ảnh đã khử nhiễu
- Chi phí gần như 0 (vài giây GPU/video); guard chống no-op đầy đủ

## Receipts điểm (series của họ)
- Base floor tự nhận **0.946** (với DAE α=0.15); α=0.17 = candidate "one isolated leftover" (chưa có điểm trong folder)
- **α=0.20 → rớt về 0.938** — receipt rõ ràng dải α an toàn ≤ ~0.17
- Comment kèm: "sdm9 arm alone scored LB 0.939" (SAFE_DIV_MAX 9); "kimi-v18 LB sweep [DIVERGE_UM] peaked ~4.0-4.5" (mình/notebook này đang 2.25 — Receipts trục DIVERGE đáng ghi vào backlog A/B v12)

## Đánh giá port
- Trục DAE = trục DETECTION (khử nhiễu ảnh đầu vào). Theo E-7 lượt 4 alfonso: gap node 0b24 của mình chủ yếu ASSOCIATION (~1.394 node) chứ không phải detection (~461) → DAE không đánh trúng điểm nghẽn chính của mình.
- Chi phí port thấp (patch ~60 dòng) nhưng cần 1 lượt GPU A/B; nếu v12 còn slot GPU sau các biến thể edge-axis thì xếp DAE α=0.10-0.15 vào hàng chờ.
- Trục DIVERGE_UM 4.0-4.5 (receipt kimi-v18): A/B khô được ngay trên cache output v10 — ghi vào backlog.

## So knob với mình
DET 0.965 / SAFE_DIV 9/14/τ0.6/2.25 / min len 6 + short rescue / DC gap 0.25 — trùng; khác: bonus 1.35, velocity 0.75, bidir 0.30, GAP 5.8, DC safe-div 0.12, không TTA edge.
