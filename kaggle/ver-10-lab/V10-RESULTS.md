# V10-LAB KẾT QUẢ & ĐÁNH GIÁ SO SÁNH v10 vs ver-8 (v3-fast)

Ngày 17/9/2026 · Kernel `vietnguyen130593/v10-lab-gpu-t4` v2 — **COMPLETE** 3h36m (push 14:25 → finish 18:06 UTC)
GPU T4×2 · 9 dataset input · 8 stems validator (44b6×4 + 6bba×4, 189k nodes GT-matched)
Output: `v10_lab_rows.csv` (72 hàng per-stem) · `v10_lab_report.json` · `v10_lab_cache/raw_graphs.json` 27MB (đã đẩy dataset `biohub-v10-rawgraphs`) · predict 8 stems chỉ 985s.

---

## 1. ĐỘ TIN CẬY CỦA LAB (cổng kiểm chứng đầu tiên) — PASS

| Đại lượng | v10-lab đo được | Mốc tham chiếu (ver-9 gate, 15/9) | Khớp |
|---|---|---|---|
| ref adjEJ (weighted 8 stems) | **0.928665** | 0.9287 | ✓ 6 chữ số |
| ref proxy (adjEJ + 0.1·divJ) | **0.959434** | 0.9594 | ✓ |
| ref division tp/fp/fn | 4/1/8 | 4/1/8 | ✓ |
| ppsweep base | base 0.959434 | ppTight5565fb 0.9594 | ✓ |

→ Replay **deterministic**: grid v10 tái lập CHÍNH XÁC nền v3-fast → mọi delta trong grid có thể tin dùng trực tiếp.
→ Đồng thời xác nhận: "ver8-base 0.926142" (đối chứng V10-TRIAL-ACCOUNTS) chính là **tight_60 toàn cục** — cấu hình sweep ver-8 v1 đã chọn; v3-fast (per-prefix 5.5/6.5) hơn nó **+0.0025** (đúng bằng delta gate v3-fast ngày 15/9).

## 2. BẢNG KẾT QUẢ GRID 9 CONFIGS (8 stems, official rule, weighted)

| Config | adjEJ | Δ vs ref | proxy | Δ proxy | div tp/fp/fn | cạnh bỏ |
|---|---|---|---|---|---|---|
| **ref = ver-8 v3-fast** | **0.928665** | — | **0.959434** | — | **4/1/8** | — |
| tight 4.5 | 0.926016 | −0.002649 | 0.952683 | −0.006751 | 4/3/8 | 0 |
| tight 5.0 | 0.926655 | −0.002010 | 0.951655 | −0.007779 | 4/4/8 | 0 |
| tight 6.0 | 0.926142 | −0.002523 | 0.954713 | −0.004721 | 4/2/8 | 0 |
| tight 7.0 | 0.928226 | −0.000439 | 0.953226 | −0.006208 | 4/4/8 | 0 |
| **rlf_only** | 0.928665 | **±0.000000** | 0.959434 | ±0.000000 | 4/1/8 | rlf-21 |
| **veto1** | **0.930492** | **+0.001828** | **0.961262** | **+0.001828** | **4/1/8** | veto-455 |
| veto2 (≡ ver-9) | 0.930328 | +0.001663 | 0.953405 | −0.006029 | 3/1/9 | veto-573 |
| veto2rlf (≡ ver-9 nộp) | 0.930328 | +0.001663 | 0.953405 | −0.006029 | 3/1/9 | veto-573/rlf-4 |

Runtime: ref 1057s · veto1 **2306s** (gồm HOCT compute ~1249s cho 189k nodes ≈ 6.6s/1000 nodes thực đo T4) · veto2/veto2rlf 1078s/1073s (reuse cache HOCT — log xác nhận "HOCT edges reused from cache"). Tight sweep ≈ ref (post-processing thuần).

## 3. PHÁT HIỆN CHÍNH

### 3.1 RLF CHẾT HOÀN TOÀN — "v10 = v3-fast + RLF" vô nghĩa
- ΔadjEJ **0.000000**, Δproxy **0.000000**, div giữ nguyên — 21 cạnh RLF bỏ không đổi metric nào.
- Trùng field: ver-9 cũng chỉ bỏ được 2/118.061 cạnh (0.0017%) trên submission thật.
- **Kết luận: KHÔNG nộp v10-RLF. Nó ≡ v3-fast.**

### 3.2 Tight sweep: 5.5/6.5 per-prefix của v3-fast là tối ưu cục bộ
- Cả 4 giá trị toàn cục (4.5/5.0/6.0/7.0) đều ÂM (−0.0004…−0.0026) — trong đó tight 6.0 (−0.0025) chính là cấu hình ver-8 v1 từng chọn bằng sweep.
- Xác nhận v3-fast đã tối ưu đúng hướng; không còn gì để gặt ở nhánh tight.

### 3.3 ★ VETO MODE 1 > MODE 2 — cấu hình duy nhất thắng CẢ HAI chỉ số
- **veto1: adjEJ +0.001828 (cao nhất grid) + proxy +0.001828 (DUY NHẤT dương) + division NGUYÊN VẸN 4/1/8.**
- veto2 (= chế độ ver-9 dùng): adjEJ +0.001663 nhưng mất 1 div_tp (4→3, divJ −0.077) → proxy −0.0060 → đúng lý do gate ver-9 ra FALLBACK.
- Khác biệt nằm ở **1 dòng code** (`_hv_apply_veto`, cell-monolith dòng 3887):
  `if (s,t) in hoct_pairs or (mode == 1 and out_deg[s] >= 2): keep`
  → mode 1 **giữ nguyên cả 2 cạnh của mọi node cha ≥2 con** (bảo vệ division), chỉ veto cạnh đơn; mode 2 veto tất.
- Per-stem: gain veto1 đến từ 2 stem dày **6bba_09961292 +0.00491 (w=1997 — trọng số lớn nhất grid, 33%)** và **6bba_07e24132 +0.00452**; thiệt hại nhỏ 44b6_267148e4 (−0.00054) + 44b6_2a2eff9f (−0.00445); 4 stem còn lại ±0.
- Trên 44b6_267148e4: veto2 phá divJ 1.0→0.0 (mất div_tp) — mode 1 giữ. Đây là toàn bộ khác biệt div.

### 3.4 Runtime HOCT đo thực — đối chiếu rủi ro TLE
- Thực đo validator: **6.6s/1000 nodes** (T4) < slope dự đoán 9s của budget-guard → guard hiện tại KHÔNG kích hoạt skip trên validator (không video nào bị skip).
- Nhưng ver-9 đã TLE trên hidden: chi phí HOCT theo **node/frame (bậc 2)**, embryo-3 hidden dày nhất → dự đoán TUYẾN TÍNH theo tổng node của guard **không nhìn thấy mật độ** — đây là lỗ hổng.
- Guard hiện có: `MAX_VIDEO_S 900s` + `DEADLINE 10h` + skip TRƯỚC video; **không abort GIỮA video** — 1 video chạy lan có thể đốt nhiều giờ.

## 4. ĐÁNH GIÁ SO SÁNH v10 vs ver-8 (v3-fast — bản LB 0.947 hạng 165)

| Tiêu chí | **ver-8 v3-fast** (đang giữ bạc) | **v10-veto1** (ứng viên) | v10-RLF | v10-veto2 (≡ ver-9) |
|---|---|---|---|---|
| Validator adjEJ | 0.928665 | **0.930492 (+0.001828)** | 0.928665 (±0) | 0.930328 (+0.0017) |
| Proxy (metric đầy đủ) | 0.959434 | **0.961262 (+0.0018)** | 0.959434 (±0) | 0.953405 (−0.0060) |
| Division tp/fp/fn | 4/1/8 | **4/1/8 (không đụng)** | 4/1/8 | 3/1/9 (mất 1 tp) |
| LB hidden (đã biết/dự báo) | **0.947 ✓ pass 1.74h** | 0.949±0.001 (nếu transfer) | ≡ 0.947 | **TLE FAIL** (đã chết) |
| Runtime public ước | 1.74h | ~2.0–2.2h (strip replay) | 1.74h | 2.4h → hidden >12h |
| Rủi ro TLE hidden | không | **TRUNG BÌNH** (guard cần thắt) | không | ĐÃ XẢY RA |
| Nguồn gain | re-parent + DivNet rank + tight 5.5/6.5 | HOCT consensus linker mode 1 trên stem dày | — | — |

**Diễn giải chuyển giao LB (nếu +0.0018 adjEJ giữ nguyên trên hidden):**
- v3-fast full-precision ≈ 0.9475–0.9479 → +0.0018 → **0.9493–0.9497** → vượt cụm 0.948 (55 đội, hạng 89–143) → **hạng ~89–120**.
- Điểm mạnh của phép ngoại suy này: veto1 **không đụng division** (Δ divJ = 0 trên validator) → toàn bộ delta là adjEJ thuần, không phải nhiễu divJ 4-mẫu đã làm lỡ gate ver-9.
- Bằng chứng bên ngoài: sjlee101 (tác giả port HOCT) đo +0.0040 CI-dương trên 20 video honest split — cùng bậc độ lớn, dương.

**Vì sao đáng đánh đổi:**
- Hiện hạng 165, cắt bạc 180 — **chỉ dư 15 chỗ**, cụm 0.947 có 525 đội đang đẩy full-precision. Không leo = nguy cơ mất bạc thực tế trước 29/9.
- Còn ~12 ngày, 5 lượt/ngày → 1 field test TLE chỉ tốn 1 lượt.
- Kernel production v10 sẽ **strip toàn bộ validator/gate replay** (bài học ver-9: ~45' public overhead ×5-7 hidden) → public ~2.0–2.2h → hidden ~7–9h nếu mật độ ngang validator; TLE chỉ khi embryo-3 bùng nổ bậc 2 như ver-9.

## 5. GATES D1–D5 (theo V10-LAB-PLAN)

| Cổng | Tiêu chí | Kết quả |
|---|---|---|
| D1 | ref tái lập mốc ver-9 gate (±0.0002) | **PASS** (khớp 6 chữ số) |
| D2 | tồn tại config ΔadjEJ ≥ +0.0010 | **PASS** — veto1 +0.001828 |
| D3 | config thắng KHÔNG hạ div_tp | **PASS** — veto1 giữ 4/1/8 |
| D4 | runtime hidden khả thi (strip replay) | **CẦN VÁ** — guard mật độ + abort giữa video |
| D5 | RLF/tight có giá trị riêng | **FAIL** — cả hai đều chết |

## 6. KHUYẾN NGHỊ

1. **KHÔNG nộp v10-RLF / v10-tight** (≡ v3-fast hoặc tệ hơn — đốt lượt vô ích).
2. **Xây kernel v10 production = v3-fast + HOCT veto MODE 1 + hard guard chống TLE:**
   - `BIOHUB_HOCT_VETO=1`, tight 5.5/6.5 hardcode giữ nguyên, KHÔNG RLF (không giá trị), KHÔNG gate/validator replay trong notebook.
   - Thắt guard: `MAX_VIDEO_S` 900→**300s**; `DEADLINE` 10→**7.5h**; thêm **mật độ node/frame vào dự đoán** (slope theo max nodes/frame thay vì tổng); abort giữa video bằng deadline-check trong vòng frame-pair nếu khả thi.
   - Estimate budget theo thực đo mới: 6.6s/1000 nodes (thay slope 9s) — nhưng nhân hệ số an toàn 3× cho embryo dày.
3. **Quota GPU**: tuần này đã dùng ~5.6h/30h (ver-9 2.4h + probe + v10-lab 3.6h) → còn ~1.5h — **chờ refresh 19/9 (T7)** rồi push v10 production (~2h public). Deadline 29/9 — dư thời gian.
4. **Kỳ vọng**: pass → 0.948–0.949 → hạng ~89–143, bạc chắc chắn + mở đường 0.949; fail TLE → mất 1 lượt, v3-fast vẫn là final → rủi ro giới hạn.
5. Nếu muốn thêm bằng chứng trước khi tốn lượt: replay veto1 trên raw_graphs cache (CPU, 0 GPU) với các ngưỡng skip-density khác nhau để chọn guard tối ưu.
