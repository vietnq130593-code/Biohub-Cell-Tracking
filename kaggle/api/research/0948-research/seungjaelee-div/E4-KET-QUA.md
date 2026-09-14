# E4 — Kết quả 6 notebook div-tuning của sjlee101 (Seung Jae Lee, 7-8/9)

Kéo về: `kaggle/api/research/0948-research/seungjaelee-div/*.ipynb` (6 notebook) +
output ppsweep_results.csv của từng kernel (thư mục /tmp/sjl-* đã phân tích).

## Khác biệt cấu hình (so với base divparent12)

| Notebook | SAFE_DIV_MAX | SISTER_MAX | GLOBAL_FRAC_CAP | DC_SAFE_DIV_THRESHOLD |
|---|---|---|---|---|
| divparent12 (base) | 12.0 | 14.0 | 0.00375 | 0.25 |
| divsister16 | 9.0 | 16.0 | 0.00375 | 0.25 |
| divboth-12-16 | 12.0 | 16.0 | 0.00375 | 0.25 |
| divmax-14-18 | 14.0 | 18.0 | 0.00375 | 0.25 |
| divglobalcap | 9.0 | 14.0 | **0.0075 (2×)** | 0.25 |
| divveto015 | 9.0 | 14.0 | 0.00375 | **0.15** |

## Kết quả validator (rule nội bộ double-reading, CÙNG 8 stems held-out của ta)

**TẤT CẢ 6 notebook: div 4 TP / 1 FP / 8 FN — divJ 0.3076, adjEJ 0.9297, proxy 0.9605. GIỐNG HỆT NHAU.**

## Phân tích

1. Mở gate parent (9→12→14), sister (14→16→18), gấp đôi ngân sách global cap, nới
   DeepCenter veto (0.25→0.15) — **KHÔNG thay đổi KẾT QUẢ phân bào** trên stack sạch
   của họ (0.942-line, cùng 8 stems).
2. → Trần div_tp=4 trên stack của họ không do gate — do (a) chỉ ~4 GT division có
   hình học ứng viên khả thi, phần còn lại bị chặn ở mutual-NN / divergence /
   thiếu node mồ côi (cần E0 audit để xác nhận chi tiết trên stack TA).
3. Khẳng định lần 3 chẩn đoán megayak (sau megayak end-to-end + ver-7b của ta):
   **gate không phải nút thắt — ranking bằng chứng mới là**.
4. Ghi chú GT measurements từ comment notebook (phổ biến cho mọi stack):
   parent-daughter link tối đa 10.4µm (cap 7µm loại ~25% link thật);
   sister separation tới 13.7µm (median 10.4, p90 13.0) — cap 12µm loại ~29% div thật.
   "kimi-v18 LB sweep peaked ~4.0-4.5" cho DIVERGE_UM (chặt hơn 2.25 lại tốt hơn trên LB!).
5. Điều lưu ý cho ver-8: adjEJ 0.9297 của họ < 0.9345 (core) của ta → stack Reyhan vẫn
   mạnh hơn về adjEJ; div 4/1/8 của họ (rule đôi) ≈ 2/1/10 theo official ước tính.

## Files
- `/tmp/sjl-{parent12,divsister16,divboth-12-16,divmax-14-18,divglobalcap,divveto015}/ppsweep_results.csv`
- Notebook nguyên vẹn trong repo: `kaggle/api/research/0948-research/seungjaelee-div/`
