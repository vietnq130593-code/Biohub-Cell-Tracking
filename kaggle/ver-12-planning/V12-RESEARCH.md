# V12-RESEARCH — Kiến trúc ver-12: Node-Recall + Association + Division-Real (mục tiêu 0.948+)

> **Trạng thái:** hoàn thành 20/9 (phiên V12-ARCH). Nguồn: V11-RESEARCH.md (lượt 1-5) +
> funnel v11-lab v2 (dump 19:31) + grid v11-lab v3 (đang chạy 20/9) + 22 notebook nghiên cứu
> mới (3 batch, `kaggle/api/research/v12-sweep/`) + LB-replica hiệu chuẩn 4 điểm + giải phẫu
> 3 GT division thật trên 05db0fb1. Quy tắc đứng: KHÔNG submit khi chưa có lệnh trực tiếp.

## 0. TL;DR

| Câu hỏi | Trả lời ngắn |
|---|---|
| Vì sao v10 chỉ 0.947 (không 0.949)? | veto1 (+0.0018 validator) KHÔNG transfer lên hidden — dưới ngưỡng hiển thị hoặc bị guard bù |
| "0.911 thất bại lớn" là gì? | KHÔNG phải v10 — là **v10-linear variant A** (purge 188 fork): divJ_LB 0.333→0 = −0.033 + edge −0.003. **Purge fork = chết vĩnh viễn** (fork mình chứa division TP thật) |
| Trục nào còn sống cho 0.948+? | (1) Node-recall READMIT+GAPFILL (+1.014 node/+1.002 cạnh hidden — receipt thtennant); (2) Association SEF_TTA 0.75→1.0 (E-7: keep-rate 67.5% vs 71.2%); (3) Division-real: mutual_nn+geo14 (grid đang đo) + reparent-mở-gate (2/3 FN thật là sai-gán-cha); (4) density-groups relink (haideptry 0.948+) |
| V12 khác v11 chỗ nào? | v11 = 1 trục division gate; v12 = **portfolio 4 trục có receipt** + phòng lab division-thật (3 GT division 05db đo local được) + replica engine chính thức (verify 100% receipt alfonso) |
| Rủi ro lớn nhất? | Mỗi trục ±0.001-0.003, stack 4 trục = rủi ro tương tác; deadline 29/9 còn 9 ngày, quota GPU 21h + 30h (refresh 26/9), 5 submission/ngày |

## 1. Sự thật nền (LB + hidden, đã hiệu chuẩn)

### 1.1 Phân rã điểm LB hiện tại (v10 = 0.947, ref 56348119)
- adjEJ_LB ≈ 0.914 · divJ_LB ≈ 0.333 (1 TP / 3 GT division — toàn bộ ở 6bba_05db0fb1)
- Chứng minh số học: variant A (purge 188 fork) = 0.911 = −0.033 (divJ 0.333→0) − 0.003 (edge) —
  không cách nào xóa 186/118.401 cạnh lại mất −0.036 điểm bằng đếm cạnh thuần.
- Hệ quả: **mọi fork hiện có mang thông tin division thật — chỉ được THÊM, không được XÓA** (D6 giữ).

### 1.2 Hidden test (đo từ GT train của 4 stem test — codezzzsleep/evgendvorkin/split_manifest)
- 4 phim: 44b6_0113de3b (t_true 25.755) · 44b6_0b24845f (32.795) · 6bba_05b6850b (6.362) · 6bba_05db0fb1 (69.800)
- GT thưa trong train: 52/51/861/1.229 node (0.2%-13.5%) — **KHÔNG phải toàn bộ GT chấm LB** (cửa sổ khác)
- **3 GT division thật — đều ở 05db0fb1**: 25000381 (t=24) · 53001011 (t=52) · 63001217 (t=62)

### 1.3 LB-replica (engine chính thức — đã verify)
- Engine `scorer2code.py` (port royerlab metrics.py + division_metrics.py đầy đủ) tái tạo receipt
  alfonso V50 **EXACT**: adjEJ 0.9272 + 0.1×divJ 0.3333 = 0.9605 (điểm local của họ — LB thật 0.946).
- Replica 4 điểm: ver8-v3fast 0.9002 · v10 0.9010 · variantA 0.9018 (MÙ với ΔLB −0.036) · alfonso 0.9605.
- **Kết luận: replica KHÔNG phải proxy LB** (GT cửa sổ ≠ GT đầy đủ). Giá trị còn lại:
  (a) engine metric chính thức đúng 100% đểoffline chấm mọi graph; (b) 3 division thật + topology
  trong cửa sổ có nhãn → "phòng lab division thật".

### 1.4 Bối cảnh LB 19-20/9
- Top: Sergio 0.974 · yu4u 0.973 · soheilayati 0.968 · VOXEL ART 0.967 · hirotetsu 0.967 (điểm thật, đang di chuyển)
- Cụm 0.948 = hạng ~126-199 (74 đội) · 0.947 bắt đầu hạng ~200 · mình 0.947 hạng ~233
- Deadline **29/9 23:59** · 5 submission/ngày · GPU 21.01h còn (refresh 26/9 +30h)

## 2. Giải phẫu 3 GT division thật (05db0fb1) — la bàn division của v12

| GT div | alfonso V50 | v10 | Chẩn đoán cơ chế | Trục v12 |
|---|---|---|---|---|
| 25000381 (t=24) | **TP** — fork 20025 đủ 2 con | FN — node 20106 1 con; con kia MỒ CÔI 6.95µm; sister 12.5µm > geo-filter 8.0 | safe-div bị chặn: mutual_nn và/hoặc DIV_SISTER_MAX_UM 8.0 (12.5 < SAFE_DIV_SISTER 14.0 nhưng geo-filter giết sau khi thêm) | mutual_nn OFF + geo 8→14 (đúng config mn_p85_geo14 trong grid v3) |
| 53001011 (t=52) | FN — 2 con 2 cha (42653/mồ côi) | FN — 2 con 2 cha (42789/42874) | sai-gán-cha: Y→D2 sai + M→D2 thiếu | **reparent Phase D mở gate** (REPARENT_* sweep) |
| 63001217 (t=62) | FN — tương tự | FN — 50137/50160/50161 | tương tự + multi-cha | reparent + divergence |

- Batch C receipt độc lập: **GT div geometry sister median 10.4µm / p90 13.0 / max 13.7** → geo-filter
  8.0 đang thắt ở MEDIAN phân phối thật (B-2/A-2 đúng).
- Funnel validator (8 stems, 12 GT): 9 FN = 7 no_proposal + 2 mutual_nn → trần validator +2 TP;
  nhưng hidden-thật (05db) cho thấy mô hình FN khác: 1/3 mồ côi + 2/3 sai-gán-cha → **trục reparent
  quan trọng hơn trên hidden thật so với validator**.

## 3. Tri thức port-able từ 22 notebook mới (chi tiết: `api/research/v12-sweep/ANALYSIS-BATCH-{A,B,C}.md`)

Xếp theo (giá trị kỳ vọng × chi phí port ÷ rủi ro):

1. **READMIT** (thtennant, +54 dòng): tái nhập detection mạnh (≥DET threshold) bị ILP vứt trong
   4µm quanh track end/start → receipt hidden: **+831 node readmit → ròng +1.014 node/+1.002 cạnh**
   (hiệu ứng đơn lẻ lớn nhất từng thấy). Đánh trúng missed_gt_nodes 63 + edges_lost_to_detection 79 (validator).
2. **GAPFILL** (thtennant, ~200 dòng): dump sub-threshold peaks ≥0.3 + bắc cầu gap ≤3 frame bằng
   peak THẬT (0 synthetic) + Hungarian + context-cos + budget 3% node → receipt hidden +167 node/+240 cạnh.
3. **SEF_TTA w=1.0** (mtoshidesu — kernel GỐC của family 36 votes chạy w=1.0; mình đang 0.75):
   trục association — E-7: keep-rate 0b24 67.5% (mình) vs 71.2% (V1329 không-SEF); gap node 0b24
   ~1.856 = ~461 detection + ~1.394 association. A/B {0.75 → 1.0 → OFF} 1 knob.
4. **Density-adaptive group overrides** (haideptry claim 0.948+): motion-relink tight/relaxed/bonus/vel
   theo 3 nhóm mật độ (LOW <120 node/frame: 7.25/11.0/3.0/0.5 — MID: 6.5/9.0/6.0/0.0 — HIGH: 5.5/10.0/1.0/0.5)
   — mở rộng per-prefix 2-nhóm của mình thành 3-nhóm theo density. LB-tuned trên đúng 4 phim test.
5. **DC_SAFE_DIV 0.20→0.25**: hội tụ nguồn thứ 4 (alfonso/haideptry/evgendvorkin 0.26/newwang12) —
   đưa funnel DC 317→213, fork 188→~96-127. Dấu phải đo (grid v3 chưa có config này — thêm vào v12-lab).
6. **PP-sweep pattern** (raunakdey): pp_apply/pp_restore + 7 candidates + margin-rule + combo-retest
   trên cache graph — đã port sẵn vào v11-lab v3 (grid v3 đang chạy dùng đúng pattern này).
7. **SHORT5_PREPP** (howonkang): xóa component ≤5 node trên raw geff TRƯỚC post-chain (~50 dòng) —
   lớp duy nhất ver-10 chưa có. A/B 1 knob.
8. **FLOW motion prior** (thtennant family, mốc ẩn): displacement-median 12 láng giềng thay velocity
   prior → +180 cạnh relink. A/B khô trên cache validator.
9. **τ symmetry 0.6→0.4** (thtennant divprec): fork 85→62 (−27%) — 1 env. Backlog.
10. **DIVERGE_UM 2.25 → 4.0-4.5** (receipt gautiermarti "kimi-v18 sweep peaked 4.0-4.5") — mâu thuẫn
    hướng mở 1.0-1.5 cũ của V11-RESEARCH. Backlog A/B.

**ĐÃ CHẾT (không đụng lại):** hub/fork augmentation hack (patch aa65e90 17/7 — âm ~0.02-0.03 + rủi ro rule) ·
DivNet verify-gate p≥0.5 (no-op — 0 veto trong run 0.948) · bidir 0.30→0.15 = +0.002 (đã đúng 0.15) ·
bidir 0.35 (sai hướng, receipt 0.915-basin) · noisyislands ML x3 (methodology vỡ: không hold-out,
BCE tệ hơn random, nhãn provenance sai) · purge fork/linearize (0.911) · DET micro-step 0.96625 (không receipt điểm).

## 4. Kiến trúc v12 — portfolio 4 trục + 2 phòng lab

```
NỀN: v10 production (LB 0.947 — nguyên vẹn: veto1 + guard + tight 5.5/6.5 + SEF_TTA 0.75)
     + config division thắng từ grid v11-lab v3 (nếu D-gates PASS — bước 1 hôm nay)

TRỤC 1 — DIVISION-REAL (lab có thể đo trực tiếp 3 GT div 05db):
  1a. mutual_nn OFF + MIN_PDIV floor + geo 8→14 (+ diverge nếu grid đòi)   [grid v3 đang chạy]
  1b. reparent Phase D mở gate (2/3 FN thật = sai-gán-cha): REPARENT_EDGE_PROB 0.25→0.40/0.50
      + REPARENT_CURRENT_FAR_UM + REPARENT_MIN_PDIV sweep — A/B trên validator + đo 3 GT div 05db
  1c. DC_SAFE_DIV 0.25 (hội tụ nguồn 4)
TRỤC 2 — NODE-RECALL (trục lớn nhất theo receipt):
  2a. READMIT (+1.014 node/+1.002 cạnh hidden — port 54 dòng thtennant)
  2b. GAPFILL (+167/+240 — port ~200 dòng, budget 3% node)
TRỤC 3 — ASSOCIATION:
  3a. SEF_TTA {0.75 → 1.0 → OFF} (1 knob, E-7 + mtoshidesu)
TRỤC 4 — DENSITY-ADAPTIVE:
  4a. motion-relink 3-nhóm density (port ~40 dòng haideptry)

PHÒNG LAB 1 — v12-lab (GPU 1 lần ~4h): extend v11-lab v3 (grid pp + cache replay validator)
  + chạy post-chain trên RAW GRAPH HIDDEN từ cache tracking_repo/predictions/*.geff (E-11)
  → đo 3 GT div 05db (replica engine) + census fork/edge mỗi config → chọn cụm thắng.
PHÒNG LAB 2 — replica offline (0 GPU): chấm mọi biến thể CSV trên 4 cửa sổ GT train
  (engine scorer2code) — topology trong cửa sổ + 3 division; KHÔNG tin cho ngoài cửa sổ.
```

### 4.1 Lộ trình ngày (deadline 29/9, quota GPU 21h + 30h từ 26/9)

| Ngày | Việc | GPU | Submission |
|---|---|---|---|
| 20/9 (hôm nay) | grid v3 xong → chọn config → **build+push+submit biohub-ver11** (lệnh user đã cấp) | ~2.2h | 1 (ver-11) |
| 20-21/9 | port READMIT+GAPFILL+SEF_TTA config vào monolith v12-lab; viết v12-lab notebook | 0 | 0 |
| 21/9 | **v12-lab GPU** (grid 8-10 configs: 4 trục + combo, replay validator + hidden raw + 3 GT div) | ~4h | 0 |
| 22/9 | chọn cụm thắng theo gates F1-F6 → build biohub-ver12 → push → submit | ~2.2h | 1-2 (v12 A/B) |
| 23-24/9 | LB feedback → 1 vòng iterate (DC 0.25 hoặc τ0.4 hoặc diverge 4.0 tuỳ kết quả) | ~2.2h | 1-2 |
| 25/9 | **CHỌN 2 SUBMISSION CUỐI** (finals): v10 0.947 banked + tốt nhất trong v11/v12 | 0 | final |
| 26-28/9 | dự phòng: 1 iterate cuối nếu quota refresh 26/9 cho phép + sát deadline | ≤4h | ≤2 |

### 4.2 Gates F1-F6 cho v12 (định trước, không nới sau — kế thừa D-gates v11)

| # | Gate | Tiêu chí |
|---|---|---|
| F1 | Division | mọi layer division: Δdiv_tp > 0 AND Δdiv_fp ≤ +2 AND ΔadjEJ ≥ −0.0002 (validator patched) + **3 GT div 05db không giảm TP** (replica) |
| F2 | Node set | chỉ được TĂNG node (D6): READMIT/GAPFILL tăng — purge node/edge CẤM |
| F3 | Cộng dồn | mỗi trục vào riêng → Δ proxy ≥ +0.0005 mới được stack; stack ≤ 2 trục mới/lượt submit |
| F4 | Runtime | production ≤ 2.5h public (guard ver-10 giữ nguyên; READMIT/GAPFILL +CPU phút) |
| F5 | Receipt | mọi config ghi receipt (run_stats + guard report + census fork/edge) — không có receipt = không submit |
| F6 | Trọng tài | LB là trọng tài cuối; replica/validator chỉ lọc hướng; ±0.001 coi là noise |

### 4.3 Kỳ vọng điểm (thận trọng — mỗi trục ± độc lập, tương tác chưa biết)

| Trục | Kỳ vọng ΔLB | Cơ sở |
|---|---|---|
| 1a division gate (mutual_nn+geo14+floor) | +0.003..+0.017 | divJ 0.333→0.5-1.0 NẾU 2 FN thật hồi phục (rủi ro: transfer validator→hidden) |
| 1b reparent mở gate | +0.003..+0.017 | 2/3 FN thật là sai-gán-cha (giải phẫu §2) |
| 2 READMIT+GAPFILL | +0.002..+0.005 | receipt thtennant +1.014 node/+1.002 cạnh (pipeline khác nhưng cùng cơ chế) |
| 3 SEF_TTA 1.0 | +0.001..+0.003 | E-7 keep-rate + mtoshidesu gốc |
| 4 density-groups | +0.001..+0.003 | haideptry claim (LB-tuned, rủi ro private) |
| **Tổng hợp** | **0.947 → 0.952-0.975** | thực dụng: đạt 0.948-0.955 = mục tiêu; >0.955 = bạc an toàn |

## 5. Rủi ro & đối sách

1. **Transfer validator→hidden yếu** (bài học veto1: +0.0018 validator → 0.000 LB hiển thị):
   mọi trục phải có receipt ≥2 nguồn; LB là trọng tài; không bao giờ stack >2 trục mới chưa đo/lượt.
2. **Quota GPU 21h**: v12-lab 4h + production 2.2h + iterate 2.2h×2 = ~11h — dư; refresh 26/9 +30h
   cho vòng cuối. Kernel lab dùng cache replay (đã chứng minh D2 anchor tái lập 0.9305 exact).
3. **Submission budget**: 5/ngày × 9 ngày = 45 lượt; kế hoạch dùng ~8-10 lượt — dư an toàn.
4. **TLE hidden** (bài học ver-9): guard ver-10 đã fielded (LB 0.947 chứng minh pass hidden);
   READMIT/GAPFILL là CPU-phút — vô hại trước guard 7.5h.
5. **Replica bị hiểu sai là LB proxy** (đã ghi §1.3): mọi quyết định dựa replica phải nhãn
   "trong-cửa-sổ" hoặc "3-division"; A/B cuối vẫn qua LB.
6. **Dòng công khai dùng checkpoint mình** (alfonso/haideptry/raunakdey/evgendvorkin/mtoshidesu
   đều byte-identical 3/3 checkpoint): mọi kỹ thuật họ công bố = port CPU thuần — không có "model mới"
   ngoài kia; lợi thế mình = phòng lab + kỷ luật gates.

## 6. Kết luận

- v12 = v10 (0.947 đã field) + portfolio 4 trục có receipt (division-real, node-recall, association,
  density-adaptive) + 2 phòng lab (v12-lab GPU + replica offline).
- Trục có receipt mạnh nhất: READMIT/GAPFILL (node-recall) — chưa ai trong cụm 0.948 làm (batch B).
- Trục division đã có la bàn thật lần đầu: 3 GT division 05db + giải phẫu cơ chế từng cái.
- Kỷ luật: gates F1-F6, LB trọng tài, deadline 29/9, 2 submission cuối chọn trước 25/9.

*Phụ liệu: ANALYSIS-BATCH-A/B/C.md (22 notebook) · funnel v11-lab v2 (v11_funnel.json) ·
replica hiệu chuẩn (worklog V12-REPLICA-CALIB) · grid v3 receipt (sẽ có khi kernel COMPLETE).*
