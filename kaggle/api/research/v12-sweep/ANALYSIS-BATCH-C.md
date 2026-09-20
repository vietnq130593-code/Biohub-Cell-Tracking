# ANALYSIS — BATCH C (11 notebook sweep rộng, v12 research)

**Task ID:** 5-c · **Ngày:** 20/9 · **Mục tiêu:** gắn nhãn PORT / THEO DÕI / BỎ cho 11 notebook còn lại, quy đổi cho kiến trúc v12 (mục tiêu ≥0.948, mình đang 0.947).
**Nguồn:** /home/z/v11-recovery/research/<tên>/ · **Tham chiếu stack mình:** ver-10/cell-monolith.py (đã verify trực tiếp các knob: DET 0.965, tight 5.5 + per-prefix {44b6:5.5, 6bba:6.5}, SAFE_DIV 9/14/2.25/τ0.6/mutualNN, DC 0.20, bidir 0.15, SEF_TTA=1 w0.75, LINEFIT w0.8 win2, ILP div 1.2, min len 6, **ADAPTIVE_SHORT_TRACK_RESCUE=1 params identical 0.88/3.0/1.2%/120**).

> evgendvorkin đã có batch A riêng — BỎ qua theo chỉ thị. Tổng 10 notebook phân tích.

## Bảng tổng hợp

| # | Notebook | Kiến trúc (1 câu) | Delta chính vs stack mình | Nhãn |
|---|---|---|---|---|
| 1 | **howonkang-short5** "0947 short5 prepp r1" | Fork harmonic_v3 (0.939 base) + 3 lớp: SHORT5 raw-clean, short-rescue, PP sweep margin-rule | SHORT5_PREPP = xóa component ≤5 node (undirected) trên raw geff TRƯỚC post-chain — lớp duy nhất mình chưa có; title claim 0.947 | **PORT (A/B khô CPU)** |
| 2 | **yongjilyu-sp402** | Baseline support-pack 402ep + ILP, DET 0.99, không post-chain | Không có gì mình thiếu; DET 0.99 ngược hướng cả cụm | **BỎ** |
| 3 | **newwang12-v1-grouped** (12 votes) | Base ver-8-family + hạ tầng packet-grouping (4 feature đo từ test zarr → severity low/mid/high → 65 param/group; v1 override trống) + minlen4 + R3 zero-prob purge | Grouping infra (mình chỉ có per-prefix tight); R3: bỏ candidate learned_prob==0 khỏi Hungarian motion relink | **THEO DÕI** (+2 patch nhẹ A/B được) |
| 4 | **fabriciodasilva-dodecatiad** | Classical DoG multi-scale + Hungarian + gap-interpolation, không ML, không division | Không gì port được; xác nhận GT edges dt=1 | **BỎ** |
| 5 | **ayodeji-det96625** (V929) | V909 core (public 0.915) + 1 knob: DET 0.9671875→0.96625; V33 harness SHA-chain | Receipt trục DET micro-step (plateau ~0.965-0.9675); base khác basin | **THEO DÕI** |
| 6 | **ayodeji-bidir35** (V928) | V909 core + 1 knob: bidir 0.30→0.35 (DET giữ 0.9671875) | Receipt trục bidir vùng 0.30-0.35 tồn tại ở family 0.915; diff vs det96625 = A/B đơn biến sạch nhất batch | **THEO DÕI** |
| 7 | **gautiermarti-dc-training** | KHÔNG phải training — preset v29 0.945 (DC_SAFE_DIV 0.26, veto safe-div OFF) + docs Nga đầy đủ lộ trình 0.808→0.945 | Kho receipt LB 10 phiên bản + lineage map 6 public kernel + GT div geometry | **THEO DÕI (receipts)** |
| 8 | **ghazaros-dae017** | "0.946 floor" riêng họ (bonus 1.35, velocity 0.75, bidir 0.30, không edge-TTA) + DAE denoise prefilter α=0.17 | DAE: Conv3d 4-tầng tự học 30 bước/video, `imgs += α(denoised−imgs)` trước detector; α=0.20→0.938; receipt kimi-v18: DIVERGE 4.0-4.5 peak | **THEO DÕI** (DAE + backlog DIVERGE) |
| 9 | **arnav170-reid3** | Base harmonic_v3 + hệ RE-ID: descriptor 28 chiều thủ công + GBDT (leave-one-volume-out) → `cost -= w×p` trong motion relink | Cơ chế association-appearance hoàn toàn mới; tự đào tạo trên GT validator; sweep w4/8/12 | **THEO DÕI (kỹ thuật)** |
| 10 | **mtoshidesu-lf-dctta** (36 votes) | Bản GỐC public của family: lf + DC TTA 0.20 + **SEF_TTA_WEIGHT=1.0**; kèm 10 nhận xét kỹ thuật của người copy | **SEF_TTA w=1.0 vs mình 0.75** — điểm A/B trực tiếp cho trục E-7; mutualNN 1 chiều; ILP edges bị relink thay | **THEO DÕI (mạnh — knob intel)** |
| 11 | evgendvorkin | — | đã batch A | (skip) |

## Mọi receipt điểm tìm được trong batch C

**Trực tiếp (có trong notebook/folder):**
1. gautiermarti bảng LB: v10 0.923 → v11 0.927 → v15 0.928 → **v16 0.930 (BIDIR 0.30→0.15 +0.002)** → v17 0.931 → v20 0.933 (SEC_DET 0.80) → v22 0.930 (SEC_DET 0.85 tệ hơn) → v27 0.934 → **v28 0.942 (div geometry 9/14 + τ0.6 + DC epoch2)** → **v29 0.945 (EDGE_FEATURE_TTA + tight 5.5 + DC_SAFE_DIV 0.26)** → v30 (mục tiêu 0.948, chưa có)
2. gautiermarti (huristic era): v2 0.808 → v6 0.860 (trần classical)
3. ghazaros: floor **0.946** tự nhận (DAE α=0.15); **α=0.20 → 0.938**; comment "sdm9 alone scored LB 0.939"; comment "kimi-v18 LB sweep DIVERGE_UM peaked ~4.0-4.5" (mình/ghazaros đang 2.25)
4. ayodeji: parent **V909 public 0.915** (submission_ref 56182642, CSV SHA 9f1fc6…); V928/V929 status "candidate_unverified_quality" — không điểm
5. mtoshidesu (validator receipt, không LB): base proxy 0.9490 (adjEJ 0.9260, divJ 0.2308) → sweep chọn tight55 0.9511 (+0.0021)
6. howonkang: title claim 0.947 trên base 0.939 — tự nhận, không kiểm chứng

**Gián tiếp (docs gautiermarti trích từ public kernels):**
7. rogerrogerroger3r/biohub-run79 (LB 0.944): EDGE_FEATURE_TTA → edge-J trên 44b6_12dfb391: 0.9115→0.9256 (+0.014), nodes 42700→45004
8. redoctopusk/biohub-942tta (LB 0.946): PPSWEEP chọn tight55, proxy +0.0021, adjEJ +0.0021, divJ giữ 0.2308
9. rishabhr0y 0.938 / kunaldesale2408 0.940 / analyticaobscura 0.942 (validator N=8 + DC 0.25)
10. **GT division geometry (từ biohub-div45-stack):** sister separation median 10.4µm / p90 13.0 / max 13.7; parent-daughter max 10.4 → xác nhận SAFE_DIV 9/14 đúng khung

## 3 phát hiện đáng chú ý nhất

1. **SEF_TTA w=1.0 vs w=0.75 (mtoshidesu):** kernel gốc 36-vote của cả family chạy SECONDARY_EDGE_FEATURE_TTA_WEIGHT=**1.0** (thay toàn bộ feature secondary bằng trung bình TTA) — docstring "three-quarter-strength" là STALE (nhận xét #10 của người copy); howonkang (fork) mới đặt 0.75 giống mình. Vì E-7 đã nghi ngờ w0.75 làm tụt keep-rate association trên 0b24 (67.5% vs 71.2% V1329 không-SEF), đây là điểm đối chiếu tự nhiên: **A/B v12-lab SEF_TTA ∈ {0.75, 1.0, OFF}** — mọi knob khác của mtoshidesu ~trùng mình.
2. **Family-level convergence ngạc nhiên:** ADAPTIVE_SHORT_TRACK_RESCUE (params byte-identical 0.88/3.0/1.2%/120) có trong TẤT CẢ 7 notebook thuộc dòng harmonic_v3 — và cũng đã có trong ver-10 mình; nghĩa là cụm 0.939→0.947 chia sẻ di sản chung gần như nguyên vẹn, khác biệt nằm ở: HOCT/reparent/density-guard (mình hơn), SHORT5_PREPP (howonkang hơn), grouping infra (newwang12), REID (arnav), DAE (ghazaros).
3. **Receipt bidir khép trục:** gautiermarti v15→v16 (LB +0.002 khi hạ 0.30→0.15) + ayodeji probe 0.30→0.35 trên base 0.915 (không cải thiện được kiểm chứng) → bidir 0.15 của mình được 2 nguồn độc lập bao vây; KHÔNG mở trục này ở v12. Ngược lại DIVERGE_UM có receipt ngược (kimi-v18 peak 4.0-4.5 vs mình 2.25) → backlog A/B khô.

## Hành động đề xuất cho v12 (xếp theo chi phí/tác động)
1. **A/B SEF_TTA {0.75 → 1.0}** trên v10 output (E-7 axis, receipt mtoshidesu) — CPU/1 lượt GPU.
2. **A/B SHORT5_PREPP** port ~50 dòng lên trước post-chain (receipt claim 0.947-howonkang, không verify) — CPU khô trên cache geff.
3. **Backlog khô:** DIVERGE_UM {2.25 → 4.0} (receipt kimi-v18), R3 zero-prob purge (1 dòng), minlen4 + DC 0.25 (delta newwang12/alfonso convergence).
4. **Không làm:** bidir (khép), DET micro-step (plateau, khác basin), grouping infra (effort quá lớn cho deadline 29/9), DAE (trục detection — E-7 nói gap mình ở association), REID (blueprint giữ cho v12-lab nếu mở trục association sau SEF_TTA).

*Chi tiết từng notebook: `<tên>/ANALYSIS.md` cùng thư mục.*
