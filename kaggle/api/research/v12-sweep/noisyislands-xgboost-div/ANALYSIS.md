# ANALYSIS — noisyislands/biohub-xgboost-division-events (XGBoost Division Events)

**Task ID:** 5-b · **Ngày:** 20/9 · **Loại:** KERNEL TRAINING (không phải submission — không đụng test, không sinh submission.csv)
**Nguồn:** /home/z/v11-recovery/research/noisyislands-xgboost-div/biohub-xgboost-division-events.py (474 dòng, script kernel) + output pull 20/9 (log + diag.json + xgboost35_full/{xgboost.json, manifest.json, context.json}).
**Chủ:** noisyislands — 3 kernel public toàn bộ đều là training-infra (Sep 19), chưa có kernel submission nào tích hợp; LB best 0.947 (từ stack khác, không phải từ model này).

## 1. Xgboost Division Events là gì

GBDT ranker phân loại sự kiện phân bào, train trên GT-only features, theo "plan §5A" của repo private họ. Mục tiêu khai báo: model artifact `xgboost35_full/` cho local inference (mirror `scripts/mine_xgboost_context.py`).

### Feature set (13 cột, cố định, trỏ khớp `artifacts/tabpfn35/manifest.json`)
```
daughter_separation_per_frame_um, is_first_frame, is_last_frame, local_density,
n_frames_after, n_frames_before, parent_daughter_dist_absdiff_um,
parent_daughter_dist_max_um, parent_daughter_dist_sum_um, parent_daughter_dist_um,
parent_velocity_um, sister_dist_um, sister_symmetry
```
- Voxel (1.625, 0.40625, 0.40625) — đúng chuẩn thi.
- **GT-only mode ⇒ `local_density` và `parent_velocity_um` = NaN toàn bộ** (2/13 feature chết).
- `sister_symmetry = 1 − |d_pa−d_pb|/(d_pa+d_pb)` — cùng công thức gate τ của mình (chỉ inverse).

### Nhãn (mining)
- **+1** = GT fork: parent có ≥2 con cùng frame (lấy đúng 2 con đầu `children[0], children[1]`).
- **0** = hard negative tổng hợp: parent 1-con + 1 node ngẫu nhiên cùng frame (không phải con) → giả-fork. `--neg-per-fork 40`, cap tổng `--max-neg-total 10000`.
- Không có nhãn −1 ở kernel này (chỉ TabPFN notebook có khái niệm unannotated).

### Hyperparams + runtime
- 200 rounds, depth 4, lr 0.05, subsample 0.8, colsample_bytree 0.9, min_child_weight 3, `scale_pos_weight = n_neg/n_pos`, objective binary:logistic, eval AUC.
- **Chạy thật (log pull 20/9):** 597 GEFF discovery (199 `.geff` + 398 zarr-dir) → **398 node-rich** → **302 fork positive**; negatives thô 2.426.374 → cap 10.000; train xong trong **0.2 s**; in-sample P(1) pos 0.9963 / neg 0.0035, acc 0.9974; model sha `a662314158f2ee69…`.

## 2. Đánh giá nghiêm túc

- **Không có hold-out/CV:** tham số `--fold` tồn tại nhưng không dùng — train + đánh giá trên cùng 1 tập (acc 0.9974 vô nghĩa, chỉ nói model fit được 302 điểm).
- **Không threshold, không tích hợp:** không có bước inference vào pipeline, không receipt điểm nào dùng model này. Rank-ethos giống DivNet của mình (rank-only W=15µm) nhưng dừng ở artifact.
- **Feature nghèo hơn mình:** DivNet mình (UNet 3D lags −1..+2) nhìn ảnh quanh fork; 13 feature hình học thuần ở đây là tập con + 2 feature NaN. Không có gì mình thiếu.
- Hạn chế data thật: GT train thưa — chỉ 302 fork trên 398 phim (~0.76/phim); lớp cân bằng lại bằng 10k neg tổng hợp từ cùng phân bố đó ⇒ nguy cơ học "phân biệt fork-thật vs fork-giả-ngẫu-nhiên" (easy shortcut: neg ngẫu nhiên xa parent) thay vì phân biệt fork-thật vs near-duplicate-split — đúng loại FP mình cần giết.

## 3. Receipt đáng giữ (duy nhất)

- **Census GT division toàn train:** 597 GEFF / 398 node-rich / **302 GT fork**. Đối chiếu: validator mình 12 GT division trên 8 stem; hidden ≈2–3 GT division (receipt alfonso V50). Không mâu thuẫn — 302 là toàn bộ 398 phim.
- Cơ chế discovery GEFF (glob `.geff` + zarr-dir, skip edge-only) — chính là pattern v11-lab của mình đã tự có.

## 4. Verdict cho v12

**BỎ** (không port gì): không tích hợp, không đánh giá hold-out, feature ≤ DivNet mình, negative mining tạo shortcut. Giữ duy nhất census 302 fork + thiết kế "hard negative = parent 1-con + node cùng frame" nếu cần baseline GBDT so DivNet trong v12-lab (chi phí 0.2 s/train — nếu muốn A/B learned-gate vs gate hình học hiện tại thì đây là khung rẻ nhất, nhưng kỳ vọng thấp vì 2 feature NaN + 302 điểm).
