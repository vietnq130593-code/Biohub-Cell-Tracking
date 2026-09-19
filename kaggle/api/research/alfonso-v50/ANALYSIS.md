# ANALYSIS — alfonso1799 "Biohub Top 3 Push V50 Streamlined SOTA" (LB 0.9605)

> Nghiên cứu 19/9/2026 (03:44–03:55). Nguồn: `kaggle kernels pull alfonso1799/biohub-top-3-push-v50-streamlined-sota` + `kaggle kernels output` (kernel COMPLETE).
> Files: `biohub-top-3-push-v50-streamlined-sota.ipynb` (3 cells), `v1329_runner.py` (giải nén từ base64+gzip của Cell 1 — 3.092 dòng, 176KB), `submission.csv` (final), `v1329_submission.csv` (foundation), `v1329_work/*` (receipts).

---

## 0. Tóm tắt 1 đoạn

Notebook Top-3 (0.9605) = **cùng dòng dõi harmonic stack của mình** (V1290/V1327-family; env run-config trùng hệ ver-10 của ta: DET 0.965, ILP 0.0/2.0, SAFE_DIV 9.0/14.0/tau 0.6, DC 0.25/0.25, gap 5.0, bidirectional 0.15) + 2 khác biệt lớn:

1. **Primary detector fine-tuned** (V1327-W3: 256 bước centered-W3 từ V1274, frozen transformer+BN, sha `c0562f35…`, dataset riêng `biohub-v1327-w3-real-model`) — bước mình KHÔNG có (mình dùng weights gốc support-pack).
2. **Lớp post-link "V50" (Cell 2 — thứ thật sự MỚI):**
   - **Fork linearization**: MỌI node có 2 cạnh out → giữ con GẦN hơn (theo µm, scale (1.625, 0.40625, 0.40625)), bỏ cạnh kia → **0 division theo thiết kế**;
   - **Physical cytokinesis recovery**: chỉ trên dataset dày (≥30.000 node), tối đa **2 division/dataset**, qua ~10 gate hình học hyper-chặt + fitness score;
   - Assert DAG (out ≤ 2, in ≤ 1, t+1).

Kết quả trên hidden test (output thật tải về): 92 fork của V1329 (44+16+5+27) bị purge hết → final chỉ còn **2 division rescued trên `6bba_05db0fb1`** (0/0/0/2). Markdown tự nhận: TP=1, FP=0, **Div Jaccard 0.3333**.

## 1. Census hidden test (từ receipts — thứ quý nhất)

4 dataset, 100 frame mỗi dataset, tổng ~123.485 node (V1329 output):

| dataset | node (final) | edge (final) | div_parents V1329 → final | mật độ/frame |
|---|---|---|---|---|
| `44b6_0113de3b` | 25.290 | 24.604 → 24.560 | 44 → **0** | ~221–294 |
| `44b6_0b24845f` | 22.580 | 21.179 → 21.163 | 16 → **0** | ~190? (fallback 98/100 frame!) |
| `6bba_05b6850b` | 6.086 | 5.898 → 5.893 | 5 → **0** | ~55–95 |
| `6bba_05db0fb1` | 69.529 | 67.211 → 67.186 | 27 → **2** | ~695 (dense) |

- **Div jaccard 0.3333 + "TP=1, FP=0"** → GT division hidden test ≈ **2–3 SỰ KIỆN TOÀN BỘ** (nếu pred đếm=1: GT=3; nếu pred đếm=2 (như CSV): GT=2). So: validator mình 12 GT (8 stems), audit megayak 151 GT — **hidden test thưa gấp ~4–50 lần**.
- 0.9605 ≈ edge 0.927 + 0.1×0.333 → **điểm Top-3 đến từ EDGE, không phải division**.
- Retention guard: `44b6_0b24845f` fallback 98/100 frame về primary (min_ret 0.278) — secondary/harmonic fusion TỒN TẠI trên dataset đó; các dataset khác min_ret 0.905–0.974.

## 2. Kiến trúc V50 (2 cell)

**Cell 1** = launcher: giải nén `v1329_runner.py` (base64+gzip 56KB) → subprocess riêng. Runner = stack V1290-family đầy đủ: 8-view D4 TTA (cả 2 seed), logit-align + blend secondary (det w=0.80, edge w=0.15, mode `low_margin_consensus`, low-margin 0.35, edge-cand-threshold 0.48), harmonic bidirectional (w=0.15), ILP pyscipopt (app 0.0, dis 2.0, **div 1.2** — [sửa lượt 2: env run-config `BIOHUB_ILP_DIVISION_WEIGHT=1.2`, không phải 1.0]), retention guard 0.90 per-frame fallback, 2-GPU shard + merge, ILP → geff → post: edge-filter (max 14µm) → motion relink (tight/relaxed internal, velocity internal, **learned bonus 1.0** [sửa lượt 2: env `MOTION_RELINK_LEARNED_BONUS=1.0`, không phải 0.75]) → single-parent repair → gap-close (6µm run / 5.0 run-config, reuse 3.2, cap 5%/2000, synthetic-midpoint refine percentile-weighted) → **gap2 ON** (env `OUTPUT_GAP2_RECOVERY=1` [sửa lượt 2: lượt 1 ghi "off" — sai]) → **safe-div** (run-config: parent 9.0, sister 14.0, tau 0.6, diverge 2.25, mutual-NN, DC veto 0.25; source hiện tại đã siết 4.7/7.2/tau 0/DC 0.10–0.12) → geo-filter (10.5/8.0, drop-to-single) → prune isolated → short-track filter (min 6, keep div components) → **linefit smooth (w=0.8, window ±2, degree-1 per-axis, blend)** → **V1057 reconcile (min raw edge prob 0.30 — xem §7 lượt 2: delta THẬT thứ 3, mình KHÔNG có)** → CSV (z/y/x **round int**, max(0,·)) → guard report sha256.

Chi tiết đáng học riêng:
- `linefit_smooth_output_graph`: với node interior của track tuyến tính (chain 1-1), fit đường thẳng per-axis trên cửa sổ ±2 frame, `new = 0.2×orig + 0.8×fit` — giảm nhiễu vị trí node → lợi adjEJ. **Mình đã có** (ver-10 LINEFIT 1/0.8/2 ✓).
- `refine_synthetic_midpoint`: midpoint gap được refine bằng intensity-centroid cục bộ (percentile-20 baseline, weight=max(patch−base,0), shift ≤3.2µm). **Mình đã có** ✓.
- V1284 coordinate refinement: **TẮT** (`V1284_MODE='zero'`) — không phải delta active.
- Runner hiện tại (source mới) siết safe-div 9.0→4.7 / sister 14.0→7.2 / tau 0.6→0 / DC 0.25→0.10–0.12: thừa nhận gate cũ LỎNG (FP fork nhiều) — nhưng với Cell 2 linearize thì gate trong chỉ ảnh hưởng fork pre-linearize (chọn con nào sống).

**Cell 2 = "Master SOTA Post-Link"** (code đầy đủ trong notebook, ~200 dòng, KHÔNG nén) — thứ mình chưa có:

1. **Linearize**: fork (len tgts == 2) → giữ con gần parent hơn (µm); dropped_forks đếm per dataset.
2. **Cytokinesis recovery** (chỉ dataset ≥ 30.000 node; thực tế chỉ `6bba_05db0fb1`):
   - source phải có đúng 1 con hiện tại; candidate = node t+1 **in-deg 0** (mồ côi);
   - **mutual-NN bắt buộc**: candidate phải là NN của con hiện tại (cKDTree);
   - gate: parent→con ≤ 8.5µm (cả 2 con); sister ∈ [8.5, 13.5]µm; x,y ∈ [20, 236] (margin biên FOV); track_len cả 2 ≥ 12; cháu: `gc_dist − sister_dist ≥ 1.20µm`; góc 2 vector parent→con ≥ 140°; COM-dev (parent tới midpoint con) ≤ 3.2µm; sister tách xy ≥ 9.6µm, dz ≤ 4.0µm;
   - fitness = `ang/180 + (1 − com_dev/2.8) + div/5 + min(l1,l2)/30`; sort desc; greedy 1-lần-dùng (parent, con không trùng); **cap 2/dataset**.
3. Assert DAG + rebuild CSV.

**Guard report tự nhận** (minh bạch đáng khen): `organizer_labels_used_for_configuration: true` (fine-tune trên released labels), `leaderboard_feedback_used_for_configuration: true` — tức các gate cytokinesis ĐÃ được tune bằng feedback LB (biết div jaccard 0.3333 và sự kiện cụ thể P=20025→D=20865 sau submit). Copy nguyên gate = copy phần fit-hidden-test của họ; bài học chuyển được là **cấu trúc** (purge + hyper-verify + cap), không phải con số.

## 3. Phả hệ & score axis

- Chain: `reyhanksatria/biohub-cell-tracking-0-946-lb` (public 0.946) → `raykkretzschmar/biohub-bidirectional-primary-union13-diagnostic-v1` → V1274/V1290 → **V1327 (adapted det)** → V1329 → **V50 (notebook này)**.
- Score axis nội bộ: 0.933 fixed-90 dual-seed → 0.934 harmonic fusion → 0.939 wider divisions/calmer fusion → 0.941 repair adaptation → 0.946 edge-feature TTA → (V50: +adapted det + linearize + rescue) → **0.9605**.
- +0.0145 bước cuối = adapted detector (không tách được) + purge 92 fork (sạch FP edge+div) + 2 rescue (0.033 div term). Khoảng ⅔ gain khả năng đến từ purge fork (edge precision) — đúng dạng phạt FP division mà megayak/zhincez đã đo.
- Runtime: **3.6h** hidden test (bỏ "redundant V42 linear edge inference ~6h" — không có trong stack mình). Predict chỉ 9.9 phút trên 2 GPU; phần còn lại là ILP + post + install deps.

## 4. So sánh trực tiếp với ver-10 mình

| Thành phần | alfonso V1329/V50 | ver-10 mình | Đánh giá |
|---|---|---|---|
| D4 TTA 8-view, harmonic bidir 0.15, low_margin_consensus, retention guard, linefit 0.8/±2, short-track 6, gap-close+refine, gap2 | ✓ | ✓ (đã có đủ) | parity |
| Env run-config | DET 0.965, ILP 0.0/2.0, SD 9/14/τ0.6, DC 0.25/0.25, gap 5.0 | DET 0.965, ILP 0.0/2.0, SD 9/14/τ0.6, DC 0.25/**0.20**, gap 5.0 | gần trùng (DC safe-div 0.20 vs 0.25) |
| Primary detector | V1327-W3 fine-tuned 256 bước (sha verify, dataset riêng) | weights gốc support-pack | **delta thật — cần train, rủi ro, không làm mùa này** |
| Secondary seed | seed 314159, best 0.978, epoch 381/400 | tương đương (cùng pack) | parity |
| **Fork linearization + cytokinesis rescue** | ✓ (Cell 2) | ✗ | **delta MỚI — CPU-only, ~200 dòng, áp được lên output v10** |
| **V1057 reconcile (re-add raw edge ≥0.30 sau filter)** | ✓ (chạy SAU linefit, TRƯỚC CSV) | ✗ (không có hàm tương đương) | **delta MỚI phát hiện LƯỢT 2 — port candidate #3, ~110 dòng, xem §7** |
| Env run-config (37 knobs) | 36/37 giống hệt | chỉ `DEEPCENTER_SAFE_DIV_THRESHOLD` 0.25 (mình 0.20) | **parity gần tuyệt đối [lượt 2]** |
| Output fork count hidden | 92 → 2 | **188 → chưa áp (đếm trực tiếp từ CSV banked v3fast + output v10)** | **mình GẤP ĐÔI: 127 safe-div (DC 0.20) + ~80 reparent [lượt 2]** |

## 5. Hàm ý chiến lược (cho V11-RESEARCH.md §2.3/§5.4)

1. **Kinh tế division trên hidden test khác hẳn validator**: hidden ≈ 2–3 GT tổng; ~90 fork như mình → div jaccard ≈ 0.03–0.08 (TP 2–3/90 pred). Trần kênh division trên hidden: 0.1×(3/3 − ~0.03) ≈ +0.067 LÝ THUYẾT, +0.01–0.04 thực dụng. alfonso đã lấy 0.033 bằng 1 TP. **Cuộc đua thật ở trục edge (0.927 của họ).**
2. **Fork FP đắt gấp đôi** (đã biết) nhưng giờ có SỐ: purge 92 fork ≈ đóng góp lớn trong +0.0145. Với hidden ≈ 3 GT, chiến lược "purge + hyper-verify" có sign dương trên hidden dù sign ÂM trên validator (linearize giết 4/12 TP validator) → **validator không thể trọng tài quyết định này; đây là cược domain-economy dựa trên receipt của top-3**.
3. **Trục mới rẻ nhất mùa giải: "v10-linear"** = v10 output + Cell 2 layer (linearize + rescue, có thể giữ nguyên gate của họ làm baseline rồi calibrate trên validator bằng cách đếm bao nhiêu TP validator 12 GT sống sót qua gate — nếu ≥4 thì gate quá lỏng, nếu 0 thì quá chặt). CPU-only, không đụng pipeline bank, A/B được bằng 2 lượt submit.
4. Kế hoạch V11 cũ (mở gate + DivNet) **không chết** nhưng phải re-base: nó đuổi phần div term còn lại (+0.01–0.02 max trên hidden) và các gate mở phải giữ FP gần 0 — trong khi fork base ~90 FP đã ở đó. **Thứ tự đúng: purge trước (v10-linear), mở gate sau (v11) — hoặc gộp: v11 = mở gate + linearize + rescue (bắt cả hai phía).**
5. Fine-tune detector kiểu V1327-W3: ghi nhận là delta của họ, không sao chép (cần train + rủi ro + còn 10 ngày).

## 6. Nguồn checksum (đối chiếu sau này)

- Notebook sha (guard): parent `79d8ac1b…`, exact V1327 parent `74cc03e0…`, source `3e65ca69…`
- Checkpoints: primary `12f6881e…`, secondary `9bac2fa0…` (seed 314159, best 0.978), deepcenter `8040999a…`
- Final submission.csv 242.287 rows; v1329_submission.csv 242.377 rows.

---

## 7. ⭐ REVIEW LƯỢT 2 (19/9 ~04:30 — tái nghiên cứu deep-verify, 3 vai trò AI-engineer/architect/algorithms)

Mục tiêu: tìm điểm lượt 1 bỏ sót. Kết quả: **4 sửa trực tiếp ở trên (gap2 ON, ILP div 1.2, learned bonus 1.0, V1057 vào bảng §4) + 6 phát hiện mới + 2 cave.**

### 7.1. Verify bằng đếm trực tiếp (không tin doc lượt 1)

- **Census KHỚP 100%**: đếm lại từ 2 CSV — V1329: 25.290/22.580/6.086/69.529 node, 24.604/21.179/5.898/67.211 edge, forks **92** (44/16/5/27); final: forks **2** (cả hai trên `6bba_05db0fb1`), node set **123.485 = 123.485** (bảo toàn 100%), edge 118.892 → 118.802 = **đúng 90 cạnh bị purge = 92 fork − 2 rescue** — nhất quán nội bộ hoàn hảo.
- **2 rescue events cụ thể (verify từ CSV final)**: (1) parent **20025** (t=24, x=120,y=77) → daughters {20823, 20865}, d=2.87µm/8.05µm — khớp markdown `P=20025 -> D=20865`; d=8.05µm sát biên gate 8.5µm; (2) parent **32231** (t=39, x=215,y=42) → daughters {32980, 33069}, d=6.40µm/4.91µm — event thứ 2 markdown không nhắc. **Cả 2 nằm giữa FOV (x,y ∈ [20,236])** — gate biên FOV loại vùng rìa (nhiễu dự đoán biên cao).

### 7.2. ⭐ Phát hiện lớn nhất lượt 2 — V1057 reconcile là delta THẬT thứ 3 (port candidate #3)

`_v1057_reconcile_in_memory` (runner dòng 2654–2760, gọi ở dòng 2912 — **SAU toàn bộ filter chain + linefit, TRƯỚC CSV**):
- Input: raw edges (ILP output, kèm `edge_prob`) + node set final + edge set final;
- Lặp mọi raw edge KHÔNG có trong final: nếu 2 đầu còn sống, t+1, source không phải fork (out ≤ 1), owner hiện tại của target không phải fork, **raw edge_prob ≥ 0.30** → ứng viên;
- Greedy theo prob giảm dần, mỗi source/target dùng 1 lần; **được phép THAY cạnh yếu hơn** (cạnh final có source/target bị ứng viên chiếm sẽ bị loại) — mô tắn code: "Hidden movies may contain conflicts absent from the visible/local census. Resolve those deterministically by raw confidence";
- Assert DAG (in ≤ 1, out ≤ 2) + nhận xét `preserve_existing_divisions: true`.

→ Bản chất: **lớp hồi phục recall cho trục EDGE** — post-processing (edge-filter/relink/gap/short-track) bỏ nhầm cạnh có evidence cao → reconcile trả lại. **Kiểm tra: KHÔNG có trong ver-8/9/10 mình (grep 0 kết quả) và KHÔNG có trong cả public 0.947/0.948 family (zhincez runnable, cloudssdut, zhuzhenghaomax — grep 0)** → độc quyền nhánh alfonso, cùng cấp độ "layer mình chưa có" với Cell 2.
⚠️ **Rủi ro interplay khi port**: reconcile có thể trả lại cạnh mà HOCT veto mode-1 của mình đã giết (alfonso không có HOCT — không có hướng dẫn). Nếu port: chạy reconcile TRƯỚC HOCT veto (để HOCT vẫn có quyền phê duyệt cuối) hoặc loại cạnh đã-veto khỏi pool ứng viên. Gain thực tế KHÔNG đo được từ receipts của họ (stats variant_rows không nằm trong output tải về) — phải A/B bằng LB như Cell 2.

### 7.3. Env diff hệ thống (37 knobs regex trên cả 2 file) — parity gần tuyệt đối

36/37 knobs **giống hệt từng giá trị** (kể cả GAP_DENSITY_ADAPTIVE 1/6.5/0.040/0.125/3, ADAPTIVE_SHORT_TRACK_RESCUE 1/4/0.88/3.0/0.012/120, DC_GAP_VETO 0.25/8.5, EDGE_FEATURE_TTA, DUAL_SEED 0.90, SAFE_DIV full 9/14/τ0.6/2.25/10.0/0.0076/0.00375…). Khác biệt duy nhất: **`DEEPCENTER_SAFE_DIV_THRESHOLD` 0.25 (họ) vs 0.20 (mình)**.
- Funnel DC của họ (receipts): 763 geometric candidates → DC-checked 763 → accepted 213 (rejected 550) → added 92 (caps/mutual-NN/timing).
- Funnel DC của mình (run_stats v3fast): accepted **317** → added **127**. Ngưỡng 0.20 lỏng hơn → +104 proposals sống, +35 forks. **Đây là 1 trong 2 nguồn fork cao của mình.**
- Knobs mình CÓ mà họ KHÔNG (lớp riêng của mình, không phải thiếu): DIVNET_* (rank W15), REPARENT_* (Phase D), HOCT_*, MOTION_RELINK_TIGHT_UM 5.5 + per-prefix {44b6:5.5, 6bba:6.5}, SECONDARY_EDGE_FEATURE_TTA_W 0.75, DEEPCENTER_TTA, PPSWEEP_*, GAP2_MAX_STEP_UM 4.4, GPU_SHARD val_single (họ shard 2 GPU).

### 7.4. ⭐ Fork count của MÌNH trên hidden = 188 (đếm trực tiếp, không ước lượng)

- ver-8 v3fast (banked 0.947): forks **188** (64/41/13/70) — GẤP ĐÔI alfonso 92.
- Output v10 (kernel COMPLETE 04:14, đã submit ref 56348119): forks **188 y nguyên** (HOCT mode-1 bảo vệ node ≥2 con → fork không đổi ✓ đúng thiết kế).
- Phân rã (run_stats): `safe_divisions_added` = 127 (55/25/10/37) + `reparent_added` = 80 (15/19/3/43) → 188 fork sources (có chồng lấn). **80 fork từ reparent Phase D — lớp alfonso không có** → port Cell 2 nguyên văn sẽ purge cả fork reparent (188−2 = 186 cạnh, gấp đôi volume của alfonso).
- Node count hidden của mình: 25.637/20.724/6.151/70.300 vs họ 25.290/22.580/6.086/69.529 — khác nhiều nhất `44b6_0b24845f` (mình thiếu ~1.856 node — dataset harmonic-fusion fallback 98/100 frame của họ; trục node ảnh hưởng adjEJ qua node-multiplier, không actionable mùa này).

### 7.5. ⭐ Cave quan trọng — fork ≠ division prediction theo rule scorer patch

Validator mình (8 stems, production v10): `safe_divisions_added` = 139 nhưng scorer đếm **div_fp = 2** (4 TP/2 FP/8 FN, divJ 0.286). → **Phần lớn fork KHÔNG được rule patched tính là division prediction** (yêu cầu cấu trúc parent-match + 2 nhánh con phân biệt). Hệ quả:
1. Đọc census "44→0, 16→0…" của alfonso như "purge 92 FP division" là **xấp xỉ** — giá trị TIN CẬN của purge là **edge precision** (mỗi fork sai ≥ 1 cạnh FP trên trục edge), còn ΔdivJ phụ thuộc cấu trúc từng fork, không đếm được từ ngoài;
2. divJ hidden của MÌNH hiện tại không suy ra được từ 188 forks (có thể từ ~0.01 đến ~0.4) → **không phân rã được 0.947 của mình thành edge + div** — mọi so sánh "edge mình 0.94x vs edge họ 0.927" là SỰ ĐOÁN, không phải receipt;
3. Con số divJ 0.3333/TP=1/FP=0 của alfonso là **suy luận từ LB feedback** của họ (guard report tự nhận `leaderboard_feedback_used_for_configuration: true`) — không thể verify từ ngoài, chỉ tin ở mức "họ đã tune gate rescue quanh các event này".

### 7.6. Sửa nhận định "0.9605 = edge 0.927 + 0.1×0.333"

Số học: markdown họ ghi EJ 0.9247 + Node Recall 0.9816; 0.9247 + 0.0333 = 0.9580 ≠ 0.9605 — khoảng cách +0.0025 ≈ **node-multiplier term** (adjEJ = EJ hiệu chỉnh theo node recall, đúng cấu trúc metric `adjusted_edge_jaccard` có `node_multiplier_term 0.1×ratio`). Kết luận lượt 1 giữ nguyên về hướng (edge ~0.927 khớp 0.9605 − 0.0333) nhưng phải ghi rõ: EJ 0.9247 là **con số tự nhận** của họ, chưa từng verify; và với §7.5, hướng "Top-3 thắng bằng EDGE" vẫn là suy luận hợp lý chứ không phải phép đo.

### 7.7. Vụn (cập nhật trạng thái, không đổi kết luận)

- reyhanksatria public là **0.946** (lượt 1 chỗ ghi 0.946 chỗ 0.947 — thống nhất 0.946 theo score-axis chính họ in trong runner: `0.933→0.934→0.939→0.941→0.946`);
- Guard `_EXPECTED_NUMERIC` của họ hard-code đúng bộ 9.0/0.25/… — **cùng pattern guard B-1 của mình** (giúpxfc thêm bằng chứng guard pattern là idioms của family, phải vá khi đổi gate);
- `gap_close_effective_max_gap = 1` trong run_stats của họ dù env MAX_GAP=2 — gap2 ON ở env nhưng thực thi chỉ gap1 (không vặn gì thêm);
- Runtime predict 9.9 phút (2 GPU) + ~3.6h tổng (ILP + install); mình 1 GPU ~2.2h production — không đổi kế hoạch.

### 7.8. Đánh giá tổng 3 delta của alfonso (sau lượt 2 — xếp theo chi phí/gain cho mình)

| # | Delta | Chi phí port | Ưu tiên | Ghi chú |
|---|---|---|---|---|
| 1 | **Cell 2 linearize + cytokinesis rescue** | ~200 dòng CPU, có sẵn code | **#1 (đã lên kế hoạch §5.4-bis)** — volume purge của mình 186 cạnh (GẤP ĐÔI họ) | A/B bằng LB; gate rescue giữ nguyên làm baseline (đã chứng minh trên hidden của họ) |
| 2 | **V1057 reconcile** | ~110 dòng CPU + pool raw edge_prob (có sẵn trong pipeline mình) | **#2 MỚI — thêm vào §5.4-bis như biến thể B** | ⚠️ interplay HOCT (chạy trước veto hoặc loại cạnh đã veto); gain không đo được offline |
| 3 | Detector fine-tune V1327-W3 | train 256 bước + dataset riêng | Bỏ mùa này (giữ nguyên kết luận lượt 1) | rủi ro + còn ~10 ngày |

Kết luận lượt 2: **lượt 1 không bỏ sót gì về hướng chiến lược (census + hidden 2–3 GT + purge-trước-mở-gate), nhưng bỏ sót (a) V1057 reconcile là port candidate, (b) fork count thật của mình = 188 (không phải ~90) → kỳ vọng gain purge cao hơn nhưng cũng rủi ro đốt TP reparent nhiều hơn, (c) 3 sai số chi tiết stack (gap2/bonus/ILP div), (d) cave fork ≠ divFP làm mọi phép phân rã điểm 0.947/0.9605 thành suy đoán.**

---

## 8. Điểm nối tiếp — lượt 3 (19/9 ~05:30)

Diff CSV↔CSV trực tiếp giữa output v10 của mình và 2 submission của alfonso trên cùng hidden test (match node 1-1 bán kính 2 voxel, join guard jsonl, diff run_stats): node overlap 87,1% — gap node tập trung ở 44b6_0b24845f (76,8% match; 1.856 node = ~820 do blend mình under-detect 36 frame + ~683 do association keep-rate); primary_candidates GIỐNG HỆT nhau từng frame (adapted detector của họ không phải nguồn node thừa — họ fallback 98/100 frame về primary gốc); cạnh trên node chung đồng ý 99% → V1057 reconcile downgrade. Chi tiết đầy đủ: `kaggle/ver-11-planning/V11-RESEARCH.md` §2.3-ter + Phụ lục D (biến thể D "v10-primary0b24" mới).
