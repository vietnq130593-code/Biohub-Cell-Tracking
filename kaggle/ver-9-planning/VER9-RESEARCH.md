# VER-9 — NGHIÊN CỨU TRI THỨC MỚI & KẾ HOẠCH TRIỂN KHAI

**Ngày 15/9/2026 (~11:00, REV-2 review 13:30)** · ver-8 (56242181,
re-parenting) submit 01:09 — **vẫn PENDING** (~12,3h trôi qua, cửa sổ chấm
6–12h · ver-7 = 0.947 xác nhận)
· **v8-v2 kernel COMPLETE ~09:13 UTC** (7,9h) — ppsweep chọn **ppTight5565**
(proxy 0,9594) · **rp-ep50/75 thất bại** (div_tp đứng ở 4, div_fp 2→4) →
REPARENT_EDGE_PROB giữ 0,25
· LB 13:15: **3569 đội** · ta hạng **183** (cụm 0.947 = 479 đội)
· **Cụm 0.948 = 46 đội** (hạng 79–124) · Pilkwang Kim = 0.949 · đỉnh 0.970
· Nghiên cứu nguồn: trang `/code` của cuộc thi (17 notebook mới pull về
`kaggle/api/research/v9-research/`) + 6 thread discussions + web (arXiv 2607.11754)

> Mục tiêu: v9 nâng điểm so với v8/v7 (0.947). Mọi phát hiện dưới đây đều có
> nguồn + số liệu kèm — theo nguyên tắc "tune trên dữ liệu, không đoán".

---

## 0. Tóm tắt điều hành — 6 phát hiện then chốt (MỚI, chưa có trong VER8-RESEARCH)

| # | Phát hiện | Nguồn | Số liệu cốt lõi | Giá trị cho v9 |
|---|---|---|---|---|
| **F1** | **HOCT consensus veto — MODE 2 (veto cả cạnh division) là biến thể được đo và fielded** (rev-2 sửa attribution: log chạy thật ghi `HOCT_VETO_ARMED mode=2`; phép đo offline mô tả "keeping only edges proposed by BOTH linkers" = intersection đầy đủ bao gồm cạnh division) — linker học sâu độc lập (royerlab, BSD-3) chạy trên node set + raw intensity | sjlee101/biohub-lf-hoctveto-div-b (25 votes, chạy 11/9, `BIOHUB_HOCT_VETO=2`) + arXiv 2607.11754 | **+0.0040 [+0.0006, +0.0058] trên 20 video honest (CI dương) — thuộc mode 2**; false divisions 55→29 (mode 2); chạy thật 4/4 video test, 1097s HOCT; divisions 124→71 (−43%) trên submission thật | **Lớn nhất: ~+0.004 adjEJ + giảm div_fp** — độc lập hoàn toàn với pipeline ta (khác encoder, khác data) → true consensus. LƯU Ý: div edges của ta (safe-div + re-parent) lành mạnh chưa từng được HOCT duyệt → bắt buộc audit A1 đo mode 2 trên 8 stems trước khi mặc định |
| **F2** | **Repeat-lineage division filter** — trên GT không có division nào có tổ tiên cũng division | pawanmali/biohub-942tta-fork-divfix-v1 (15/9 — "divfix", chính tác giả dòng 0.945) | **0/132 divisions GT có earlier division cùng lineage**; +0.0021 trên pipeline khác của tác giả (0.9297→0.9318); thuần post-hoc, chỉ BỎ cạnh | Giảm div_fp an toàn — đặc biệt trên TEST nơi pipeline sinh ~124 forks/4 video (vs 12 GT trên 8 held-out stems!) |
| **F3** | **Nhân phân bào CO NHỎ lại chứ KHÔNG mờ** — volume drop bắt đầu 2 khung TRƯỚC split, peak brightness giữ nguyên | zhincez/a-dividing-nucleus-gets-smaller-not-dimmer (Lê Quang Cảnh) | Volume −0.27 tại lag +3, khác 0 ở lag −2,−1,+1..+5 (bootstrap paired); peak interval phủ 0 mọi lag trừ khung split | Feature ranker division MỚI (size-drop sớm hơn brightness AUC 0.73) — enrich DivNet/re-parent evidence |
| **F4** | **Cấu trúc labels: 2 embryo train, test = embryo thứ 3; 1 embryo nhãn đậm gấp 12×** | zhincez/label-eda-two-embryos-151-divisions | Median label density 0.8% vs 9.7%; 85% label nodes từ embryo đậm (128/199 films); divJ resolution = 1/D mỗi event; bộ đếm division khớp official scorer 45/45 films | Hiểu vì sao held-out (embryo train) KHÔNG dự báo tốt test (embryo 3, dày hơn); validator phải chọn video giàu division |
| **F5** | **Frontier thật đã xa hơn tưởng** — top đang 0.949–0.970, Pilkwang 0.949, người hạng 32 fielded 0.9557 | LB 10:50 + thread focus3d (hengck23, 33 votes) | Fine-tune detection head OK nhưng **encoder moving phá frozen edge transformer**; velocity extrapolation thua 0/381 contested; link model chọn đúng con 44/290 (15.2%) contested → structured softmax đáng +0.005 EJ | Bản đồ "không đi": fine-tune encoder + velocity-only; bản đồ "đi": HOCT chính là structured second opinion |
| **F6** | **Ultrack weights chính chủ public + Zebrahub được phép** | hengck23 threads + Masha Mikhisor (hạng 13, 13h trước) | `public.czbiohub.org/royerlab/ultrack/unet_weights/unet-daxi.pt` + `unet-simview.pt`; Zebrahub OK (organizer confirm); embryo `2024_03_22_dorado/stabilized.zarr` = ứng viên validation embryo-3 | Nguồn external để build validator embryo-thứ-3 (private phase) + domain adaptation 2-head (hengck23: Kaggle zyx = Focus3D zyx + dzyx) |

**Kết luận chiến lược v9 — 3 đòn bổ trợ (không loại trừ nhau):**

- **(A) HOCT consensus veto MODE 2 làm layer xác nhận mới** (chủ lực, +0.004
  đo được CI dương — rev-2: bằng chứng thuộc mode 2, chính là biến thể
  sjlee fielded; mode 1 chỉ là fallback nếu audit 8-stems cho mode 2 mất
  div_tp): mọi cạnh — kể cả cạnh division của safe-div lẫn re-parent —
  chỉ sống nếu HOCT cũng đề xuất. Re-parent v8 tự động nhận consensus
  I4 mà không cần gate riêng.
- **(B) Repeat-lineage division filter** (thuần post-hoc, 0 rủi ro topology): dọn div_fp
  trên test dày — chính nơi divJ được tính. Chạy output-level SAU CÙNG
  (sau veto), đúng nguyên bản pawanmali.
- **(C) Volume-drop feature (F3) enrich ranker** DivNet cho re-parent wave sau (v9.1)
  nếu audit 8-stems cho tín hiệu rõ.
- **(D) MỚI rev-2 — SAFE_DIV_DIVERGE_UM 4.0/4.5** (đỉnh LB sweep kimi-v18,
  ghi trong comment caassicca-v5; ta đang 2.25; E0 của ta chỉ từng sweep
  XUỐNG 1.0/1.5 — sai hướng). Gate divergence chặt hơn = ít fork FP hơn —
  đặc biệt đúng trên test embryo dày (F4). Đưa vào audit A1 như arm đo.

---

## 1. BỐI CẢNH ĐIỂM SỐ HIỆN TẠI (10:50 15/9)

| Mốc | Giá trị |
|---|---|
| ver-7 LB | 0.947 (COMPLETE ×2 lần chạy, deterministic) |
| ver-8 v1 | 56242181 PENDING ~12,3h — submit 01:09, kỳ vọng ≈0.948–0.950 nếu re-parent MAP giữ tỷ lệ |
| ver-8 v2 | kernel COMPLETE 09:13 (7,9h): chọn ppTight5565 proxy 0,9594 (adjEJ 0,9287, div 4/1/8) — KHÔNG nộp, chờ điểm v1 (Δ vs v1 chỉ +0,0003 — dưới ELEVEN) |
| Ta | hạng 183/3569 (13:15) — đội mới nhập cuộc liên tục |
| Cụm 0.948 | 46 đội (79–124) — **mục tiêu trực tiếp** |
| Cụm 0.947 | 479 đội — "bức tường" fork Reyhan |
| Pilkwang Kim | 0.949 — tác giả support-pack đã vượt 0.948 bằng tweaks riêng |
| Đỉnh | 0.970 Sergio Alvarez (14/9); 0.968 Soheil Ayati (15/9 02:04); Tang + unicellular 0.966 (15/9) |
| GPU quota | **23,07/30h đã dùng → còn 6,93h** (refresh 19/9 00:00 UTC) — đủ cho audit A1 (~1,5h) + ver-9 lean (~2h) NGAY HÔM NAY (rev-2: v2 cho thấy PPSWEEP chiếm 6,87/7,95h kernel → bỏ sweep tiết kiệm gần như toàn bộ) |
| Submit hôm nay | 1/5 đã dùng (ver-8 v1) — còn 4 |

Hiệu chuẩn proxy↔LB giữ nguyên (−0.006…+0.002, 3/8 phiên bản lệch hướng).

---

## 2. CHI TIẾT 6 PHÁT HIỆN (đã đối chiếu code + log chạy thật)

### 2.1 F1 — HOCT consensus veto (quan trọng nhất)

**Nguồn gốc model:** "Higher-Order Cell Tracking Transformer" (HOCT),
arXiv 2607.11754 (13/7/2026, royerlab — BSD-3-Clause, code + weights public).
Edge-centric transformer xếp hạng candidate links bằng attention giữa các link
(biased bằng inter-link geometry), SOTA Cell Tracking Challenge + bacteria
division benchmark, KHÔNG cần encoder pre-training sâu → model general
(`general_v0.pt`, 6.25M params). **Hợp lệ quy tắc: model public, không train
trên Biohub test.**

**Tài nguyên Kaggle (đã public, offline-ready):**
- wheels: `sjlee101/biohub-hoct-020-wheels` (hoct==0.2.0 + spatial-graph==0.1.1 + pooch==1.9.0)
- weights: `musculer/biohub-hoct-general-v0-official/general_v0.pt`

**Cơ chế (port nguyên văn từ cell 6 notebook sjlee101, 550 dòng):**
1. Rasterize cầu 3µm (anisotropic theo voxel 1.625/0.40625/0.40625) quanh MỖI node cuối → labels int16.
2. Đọc raw volume (T,Z,Y,X) uint16.
3. `hoct.predict(model, labels, images=raw, scale=(1.0,*VOXEL_SCALE), max_delta_t=1, tiling=(5,32,128,128)+(1,8,16,16))` → solution graph.
4. Snap nodes HOCT → pipeline node ids (cKDTree từng frame, bắt buộc 1-1).
5. **Veto: bỏ mọi cạnh pipeline không có trong tập cạnh HOCT** (mode 1: miễn cả 2 cạnh division; mode 2: veto cả division).

**Hiệu năng T4 (đo thật trong log):** 9s/1000 nodes + 10s fixed →
6k nodes 62s · 20k nodes 131s · 25k nodes 164s · 70k nodes 718s. Tổng 4 video test
= 1097s (~18 phút). Chunk-retry 1→2→4 khi SCIP ILP cả phim fail.

**Bằng chứng hiệu quả (2 nguồn độc lập):**
- sjlee101 đo offline trên 20 video honest, converged linker: intersection **+0.0040
  [+0.0006, +0.0058]** (paired, CI dương), dương trên cả 2 prefix; union −0.004;
  **scorer-visible false divisions 55 → 29**.
- Đo trên submission thật (diff 2 file output kernel sjlee101): divisions
  124→71, edges 118,469→118,102 (−2,130/+1,763 do sweep rewrite), nodes giữ.

**Fail-safe sẵn có:** deadline 10h notebook + per-video cap 900s + backup
submission trước veto + bỏ qua từng video nếu fail — KHÔNG bao giờ làm hỏng run.

**Khoảng trống mà TA sẽ lấp (chưa ai làm — xác nhận bởi Hammad Farooq trong
discussion 14/9):** *"Has anyone measured HOCT mode 1 vs mode 2 on a held-out
split? The notebook's validator never scores the veto itself."* → Hệ đo
system-view official 8-stems của ta (đã có từ ver-8) + veto = đo được trước khi
submit. **Đây là lợi thế thông tin thật của ta so với sjlee101.**

**Runtime risk (Hammad Farooq 14/9):** validator+sweep ~75 phút trước write cuối;
hidden test ≈ 199 video (lớn hơn 4 video public ×50) → HOCT có thể trượt deadline
10h → video bị skip veto. Giải pháp của họ: hardcode tight55 (đã chọn deterministic
mọi rerun) + bỏ validator/sweep/base-write → tiết kiệm ~75 phút cho HOCT.
**v9 áp dụng: hardcode tight55 + rút gọn write + HOCT deadline 10.5h.**

### 2.2 F2 — Repeat-lineage division filter (pawanmali divfix, 15/9)

Cell 10.5 mới trong `biohub-942tta-fork-divfix-v1` (diff với 942tta-fork-v1 đã
xác minh — chỉ thêm cell này, manifest chuyển xuống cuối):
- Với mỗi node out-degree ≥ 2: walk predecessors; nếu TỔ TIÊN cũng là divider →
  drop cạnh con XA hơn (theo dist µm).
- Cơ sở: **0/132 divisions GT** (đo trên pipeline `port_geom_plus_steal` của
  chính Pawan) có earlier division cùng lineage — tức "2 lần chia liên tiếp trên
  một lineage trong window quan sát" chưa từng thấy trên GT.
- +0.0021 (0.9297→0.9318) khi compose với "Erlang division-cost fix" trên local
  held-out của pipeline đó.
- Chỉ BỎ cạnh (không thêm node/cạnh) → an toàn topology tuyệt đối; có audit
  structural sau filter (ids contiguous, dataset match, degree/frame rules).
- Pawan cảnh báo validator của họ bị contamination (secondary detector train
  trên cả 199 wells) → họ chọn A/B bằng submission thật. **Ta có validator
  sạch hơn (8 stems official) — đo được offline.**

**Lưu ý giá trị y hệt cho ta:** trên held-out 8 stems div_fp của ver-7/ver-8
chỉ ~1 → filter gần như không đổi ĐÓ. Nhưng trên test embryo-3 (dày), pipeline
sjlee101 sinh 124 forks/4 video — filter này có đất diễn. Nhân quả: FP fork
của safe-div/re-parent thường bám vào track đã có fork (motion pattern bị
"đề xuất" 2 lần) → lọc theo lineage cắt đúng lớp này.

### 2.3 F3 — Division = "smaller, not dimmer" (zhincez, đo GT thật)

Phép đo 3 mặt trong cùng box (peak/volume/mean) + paired controls cùng film
cùng frame (bỏ drift/bleach):
- **Volume**: −0.27 tại lag +3; khác 0 ở lag −2, −1 (sớm!), +1…+5; hết hiệu lực ~+6.
- **Peak**: KHÔNG đổi (interval phủ 0 mọi lag, trừ đúng khung split).
- Mean giảm = artefact của probe bán kính cố định trên vật nhỏ đi.

Ứng dụng v9.1 (wave sau): feature `volume_ratio(t)` quanh node mẹ (so với baseline
pre-division) cho DivNet ranker / re-parent evidence e8 — tín hiệu đến SỚM HƠN
brightness (−2 frame) và ít nhiễu hơn (peak ổn định). Lưu ý voxel anisotropic
1.625/0.40625/0.40625 — half-max volume ước lượng thô nhưng đủ làm feature.

### 2.4 F4 — Kiến trúc labels: 2 embryo train / test = embryo 3 (zhincez EDA)

- Division counter của EDA (out-degree ≥ 2, validate directedness/duplicates)
  **khớp official scorer 45/45 films** → con số 151 divisions tin được.
- Embryo A: median label density 0.8%; embryo B: 9.7% (12×); 85% label nodes
  thuộc B (128/199 films). → adjEJ trên film của A và B KHÔNG so trực tiếp được.
- Test embryo-disjoint với cả 2 → hidden test có mật độ "không ai ngoài BTC
  biết" → **quyết định config không được quá khớp 8 stems validator** (đã là
  nguyên tắc của ta; đây là bằng chứng gốc).
- divJ resolution: mỗi event = 1/D; đóng góp tổng ≈ 0.1/D → với D=12 (held-out),
  1 event = 0.0083 divJ = 0.00083 điểm. Với test D lớn hơn nhiều (embryo dày),
  mỗi event rẻ hơn → **precision trên test quan trọng hơn recall từng event**
  (khớp nguyên tắc "GT thưa, FP đắt").

### 2.5 F5 — Frontier thật & bản đồ "không đi" (thread focus3d, hạng 32 + hengck23)

Từ comment người hạng 32 (fielded 0.9557, honest baseline 0.9462 — weights
override đổi cả primary link model):
- Fine-tune detection head trên dense labels: gần như miễn phí; **hỏng đến khi
  encoder dịch chuyển — edge transformer frozen đọc encoder đó** → mất liên kết.
- Elastic augmentation từ secondary seed: McNemar p=0.0028 CẢI THIỆN top-1
  (92.90% vs 92.46%) — đang chờ correct run (checkpoint nhầm secondary).
- Bias residuals đo 15,693 pairs: dz −0.57µm (48 SE!), dy −0.24 (31 SE), dx −0.20
  (26 SE) — embryo-dependent; correct bằng hằng số MẤT 0.0031 (phải học per-node).
- **381 contested GT edges: velocity extrapolation chọn đúng con 0/381; swap rẻ
  hơn 0/271 (margin 16.75µm NGƯỢC)** → trên contested, cả appearance lẫn
  trajectory đều sai hướng — "correct answer is behind on every local signal".
- Link model đúng 44/290 contested (15.2%) → structured softmax fix được ~1/6
  ≈ +0.005 EJ tiềm năng — đúng lớp vấn đề HOCT giải (second opinion học đường KHÁC).

→ v9 KHÔNG đi: fine-tune encoder (GPU đắt + phá linker), velocity-only relink,
constant offset dzyx. v9 ĐI: consensus linker độc lập (HOCT) + postprocess an toàn.

### 2.6 F6 — External chính chủ public (để private phase / validator embryo-3)

- Ultrack UNet weights: `https://public.czbiohub.org/royerlab/ultrack/unet_weights/unet-daxi.pt`
  + `unet-simview.pt` (hengck23 chia sẻ trong "magic or overfitting?").
- Zebrahub được BTC xác nhận OK dùng (thread Masha Mikhisor, hạng 13).
- Embryo `2024_03_22_dorado/stabilized.zarr` (public Ultrack embryo) — ứng viên
  validation "embryo thứ 3" nếu không trùng train/test.
- hengck23 domain-adaptation trick: 2 heads (Focus3D zyx + delta dzyx) →
  Kaggle zyx = Focus3D + dzyx; delta học bằng µm liên tục, không quantize.
- hikaggler thread: official repo `royerlab/kaggle-cell-tracking-competition`
  có `evaluate_datasets()` trả edge_jaccard + division_jaccard TÁCH RIÊNG, chạy
  local trên train .geff — không tốn submission (đã có tương đương trong eval
  cell của ta).

---

## 3. BẬC SUY DIỄN NHÂN QUẢ — TÍNH TRƯỚC CÁC BƯỚC ĐI

### Bậc 1 — Quan sát (đo được, đã có số liệu)

- O1: HOCT intersection (đầy đủ, kể cả cạnh division = mode 2) +0.0040 CI
  [+0.0006,+0.0058] trên 20 video (sjlee, linker converged ≈ pipeline 0.947
  cùng họ Reyhan/Pilkwang). Biến thể fielded của sjlee = mode 2 (log xác nhận).
- O1b (rev-2): v8-v2 thực nghiệm mở REPARENT_EDGE_PROB 0.25→0.50/0.75 trên 8
  stems: div_tp KHÔNG tăng (đứng ở 4), div_fp tăng 2→4 → phần re-parent còn
  chặn là FP-trên-held-out, không phải event thật bị chặn.
- O6 (rev-2): submission cuối có 0 cạnh dt>1 (gap-recovery chèn node synthetic
  làm cầu) → HOCT max_delta_t=1 có thể đề xuất cấu trúc MỌI cạnh — không có
  lớp cạnh nào tự-nghiên-canh với veto.
- O2: GT không có repeat-lineage division (0/132).
- O3: Volume-drop là tín hiệu phân bào sớm (−2 khung), peak bất biến.
- O4: Test (embryo 3) dày hơn held-out (124 forks sinh ra trên 4 video test của
  sjlee vs 12 GT division trên 8 stems held-out) → mọi phép đo trên held-out
  UNDER-estimate hoạt động của postprocess division trên test.
- O5: 46 đội 0.948 + Pilkwang 0.949 → bức tường 0.947 đã bị vượt bởi tweaks
  division/TTA nhỏ, không phải kiến trúc mới.

### Bậc 2 — Can thiệp (nếu áp X thì Y, với cơ chế)

- I1 (rev-2 — đảo ưu tiên theo bằng chứng): Áp HOCT veto **mode 2** (veto cả
  cạnh division) lên submission ver-8 → kỳ vọng +0.004 adjEJ (đây LÀ biến thể
  được đo CI-dương trên 20 video và fielded bởi sjlee, log mode=2); cắt div_fp
  (55→29 của họ; 124→71 submission thật). Rủi ro: cắt nhầm division TP nếu
  HOCT miss cạnh đúng — div edges của ta (safe-div/re-parent, sinh post-hoc,
  khác pipeline sjlee) chưa từng được HOCT duyệt → bắt buộc đo A1 trước.
- I2: Áp HOCT veto mode 1 (ch exempt cạnh division) → an toàn cho div_tp của
  v8 nhưng KHÔNG có phép đo CI-dương riêng nào (chỉ là biến thể khoan dung
  hơn của cùng cơ chế) → dùng làm FALLBACK khi audit cho mode 2 mất div_tp.
- I3: Repeat-lineage filter SAU CÙNG (output-level, nguyên bản pawanmali:
  bỏ cạnh con XA hơn của fork có tổ tiên cũng fork, walk toàn lineage, giữ
  node) → div_fp giảm trên test dày; trên held-out gần như no-op (div_fp ~1)
  → chấp nhận no-op validator + dựa vào Bậc-1 O2 (0/132 GT).
- I4 (rev-2 — hạ kỳ vọng theo O1b): mode 2 TỰ ĐỘNG áp consensus lên cạnh
  re-parent M→D2 (chúng là cạnh division). Kỳ vọng cũ "thu hồi 2–4/6 event"
  bị mâu thuẫn trực tiếp bởi O1b (mở ep không thêm tp trên held-out) → coi
  I4 chỉ là lớp bảo vệ precision cho TEST dày, KHÔNG tính vào EV bảng §5.

### Bậc 3 — Phản thực / tổ hợp (compute-before-step)

- C1: Nếu v8 chấm < 0.947 (regression MAP) → nguyên nhân khả dĩ: re-parent thêm
  cạnh trên test embryo-dày gây div_fp (giống ver-7b triệu chứng). Lúc đó v9 =
  ver-7 + HOCT mode2 + repeat-lineage (mode 2 tự cắt cả re-parent FP) — vẫn
  +0.004 quỹ đạo độc lập với re-parent.
- C1b (rev-2, thiếu sót cũ): Nếu v8 chấm = 0.947 đúng → re-parent trung tính
  trên public test (held-out +0,008 không chuyển). Coi như C1 xử lý khoan dung:
  giữ re-parent (held-out dương, không bằng chứng hại trên test) + mode 2
  (audit A1 sẽ cho biết div_tp có giữ được không) — KHÔNG nộp thêm biến thể
  micro-delta của re-parent.
- C2: Nếu v8 ≥ 0.948 → re-parent MAP tốt → v9 = v8 + HOCT mode2 + repeat-lineage
  + (D nếu audit A1 xanh) → kỳ vọng 0.949–0.952.
- C3: Runtime — rev-2 tính lại: PPSWEEP chiếm 6,87/7,95h của kernel v2 →
  v9 lean (hardcode, không sweep) ≈ 1,5–2h tổng kể cả HOCT (~0,35h) + RLF (~0)
  + 1 eval replay (~0,4h). **REV-3 (15/9 13:50 — bằng chứng mới): cuộc thi CÓ
  rerun notebook trên hidden test ngay dev-phase** — submission v8-v1 (56242181)
  failed với errorDescription "submission notebook exceeded the allowed runtime
  ... hidden dataset can be larger/smaller/different than the public dataset";
  tổngBytes=0, không có điểm. Ước scaling: 12h limit / 6,2h public ≈ 1,9× →
  hidden test ≈ 2× public. ver-7 (117 phút → ~4h hidden) pass ✓. **Bỏ sweep
  không còn là tối ưu mà là BẮT BUỘC để được chấm**; ngân sách runtime public
  ≤ 5,5h (an toàn ≤ 2h). Fail-safe giữ nguyên (per-video cap 900s + deadline +
  backup).
- C4: Nếu HOCT wheels/weights hỏng trên Kaggle → fail-safe pass-through (đã có
  trong code sjlee) — vẫn là run ver-8/7 hợp lệ. Chỉ mất phần +0.004 tiềm năng.
- C5: Tổ hợp các đòn độc lập về cơ chế (linker appearance · topology lineage)
  → kỳ vọng cộng gần tuyến tính trên đoạn nhỏ: +0.004 (A, mode 2 đo được) +
  +0.000…+0.002 (B, trên test dày) + 0…+0.001 (D, nếu audit xanh) ≈
  **+0.004…+0.007 trên nền v8** → mục tiêu 0.949–0.951 nếu v8 ≈ 0.947–0.948.
  (Rev-2: con số +0,021 cũ ở §5 là so với v7 — gồm cả phần đã bank trong v8;
  Δ thực của v9 so với v8 nằm trong khoảng này. I4 không tính vào EV — xem O1b.)

### Phân bổ thời gian còn lại (15→29/9) — rev-2 chỉnh theo quota thật

| Ngày | Việc |
|---|---|
| 15/9 (nay) | **Wave-A audit A1/A2 (GPU mini-kernel ~1,5h từ quota 6,93h còn lại)** + dựng ver-9 monolith + unit test offline; nếu audit + điểm v8 đều về kịp → **push ver-9 lean tối nay (~2h, vẫn còn dư quota)** |
| 16–18/9 | ver-9 submit (cổng §6) + (nếu xanh) ver-9.1 volume-feature + PPSWEEP-3 sau-refresh |
| 19/9 | GPU quota refresh (+30h) |
| 20–21/9 | PPSWEEP-3 (DIVERGE/threshold arms) trên graph cache + validator embryo-dorado bắt đầu |
| 22/9 | **Deadline entry** — bảo đảm mọi version dự final có ≥1 submission hợp lệ |
| 23–28/9 | Validator embryo-dorado (F6) + chọn 2 final |
| 29/9 | Chốt 2 final: kế hoạch (a) ver-7 port 0.947 đã verify ×2, (b) ver-9 tốt nhất |

---

## 4. KẾ HOẠCH THỰC NGHIỆM — WAVE-A (rev-2: **mini-kernel GPU ~1,5h** — CPU không đủ cho HOCT, làm NGAY trong lúc v8 chấm)

### A1. Audit HOCT veto trên 8 stems held-out (lấp khoảng trống của sjlee101)

Mini-kernel GPU T4 (quota ~1,5h) — replay postprocess CPU được nhưng HOCT
inference cần GPU (9s/1000 nodes trên T4; CPU chậm 5–15× → 4,5–13,5h cho
~360k nodes của 8 stems là không kịp):
- Input: 6 dataset theo pattern `biohub-ver8-wave1` (gồm `biohub-v7-heldout-preds`
  8 .geff raw + `biohub-wave1-features`) + **2 dataset HOCT** + competition
  source (train zarr cho images) — tổng 8 dataset + 1 competition.
- Cài HOCT từ wheels dataset trên GPU, chạy trên **node set sau postprocess**
  của từng stem (đúng như runtime thật), tính hoct_pairs MỘT LẦN mỗi stem rồi
  tái dùng cho mọi chế độ đo.
- Đo 5 chế độ (mỗi chế độ chỉ là áp veto/RLF lên cùng graph + chấm official
  rule system-view — scorer 075fc5f đã có):
  `base` · `veto1` · `veto2` · `veto2+rlf` · `veto1+rlf` — kèm breakdown
  div_tp/div_fp/div_fn + số cạnh bị veto + số cạnh RLF lọc mỗi chế độ.
- **Arm D (rev-2): replay thêm 2 config `diverge4.0` / `diverge4.5`**
  (SAFE_DIV_DIVERGE_UM 2.25→4.0/4.5 — REPARENT_DIVERGE_UM giữ 2.25 riêng) —
  đo trên cùng 8 stems như PPSWEEP arm; nếu Δproxy ≥ +0.002 và div_fp giảm
  → đưa vào v9 hardcode.
- Đầu ra: bảng so sánh + quyết định config cho v9 theo cổng (mục 6).

### A2. Kiểm chứng resources Kaggle (✅ ĐÃ XONG rev-2 13:10)

- Verify dataset `sjlee101/biohub-hoct-020-wheels` (hoct-0.2.0 + pooch +
  spatial_graph wheels) + `musculer/biohub-hoct-general-v0-official`
  (general_v0.pt 25,5MB + nguồn hoct) — **cả 2 list/get OK qua API** →
  attach cho kernel v9 + audit.

### A3. Soạn ver-9 monolith (fork ver-8, 6 thay đổi — rev-2 mở rộng)

1. Thêm block `[ver9-hoct]` SAU filter_output_graph: veto consensus (port
   nguyên văn cơ chế wrap-write/snap/rasterize/predict/budget/fail-safe từ
   cell 6 sjlee101 — đã có trong repo `v9-research/sjlee101-hoctveto-div/`).
   **`BIOHUB_HOCT_VETO` mặc định "2"** (rev-2: bằng chứng +0.0040 thuộc
   mode 2 — biến thể sjlee fielded; mode 1 = fallback nếu audit A1 cho
   mode 2 mất div_tp).
2. Thêm block `[ver9-rlf]` SAU CÙNG (output-level): port nguyên văn
   pawanmali cell 10.5 — với mỗi fork có tổ tiên cũng fork, bỏ cạnh con
   XA hơn (µm); walk toàn lineage; KHÔNG đụng node set; chạy SAU veto
   (rev-2 sửa: RLF chỉ tác động lên cạnh division theo định nghĩa —
   chạy trước veto mode 1 sẽ làm cạnh con còn lại bị lộ ra diện veto,
   mất cạnh oan).
3. Hardcode **`MOTION_RELINK_TIGHT_PER_PREFIX={"44b6":5.5,"6bba":6.5}`**
   (global fallback 5.5) — rev-2: v2 PPSWEEP 19 candidates đã chọn
   ppTight5565 (proxy 0,9594 > tight55 0,9591) — KHÔNG hardcode tight55
   như bản cũ. **Bỏ hoàn toàn PPSWEEP sweep cell** (6,87h!) — chỉ giữ
   eval cell 1 lần duy nhất SAU veto+RLF (đo system-view thực tế của
   submission cuối — điều sjlee KHÔNG có).
4. Config re-parent giữ nguyên v1: `REPARENT_EDGE_PROB=0.25` (rev-2:
   rp-ep50 no-op, rp-ep75 giảm — mở thêm chỉ thêm FP).
5. EXPERIMENT_TAG `secondary_deepcenter_tta_0947_reparent_hoct_v9`;
   deadline HOCT 10.5h; backup `submission_before_hoct_veto.csv`.
6. (Tuỳ chọn sau audit A1) Nếu arm D xanh: hardcode
   `SAFE_DIV_DIVERGE_UM=4.0/4.5` (REPARENT_DIVERGE_UM giữ 2.25).

Unit test offline (CPU): snap 1-1 KD-tree · veto mode 1/2 · repeat-lineage walk ·
budget rule · fail-safe restore — mô phỏng không cần model thật (mock pairs).

### Wave-B — 1 run GPU (~1,5–2h lean — rev-2) + 1 submit (khi v8 có điểm + Wave-A xanh)

Push `vietnguyen130593/biohub-ver9` (T4×2, **9 input: 7 dataset cũ của ver-8
+ 2 HOCT datasets** — rev-2 sửa: ver-8 có 7 dataset sources, không phải 6),
chạy → đọc eval system-view trong output → cổng submit (mục 6) → submit.
Quota: 6,93h còn lại đủ cho audit (1,5h) + ver-9 (2h) hôm nay; KHÔNG cần chờ
refresh 19/9 (kế hoạch cũ tính sai vì tưởng sweep phải giữ lại).

### Wave-C — tuỳ chọn (sau 19/9 refresh)

- v9.1 volume-drop feature vào DivNet ranker (F3) — nếu A1 cho thấy DivNet còn miss.
- Validator embryo dorado (F6) cho private phase.
- PPSWEEP-3 trên graph cache sau veto (cửa hẹp nhưng rẻ).

---

## 5. VÌ SAO KẾ HOẠCH NÀY NÂNG ĐIỂM SO VỚI V8 (phân rã kỳ vọng — rev-2)

| Lever | Cơ chế | Kỳ vọng Δ so với v8 | Độ tin (bằng chứng) |
|---|---|---|---|
| +HOCT veto **mode 2** | bỏ mọi cạnh FP (kể cả div FP) không đồng thuận | **+0.004** | đo 20 video CI dương + chạy thật 4 video + fielded sjlee (log mode=2) |
| +Repeat-lineage filter | dọn div_fp trên test dày | +0.000…+0.002 (test) | 0/132 GT + no-op held-out (an toàn) |
| +DIVERGE 4.0/4.5 (arm D) | gate fork chặt hơn | 0…+0.001 (nếu audit xanh) | đỉnh LB sweep kimi-v18 (public) |
| +Re-parent qua mode 2 | precision re-parent trên test dày | KHÔNG tính vào EV | O1b: mở ep không thêm tp held-out |
| **Cộng gộp Δ(v9 − v8)** | | **+0.004…+0.007** | (con số +0,021 cũ là Δ so với v7, gồm phần v8 đã bank) |

So với: node-count tuning (−0.004), metric hack (đã vá/DQ), fine-tune encoder
(phá linker — F5), velocity-only (0/381 — F5). → HOCT(mode 2) + RLF là 2 lever
mới duy nhất có bằng chứng đo được mà TA CHƯA CÓ; D là lever rẻ thứ ba.

---

## 6. CỔNG SUBMIT VER-9 (siết — rev-2 sửa logic cổng mode)

- Đo system-view official 8 stems SAU veto+RLF (trong kernel, eval cell bản đã vá):
  - `ΔadjEJ ≥ −0.0005` so với cùng replay không veto
  - **mode 2 (mặc định): `div_tp(mode2) == div_tp(base)`** (không mất event
    thật) **∧ `div_fp(mode2) ≤ div_fp(base)`** ∧ `ΔadjEJ ≥ −0.0005`.
    (Cổng cũ "div_tp ≥ +1 mới bật mode 2" là BẤT KHẢ — veto chỉ bỏ cạnh,
    không thể tạo tp mới; rev-2 bỏ.)
  - mode 1 (fallback): chỉ dùng nếu mode 2 mất div_tp trên audit; cổng
    `div_tp ≥ 0` so base.
  - `div_fp ≤ +3` (so base, cho mọi chế độ)
- Guards 5/5 (compare.py) + node budget ±10% stem chung
- Repeat-lineage: số cạnh bị lọc ≤ 0.5% tổng cạnh (guard vô ý)
- ELEVEN rule: Δproxy ≥ +0.005 mới submit tự tin; 0.001–0.005 → cần thêm lý do
  độc lập (div_fp giảm rõ + v8 LB ≥ 0.948 xác nhận MAP re-parent)
- Runtime (rev-2): kernel lean ~1,5–2h — thoải mái trong hạn 9–12h; vẫn giữ
  HOCT deadline 10.5h + per-video cap 900s + backup cho fail-safe; nếu HOCT
  skip > 2/4 video public → xem lại tile/budget trước submit

---

## 7. NGUYÊN TẮC (thừa hưởng VER8-RESEARCH §6 + 3 mới)

1–8. (giữ nguyên: không hack / ELEVEN / không tin proxy một mình / tune trên GT /
mở gate đi kèm ranker / sinh học > tham số / artifact sống trên Kaggle / không
săn micro-delta public).

9. **Consensus phải ĐỘC LẬP** — linker thứ hai chỉ có giá trị nếu không chia sẻ
   encoder/data/định kiến với linker thứ nhất (HOCT: khác kiến trúc, khác data,
   intensity-only → đạt).
10. **Fail-safe một chiều** — mọi bước post-hoc mới phải thiết kế sao cho khi hỏng
    thì trở về graph gốc, không bao giờ tệ hơn baseline đã có điểm.
11. **Đo trước khi tin** — mọi claim cộng đồng (+0.004 của sjlee, +0.002 của
    Pawan) phải tái hiện trên hệ đo 8-stems official của ta trước khi vào submission.

---

## 8. NGUỒN TÀI LIỆU MỚI (toàn bộ trong repo)

| Nguồn | Vị trí |
|---|---|
| HOCT veto arming cell (550 dòng) + log chạy + 2 submission trước/sau | `kaggle/api/research/v9-research/sjlee101-hoctveto-div/` + `sjlee101-hoctveto-output/` |
| Divfix repeat-lineage (diff đã xác minh) | `v9-research/pawanmali-divfix/` + `pawanmali-942tta-base/` |
| EDA smaller-not-dimmer + label-eda | `v9-research/zhincez-dividing-smaller/` + `zhincez-label-eda/` |
| 0.947 runnable (bảng lịch sử 0.934→0.947) | `v9-research/zhincez-0947-runnable/` |
| Clean-strict graph repair (toán ILP/repair đầy đủ) | `v9-research/binasalama-gaprecovery/` |
| Caassicca/mtoshidesu/hahuyy/indarkarhana/sarvesh/karl/tangai (fork nhỏ) | `v9-research/*/` |
| Discussions (6 thread đã đọc) | kaggle.com/.../discussion — Hammad HOCT speedup · focus3d (hạng 32) · magic-or-overfitting (ultrack weights) · divJ 0.22 (hikaggler) · external data (Masha) · division base rates (Lê Quang Cảnh) |
| LB snapshot 15/9 10:50 | `kaggle/api/research/v9-research/biohub-...-2026-09-15T10:50:50.csv` |

---

## 9. BƯỚC TIẾP THEO NGAY (rev-2)

1. Wave-A A1/A2/A3 (A2 ✅ xong; A1 = GPU mini-kernel ~1,5h; A3 dựng monolith + unit test).
2. Khi v8 (56242181) có điểm → rẽ nhánh C1/C1b/C2 (mục 3-Bậc 3).
3. Push ver-9 lean (~2h GPU) + submit theo cổng mục 6.
4. Cập nhật app + GitHub push sau mỗi mốc (nguyên tắc 7).

---

## 10. REV-2 — BIÊN BẢN REVIEW KẾ HOẠCH (15/9 13:30 UTC, yêu cầu user)

Phạm vi: đối chiếu toàn bộ giả định kỹ thuật của bản kế hoạch này với code
nguồn thật (sjlee101 cell 6, pawanmali cell 10.5, monolith ver-8), dữ liệu mới
(output kernel v8-v2 COMPLETE 09:13), và hạ tầng Kaggle thật (quota, datasets,
metadata kernel). Kết quả: **6 lỗi đã sửa tại chỗ + 7 thiếu sót đã bù + 3 giả
định nguy hiểm nhất đã được kiểm chứng và hoá giải**.

### 10.1 LỖI tìm thấy & đã sửa

| # | Lỗi | Bằng chứng | Sửa |
|---|---|---|---|
| E1 | **Attribution mode HOCT sai** — gán +0.0040 cho mode 1 | Log chạy thật: `HOCT_VETO_ARMED mode=2 (division edges vetoed too)`; header mô tả phép đo "keeping only edges proposed by BOTH linkers" + false divisions 55→29 (chỉ xảy ra khi div bị veto); tên notebook fielded = "-div-b" | v9 mặc định **mode 2**; mode 1 = fallback (§0-A, §2.1, I1/I2 đảo) |
| E2 | Cổng mode 2 "div_tp ≥ +1 mới bật" — **bất khả về toán học** (veto chỉ bỏ cạnh, div_tp không thể tăng) | Cấu trúc phép veto `_hv_apply_veto` chỉ drop | Cổng mới: div_tp(mode2)==div_tp(base) ∧ div_fp giảm ∧ ΔadjEJ ≥ −0.0005 (§6) |
| E3 | Bảng §5 "+0.004…+0.021" trộn baseline v7/v8 | +0.021 = phần re-parent đã bank trong v8 | Δ(v9−v8) = **+0.004…+0.007** (C5, §5) |
| E4 | Đếm input sai "6 cũ + 2 = 8" | kernel-metadata ver-8: **7 dataset_sources** | v9 = **9 input** (A3, Wave-B) |
| E5 | RLF "chỉ dùng cho cạnh NON-division" — sai semantics; chạy RLF TRƯỚC veto làm mất cạnh oan | Cell 10.5 pawanmali: RLF chỉ đụng cạnh division (fork), output-level, SAU CÙNG | RLF chạy SAU veto, port nguyên văn (I3, A3.2) |
| E6 | Hardcode tight55 lạc hậu | v2 PPSWEEP (COMPLETE 09:13) chọn **ppTight5565** proxy 0.9594 | Hardcode per-prefix 5.5/6.5 (A3.3) |

### 10.2 THIẾU SÓT bù thêm

- **O1 — DIVERGE_UM 4.0/4.5** (kimi-v18 LB-peak, comment caassicca-v5; E0 của
  ta từng sweep sai hướng 1.0/1.5) → arm D trong audit A1 + §5.
- **O2 — Timeline/quota tính sai**: PPSWEEP chiếm **6.87/7.95h** kernel v2 →
  v9 lean ≈ 1.5–2h; quota còn 6.93h → **audit + push ver-9 được NGAY HÔM NAY**,
  không cần chờ refresh 19/9 như kế hoạch cũ (C3, timeline).
- **O3 — A1 CPU không khả thi**: HOCT CPU chậm 5–15× T4 → 4.5–13.5h cho ~360k
  nodes → audit A1 chuyển sang GPU mini-kernel ~1.5h (§4).
- **O4 — thiếu nhánh C1b (=0.947 đúng)** cho cây quyết định (Bậc 3).
- **O5 — v2 evidence chưa nhập**: rp-ep50 no-op / rp-ep75 div_fp 2→4 →
  REPARENT_EDGE_PROB giữ 0.25; I4 hạ khỏi EV (O1b, A3.4).
- **O6 — kiểm chứng gap-edge**: submission có **0 cạnh dt>1** → HOCT
  max_delta_t=1 phủ được cấu trúc mọi cạnh — rủi ro lớn nhất của port đã hoá
  giải bằng đo đạc (O6).
- **O7 — stale app/UI**: cập nhật trạng thái v2 COMPLETE + kết quả vào app.

### 10.3 Giả định kiểm chứng OK (không cần sửa) — REV-3 sửa mục 4

1. 2 dataset HOCT (wheels + weights) tồn tại, truy cập được qua API (A2 ✅).
2. Cơ chế veto wrap-write/fail-safe/backup đọc trực tiếp từ cell 6 sjlee —
   port được nguyên văn; 4 video test đều dưới cap 900s (lớn nhất 70,300 nodes
   → 643s dự đoán).
3. RLF pawanmali: chỉ bỏ cạnh con xa hơn, giữ node, audit cấu trúc sau lọc —
   an toàn topology tuyệt đối đúng như kế hoạch đã mô tả.
4. ~~Dev-phase chấm CSV trực tiếp — không rerun hidden test~~ **SAI — REV-3
   13:50**: submission 56242181 fail đúng vì rerun vượt runtime trên hidden
   test LỚN HƠN public (errorDescription + totalBytes=0). Mọi submission đều
   rerun notebook trên hidden test; ngân sách runtime là ràng buộc CỨNG hàng
   đầu (mục C3).
5. Train zarr cho 8 stems có sẵn qua competition input (pattern wave1
   `_wave1_find_train_dir`).

### 10.4 Thuật toán bổ sung (lý thuyết — câu hỏi của user)

| Đòn | Cơ chế | Chi phí | Phán quyết rev-2 |
|---|---|---|---|
| **DIVERGE_UM 4.0/4.5** (kimi-v18) | gate fork chặt hơn (yêu cầu divergence ≥4µm) | ~0 (arm audit) | **ĐI — vào audit A1** |
| SEC_TTA_W=1.0 / DET_THR=0.99 (mtoshidesu/caassicca LB 0.947) | knob trung tính tại operating point | ~0 (arm) | Ghi nhận — chỉ thêm nếu sau refresh còn quota |
| **Erlang division-age hazard** (mở rộng pawanmali "+0.0021 compose Erlang") | feature tuổi-track-từ-chia-cuối cho DivNet ranker — trục thời gian của RLF | thấp (feature graph thuần) | **v9.1 lý thuyết — ghi vào Wave-C** |
| Volume-drop feature (F3) + GT stats p–d 10.4µm / sister 13.7µm | bằng chứng sớm hơn brightness | thấp | v9.1 như kế hoạch cũ |
| Structured softmax link model (F5 +0.005 EJ tiềm năng) | retrain | cao | KHÔNG v9 — private phase |
| SSL pretrain 199 films (tangai1 intel) | retrain | cao | KHÔNG v9 — private phase |
| Cross-movie learned motion repair (indarkarhana) | port + retrain weights | trung bình | Bỏ — LB 0.946 không vượt baseline |
| Division metric exploit (xiaoleilian hub t=−1000) | exploit | ~0 | **TUYỆT ĐỐI KHÔNG** — metric đã vá, rủi ro DQ final |

### 10.5 Kết luận review — REV-3 bổ sung (15/9 13:50)

Kế hoạch v9 về mặt khung (3 đòn A/B/C + audit trước khi tin + cổng submit) là
đúng hướng và giữ nguyên; **cấu hình mặc định sai 1 chỗ quan trọng (mode 2 thay
mode 1), 1 cổng logic bất khả đã được thay, hardcode cập nhật theo v2, timeline
rút ngắn 4 ngày (push được ngay hôm nay thay vì 19/9)**, và thêm được 1 đòn rẻ
(DIVERGE) + 2 hướng lý thuyết (Erlang-age, volume-drop) cho v9.1. EV thực chỉnh
từ "+0.004…+0.021" (lẫn baseline) về **+0.004…+0.007 so với v8** — vẫn đủ vượt
cụm 0.948 nếu v8 ≥ 0.947, và an toàn hơn nhờ fail-safe một chiều nguyên vẹn.

**REV-3 (13:50): v8-v1 (56242181) đã FAIL vì rerun vượt runtime trên hidden

test lớn hơn public ~2× (totalBytes=0, errorDescription rõ ràng). Hệ quả:**
- Rẽ nhánh C1/C1b/C2 (chờ điểm v8) → **chết nhánh chờ**: không có tín hiệu
  LB của re-parent. Mặc định xử lý theo C1b (giữ re-parent +0,008 held-out,
  không bằng chứng hại).
- **Bỏ PPSWEEP là BẮT BUỘC** để submission được chấm — hành động ngay: dựng
  **v8-v3-fast** (ver-8 + hardcode ppTight5565 + sweep 1-2 candidates, public
  ~1,1h → hidden ~2,2h, an toàn) để cứu đầu tư re-parent; v9 = v8-v3-fast +
  HOCT mode 2 + RLF sau khi audit A1 xanh.
- Cảnh báo: submission 56255523 (13:33, không có mô tả — KHÔNG phải tool của
  ta) totalBytes=0 đang PENDING — nếu nó là kernel ver-8 v1/v2 (chứa sweep
  6,9h) thì sẽ fail y hệt sau ~12h; không nộp thêm gì trên kernel chậm.
- Quota hôm nay: đã dùng 3/5 lượt (01:09 + 03:05-deleted + 13:33) → còn 2;
  GPU còn 6,93h đủ cho v8-v3-fast (~1,1h) + audit A1 (~1,5h) + v9 (~2h).

