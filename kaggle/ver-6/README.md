# ver 6 — Fork 0.945 + cell 5 ver 5.1 (LB 0.945 ×2 deterministic)

## Provenance — thư mục này được phục hồi thế nào

Sự cố sandbox rollback 22:30 13/9/2026 đã xoá mất toàn bộ `kaggle/ver-6/` ở local
cùng `download/ver6-cell-tracking.ipynb`. Thư mục này được **kéo lại byte-exact từ
kernel Kaggle** `vietnguyen130593/biohub-ver6` (trạng thái COMPLETE) ngày 14/9/2026:

```
kaggle kernels pull vietnguyen130593/biohub-ver6 -p /tmp/ver6pull
cp /tmp/ver6pull/biohub-ver6.ipynb download/ver6-cell-tracking.ipynb
```

- Notebook chính: `download/ver6-cell-tracking.ipynb` — sha256 `22bbd49af25c87af…`
- Mỗi cell code tách ra `cellNcode.py` (compile PASS từng file) — chỉ để đọc/tìm kiếm;
  bản chạy thật luôn là notebook.

## Cấu trúc 10 cell

| # | File | Nội dung |
|---|---|---|
| 1 | `cell1code.py` | S1 env — 46 biến cấu hình (mặc định = đúng 0.945) |
| 2 | `cell2code.py` | S2 configuration guard — chốt đúng 1 thay đổi model-level |
| 3 | `cell3code.py` | S3 imports + đường dẫn mount 3 pack pilkwang |
| 4 | `cell4code.py` | Cài deps + tự tìm 3 model pack dưới mọi tên mount, SHA256, lỗi tự chẩn đoán (bản cứng hoá so với notebook gốc 0.945) |
| 5 | `cell5code.py` | **ver 5.1** — patch suy luận hai pha (verify-then-write) + chạy dự đoán song song 2 GPU: TTA D4 8 hướng · dual-seed calibrated · low_margin_consensus · retention guard 0.90 · bidirectional harmonic fusion w=0.15 · EDGE_FEATURE_TTA · SECONDARY_EDGE_TTA |
| 6 | `cell6code.py` | S6 hậu xử lý 70KB — tracking/linking/safe-div/retention guard 3,6 + 0,4×gap |
| 7 | `cell7code.py` | S7 audit độc lập — frozen frame-retention probe |
| 8 | `cell8code.py` | S8 official eval held-out trên train dir (8 video, rule đã vá double-reading) |
| 9 | `cell9code.py` | S9 validator + so sánh baseline |
| 10 | `cell10code.py` | S10 tổng kết manifest + chỉ số run |

## Kết quả Kaggle

| Submission | Ngày | Điểm |
|---|---|---|
| 56207468 (v2) | 13/09 13:03 | **0.945** |
| 56210873 (v3 re-run verified) | 13/09 16:18 | **0.945** — khớp tuyệt đối → deterministic |

Validator proxy nội bộ: 0.9430 · adj_edge_jaccard 0.9230 · division_jaccard 0.2000
(điểm yếu đã biết, ver-7b nhắm đúng div_fn=12 nhưng regression → không nộp).

## Chạy lại

Notebook gốc yêu cầu: GPU **T4×2**, Internet **OFF**, 4 Input (competition + 3 pack
pilkwang `biohub-tracking-support-pack-50ep-v1` / `biohub-deepcenter-unet3d-center-prior-v1`
/ `biohub-temporal-unet3d-seed314159-v1`). Save & Run All ~36 phút.
Hoặc dùng `kaggle/api/ktool.py` (`--ver 6`): push / watch / submit tự động.
