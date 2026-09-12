# Registry phiên bản bài nộp — Kaggle "Biohub - Cell Tracking During Development"

Mỗi lần thay đổi thuật toán nộp bài = **một phiên bản (ver)**. Code của từng cell
được lưu tại `ver-N/cell1code.py` … `cell4code.py` — dán đè cell tương ứng của
notebook Kaggle gốc rồi **Save & Run All → Submit**.

> Quy ước: cell1code = Cell 1 (imports) · cell2code = Cell 2 (siêu tham số) ·
> cell3code = Cell 3 (pipeline chính) · cell4code = Cell 4 (xuất submission.csv).
> Cell 1 và Cell 4 gần như bất biến; mọi thay đổi thuật toán nằm ở Cell 2 + Cell 3.

## ver 1 — Stage 0+2 (bản hiện tại)

- **Ngày**: 2026-09-12 · **Trạng thái**: đã chạy Cell 3 trên Kaggle test 4 dataset ✓, chờ submit lấy điểm sàn
- **Nguồn**: `ver-1/` (đồng bộ `download/stage0plus2-kaggle-4cells.py` / `.ipynb`)
- **Nâng cấp so với ver 0** (baseline getting-started):
  1. Đọc Zarr: lắp ghép đủ chunk có mặt (chunk 0/0/0 vẫn là đường nhanh)
  2. Detection: downsample bất đối xứng z×2/xy×4 · liên kết 26-ô (chống tách nhân giữa các lát z) ·
     tâm **center-of-mass theo cường độ** (float nội bộ, int khi xuất) · lọc MIN/MAX 4–1000 voxels
  3. Linking: **motion model EMA** (v ← 0.5·mới + 0.5·cũ), Hungarian trên vị trí **dự đoán**,
     gate thích ứng = 2.5×trung vị bước đi, kẹp 5–12 µm
  4. Frame-skip: nối lại track mất 1 khung + **nội suy node giữa** + 2 cạnh liền khung
     (cạnh nhảy t→t+2 luôn FP theo metric — nội suy mới thu được +2 TP)
  5. Phân bào: cạnh thứ 2 với DIV_PARENT_GATE 10 µm + DIV_SIBLING_GATE 12 µm +
     bảo toàn độ sáng (0.55–1.8) + DIV_MIN_CHILD_FRAC 0.15
  6. Vận hành: TIME_LIMIT_HOURS 11, progress print 50 khung
- **Kết quả chạy Kaggle (test công khai 4 dataset, 12/09/2026)**:

  | dataset | nodes | edges | phân bào | thời gian |
  |---|---:|---:|---:|---:|
  | 44b6_0113de3b | 3771 | 2944 | 68 | 8s |
  | 44b6_0b24845f | 1419 | 833 | 4 | 8s |
  | 6bba_05b6850b | 458 | 328 | 0 | 6s |
  | 6bba_05db0fb1 | 3909 | 2835 | 94 | 8s |
  | **tổng** | **9557** | **6940** | **166** | **~30s / 12h** |

- **Chẩn đoán từ kết quả**: 21–41% node không có cạnh vào (track đứt — phát hiện
  nhấp nháy); mật độ phân bào ở 2 dataset dày (68/94) khả năng chứa phân bào giả
  do blob gộp–tách → xem `worklog` Task 13 để có phân tích đầy đủ.

## ver 0 — Baseline (notebook gốc Kaggle, không lưu file)

- Notebook "getting started" của ban tổ chức: P90 · 6-conn · tâm hình học ·
  Hungarian gate 15 µm · không phân bào · không frame-skip.
- Chỉ mang tính quy chiếu — không tự viết lại.

## Template cho ver 2+

```
## ver N — <tên>
- Ngày · trạng thái (draft / đã chạy Kaggle / đã submit, điểm LB)
- Nâng cấp so với ver N-1 (từng ý, ngắn gọn)
- Kết quả chạy Kaggle (bảng số liệu như trên)
- Nhận xét / hướng tune tiếp theo
```
