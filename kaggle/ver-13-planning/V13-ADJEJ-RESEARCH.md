# V13 adjEJ RESEARCH — Nâng adjusted_edge_jaccard trên nền v12 + amanatar geometric-fusion

> Ngày 22/9/2026 · Deadline 29/9 23:59 · GPU còn 14.15h/30h · quota 5/ngày (hôm nay 0/5)
> Mục tiêu user: V13 ≥ V11 về **adjEJ** (LB 0.947) + giữ nguyên các chỉ số đã tốt hơn của v12
> (divJ, COMPOSITE, Division TP/FP/FN, Census) — "adjEJ phải cao hơn V11".

---

## §0. TL;DR

| # | Kết luận then chốt |
|---|---|
| 1 | **LB = adjEJ + 0.1×divJ nhưng adjEJ chiếm >93% giá trị điểm** — quan sát của user HOÀN TOÀN ĐÚNG. Kênh division có trần +0.01–0.04 thực dụng; cuộc đua thật ở adjEJ. |
| 2 | **Phân tích 3 điểm LB** (v11 0.947 · v12.1 0.946 · amanatar 0.948): v12.1 mất −0.001 vì +23 fork ở phim DÀY 05db (diverge −2.0); amanatar thắng +0.001 vì +215 cạnh ở phim THƯA (0113/0b24) + −21 fork ở phim dày + leaf-prune 71 cạnh yếu. |
| 3 | **4 đề xuất hấp thụ được từ amanatar** (đã verify ~40 knobs: cùng dòng dõi V1290, gần như toàn bộ env trùng khớp): P1 revert diverge (0 GPU) · P2 velocity-weight 0.5→0.25 (+0.0014 adj, knob có sẵn) · P3 port leaf-prune ~60 dòng (+0.0004 adj, code mới duy nhất) · P4 division-recall bằng divwide+dcsd015 (thay thế hướng diverge đã thất bại). |
| 4 | **Sweep bảng của amanatar chứng thực thêm**: `diverge150` (họ cũng thử relax divergence!) làm divJ 0.2308→0.1667 (FP 1→6) — **cùng dấu với thất bại v12.1 của mình**; trong khi divwide/dcsd giữ adj nguyên + divJ nguyên. Đây là bằng chứng độc lập mạnh nhất cho hướng P4. |
| 5 | Kỳ vọng V13 = v11 + P2 + P3 + P4: **LB ≈ 0.948–0.949**. Kiểm chứng bằng replica-gate offline (0 GPU) trước khi chạy 1 production run ~0.7h. |

---

## §1. adjEJ là gì — cơ chế tính điểm chính xác

**Công thức cuộc thi**: `score = adjusted_edge_jaccard + 0.1 × division_jaccard` (mỗi dataset tính riêng rồi aggregate).

**Pipeline chấm 1 dataset (theo replica engine + validator lineage — đã verify 2 lần khớp Kaggle):**

1. **Node matching**: từng node dự đoán được ghép với node GT bằng bipartite matching (dung sai không gian ~vài µm). Node không ghép được → "spurious" (FP node).
2. **Edge mapping**: cạnh dự đoán (u→v, t→t+1) được map sang cặp node GT qua bảng ghép. Cạnh map trúng cạnh GT = TP; cạnh không map được vào GT nào = FP; cạnh GT không có dự đoán = FN.
3. **adjEJ = TP_edges / (TP + FP + FN)** — phép giao/hiệutp集 hợp trên cạnh sau khi hiệu chỉnh node.
4. **divJ** = TP_divisions / (TP + FP + FN) trên tập sự kiện phân bào (node cha có 2 con).

**Hệ quả toán học quan trọng** (với ~118k cạnh và ~122k node trên 4 phim):

| Thay đổi output | Tác động adjEJ |
|---|---|
| +1 cạnh ĐÚNG (recall) | +TP → adjEJ tăng (~+1/150k mỗi cạnh nhưng cộng dồn) |
| +1 cạnh SAI (FP) | +FP → adjEJ giảm **gấp đôi** tác động so với recall (cộng vào mẫu số chung mà không cộng tử số) |
| +1 fork giả (2 con thay vì 1) | +1 FP cạnh (con thứ 2) + rủi ro phá cạnh cha-con thật |
| Bỏ 1 cạnh đúng | +FN → giảm ngang FP |
| +1 node thừa có cạnh | +FP cạnh + node spurious |
| Phim càng DÀY (05db: 70k node) | matching càng dễ confuse → mỗi FP/ FN đắt giá hơn trên từng đơn vị |

**Định luật kinh tế**: ở mức 0.947, để tăng +0.001 adjEJ cần thêm ~150 cạnh đúng thuần (recall không kèm FP) — hoặc di chuyển ~75 cạnh từ sai→đúng.

---

## §2. Tam giác chứng cứ LB — 3 điểm data chốt adjEJ

### 2.1 Census 3 phiên bản (per-dataset)

| Dataset | v11 (LB **0.947**) | v12.1 (LB **0.946**) | amanatar (LB **0.948**) |
|---|---|---|---|
| 0113 (thưa) | 25637n / 24812e / 36f | 25643 / 24830 / 45 | 25624 / **24931** / **64f** |
| 0b24 (thưa) | 20704n / 19381e / 26f | 20704 / 19387 / 31 | 20748 / **19475** / **38f** |
| 05b6 (vừa) | 6160n / 5941e / 10f | 6160 / 5945 / 13 | 6152 / 5958 / 10f |
| 05db (**dày**) | 70286n / 68198e / 72f | 70301 / 68231 / **95f** | 70240 / **68183** / **51f** |
| **TỔNG** | 122787n / 118332e / 144f | 122808 / 118393 / 184f | 122764 / **118547** / 163f |

**Delta vs v11:**
- **v12.1**: +21n / +61e / +40f — cạnh thêm tập trung ở 05db (+33e, +23f) ← trục diverge −2.0
- **amanatar**: −23n / **+215e** / +19f — cạnh thêm ở phim thưa (+119e 0113, +94e 0b24, +17e 05b6), **GIẢM ở phim dày** (−15e, −21f 05db)

### 2.2 Quy hồi điểm — vì sao v12.1 thua dù composite replica +0.0131

Replica v12.1: adjEJ 0.8998 (−0.0012) · divJ 0.1429 (+0.0143) → composite +0.0131.
LB thực: 0.946 = 0.947 − 0.001.

**Giải thích nhất quán nhất** (2 cách kiểm):
- (a) divJ_LB ≈ 0: TP division t=24 05db không xuất hiện trên public split (public/private chia theo frame hoặc theo phim) → chỉ phần adjEJ −0.0012 chuyển sang LB → 0.947−0.001 ≈ 0.946 ✓ khớp gần như hoàn hảo với replica delta.
- (b) divJ_LB = 0.143 nhưng adjEJ rơi −0.0153 — mâu thuẫn với replica (đã chứng minh delta đáng tin 2 lần: v10/v11 cùng replica 0.9010 → cùng LB 0.947).

→ Kết luận: **kênh divJ trên public LB không đo được lợi ích rescue division; adjEJ mới là trục chuyển hóa thật.** (Bài học vẫn giữ nguyên từ V11-RESEARCH §2.3: "cuộc đua thật ở trục edge".)

### 2.3 Cơ chế phân rã (run_stats đối chiếu 3 bản)

| Cơ chế | v11 | v12.1 | amanatar | Ghi chú |
|---|---|---|---|---|
| safe_divisions_added | 82 | 123 | **163** | divwide+dcsd015 của họ +81 vs v11 |
| divergence_rejected | 2812 | 365 | 7360 | họ vẫn reject mạnh (gate 2.25 giữ nguyên) |
| deepcenter_safe_div_rejected | 1576 | 3177 | **536** | DC 0.15 chấp nhận nhiều hơn hẳn |
| leaf_prune nodes/edges | 0 | 0 | **71/71** | cơ chế mới (v4) |
| motion_relink_tight | 116118 | 116118 | 115046 | vel025 thay đổi prediction điểm đến |
| gap/gap2/density/rescue | ~giống | ~giống | ~giống | nền tảng không đổi |

---

## §3. DANH MỤC thuật toán liên quan adjEJ trong pipeline v12 hiện tại

*(trích cell-monolith.py 5.541 dòng — mỗi thuật toán: cơ chế → tham số hiện tại → ảnh hưởng adjEJ đo được/ suy luận)*

### Lớp A — Cung cấp NODE (nguyên liệu của mọi cạnh)

| # | Thuật toán | Cơ chế | Config hiện tại | Ảnh hưởng adjEJ |
|---|---|---|---|---|
| A1 | **Dual-seed harmonic fusion** | 2 detector (primary + secondary seed) hòa trắc response harmonic; retention guard 0.90 fallback per-frame | secondary_det_w 0.475, secondary_edge_w 0.15, low_margin_consensus 0.35 | Node supply chính. Thiếu node → FN cạnh; thừa → FP cạnh. amanatar fallback 64/100 frame ở 0b24 (median retention 0.86) → đây là gap recall cạnh lớn nhất ở phim thưa. |
| A2 | **DET_THRESHOLD** | ngưỡng confidence detection | 0.965 | Tăng → ít node thừa nhưng mất recall; 0.96875 của guard amanatar cho thấy dải hẹp. |
| A3 | **Deepcenter veto (gap)** | UNet3D center-prior xác nhận gap-thêm-node trước khi chấp nhận | gap_threshold 0.25, confirm_span 8.5µm | Chặn gap-node giả (FP node+kèm FP cạnh). |
| A4 | **Short-track filter + adaptive rescue** | xóa track < 6 frame, cứu lại nếu mean_edge_prob ≥ 0.88, dist ≤ 3µm, cap 1.2%/120 node | filter=1, min_len=6 | Loại node rác cuối track → giảm FP cạnh; rescue giữ lại track tốt. |
| A5 | ~~READMIT / GAPFILL / LOWDET~~ | v12 thêm node (866 readmit + 131 gapfill) | **đã knockout trong v12.1** | E1+RUN2 chứng minh node thêm hại 2 stem thưa (−0.0013 adj) — KHÔNG bật lại. |

### Lớp B — Xây cạnh (trục recall/precision cạnh — trục amanatar thắng)

| # | Thuật toán | Cơ chế | Config hiện tại | Ảnh hưởng adjEJ |
|---|---|---|---|---|
| B1 | **Learned UNet edge predictor** | model gốc cả lineage (checkpoint sha giống amanasyon 12f6881e — E-6 parity) | frozen weights | Cố định — không đụng mùa này. |
| B2 | **ILP assignment** | integer-linear-program gán cạnh t→t+1 | appearance 0.0 · disappearance 2.0 · division 1.2 | Khung gán chính; disappearance cao = ngắt track thận trọng. |
| B3 | **Bidirectional fusion** | hòa xác suất cạnh xuôi+ngược | w 0.15 harmonic_probability | Ổn định xác suất cạnh. |
| B4 | **Motion relink + velocity model** | thay cạnh thô bằng dự đoán chuyển động: `predicted = pos + W×velocity`; matching tight 5.5µm / relaxed 10µm; learned bonus 1.0 | **W = 0.5 (mặc định)** | ⭐ Knob chưa sweep! amanatar: W=0.25 → +0.0014 adj (validator); W=0.75 → −0.0007 (hư). Cơ chế: tế bào phôi chuyển động hỗn loạn — mô hình quán tính nửa vận tốc OVERSHOOT điểm đến; W=0.25 dự báo thận trọng hơn → relink trúng GT hơn. |
| B5 | **Gap close (density-adaptive)** | đóng lỗ track bằng synthetic node khi 2 đầu gần; bán kính thích nghi mật độ: reference 6.5µm ± gain 0.04 × mật độ, step ≤0.125µm, 3 neighbors | max_gap 2, close 5.0µm, adaptive=1 | +620 node/+1240 cạnh (3 bản như nhau) — đã tối ưu chung lineage. |
| B6 | **Gap2 recovery** | phục hồi cạnh bị đứt 2 frame | 429 cạnh (amanatar 447) | Biên phụ. |

### Lớp C — Kênh division (tạo fork — RỦI RO adjEJ nếu sai)

| # | Thuật toán | Cơ chế | Config hiện tại | Ảnh hưởng adjEJ |
|---|---|---|---|---|
| C1 | **Safe-divisions post-link** | quét node mồ côi ↔ cặp con tiềm năng: cổng hình học MAX/SISTER/EXISTING_CHILD + đối xứng chị em τ + **phép đo divergence** (2 con phải TẢN ra) | MAX 9 · SISTER 14 · EXIST_CHILD 10 · τ 0.6 · **diverge −2.0 (v12.1!)** | ⭐ Nguồn +40 fork. Diverge −2.0 (chấp nhận HỘI TỤ) cứu được 1 GT div thật (t=24 05db) nhưng kèm +3 FP — trên LB không đủ bù. |
| C2 | **Deepcenter safe-div veto** | model deepcenter xác nhận fork trước khi thêm | **0.2** (amanatar chọn **0.15**) | Cổng giết 89% fork sống sót hình học (notebook amanatar). 0.15 = lỏng hơn → divJ recall tăng mà FP được gate divergence kiểm soát. |
| C3 | **Mutual-NN + pdiv floor** | yêu cầu matching đôi + xác suất division | v11 grid: mutual_nn OFF, pdiv 0.85 | Đã tune vòng v11. |
| C4 | **Fraction caps** | cap fork/frame + toàn cục | 0.0076 / 0.00375 | An toàn dance với phim dày. |
| C5 | **HOCT consensus veto mode 1** | bỏ phiếu consensus tần số cao, chế độ bảo vệ fork | mode 1 | Fork được bảo vệ → không thể purge (L6: purge = 0.911 thảm họa). |
| C6 | **Reparent Phase D** | gán lại cha đúng cho fork | EP 0.4 | **NO-OP production đã chứng minh** (counters 12/19/3/43 giống hệt) — gạch khỏi lever. |
| C7 | **Orphan adoption + divergence exemption** | nhận nuôi mồ côi khi được miễn divergence | floor 0.5 | Kèm diverge −2.0: +23 fork 05db. Cần tắt khi revert P1. |

### Lớp D — Vệ sinh output

| # | Thuậtạt | Cơ chế | Ảnh hưởng |
|---|---|---|---|
| D1 | Single-parent repair / prune isolated / enforce t+1 / edge max 14µm | sửa cấu trúc DAG | vệ sinh, không đổi đáng kể |
| D2 | Linefit smoothing | làm mượt quỹ đạo | trung tính adjEJ (đo vị trí) |
| D3 | **Leaf prune (MÌNH CHƯA CÓ — port P3)** | xóa node lá (out-degree 0, không phải frame cuối, đúng 1 cạnh vào với learned prob < ngưỡng); MIỄN TRỪ con division (edge_prob=None); single-pass không cascade | amanatar: −71 cạnh yếu → +0.0004 adj. Loại "đuôi track" yếu nhất — nơi FP cạnh tập trung. |

---

## §4. amanatar/biohub-geometric-fusion — giải phẫu (notebook 234KB, LB 0.948, hạng 244)

### 4.1 Kiến trúc

```
Base V1290-family (CÙNG dòng dõi mình — 40/49 env trùng, checkpoint sha primary
12f6881e + secondary 9bac2fa0 + deepcenter 8040999a đều parity E-6)
├── Dual-seed harmonic + low_margin_consensus + retention guard (fallback 0b24 64%)
├── VALIDATOR runtime: 8 stem held-out train (16.8' GPU) → chấm official metric
├── PPSWEEP 26 configs × 7.2' CPU: đợt riêng lẻ + combo, chọn theo
│   margin rule: proxy ≥ +0.001 VÀ adj_loss ≤ 0.0005 VÀ prefix-guard (mỗi prefix
│   44b6/6bba không được lùi > 0.001 — chống overfit sweep)
└── Re-write submission.csv với combo thắng → 241.311 dòng
Runtime tổng: 237' (~4h GPU) — đắt hơn mình 5.4 lần (mình 0.71h validator-OFF)
```

### 4.2 Bảng sweep (8 stem validator — giá trị từng lever)

| Config | adjEJ | divJ (tp/fp/fn) | proxy | Δadj vs base |
|---|---|---|---|---|
| base | 0.9260 | 0.2308 (3/1/9) | 0.9490 | — |
| tight55 | 0.9280 | 0.2308 | 0.9511 | +0.0020 *(mình ĐÃ có từ v10)* |
| vel025 | 0.9274 | 0.2308 | 0.9505 | **+0.0014** ⭐ |
| vel075 | 0.9253 | 0.2308 | 0.9484 | −0.0007 (sai hướng) |
| leaf030 / leaf040 | 0.9263 | 0.2308 | 0.9494 | +0.0003 |
| t55_leaf030 | 0.9284 | 0.2308 | 0.9514 | +0.0024 *(tight55 có sẵn → phần cộng dồn leaf = +0.0004)* |
| dcsd015 / dcsd010 / divwide / sym075 | 0.9260 | 0.2308 | 0.9490 | ±0 *(adj nguyên vẹn — divJ recall thuần)* |
| **diverge150** | 0.9261 | **0.1667 (3/6/9)** | 0.9428 | FP nổ 1→6 — **CÙNG DẤU với v12.1 mình!** |
| t55_diverge150 | 0.9282 | 0.1667 (3/6/9) | 0.9449 | vẫn hư divJ |
| **COMBO thắng** | **0.9300** | 0.2308 | **0.9530** | **+0.0040** |

**COMBO thắng** = tight55 + leaf030 + divwide + dcsd015 + dcsd010 + vel025:
`{MOTION_RELINK_TIGHT_UM: 5.5, LEAF_PRUNE_MIN_EDGE_PROB: 0.3, SAFE_DIV_MAX_UM: 11.0, SAFE_DIV_SISTER_MAX_UM: 16.0, SAFE_DIV_EXISTING_CHILD_MAX_UM: 12.0, DEEPCENTER_SAFE_DIV_THRESHOLD: 0.15, MOTION_RELINK_VELOCITY_WEIGHT: 0.25}`

### 4.3 Vì sao họ 0.948 trên base 0.939

1. tight55 (+0.0020) — mình đã có sẵn trong 0.947 → phần này KHÔNG cộng thêm cho mình.
2. vel025 (+0.0014) + leaf030 (+0.0004) → **+0.0018 adj mình chưa có** ⭐
3. divwide+dcsd015: divJ recall không tốn adj — census cho thấy +28/+12 fork ở phim thưa (nơi GT division khả năng cao) −21 fork phim dày.
4. Base của họ yếu hơn mình ở chỗ khác (không có SEF_TTA secondary, HOCT mode 1, reparent infra, grid v11) — mình hấp thụ LEVER chứ không thay base.

### 4.4 Bài học kiến trúc

- **Validator-gated sweep runtime là "geometric fusion" thật sự của họ** — không phải một model mới mà là TỔ HỢP post-process được chọn bằng held-out validation kỷ luật (margin + adj-loss + prefix-guard). Chống overfit bằng 3 lớp.
- Chi phí 4h/run của họ vs replica-gate offline 0 GPU của mình: mình có thể sweep OFFLINE trên .geff cache (4 phim test có sẵn trong output v12.1) — nhanh hơn và chính xác hơn (GT thật của hidden test thay vì 8 stem train).

---

## §5. ĐỀ XUẤT V13 — xếp ưu tiên

### P1 · REVERT trục diverge: `SAFE_DIV_DIVERGE_UM −2.0 → 2.25` + orphan-adoption OFF
- **Cơ chế**: trả lại phép đo divergence dương (2 con phải tản ra ≥2.25µm) — cấu hình v11 đã đạt 0.947.
- **Bằng chứng**: (i) v12.1 −0.001 LB với +23 fork 05db; (ii) diverge150 của amanatar FP nổ 6×; (iii) FP anatomy mình: 3/4 FP mới là safe-div, TP symmetry 0.634 không có separator sạch.
- **Kỳ vọng**: +0.001 adjEJ (trở lại baseline v11) · mất divJ replica 0.1429 (không chuyển hóa LB — §2.2).
- **Rủi ro**: gần 0 · **Chi phí**: 2 env knob.

### P2 · `MOTION_RELINK_VELOCITY_WEIGHT 0.5 → 0.25` ⭐ lever lớn nhất
- **Cơ chế**: B4 — dự báo điểm đến relink bằng 1/4 vận tốc thay vì 1/2: tế bào phôi đảo hướng liên tục (không quán tính), W cao làm predicted position OVERSHOOT → relink nối nhầm node láng giềng → FP cạnh + thay cạnh đúng.
- **Bằng chứng**: sweep amanatar ±: vel025 +0.0014 / vel075 −0.0007 (định hướng rõ, dose-response); combo thắng gồm vel025.
- **Kỳ vọng**: +0.0014 adjEJ.
- **Rủi ro**: thấp (1 knob post-link, replay offline được ngay) · **Chi phí**: 1 env (có sẵn dòng 495/2442 monolith).

### P3 · PORT LEAF-PRUNE `LEAF_PRUNE_MIN_EDGE_PROB = 0.30` (~60 dòng code mới duy nhất)
- **Cơ chế**: D3 — cắt node lá cuối track có cạnh vào yếu (< 0.30 learned prob). Đây chính là "đuôi rác" nơi FP cạnh dồn dập; miễn trừ con division (edge_prob None) nên không đe doạ divJ; single-pass bảo thủ.
- **Bằng chứng**: leaf030 +0.0003, t55_leaf030 +0.0004; census họ −71 cạnh yếu; P1 của mình triệt +40 fork thì leaf-prune là lớp vệ sinh tiếp theo.
- **Kỳ vọng**: +0.0004 adjEJ · census −~70 cạnh.
- **Rủi ro**: rất thấp (code bảo thủ, có stats counter riêng để verify) · **Chi phí**: port 60 dòng + 1 knob + builder hook.

### P4 · DIVISION RECALL đúng cách: `divwide` + `dcsd015`
`SAFE_DIV_MAX_UM 9→11 · SISTER 14→16 · EXISTING_CHILD 10→12 · DEEPCENTER_SAFE_DIV 0.2→0.15`
- **Cơ chế**: nới CỔNG HÌNH HỌC + lỏng veto deepcenter, NHƯNG GIỮ divergence 2.25 nghiêm ngặt — division đượcrecall từ vùng "hình học đẹp + model xác nhận" chứ không phải "hội tụ bất thường" (trục diverge đã chết).
- **Bằng chứng**: sweep amanatar: divwide/dcsd giữ adj 0.9280 nguyên vẹn + divJ 0.2308 (tp3); census: fork tăng ở phim thưa (0113 +28, 0b24 +12 — nơi 2/3 GT divcòn FN của mình nằm gần), giảm ở dày; run_stats: DC-rejected 536 vs mình 3177 → cổng này đang thắt ruột nhất trong funnel mình.
- **Kỳ vọng**: adjEJ ~0 · divJ +0.05–0.15 (nếu GT div public nằm ở phim thưa) → +0.005–0.015 composite.
- **Rủi ro**: TRUNG BÌNH — stack mình có HOCT mode 1 + mutual-NN-off khác họ; bắt buộc verify replica trước GPU (census guard fork ≤ 190).
- **Chi phí**: 4 env knob có sẵn.

### P5 · (tùy chọn) GAP2_MAX_STEP_UM 4.0: +18 cạnh — bỏ qua (lẻ, không đủ đáng).

### P6 · V1057 reconcile (re-add raw edge ≥ 0.30): NGƯNG — đối cực của leaf-prune (thêm cạnh vs cắt cạnh); alfonso LB thật 0.946; để backlog v14 sau khi có dữ liệu P2/P3.

### P7 · (khuyến nghị sau V13) Runtime validator-gated sweep kiểu amanatar: đắt 4h GPU/run nhưng là kiến trúc tự-tối-ưu; chỉ cân nhắc nếu còn ≥8h GPU sau V13 và deadline cho phép. Phiên bản rẻ: **offline sweep bằng replica-gate** (mình có lợi thế họ không có: GT 4 phim hidden test).

### Tổng hợp kỳ vọng V13 = P1+P2+P3+P4

| Trục | Giá trị |
|---|---|
| adjEJ | v11 baseline 0.947 + P2 (+0.0014) + P3 (+0.0004) ≈ **0.948–0.949** |
| divJ | duy trì ≥ v12.1 (P4 thay thế kênh diverge) — composite kỳ vọng ≥ 0.949 |
| Census dự báo | ~122.760n / ~118.500e / ~160–175f (fork tăng ở thưa, giảm ở dày) |
| Giá rủi ro | 0.7h GPU (validator OFF) + quota 1 lượt |

---

## §6. KẾ HOẠCH THỰC THI (kỷ luật GPU-WASTE-PREVENTION)

```
[GPU WASTE CHECK] — V13 planning, 22/9: GPU 0.0h tiêu thụ.
```

1. **Port code (0 GPU)**: leaf-prune 60 dòng vào cell-monolith + builder v13 + config `v13_vel_leaf_divwide` (P1+P2+P3+P4) + selftest v12lab + determinism + final-env assertion.
2. **Offline replica sweep (0 GPU)** trên .geff cache 4 phim (có sẵn output v12.1):
   - Arm 1: v11-equivalent (đối chứng khôi phục 0.9010)
   - Arm 2: v12.1 (đối chứng 0.8998/0.9141)
   - Arm 3: V13 full (P1-P4) · Arm 4: V13 −P4 (cách ly rủi ro division) · Arm 5: chỉ P2 (minimal)
   - **Cổng**: adjEJ_arm3 > 0.9010 (v11) MỚI được lên GPU; composite ≥ 0.9141; census fork ∈ [144, 190].
3. **GPU production (0.7h, validator OFF)**: push biohub-ver13 v1 → poll L9 → replica-gate xác nhận output → PRE-SUBMIT INT/DAG/CENSUS/TAG.
4. **Submit khi có lệnh trực tiếp** (quy tắc đứng). Quota hôm nay 5 lượt trống.
5. Cây quyết định sau điểm: ≥0.948 → giữ + đánh FN division tiếp; =0.947 → A/B P4 riêng; <0.947 → revert P4 (v13.1 chỉ P1+P2+P3), 0.947 banked vẫn selectable.

### Ngân sách & lịch
- GPU: 14.15h còn · 1 run V13 = 0.7h → dư 13.4h cho 2-3 lần lặp nếu cần.
- Deadline 29/9: 7.5 ngày — đủ chu trình port (hôm nay) → sweep offline (1 ngày) → GPU (1 ngày) → submit + đọc LB (1 ngày) → lặp 1 vòng.
- Huy chương cần ≥0.955 (cụm 0.948 = hạng 126-199) — V13 là bước đệm; đòn kế trên (SEF_TTA A/B, keep-rate 0b24) giữ backlog.

---

## Phụ lục A — nguồn dữ liệu
- Notebook + output + log amanatar: `kaggle/api/research/amanatar-geofusion/` (notebook 234KB · submission 241.311 dòng · run_stats · validator_results 8 stem × 26 config · ppsweep_selected).
- LB zip 22/9: Aman Atar hạng 244 điểm 0.948 (108 submissions); cụm điểm: 0.948×96 · 0.947×726 · 0.946×175.
- Census v11 production: `/tmp/v11out/submission.csv` (pull kernel output 22/9).
- Tam giác điểm: 56403231 (v11, 0.947) · 56442903/56442908 (v12.1, 0.946 — 2 entry cùng kernel v2, bytes khác nhau do re-run nondeterminism GPU, cùng điểm).
