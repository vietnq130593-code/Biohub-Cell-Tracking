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

Lộ trình sau ver 2: Stage 1 thật sự (ngưỡng cục bộ thích ứng + DoG + watershed
cho blob gộp đầy) → Stage 3 (U-Net nhẹ + transformer linking như baseline BTC).
