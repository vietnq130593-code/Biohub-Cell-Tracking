# ANALYSIS — noisyislands/biohub-cell-tracking-tabpfn-3-5-events (TabPFN 3.5 Events)

**Task ID:** 5-b · **Ngày:** 20/9 · **Loại:** KERNEL TRAINING (16 cell, plan §5A; không submission)
**Nguồn:** /home/z/v11-recovery/research/noisyislands-tabpfn/biohub-cell-tracking-tabpfn-3-5-events.ipynb + output pull 20/9 (log 10 KB + artifacts/tabpfn35 + mined_features).

## 1. Pipeline

1. **Bootstrap:** install tabpfn/zarr/lightgbm; download checkpoint HF `Prior-Labs/tabpfn_3_5` — fast variant `tabpfn-v3.5-fast-20260909.safetensors` 334 MB (sha256 `14e0b81285bca7a6…`, có fallback full 876 MB).
2. **Mining (cell 8):** GT-only — +1 = GT fork (≥2 con), 0 = hard negative (parent 1-con + non-child cùng frame, 1 neg/fork), −1 = unannotated (khái niệm có trong markdown, không sinh ra ở code này). `MAX_MOVIES=8` mặc định. Cùng 13 feature như XGBoost kernel (local_density/parent_velocity NaN).
3. **Fit (cell 11):** TabPFN 3.5, `n_estimators=8`, context = leave-outer-movie-out (outer = phim đầu theo alphabet); đánh giá outer-fold; **calibration affine** (w,b lstsq trên inner probs); LightGBM reference (100 estimators, leaves 15) cùng feature.
4. **Provenance (cell 15):** device/GPU/sha/fold/calib.

## 2. Receipt chạy thật (log pull 20/9) — giá trị bằng chứng ≈ 0

- Bundle v2 được mount, nhưng code cell 8 **chỉ có nhánh `gt_only_mine_division`** — manifest vẫn ghi `source: production_detector` ⇒ **nhãn provenance sai**.
- Discovery khác XGBoost kernel: glob `.geff` only → 199 phim, xử lý 8 phim đầu (đều 44b6_*).
- **Kết quả mining: 1.082 row, pos = 1, neg = 1.081.** Context (1.061, 13) với **1 positive**; outer fold = 44b6_0b24845f với n=21, **pos=0**.
- TabPFN fit 6.4 s → "outer acc = 1.000" (cả fold không có positive — trivial); calibration w=1.019 b≈0; LightGBM outer acc 1.000 (cùng trivial). Tổng runtime ~40 s.

## 3. Đánh giá độ nghiêm túc

- **Zero-shot tabular cho division events** = ý tưởng hay trên giấy, nhưng ở trạng thái hiện tại: 8/597 phim, 1 positive, eval all-negative, provenance mislabeled, không inference integration (consumes bởi `src/models/tabpfn_events.py` trong repo private — chưa từng qua LB).
- Khẳng định độc lập đáng giá duy nhất (đụng chạm đến 计 hoạch division của mình): **phim 44b6 đầu bảng gần như không có GT division nào** (0113de3b: 0 pos; 0b24845f: 0 pos; chỉ 12dfb391 [phim train, không phải test] có 1) — nhất quán với census "hidden ≈ 2–3 GT division" (alfonso V50) và với việc funnel validator mình (12 GT/8 stem) đến từ các stem 6bba/44b6-khác.

## 4. Verdict cho v12

**BỎ.** Không có gì port được về thuật toán (feature trùng XGBoost kernel, model không được đánh giá trên dữ liệu có signal). Template đáng giữ nếu sau này muốn zero-shot baseline cho DivNet: manifest{features, calibration affine, checkpoint_sha256} + leave-outer-movie-out — nhưng khi đó dùng đúng mining của XGBoost kernel (597 GEFF/302 pos) chứ không dùng bản 8 phim này.
