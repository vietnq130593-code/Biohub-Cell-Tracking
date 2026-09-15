# WAVE-1 v5 KẾT QUẢ — E2 PPSWEEP-2 + E3 CHẨN ĐOÁN 2 VIDEO XẤU

**Kernel:** vietnguyen130593/biohub-ver8-wave1 v5 · COMPLETE 00:07 UTC 15/9/2026
**Output:** kaggle/api/output/wave1-v5/ (download đầy đủ)

## E1 system-view (cached từ v2 — xác nhận lại)

- adjEJ **0.9280** + div **2/1/10** (divJ 0.1538) → proxy **0.9434** (8 stems, official rule)
- Self-check replay==verbatim: **OK** (không lệch cạnh nào)

## E2 — PPSWEEP-2 (18 global + 2 per-prefix, internal rule + official top-3)

### Bảng official (chỉ top-3 qua gate adjEJ −0.0005):

| Config | adjEJ | edge tp/fp/fn | div t/f/fn | proxy | Δ vs tight55 |
|---|---|---|---|---|---|
| **pp-tight-55-65** | **0.92833** | 5540/236/211 | 2/1/10 | **0.94371** | **+0.00032** |
| tight55 (production) | 0.92801 | 5539/237/212 | 2/1/10 | 0.94340 | — |
| tight65 | 0.92676 | 5539/245/212 | 2/1/10 | 0.94214 | −0.00126 |

**pp-tight-55-65** = per-prefix MOTION_RELINK_TIGHT_UM (44b6→5.5µm, 6bba→6.5µm):
+1 tp, −1 fp, −1 fn so với tight55 toàn cục. **Cải tiến nhỏ nhưng THẬT.**

### Internal (rule nội bộ — div đọc gấp đôi official):

- **relaxed8**: div 4/2/8, proxy internal 0.9539 (cao nhất) NHƯNG adjEJ 0.9254 (−0.0006
  so base) → bị gate adjEJ −0.0005 chặn, không chạy official. +1 div_tp đổi −0.0006 adjEJ
  = không đáng theo đuổi (đúng thiết kế gate bảo vệ).
- Còn lại (tight50, vw040/060, dcgap030/040, bonus110/135, gap55, reuse36, gap2step48,
  minlen5/7, rescue085, edgemax13, relaxed11, pp-tight-50-60): đều ≤ base hoặc kém hơn
  pp-tight-55-65 trên internal.

## E3 — chẩn đoán 2 video xấu (6bba_07e24132, 44b6_267148e4)

- **6bba_07e24132** (t_true 21.485): FP edges ~330/khung tập trung khung 5–12 (đầu video);
  FN rải rác 2–3/khung.
- **44b6_267148e4** (t_true 19.130): FP edges ~270/khung tập trung khung 33–37.
- → FP tập trung theo dải khung — dấu hiệu over-prediction cục bộ (detector), không phải
  lỗi linking toàn cục. Cần can thiệp ở detector/loại node theo dải khung nếu khai thác.

## KẾT LUẬN CHO VER-8

1. Config postprocess tốt nhất hiện biết: **pp-tight-55-65** (+0.0003 official) — chưa có
   trong PPSWEEP của ver-8 v1 (cần per-prefix code trong monolith → defer sang v2 nếu cần).
2. Gate adjEJ hoạt động đúng: chặn relaxed8 (đổi div bằng adjEJ — không đáng).
3. Re-parenting vẫn là đòn chính (+0.0077/sự kiện) — đợi ver-8 GPU v1 chạy xong.
