# ANALYSIS — pawanmali/biohub-zhincez947-nodiv-ablation-v1 (zhincez947 nodiv ablation)

**Task ID:** 5-b · **Ngày:** 20/9 · **Loại:** SUBMISSION KERNEL + ABLATION CELL — bằng chứng trực tiếp nhất batch B về giá trị ròng của kênh division trên hidden test.
**Nguồn:** /home/z/v11-recovery/research/pawanmali-nodiv-ablation/biohub-zhincez947-nodiv-ablation-v1.ipynb (4 cell: markdown 2 + monolith 214 KB + ablation 30 dòng) + output pull 20/9 (submission.csv POST-ablation, run_stats.csv, ppsweep_results.csv, live_resume logs).

## 1. Cấu trúc

- **Cell 0–2:** nguyên văn notebook **zhincez "0.947 LB runnable with public datasets"** (= Reyhan Ksatria 0.947 v5) chỉ đổi 3 path artifact sang dataset public của pilkwang; SHA verify 3/3 checkpoint (primary `12f6881e…`, secondary `9bac2fa0…`, deepcenter `8040999a…`) — **cùng 3 checkpoint với mình**. Env khớp stack mình: DET 0.965, ILP 0/2/div1.2, SAFE_DIV 9/14/τ0.6/2.25/10.0/caps 0.0076/0.00375, DC 0.20, gap 5.0, bidir 0.15, SEF_TTA 0.75, tight 6.0 (→ ppsweep chọn tight55).
- **Cell 3 (bản chất của notebook):** "Real ablation" — đọc `submission.csv` của chính kernel, với mỗi dataset duy nhất `source_id`: giữ cạnh ĐẦU TIÊN theo thứ tự CSV, xoá mọi cạnh thứ 2+ ⇒ **loại toàn bộ division prediction, không thêm node/edge giả**. Ghi đè lại submission.csv.

## 2. Receipts

**Đã ghi trong markdown:**
- Base: submission 56207450 → **public LB 0.947** (T4×2).
- Biến thể ILP_DISAPPEARANCE_WEIGHT 2→1.5 + MOTION_RELINK_RELAXED_UM 10→8.5: submission 56207453 → **0.947** ("no visible change at three decimals") — receipt plateau 2 knob này.
- **Không ghi điểm cho nodiv CSV** — kernel chạy 20/9 01:16; LB best của pawanmali vẫn 0.947 (không phân biệt được nodiv < hay = 0.947).

**Tính lại từ output (verify số học):**
- Pipeline log: safe-divisions added = 55+25+10+34 = **124 fork** trên hidden test; pre-ablation 241.356 row (122.808 node / 118.548 edge).
- Output submission.csv post-ablation: 241.232 row (122.808 node / **118.424 edge**) ⇒ đúng xoá **124 cạnh fork**, node bảo toàn — ablation chạy đúng như mô tả.
- **ppsweep (8 stem validator, N=8 như mtoshidesu batch C):** base proxy 0.9490 (adjEJ 0.9260, divJ 0.2308) → tight55 0.9511 (+0.0021); **div 3 TP / 1 FP / 9 FN trên 12 GT division — TRÙNG funnel validator của mình** (9 FN, trong đó 7 no-proposal + 2 mutual_nn); missed_gt_nodes 63, spurious_pred_nodes ~183k, edges_fragmented 133, edges_lost_to_detection 79, wrong_association 0.

**Bối cảnh dòng "nodiv" trên Kaggle (khai quật thêm):**
- `adityaraj0612/biohub-probe-nodiv-sub` (26/8): kernel 10 dòng copy một CSV nodiv từ dataset vào working để chấm — điểm không công khai; Aditya2909rb LB best 0.947.
- `pawanmali/biohub-cli-core-nodiv-v1` (3/9, markdown đầy đủ): stack CLI-config 400-epoch yếu hơn (không TTA patch, không post-chain): CORE không division đo local 0.9136 (divJ=0) vs +learned-division-classifier local 0.9338 nhưng **LB 0.889 — kèm anti-transfer receipt**: "prior best 0.926 là pipeline thuần không division"; quote tiền lệ 26/7 "mcflow CORE division disabled" 0.883. ⇒ Ở basin yếu, kênh division local +0.02 đảo thành LB −0.037.
- zhincez (người sở hữu base notebook) có chuỗi kernel phân tích riêng (0.952, div sign khớp LB 3/3 — đã thuộc batch A).

## 3. Ý nghĩa cho v12

1. **Census fork family:** Reyhan-0.947 stack sinh **124 fork** trên hidden test; mình (DC 0.20 + HOCT mode-1 + reparent) sinh 188. Nếu chuyển sang flavor thtennant (flow prior, xem batch-B thtennant) chỉ còn 85. Độ nhạy 124↔188↔85 cùng claim 0.947 cho thấy kênh fork có tolerance lớn ở cụm này (khớp tolerance ±54 cạnh của V49 alfonso ở đỉnh).
2. **Điểm cuối trục purge:** ablation này = "purge 100% ngơ ngơ" (giữ cạnh đầu theo thứ tự CSV, không chọn con gần µm hơn, không rescue). Biến thể A của mình (port Cell-2 alfonso: linearize giữ con gần µm + cytokinesis rescue, receipt 188→0 int) **là bản thông minh hơn của đúng thử nghiệm này** — không cần port gì thêm từ pawanmali.
3. **Funnel parity:** 3 TP/1 FP/9 FN y hệt mình ⇒ mọi kết luận funnel của mình đúng cho cả family public 0.947; trần division validator (+2 TP mutual_nn) không đổi.
4. Nếu pawanmali (hoặc ai đó) công khai điểm nodiv: nếu nodiv ≥ 0.947 thì toàn bộ 124 fork ròng ≈ 0 trên LB (purge an toàn tuyệt đối); nếu < 0.947 thì một phần fork là TP edge (dùng làm cận trên giá trị rescue của biến thể A). Hiện CHƯA có — không thay đổi kế hoạch A/B bằng LB của mình.

## 4. Verdict cho v12

**THEO DÕI** (data point công khai, không port code): bản purge ngu hơn biến thể A đã có sẵn của mình; giá trị = (a) xác nhận 2 receipt plateau ILP-disapp/relaxed, (b) census 124 fork, (c) funnel parity 3/1/9, (d) khả năng lộ điểm nodiv trong vài ngày tới để đối chiếu chéo với biến thể A của mình khi submit.
