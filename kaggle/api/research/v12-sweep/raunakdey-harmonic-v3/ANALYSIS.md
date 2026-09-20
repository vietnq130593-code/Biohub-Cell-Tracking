# ANALYSIS — raunakdey "Biohub: Harmonic Fusion V3" (80 votes — phổ biến nhất cụm 0.948)

## 0. Metadata
- **Nguồn:** `/home/z/v11-recovery/research/raunakdey-harmonic-v3/biohub-harmonic-fusion-v3.ipynb` (13 cells, 225KB, không monolith).
- **Output KHÔNG pull được** (`kernels output` → permission denied — slug đúng nhưng có thể private output/benchmark slug khác). Mọi kết luận từ source notebook.
- **Định vị:** đây chính là bản **"harmonic_v3_division_wide" GỐC** của cụm — haideptry là fork trực tiếp của nó (diff 4 cell chung: cell07/dep IDENTICAL, imports/inference/audit chỉ chêm vài dòng — đã verify bằng diff). Preset: `BIOHUB_PRESET='harmonic_v3_division_wide'`, score axis "public 0.939 base + **holdout-selected post-process configuration**".
- 80 votes = notebook "trung tâm dân cư" của cụm 0.939-0.947: ai fork cũng đi qua đây.

## 1. Kiến trúc (1 câu)
Bản chuẩn hóa đầy đủ nhất của dòng public: dual-seed harmonic fusion (primary+secondary + low_margin_consensus 0.20/0.80/0.35 + 8-view TTA + EDGE_FEATURE_TTA + SEF_TTA w0.75 + DC TTA) + ILP + post-chain đầy đủ + **validator holdout chọnDivision-aware + PP sweep 7 candidate tự chọn config + re-write submission** — tất cả trong 1 kernel "self-tuning".

Env knobs: IDENTICAL haideptry trừ phần haideptry thêm (không có DivNet, không density-group, không speed pack, MOTION_RELINK_TIGHT_UM default 6.0 — không set 5.5!). So với mình: chỉ chênh DC_SAFE_DIV 0.25 (vs 0.20) — còn lại trùng.

## 2. Kỹ thuật đáng giá cho v12

### 2.1 ★★★ In-kernel PP SWEEP với selection rule + combo re-test (cell10+11)
- `PP_CANDIDATES` = 7 biến thể đơn: gap45 (GAP_CLOSE 4.5), tight55 (5.5), relaxed9 (9.0), bonus125 (1.25), gap2step40 (4.0), reuse28 (2.8), dcgap035 (0.35).
- Cơ chế `pp_apply/pp_restore`: patch `globals()[key]` của 21 hằng số post-process (PP_SWEEP_KEYS whitelist), re-run toàn bộ post-chain trên **raw graph cache** (VAL_RAW_GRAPHS load 1 lần), chấm điểm validator mỗi variant — không chạy lại inference.
- **Selection rule (phần đáng học nhất):** một candidate được tính "positive" nếu `proxy ≥ base + 0.0005` VÀ `adjusted_edge_jaccard ≥ base − 0.0005` (không hy sinh edge axis quá 0.0005). Positive ≥2 → tạo **combo** (gộp override) và re-test combo. Cuối cùng chỉ chấp nhận nếu `proxy ≥ base + PP_SELECT_MARGIN (0.001)`; ngược lại giữ base. Ghi `ppsweep_selected.json` + `ppsweep_results.csv` receipt.
- **Ý nghĩa với mình:** mình đang A/B thủ công từng knob bằng LB/lab; pattern này cho phép A/B 7 knob + combo trong 1 kernel CPU-only trên cache geff. Tương thích trực tiếp với hạ tầng v11-lab (đã có dump rawgraphs + probe 2 layout). Đây là "iteration multiplier" rẻ nhất chưa có.

### 2.2 ★★ Validator division-aware selection (cell08, có cả trong evgendvorkin)
Chọn N-per-type holdout movie ƯU TIÊN phim có GT division (computed per-video qua out-degree ≥2, không hardcode). evgendvorkin ghi chú census: **GT division chỉ được annotate trong ~44% video train** → selection ngẫu nhiên dễ ra val-set không đo được divJ. Mình đã biết tương đương (12 GT val), nhưng việc code selection theo flag division là 15 dòng đáng có trong mọi validator.

### 2.3 ★★ Offline metric implementation đầy đủ + error decomposition (cell09)
- Bipartite 7µm/frame matching + edge TP/FP/FN + adjusted (α=0.1, dùng `estimated_number_of_nodes`) + division confusion component-based + **`decompose_errors`**: missed_gt_nodes / spurious / edges_recovered / edges_fragmented / edges_lost_to_detection / wrong_association_edges — đúng bộ phân rã lỗi mà lượt 3-4 mình đã tự xây cho alfonso analysis. Khớp ~99% logic validator mình đang có (không cần port, xác nhận thiết kế).
- **CẢNH BÁO QUAN TRỌNG (từ megayak notes, repo 0948-research):** division confusion kiểu component-reachability này **đọc divJ ≈ GẤP ĐÔI official** (0.25 vs 0.125 trên cùng prediction) — rule đã bị organizers patch 17/7 (commit aa65e90). Validator của mình phải chạy `division_metrics.py` post-patch làm trọng tài divJ, không dùng bản component-based này.

### 2.4 ★ Thứ tự pipeline + guard format (cell12)
Assert cuối: edge t+1, in-degree ≤1, out-degree ≤2, dataset coverage, id contiguous — trùng bộ DAG-assert của mình (đã có).

## 3. Claim điểm + bằng chứng
- Không claim trực tiếp trong notebook; benchmark table của haideptry gán họ vào band "0.939-0.946". Env của notebook này khớp V29-V30-era của evgendvorkin (0.945-0.947 territory) + tight 6.0 (chưa 5.5) → có lẽ ~0.945. Không receipt (output không pull được).
- Delta so với "bản public gốc 0.947 Reyhan Ksatria" mình đã port: raykkretzschmar-lineage thay vì reyhanksatria — về bản chất cùng chất liệu (checkpoints giống hệt), khác ở chỗ này KHÔNG có per-movie override nào; các giá trị tight 6.0/relaxed 10.0/bonus 1.0 = family defaults.

## 4. Nguy cơ
1. PP sweep dùng validator component-based → có thể chọn sai config theo trục divJ "compass reads double" (đã có bằng chứng megayak). Nếu port pattern này, phải thay scoring bằng official division_metrics.py post-patch + trục adjEJ ưu tiên.
2. Sweep chạy 8 phim holdout prediction = ~90 phút GPU thêm nếu VALIDATOR_ENABLE=1 (đó là lý do haideptry tắt). Với mình: chỉ port phần sweep-on-cache (CPU), không port phần predict-val.

## 5. Verdict cho v12
**PORT (pattern, không port code nguyên văn):** pp_apply/pp_restore + 7-candidate sweep + margin-rule + combo-retest — gắn vào v11-lab trên cache geff, chấm bằng official patched metric. **Đã có, xác nhận:** validator + decomposition + division-aware val selection. **Cảnh báo:** divJ component-based = 2x official — không dùng làm trọng tài. Notebook này không có delta scoring nào mình thiếu; giá trị là hạ tầng self-tuning.
