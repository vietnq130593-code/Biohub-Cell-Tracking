# VER-8 — NGHIÊN CỨU ĐƯỜNG TỚI 0.948+

**Ngày 14/9/2026** · Sau ver-7 = **0.947 Public LB COMPLETE** (ref 56217216)
· Vị trí: **hạng 342/3523**, nằm trong cụm 401 đội (hạng 106–506) cùng điểm 0.947
· Mục tiêu: **≥ 0.948** (cụm kế tiếp: 40 đội, hạng 66–105)

> Nghiên cứu tổng hợp từ **mọi tài liệu đã thu thập**: lịch sử thí nghiệm v10→v30 của
> dòng họ notebook public, VER7-PLAN + Phase B/C, phán quyết ver-7b, discussion #740573,
> CELL5-TRIEN-KHAI §6, kết quả official eval 8 video held-out, PPSWEEP logs, và **3
> notebook nghiên cứu mới** (megayak metric-bug analysis + 2 bản "0.948 Reproduction").

---

## 0. Tóm tắt điều hành

| | |
|---|---|
| Ngân sách GPU | **21,04h còn** (refresh 19/9) — đủ ~9 run T4×2 |
| Lượt submit hôm nay | **4/5 còn** (ver-7 đã dùng 1 lúc 00:10) |
| Deadline | entry **22/9** · chốt final **29/9** |
| Frontier public | vẫn **0.947** (Reyhan — ta đã port = ver-7) |

**5 phát hiện then chốt từ nghiên cứu:**

1. **Đỉnh bảng 0.963–0.966 là HOÁ THẠCH lỗi metric** (megayak chứng minh bằng
   commit): khai thác "weakly connected component + fork giả" đã bị vá ngày
   17/7/2026 (`aa65e90`). Các điểm đó đứng mãi trên LB nhưng **không tái hiện
   được**. Frontier trung thực ≈ 0.947–0.950. → Không đuổi theo 0.966+; mục tiêu
   +0.001→0.948 là đúng tầm.
2. **Điều khoản division đáng tới +0,100 điểm và gần như không ai thu được.**
   ver-7 trên 8 video held-out (official rule, core view): div **0 TP / 0 FP / 12 FN**.
   Trên toàn train (199 video, đo bởi megayak): 151 phân bào GT, gate stack hiện tại
   chỉ để **35/151 (23%) reachable**.
3. **Ràng buộc của division là RANKING, không phải gates** (megayak đo end-to-end):
   mở gate một mình làm điểm XUỐNG (0.9508 → 0.9341) vì budget ~5 fork/khung bị
   rank key hình học (`parent_dist + 0.15×sister_dist`, ưu tiên cặp SÁT NHAU) tiêu
   hết vào **bản sao trùng lặp** (duplicate detections) trước khi chạm phân bào thật.
   ver-7b của ta đã tái hiện đúng triệu chứng này (gate tau 0.6→1.2 → div_fp 1→21,
   proxy −0.013). → Phải mở gate **đi kèm** ranker bằng chứng ML (DivNet đã có sẵn,
   7/7 unit test).
4. **Hai "đường tắt 0.948 public" đều thất bại**: notebook "0.948 Reproduction" của
   zhuzhenghaomax/wzyxp_123 banked cấu hình **0.936** (đã kéo về đọc cell config
   guard); claim của cloudssdut là giả (tác giả best 0.939). Cụm 40 đội 0.948 = **tinh
   chỉnh private** trên nền public 0.947. → Không có đường tắt; phải tự cải tiến.
5. **La bàn đo hiện đọc GẤP ĐÔI** với official rule (validator cũ double-reading
   divJ 0.2 ↔ official 0.125; megayak xác nhận 0.25 ↔ 0.125) và eval cell của ta
   chỉ đo **core view** (raw predictions) chứ không đo **system view** (submission
   thật sau postprocess — thứ LB chấm). → Sửa hệ đo là điều kiện tiên quyết trước
   khi tune division.

**Kết luận chiến lược — 3 đòn song song:**

- **(A) Division evidence-ranking (ver-8 chủ lực)**: DivNet RANK-ONLY + mở gate
  VỪA PHẢI (không như ver-7b) + ngưỡng P_div + ngân sách fork theo bằng chứng.
  Kỳ vọng +0.001…+0.005, tiềm năng lớn nhất (trần +0.100).
- **(B) PPSWEEP-2 mở rộng** trên graph cache qua mini-kernel CPU (0 GPU): sweep
  ~30 configs (per-prefix radii, SYMMETRY_TAU, caps, MIN_TRACK_LEN…) chọn bằng
  official rule + paired guards. Kỳ vọng +0.001…0.003, rủi ro thấp.
- **(C) Sửa hệ đo**: system-view official eval + baseline đồng cứng → mọi quyết định
  chọn config sau này dựa số liệu đúng luật.

---

## 1. Giải phẫu điểm số hiện tại

### 1.1 Phân bố LB (10:25 14/9, 3523 đội)

| Điểm | Số đội | Hạng | Ghi chú |
|---|---:|---|---|
| 0.970 | 1 | 1 | Sergio Alvarez (submit 14/9 — mới) |
| 0.968–0.966 | 4 | 2–5 | vùng điểm hoá thạch/tư nhân |
| 0.965–0.960 | 3 | 6–8 | |
| 0.958–0.950 | 25 | 9–53 | |
| 0.949 | 12 | 54–65 | |
| **0.948** | **40** | **66–105** | **← mục tiêu kế tiếp** |
| **0.947** | **401** | **106–506** | **← chúng ta ở đây (hạng 342)** |
| 0.946 | 177 | 507–683 | |
| 0.945 | 55 | | |

Nhận định: cụm 0.947 = spike fork public Reyhan (VER7-PLAN ghi 360 đội tái hiện;
nay 401). Cụm 0.948 (40 đội) không có notebook public tương ứng → là tinh chỉnh
private. Khoảng cách frontier trung thực (≈0.950) → 0.948 rất hẹp.

### 1.2 Công thức điểm (đối chiếu 3 nguồn, khớp tuyệt đối)

`score = adjusted_edge_jaccard + 0.1 × division_jaccard` (match hai phía ≤7µm)

Đối chiếu: v16 proxy 0.9438 = 0.9238 + 0.1×0.2000 ✓ · v27: 0.9385 = 0.9218 +
0.1×0.1667 ✓ · v28: 0.9417 = 0.9217 + 0.1×0.2000 ✓. Official scorer 075fc5f
tính `proxy_score` đúng công thức này.

**Hệ quả:** divJ tăng +0.10 ↔ tổng +0.01; divJ 0→1.0 = +0.100 điểm. Đây là quỹ
đạo duy nhất còn dư địa lớn.

### 1.3 Hiệu chuẩn proxy ↔ LB (2 điểm thực đo của ta)

- ver-6: validator proxy 0.9430 → LB **0.945** (LB cao hơn +0.002)
- ver-7: validator proxy 0.9490 → LB **0.947** (LB thấp hơn −0.002)

Lịch sử v10→v30 của dòng public: lệch −0.006…+0.001, **3/8 phiên bản proxy↑ mà
LB↓**. → Nguyên tắc đã được xác nhận lần nữa: **không bao giờ quyết định submit
chỉ theo proxy**; phải qua official rule + N video lớn + paired guards.

### 1.4 Bối cảnh private shake-up (giữ nguyên từ VER7-PLAN)

Public LB ≈ 1 phim (29% của 4 phim test); private = 3 phim embryo-disjoint.
401 đội cùng detections → rung lắc final sẽ do (a) sự khác nhau giữ 2 submission
cuối, (b) ai cải thiện division/adjEJ thật. Final: 29/9.

---

## 2. Phân rã lỗi ver-7 (error budget trên 8 video held-out, official rule)

### 2.1 Core view (raw predictions — thứ ILP nhả ra trước postprocess)

| Chỉ số | Giá trị |
|---|---|
| adjEJ micro | 0.9345 (8 video) |
| cạnh tp / fp / fn | 5543 / 191 / 208 |
| **div tp / fp / fn** | **0 / 0 / 12** (100% miss) |
| per-video adjEJ | 6bba_062c8d37 **0.9972** · 44b6_12dfb391 0.9045 · 44b6_267148e4 0.8508 · 6bba_07e24132 **0.8197** |

### 2.2 System view (validator cũ, double-reading, sau postprocess — chỉ để tham khảo)

PPSWEEP base: div 4/24/8 → divJ cũ 0.111 · adjEJ 0.9248. Được chọn:
combo(tight55+dcgap035) adjEJ 0.9259, div 4/21/8. (số ver-7b tương tự vì core
không đổi.)

### 2.3 Các triệu chứng phụ (từ run_stats + retention guard)

- **Over-prediction**: 183k spurious pred nodes trên 8 video validator (~23k/video)
  — nhưng node budget guard G3 ±10% đã giữ; đây là đặc trưng của detector ensemble
  rộng, chưa phải đòn syscall.
- **Retention guard**: video test 44b6_0b24845f **64/100 khung fallback** (hai
  seed bất đồng mạnh, median retention 0.86, min 0.453) — 3 video test còn lại
  0–1 fallback. Đây là điểm yếu cục bộ lớn nhất phía detection.
- **Wrong association = 0** (mọi version!) — linking gần như hoàn hảo; lỗi adjEJ
  nằm ở **detection (missed/spurious)** và **fragmented edges** (5544/8 video),
  không phải ghép sai.

### 2.4 Kết luận phân rã

Quỹ đạo nâng điểm, xếp theo (khoảng trống × khả chạm):

1. **divJ: 0 → 0.3–0.5** = +0.03…+0.05 tổng — quỹ đạo LỚN NHẤT, có bản đồ rõ
   (gates + ranking + budget), có sẵn ranker DivNet + 12 sự kiện held-out để đo.
2. adjEJ: 0.9345 → +0.002…0.005 qua PPSWEEP-2 + per-prefix radii — an toàn hơn,
   cỡ đúng mục tiêu +0.001.
3. Sửa 2 video xấu nhất (0.82/0.85) — chưa rõ nguyên nhân, cần E3 chẩn đoán.

---

## 3. Tổng hợp tri thức từ toàn bộ tài liệu đã thu thập

### 3.1 Lịch sử v10→v30 (pawanmali 0.945 — cha của nền ver-6/7)

Bài học đã kiểm chứng:

- **SEC_DET 0.80 là tối ưu** (0.85 quá tay → missed GT +2, LB −0.003); tương tác
  SEC_DET × BIDIR: 0.80+0.30 → 0.933; **0.80+0.15+EDGE 0.20 → 0.934** (final).
- **Proxy≠LB** (3/8 phiên bản lệch hướng); cụ thể BIDIR↓ làm proxy↑ nhưng LB↓.
- **"Sinh học quan trọng hơn tham số"**: bước đột phá 0.934→0.942 đến từ MỞ GEOMETRY
  phân bào theo số đo GT (SISTER 12→14 vì GT max 14.65; SYMMETRY_TAU 0.6), không
  phải từ vặn ensemble.
- **PPSWEEP của 0.946-work**: chỉ 1 ứng viên sống sót qua sweep (tight 6.0→5.5,
  +0.0021 proxy) — chi tiết đáng nhớ: sweep hầu như không tìm ra gì mới ngoài
  hiệu chỉnh nhỏ; giá trị thật là **chứng minh không còn gì để vặn trong không gian
  tham số cũ**.
- v30 tuyên bố "TTA-fusion link logits (+0.002–0.003)" nhưng **code chỉ làm mức
  feature-map** (CELL5-TRIEN-KHAI §6 #3) → +0.002–0.003 này CHƯA AI THỰC HIỆN.

### 3.2 Discussion #740573 (Lê Quang Cảnh hạng 40 + hengck23) — đo trực tiếp GT

- Bước mẹ→con nằm trọn trong vùng bước thường: **base rate 24:1** (tại 10µm: 38:1)
  → khoảng cách KHÔNG PHẢI tín hiệu phân bào.
- **Sister separation 8.85µm median** (vs 1.72 continuation) = tín hiệu hình học
  mạnh nhất nhưng thuộc tính CỦA CẶP (dùng sau khi đề xuất).
- **Mẹ sáng dần trước khi chia: AUC 0.73** (đỉnh cường độ); con 0.68–0.70.
  Đường sáng mảnh anaphase xuất hiện VÀI KHUNG TRƯỚC khung tách (hengck23).
- **Bẫy đo trên node dự đoán**: median bước trên GT 6.36µm nhưng trên node dự đoán
  8.47µm → tune gate phải trên GT.
- GT theo **segment** (351/572 track bắt đầu muộn/kết thúc sớm) → phát hiện phân
  bào thật nơi GT không nhãn vẫn tính FP → **precision quan trọng hơn recall**.
- Nguồn ngoài **khớp voxel Kaggle**: ultrack zebrafish ome.zarr (train detector
  phân bào ứng viên).

### 3.3 VER7-PLAN Phase C (đã dựng sẵn, còn hiệu lực)

- Ưu tiên 1: DivNet RANK-ONLY (W=15µm) — ver-7b đã chứng minh ranker chạy đúng
  (div_tp 3→4, rank_flips 3–131, p_added 0.21–0.70) nhưng gate nới quá tay.
- Ưu tiên 2: **Per-prefix gating radii** — 6bba disp_p99 7.9µm vs 44b6 4.9µm
  (chênh 1.6×) → gate theo prefix thay vì toàn cục. CHƯA thử.
- Ưu tiên 3: velocity-projected gap closing (topic 739570).
- ĐÃ LOẠI: node-count tuning (zhincez −0.004 sau khi validator hứa +0.013);
  metric hack; nối orphan thành fork.

### 3.4 megayak — phân tích lỗi metric + gate audit (MỚI, quan trọng nhất)

*(notebook đã lưu: `api/research/0948-research/megayak-*.ipynb` + notes.md)*

- **Lỗi metric đã vá 17/7/2026** (commit `aa65e90`): hub node ở t=−1000 nối vào
  gốc mọi track + chuỗi fork giả thỏa "single connected component + contains a
  fork" → mọi phân bào GT có parent + 2 con được match đều đếm TP → divJ≈1.0 →
  0.966. Rule mới: fork phải là parent được match HOẶC kế vị trực tiếp, 2 con phải
  nằm trên 2 nhánh con TRỰC TIẾP của fork đó.
- **Gate audit 151 phân bào GT toàn train** (chỉ đọc .geff, CPU 30 giây): stack
  gate đang ship để **35/151 reachable**; `divergence 2.25µm` nằm ở **median**
  phân bố thật (giết 50%); `symmetry 0.6` ở ~p60.
- **Thí nghiệm mở gate end-to-end**: gates gốc 0.9508 · mở hết (−999/off) 0.9341
  · giữa (0.0/1.2) 0.9354 → mở gate một mình LUÔN tệ hơn. Nguyên nhân: budget
  ~5 fork/khung bị tiêu bởi rank hình học chọn **duplicate detections** (cặp sát
  nhau = bản sao, không phải phân bào).
- **Chẩn đoán vàng**: "Anything that scores a candidate fork on **evidence**
  rather than on how close the two points are should recover this, and **the
  gates have to come open at the same time or there is nothing to rank**."
- Offline div metric của public stack đọc **GẤP ĐÔI** official (0.25 ↔ 0.125).

### 3.5 Trải nghiệm "0.948" của cộng đồng (MỚI — đều thất bại)

- `zhuzhenghaomax/biohub-0-948-reproduction-20260901` — đã kéo + đọc: config
  guard ngân hàng **0.936** (SEW 0.15, SAFE_DIV 7/12 hẹp, preset
  harmonic_v3_division_wide). Thí nghiệm "tái hiện 0.948" thực chất banked 0.936.
- `cloudssdut/…-0-948-reproduction…` — VER7-PLAN đã kết luận claim GIẢ (best 0.939).
- `Rishabh Roy/biohub-948_sew20` (SEW 0.20), `hisatarosu/biohub-948-baseline-repro`
  — cùng thế hệ thử nghiệm, không có bằng chứng đạt 0.948 public.
- Hệ quả: **cụm 0.948 không đến từ notebook public nào** — là private tweaks.

### 3.6 Dòng div-tuning của Seung Jae Lee (chưa khai thác — đề xuất đọc)

`biohub-lb942-divparent12` · `divsister16` · `divboth-12-16` · `divmax-14-18` ·
`divglobalcap` · `divveto015` (6 notebook, 7–8/9) — một người SYSTEMATIC vặn
riêng kho phân bào trên nền 0.942: parent gate 12, sister 16, max 14→18, global
cap, veto 0.15. **Chưa kéo về đọc** — Wave 1 nên kéo + đối chiếu kết quả từng
notebook (mỗi cái là một điểm dữ liệu phép vặn div với validator của họ).

### 3.7 Khoảng trống công nghệ chưa ai làm (tổng hợp)

| Ý tưởng | Nguồn gốc | Bằng chứng | Trạng thái |
|---|---|---|---|
| True link-logit TTA | v30 claim nhưng code chỉ feature-level | claim +0.002–0.003 | **chưa ai thực hiện** |
| Division evidence-ranker trong budget | megayak chẩn đoán | cần rank by evidence | **chưa ai thực hiện** (ver-7b gần nhất, sai calibration) |
| Per-prefix gate radii | VER7-PLAN | 6bba vs 44b6 chênh 1.6× | chưa thử |
| VALIDATOR_N_PER_TYPE 2→4 | 0.942-work dùng 8 | giảm nhiễu chọn | chưa bật (ver-7 vẫn "2") |
| Mẹ sáng dần (AUC 0.73) làm feature ranker | #740573 | đo GT | chưa tích hợp |

---

## 4. CÁC HƯỚNG ĐI MỚI — XẾP HẠNG THEO (KỲ VỌNG × KHẢ THI) / RỦI RO

| # | Hướng | Cơ chế | Kỳ vọng | Cost | Rủi ro & giảm thiểu |
|---|---|---|---|---|---|
| **H1** | **Division evidence-ranking v2 (ver-8 chủ lực)** — DivNet RANK-ONLY, gate mở VỪA PHẢI (tau 0.6→0.8, diverge 2.25→1.5), ngưỡng P_div ≥0.5, tăng role P_div trong rank key (W 15→25), giữ frame/global caps | mở reachable 23%→~45% mà budget tiêu vào chỗ có bằng chứng | **+0.001…+0.005** (trần lớn hơn nhiều nếu div_tp bùng) | 1 run GPU (~2h) + 1 submit | FP nổ như ver-7b → bắt buộc cổng Phase B: div_fp ≤ +3, ΔadjEJ ≥ 0, guards 5/5 |
| **H2** | **PPSWEEP-2 trên graph cache qua mini-kernel CPU** — mở rộng từ 9 configs hiện có lên ~30: per-prefix radii (6bba/44b6), SYMMETRY_TAU {0.4,0.6,0.8}, FRAME_FRAC_CAP, GLOBAL_FRAC_CAP, MIN_TRACK_LEN {5,6,7}, LEARNED_BONUS, GAP_DENSITY_* | mỗi config ~4–5 phút CPU, 0 GPU quota | +0.001…0.003 | 0 GPU (mini-kernel) | chọn sai vì proxy↔LB lệch → chỉ nhận khi official-rule 8-video + guards đồng thuận |
| **H3** | **Sửa hệ đo: system-view official eval** — eval cell đo submission .geff THẬT (sau postprocess) bằng official rule, kèm baseline ver-6 đông cứng; kèm VALIDATOR_N_PER_TYPE=4 cho các run sau | mọi quyết định H1/H2 dựa đúng luật | điều kiện tiên quyết | 0 GPU (đã có pattern biohub-eval-v6) | — |
| **H4** | Per-prefix gating radii (gộp vào H2) | 6bba disp_p99 7.9µm vs 44b6 4.9µm | +0.001? | 0 GPU (trong sweep) | quá khớp validator → margin rule như PPSWEEP Reyhan |
| **H5** | True link-logit TTA (chỉ cặp cạnh gần gate) | +0.002–0.003 (claim chưa ai làm) | +0.002? | 1 run GPU | chi phí ×8 edges → chỉ near-gate; cần so fp32 |
| **H6** | Chẩn đoán 2 video xấu nhất (0.8197 / 0.8508) | tìm error mode riêng (dense? mờ?) | không trực tiếp +điểm, mở hướng | 0 GPU | — |
| **H7** | Per-dataset secondary weight cho 44b6_0b24845f (retention 64% fallback) | hai seed bất đồng ở đúng video test này | +0.001? | 1 run GPU | rủi ro overfit 1 video |
| **H8** | Đọc 6 notebook div-tuning của Seung Jae Lee | bản đồ "vặn gì xảy ra gì" của người khác | thông tin | 0 | — |
| **H9** | External data (ultrack zebrafish) train division model riêng | nguồn voxel-khớp | +0.005+ nếu thành | 2–3 ngày, nhiều run | muộn cho deadline 22/9 entry; để private phase |

**Không làm (đã loại khỏi roadmap, tái khẳng định):** metric hack mọi biến thể
(hub/fork giả — vừa vô hiệu vừa rủi ro DQ); node-count tuning; săn public-LB
micro-delta <0.005.

---

## 5. KẾ HOẠCH THỰC NGHIỆM — 3 WAVES

### Wave 1 — CPU, 0 GPU quota (làm NGAY hôm nay)

**E0. Gate-audit ver-8 trên 199 train .geff** (mini-kernel CPU, pattern
`biohub-eval-v6 v3` — đã có support-pack + pip offline):
đọc GT .geff, mô phỏng từng tổ hợp gate (tau ∈ {0.6, 0.8, 1.0, 1.2} × diverge ∈
{2.25, 1.5, 1.0, 0.0}) × rank key (geometry thuần vs `+W×P_div` với DivNet
checkpoint đã có) → bảng "số phân bào reachable / số duplicate lọt budget" cho
từng tổ hợp. Kết quả = chọn calibration H1 bằng số liệu, không đoán.
*Đầu ra: báo cáo audit + tổ hợp gate tối ưu.*

**E1. Sửa eval cell → system-view official** (dùng bản đã vá path từ Task 35):
đo submission .geff thật + baseline ver-6 (dataset heldout-preds đã có) bằng
official rule trên 8 video → chốt "la bàn không đọc đôi".
*Đầu ra: eval_report_official_system_v7.json + paired A/B baseline.*

**E2. PPSWEEP-2** (mini-kernel CPU, tái dùng graph cache .geff từ run ver-7
đã có trong output/latest): sweep ~30 configs (mục 4-H2/H4), chọn bằng
official rule + 5 guards + margin rule.
*Đầu ra: ppsweep2_results.csv + danh sách overrides đạt guards.*

**E3. Chẩn đoán 2 video xấu nhất** từ held-out .geff: phân rã FP/FN/fragmented
theo khung & mật độ.
*Đầu ra: ghi chú nguyên nhân + có/không hướng xử lý rẻ.*

**E4. Kéo 6 notebook div-tuning của Seung Jae Lee** về repo research (0.5h).

### Wave 2 — 1 run GPU (~2h) + 1 submit (chỉ khi Wave 1 xanh)

**ver-8 = ver-7 + calibration tốt nhất từ E0/E2:**
DivNet RANK-ONLY (W 15→25 tuỳ E0) · gate tau 0.8 / diverge 1.5 (tuỳ E0) ·
`BIOHUB_DIVNET_MIN_PROB 0.5` · frame/global caps giữ nguyên · PPSWEEP-2
overrides đạt guards · VALIDATOR_N_PER_TYPE=4 · eval cell bản đã vá (tự chấm
system-view + baseline trong run).

**Cổng submit (Phase B v2 — siết hơn ver-7b):**
- official system-view: ΔadjEJ ≥ −0.0005 (gần như không được mất)
- div_tp ≥ +2 và div_fp ≤ +3 (trên 8 video held-out)
- guards 5/5 (G1 div_fn, G2 div_fp, G3 node budget stem chung, G4 per-video
  sụt ≤0.010, G5 paired integrity)
- ELEVEN rule: Δproxy ≥ +0.005 mới submit tự tin; 0.001 ≤ Δ < 0.005 → chỉ cân
  nhắc khi div_tp tăng rõ (mục tiêu +0.001 nhỏ nhưng noise proxy↔LB ±0.006)

### Wave 3 — tuỳ chọn (quota còn, sau ver-8)

- H5 true link-logit TTA near-gate
- H7 per-dataset secondary weight 44b6_0b24845f
- H9 external data (chỉ nếu còn thời gian sau 22/9)

### Trục thời gian

| Ngày | Việc |
|---|---|
| 14/9 (hôm nay) | Wave 1 toàn bộ + (nếu xanh) Wave 2 push + submit |
| 15–18/9 | Wave 3 + cải tiến vòng sau theo số liệu E-series |
| 19/9 | GPU quota refresh (thêm 30h) |
| 22/9 | **deadline entry** — mọi version dự tính final phải có ≥1 submission hợp lệ |
| 29/9 | chốt 2 final submission (kế hoạch: ver-7 port + bản division tốt nhất nếu đạt) |

---

## 6. Nguyên tắc thực nghiệm (tổng hợp mọi bài học)

1. **Không metric hack** — hoá thạch 0.966 không tái hiện; rule đã vá; rủi ro DQ.
2. **ELEVEN rule** — Δ ≥ 0.005 mới tự tin submit; nhỏ hơn phải qua thêm lý do
   độc lập (div_tp tăng, sinh học giải thích được).
3. **Không tin proxy một mình** — 3/8 phiên bản lệch hướng; mọi chọn lựa qua
   official rule + N video lớn + paired bootstrap + guards.
4. **Tune trên GT, không tune trên output** (bẫy 6.36 vs 8.47µm).
5. **Mở gate phải đi kèm ranker bằng chứng** (megayak + ver-7b cùng một tiếng).
6. **Sinh học > tham số** (v28: geometry theo số đo GT thắng vặn ensemble).
7. **Mọi artifact sống trên Kaggle** (kernel + dataset + submission); GitHub
   push ngay sau mỗi đợt (bài học rollback ×2).
8. **Không săn public-LB micro-delta** — public = 1 phim, nhiễu chi phối.

---

## 7. Nguồn tài liệu (toàn bộ trong repo)

| Nguồn | Vị trí |
|---|---|
| Lịch sử v10→v30 + bảng proxy/LB | `kaggle/ver-5/original-analysis-notes.md` |
| Phân tích cell 5 + 8 cải tiến xếp hạng | `kaggle/ver-5/CELL5-TRIEN-KHAI.md` (§6) |
| Kế hoạch ver-7 + Phase C | `kaggle/ver-7-planning/VER7-PLAN.md` |
| Phán quyết ver-7b (gate quá tay) | `kaggle/eval/reports/ver7b-phase-c-verdict.md` |
| A/B ver-7 vs ver-6 official | `kaggle/eval/reports/ver7-vs-ver6-official.md` |
| Official eval self 8 video | `kaggle/api/output/latest/eval_report_official_self.json` |
| PPSWEEP ver-7/7b | `kaggle/api/output/latest/ppsweep_*.json/csv` + `eval/reports/ppsweep_*.csv` |
| Retention guard | `kaggle/api/output/latest/dual_seed_frame_retention_guard_report.json` |
| Insight GT #740573 | `kaggle/README.md` (mục Insight) |
| **megayak metric-bug analysis (MỚI)** | `kaggle/api/research/0948-research/megayak-*` |
| **0.948 Reproduction (thất bại) (MỚI)** | `kaggle/api/research/0948-research/{zhuzhenghaomax,cloudssdut}-*` |
| DivNet ranker + unit test 7/7 | `kaggle/ver-7b/` (tái dùng cho ver-8) |
