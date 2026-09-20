# ANALYSIS — haideptry "Biohub SOTA 0.948+ | Density-Adaptive 2xT4 (22m)"

**Task ID:** 5-a (batch A #1) · **Ưu tiên:** CAO NHẤT (đúng target 0.948+ của v12)

## 0. Metadata
- **Nguồn:** `/home/z/v11-recovery/research/haideptry-sota948/biohub-sota-0-948-density-adaptive-2xt4-22m.ipynb` (17 cells, 203KB, không monolith base64)
- **Output đã pull (kiểm chứng trực tiếp):** `/home/z/v11-recovery/research/haideptry-sota948/output/` — submission.csv 241.362 rows (INT dtype ✓), run_stats.csv, kernel log 2.061 dòng, integrity json, retention guard reports. Receipts nhỏ copy vào thư mục này.
- **Kernel lineage (từ log):** `source_kernel: raykkretzschmar/biohub-bidirectional-primary-union13-diagnostic-v1`; attribution rule harmonic fusion = `yusuketogashi/no-hack-biohub-cell-another-approch-3rd v18` (CC0). Cùng họ hàng reyhanksatria/evgendvorkin nhưng nhánh raykkretzschmar.
- **`leaderboard_feedback_used_for_configuration: true`** — các knob per-movie được tune bằng feedback LB.
- **Runtime thật (từ log):** ~1.686s ≈ **28 phút** tổng (inference 8,92 phút, post-processing ~8,2 phút song song 4 thread). Title "22m" = marketing.

## 1. Kiến trúc (1 câu)
Fork của public "harmonic_v3_division_wide" (raykkretzschmar lineage) = dual-seed harmonic fusion + 8-view planar TTA + edge-feature TTA + ILP + post-chain chuẩn họ (gap/gap-density/gap2/safe-div/DC-veto/short-track+rescue/linefit), **thêm 3 lớp riêng:** (a) density-adaptive group overrides cho motion relink, (b) DivNet 3D-CNN mitosis gate, (c) GPU speed engineering (direct-path I/O, CUDNN wscap, batch 8).

**Parity 3/3 checkpoint với mình + alfonso** (integrity json): primary `12f6881e…`, secondary `9bac2fa0…`, deepcenter `8040999a…` → chênh điểm KHÔNG đến từ model, chỉ đến từ lớp config/post-processing (giống kết luận E-6 lượt 4 alfonso).

## 2. Bảng env-knob diff vs stack mình (ver-8/v3-fast)

| Knob | Mình | haideptry | Đánh giá |
|---|---|---|---|
| DET_THRESHOLD | 0.965 | 0.965 | GIỐNG |
| ILP appear/disappear/div | 0.0 / 2.0 / 1.2 | 0.0 / 2.0 / 1.2 | GIỐNG |
| GAP_CLOSE_UM / MAX_GAP | 5.0 / 2 | 5.0 / 2 | GIỐNG |
| GAP_DENSITY_ADAPTIVE (gain 0.04/ref 6.5/Δ0.125/nb3) | có | có | GIỐNG (di sản chung) |
| SAFE_DIV 9/14/2.25/τ0.6/mutualNN | có | có | GIỐNG |
| SAFE_DIV_EXISTING_CHILD_MAX_UM | 10.0 | 10.0 | GIỐNG |
| Caps frame/global | 0.0076/0.00375 | 0.0076/0.00375 | GIỐNG |
| MIN_TRACK_LEN | 6 | 6 | GIỐNG |
| ADAPTIVE_SHORT_TRACK_RESCUE (0.88/3.0/1.2%/120) | có | có | GIỐNG (đã có từ ver-10, di sản harmonic_v3) |
| BIDIR 0.15 harmonic + retention 0.90 | có | có | GIỐNG |
| SEF_TTA w0.75 + EDGE_FEATURE_TTA + DC_TTA | có | có | GIỐNG |
| MOTION_RELINK_TIGHT_UM | 5.5 global + per-prefix {44b6:5.5, 6bba:6.5} | 5.5 global, **override per-density: LOW 7.25 / MID 6.5 / HIGH 5.5** | **KHÁC** — nhóm theo density (3 nhóm) thay vì prefix (2 nhóm); tách 05b6850b (LOW) khỏi 05db0fb1 (HIGH) trong khi mình gộp cả 2 vào 6bba=6.5 |
| MOTION_RELINK_RELAXED_UM | default 10.0 (không override) | **per-density: LOW 11.0 / MID 9.0 / HIGH 10.0** | **KHÁC** — mình không tune trục này |
| MOTION_RELINK_LEARNED_BONUS | 1.0 | 1.0 global, **override: LOW 3.0 / MID 6.0 / HIGH 1.0** | **KHÁC LỚN NHẤT** — MID (2 phim 44b6) weighting learned-prob gấp 6x |
| MOTION_RELINK_VELOCITY_WEIGHT | 0.5 | **LOW 0.5 / MID 0.0 / HIGH 0.5** | KHÁC — MID tắt motion prediction |
| DEEPCENTER_SAFE_DIV_THRESHOLD | **0.20** | **0.25** | **KHÁC** — hội tụ với alfonso (0.25) + evgendvorkin (0.26) + newwang12 (0.25) |
| DEEPCENTER_SAFE_DIV_VETO | 1 | 1 | GIỐNG (evgendvorkin thì OFF) |
| DEEPCENTER_GAP_THRESHOLD | 0.25 | 0.25 | GIỐNG |
| DivNet | RANK-ONLY W=15 | VERIFY p≥0.50 gate | **KHÁC mode** — nhưng xem §3.2: NO-OP trong run thật |
| UNET_BATCH_SIZE | 4 | 8 | KHÁC (chỉ runtime) |
| VALIDATOR_ENABLE | off (lab riêng) | 0 | giống triết lý |

Census output (verify trực tiếp CSV): **122.821 node / 118.541 edge / 96 fork** (46/14/9/27) — ngang alfonso foundation (92), bằng ~½ fork mình (188). run_stats: safe_divisions_added = 46+14+9+27 = 96 → toàn bộ fork từ safe-div, DC 0.25 chấp ~213 vs DC 0.20 của mình chấp ~317.

## 3. Kỹ thuật đáng giá cho v12

### 3.1 ★★★ Density-Adaptive Group Overrides (ĐÂY LÀ DELTA THẬT CỦA NOTEBOOK NÀY)
```python
DENSITY_GROUP_OVERRIDES = {  # áp vào motion_relink_edges(tight, relaxed, velocity, bonus)
  "low":    {"tight_um": 7.25, "relaxed_um": 11.0, "velocity_weight": 0.5, "learned_bonus": 3.0},   # 6bba_05b6850b (~61 node/frame)
  "middle": {"tight_um": 6.5,  "relaxed_um": 9.0,  "velocity_weight": 0.0, "learned_bonus": 6.0},   # 44b6_0b24845f, 44b6_0113de3b (~259-354)
  "high":   {"tight_um": 5.5,  "relaxed_um": 10.0, "velocity_weight": 0.5, "learned_bonus": 1.0},   # 6bba_05db0fb1 (~703)
}
# determine_density_group: avg_per_frame <120 → low; <400 → middle; else high
```
- **Phù hợp hướng density-guard của mình nhưng GENERAL HƠN**: mình override mỗi knob `tight` theo prefix; họ override 4 knob (tight+relaxed+bonus+velocity) theo density đo được <0.001s. Phân nhóm cũng KHÁC: mình gộp 05b6850b+05db0fb1 vào "6bba=6.5", họ tách LOW(7.25, bonus 3, relaxed 11 — cell di chuyển tự do) vs HIGH(5.5, bonus 1 — chống nhầm lẫn hàng xóm).
- Không có receipt nào trong output chứng minh từng nhóm contributed bao nhiêu — chỉ có claim bảng markdown "0.947→0.948+". Với `leaderboard_feedback_used_for_configuration: true`, các con số này đã qua ít nhất vài probe LB của lineage (không biết của ai).
- **Port cost:** ~40 dòng (dict + determine_density_group + parametrize motion_relink_edges — hàm motion_relink của mình đã nhận đủ 4 param nếu là bản harmonic_v3 chuẩn). A/B khô được trên cache geff của v10.

### 3.2 ★ DivNet 3D-CNN Mitosis Gate — PHÁT HIỆU NGHIÊM TRỌNG: **NO-OP TRONG RUN 0.948**
- Gate nằm trong `filter_output_graph` → nhánh division-geometry-filter: với mỗi fork, tính prob từ DivNet (Conv3D 4-frame crop 16×32×32 quanh parent, zpad8/xypad16, checkpoint `giorgosi/biohub-divnet-v2`) và veto nếu p<0.50.
- **Receipt trong run_stats.csv + log: cột `divnet_vetoed_divisions` KHÔNG TỒN TẠI** (= không lần nào được increment) → DivNet đã load OK nhưng **không veto fork nào cả 4 phim** (geometric candidates 175/229/23/304 → added 46/14/9/27, geometry filter giữ 100%). "Pillar #2" của notebook là trang trí.
- → **Không port gì từ phần này** (mình đã có DivNet RANK-ONLY W=15 tinh tế hơn). Tiết kiệm được effort: cổng CPU+GPU này vô ích trên fork đã qua geometric gates.
- Ngoài ra module có 1 bug tiềm ẩn đáng học: `divnet_score_division` trả `None` khi exception → silently pass (fail-open). Nếu port bất kỳ veto học nào cho v12: phải fail-closed hoặc đếm rõ.

### 3.3 ★★ DC_SAFE_DIV 0.20 → 0.25 (hội tụ lần thứ 4)
alfonso 0.25 · haideptry 0.25 · evgendvorkin 0.26 · newwang12 (batch C) 0.25 — mình là ngoại lệ duy nhất còn 0.20. Trên hidden: 0.25 cắt funnel 736→213 (alfonso E-8) vs 0.20 cắt 763→317. Đây là knob rẻ nhất để đưa fork count mình về vùng ~96-127. Đã nằm trong backlog batch C; notebook này tăng thêm độ tin.

### 3.4 ★ Direct-path I/O + CUDNN wscap + batch 8 + ThreadPool(4) post-processing
- `_dc_checkpoint_candidates`: thay recursive `glob("**/full_frame_center/**")` trên FUSE (đông cứng ~5.75 phút) bằng direct paths `/kaggle/input/datasets/<owner>/<slug>/...` + fallback glob. **Trùng fix v11-fix-r4 của mình** (probe 2 layout) — xác nhận đúng hướng.
- `CUDNN_CONV_WSCAP_DBG=1024`, `TORCH_CUDNN_V8_API_ENABLED=1`, TF32 override, `UNET_BATCH_SIZE=8` (4→8): inference 9 phút/2×T4. Port-trivial nếu v12 cần room cho validator chạy cùng kernel.

### 3.5 (nhỏ) `BIOHUB_VALIDATOR_N_PER_TYPE=4` + guard chống config-drift `_EXPECTED_NUMERIC` assert
Pattern "config guard" (raise nếu env drift) có trong cả 4 notebook — mình đã có tương đương trong harness; không mới.

## 4. Claim điểm + bằng chứng
- **Claim:** bảng markdown "Our Adaptive SOTA (New) = 0.948+ 🚀 ~22m". Benchmark table trong markdown: baseline 0.913 → harmonic 0.939-0.946 → "Our Previous SOTA" 0.947 → adaptive 0.948+.
- **Receipt trong output:** KHÔNG có điểm LB (kernels output không chứa LB). Có: submission sha256 `60698918…`, 241.362 rows, topology sạch (INT, DAG, out≤2, t+1). Run COMPLETE.
- **Đánh giá độ tin:** kiến trúc = đúng cụm 0.947 + 2 delta thật (density-group relink + DC 0.25). Claim +0.001-0.002 so với 0.947 baseline là KHA THI (không kiểu 0.9605-alfonso). Không thể verify trực tiếp không có LB access; coi như "plausible, chưa kiểm chứng". Lưu ý: title "SOTA" và badge "Top-Tier" là tự gắn.

## 5. Nguy cơ sai / overfit
1. **Per-movie tuning qua LB feedback** (`leaderboard_feedback_used_for_configuration: true`) — các giá trị 7.25/11.0/3.0... là probe LB trên đúng 4 phim test → gain có thật trên LB nhưng có thể không transfer sang private (nếu private khác movies). Với mục tiêu huy chương (private final) cần cân nhắc; với mục tiêu "0.948 LB" thì hợp lệ.
2. Mid-group `learned_bonus=6.0` + `velocity=0.0` là cặp giá trị mạnh và bất thường (họ tin learned-prob hơn hình học 6x ở phim 44b6) — nếu fork base khác (như của mình có HOCT/reparent), giá trị này có thể không còn tối ưu.
3. DivNet gate nếu ai copy không để ý sẽ tưởng có tác dụng (không có).
4. Runtime 28' không 22' — vẫn thoải mái quota.

## 6. Verdict cho v12
**PORT (chọn lọc):** (1) density-adaptive group overrides cho motion relink — port ~40 dòng, A/B khô trên cache v10, kỳ vọng +0.001~0.003 (đúng trục association/edge — trục chiến đấu thật); (2) DC 0.25 — knob 1 dòng, hội tụ 4 nguồn. **KHÔNG port:** DivNet verify gate (no-op + fail-open). **Tham khảo:** GPU speed pack nếu v12 cần chạy validator trong cùng kernel. Rủi ro overfit LB của bộ override: chấp nhận được ở giai đoạn này, ghi rõ nguồn knob = LB-tuned.
