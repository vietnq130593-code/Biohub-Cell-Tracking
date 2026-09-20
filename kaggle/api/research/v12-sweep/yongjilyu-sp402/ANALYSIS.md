# yongjilyu-sp402 — "biohub-ct-sp402"

**Nguồn:** /home/z/v11-recovery/research/yongjilyu-sp402/biohub-ct-sp402.py (104 dòng, script thuần)
**Nhãn: BỎ**

## Kiến trúc 1 câu
Baseline đơn giản: chạy predictor support-pack (unet+transformer edge predictor, weights tự continued-train 402 epoch = "cont402") trên từng video test + ILP trực tiếp, rồi convert geff → submission.csv.

## Delta so stack mình
- DET threshold **0.99** (cực bảo thủ; mình 0.965), ILP appearance 1.0 / disappearance 2.0 (mình 0/2), không dual-seed, không harmonic fusion, không post-chain (safe-div/reparent/geo-filter/DC veto đều không có), không TTA, không DivNet
- Docstring: "on the 4 public test videos" — kernel thời kỳ đầu khi test mới lộ 4 video
- Có 1 chi tiết nhỏ: pip install offline từ wheels vendored trong dataset pack (pattern packaging mình đã biết)

## Đánh giá
Không có lớp nào mình thiếu; không receipt điểm; DET 0.99 + ILP app 1.0 là hướng ngược với mọi thứ cụm 0.948 đã xác nhận. Chỉ đáng ghi nhận "cont402" = fine-tune edge predictor 402 epoch (song song với ý tưởng fine-tune V1327-W3 của alfonso) nhưng không có bằng chứng nó vượt checkpoint chuẩn.
