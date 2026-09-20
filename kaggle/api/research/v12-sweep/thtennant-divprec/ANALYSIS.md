# ANALYSIS — thtennant/biohub-frontier947-divprec-v1 (division precision experiment)

**Task ID:** 5-b · **Ngày:** 20/9 · **Loại:** SUBMISSION KERNEL — biến thể divprec của family frontier947 (xem ANALYSIS thtennant-gapfill cho cấu trúc family + base env).
**Nguồn:** /home/z/v11-recovery/research/thtennant-divprec/biohub-frontier947-divprec-v1.ipynb + output pull 20/9.

## 1. Biến thí nghiệm (cô lập bằng diff)

= gapfill-v1 + **`BIOHUB_SAFE_DIV_SISTER_SYMMETRY_TAU` 0.6 → 0.4** (siết gate đối xứng con: |d1−d2|/mean ≤ τ) + 1 knob chết `BIOHUB_SAFE_DIV_SISTER_MIN_UM=0` kèm comment gốc:
> "Sister minimum (agent/frontier943_divprec), off at 0: **it did not hold on both caches (RESEARCH 24)**."

⇒ 2 dữ liệu: (a) họ đã thử "sister-min" (đ exceedingly gần nhau ⇒ không phải division — đúng profile near-duplicate split của mình) và **nó KHÔNG giữ được trên 2 cache validator của họ** → receipt phủ định cho 1 ý tưởng mình từng cân nhắc; (b) trục đang thử nghiêm túc = τ symmetry.

## 2. Receipt chạy thật (hidden test, so gapfill-v1 cùng base)

| | gapfill (τ0.6) | divprec (τ0.4) | delta |
|---|---|---|---|
| fork FINAL | 42/11/9/23 = **85** | 34/7/4/17 = **62** | **−23 fork (−27%)** |
| node set | 123.232 | 123.232 | 0 |
| cạnh FINAL | 119.036 | 119.013 | −24 (−23 cạnh fork + 1 cạnh khác) |
| safe-div geometric cand (0113) | 157 | 157 | 0 |
| DC rejected (0113) | 110 | 122 | +12 |
| post-veto → added (0113) | 47 → 42 | 35 → 34 | siết ở symmetry gate |

Cơ chế: τ0.4 giết đúng lớp proposal "con lệch nhau" trước khi vào DC veto — funnel shift tương tự hướng mình từng mô phỏng (gate giết near-duplicate split). **Không LB, không validator trong run** (VALIDATOR_ENABLE=0, sweep skip) ⇒ không có dấu hiệu hướng, chỉ có quy mô.

## 3. Đặt trong bối cảnh trục division của mình

- Validator mình: 12 GT, 3 TP/1 FP/9 FN (pawanmali parity) — **FP chỉ 1** ⇒ dư địa precision trên validator cạn; τ siết thêm có nguy cơ cắt TP (funnel mình: 9 FN phần lớn no-proposal, τ không cứu được).
- Hidden test ≈ 2–3 GT division ⇒ trần điểm của trục ~±0.003; alfonso V50 đo divJ 0.333 (TP=1) trên hidden với chỉ 2 rescue.
- Receipt chéo batch C: GT sister separation median 10.4 µm / p90 13.0 / max 13.7 — τ symmetry là hàm của TỈ LỆ d1/d2, không phải khoảng cách tuyệt đối; không có census symmetry của GT nên τ0.4 đang mù dữ liệu.
- Kết luận trục: đúng hướng "sign division khớp LB" (zhincez 3/3) nhưng phiên bản đắt nhất để thử là **A/B khô 1 knob trên validator + 1 lượt LB** — không phải port code gì (mình đã có TAU knob).

## 4. Verdict cho v12

**THEO DÕI (A/B 1-env, không port code):** τ ∈ {0.6, 0.4} chỉ đáng 1 slot trong lưới A/B post-chain trên validator (cùng lúc với biến thể A/purge — vì purge-fork và τ-siết cùng nhắm lớp near-duplicate split, phải đo TÁCH BIỆT để tránh double-counting). Giữ receipt phủ định sister-min (RESEARCH 24) — đừng lãng phí slot thử ý tưởng đó.
