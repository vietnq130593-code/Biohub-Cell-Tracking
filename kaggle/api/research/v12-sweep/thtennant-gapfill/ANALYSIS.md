# ANALYSIS — thtennant/biohub-frontier947-gapfill-v1 (gap filling bằng sub-threshold peaks)

**Task ID:** 5-b · **Ngày:** 20/9 · **Loại:** SUBMISSION KERNEL — 1 biến thể trong ablation family "frontier947" của Teddy Tennant.
**Nguồn:** /home/z/v11-recovery/research/thtennant-gapfill/biohub-frontier947-gapfill-v1.ipynb (12 cell) + output pull 20/9 (log, run_stats.csv, submission.csv, edge_cache, ppsweep_selected.json). Pull thêm 2 mốc họng line: `fast-v1` (17/9) và `flow2-v1` (18/9) để cô lập biến.

## 1. Vị trí trong family frontier947 (cumulative)

```
fast-v1  (17/9)  = base stack 0.947-flavor (không flow, không gapfill)
flow-v1 / flow2-v1 (18/9) = + MOTION_RELINK_FLOW   (neighbourhood-flow motion prior)
gapfill-v1 (19/9) = flow2 + GAPFILL               (node insertion từ sub-threshold peaks)  ← notebook này
readmit-v1 (19/9) = gapfill + READMIT             (re-admit detection bị ILP vứt)
divprec-v1 (19/9) = gapfill + τ symmetry 0.4      (division precision)
```
Các cell 1,3,4,6–11 byte-identical giữa 3 notebook mình có; delta nằm đúng cell0 (env), cell2 (constant), cell5 (code ~94–97 KB). Family dùng **cùng 3 checkpoint pilkwang như mình** (SHA verify 12f6881e/9bac2fa0/8040999a), env 0.947-flavor: DET 0.965, ILP 0/2/div1.2, SAFE_DIV 9/14/τ0.6/2.25/caps, gap 5.0 + density-adaptive, bidir 0.15, EDGE_TTA + SEF_TTA w0.75, LINEFIT w0.8/win2, short-track-rescue 0.88/3.0/1.2%/120, **tight55 pre-baked**, DC_SAFE_DIV **0.25** (vs mình 0.20), **VALIDATOR_ENABLE=0** ⇒ "SWEEP: validator unavailable — keeping base" (không có sign offline trong các run này; họ có hệ cache validator riêng ngoài Kaggle — comment "RESEARCH 24").

## 2. Cơ chế GAPFILL (điểm mới so với gap-close/gap2 của mình)

**Bước 1 — dump low-detections (patch prediction cell, cell4):** string-patch `predict_video` (anchor count==1 + compile check + non-fatal): chạy `_detect_cells_pooled` lần 2 ở threshold **0.3** mỗi frame, lưu mọi peak kèm sigmoid score → `edge_cache/<dataset>.npz {low_coords(t,z,y,x), low_score}`. (Cùng patch cũng dump coords + candidate edges; CACHE_EDGE_THRESHOLD=1.0 ⇒ thực tế chỉ lowdet + coords được dùng.)

**Bước 2 — `fill_gaps_from_low_detections` (cell5, ~170 dòng):** chạy SAU gap-close + gap2, trên những gì còn hở:
- Pool: peak score ≥ **0.5**, cách mọi node hiện có > **2.0 µm** (loại duplicate của chính node set).
- Cặp ứng viên: track-END tại t ↔ track-START tại t+g+1, g ≤ **3**, tổng span ≤ STEP **5.0 µm** × (g+1).
- Chuỗi: sample đường thẳng end→start mỗi frame thiếu; peak tự do gần nhất trong **3.5 µm** của điểm sample; **ALLOW_SYNTHETIC=0** (không được "bịa" node — mọi frame phải có peak thật; máy móc synthetic chỉ bật khi knob >0, dùng refine midpoint như gap-close).
- Context gate: cos(stepping vector, prev-segment của end) và cos(, next-segment của start) ≥ −0.25.
- Assignment: **Hungarian trên cost = span/(g+1) + độ lệch trung bình của các peak** — gap ngắn trước, mỗi end/start dùng 1 lần.
- **Budget: thêm tối đa 3% node set** (GAPFILL_MAX_ADDED_FRAC 0.03).
- Node mới mang flag `gapfill_peak`/`gap_synthetic`; cạnh mới flag `gap_filled` (edge_prob=None).

## 3. Receipt chạy thật (hidden test, output pull)

| phim | pool free peaks | gapfill thêm |
|---|---|---|
| 44b6_0113de3b | 1.722 | +3 node, +4 cạnh |
| 44b6_0b24845f | 26.152 | **+111 node, +162 cạnh** |
| 6bba_05b6850b | 1.915 | +0 |
| 6bba_05db0fb1 | 9.734 | +53 node, +74 cạnh |
| **Tổng** | | **+167 node, +240 cạnh** |

FINAL 123.232 node / 119.036 cạnh (vs Reyhan base cùng checkpoint: 122.808/118.548 — chênh còn lại do flow prior + fork 85 vs 124). Không có LB receipt riêng (Teddy Tennant LB best 0.947); family không chạy validator trong kernel.

## 4. So với gap-close/gap2 của mình & rủi ro

- Mình chỉ (a) nối cạnh giữa node tồn tại (gap-close 5.0 µm + density-adaptive + gap2 ≤2 frame, midpoint synthetic có refine) — **chưa bao giờ INSERT node từ detection sub-threshold**. Gapfill trực tiếp tăng node recall (trục node-multiplier) và hồi những bridge mà gap-close không làm được vì frame giữa trống detection.
- Khớp chéo với E-7 (lượt 4 alfonso): gap node 0b24 ≈ 461 node detection-missed ⇒ pool 26k free peaks của 0b24 là nguồn hồi phục đúng trục này (nhưng chỉ ~111 bridge đạt điều kiện — budget/gate kén).
- Rủi ro: (1) node FP → node-multiplier (validator đã spurious ~183k — có lẽ đã no); (2) cạnh `gap_filled` edge_prob=None đi qua edge-filter? (cạnh được viết thẳng, phải chắc không bị filter sau đó giết); (3) tương tác với SHORT_TRACK filter + retention guard + HOCT của mình chưa biết; (4) sinh thêm parent 1-con → thay đổi funnel safe-div (đã thấy: 85 fork vs 124 của base).

## 5. Verdict cho v12

**PORT (A/B validator + LB):** trục node-insertion hoàn toàn mới so với mình, code tự chứa (~170 dòng + patch dump ~40 dòng — mình tích hợp thẳng vào monolith, không cần string-patch), cùng checkpoint, budget 3% tự chặn rủi ro. A/B metric: missed_gt_nodes (63 trên validator) + edges_fragmented (133) + node recall 05db-GT (mỏ neo hidden đo được). Nếu port: đặt GAPFILL sau gap2, TRƯỚC safe-division + short-track filter, và để ALLOW_SYNTHETIC=0 giữ đúng tinh thần "chỉ peak thật".
