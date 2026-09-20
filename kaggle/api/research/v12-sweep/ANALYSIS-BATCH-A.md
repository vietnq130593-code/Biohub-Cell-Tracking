# ANALYSIS — BATCH A (4 notebook đỉnh cụm: haideptry 0.948+, raunakdey HF-V3, codezzzsleep 0.95, evgendvorkin proxy)

**Task ID:** 5-a · **Ngày:** 20/9 · **Mục tiêu:** tìm kỹ thuật/value cho kiến trúc v12 (≥0.948; mình 0.947).
**Nguồn:** `/home/z/v11-recovery/research/<tên>/` · Output 3/4 kernel đã pull & verify trực tiếp (raunakdey bị denied).
**Tham chiếu stack mình:** ver-8/v3-fast = dual-seed harmonic + ILP + post-chain (DET 0.965, ILP 0.0/2.0/1.2, SAFE_DIV 9/14/2.25/τ0.6/mutualNN, DC 0.20, caps 0.0076/0.00375, tight 5.5 + per-prefix {44b6:5.5, 6bba:6.5}, SEF_TTA w0.75, rescue 0.88/3.0/1.2%/120, HOCT veto-1, reparent Phase D).

## Bối cảnh chung quan trọng (đọc trước)
Cả 4 notebook thuộc **MỘT gia đình** (checkpoints primary/secondary/deepcenter = sha256 byte-identical với nhau VÀ với mình + alfonso): khác biệt chỉ nằm ở lớp config + post-processing. Đó là tin tốt: mọi delta là CPU-port được, không phải "model mới".

## Bảng so sánh 4 notebook

| | haideptry-sota948 | raunakdey-harmonic-v3 | codezzzsleep-095-owned | evgendvorkin-proxy942 |
|---|---|---|---|---|
| Vai trò | Fork harmonic_v3 + density-adaptive + DivNet (no-op) | Bản "harmonic_v3_division_wide" GỐC + PP sweep tự chọn | Baseline mộc 0.913 + **hub/fork augmentation hack** + owned-validation | Tổ tiên dòng public (v2→v31 docs đầy đủ) + proxy scorer |
| Fork count (verify CSV) | 96 | n/a (≈ family defaults) | 0 (clean) / 24 fake | 200 (DC veto OFF) |
| Nodes/edges | 122.821 / 118.541 | ~ | 124.743 / 115.786 (clean) | 122.975 / 118.786 |
| Knob khác mình | DC 0.25; density-group relink 4-knob; tight 5.5 global | DC 0.25 (còn lại trùng) | mọi thứ đều sơ khai | DC 0.26 + veto OFF; gap 5.8 |
| Claim điểm | 0.948+ (LB-tuned, plausible ±0.001-0.002, chưa verify) | 0.939-0.946 (không claim riêng) | **0.95 = đo bằng metric PRE-PATCH, không tái tạo được trên LB** | 0.942 (đáng tin — nguồn gốc dòng public) |
| Runtime thật | 28' (inference 8.9') | ~131' nếu validator ON | ~5.6' | ~35' + val |
| Receipt | submission+run_stats+log full | denied | submission clean+augmented+log | full + validator_results.csv |

## Top-10 kỹ thuật port-able cho v12 (xếp theo giá trị kỳ vọng × chi phí port)

1. **★★★ Local LB-REPLICA validator — chấm submission trên GT của chính 4 phim test lấy từ `train/`** *(nguồn: codezzzsleep §2.1 + evgendvorkin log "excluding 4 TRAIN stems…" + split_manifest)* · chi phí: 1 kernel CPU + 1 lần verify · giá trị: **n +∞ vòng lặp A/B miễn phí** thay 5 subs/ngày; điều kiện tiên quyết cho mọi thử nghiệm dưới. Bước verify bắt buộc: chấm submission ver-8 (LB 0.947 đã biết) — nếu replica trả 0.947±0.002 (dùng division_metrics post-patch) thì khóa tin cậy. Lượt 5 mới đo 1/4 phim (05db adjEJ 0.8551) — cần 3 phim còn lại.
2. **★★★ Density-Adaptive Group Overrides cho motion relink** *(haideptry §3.1)* · ~40 dòng, A/B khô trên cache v10 · kỳ vọng +0.001~0.003 · LOW(05b6850b): tight 7.25/relaxed 11.0/bonus 3.0/vel 0.5; MID(2 phim 44b6): 6.5/9.0/6.0/0.0; HIGH(05db0fb1): 5.5/10.0/1.0/0.5 · phân nhóm theo density (avg node/frame <120/<400/else) — khớp và mở rộng hướng per-prefix tight của mình (tách LOW vs HIGH mà mình đang gộp). Lưu ý: giá trị LB-tuned của lineage raykkretzschmar → verify bằng LB-replica trước.
3. **★★ DC_SAFE_DIV 0.20 → 0.25** *(haideptry + alfonso + evgendvorkin 0.26 + newwang12 batch C — hội tụ lần 4)* · 1 env knob · đưa funnel DC về ~213 (vs 317 của mình), fork 188→~96-127 · kỳ vọng ±0.001-0.002 (dấu cần đo, không đoán).
4. **★★ PP-sweep pattern: pp_apply/pp_restore + 7 candidate + margin-rule + combo-retest trên cache graph** *(raunakdey §2.1)* · ~150 dòng vào v11-lab · biến 7 knob thành 1 buổi CPU · PHẢI thay scoring divJ component-based bằng official post-patch (xem cảnh báo).
5. **★★ A/B SEF_TTA {0.75 → 1.0 → OFF}** *(evgendvorkin + mtoshidesu batch C: kernel gốc dùng w=1.0; E-7 nghi vấn keep-rate 0b24)* · 1 knob trên cache · trục association = kẽ hở keep-rate lớn nhất của mình (67.5% vs 71.2% V1329).
6. **★ Under-prediction adjEJ bonus (trục nghịch lý)** *(evgendvorkin §3.3 — receipt 44b6_12dfb391: adj 0.9471 vs edgeJ 0.9256 do t_pred < t_true)* · đo trong LB-replica hệ node-budget ↔ DET threshold trước khi đụng: nếu t_true(hidden) > t_pred mình ~5% thì đang bỏ ~+0.005 trên bàn.
7. **★ Direct-path I/O (bỏ FUSE glob) + CUDNN wscap + batch 8** *(haideptry §3.4)* · inference 9'/2×T4 — cho phép nhét validator + sweep vào cùng kernel production nếu cần; trùng fix v11-fix-r4 (xác nhận đúng).
8. **★ Division-aware val selection (flag GT-division khi chọn holdout)** *(raunakdey/evgendvorkin §2.2)* · 15 dòng · GT division chỉ có trong ~44% phim train — chống val-set mù divJ.
9. **★ (âm) DivNet verify gate p≥0.50 = NO-OP** *(haideptry §3.2 — receipt: 0 veto trong run 0.948, cột divnet_vetoed_divisions không tồn tại)* · tiết kiệm effort: đừng port cổng này; nếu sau này làm veto học: fail-closed + đếm rõ.
10. **★ (âm) Hub+fork augmentation hack = ĐÃ CHẾT** *(codezzzsleep §2.2 + megayak notes: patch aa65e90 ngày 17/7, rule local "fork phải là immediate successor")* · KHÔNG port; submission kiểu này giờ ÂM ~0.02-0.03 trên LB (4.145 fake edge → FP). Chỉ giữ bài học cơ chế division metric.

## Cảnh báo tổng hợp (đọc kỹ trước khi hành động)
1. **Validator divJ component-based đọc GẤP ĐÔI official** (megayak receipt 0.25 vs 0.125; cả raunakdey cell09, evgendvorkin validator, và mọi "PP sweep chọn tight55 +0.0021" trong họ đều dùng thước này). Mọi A/B divJ phải dùng `division_metrics.py` post-patch (rule local). Không có cái đó thì chỉ tin adjEJ.
2. **GT train thưa ~6% + hidden GT ~2-3 division** → divJ gần như KHÔNG nhạy với fork count trong vùng 92-200 (receipt chéo: 200 fork→0.942, 188→0.947, 96→0.948?, 2→0.946). Trục EDGE vẫn là trận chiến thật — khớp kết luận lượt 4-5 worklog.
3. **Per-movie override (density-group) là LB-tuned trên đúng 4 phim test** → gain LB thật nhưng rủi ro không transfer private; đánh đổi này phải là quyết định có ý thức (mục tiêu huy chương = private cuối).
4. Con số tự nhận của haideptry (0.948+) chưa từng được LB kiểm chứng — coi như "plausible"; codezzzsleep (0.95) gần như chắc chắn là fossil pre-patch.
5. Số liệu census đã verify lại bằng Counter trực tiếp trên CSV (bản đầu đếm bằng pandas value_counts sai 2x — cẩn thận khi tự đếm fork).

## Hành động đề xuất ngay cho v12 (thứ tự)
1. Dựng LB-replica: kéo GT 4 test stems (train/) + official metrics post-patch → chấm ver-8 (0.947) + v10 (đang PENDING) → khóa tin cậy. (CPU-only, không tốn quota.)
2. Trên replica: A/B DC 0.25 → density-group relink → SEF_TTA {0.75/1.0/OFF} (2 ngày CPU).
3. Port pp-sweep pattern vào v11-lab cho các knob còn lại (relaxed_um, bonus, gap 5.0-5.8, reuse, gap2step).
4. KHÔNG đụng: hack augmentation, DivNet gate, bidir (đã khép trục batch C), DET micro-step.

*Chi tiết từng notebook: `<tên>/ANALYSIS.md` cùng thư mục. Song song: ANALYSIS-BATCH-C.md (11 notebook khác).*
