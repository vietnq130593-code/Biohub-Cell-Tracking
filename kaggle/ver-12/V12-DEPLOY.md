# V12-DEPLOY — Triển khai ver-12 (portfolio 4 trục)

## 🚀 RUN 2 — v12.1 KNOCKOUT biohub-ver12 v2 (21/9 tối — user: "tiếp tục công việc đang dở")

**[GPU WASTE CHECK]** ✅ Chạy này là production (sinh submission.csv cho đợt submit
tiếp theo) — không phải thí nghiệm. Vượt cần (necessary): E1 CSV surgery KHÔNG nộp
được trực tiếp (submission phải là output kernel — tiền lệ L1/400 "Did not find
provided Notebook Output File") → knockout cấp kernel là con đường ĐÚNG duy nhất.
CPU thay thế: KHÔNG CÓ. GPU ước 0.77h (RUN 1 receipt; giảm thêm chút vì không dump
lowdet). Sổ: 15.14h → ước ≤15.91h/30h.

**Cơ sở quyết định (đáp ứng kỷ luật user "tốt hơn mới nộp")**: E1 receipt composite
**0.9173 > v12 0.9128 > v11 baseline 0.9010** — knockout READMIT/GAPFILL giải quyết
tension HOLD của RUN 1 (adjEJ −0.0025 nhưng composite +0.0118): bỏ node thêm giữ
nguyên TP+1 division (t=24 05db) + BỚT 1 division FP (1/2/2 → 1/1/2) + hết hại 3
stem thưa.

**Config v12.1 = RUN 1 giữ nguyên 4 trục, chỉ tắt node-addition (env-gated có sẵn
từ lúc viết v12 — không đụng code):**

| env | RUN 1 | RUN 2 (ko) | hiệu ứng trong monolith |
|---|---|---|---|
| `BIOHUB_READMIT_RADIUS_UM` | 4.0 | **0.0** | line 3178/3949 gate `<= 0` → readmit idle |
| `BIOHUB_GAPFILL_MAX_GAP` | 3 | **0** | line 3224 gate `< 1` → gapfill idle |
| `BIOHUB_LOWDET_THRESHOLD` | 0.5 | **0.0** | predict dump `_LOWDET_THRESHOLD > 0` → không dump |
| (pool load) | — | — | line 3123 early-return khi cả 2 off → không đọc pool |

Giữ: reparent EP=0.4 · orphan-adopt=1 floor=0.5 · diverge=−2.0 · SEF_TTA w=0.75 ·
DC=0.2 · validator=OFF. Tag: `…reparent_hoct_v12_portfolio_d2_divm2_ko` (tiền tố
v12 giữ cho submit-v12.py PASS).

**Receipt build local (0 GPU)**: diff monolith RUN 1 ↔ RUN 2 = đúng 6 dòng (3 env +
tag + guard-report + receipt print) — submission-path code byte-identical ·
determinism 3× rebuild md5 `8ee517bcdae7c4ea92aa88f70afa9f7b` · selftest v12lab
PASS (readmit 1 / gapfill 3n+4e / orphan 1·1 / INT/DAG — selftest tự override env
4/3 cho đồ thị tổng hợp nên vẫn đo được hàm) · notebook regenerate 355KB 23 mấu +
guard 9 hằng · config RUN 1 lưu `ver-12-config.run1.json`.

⚠ **Kỳ vọng vs đo thật**: v12.1 (kernel-level) ≠ E1 (CSV surgery) ở hiệu ứng bậc 2 —
node thêm của RUN 1 từng hiện diện trong safe-div/reparent processing; kỳ vọng ≈ E1
± nhỏ. Lab replica không re-run: trong lab READMIT/GAPFILL đã no-op từ draft-2 (thiếu
dump hidden) → cấu hình này đã đo 0.8990/0.9053 — không thông tin mới. Sự thật do
**replica-gate trên output GPU** phán.

**TRẠNG THÁI: push v2 → poll đồng bộ → pull → replica-gate → bảng so sánh cuối
v11/v12/v12.1 → CHỜ LỆNH SUBMIT TRỰC TIẾP.**

### ✅ KẾT QUẢ RUN 2 — COMPLETE ~37' wall · GPU 15.14h → 15.85h = 0.71h

Config live (receipt log): `READMIT r=0.0um · GAPFILL gap<=0 · lowdet>=0.0 ·
readmitted=0/gapfill=0 trên 4 dataset · lowdet dir VẮNG (dump off) · diverge=-2.0 ·
orphan-adopt=1 · DC=0.2 · validator=OFF` · 241.201 dòng (v11: 241.119 · v12 RUN 1:
244.004).

### Bảng so sánh cuối (cổng replica GT khôi phục — engine verify 100% alfonso)

| chỉ số | v11 (0.947 LB) | v12 RUN 1 | **v12.1 RUN 2** | E1 (CSV surgery) |
|---|---|---|---|---|
| replica adjEJ | 0.9010 | 0.8985 | **0.8998** | 0.8973 |
| replica divJ | 0.0000 | 0.1429 | **0.1429** | 0.2000 |
| **COMPOSITE (metric LB)** | 0.9010 | 0.9128 | **0.9141** | 0.9173 |
| div cửa sổ TP/FP/FN | 0/1/3 | 1/4/2 | **1/4/2** | 1/2/3 |
| census n/e/fork | 122.787/118.332/144 | 124.194/119.810/189 | **122.808/118.393/184** | — |
| per-stem adjEJ | .8683/.9372/.9636/.8590 | .8680/.9353/.9621/.8559 | **.8683/.9372/.9625/.8577** | — |

- Knockout hiệu quả đúng hướng: 0113 + 0b24 hồi phục CHÍNH XÁC bằng v11 (0.8683/
  0.9372) — node thêm là nguyên nhân hại 2 stem thưa của RUN 1. v12.1 = +0.0013
  composite so RUN 1 (0.9128→0.9141), nhưng E1 hứa +0.0045 → **hiệu ứng bậc 2 ăn
  70% kỳ vọng** (node thêm từng hiện diện trong processing của RUN 1).
- VERDICT cổng (tiêu chí adjEJ nguyên văn): HOLD — 0.8998 < 0.9010 − 0.0005.
  Composite-với-composite: **+0.0131**. Cổng giữ nguyên semantics (không đổi sau khi
  thấy kết quả — F6, user trọng tài). Deficit adjEJ tập trung 05b6 (−0.0011) +
  05db (−0.0013) = tác dụng phụ division FP.

### 🔬 FP ANATOMY (0 GPU — fp-anatomy2.py, semantics chính thức evaluate_divisions)

4 division FP của v12.1 (05b6 t=28/37 · 05db t=55/75) + 1 TP (t=24 05db):

| sự kiện | p1/p2 (µm) | sister | sym | divergence | GT nói | nguồn gốc |
|---|---|---|---|---|---|---|
| **TP t=24** 05db fork 20106 | 2.96/5.70 | 8.38 | 0.634 | +2.52 (gate-time −1.79) | CHIA (GT div) | **diverge −2.0** (F1 receipt) |
| FP t=37 05b6 fork 2750 | 4.00/2.87 | 6.76 | 0.328 | +2.93 | tuyến tính | **pre-existing v11** (banked 0.947) |
| FP t=28 05b6 fork 2168 | 4.16/5.17 | 9.31 | 0.216 | +1.24 | tuyến tính | safe-div mới (node 2232 v11 bị prune) |
| FP t=55 05db fork 44876 | 2.60/3.83 | 3.98 | 0.383 | n/a (con hết track) | tuyến tính | mới (orphan-adopt khả nghi nhất) |
| FP t=75 05db fork 59486 | 4.89/5.34 | 10.03 | 0.088 | +1.75 | tuyến tính | mới (DC 0.25→0.2 khả nghi) |

Phát hiện quan trọng (run_stats đối chiếu v11 ↔ v12.1):
1. **reparent EP 0.4 = NO-OP trên production**: reparent_added GIỐNG HỆT 12/19/3/43
   ở cả 2 bản — trục 1b không tạo tác dụng gì (candidates 1634→1648 nhưng added
   không đổi). Fork t=28 KHÔNG phải từ reparent (đoán đầu sai) — từ safe-div.
2. **+40 fork deltas = toàn bộ trục safe-div** (diverge −2.0 + orphan + DC):
   divergence_rejected 2.812 (v11) → 365 (v12.1); safe_divisions_added 82 → 123.
3. **Không có separator hình học sạch**: TP có symmetry CAO NHẤT (0.634) — ngược
  trực giác; sister/divergence FP trộn lẫn với TP. Mọi ngưỡng diệt FP đều đe doạ TP
   hoặc mù (post-hoc ≠ gate-time — divergence TP đo sau là +2.52 nhưng gate-time
   là −1.79 vì đồ thị đổi sau khi gate chạy).
4. pdiv/dc dumps (v11_lab_cache) MẤT theo sandbox reset → replay toàn gate không
   thể — attribution chỉ còn cấu trúc + counters (đã làm ở trên).

### 💡 Quyết định đề xuất (user là trọng tài)

- **Khuyến nghị: SUBMIT v12.1** khi user ra lệnh. Lý do: (a) composite +0.0131 —
  lớn nhất từ trước tới nay; (b) TP t=24 là GT THẬT trong phim test → chuyển giao
  LB chắc chắn; (c) census lành (không purge, gần baseline); (d) thông tin LB
  (divJ transfer) CHỈ có thể học bằng cách nộp — replica mù ngoài cửa sổ 1.6%;
  (e) 0.947 banked vẫn selectable — rủi ro downside bị chặn; (f) quota 5/ngày,
  deadline còn 8 ngày — submission không khan hiếm.
- Nếu LB về < 0.947 (divJ transfer yếu/FP-heavy): bài học = FP:TP ratio trên GT
  dày tệ hơn cửa sổ thưa → v12.2 ứng viên đã có tên: orphan-adopt OFF (−3 fork
  05db, khả năng giết t=55) + DC 0.25 (khả năng giết t=75) + giữ diverge −2.0.
- Nếu LB về ≥ 0.948+: xác nhận cơ chế division hoạt động — hướng tiếp theo là mở
  rộng recall division (FN còn 2/3 cửa sổ).

**PRE-SUBMIT dry-run: INT PASS (241.201 dòng) · DAG PASS (118.393 cạnh t→t+1) ·
CENSUS L12 PASS (122.808n/118.393e/184f — fork ≥100 guard PASS) · TAG PASS
(+5 counters mới) → submit được NGAY khi có lệnh.** KHÔNG submit khi chưa có
lệnh trực tiếp (luật đứng).

## 🚀 RUN 1 — production biohub-ver12 v1 (21/9 — PAT mới của user, lệnh "triển khai v12 lên GPU")

**COMPLETE ~53 phút wall · GPU sổ 14.37h → 15.14h = 0.77h/run** — VALIDATOR=OFF (port
andnyu REVIEW-3) hiện thực hoá: 2.2h → 0.77h. Core log ~46 phút, experiment_tag
`secondary_deepcenter_tta_0947_reparent_hoct_v12_portfolio_d2_divm2`.

Config live (receipt log): reparent EP=0.4 · orphan-adopt=1 floor=0.5 · READMIT r=4.0µm
s≥0.965 (866 node: 82/335/64/385) · GAPFILL gap≤3 (131n + 189e) · LOWDET dump stage
chạy (lowdet/*.npz) · SEF_TTA w=0.75 · DC=0.2 · validator=OFF · diverge=−2.0.
Validator artifacts VẮNG trong output (ppsweep_results/validator_results bị xoá — đúng).

### Kết quả cổng replica (GT 84 file khôi phục lại — fix paging CLI 2.x commit 9dc29d1)

| chỉ số | v11 baseline (ref 56403231) | v12 RUN 1 | Δ |
|---|---|---|---|
| replica adjEJ | 0.9010 | 0.8985 | −0.0025 |
| replica divJ | 0.0000 | 0.1429 | +0.1429 |
| **COMPOSITE (metric LB = adj+0.1·divJ)** | **0.9010** | **0.9128** | **+0.0118** |
| census n/e/fork | 122.787/118.332/144 | 124.194/119.810/189 | +1,15%/+1,25%/+45 fork (không purge) |
| div 05db TP/FP/FN | 0/0/3 | **1/2/2** | TP+1 · FN−1 |

- Per-stem adjEJ v11→v12: 0113 0.8683→0.8680 · 0b24 0.9372→0.9353 · 05b6 0.9636→0.9621
  (div FP 1→2) · 05db 0.8590→0.8559.
- **VERDICT gate (tiêu chí adjEJ như thiết kế): HOLD** — 0.8985 < 0.9010 − 0.0005.
  TENSION minh bạch: baseline 0.9010 là COMPOSITE v11 (divJ=0 nên adj=composite); LB
  metric = adjEJ+0.1·divJ → so composite-với-composite thì v12 **+0.0118 TỐT HƠN**.
  Không đổi semantics cổng sau khi thấy kết quả — user là trọng tài (F6).
- **E1 knockout (0 GPU, CSV dựng local: v12 bỏ 1.563 node thêm)**: composite 0.9173
  (adj 0.8973 · divJ 0.2000 · 05db 1/1/2). Division TP+1 KHÔNG phụ thuộc node thêm;
  node thêm hại 3 stem thưa nhưng giúp stem dày 05db (+0.0039) — khớp hướng receipt
  thtennant trên GT dày → trên LB khả năng DƯƠNG (hình phạt cửa sổ thưa khả năng artefact).
- PRE-SUBMIT dry-run: INT PASS · DAG PASS (119.810 cạnh t→t+1) · CENSUS L12 PASS ·
  TAG PASS (+5 counters mới) → **submit được luôn khi có lệnh** (persist ≥20' thoả).
- **TRẠNG THÁI: CHỜ LỆNH SUBMIT CỦA USER.** Phương án (A) submit v12 nguyên bản
  (khuyến nghị — xem worklog V12-RUN-1) hoặc (B) v12.1 knockout READMIT/GAPFILL
  (env-gated · +0.75h GPU · kỳ vọng replica ≈ E1 0.9173) rồi mới submit.

## 🔍 REVIEW-3 (23/9 — receipt v11 = 0.947 + phân tích notebook andnyu 0948-repro)

**v11 ref 56403231 = 0.947 (user xác nhận 21/9)** — bắng v10 banked, không vượt 0.948.

Đối chiếu notebook `andnyu/biohub-density-adaptive-0-948-reproduction` (public 21/9,
21m47s T4×2, **điểm thật 0.945 V1**) với kiến trúc v12:

| Thành phần andnyu | Trạng thái trong v12 | Quyết định |
|---|---|---|
| DivNet 3D mitosis veto (p<0.50) | **DEAD CODE trong chính notebook họ** — `BIOHUB_OUTPUT_DIVISION_GEOMETRY_FILTER` không bao giờ set (mặc định 0) → `divnet_score_division()` có đúng 1 call-site trong block bị gate OFF; trùng receipt batch-A "haideptry DivNet = NO-OP" | KHÔNG port veto; giữ divnet RANK-ONLY như v11 |
| Density-group overrides (tight 7.25/6.5/5.5 theo node/frame <120/<400) | Ta đã có per-prefix {44b6:5.5, 6bba:6.5} (E2 +0.0003) — reproduction đạt 0.945 < 0.947 | KHÔNG port mặc định; backlog A/B đơn-knob 05b6→7.25 |
| GAP2 / GAP_DENSITY_ADAPTIVE / DC 0.25 / DC_TTA / bonus 1.0 | **đã có sẵn trong ver-10/11 của ta từ trước** (diff env ver-11 monolith) | không đổi |
| reparent Phase D + mn_p85_div05 + p_div floor | **thiếu trong andnyu** (base cũ hơn cả ver-10 ta) — partly why 0.945 | lợi thế của ta |
| **VALIDATOR_ENABLE=0 (Fast mode)** | ver-11/v12 ta: validator mặc định ON — nhưng `PP_CANDIDATES = {}` (rỗng) → sweep không bao giờ chọn/rewrite submission → **validator = ~90 phút GPU no-op mỗi run production** (receipt andnyu 21m47s end-to-end + thtennant precedent) | **PORT — đây là phát hiện đáng giá nhất: v12 giờ tắt validator, submission byte-identical** |
| Dual T4 sharding, batch 8, CUDNN cap | Ta đã có dual-T4 sharding từ ver-11; batch 4→8 KHÔNG chắc byte-identical | giữ batch 4 (kỷ luật "submit được luôn"); runtime kỳ vọng 2.2h → **~0.5-0.75h** |

→ Verdict: notebook không có kỹ thuật scoring nào đánh bại v12 (0.945 < 0.947, DivNet
trang trí, density-group âm tính) — nhưng bày cho ta **cách tắt 90 phút GPU thừa**.
Build v12 cập nhật: +1 dòng env `BIOHUB_VALIDATOR_ENABLE='0'` (diff toàn bộ monolith
chỉ 1 env + 1 print — mọi đường submission giữ nguyên); selftest PASS; determinism
PASS (md5 ổn định qua rebuild); notebook 355KB regenerate; final-env assertion 22 key.

## 🔍 REVIEW-2 (22/9 — pre-GPU rà soát toàn diện "submit được luôn")

**Bối cảnh**: sandbox bị reset giữa chừng (repo local + ~/.kaggle + /home/z/v11-recovery mất)
→ clone lại từ GitHub `vietnq130593-code/Biohub-Cell-Tracking` (đầy đủ tới commit f46363f
"v12 WRITE + LAB"). Review lượt 2 đối chiếu code build vs script THẬT trích từ git history
(`d523f9f:kaggle/api/output/latest/tracking_repo/scripts/predict_unet_transformer.py`,
971 dòng — bản v10-out đã patch chạy thật trên Kaggle).

**3 vấn đề tìm ra — ĐÃ SỬA + XÁC MINH (commit này):**

1. 🔴 **BUG env-ordering (nghiêm trọng — âm thầm)**: block `[ver12]` Phase H được chèn
   sau print `[ver11]` nhưng block `[ver8]` reparent chạy SAU nó → `BIOHUB_REPARENT_EDGE_PROB`
   bị ghi đè **0.4 → 0.25** — trục 1b tắt âm thầm, config ≠ thực tế chạy. SỬA: chèn block
   v12 SAU CÙNG mọi block env legacy (sau `BIOHUB_DIAGNOSTIC_ARM`) + builder thêm mới
   **final-env-value assertion 21 key** (mọi key v12 phải là assignment cuối file —
   hồi quy kiểu này sẽ fail build ngay).
2. 🔴 **ktool.py thiếu ver-12**: `version_config()` không có nhánh "12" (rơi về ver-6!)
   + argparse choices chặt `--ver 12`. SỬA: VER12_NOTEBOOK/DATASETS(=9 ver-11)/SLUG
   `biohub-ver12` + 7 choices + nhãn submit — `push --ver 12` giờ resolve đúng.
3. 🟡 **không có submit-v12.py**: submit-v11 hardcode ver-11. TẠO MỚI
   `kaggle/api/submit-v12.py`: cổng PRE-SUBMIT tự động (INT / DAG t→t+1 / census
   per-dataset L12 đối chiếu ver-11 122.787n/118.332e/144f / run_stats tag v12 +
   counters mới) rồi mới gọi kagglesdk — test sống trên output cũ: INT/DAG/census PASS,
   cổng TAG chặn đúng output v10 (hành vi an toàn mong muốn).

**Đối chiếu ngữ nghĩa đã xác minh (chống rủi ro crash GPU — ngoài anchor/compile):**

- `det_logits: list of W × (1,1,Z,Y,X)` (script thật dòng 378-379) → `_lg =
  det_logits[f_idx][0][0]` = (Z,Y,X) 3D — index `[z,y,x]` của LOWDET **ĐÚNG** (lo ngại
  ban đầu về tensor 2D không xảy ra).
- 3/3 anchor LOWDET khớp script v10-out thật; vùng patch ver-11 == ver-10 (byte-exact)
  → state script tại lúc patch LOWDET chính là bản đã chạy COMPLETE trên Kaggle.
- `name`/`downsample` ở scope module-level của save-point (dòng 834 `for name in
  tqdm(test_names)`; `*= downsample` mirror đúng `*= ds_arr` trong predict_video).
- `motion_edges` là tập cạnh ĐẦY ĐỦ (dòng 3953-3955 `edges = motion_edges` thay toàn
  bộ) → READMIT anchors on track end/start đúng ngữ nghĩa thtennant.
- CSV writer `int(round())` + max(0,·) (L5 PASS); cạnh luôn t→t+1 (DAG cấu trúc);
  guard 9 numeric + 6 text khớp config, không có entry DIVERGE → −2.0 không vạ guard.
- rerank unpack theo index + `*prop[6:]` (7-tuple ổn); `_v12_orphan` reset mỗi vòng
  candidate; stats init đủ 12 key mới; sha256 verify chạy TRƯỚC patch động; env trước
  subprocess launch (LOWDET env tới shard ✓); thiếu dump → non-fatal idle (resume an toàn).

**Xác minh sau sửa**: build lại (5.541 dòng) + final-env PASS 21 key (EP=0.4 cuối cùng,
  diverge=−2.0 cuối cùng) + v12lab selftest PASS (readmit 1/gapfill 3+4/INT/DAG/orphan
  1+1) + determinism (rebuild == rebuild) + notebook regenerate (cell == monolith,
  355KB) + ktool `--ver 12` resolve đúng.

**Cần trước khi push Kaggle (sandbox mới)**: (a) user cấp lại token —
`python3 kaggle/api/ktool.py token '<token>'`; (b) `pip install kagglesdk` (submit-v12
đáng tin hơn CLI file submit đã bị 400). GPU ước tính giữ nguyên ≤6.6h dự phòng.

## ⛽ GPU WASTE CHECK — bắt buộc (GPU-WASTE-PREVENTION.md §4)

- **GPU ước tính: ≤2.5h** (tối đa 3 lần production × ~0.75h — REVIEW-3 tắt validator
  no-op ~90 phút/run; trước ước 6.6h) + **0h thí nghiệm** — toàn bộ
  thí nghiệm v12-lab đã chạy LOCAL CPU-only hôm nay (21/9): selftest + validator replay
  8 stems (198s/config) + hidden instrumented 4 phim (~90s/config) + replica — **0 GPU đã dùng**.
- Cách CPU: trích env-block/constants/post-chain/scoring từ monolith v12 → exec namespace
  + shim pdiv/dc pre-baked (npz v11-lab v2) → replay + gate-flip + replica scorer2code.
- PRE-GPU đã pass (L2 smoke): [x] build must_count + AST + py_compile [x] LOWDET patch
  mô phỏng áp lên bản sao predict script v10-out (3 anchor match, script vẫn compile)
  [x] v12lab selftest PASS (orphan-adoption + READMIT + GAPFILL + INT/DAG trên đồ thị
  tổng hợp) [x] validator replay fidelity: adjEJ 0.929415 vs anchor D2 0.930492 (Δ−0.0011)
  + error-signature khớp EXACT (missed_gt 63, spurious ~183k, edges_lost_det 79)
  [x] guard _EXPECTED_NUMERIC 9 hằng đúng config.
- PRE-SUBMIT (khi tới lượt — CHƯA tới): [ ] kernel COMPLETE + persist ≥20' [ ] INT/DAG
  [ ] census theo dataset (L12) [ ] run_stats tag + counters mới (readmitted_nodes,
  gapfill_*, safe_division_orphan_*) [ ] **CỔNG REPLICA (REVIEW-3 mới — ý user:
  "chạy thử xong so sánh, tốt hơn mới nộp"): `python3 kaggle/api/replica-gate.py --pull`
  → verdict SUBMIT-ELIGIBLE mới được cân nhắc (adjEJ replica ≥ baseline v11 0.9010 +
  margin, HOẶC division cửa sổ 05db TP>0; census forks ≥100 + nodes ±5%)** [ ] quota
  5/ngày [ ] v10 banked 0.947 còn selectable
  [ ] **lệnh submit trực tiếp của user** (luật đứng — KHÔNG tự nộp).
- Chính sách fork: KHÔNG purge (L6 = 0.911). Census kỳ vọng 144 → ~150+ (chỉ được thêm).
- Rollback: v10 banked 0.947 (ref 56348119) luôn selectable — KHÔNG đụng.
- Lỗi cũ có nguy cơ (đối chiếu L1-L12): L1 lab≠production — v12-lab LOCAL không push
  kernel lab; L2 smoke trước mọi thay đổi — xong; L3 persist 20' — khi submit; L5 commit
  ngay — xong; L6 không purge; L7 replica/validator chỉ lọc, LB trọng tài (F6); L8 0 GPU
  thí nghiệm — xong (0h); L9 KHÔNG watcher nền — poll đồng bộ; L12 census theo dataset.
- Cam kết sau hoàn thành: commit ngay + cập nhật sổ GPU §1 (0h hôm nay) + postmortem nếu dưới base.

## 1. Ver-12 là gì (1 đoạn)

Ver-12 = ver-11 (đang chấm ref 56403231) + **portfolio 4 trục có receipt** — mỗi trục
env-gated để A/B: (1b) reparent mở gate EP 0.25→0.40 + sweep config; (1c) orphan-adoption
exception sửa "tấm màn" gate divergence + floor p_div riêng; (1c') **SAFE_DIV_DIVERGE_UM
0.5→−2.0** (cho phép con hội tụ — receipt đo được hôm nay: replica +0.0067, TP hidden
+1, FP −4); (2) READMIT + GAPFILL port thtennant batch-B (+1.014 node/+1.002 cạnh hidden)
+ LOWDET dump stage mới trong predict script; (3) SEF_TTA/DC config-driven.

## 2. Artefact (kaggle/ver-12/)

| File | Vai trò |
|---|---|
| `build-ver12-monolith.py` | Builder 16 thay đổi từ ver-11 → cell-monolith.py (must_count mọi anchor + AST + py_compile) |
| `ver-12-config.json` | Config draft-2 (portfolio_d2_divm2) + **lab_receipts đầy đủ** (mọi quyết định kèm chứng đo) |
| `cell-monolith.py` | Monolith v12 đã build (5.542 dòng sau REVIEW-3 +validator-off; ver-11: 5.107) |
| `make-ver12-ipynb.py` | Đóng gói notebook (23 mấu + guard 9 hằng) → download/ver12-cell-tracking.ipynb (355KB) |
| `v12lab.py` | **V12-LAB CPU-ONLY** (Phòng lab 1 REVIEW-1 redesign): selftest / validator / hidden --flips / replica |
| `V12-DEPLOY.md` | File này (kèm REVIEW-2 + 3 fix) |
| `../api/ktool.py` | Push/watch/submit CLI — ver-12 support (REVIEW-2 fix) |
| `../api/submit-v12.py` | Submit v12 + cổng PRE-SUBMIT tự động (REVIEW-2 mới) |
| `../api/replica-gate.py` | **REVIEW-3 mới** — cổng replica pre-submit (pull output → restore GT → chấm → verdict SUBMIT/HOLD) |

## 3. Kết quả phòng lab hôm nay (21/9 — 0 GPU, ~35 phút CPU)

| Thí nghiệm | Kết quả | Kết luận |
|---|---|---|
| selftest (đồ thị tổng hợp) | readmit 1 node · gapfill 3 node + 4 cạnh · orphan exempted 1/adopted 1 · INT/DAG PASS | code 3 đường mới chạy đúng |
| validator anchor (v11-equivalent) | adjEJ 0.929415 div 5/3/7 vs Kaggle D2 0.930492 div 4/1/8; missed_gt 63 · edges_lost_det 79 khớp EXACT | replay engine fidelity ±0.001 — đủ cho A/B tương đối |
| hidden base (draft-1, geo-mode) | div 0/10/3 (khớp replica ver11 receipt 0/3) | graph 05db tái lập đúng trạng thái ver-11 |
| **gate-flip: diverge −2.0** | **05db div 0/10/3 → 1/6/2 (TP+1 FP−4)**; replica 4 phim: adjEJ +0.0004, divJ 0→0.0625, **REPLICA +0.0067**; 0b24 adjEJ +0.019 | **knob division mạnh nhất đo được — vào config draft-2** |
| gate-flip: divergence OFF | 1/12/2 — cùng TP nhưng FP gấp đôi diverge −2.0 | từ chối — quá đục |
| gate-flip: orphan-adoption | exempted 55/adopted 6-7, TP 0 — t=24 KHÔNG cần nó (có successor!) | giữ ON floor 0.5 (thận trọng) |
| gate-flip: reparent geo EP 0.50 | reparent_added 234 nhưng t=52/t=62 VẪN FN (cha sai 0.0-1.4µm — 'weak-edge' không kích hoạt được) | **kỳ vọng trục 1b HẠ xuống ~0** — sai-gán-cha có cha sai quá gần |
| trace 3 GT div (F1 instrumented) | t=24: mồ côi 20908 CÓ successor; diverge = −1.79µm < 0.5 → chặn ở ĐO divergence; t=52/62: unrecoverable bằng post-chain | **root-cause thật khác giả thuyết ban đầu — instrumented replay đáng giá** |

⚠ **TENSION phải biết trước khi submit**: diverge −2.0 trên validator replay = adjEJ
−0.0006 / FP +4 (F1 validator FAIL) nhưng 3-GT-div-05db PASS + replica PASS (+0.0067).
Bài học veto1 (validator +0.0018 → LB 0.000): transfer validator→LB yếu cả 2 chiều.
Quyết định cuối theo F6: **LB là trọng tài** — nếu submit v12, diverge −2.0 là thay đổi
lớn nhất cần A/B (submit v12-divm2 rồi so v11; nếu thua → rebuild diverge 0.5).

## 4. Luồng triển khai (khi được lệnh — CHƯA tự động)

```
1. (tuỳ chọn) v12-lab vòng 2: grid thêm {SEF_TTA 1.0, DC 0.25, τ 0.4, DIV_PARENT 12}
   — mỗi config 198s CPU local: python3 kaggle/ver-12/v12lab.py validator --env K=V
   (⚠ REVIEW-2: /home/z/v11-recovery đã mất theo sandbox reset — cần khôi phục dump
   rawgraphs/pdiv/dc từ git history hoặc chạy lại lớp validator trước khi grid)
2. Chọn config thắng theo gates F1-F6 → ghi lại ver-12-config.json → python3 build-ver12-monolith.py
3. python3 make-ver12-ipynb.py → push Kaggle kernel biohub-ver12 (ktool push --ver 12)
4. Kernel **~0.5-0.75h GPU** (REVIEW-3: validator no-op đã tắt; READMIT/GAPFILL
   +CPU-phút) → poll ĐỒNG BỘ trong lệnh Bash (L9):
   python3 kaggle/api/ktool.py watch --ver 12
4b. **CỔNG REPLICA PRE-SUBMIT (REVIEW-3, ý user 21/9 — bắt buộc trước khi xin lệnh
   submit)**: `python3 kaggle/api/replica-gate.py --pull` — tự khôi phục test-gt
   (84 file GT từ competition files API — sandbox reset 21/9 đã mất /home/z/v11-recovery)
   → chấm replica → so baseline v11 (0.9010): SỤT → giữ quota nghiên cứu tiếp;
   TĂNG/division TP → SUBMIT-ELIGIBLE. (⚠ replica mù ngoài cửa sổ GT thưa 1.6% —
   verdict là điều kiện CẦN; quyết định cuối thuộc user)
5. PRE-SUBMIT TỰ ĐỘNG: python3 kaggle/api/submit-v12.py --dry-run (INT/DAG/census/tag)
   → CHỜ LỆNH SUBMIT CỦA USER (bỏ --dry-run)
```

## 5. Sổ GPU (trung thực, cập nhật sau mỗi lần chạy)

| Ngày | Hạng mục | GPU |
|---|---|---|
| 20/9 (tích lũy) | ver-10/11 production + lab cũ | 15.1h/30h |
| **21/9** | **viết ver12 + v12-lab 3 lớp + replica** | **0.0h** ✅ |
| **23/9 (REVIEW-3)** | phân tích andnyu 0948-repro + validator-off + cổng replica | **0.0h** ✅ |
| **21/9 RUN 1 (PAT mới)** | biohub-ver12 production ×1 COMPLETE ~53' (validator OFF) | **0.77h** (14.37→15.14) |
| **21/9 RUN 2 (v12.1 knockout)** | biohub-ver12 v2 COMPLETE ~37' (validator OFF + không dump lowdet) + FP anatomy 0 GPU | **0.71h** (15.14→15.85) |
| (dự phòng) | v12.2 iterate ×≤1 (~0.71h/run) — chỉ khi LB dạy điều gì đó mới | ≤0.71h |
