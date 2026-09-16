# TÀI LIỆU TRIỂN KHAI — CELL 5: PATCH SUY LUẬN + CHẠY DỰ ĐOÁN SONG SONG

**Nguồn nghiên cứu**: [`kaggle.com/code/pawanmali/biohub-942proxy-fork-v1`](https://www.kaggle.com/code/pawanmali/biohub-942proxy-fork-v1)
· Public score **0.945** · Runtime **36m34s trên GPU T4 ×2** · Internet TẮT (offline)
· Tác giả: PAWAN RAMA MALI (publich 9h trước lúc nghiên cứu, 23 views, 3 votes)
· Ngày nghiên cứu: 14/09/2026 (Task 20) · **Cập nhật bản nâng cấp ver 5.1: 15/09/2026 (Task 21)**

> **Trạng thái**: §1–§8 mô tả BẢN NỀN nguyên văn (đã rà soát + sửa 3 sai sót — xem
> §0.1); §9 mô tả **BẢN NÂNG CẤP cell5code.py (ver 5.1)** đang là file dùng chính.

---

## 0. Tóm tắt một đoạn

Cell 5 là **trái tim kỹ thuật** của notebook 0.945: nó *không chứa model* mà chứa **6 bản vá
(string-patch) cấy vào script dự đoán gốc** của repo `biohub_tracking` trước khi chạy, biến
một pipeline UNet-đơn-giản thành tổ hợp: **TTA 8 hướng + dual-seed ensemble + retention
guard + bidirectional harmonic fusion + feature-TTA (primary & secondary)**, rồi **chia 2
GPU chạy song song** và ghép kết quả. Toàn bộ sửa đổi được **kiểm chứng cú pháp bằng
`compile()` và fail-fast** — nếu anchor không khớp thì dừng ngay chứ không chạy im lặng
sai.

### 0.1 Rà soát lần 2 (Task 21) — 3 sai sót đã sửa trong tài liệu này

1. **§3 "cơ chế vá chung" mô tả SAI cho patch 1**: patch 1 KHÔNG dùng `count==1` +
   `RuntimeError` + `compile()` — nó dùng `if _old in _s:` rồi **in warning**
   (`TTA WARNING: block not found - using default 4-way`), `_s.replace(_old, _new)`
   **không giới hạn số match**, và **không compile** trước khi ghi. Fail-fast chỉ xảy ra
   gián tiếp ở patch 2 (anchor #2 của dual-seed bám đúng văn bản sau patch 1) — điểm
   yếu này đã được bản nâng cấp §9 vá bằng hai pha.
2. **§5 bảng env ghi sai nơi đặt 4 biến**: `BIOHUB_EDGE_FEATURE_TTA`,
   `BIOHUB_SECONDARY_EDGE_FEATURE_TTA`, `BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT`
   được đặt **trong chính cell 5** (không phải S1/S4); `BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION`
   bị cell 5 **ghi đè cứng** 0.90 dù S1 đã đặt — nghĩa là sửa trong S1 KHÔNG có tác dụng
   (bẫy tune, đã đối chứng bằng test T8). Bảng §5 đã sửa + bổ sung
   `BIOHUB_DUAL_SEED_EDGE_THRESHOLD`.
3. **§6 cải tiến #2 gọi sai tên núm**: núm thật là `BIOHUB_VALIDATOR_N_PER_TYPE`
   (mặc định "2" mỗi loại × 2 loại có/không phân bào ≈ 4 video) — không phải
   "VALIDATOR_N". Muốn ~8 video thì đặt `BIOHUB_VALIDATOR_N_PER_TYPE=4` ở S1.

Ngoài ra đã xác minh thêm (không sai nhưng đáng ghi): bản sao trong repo khớp notebook
**gốc từng byte** (49.800 bytes, đã diff); 29 cell = **12 code + 17 markdown**; S2 guard
đúng **9 số + 2 text**; `start_time` có được dùng ở cuối cell (in số phút); lệnh chạy
trích trong §4.7 khớp giá trị hiệu dụng (S1 đặt appearance=0.0, disappearance=2,
division=1.2; S3 mặc định edge=-1.0, batch=4, use_ilp=1).

---

## 1. Notebook gốc là gì — có chứa "bài thi mẫu" không?

### Câu trả lời: **CÓ** — theo cả hai nghĩa

**(a) Chứa giải pháp nền đầy đủ để copy (đây là điều quan trọng nhất).**
Markdown cell 6 của notebook ghi rõ: *"Детально разобранная копия одной из лучших
публичных работ этого соревнования"* — **bản sao mổ xẻ chi tiết của một trong những giải
pháp public tốt nhất của competition**. Cả chuỗi 10 section code (S1→S10) là pipeline hoàn
chỉnh, chạy được end-to-end, đã đạt 0.945 trên LB. Ta đã sao lưu:

| File trong repo chúng ta | Nội dung |
|---|---|
| `kaggle/ver-5/original-biohub-942proxy-fork-v1.ipynb` | Notebook gốc **nguyên vẹn** (29 cell, 462KB) |
| `kaggle/ver-5/cell5-foundation-verbatim.py` | **Section 5 nguyên văn = nền** (không chỉnh sửa — đã diff khớp từng byte) |
| `kaggle/ver-5/cell5code.py` | **BẢN NÂNG CẤP ver 5.1** — dùng chính (xem §9) |
| `kaggle/ver-5/make-ver5-upgrade.py` | Tool lắp ráp ver 5.1 (trích payload byte-đúng bằng AST) |
| `kaggle/ver-5/test-ver5-cell5.py` | Bộ kiểm chứng 57/57 (xem §9.3) |
| `kaggle/ver-5/original-analysis-notes.md` | 8 cell markdown gốc (lịch sử thí nghiệm v10→v30) |

**(b) KHÔNG chứa notebook starter/getting-started gốc của competition** (kiểu 4-cell đọc
Zarr → watershed → nộp CSV như ver-1 của ta). Nền của nó là **repo giải pháp ML riêng**
(`src/biohub_tracking/`, script `predict_unet_transformer.py`) đóng gói trong dataset
"Biohub Tracking Support Pack".

### Chuỗi nguồn gốc (provenance) — notebook ghi lại rất minh bạch

```
0.923  base "Dual-Seed + Harmonic Bidirectional Fusion"  ← được copy mổ xẻ
        │  (TemporalUNet3D + Node Transformer + ILP + DeepCenter + dual-seed)
        ▼  v28: mở rộng hình học phân bào (SAFE_DIV 7→9µm, SISTER 12→14µm,
        │        SYMMETRY_TAU 0.6, DeepCenter best.pt epoch 2)      → LB 0.942
        ▼  v29: EDGE_FEATURE_TTA + DC_SAFE_DIV 0.26 +
        │        MOTION_RELINK_TIGHT_UM 6.0→5.5                     → LB 0.944–0.946
        ▼  v30 (notebook này): TTA-fusion link logits (feature-map),
           Secondary Edge TTA w=0.75, DeepCenter TTA                → LB 0.945
```

Các public work mà nó học: `rishabhr0y/biohub-div45-stack` (0.938) ·
`kunaldesale2408/biohub-cell-tracking` (0.940) · `analyticaobscura/biohub-lb-942` (0.942) ·
`rogerrogerroger3r/biohub-run79` (0.944) · `redoctopusk/biohub-942tta` (0.946) ·
`sjlee101/biohub-lf-dctta`.

**Hệ quả chiến lược cho chúng ta**: con đường nhanh nhất tới điểm cao không phải là sửa
ver-4 (heuristic, 0.198) mà là **fork nguyên notebook này** (Copy & Edit trên Kaggle → Save
& Run All ~36 phút → Submit). Cell 5 trong tài liệu này = section 5 của notebook đó.

---

## 2. Vị trí cell 5 trong pipeline 10 section

| # | Section (code cell) | Việc | Phụ thuộc |
|---|---|---|---|
| 1 | S1 — Cấu hình toàn cục | Đặt **~45 biến môi trường `BIOHUB_*`** (preset `v29_edge_tta_tight55`) | — |
| 2 | S2 — Configuration Guard | Assert 9 số + 2 text env đúng kỳ vọng, chống drift | S1 |
| 3 | S3 — Imports + đường dẫn | `REPO_DIR=/kaggle/working/tracking_repo`, `TEST_DIR`, `METHOD='unet_transformer'`, đọc mọi env thành hằng Python | S1 |
| 4 | S4 — Cài deps + tìm model | Tìm support pack theo manifest, **verify SHA256** cả 3 model + 12 file repo; cài wheel offline; materialize repo + weights; đặt env secondary | S3 |
| **5** | **S5 — Patch suy luận + chạy dự đoán** | **6 bản vá vào `scripts/predict_unet_transformer.py`** + chạy song song 2 GPU | **S1·S3·S4** |
| 6 | S6 — Hậu xử lý + submission.csv | Đọc .geff dự đoán → motion relink / gap close / safe divisions (có veto DeepCenter) / lọc track ngắn / linefit → CSV | S5 |
| 7 | S7 — Audit | Kiểm tra submission độc lập + báo cáo frame-retention guard | S6 |
| 8 | S8 — Validator (dự đoán) | Chọn N video train giữ lại, chạy dự đoán trên chúng | S5 |
| 9 | S9 — Validator (metric) | Tính metric chính thức: matching hai phía ≤7µm, adjEJ + divJ | S8 |
| 10 | S10 — Manifest | In trạng thái thực tế mọi cơ chế đã bật | tất cả |

Cell 5 **tiêu thụ** từ các cell trước: `REPO_DIR`, `TEST_DIR`, `METHOD`,
`WEIGHTS_RELATIVE`, `UNET_BATCH_SIZE`, `DET_THRESHOLD`, `ILP_*`,
`SLICE`, `WORKING_DIR` (S3); mọi env `BIOHUB_SECONDARY_*` đã đặt sẵn trong S4;
repo đã materialize + weights primary/secondary/DeepCenter đã verify (S4).

---

## 3. Kiến trúc bên trong cell 5

```
cell 5 (49.8KB, 475 dòng)
├── (0) Fail-fast: torch.cuda.is_available() else raise
├── (1) PATCH TTA 8 hướng        — vá khối if cfg.det_tta (4 hướng → 8 hướng D4)
├── (2) PATCH dual-seed            — 6 phép thay đổi chuỗi: thêm tham số
│       secondary_model/edge/detection/link_mode/temperature/low_margin
│       vào hàm predict + logic trộn detection & edge logits + load model phụ
├── (3) PATCH retention guard      — nếu blend làm mất >10% ứng viên → dùng det gốc
├── (4) PATCH bidirectional        — fusion hài hòa xác suất xuôi/ngược + manifest tọa độ
├── (5) PATCH EDGE_FEATURE_TTA     — trung bình feature map 8 view (model chính)
├── (6) PATCH SECONDARY_EDGE_TTA   — trung bình feature 8 view (model phụ, w=0.75)
└── (8) CHẠY DỰ ĐOÁN
    ├── list test stems, ghi splits JSON
    ├── predict_cmd = python scripts/predict_unet_transformer.py
    │       --data-dir TEST --weights ... --det-threshold 0.965
    │       --ilp-edge-weight -1 --ilp-appearance 0 --ilp-disappearance 2
    │       --ilp-division 1.2 --use-ilp
    ├── nếu ≥2 GPU: 2 subprocess, mỗi cái CUDA_VISIBLE_DEVICES=i,
    │       BIOHUB_GPU_SHARD=i/2, --method ..._gpu{i} --slice i::2
    │       → chờ cả hai (fail thì terminate hết) → _merge_prediction_shards
    │       (verify phủ đủ + không trùng + staging + rename)
    └── nếu 1 GPU: single-process
```

**Cơ chế vá chung** (lặp lại 6 lần, rất đáng học — nhưng patch 1 là NGOẠI LỆ, xem §0.1):
1. `_s = _ps.read_text()` — đọc script gốc.
2. `_count = _s.count(_old)` — **bắt buộc đúng 1 match**, sai thì `RuntimeError` *(patch 2–6;
   patch 1 chỉ `if _old in _s` + warning)*.
3. `_s.replace(_old, _new, 1)` — thay đúng 1 chỗ *(patch 1 không truyền count — thay mọi
   match)*.
4. `compile(_s, ...)` — kiểm tra cú pháp Python **trước khi ghi** *(patch 2–6; patch 1 bỏ
   qua bước này)*.
5. `_ps.write_text(_s)` — ghi đè *(patch 2–6 ghi sau khi compile; các patch ghi ĐĨA TUẦN
   TỰ — hỏng giữa chừng để lại file vá dở, đã đối chứng bằng test T5)*.
6. (patch 5,6) đọc lại file để xác nhận chuỗi đánh dấu (`EDGE_TTA_ACTIVE`) đã tồn tại —
   chống vá không ăn.

Toàn bộ patch đều **idempotent-by-fail**: chạy lại notebook lần 2 thì repo được materialize
lại từ support pack (S4 xoá rồi chép) → patch tìm đúng anchor bản gốc lần nữa.

---

## 4. Chi tiết từng patch

### 4.1 Patch 1 — Detection TTA 8 hướng (thay 4 hướng)

Bản nền (code gốc trong repo — chính là chuỗi `_old`):
3 phép lật `(-1,), (-2,), (-2,-1)` trên ảnh + identity → **4 view**, chia 4.

Bản vá: đủ **nhóm nhị diện D4 trên mặt phẳng (y,x)** — 8 phép:
identity · 3 lật · `rot90` k=1,3 (dims `(-2,-1)`) · transpose `(-1,-2)` ·
anti-transpose (rot90 rồi transpose). Đếm `_nv` tăng dần rồi chia — không hard-code số 8.
Chú ý **không lật trục z** (bất đối xứng vật lý của ảnh kính hiển vi).

### 4.2 Patch 2 — Dual-seed ensemble "calibrated" (6 phép thay)

* Thêm 6 tham số vào hàm predict: `secondary_model`, `secondary_edge_weight`,
  `secondary_detection_weight`, `secondary_link_mode`, `secondary_mix_temperature`,
  `secondary_low_margin_max`.
* **Detection**: model phụ encode + 8-view TTA riêng; **z-score align** logit phụ về
  logit chính (mean/std, tỉ lệ scale kẹp [0.5, 2.0]) rồi trộn
  `(1−w)·primary + w·secondary_aligned`.
* **Edge**: lấy feature từ `secondary_unet_out` theo tọa độ node, gọi
  `predict_edges` của model phụ, rồi trộn theo 1 trong 4 `link_mode`:
  `raw` · `calibrated` (z-align rồi trộn) · `adaptive` (trọng số theo margin top-2 của
  softmax, cùng-cha thì giữ mức sàn) · `low_margin_consensus` (chỉ tin model phụ ở vùng
  model chính **bất định** — margin < ngưỡng — và hai model phải cùng chọn cha).
  Bản 0.945 chạy `low_margin_consensus` với `LOW_MARGIN_MAX=0.35` (đặt ở S4).
* `mix_temperature` ≠ 1 thì nén/mở rộng logits quanh tâm.
* Load model phụ từ env `BIOHUB_SECONDARY_WEIGHTS`, validate khoảng giá trị mọi tham số,
  kiểm **cùng window_size + downsample** với model chính.
* Env từ S4: `SECONDARY_EDGE_WEIGHT=0.20` (= "EDGE_WEIGHT" trong bảng phân tích) ·
  `SECONDARY_DETECTION_WEIGHT=0.80` (= "SEC_DET") · mode `low_margin_consensus`.

### 4.3 Patch 3 — Retention guard (an toàn khi trộn detection)

Với mỗi khung: đếm số ứng viên từ logit gốc vs logit trộn (cùng hàm
`_detect_cells_pooled`, ngưỡng `cfg.det_threshold`). Nếu
`blended/primary < 0.90` (env `BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION`) → **dùng
logit gốc cho khung đó**, ghi JSONL `retention_guard_{shard}.jsonl` vào
`/kaggle/working` (S7 đọc lại để audit). Ý nghĩa: model phụ không bao giờ được làm
"mất" >10% tế bào — chống recall tụt khi hai seed không đồng thuận.

### 4.4 Patch 4 — Bidirectional harmonic fusion (trọng số 0.15, có guard)

Cạnh A→B tính logits **cả chiều ngược B→A** (transpose), z-align về chiều xuôi, rồi lấy
**trung bình điều hòa xác suất**:
`p = 1 / ((1−w)/p_fwd + w/p_rev)`, chuẩn hóa lại, quay về logits, tái-align scale.
Guard ở đầu patch **assert đúng `BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT == 0.15`** (khác là
raise). Kèm hook **coordinate manifest**: khi `BIOHUB_DIAGNOSTIC_ARM` bật, ghi SHA256
của mảng tọa độ node sau detection (trước ILP) — để đối chiếu 2 nhánh A/B không lệch
nhau.

### 4.5 Patch 5 — EDGE_FEATURE_TTA (model chính)

Trước đây 8 view TTA chỉ lấy `det_logits`, **vứt feature map** (`_` trong
`_, det_flip = model.encode(...)`). Patch giữ lại feature của từng view, cộng dồn,
chia `_nv`, rồi **thay `unet_out`** = feature trung bình → Node Transformer chấm cạnh trên
feature ổn định theo mọi hướng ảnh. Hai guard cứng: sai shape → raise;
`mean|Δ| == 0` (patch vô tác dụng) → raise (chống đọc kết quả null giả).
Bật env `BIOHUB_EDGE_FEATURE_TTA=1`. Đây là phần "+0.014 edge Jaccard trên 1 video"
của v29.

### 4.6 Patch 6 — SECONDARY_EDGE_TTA (model phụ, w=0.75)

Như patch 5 nhưng cho model phụ: `secondary_unet_out ←
(1−0.75)·single + 0.75·mean_8view` (env `BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT=0.75`),
kèm 2 guard shape/no-op tương tự.

### 4.7 Chạy dự đoán song song + ghép

* Ghi `kaggle_test_splits_50ep.json` (danh sách test stems) trong REPO_DIR.
* Lệnh: `python scripts/predict_unet_transformer.py --data-dir TEST --splits … --split 0
  --weights weights/unet_transformer/split_0/edge_predictor_best.pth
  --unet-batch-size 4 --det-threshold 0.965 --ilp-edge-weight -1
  --ilp-appearance-weight 0 --ilp-disappearance-weight 2 --ilp-division-weight 1.2
  --use-ilp`.
* 2 GPU: chia **round-robin theo index** (`test_stems[i::2]`), mỗi process một
  `CUDA_VISIBLE_DEVICES`, `PYTHONPATH=src`, method riêng `unet_transformer_gpu{i}`
  (thư mục dự đoán riêng). Chờ vòng `poll()`; một shard fail → terminate tất cả → raise.
* Ghép: mỗi shard phải ra **đúng** tập .geff giao cho nó (thiếu/thừa đều raise), không
  trùng nhau, hợp lại đúng toàn bộ test; move qua staging dir rồi rename atomically;
  dọn thư mục shard.

---

## 5. Cấu hình cell 5 tiêu thụ (bảng dưới ghi rõ biến đặt ở đâu — cột cuối)

| Env | Giá trị bản 0.945 | Ý nghĩa | Đặt ở đâu |
|---|---|---|---|
| `BIOHUB_DET_THRESHOLD` | 0.965 | ngưỡng detection | S1 |
| `BIOHUB_SECONDARY_WEIGHTS` | (đường dẫn) | model phụ seed 314159 | S4 |
| `BIOHUB_SECONDARY_EDGE_WEIGHT` | 0.20 | trọng số trộn edge ("EDGE_WEIGHT") | S4 |
| `BIOHUB_SECONDARY_DETECTION_WEIGHT` | 0.80 | trọng số trộn detection ("SEC_DET") | S4 |
| `BIOHUB_SECONDARY_LINK_MODE` | low_margin_consensus | chế độ trộn cạnh | S4 |
| `BIOHUB_SECONDARY_LOW_MARGIN_MAX` | 0.35 | vùng "model chính bất định" | S4 |
| `BIOHUB_SECONDARY_MIX_TEMPERATURE` | 1 | nén/mở rộng logits | S4 |
| `BIOHUB_DUAL_SEED_EDGE_THRESHOLD` | = cfg.threshold | ngưỡng cạnh dual-seed (đặt lại `cfg.threshold`) | S4 |
| `BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT` | 0.15 (guard ép cứng) | trọng số chiều ngược | S1 + guard trong cell 5 |
| `BIOHUB_DUAL_SEED_MIN_CANDIDATE_RETENTION` | 0.90 | sàn giữ ứng viên | S1 **và** cell 5 ghi đè cứng¹ |
| `BIOHUB_EDGE_FEATURE_TTA` | 1 | bật feature-TTA model chính | **cell 5** (cuối patch 5) |
| `BIOHUB_SECONDARY_EDGE_FEATURE_TTA` | 1 | bật feature-TTA model phụ | **cell 5** (cuối patch 6) |
| `BIOHUB_SECONDARY_EDGE_FEATURE_TTA_WEIGHT` | 0.75 | trọng số feature-TTA model phụ | **cell 5** (cuối patch 6) |
| `BIOHUB_DEEPCENTER_*` | xem S1 | veto gap/phân bào (chạy ở S6) | S1/S4 |
| `BIOHUB_MOTION_RELINK_TIGHT_UM` | 5.5 | gate chặt relink (S6) | S1 |
| `BIOHUB_GAP_CLOSE_UM` / `MAX_GAP` | 5.8 / 2 | đóng khoảng đứt (S6) | S1 |
| `BIOHUB_SAFE_DIV_MAX_UM` / `SISTER_MAX` / `SYMMETRY_TAU` | 9.0 / 14.0 / 0.6 | hình học phân bào (S6) | S1 |

¹ **Bẫy tune đã vá ở ver 5.1**: bản nền `os.environ[...] = "0.90"` ghi đè mọi giá trị S1
đặt — sửa trong S1 không có tác dụng (đối chứng test T8). Ver 5.1 đổi thành
`setdefault` cho cả 4 biến in đậm.

**Yêu cầu chạy**: Kaggle GPU (T4×2 nhanh nhất, 1 GPU vẫn chạy single-process) ·
4 Input: competition + `biohub-tracking-support-pack-50ep-v1` + `biohub-deepcenter-unet3d-center-prior-v1`
+ `biohub-temporal-unet3d-seed314159-v1` (cả 3 của user `pilkwang`) · internet tắt.
**Toàn bộ trọng số bị ghim SHA256** (primary `12f688…`, secondary `9bac2f…`, DeepCenter
`804099…` + 12 file repo) — đổi model là raise, không có chuyện chạy nhầm bản.

---

## 6. Điểm cải tiến trực tiếp từ phiên bản sẵn (xếp theo giá trị/khả thi)

| # | Cải tiến | Gốc rễ | Kỳ vọng | Công sức | Rủi ro |
|---|---|---|---|---|---|
| **0** | **BẢN NÂNG CẤP CELL 5 — ver 5.1** (hai pha verify-then-write · re-run an toàn ·
tôn trọng env S1 · preflight manifest · tổng hợp retention guard) — xem §9 | rà soát Task 21: 5 điểm yếu điều phối của bản nền (patch 1 thiếu fail-fast/compile,
ghi dĩa tuần tự, ghi đè env S1, không re-run được, không có báo cáo guard) | giữ nguyên 0.945 + chắc chắn hơn | **đã làm xong** (57/57 test) | đã kiểm chứng đẳng thức payload từng byte |
| **1** | **PPSWEEP — quét tham số hậu xử lý trên graph đã cache** (.geff sau S5; quét `MOTION_RELINK_*`, `SAFE_DIV_*`, `GAP_*`…, mỗi lần ~4–5 phút, chọn theo validator S8–S9) | notebook 0.946 (`redoctopusk/biohub-942tta`) đã làm và thắng (+0.002 proxy); bản fork chủ động **bỏ qua vì sợ 35→80 phút** — trong khi budget 12h của ta dư dả (chạy hết 36 phút!) | +0.002…0.005 | trung bình (thêm 1 section sau S5, tái dùng S6+S8+S9) | proxy↔LB lệch nhau (chính phân tích của họ chứng minh) → chỉ nhận thay đổi khi **cả proxy lẫn LB validator N-lớn đều tăng** |
| **2** | **VALIDATOR_N_PER_TYPE 2 → 4** (≈ 4 → 8 video train giữ lại; núm thật là
`BIOHUB_VALIDATOR_N_PER_TYPE` — S8 đọc, mặc định "2"/loại, S8 tự chọn có/không phân bào) | notebook 0.942 dùng ~8; giảm nhiễu chọn tham số | giảm sai lệch chọn | nhỏ (thêm 1 dòng env ở S1) | tốn thêm ~×2 thời gian validator (khoảng vài phút GPU) |
| **3** | **True link-logit TTA** — hiện chỉ trung bình *feature map* (patch 5/6); markdown v30 tuyên bố "trung bình raw link logits theo 8 view" nhưng code làm ở mức feature. Thử: gọi `predict_edges` cho từng view rồi trung bình logits | v30 tự mô tả điều mà code chưa làm đúng nghĩa đen | +0.001…0.003 (đo mới) | trung bình | tăng thời gian suy luận cạnh ×8 — cân nhắc chỉ áp cho cặp cạnh "gần gate" |
| **4** | **Division model riêng** — divJ kẹt 0.23 (chỉ 1–4 TP / 3 GT trên validator); missed GT 35–42 node | chính phần "Куда двигаться дальше" của họ; 15% trọng số metric đang bỏ trống | lớn nhất về đỉnh nhưng khó nhất | lớn | cần dữ liệu huấn luyện phân bào (có sẵn trong train .geff) |
| **5** | **fp16 + `inference_mode` cho các pass TTA** (8 encode/window) | T4 có Tensor Core; chưa thấy trong code | giảm ~30–40% thời gian cell 5 | nhỏ | cần đối chiếu output fp32 vs fp16 trước khi bật |
| **6** | **Bền hóa chuỗi patch** — thay exact-string anchor bằng AST/regex hoặc vendored script có SHA riêng | chuỗi 6 patch phụ thuộc byte-level vào 12 file repo ghim SHA; support pack đổi bản là nguyên notebook tê liệt (fail đúng nhưng khó vá nhanh) | bảo trì | trung bình | mất khả năng "chứng minh nền = artifact public nguyên vẹn" — cân nhắc giữ SHA riêng cho bản đã vá |
| **7** | **Model thứ 3 vào ensemble** (seed khác nữa) | dual-seed chỉ 2; runtime 36 phút, budget 12h | +? (thu hẹp phương sai) | trung bình | mỗi model +15 phút; lợi ích giảm dần |
| **8** | **Báo cáo retention guard tổng hợp** — S7 đã đọc JSONL; thêm thống kê tần suất khung dùng det-gốc theo dataset để phát hiện vùng hai seed bất đồng | tiện chẩn đoán #3/#4 | chẩn đoán | nhỏ | — |

**Cảnh báo từ chính dữ liệu của họ** (bảng proxy vs LB): có 3/8 phiên bản proxy tăng mà LB
giảm (v4, v7) và ngược lại (v5, v8) → **không bao giờ tune chỉ theo proxy**; mọi thay đổi
phải qua validator rộng (#2) và ưu tiên thay đổi có giải thích sinh học (hình học phân bào
chính là bài học lớn nhất của họ: "Sinh học quan trọng hơn tham số").

---

## 7. Kết nối với repo của chúng ta (ver-1…ver-4) — hội tụ độc lập

Phân tích của họ **khẳng định các con số chúng ta tự suy ra từ GT** ở ver-3/ver-4:

| Họ (0.945) | Ta (ver-3/ver-4) | Ghi chú |
|---|---|---|
| `SAFE_DIV_SISTER_MAX 14.0µm` (GT: median 10.4, p90 13.0, max 13.7) | `DIV_SIBLING_GATE_UM 14.5` (p99 13,9) | hội tụ gần như trùng |
| "parent mid-track" (C1) | C1 của ta — mẹ phải có cạnh vào | trùng |
| `DIVERGE_UM 2.25` (2 con tiếp tục tách ở t+2) | "xác nhận động học" của ta | cùng ý |
| `SYMMETRY_TAU 0.6` (đối xứng khối lượng 2 con) | "mass stability — mẹ ≤1.7× baseline" của ta | cùng ý, góc nhìn khác |
| GAP_CLOSE 5.8µm / max_gap 2 + GAP2 recovery | STITCHING 10+2(gap−1)µm / gap ≤5 + nội suy | họ bảo thủ hơn (cap tỉ lệ node thêm vào) |
| `MOTION_RELINK_TIGHT 5.5 / RELAXED 10` | GATE_MIN 7 / GATE_MAX 14 | cùng cấu trúc 2 nấc |

→ Kiến thức ver-4 của ta có giá trị **chỉnh sửa S6 (hậu xử lý)** nếu muốn thử nghiệm —
nhưng với khoảng cách 0.198 vs 0.945, nguyên tắc là: **fork nguyên vẹn trước, tinh chỉnh
sau**, mọi tinh chỉnh phải qua validator S8–S9.

## 8. Kế hoạch triển khai đề xuất (ver-5)

1. **Ngay**: Kaggle → Copy & Edit notebook gốc → Add 4 Input (competition + 3 dataset của
   `pilkwang`) → bật GPU T4×2 → **thay cell "## 5." bằng `kaggle/ver-5/cell5code.py`
   (ver 5.1)** → Save & Run All (~36 phút) → Submit.
   Kỳ vọng LB ≈ **0.94x** (vs ver-1 = 0.198). Muốn chạy nền nguyên văn 100% thì dán
   `cell5-foundation-verbatim.py` thay thế — hai bản cho kết quả vá giống hệt nhau
   (đã chứng minh bằng test T2).
2. **Sau đó (không tốn quota)**: import bản copy → thêm `BIOHUB_VALIDATOR_N_PER_TYPE=4`
   ở S1 (cải tiến #2) → thiết kế section PPSWEEP (cải tiến #1) trên graph đã cache sau
   S5, chọn theo validator S8–S9.
3. **Về sau**: cải tiến #3 (true logit-TTA) và #4 (division model) — chỉ khi 1–2 đã cạn.

---

## 9. BẢN NÂNG CẤP CELL 5 — VER 5.1 (Task 21)

### 9.1 Triết lý: fork nguyên vẹn trước, chỉ chắc chắn hoá phần điều phối

Khoảng cách 0.198 → 0.945 nằm trong **model + payload vá** — vì vậy ver 5.1 **KHÔNG đổi
chữ nào trong payload của 6 patch** (đảm bảo bằng cơ chế: `make-ver5-upgrade.py` trích
các chuỗi old/new khỏi `cell5-foundation-verbatim.py` bằng `ast.get_source_segment` —
tự động, không gõ tay) và **KHÔNG đổi section 8** (chạy dự đoán, trích nguyên văn từ ký
tự thứ 43.133 của file nền). Mọi thay đổi nằm ở **vòng điều phối quanh payload**:

| # | Nâng cấp | Vấn đề của bản nền (đã đối chứng bằng test) | Cách làm ver 5.1 |
|---|---|---|---|
| 1 | **Hai pha verify-then-write** | patch 2–6 ghi đĩa TUẦN TỰ; hỏng anchor ở giữa (ví dụ patch 4) để lại **file vá dở** (test T5: file bị sửa 3/6 patch) | xác minh từng anchor (đúng 1 match) + áp trong **bộ nhớ** → `compile()` một lần → **ghi một lần duy nhất** → đọc lại xác nhận marker; anchor hỏng → dừng **trước khi ghi**, file nguyên vẹn |
| 2 | **Patch 1 fail-fast hoá** | patch 1 chỉ `if _old in _s` + in `TTA WARNING`, replace mọi match, không compile (§0.1) | đưa vào cùng chuỗi hai pha — đếm `count==1` như 5 patch kia |
| 3 | **Re-run an toàn** | chạy lại cell 5 (không chạy lại S4) → patch 2 raise "expected one match, found 0" — phải chạy lại cả S4 | nhận diện **đã vá đủ** qua 6 marker (mỗi marker chỉ tồn tại sau khi patch tương ứng áp) → in "Patch phase skipped" → chạy thẳng dự đoán |
| 4 | **Tôn trọng env S1/S4** | 4 env bị ghi đè cứng trong cell 5 — sửa S1 không tác dụng (test T8: preset 0.85 bị ghi đè thành 0.90) | `os.environ.setdefault(...)` — S1 đặt gì dùng nấy, không đặt thì dùng đúng giá trị 0.945 → **tune giờ chỉ cần sửa S1** |
| 5 | **Preflight manifest** | không có chỗ nào in cấu hình hiệu dụng trước khi chạy → khó phát hiện drift | in 1 khối: patch target, method/slice, det threshold, ILP weights, secondary (w/mode/low_margin), retention floor, bidirectional, feature-TTA, số GPU |
| 6 | **Tổng hợp retention guard** (cải tiến #8 của §6) | JSONL có sẵn nhưng phải đợi S7 mới đọc | đọc `retention_guard_*.jsonl` ngay sau khi chạy: tổng khung guarded/tổng khung, phân bố theo dataset, retention xấu nhất ở đâu |
| 7 | **Throughput** | chỉ in số phút | thêm videos/h + số video |

### 9.2 Cấu trúc file `cell5code.py` (ver 5.1)

```
(0)  Fail-fast GPU + preflight manifest + setdefault 4 env + dọn retention log cũ
(1-6) SÁU BẢN VÁ — payload NGUYÊN VĂN từng byte của bản nền:
       _old/_new (TTA 8 hướng) · _ensemble_replacements (6 phép dual-seed) ·
       _guard_old/_new (retention) · _bi_old/_new + _coordinate_manifest_old/new
       (bidirectional) · _et_old/_new (edge TTA) · _secondary_tta_old/_new
     → _patches = 12 phép (1+6+1+2+1+1) theo đúng thứ tự bản nền áp
     → đã vá đủ (6 marker) ? bỏ qua : [verify từng anchor → áp in-memory →
       compile → ghi 1 lần → xác nhận marker sau ghi]
(8)  Run inference — NGUYÊN VĂN bản nền (list_test_stems → splits JSON →
     predict_cmd → 2 GPU round-robin + merge có verify / 1 GPU single-process)
(9)  Throughput + tổng hợp retention guard
```

### 9.3 Kiểm chứng — `test-ver5-cell5.py` (57/57 ĐẠT, không cần GPU)

Dựng **mock `predict_unet_transformer.py` nguyên trạng** từ chính các anchor trích
ra khỏi file nền (`ast.literal_eval`), tiêm **torch giả** + **subprocess giả** (mô phỏng
worker sinh .geff theo `--slice`/`--method` + ghi retention JSONL):

| Test | Chứng minh gì |
|---|---|
| T1 | cú pháp mọi file + mock compile |
| T2 | **ĐẲNG THỨC PAYLOAD**: vá mock bằng bản nền và bằng ver 5.1 (2 thư mục riêng) → file kết quả **giống hệt từng byte** — ver 5.1 không đổi hành vi vá của pipeline 0.945 |
| T3 | script sau vá compile được + đủ 6 marker |
| T4 | chạy khối vá lần 2 → "Patch phase skipped", file không đổi |
| T5 | hỏng anchor cuối chuỗi → ver 5.1 **dừng trước khi ghi** (file nguyên vẹn, thông điệp chỉ đúng patch `4/2 coordinate-manifest`); **đối chứng bản nền: file bị ghi dở 3/6 patch** — điểm yếu đã chẩn đoán tái hiện đúng |
| T6 | luồng đầy đủ 1 GPU: .geff đủ 5 video, splits JSON đúng, PYTHONPATH=src, nhánh "no logs" của tổng hợp |
| T7 | luồng đầy đủ 2 GPU: env shard đúng (CUDA_VISIBLE_DEVICES 0/1, GPU_SHARD 0/2·1/2), `--slice 0::2`/`1::2`, method riêng `_gpu0/_gpu1`, merge đủ + dọn thư mục shard, **tổng hợp retention: 1/4 guarded, worst 0.830 tại video_a frame 12, video_a: 1/2** |
| T8 | env S1 đã đặt thì **giữ nguyên** (0.85 không bị đè); chưa đặt thì mặc định 0.90/1/1/0.75; **đối chứng bản nền: preset bị ghi đè** (bẫy tune tái hiện đúng) |
| T9 | không GPU → RuntimeError |
| T10 | thiếu script → FileNotFoundError dẫn về section 4 |

### 9.4 Giới hạn & bước kế tiếp

- Mock chỉ chứng minh **chuỗi vá tự nhất quán** (anchor → anchor ăn khớp, output
  compile); tính tương thích với script THẬT trong support pack là thuộc về bản nền
  (đã chạy 0.945 trên LB) + đẳng thức payload từng byte (T2).
- **PPSWEEP (cải tiến #1)** cần môi trường Kaggle (graph .geff thật + S6 + validator)
  — thiết kế nhưng chưa triển khai ở ver 5.1 vì không kiểm chứng được cục bộ; làm
  theo kế hoạch §8.2 sau khi bản fork gốc đã chạy được.
- fp16 TTA (#5) và true logit-TTA (#3) vẫn là việc của phiên bản sau — cần đối chiếu
  output trên GPU thật trước khi bật (nguyên tắc: không ships thứ chưa kiểm chứng).

## Phụ lục — file đã lưu trong repo

* `kaggle/ver-5/original-biohub-942proxy-fork-v1.ipynb` — notebook gốc nguyên vẹn (nền).
* `kaggle/ver-5/cell5-foundation-verbatim.py` — **section 5 nguyên văn, KHÔNG sửa** (đã
  diff khớp notebook gốc từng byte — 49.800 bytes).
* `kaggle/ver-5/cell5code.py` — **ver 5.1, bản nâng cấp — dùng chính** (§9).
* `kaggle/ver-5/make-ver5-upgrade.py` — tool lắp ráp ver 5.1 (trích payload AST).
* `kaggle/ver-5/test-ver5-cell5.py` — bộ kiểm chứng 57/57 (§9.3).
* `kaggle/ver-5/original-analysis-notes.md` — 8 cell markdown gốc (lịch sử v10→v30).
* Tài liệu này: `kaggle/ver-5/CELL5-TRIEN-KHAI.md`.
