# mtoshidesu-lf-dctta — "lf dctta020 sectta1" (36 votes)

**Nguồn:** /home/z/v11-recovery/research/mtoshidesu-lf-dctta/testbiohub-lf-dctta020-sectta1.ipynb (107 cell — bản "documented edition" có 10 nhận xét kỹ thuật của người copy)
**Nhãn: THEO DÕI (mạnh) — knob SEF_TTA w=1.0 là điểm A/B trực tiếp cho trục E-7; cộng 4 cave cấu trúc đáng ghi nhận**

## Kiến trúc 1 câu
Bản gốc public 36-vote của family harmonic_v3_division_wide (DET 0.965, bidir 0.15, SAFE_DIV 9/14/τ0.6/2.25, DC SAFE_DIV **0.20** + DC TTA, linefit w0.8 win2, min len 6 + short rescue, PP sweep chọn tight55) với **SECONDARY_EDGE_FEATURE_TTA_WEIGHT = 1.0** — tên kernel chính là 3 knob: lf + dctta020 + sectta1.

## Knob đối chiếu stack mình (quan trọng nhất batch C)
| Knob | mtoshidesu | mình | Ghi chú |
|---|---|---|---|
| SEF_TTA_WEIGHT | **1.0** (thay toàn bộ feature secondary bằng trung bình TTA) | **0.75** | Docstring gốc viết "three-quarter-strength" nhưng code = 1.0 (nhận xét #10 của người copy) — nghĩa là family 36-vote chạy FULL 1.0; howonkang (fork) mới đặt 0.75 |
| DC_SAFE_DIV | 0.20 | 0.20 | trùng |
| tight | 6.0 → sweep chọn 5.5 | 5.5 | trùng qua sweep |
| HOCT/reparent/density guard | KHÔNG có | có | mình hơn họ 3 lớp ver-8 |

→ **A/B trực tiếp cho E-7**: nghi phạm keep-rate 0b24 là SEF_TTA w0.75; đây là cấu hình chạy w=1.0 với mọi knob khác ~trùng mình — lý tưởng làm điểm đối chiếu trong v12-lab (SEF_TTA 0.75 vs 1.0 vs OFF).

## 4 nhận xét kỹ thuật đáng giữ (áp cho codebase chung family mình)
1. **mutualNN chỉ kiểm 1 chiều** (§8.7): SAFE_DIV_REQUIRE_MUTUAL_NN chỉ đòi candidate là NN của existing child, không kiểm chiều ngược — kiểm lại semantic gate này trong monolith mình khi design biến thể div v12.
2. **ILP edges bị thay bởi relink edges** (§8.4/8.10): khi motion relink ra ≥1 cạnh, cạnh ILP bị vứt (chỉ giữ prob làm bonus) → division trong submission đến hoàn toàn từ safe-div stage. Nhất quán với hiểu biết của mình (div = safe-div channel).
3. **GAP_CLOSE_MAX_GAP=2 không tác dụng lên single-frame close** (effective = min(2,1)) — gap 2 chỉ qua recover_strict_gap2 riêng.
4. **Validator "held-out" chỉ loại stem trùng test dir** — không chứng minh model không train trên đó (mỏ neo validator mình đã biết); kèm cảnh báo report JSON hard-code config cũ (receipts stale — bài học quản trị receipts của chính họ hỏng).

## Receipts điểm
- Attached run (validator, không phải LB): base proxy **0.9490** (adjEJ 0.9260, divJ 0.2308) → sweep chọn tight55 proxy **0.9511** (+0.0021) — trùng receipt redoctopusk 0.946 trong docs gautiermarti.
- Không có receipt LB của chính kernel; 36 votes = kernel gốc được fork nhiều nhất cụm (howonkang/newwang12 đều là hậu duệ cấu trúc).
