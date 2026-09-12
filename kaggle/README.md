# Registry phiên bản bài nộp — Kaggle "Biohub - Cell Tracking During Development"

Mỗi lần thay đổi thuật toán nộp bài = **một phiên bản (ver)**. Code của từng cell
được lưu tại `ver-N/cell1code.py` … `cell4code.py` — dán đè cell tương ứng của
notebook Kaggle gốc rồi **Save & Run All → Submit**.

> Quy ước: cell1code = Cell 1 (imports) · cell2code = Cell 2 (siêu tham số) ·
> cell3code = Cell 3 (pipeline chính) · cell4code = Cell 4 (xuất submission.csv).
> Cell 1 và Cell 4 gần như bất biến; mọi thay đổi thuật toán nằm ở Cell 2 + Cell 3.

**Bảng điểm** (Kaggle public LB):

| ver | tên | điểm Kaggle | ngày |
|---|---|---:|---|
| 0 | Baseline (getting-started) | — (chưa submit) | — |
| 1 | Stage 0+2 | **0.198** | 13/09/2026 |
| 2 | Chống gộp blob + phân bào xác nhận | soạn thảo ✓ | — |
| 3 | Phân bào theo profile độ sáng (từ discussion #740573) | soạn thảo ✓ | — |

Top 1 (Sergio Alvarez) = **0.97** · top 10 ≈ 0.957 — khoảng cách còn rất lớn.

**Nguyên tắc rút ra từ điểm 0.198 + đọc kỹ metric chính thức** (repo
`royerlab/kaggle-cell-tracking-competition`):
1. **Node recall là đòn bẩy lớn nhất**: TP ~ r² (cả 2 đầu cạnh đều phải khớp ≤ 7 µm),
   còn phạt node thừa rất nhẹ (`adjEJ = EJ·(1 − 0.1·(N_pred−N_true)/N_true)`).
2. **Cạnh FP chỉ bị tính khi bám vào node GT** (nguồn khớp GT-có-cạnh-ra hoặc
   đích khớp GT-có-cạnh-vào) — cạnh giữa tế bào chưa được chú thích bị bỏ qua.
3. **Cạnh nhảy t→t+k bị metric bỏ hẳn** (không TP) → nội suy node giữa là bắt buộc.
4. **Fork (≥2 cạnh ra) = phân bào** theo metric; fork giả là division FP →
   mỗi fork phải được xác nhận bằng động học.

## Insight từ discussion #740573 (Lê Quang Cảnh · hạng 40 + hengck23)

Đo trực tiếp trên **73 file nhãn train** (36 phân bào có nhãn, 25.661 cạnh
continuation, 72 cạnh phân bào, 572 track) — không phải dự đoán:

### a) Khoảng cách mẹ→con KHÔNG phải tín hiệu phân bào (bài học lớn nhất)

| Loại bước (µm/khung) | n | median | IQR | p99 | max |
|---|---:|---:|---|---:|---:|
| continuation | 25.661 | 1,72 | 0,91–2,19 | 6,91 | 18,7 |
| mẹ→con (division step) | 72 | 4,57 | 3,30–6,21 | 10,6 | 12,3 |
| **2 con gái (sister sep.)** | 36 | **8,85** | 7,20–10,24 | 13,9 | **14,65** |

- IQR của bước phân bào nằm **gần trọn trong vùng bước thường** → gate khoảng
  cách đủ rộng để bắt median phân bào (≥5µm) thì cũng thu 722 bước thường,
  **24:1 base rate** (tại 10µm: 38:1). *"Thất bại là base rate, không phải
  vùng chồng lấn chỉnh gate được."*
- **Sister separation là tín hiệu hình học mạnh nhất** (8,85 vs 1,72µm) nhưng
  là thuộc tính của CẶP — chỉ dùng được sau khi đề xuất cặp.
- **Bẫy đo trên node dự đoán**: cùng phân bào đó, median bước trên nhãn 6,36µm
  nhưng trên node dự đoán 8,47µm (max 13,65) — sai số định vị detector cộng
  dồn qua 2 đầu cạnh. **Tune gate phải trên nhãn GT, không tune trên output
  chính mình.**

### b) Tín hiệu APPEARANCE (ngoại hình) — mẹ sáng lên trước khi chia

- Đỉnh cường độ (peak intensity) của mẹ tại khung tách phân biệt khỏi tế bào
  thường ở **AUC 0,73** (con ở t+1..t+3: 0,68–0,70); local contrast 0,55–0,69.
- Độ "mỏng/dài" (elongation) KHÔNG phân biệt (AUC ≈ 0,34–0,58 = random) —
  có thể vì nhìn trễ 1–2 khung (hengck23: **đường sáng mảnh ở anaphase xuất
  hiện VÀI KHUNG TRƯỚC** khung tách là manh mối rất tốt).
- hengck23: nhiều phân bào **chưa được gắn nhãn** trong data Kaggle — "hiếm
  khi chỉ 1 tế bào phân bào"; nhưng trên 36 phân bào có nhãn, các mốc tách
  **không cluster** (spread median 32 khung/phim).

### c) Cấu trúc nhãn GT (ảnh hưởng cách đọc metric)

- **Mọi cạnh GT nối đúng 1 khung** (25.661/25.661 — không có skip edge) →
  nội suy node ở khung mất (ver 2) là đúng hướng.
- Nhãn theo **segment, không theo lineage trọn đời**: 351/572 track bắt đầu
  sau frame 0, 391 kết thúc trước frame cuối, median 35 khung → 36 phân bào
  chỉ là **tập con được gắn nhãn** → phát hiện phân bào thật nơi GT không nhãn
  vẫn tính FP → **precision division quan trọng hơn recall**.

### d) Nguồn ngoài + tham chiếu ultrack

- **Dữ liệu ngoài KHỚP voxel Kaggle** (1,625/0,40625/0,40625 — đúng hệ):
  `https://public.czbiohub.org/royerlab/ultrack/zebrafish_embryo.ome.zarr/`
  — shape (522, 1, 505, 2170, 2217) uint16, cùng chế độ chụp → ứng viên
  train detector phân bào (cần tải thành Kaggle Dataset, kiểm tra rules).
  ⚠️ Bộ ZSNS001–005 (single-objective) có voxel 1,24/0,439/0,439 — KHÁC Kaggle.
- Config ultrack zebrafish: `max_distance 10.0`, `max_neighbors 5`, penalty
  appear/disappear/division rất nhỏ (0,001–0,1); fork công khai chỉnh
  division 1,2 / disappear 1,5 **không bao giờ tối ưu** được.
- Tool xem dữ liệu: napari (crop ROI quanh node t−10..t+10); focus3d hỗ trợ
  human-in-the-loop annotation. "Lặp lại thí nghiệm Figure 6 của paper ultrack
  là chìa khóa" (hengck23).

### e) Áp dụng vào pipeline của ta

| Hành động | Lý do |
|---|---|
| `SIBLING_GATE` 12 → **14,5µm** | max quan sát 14,65 — gate 12 bỏ lỡ ~10% cặp chị em |
| `PARENT_GATE` 10 → **12µm** | bắt p99 (10,6) bước mẹ→con |
| **Mới — kiểm tra "ổn định khối lượng mẹ"**: khối lượng blob mẹ tại khung tách ≤ ~1,7× baseline riêng của nó | merge-split giả: blob gộp 2 tế bào ≈ 2× đơn; phân bào thật chỉ sáng lên nhẹ (AUC 0,73) |
| Giữ nội suy + xác nhận động học | GT 100% cạnh liền khung; base rate 24:1 |
| Phân bổ công lực: 90% cho adjEJ (trọng số 1,0) — division chỉ 0,1 | Kể cả hạng 40 cũng hỏi "tín hiệu gì chạy được division > 0" |

## ver 3 — Phân bào theo profile độ sáng (từ discussion #740573)

- **Nguồn**: `ver-3/` · **kiểm chứng**: `ver-3/test-ver3-synth.py` — **21/21 ĐẠT**,
  kèm đối chứng ver 2 trên cùng dữ liệu: ver 2 xác nhận nhầm merge-split khéo
  (FP) và bỏ sót phân bào chị-em-xa; ver 3 chặn cái đầu (mass) bắt cái sau
  (gate 14,5)
- Tri thức mới (đo trên nhãn train thật — xem mục Insight ở trên):
  1. **`DIV_SIBLING_GATE_UM` 12 → 14,5**: sister separation p99 = 13,9, max
     = 14,65µm — gate cũ bỏ lỡ ~10% cặp chị em thật.
  2. **`DIV_PARENT_GATE_UM` 10 → 12**: bắt p99 bước mẹ→con (10,6, max 12,3);
     khoảng cách chỉ còn là *cửa sổ tìm kiếm*, không phải tín hiệu (base rate
     24:1 — filter thật là sáng + động học + bảo toàn).
  3. **Mới — "ổn định khối lượng mẹ"** (`DIV_MOM_MAX_RISE = 1,7`): track theo
     dõi khối lượng (mass) từng node; baseline = trung vị ~8 giá trị gần nhất
     (loại 2 khung cuối — đúng lúc sáng lên). Blob mẹ tại khung tách mà
     ≥ 1,7× baseline riêng = **blob gộp 2 tế bào** (merge-split ≈ 2×) → từ
     chối ứng viên phân bào. Phân bào thật chỉ sáng lên nhẹ (AUC 0,73) và
     blob gộp FULL cũng không tách được bằng đỉnh → đây là cửa chặn chính.
     Track non < 4 khung (chưa đủ baseline) → bỏ qua kiểm tra này.
  4. **Mới — "mẹ sáng lên" ưu tiên ứng viên** (`DIV_MOM_BRIGHT_BONUS`): ứng
     viên có mẹ sáng dần (mass tại tách / baseline ≥ 1,05) xếp trước trong
     danh sách cạnh tranh — tín hiệu appearance (AUC 0,73) mạnh hơn hình học.
  5. **Bug fix khi kiểm chứng — con kế thừa vận tốc MẸ** (không phải vectơ
     mẹ→con): vectơ mẹ→con làm dự đoán khung sau vọt xa → con không match →
     ứng viên chết "lost" và bị đề xuất lại MỖI KHUNG (vòng lặp vô hạn trên
     dữ liệu kiểm chứng). Latent bug này cũng có trong ver 2 nhưng bị che bởi
     gate hẹp (10µm) — trên Kaggle nó âm thầm giết các ứng viên phân bào.
  6. Giữ nguyên lõi ver 2: tách blob theo đỉnh + xác nhận động học ≥3 khung
     + nội suy khung mất + P90/MAX 3000 + gate 5–14µm + skip 2 khung.
- Kỳ vọng: bắt thêm phân bào chị-em-xa (ver 2 bỏ sót) và chặn thêm
  merge-split khéo (2 tế bào đi ra xa dần sau khi tách — vượt được kiểm tra
  động học của ver 2 nhưng blob mẹ ≈ 2× đơn bị bắt bởi mass stability).

## ver 2 — Chống gộp blob + phân bào xác nhận (soạn thảo, đã kiểm chứng synthetic)

- **Nguồn**: `ver-2/` (đồng bộ `download/ver2-cell-tracking.ipynb`) · **kiểm chứng**:
  `ver-2/test-ver2-synth.py` — **16/16 ĐẠT** trên Zarr tổng hợp
- 6 nâng cấp so với ver 1 (theo 4 nguyên tắc trên):
  1. **P92 → P90, MAX_NVOXELS 1000 → 3000**: tăng recall (đòn bẩy r²), phạt node
     thừa chỉ 0.1 nên đáng đổi
  2. **Tách blob gộp "eo"**: component > 90 voxel có ≥ 2 đỉnh
     `maximum_filter` cách ≥ 4 voxel ds → cắt thành 2+ node (CoM riêng từng vùng,
     gán voxel → đỉnh gần nhất). Lưu ý: blob "gộp đầy" (2 Gaussian chồng lấp
     < ~2.4σ, vùng giữa sáng hơn đỉnh yếu) KHÔNG tách được — phải chờ tế bào
     đi ra hoặc dùng watershed/DoG (Stage 1)
  3. **MAX_SKIP_FRAMES 1 → 2 + SKIP_GATE 12 µm**: phục hồi track đứt dài hơn
     (nội suy node giữa → cạnh liền khung, không bao giờ cạnh nhảy)
  4. **GATE_MAX 12 → 14 µm, BASE 8 → 9**: bắt tế bào nhanh
  5. **Phân bào xác nhận động học** (cốt lõi): cạnh divergence được HOÃN; chỉ
     ghi khi 2 con cùng sống ≥ 3 khung (`DIV_CONFIRM_FRAMES`) VÀ khoảng cách
     tăng ≥ 15% (`DIV_SEP_GROWTH`) so với lúc "sinh". Merge-split giả (2 "con"
     ở xa ngay từ đầu, đứng yên) bị từ chối → chặn division FP. Cạnh vẫn là
     cạnh liền khung (mẹ t−1 → con t) khi được xác nhận
  6. **Chẩn đoán mỗi dataset**: %node không cạnh vào, số track, trung vị độ dài
     track, phân bào xác nhận/từ chối — so trực tiếp với số liệu ver 1
- Bug đã sửa khi kiểm chứng: xác nhận phân bào từng bị reject ngay trong chính
  step tạo candidate (c1/c2 chưa từng là "prev" → `succ` rỗng) — vá bằng đếm tuổi
  riêng cho candidate vừa tạo
- Kỳ vọng (chưa đo): tăng recall + giảm phân bào giả → mục tiêu 0.3+; cần
  local scorer (dưới) đo chính xác TRƯỚC khi submit

## Local scorer — công cụ đo lường chính (kaggle/scorer/)

- **Nguồn**: `scorer/scorer1..3code.py` (đồng bộ `download/local-scorer.ipynb`) ·
  **kiểm chứng**: `scorer/test-scorer-synth.py` — **31/31 ĐẠT**, khớp 100% điểm
  tính tay trên 2 submission (tốt = 1.100 max; xấu = 0.648 đúng từng thành phần)
- Port trung thành metric chính thức từ repo BTC (không cần tracksdata/geff/zarr —
  chỉ numpy/scipy/pandas/blosc2):
  * Đọc `.geff` zarr **v2 + v3** (đã xác minh blosc2.decompress đọc được chunk blosc1)
  * Ghép node **per-timepoint** Hungarian ≤ 7 µm (như tracksdata DistanceMatching)
  * Edge metric: bỏ cạnh nhảy → collapse merge (giữ 1 cạnh/cặp GT) → cap out-degree 2 →
    TP/FP/FN với **FP có điều kiện** (nguồn/đích bám GT-có-cạnh)
  * adjEJ = EJ·(1 − 0.1·ratio) với `estimated_number_of_nodes` đọc từ geff `.zattrs extra`
  * **Division metric đầy đủ**: window grandparent→divider→children→grandchildren,
    matching per-window, strongly-connected topology, cross-component /
    malformed branches, bipartite pairing — port `division_metrics.py`
  * Micro-average + weight-averaged adjEJ đúng `summarise()`
- Cách dùng (Kaggle notebook mới + Add Input competition):
  1. Chạy notebook pipeline ver 2 → có `submission.csv`
  2. Mở notebook scorer (3 cell) → Run All → bảng điểm per-dataset + tổng
  3. Tune tham số ở cell2code của pipeline → chạy lại → so điểm **offline**,
     không đốt quota 5 submit/ngày

## ver 1 — Stage 0+2 (đã submit · 0.198)

- **Ngày**: 2026-09-13 submit · **điểm Kaggle: 0.198** · nguồn `ver-1/`
- Nâng cấp so với ver 0: CoM theo cường độ · 26-conn · motion model EMA ·
  gate thích ứng 5–12 µm · phân bào 10/12 µm + bảo toàn độ sáng · nội suy khung mất
- **Kết quả chạy test (4 dataset, 12/09/2026)**:

  | dataset | nodes | edges | phân bào | thời gian |
  |---|---:|---:|---:|---:|
  | 44b6_0113de3b | 3771 | 2944 | 68 | 8s |
  | 44b6_0b24845f | 1419 | 833 | 4 | 8s |
  | 6bba_05b6850b | 458 | 328 | 0 | 6s |
  | 6bba_05db0fb1 | 3909 | 2835 | 94 | 8s |
  | **tổng** | **9557** | **6940** | **166** | **~30s / 12h** |

- **Chẩn đoán từ 0.198**: ước tính adjEJ ≈ 0.185–0.19, divJ ≈ 0.05–0.15 → điểm
  gần như toàn bộ đến từ adjEJ; 3 điểm nghẽn: (1) node recall thấp — nhân mờ bỏ
  sót + blob gộp; (2) track đứt — 21–41% node không có cạnh vào; (3) phân bào
  giả merge-split ở 2 dataset dày (68/94). Xem phân tích đầy đủ trên website
  (Phòng đo lường & quy chuẩn → Máy tính điểm, preset "ver 1" khớp 0.197)

## ver 0 — Baseline (notebook gốc Kaggle, không lưu file)

- Notebook "getting started" của ban tổ chức: P90 · 6-conn · tâm hình học ·
  Hungarian gate 15 µm · không phân bào · không frame-skip.
- Chỉ mang tính quy chiếu — không tự viết lại.

## Template cho ver 3+

```
## ver N — <tên>
- Ngày · trạng thái (draft / đã chạy Kaggle / đã submit, điểm LB)
- Nâng cấp so với ver N-1 (từng ý, ngắn gọn)
- Điểm local scorer (trước khi submit!) + điểm Kaggle (sau khi submit)
- Kết quả chạy Kaggle (bảng số liệu như trên)
- Nhận xét / hướng tune tiếp theo
```

Lộ trình sau ver 3: (a) chạy pipeline ver 3 + local scorer trên train để
đo trước khi submit; (b) Stage 1 thật sự (ngưỡng cục bộ thích ứng + DoG +
watershed cho blob gộp đầy); (c) division detector học từ patch thời gian
trên `zebrafish_embryo.ome.zarr` (voxel khớp Kaggle); (d) Stage 3 (U-Net
nhẹ + transformer linking như baseline BTC).
