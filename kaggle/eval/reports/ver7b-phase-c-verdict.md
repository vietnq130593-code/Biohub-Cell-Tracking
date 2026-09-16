# VER-7b (Phase C: divnet RANK-ONLY + nới gate) — PHÁN QUYẾT: KHÔNG SUBMIT

Ngày 14/9 · Run vietnguyen130593/biohub-ver7b v1 · T4×2 ~105 phút COMPLETE · submission 241.643 dòng (không nộp)

## Bằng chứng (validator old-rule, 8 video held-out, system view)

| config chọn (PPSWEEP) | adjEJ | divJ (tp/fp/fn) | proxy |
|---|---|---|---|
| ver-7 tight55 | 0.9280 | 0.2308 (3/1/9) | 0.9511 |
| ver-7b combo(tight55+dcgap035) | 0.9259 | 0.1212 (4/21/8) | 0.9380 |
| **Δ** | **−0.0021** | fp +20, tp +1 | **−0.0131** |

## Phân rã nguyên nhân
- DivNet ranker HOẠT ĐỘNG đúng thiết kế: divnet_scored 26–253/video, rank_flips 3–131, divnet_p_added_mean 0.21–0.70; div_tp 3→4 (tín hiệu đúng hướng).
- Nhưng nới gate (tau 0.6→1.2, diverge 2.25→1.0) làm geometric_candidates tăng ~3–4× (vd 150→563 ở 44b6_12dfb391);
  safe-divisions thêm 139→581 trên 8 video → div_fp 1→21 → divJ sụp; adjEJ cũng mất 0.002 (cạnh fork sai = FP).
- Core view (official scorer, raw predictions) giống hệt ver-7: adjEJ 0.9345, div 0/0/12 — xác nhận thay đổi
  thuần postprocess (đúng thiết kế), và khuyết hướng của eval cell hiện chỉ đo core.

## Phán quyết theo VER7-PLAN Phase B
- Δproxy −0.013 >> ngưỡng 0.005 (ELEVEN rule) → REGRESSION → KHÔNG submit. Giữ ver-7 (56217216) làm submission.
- GATE PHÁT HUY TÁC DỤNG: đúng kịch bản megayak ("gate-only −0.017"; ở đây rank + gate-quá-rộng ≈ −0.013).

## Hướng Phase C v2 (nếu tiếp tục)
- Giữ RANK-ONLY divnet (W=15µm) nhưng KHÔNG nới gate (tau 0.6, diverge 2.25 như ver-7) — ranker tái xếp
  trong tập candidate bảo thủ; kỳ vọng div_tp tăng mà fp không nổ. Hoặc nới HƠN NHỎ (tau 0.8).
- Có thể thêm ngưỡng divnet (BIOHUB_DIVNET_MIN_PROB ~0.5) để chặn candidate P_div thấp khi gate nới.
- Lưu ý ops: notebook 7b cần eval cell BẢN ĐÃ VÁ (_find_base_root datasets/<owner>/) — lần này build trước khi vá.
