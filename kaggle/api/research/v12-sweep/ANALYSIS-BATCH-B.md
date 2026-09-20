# ANALYSIS — BATCH B (7 notebook DIVISION/ML, v12 research)

**Task ID:** 5-b · **Ngày:** 20/9 · **Mục tiêu:** nhãn PORT / THEO DÕI / BỎ cho 7 notebook nhóm division/ML, quy đổi cho kiến trúc v12 (mục tiêu ≥0.948; mình 0.947, cụm 0.948 = hạng 126–199).
**Nguồn:** /home/z/v11-recovery/research/<tên>/ · output của cả 7 kernel đã pull về (kaggle kernels output, read-only) + pull thêm 2 mốc family (fast-v1, flow2-v1) + LB zip để tra điểm tác giả.
**Tham chiếu:** alfonso-v50/ANALYSIS.md (E-1..E-11), V11-RESEARCH.md §2.3, ANALYSIS-BATCH-C.md (đã phủ 11 notebook còn lại; evgendvorkin = batch A).

> Phương pháp: parse .ipynb JSON; các monolith không base64-gzip (đều source thuần); với family thtennant dùng diff từng cell (md5) + pull 2 kernel mốc để cô lập BIẾN; mọi số "hidden test" lấy từ output log/submission.csv thật của kernel. ⚠️ Lưu ý tooling: đọc log qua `cat` bị pipeline ăn mất chuỗi `[m` (ANSI-strip) — phải dùng Read tool khi soi code chứa `[mask]`, `[movie]`.

## Bảng tổng hợp

| # | Notebook | Kiến trúc (1 câu) | Delta chính vs stack mình | Nhãn |
|---|---|---|---|---|
| 1 | **noisyislands-xgboost-div** | Kernel training GBDT 13-feature phân loại fork (GT-only mining, hard-neg = parent 1-con + node cùng frame) | Không tích hợp, không hold-out; feature ≤ DivNet mình; receipt census **302 GT fork / 398 phim node-rich** | **BỎ** |
| 2 | **noisyislands-linker-mlp** | Pilot EdgeMLP 6→16→16→1 trên 6 feature hình học + synthetic dup/noise negatives; train trên GT 4 phim hidden test | Thua xa ILP+learned-bonus mình (BCE 1.92 = không học); 2 ý tưởng: `competing_link_count`, production_sim negatives | **BỎ** (giữ 2 ý tưởng) |
| 3 | **noisyislands-tabpfn** | TabPFN 3.5 zero-shot trên cùng 13 feature + LightGBM reference + calibration affine | Chạy thật chỉ **1 positive**/1061 context, outer-fold 0 pos, "acc 1.000" trivial, provenance label sai | **BỎ** |
| 4 | **pawanmali-nodiv-ablation** | Reyhan-0.947 nguyên bản (checkpoint công khai SHA 3/3) + cell xoá toàn bộ 124 cạnh fork khỏi submission | Purge 100% bản "ngu" (giữ cạnh đầu theo thứ tự CSV); funnel parity **3TP/1FP/9FN** = đúng mình; 2 receipt plateau (disapp 1.5, relaxed 8.5) | **THEO DÕI** (data point) |
| 5 | **thtennant-gapfill** | Family frontier947 (base 0.947-flavor + flow prior) + **GAPFILL**: insert node từ peak sub-threshold (score ≥0.5) bắc cầu gap ≤3 frame | Trục **node-insertion** mình chưa có: +167 node/+240 cạnh hidden; budget 3%; Hungarian + context-cos gate | **PORT (A/B)** |
| 6 | **thtennant-readmit** | gapfill + **READMIT**: tái nhập detection đủ mạnh (≥0.965) bị ILP vứt, ≤4 µm quanh track end/start, rồi re-link | Hiệu ứng lớn nhất batch: 831 node readmit → **ròng +1.014 node/+1.002 cạnh** hidden; 05db 70.809 node vs GT 70.300 | **PORT (A/B)** |
| 7 | **thtennant-divprec** | gapfill + τ symmetry 0.6→**0.4** (+ knob sister-min ĐÃ THỬ và bị tắt: "did not hold on both caches RESEARCH 24") | Fork 85→62 (−27%), node giữ nguyên; receipt phủ định sister-min | **THEO DÕI (1-env A/B)** |

## Family thtennant frontier947 — bảng biến-thí-nghiệm → kết quả

Cấu trúc cumulative (verify md5 12 cell × 3 notebook + pull thêm fast-v1/flow2-v1):

| Biến thể | Biến cô lập | Kết quả đo trên hidden test (từ output) |
|---|---|---|
| (mốc fast-v1 17/9) | base 0.947-flavor | — |
| (flow2-v1 18/9) | +FLOW motion prior (K=12, radius 40 µm, median displacement láng giềng thay velocity prior; gate theo vị trí dự đoán) | motion-relink **+180 cạnh ròng** vs Reyhan base (118.348→118.528, cùng tight55); fork sau đó 124→85 |
| **gapfill-v1** 19/9 | +GAPFILL (so flow2) | +167 node/+240 cạnh (0b24: +111; 05db: +53; 05b6850b: 0); pool free peaks 1.7k/26k/1.9k/9.7k |
| **readmit-v1** 19/9 | +READMIT (so gapfill) | 831 readmit (85/317/63/366); ròng +1.014 node/+1.002 cạnh; gapfill tụt 167→130 (chung pool) |
| **divprec-v1** 19/9 | τ 0.6→0.4 (so gapfill) | fork 85→62 (−23); node set identical; −24 cạnh |

- Base family dùng **cùng 3 checkpoint pilkwang như mình** (SHA verify), SEF_TTA 0.75, tight55, LINEFIT 0.8/2 — chỉ khác: **DC_SAFE_DIV 0.25** (mình 0.20), không có HOCT/reparent/density-guard của mình, VALIDATOR_ENABLE=0 (không sign offline trong kernel).
- **Không có receipt LB tách biến nào** (Teddy Tennant LB best 0.947; các biến thể det096/tight60/flow2-det096 khác cũng trong family). ⇒ giá trị của batch = cơ chế + quy mô hiệu ứng trên hidden test, KHÔNG phải hướng điểm.

## Receipt điểm/bằng chứng quan trọng nhất của batch

1. **pawanmali (đã chấm):** base 0.947 (sub 56207450); ILP-disapp 1.5 + relaxed 8.5 → 0.947 (sub 56207453, "no visible change") — 2 receipt plateau khớp batch C. Nodiv CSV (xoá 124 fork) **chưa có điểm công khai** — nếu lộ: nodiv ≥ 0.947 ⇒ purge an toàn tuyệt đối, nodiv < 0.947 ⇒ cận trên giá trị rescue của biến thể A mình.
2. **Funnel parity validator:** ppsweep 8-stem của pawanmali = adjEJ 0.9260/divJ 0.2308 (3TP/1FP/9FN trên 12 GT) — **trùng hệ funnel mình** (9 FN: 7 no-proposal + 2 mutual_nn) ⇒ trần +2 TP division validator đúng cho cả family public; tight55 +0.0021 proxy (trùng mtoshidesu batch C).
3. **Census:** XGBoost kernel khai thác toàn train: 597 GEFF/398 node-rich/**302 GT fork**; TabPFN mining xác nhận 4 phim 44b6 đầu bảng ~0 GT division (hợp hidden ≈ 2–3 GT division của alfonso V50).
4. **Anti-transfer receipt lịch sử (pawanmali cli-core-nodiv 3/9):** stack yếu 0.926-era: CORE không division local 0.9136 (divJ 0) vs +learned-division local 0.9338 → **LB 0.889**; best của họ trước đó 0.926 là pipeline KHÔNG division. ⇒ ở basin yếu, kênh division local-gain đảo dấu trên LB — cảnh báo cho mọi port "ML division" (đúng lý do noisyislands-series bị BỎ).
5. **05db mỏ neo (đo được khi port):** readmit-v1 FINAL 05db = 70.809 node/68.799 cạnh vs GT 70.300/68.207 — phim hidden dày nhất có GT (lượt-5) ⇒ mọi port gapfill/readmit đo được adjEJ hidden thật offline.

## Top-5 kỹ thuật đáng giá nhất của batch B

1. **GAPFILL — insert node từ sub-threshold detections** (thtennant-gapfill): dump peak ≥0.3 lúc predict → pool peak ≥0.5 cách node >2 µm → bắc cầu end↔start gap ≤3 frame bằng peak thật (0 synthetic), Hungarian cost span/(g+1)+độ lệch peak, budget 3% node, context-cos ≥−0.25. Đánh thẳng 2 lỗi đo được trên validator: edges_fragmented 133 + missed_gt_nodes 63; và trùng trục E-7 (461 node detection-missed ở 0b24).
2. **READMIT — tái nhập detection mạnh bị vứt quanh track hở** (thtennant-readmit): peak ≥0.965 (đủ DET threshold!) trong 4 µm của end/start → thêm node → re-link. Quy mô +1k node/+1k cạnh hidden — lớn nhất batch; tấn công edges_lost_to_detection 79/stem; 54 dòng, tái dùng infra dump của gapfill.
3. **FLOW motion prior** (nền của cả 3 thtennant): dự đoán vị trí kế = median displacement của 12 láng giềng confident nhất trong 40 µm ("cell di chuyển theo đám"), gate theo vị trí dự đoán + raw; thay velocity prior 0.5 của motion-relink. +180 cạnh ròng ở bước relink trên hidden; receipt hướng chưa có — A/B khô trên cache validator trước khi port.
4. **NODIV ablation + census fork** (pawanmali): bản purge-100% của trục mình đang đứng (biến thể A thông minh hơn đã có receipt 188/0); giá trị = đối chứng độc lập + 2 receipt plateau + khả năng lộ điểm nodiv sắp tới.
5. **τ symmetry 0.4 + receipt phủ định sister-min** (thtennant-divprec): 1-env A/B cho lớp near-duplicate-split; sister-min (con quá gần ≠ division) đã bị họ đo và BỎ ("did not hold on both caches") — tiết kiệm cho mình 1 slot thử nghiệm.

## Tương tác/rủi ro cần xử lý khi port (gapfill/readmit)

- Thứ tự chuỗi: đặt sau gap-close/gap2, trước safe-division + short-track filter (node mới sẽ thay đổi funnel safe-div: family thấy fork 124→85); kiểm cạnh `gap_filled`/`readmitted` không bị edge-filter sau đó giết.
- Node-multiplier: validator đã spurious ~183k node — thêm ~1.2k node phải đo node recall/precision 2 chiều trên validator + mỏ neo 05db (70.300/68.207).
- Readmit + dual-seed fusion của mình: "peak bị vứt" phải định nghĩa theo node-set fusion (union/intersect 2 seed), không phải node-set đơn như thtennant.
- Gapfill budget 3% + ALLOW_SYNTHETIC=0 là chốt an toàn tốt — giữ nguyên khi port.

## Hành động đề xuất cho v12 (xếp theo chi phí/tác động, gộp với batch C)

1. **A/B SEF_TTA {0.75→1.0}** (batch C, E-7 axis) — giữ nguyên ưu tiên 1.
2. **PORT GAPFILL+READMIT gộp 1 nhánh lab** (~250 dòng + dump lowdet ~40 dòng vào predict cell): đo validator (missed_gt_nodes 63↓? edges_fragmented 133↓? adjEJ) + mỏ neo 05db → nếu dương, 1 lượt LB. Đây là trục NODE/EDGE hoàn toàn mới so với mọi biến thể hiện có (A/B/C/D đều chỉ xoay cạnh).
3. **A/B khô FLOW prior** trên cache validator (thay velocity prior trong motion-relink) — nếu dương thì port ~150 dòng.
4. **Slot A/B τ0.4** chỉ khi gộp lưới post-chain (đo TÁCH khỏi biến thể A purge — cùng nhắm near-duplicate split, tránh double-count).
5. **Không làm:** 3 kernel noisyislands (BỎ), nodiv-purge bản ngu (biến thể A hơn), sister-min (receipt phủ định), bidir/disapp/relaxed (plateau 2 nguồn).

*Chi tiết từng notebook: `<tên>/ANALYSIS.md` cùng thư mục.*
