# VER-8 THIẾT KẾ — RE-PARENTING DIVISION RECOVERY

**Ngày 14/9/2026** · Dựa trên dữ liệu Wave-1 v1 (E1 + div diagnostics) — đợi v2
cộng thêm: bảng E0 grid + re-parent chi tiết + E2/E3.

## 1. Phát hiện nền tảng (từ wave1 v1)

Trên 8 stems held-out (official rule), 12 sự kiện phân bào GT phân rã:

| Nhóm | Số | Mô tả | Cơ chế hiện tại |
|---|---|---|---|
| A — có cặp mồ côi | 3 | D2 mồ côi (không cạnh đến) | safe-div: 2 đã thu hồi (44b6_341df25f, 6bba_062c8d37), 1 bị mutual_nn+deepcenter từ chối (6bba_09961292) |
| **B — re-parent** | **6** | **Cả 2 con ĐÃ detect + match GT, nhưng D2 CÓ cạnh đến từ node Y khác** | safe-div KHÔNG BAO GIỜ xét (chỉ nhìn node mồ côi) |
| C — thiếu detection | 3 | Con thứ 2 không được detect | không thể cứu bằng postprocess |

Điểm hệ hiện tại: **div 2 TP / 1 FP / 10 FN → divJ 0.154**. Mỗi sự kiện nhóm B
thu hồi được = **+0.0077 điểm tổng** (giả sử FP không đổi).

## 2. Cơ chế re-parenting (mới — chưa ai làm, tổng hợp 3.7)

```
Với mỗi node M (frame t) có đúng 1 cạnh ra M→D1:
  P_div(M) = DivNet(M)  [ranker đã có]
  Với mỗi node D2 (frame t+1) trong bán kính R của M, D2 ≠ D1, D2 CÓ cạnh vào Y→D2 (Y ≠ M):
    BẰNG CHỨNG (đủ mới cho phép tháo cạnh):
      e1. parent_dist = |M→D2| ≤ REPARENT_MAX_UM (12µm — đúng số đo GT ≤10.4)
      e2. sister_dist = |D1→D2| ≤ REPARENT_SISTER_UM (16µm — GT p90 13.0)
      e3. symmetry: |child_dist − parent_dist| / mean ≤ REPARENT_TAU (0.8?)
      e4. cạnh hiện tại YỄU: edge_prob(Y→D2) ≤ REPARENT_EDGE_PROB (0.35?)
          HOẶC Y→D2 dài bất thường: |Y→D2| ≥ REPARENT_CURRENT_FAR_UM
      e5. divergence: grandchildren của D1, D2 tách nhau ≥ REPARENT_DIVERGE_UM
      e6. DeepCenter(D2) ≥ DEEPCENTER_SAFE_DIV_THRESHOLD (0.20 — giữ nguyên)
      e7. P_div(M) ≥ REPARENT_MIN_PDIV (0.5?)  [tuỳ E0]
    XẾP HẠNG theo bằng chứng + budget (frame cap / global cap như safe-div)
    HÀNH ĐỘNG: REMOVE Y→D2, ADD M→D2
```

### 2.1 Vì sao an toàn về adjEJ

- Nếu Y→D2 là cạnh SAI (FP): tháo nó → EJ tăng (bớt FP), thêm M→D2 đúng → TP.
  **Double win.**
- Nếu Y→D2 là cạnh ĐÚNG (TP): điều này chỉ xảy ra khi Y là GT-parent của D2.
  Nhưng D2 có đúng 1 GT-parent là M (mẹ phân bào) — nên nếu GT edge (Y,D2) đúng
  thì Y≡M trong GT. Nói cách khác: **nếu D2 thật sự là con của M (đang phân bào)
  thì cạnh Y→D2 với Y≠M PHẢI LÀ SAI** → thay bằng M→D2 luôn đúng.
- Rủi ro thật: D2 KHÔNG phải con của M (giả thuyết phân bào sai) → mất 1 TP (Y→D2
  đúng) + thêm 1 FP (M→D2) + có thể div_fp. EJ mất ~0.0002/edge nhưng divJ mất
  0.07 nếu div_fp. → BẰNG CHỨNG e1-e7 phải chặt.

### 2.2 Guard bổ sung (chống div_fp)

- max_outdegree(M) sau khi thêm = 2 ✓ (đã có guard submission)
- D2 sau khi tháo cạnh vẫn có 1 parent ✓ (topology hợp lệ)
- Y sau khi tháo có thể thành track đứt — chấp nhận (track Y kết thúc sớm là sinh
  học bình thường; OUTPUT_KEEP_DIVISION_COMPONENTS giữ component có phân bào)

## 3. Tham số cần E0/v2 quyết định

| Tham số | Ứng viên | Nguồn dữ liệu |
|---|---|---|
| REPARENT_MAX_UM | 9 → 12 | v2 diagnostics: dist_mother_to_daughter của 6 event |
| REPARENT_EDGE_PROB | 0.25 / 0.35 / 0.48 | v2: edge_prob cạnh hiện tại của 6 event vs phân bố nền |
| REPARENT_MIN_PDIV | 0.3 / 0.5 / tắt | v2: p_div của mẹ 6 event + E0 grid |
| REPARENT_TAU | 0.8 / 1.0 | v2: symmetry của 6 event |
| REPARENT_DIVERGE_UM | 1.5 / 2.25 | v2: diverge của 6 event |
| Budget | giữ SAFE_DIV_FRAME_FRAC_CAP 0.0076 / GLOBAL 0.00375 | như production |

## 4. Tích hợp vào monolith ver-8 (Wave 2)

1. Fork ver-7/cell-monolith.py (KHÔNG phải ver-7b — giữ gate gốc tau 0.6/div 2.25).
2. Thêm block `[ver8]` sau `add_safe_divisions_postlink` trong `filter_output_graph`
   (chạy TRƯỚC prune-isolated/short-track — đúng chỗ safe-div):
   `edges = add_reparent_divisions_postlink(nodes_by_id, edges, stats, ...)`
   + DivNet bundle đã load (tái dùng khối load của ver-7b — RANK-ONLY).
3. PPSWEEP-2: thêm candidates re-parent (min_pdiv × edge_prob) vào PP_CANDIDATES —
   validator tự chọn theo gate ±0.0005 adjEJ (cơ chế chọn an toàn ĐÃ CÓ sẵn!).
4. EVAL CELL bản đã vá: tự chấm system-view official trong run (ver-7b đã có pattern).
5. EXPERIMENT_TAG: `secondary_deepcenter_tta_0947_reparent_v8`.

## 5. Cổng submit (Phase B v2 — siết)

- official system-view: ΔadjEJ ≥ −0.0005; div_tp ≥ +2; div_fp ≤ +3 (trên 8 stems)
- guards 5/5 (G1-G5 như compare.py) + node budget ±10%
- ELEVEN rule: Δproxy ≥ +0.005 → submit tự tin; nhỏ hơn → cân nhắc khi div_tp rõ

## 6. Kỳ vọng

- Trung bình (thu 2/6 re-parent + giữ 2 hiện tại): div 4/1/8 → divJ 0.308 →
  **proxy +0.015** → LB ước 0.950-0.955 (nếu MAP sang test giữ tỉ lệ ~50%).
- Thận trọng (thu 1/6): +0.008 → LB ~0.947-0.949.
- Rủi ro: div_fp nổ → cổng chặn submit (như ver-7b) — mất 1 lần chạy GPU (~2h).

---

## 7. CHUẨN HÓA THỰC TẾ TỪ WAVE-1 v2 DIAGNOSTICS (14/9 17:15)

### 7.1 Sự kiện 6 ca re-parent (tất cả cạnh hiện tại ĐỀU GT-WRONG như lý thuyết)

| # | stem | \|M→D2\| | \|Y→D2\| (cạnh sai) | prob(Y→D2) | Ghi chú |
|---|---|---|---|---|---|
| 1 | 44b6_12dfb391 | 5.39 | 5.14 | **0.647** | hai cha gần như nhau |
| 2 | 44b6_267148e4 | 5.86 | 5.86 | **không có trong raw (→0)** | hai cha tie |
| 3 | 44b6_2a2eff9f | 11.26 | **1.62** | **0.914** | division RỘNG, cạnh sai rất gần — khó nhất |
| 4 | 6bba_07e24132(a) | 11.02 | 2.81 | **0.494** | division rộng |
| 5 | 6bba_07e24132(b) | 5.14 | **0.33** | **không có trong raw (→0)** | cạnh sai siêu gần |
| 6 | 6bba_09961292 | 6.70 | 3.63 | **0.700** | |

**Kết luận chuẩn hóa:**
- Bằng chứng "cạnh hiện tại yếu" (prob ≤ 0.35 hoặc dist ≥ 7.5µm) chỉ bắt được **2/6**
  (ca 2, 5 — cạnh không có trong raw → prob 0). Ca 4 (0.494) cần ngưỡng 0.5.
- **4/6 cạnh sai CẦN DivNet P_div(M) + sister-geometry + divergence** — edge_prob
  không đủ (3/6 cạnh sai có prob 0.65–0.91: transformer tin cạnh sai!).
- prob(M→D2) khi xuất hiện trong raw: 0.858 (ca 2) — transformer ĐÃ chấm cặp mẹ–con
  cao nhưng ILP không chọn được (assignment 1-1 không cho out-degree 2).
- P_div của 3 mẹ (nhóm có cặp): 0.89–0.95 → mẹ phân bào thật có P_div cao.

### 7.2 Tham số chốt cho ver-8 (base) + PPSWEEP tự chọn

- Base (env): `MIN_PDIV=0.5`, `EDGE_PROB=0.25`, `MAX_UM=12`, `SISTER=16`, `TAU=1.0`,
  `DIVERGE=2.25`, `CURRENT_FAR=7.5`, caps như safe-div.
- PPSWEEP candidates thêm: **`rp-off`** (tắt hoàn toàn — van thoát nếu re-parent
  gây hại), `rp-pdiv30`, `rp-ep35`, `rp-far8`, `rp-max11`, `rp-tau08`.
- Hiệu năng: P_div lazy — chỉ tính sau khi cặp qua lọc hình học (không quét 25k
  node mẹ/stem).

### 7.3 Kỳ vọng hiệu chỉnh

- Kịch bản an toàn (bắt 2 ca weak-edge + pdiv lọc sạch FP): div 4/1/8 → divJ 0.308
  → proxy +0.015 so với 0.9434.
- Kịch bản đầy đủ (DivNet mở thêm ca 4, 6): div 6/1–2/6 → +0.02–0.03.
- Rủi ro div_fp: kiểm soát bằng MIN_PDIV 0.5 + rp-off escape + cổng Phase B.
