# VER-7 — KẾ HOẠCH TRIỂN KHAI (nghiên cứu 13/9; cập nhật đợt 2 sau review chuyên gia 13/9 tối)

> (Ghi chú 13/9 22:30: sandbox bị rollback về 12/9 tối — tài liệu này được tái tạo nguyên văn
> từ phiên bản đã viết trong phiên làm việc; ver-7 v1 đã push lên Kaggle TRƯỚC rollback nên
> an toàn và đang chạy. Trạng thái ver-6: v2 = v3 = 0.945 COMPLETE — deterministic khớp tuyệt đối.)

> Mục tiêu ver-7: **0.947 Public LB** (tái hiện notebook Reyhan đã xác minh hai chiều + tăng cường
> kiểm thử bằng official scorer). Khoảng cách cần bắc cầu: +0.002.

---

## 0. Tóm tắt điều hành

| | ver-6 (kết quả thật) | ver-7 (mục tiêu) |
|---|---|---|
| Nền | pawanmali fork v30 (dòng 0.943) | Reyhan `secondary_deepcenter_tta_0947` (dòng 0.947) |
| LB Public | **0.945 ✓ (v2 + v3, deterministic)** — proxy 0.9430 đọc thấp hơn 0.002 | ≈ 0.947 (360 đội đã tái hiện — spike 0.947 trên LB) |
| Cách đạt | — | Port monolith ~3.94k dòng, đổi 5 dòng env path sang pilkwang public |
| Rủi ro chính | — | Path dataset riêng của Reyhan (đã có giải pháp: SHA256 khớp pilkwang) |
| Giữ lại từ ver-6 | ktool pipeline, cấu trúc test, validator | ktool pipeline (`--ver 6/7/7b`) |
| MỚI đợt 2 | — | + official scorer 075fc5f (dataset dalloliogm) + local CV pack (dariushafshar) gắn input → Phase B đo đúng luật |

**Điểm nhấn chiến lược đợt 2** (chi tiết RESEARCH-NOTES — bản gốc đã mất trong rollback,
tóm tắt còn lại trong worklog Task 31-33):
- Public LB ≈ 1 phim (29% của 4 phim test); private 3 phim quyết định thứ hạng cuối → đừng săn <0.005 public.
- Division = đòn bẩy lớn nhất còn lại (ver-6: 100% FN, fp=0) nhưng phải qua RANKING có bằng chứng (divnet)
  + mở gate có kiểm soát — mở gate một mình đã được chứng minh làm điểm XUỐNG 0.017 (megayak).
- Node-count tuning là bẫy đã xác minh (zhincez −0.004 LB sau khi validator hứa +0.013) → loại khỏi roadmap.
- "0.948 reproduction" của cloudssdut là claim GIẢ (tác giả best 0.939) → frontier public verified vẫn là Reyhan 0.947.

## 1. Bản đồ dòng họ notebook (điều tra 13/9)

Dòng chính (đều từ base "fixed-90 dual-seed clean pipeline 0.913"):

```
0.913 base
 └─ 0.933 → 0.934 harmonic mutual-support fusion
     └─ 0.939 wider safe-division + calmer bidirectional
         └─ 0.941 repair-threshold adaptation
             └─ 0.946 primary edge-feature TTA (8-view) + held-out post-process selection (PPSWEEP)
                 └─ 0.947 secondary feature TTA + DeepCenter TTA + safe-div thr 0.25→0.20   ← ĐÍCH (Reyhan)
```

- **Reyhan 0.947** (`reyhanksatria/biohub-cell-tracking-0-947-lb`, 20 votes): monolith 1 code cell
  (~3.937 dòng), `EXPERIMENT_TAG='secondary_deepcenter_tta_0947'`, LB best của tác giả = 0.947 ✓
  + guard in-code `verified_public_lb_0947` + 360 đội spike 0.947.
- Top 0.970 (sersasj): private, không notebook public.
- Kết luận (kiểm chứng hai chiều đợt 2): **Reyhan 0.947 là public verified cao nhất dùng được**.

## 2. Bằng chứng khả thi (đã xác minh máy)

1. **SHA256 khớp 100%**: các hash weights/repo mà code Reyhan kỳ vọng là **tập con** của bảng hash
   cell 4 ver-6 (bộ pilkwang public). Bộ dataset riêng của Reyhan = bản copy pilkwang.
2. Code Reyhan tự `materialize_inference_repo()` + fallback nhiều tầng (`ALLOW_ARTIFACT_FALLBACK=1`).
3. Cùng máy T4×2 (`machine_shape: NvidiaTeslaT4`), Internet OFF — trùng cấu hình ktool đã chạy ver-6 ×3 COMPLETE.

## 3. Diff tham số ver-6 → 0.947 (đã hiệu chỉnh đợt 2)

### 3.1 Env (level predict-script)
| Biến | ver-6 (runtime thật) | Reyhan 0.947 | Ghi chú |
|---|---|---|---|
| `BIOHUB_SECONDARY_EDGE_WEIGHT` | 0.15 | 0.15 | giữ |
| `BIOHUB_SECONDARY_DETECTION_WEIGHT` | 0.475 | **0.80** | ↑ vai trò secondary ở DETECTION |
| `BIOHUB_SECONDARY_EDGE_FEATURE_TTA` (+W 0.75) | 1 | 1 | giữ |
| `BIOHUB_EDGE_FEATURE_TTA` | 1 | 1 | giữ |
| `BIOHUB_BIDIRECTIONAL_EDGE_WEIGHT` | 0.15 | 0.15 | giữ |
| `BIOHUB_DET_THRESHOLD` | 0.965 | 0.965 | giữ |

### 3.2 Env (level post-process)
| Biến | ver-6 | Reyhan 0.947 |
|---|---|---|
| `BIOHUB_DEEPCENTER_SAFE_DIV_VETO` | 0 (TẮT) | **1 (BẬT)** |
| `BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD` | 0.26 | **0.20** |
| `BIOHUB_GAP_CLOSE_UM` | 5.8 | **5.0** |
| `BIOHUB_MOTION_RELINK_TIGHT_UM` | 5.5 | **6.0** |
| `BIOHUB_GAP2_MAX_STEP_UM` | (không có) | **4.4** |
| `BIOHUB_GAP_CLOSE_REUSE_UM` | (không có) | **3.2** |
| `BIOHUB_MOTION_RELINK_RELAXED_UM` | (không có) | **10.0** |
| `BIOHUB_SAFE_DIV_DIVERGE_UM` | (không có) | **2.25** |
| `BIOHUB_PPSWEEP_MAX_ADJ_LOSS` | (không có) | **0.0005** |
| `BIOHUB_PPSWEEP_SELECT_MARGIN` | (không có) | **0.001** |

### 3.3 Code-level (không làm được bằng env — lý do phải port nguyên monolith)
- **DeepCenter spatial TTA** (8-view flip/rot/transpose) áp vào heatmap DeepCenter của repair gate.
- **Secondary association-feature TTA** (weight 0.75).
- **PPSWEEP** — sweep hậu xử lý trên held-out, chọn theo biên an toàn.
- ⚠️ PPSWEEP + validator của Reyhan chọn config bằng divJ **rule cũ** (double-reading) — nhưng vì
  0.947 là LB-verified, phần bù đã nằm trong config → **không chỉnh sửa gì** ở đây.

## 4. Kế hoạch 4 phase

### Phase A — Port monolith Reyhan thành ver-7 (ĐÃ TRIỂN KHAI 13/9 tối)
1. ✅ `api/research/reyhan-947-full.py` (đã mất trong rollback — khôi phục được qua notebook
   pushed + diff đã kiểm trước đó: chỉ 3 dòng header + 5 nhóm dòng path pilkwang).
2. ✅ `ver-7/cell-monolith.py` — py_compile PASS, grep reyhanksatria = 0.
3. ✅ Gắn **6 dataset + competition = 7 nguồn input** (3 pilkwang + official-scorer + cv-pack + v6-heldout-preds).
4. ✅ Đóng gói notebook 3 cell (markdown + monolith + cell Phase B eval).
5. ✅ Push `vietnguyen130593/biohub-ver7` v1 (T4×2, Internet OFF) — **đang chạy** lúc rollback.
6. ⏳ Watch COMPLETE → verify: submission ~241k dòng, audit SHA256, `ground_truth_accessed=false`.
7. ⏳ Submit khi Phase B đạt ngưỡng → kỳ vọng LB ≈ 0.947.

### Phase B — Kiểm chứng bằng official scorer (công cụ đã dựng, tái tạo sau rollback)
1. `cell-eval-official.py` (382 dòng, byte-exact từ notebook pushed) — cell Phase B nhúng SAU monolith:
   chấm predictions held-out bằng **official scorer 075fc5f** cho CẢ ver-7 (self) VÀ baseline ver-6
   (dataset `vietnguyen130593/biohub-v6-heldout-preds`); in preview A/B ngay trong log; **exception-safe**.
2. `compare.py` (tái tạo sau rollback, selftest 3/3 PASS) — paired A/B tại local: micro-pooled
   ΔadjEJ/ΔdivJ/Δproxy + bootstrap CI95 (10k, seed 314159) + 5 guard (G1 div_fn, G2 div_fp,
   G3 node budget, G4 sụt per-video, G5 paired integrity) + VERDICT + gate tuyệt đối.
3. Baseline đông cứng: dataset biohub-v6-heldout-preds (4 .geff raw ver-6, deterministic v2=v3=0.945).
4. Hiệu chuẩn proxy→LB: ver-6 0.9430 → 0.945 (điểm hiệu chuẩn duy nhất).

**Ngưỡng submit ver-7:** `adjEJ_official ≥ 0.942` HOẶC `PROXY_official ≥ 0.945`
(so bằng `compare.py --gate adj:0.942 --gate proxy:0.945`); divJ chỉ tham khảo + guard FP.
**Quy trình sau run:** ktool output → compare.py → chỉ submit khi verdict ≥ LIKELY-UPGRADE và gate đạt.

### Phase C — Nâng cấp vượt 0.947 (DỰNG SẴN ver-7b, chờ cổng Phase B)
**Ưu tiên 1 — Division ranker (divnet RANK-ONLY) + mở gate CÓ KIỂM SOÁT**:
- ver-7b đã dựng: gắn `giorgosi/biohub-divnet-v2`; fork rank key
  `parent_dist + 0.15×sister_dist − 15×P_div` (W=15µm, chuẩn tác giả divnet RANK-ONLY);
  ĐỒNG THỜI nới gate (tau 0.6→1.2, diverge 2.25→1.0).
- Unit test 7/7 PASS với checkpoint thật (epoch 20, best_score 0.893): load + forward + crop
  (16×128×128 raw → pool 4×4 → 16×32×32) + rerank + deterministic + batch consistency.
- Đã vá 1 bug thật trong quá trình: `_postprocess_resume_signature` thiếu prefix DIVNET_
  (resume có thể dùng kết quả postprocess cũ bỏ qua thay đổi divnet).
- Trần thực tế (manifest divnet): LB upside sim ≈ 0.9556 (top-2/phim) — Phase C trọn gói ≈ +0.008.
- Rủi ro đã biết: tác giả divnet + canhtoanle đều chỉ đạt 0.946–0.947 → tích hợp tinh vi;
  phải qua Phase B (official scorer) trước.
**Ưu tiên 2 — Per-prefix gating radii**: 6bba disp_p99 7.9µm vs 44b6 4.9µm — sweep theo prefix.
**Ưu tiên 3 — Velocity-projected gap closing** (topic 739570): chỉ làm nếu quota dư.
**LOẠI KHỎI ROADMAP**: node-count tuning; metric hack; nối orphan thành fork.

### Phase D — Chiến lược final submission cho PRIVATE
- Public = ~1 phim; private = 3 phim; embryo-disjoint; 360 đội cùng detections → shake-up dự đoán.
- Ngày: hết hạn entry **22/9**, chốt final **29/9**.
- Kế hoạch 2 final: (a) ver-7 port nguyên bản; (b) nếu Phase C đạt trên 8 phim held-out → bản
  division-enhanced ver-7b. KHÔNG chọn final theo public-LB delta < 0.005.
- Trước 22/9: mọi version đã có ít nhất 1 submission hợp lệ.

## 5. Rủi ro & giảm thiểu

| Rủi ro | Xác suất | Giảm thiểu |
|---|---|---|
| Mount path pilkwang khác trong kernel push | Thấp (đã verify + fallback nhiều tầng) | walker cứng hoá của Reyhan + SHA256 |
| Monolith ~3.9k dòng khó audit | Trung bình | diff 5 nhóm path + header đã kiểm; guard report in-code |
| 0.947 của Reyhan dùng config khác markdown | Thấp | code là chân lý — env trích từ code |
| Tin proxy khi tune division | Cao nếu làm ẩu | Phase B bắt buộc official scorer |
| Hết lượt submit trong ngày | — | chỉ submit khi Phase B đạt (5/ngày) |
| Săn public-LB micro-delta < 0.005 | Cạm bẫy | 1 phim = nhiễu; không submit < 0.005 kỳ vọng |
| Notebook chờ chấm > 6h | Đã biết | bình thường (6–12h phổ biến) |
| **Sandbox rollback mất file local** | ĐÃ XẢY RA 13/9 22:30 | mọi artifact quan trọng đã/đang đẩy Kaggle; tái tạo từ context + kernels pull |

## 6. Tệp nghiên cứu (api/research/ — bản gốc mất trong rollback 13/9; có thể kéo lại từ Kaggle)

- `reyhan-947-full.py` — monolith 0.947 (khôi phục qua diff từ notebook pushed hoặc kernels pull)
- `divnet/v2/best_overall.pt` + ARTIFACT_MANIFEST — ✅ ĐÃ khôi phục (tải lại từ giorgosi/biohub-divnet-v2)
- Các notebook nghiên cứu khác (megayak, zhincez, canhtoanle, cv-pack, official-scorer...) — kéo lại
  bằng `kaggle kernels pull <owner>/<slug>` khi cần; danh sách slug trong worklog Task 31-33.
