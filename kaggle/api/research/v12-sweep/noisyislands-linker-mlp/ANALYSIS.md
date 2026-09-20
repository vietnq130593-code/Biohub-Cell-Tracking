# ANALYSIS — noisyislands/biohub-linker-association-mlp (Linker Association MLP)

**Task ID:** 5-b · **Ngày:** 20/9 · **Loại:** KERNEL TRAINING PILOT (plan §7/§8; không submission)
**Nguồn:** /home/z/v11-recovery/research/noisyislands-linker-mlp/biohub-linker-association-mlp.py (595 dòng) + output pull 20/9 (log + linker_fold0/{best.pt, prov.json}).

## 1. Mô hình & feature

**EdgeMLP 6→16→16→1 (PyTorch, BCEWithLogits):** phân loại cạnh ứng viên true/false.

Feature (6):
```
displacement_um/10, temporal_delta, is_first, is_last,
motion_residual/10 (= max(0, dist−4.0µm)), competing_link_count
```
- Candidate pool: KD-tree mọi c (t→t+1) trong 10 µm, giữ **top-3 mỗi target** (aim_recall 0.995 khai báo).
- Class balance: neg:pos = 1.5, giữ toàn bộ positive.

### Điểm đáng chú ý nhất: `--candidate-mode production_sim`
Inject node tổng hợp mô phỏng lỗi detector production trước khi sinh candidate:
- **duplicate:** 15% node GT được nhân bản lệch ≤3 µm (~7 voxel xy) — đúng forensics "detector tạo duplicate ~3µm" (khớp phát hiện near-duplicate-split của mình ở fork funnel E-4).
- **noise:** 10% frame thêm node vị trí ngẫu nhiên trong bbox.
- Ý đồ: MLP thấy hard negative "impostor gần hơn cặp thật" — đúng failure mode keep-rate association.
- Bug nhẹ: `inject_synthetic_nodes` tạo `base_gt_edges = set()` trống và caller không đút vào ⇒ duplicate KHÔNG thừa hưởng cạnh GT như docstring — vô hại cho mục đích negative-mining (dup thành negative đúng ý), nhưng code không match comment.

### Training receipt (log pull 20/9)
- **Train trên đúng 4 phim hidden test** (44b6_0113de3b, 44b6_0b24845f, 6bba_05b6850b, 6bba_05db0fb1 — GT node-rich có trong competition train, hợp lệ vì data được cung cấp; cũng là 4 phim mà GT sparse: 44b6 chỉ ~63 candidate-row/phim).
- 2 epochs, tổng 2.866 mẫu (pos ~2.127 / neg ~739), chạy **22 giây** trên GPU.
- **best BCE loss 1.915** — rất xấu (random ≈ 0.69): MLP 6 feature không tách nổi true/impostor; loss>2 ở epoch 1 = confidently wrong.

## 2. So với ILP + learned bonus của mình

| Khía cạnh | noisyislands MLP | Mình (ver-8/v3-fast) |
|---|---|---|
| Signal association | 6 feature hình học thuần | edge_prob học từ UNet-feature (primary+secondary, D4-TTA, harmonic bidir) |
| Solver | chưa có (ckpt only; "event_solver explicit b/d/c/h" chỉ là prov string) | ILP全局 + motion relink + Hungarian |
| Learned integration | không | MOTION_RELINK_LEARNED_BONUS=1.0 đã bật |
| Đánh giá | loss only | validator + LB |

⇒ Về thực chất **không cạnh tranh** với lớp association của mình. Giá trị nằm ở 2 ý tưởng chuyển được:
1. **`competing_link_count`** (số source khác tranh cùng target) làm feature/cost — mình chưa đưa trực tiếp vào cost relink (chỉ có qua ILP). Rẻ, có thể A/B như bonus trừ cho target bị tranh chấp.
2. **Synthetic dup/noise injection** cho hard-negative — khuôn mẫu nếu v12-lab cần train lại Motion-Linker trên GT validator.

## 3. Verdict cho v12

**BỎ** (không port model/ckpt): pilot 2 epoch, loss cho thấy không học được gì, không inference path, không receipt. Ghi nhớ 2 ý tưởng: competing_link_count + production_sim negatives.
