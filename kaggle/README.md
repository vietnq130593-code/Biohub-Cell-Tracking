# Registry phiên bản bài nộp — Kaggle "Biohub - Cell Tracking During Development"

Mỗi lần thay đổi thuật toán nộp bài = **một phiên bản (ver)**. Code của từng cell
được lưu tại `ver-N/cell1code.py` … `cell4code.py` — dán đè cell tương ứng của
notebook Kaggle gốc rồi **Save & Run All → Submit**.

> Quy ước: cell1code = Cell 1 (imports) · cell2code = Cell 2 (siêu tham số) ·
> cell3code = Cell 3 (pipeline chính) · cell4code = Cell 4 (xuất submission.csv).
> Cell 1 và Cell 4 gần như bất biến; mọi thay đổi thuật toán nằm ở Cell 2 + Cell 3.

**Bảng điểm** (Kaggle public LB):

| ver | tên | điểm Kaggle | ngày |
|---|---|---:|---|
| 0 | Baseline (getting-started) | — (chưa submit) | — |
| 1 | Stage 0+2 | **0.198** | 13/09/2026 |
| 2 | Chống gộp blob + phân bào xác nhận | soạn thảo ✓ | — |
| 3 | Phân bào theo profile độ sáng (từ discussion #740573) | soạn thảo ✓ | — |
| 4 | Stitching hậu kiểm (nối lại track đứt) | soạn thảo ✓ | — |
| 5 | Fork giải pháp ML 0.945 — cell 5 ver 5.1 nâng cấp | nghiên cứu ✓ + nâng cấp ✓ | — |
| 6 | Ensemble 2 lượt + retention guard | **0.945** ×2 deterministic | 13/09/2026 |
| 7 | Port monolith Reyhan 0.947 + Phase B official eval | **0.947** ✓ (hạng 342/3523) | 14/09/2026 |

## Hotfix — NameError STRUCT26 (rơi trên Kaggle 13/09/2026)

**Hiện tượng**: Cell 3 báo `NameError: name 'STRUCT26' is not defined` tại
`label(mask, structure=STRUCT26 if CONN26 else None)` trong `detect_nodes`.

**Gốc rễ**: `STRUCT26 = np.ones((3, 3, 3), dtype=bool)` từng nằm ở **dòng đầu
tiên của Cell 3** — khi dán đè cell, dòng đầu dễ bị rơi (chọn nhầm vùng dán /
clipboard cắt đầu) → biến toàn cục biến mất nhưng vẫn được tham chiếu sâu bên
trong `detect_nodes`. Số dòng traceback lệch đúng 18 dòng so với file gốc
chứng tỏ bản dán thiếu đầu cell.

**Vá**: xoá biến toàn cục `STRUCT26`, chuyển cấu trúc 26-liên kết vào **trực
tiếp** trong lệnh `label()` của `detect_nodes`:
```python
labeled, n = label(mask, structure=np.ones((3, 3, 3), dtype=bool) if CONN26 else None)
```
Áp dụng cho `ver-1/`, `ver-2/`, `ver-3/` và `download/stage0plus2-kaggle-4cells.py`;
regenerate 3 file ipynb (ver2/ver3/stage0plus2). Kiểm chứng lại: ver-3
**21/21 ĐẠT** + ver-2 **ĐẠT TẤT CẢ** — Cell 3 giờ **tự chứa**, dán thiếu dòng
đầu không còn gây NameError.

**Vá nhanh trên notebook đang chạy** (không cần dán lại): thêm 1 dòng vào đầu
Cell 3:
```python
STRUCT26 = np.ones((3, 3, 3), dtype=bool)
```

## Hotfix 2 — NameError maximum_filter (rơi trên Kaggle 14/09/2026)

**Hiện tượng**: Cell 3 ver-4 báo `NameError: name 'maximum_filter' is not
defined` tại `mf = maximum_filter(smoothed, size=PEAK_SIZE)` trong
`detect_nodes` — ngay khung đầu của dataset đầu.

**Gốc rễ**: traceback khớp **từng dòng** file gốc (offset 0) → cell 3 được dán
đúng nguyên văn. Vấn đề nằm ở chỗ cell 3 **thiếu import** — nó trông chờ
cell 1 import `maximum_filter` (chỉ được thêm từ ver-3), nhưng notebook Kaggle
đang giữ **cell 1 bản cũ** (chưa từng có `maximum_filter`) trong khi cell 2/3
đã dán ver-4. Test cục bộ không bắt được vì harness chạy `cell1code.py`
(trong đó có import) trước khi exec cell 3.

**Vá (mức gốc)**: cell 3 ver-4 giờ **tự chứa hoàn toàn**:
- khối **IMPORT TỰ CHỮA** đầu cell (import lại vô hại, kèm thông báo rõ nếu
  thiếu blosc2);
- khối **CẤU HÌNH MẶC ĐỊNH ver-4** chỉ áp khi cell 2 ver-4 **chưa** chạy
  (cờ `PIPELINE_CONFIG_VERSION` cuối cell 2) và chưa ai tự đặt `DATA_DIR` →
  dán đè **đơn lẻ** cell 3 vào notebook giữ cell 1/2 cũ vẫn chạy đúng núm
  ver-4; cell 2 ver-4 đã chạy thì núm tune ở đó vẫn thắng.
- cell 4 tự import `pandas` (cùng cơ chế).

**Kiểm chứng lại**: `test-ver4-synth.py` **ĐẠT TẤT CẢ 28+3** — thêm 3 kiểm
**TỰ CHỨA**: chỉ exec cell 3+4 trong namespace trống (không cell 1/2, mô phỏng
đúng sự cố) → chạy được **và cho submission y hệt từng hàng** so với chạy đầy
đủ cell 1+2+3; `test-ver4-train-eval.py` E2E vẫn **1.1000**. Script sinh
notebook được giữ lại: `ver-4/make-ver4-ipynb.py` (2 ipynb trong `download/`
đã regenerate).

Top 1 (Sergio Alvarez) = **0.97** · top 10 ≈ 0.957 — khoảng cách còn rất lớn.

**Nguyên tắc rút ra từ điểm 0.198 + đọc kỹ metric chính thức** (repo
`royerlab/kaggle-cell-tracking-competition`):
1. **Node recall là đòn bẩy lớn nhất**: TP ~ r² (cả 2 đầu cạnh đều phải khớp ≤ 7 µm),
   còn phạt node thừa rất nhẹ (`adjEJ = EJ·(1 − 0.1·(N_pred−N_true)/N_true)`).
2. **Cạnh FP chỉ bị tính khi bám vào node GT** (nguồn khớp GT-có-cạnh-ra hoặc
   đích khớp GT-có-cạnh-vào) — cạnh giữa tế bào chưa được chú thích bị bỏ qua.
3. **Cạnh nhảy t→t+k bị metric bỏ hẳn** (không TP) → nội suy node giữa là bắt buộc.
4. **Fork (≥2 cạnh ra) = phân bào** theo metric; fork giả là division FP →
   mỗi fork phải được xác nhận bằng động học.

## Insight từ discussion #740573 (Lê Quang Cảnh · hạng 40 + hengck23)

Đo trực tiếp trên **73 file nhãn train** (36 phân bào có nhãn, 25.661 cạnh
continuation, 72 cạnh phân bào, 572 track) — không phải dự đoán:

### a) Khoảng cách mẹ→con KHÔNG phải tín hiệu phân bào (bài học lớn nhất)

| Loại bước (µm/khung) | n | median | IQR | p99 | max |
|---|---:|---:|---|---:|---:|
| continuation | 25.661 | 1,72 | 0,91–2,19 | 6,91 | 18,7 |
| mẹ→con (division step) | 72 | 4,57 | 3,30–6,21 | 10,6 | 12,3 |
| **2 con gái (sister sep.)** | 36 | **8,85** | 7,20–10,24 | 13,9 | **14,65** |

- IQR của bước phân bào nằm **gần trọn trong vùng bước thường** → gate khoảng
  cách đủ rộng để bắt median phân bào (≥5µm) thì cũng thu 722 bước thường,
  **24:1 base rate** (tại 10µm: 38:1). *"Thất bại là base rate, không phải
  vùng chồng lấn chỉnh gate được."*
- **Sister separation là tín hiệu hình học mạnh nhất** (8,85 vs 1,72µm) nhưng
  là thuộc tính của CẶP — chỉ dùng được sau khi đề xuất cặp.
- **Bẫy đo trên node dự đoán**: cùng phân bào đó, median bước trên nhãn 6,36µm
  nhưng trên node dự đoán 8,47µm (max 13,65) — sai số định vị detector cộng
  dồn qua 2 đầu cạnh. **Tune gate phải trên nhãn GT, không tune trên output
  chính mình.**

### b) Tín hiệu APPEARANCE (ngoại hình) — mẹ sáng lên trước khi chia

- Đỉnh cường độ (peak intensity) của mẹ tại khung tách phân biệt khỏi tế bào
  thường ở **AUC 0,73** (con ở t+1..t+3: 0,68–0,70); local contrast 0,55–0,69.
- Độ "mỏng/dài" (elongation) KHÔNG phân biệt (AUC ≈ 0,34–0,58 = random) —
  có thể vì nhìn trễ 1–2 khung (hengck23: **đường sáng mảnh ở anaphase xuất
  hiện VÀI KHUNG TRƯỚC** khung tách là manh mối rất tốt).
- hengck23: nhiều phân bào **chưa được gắn nhãn** trong data Kaggle — "hiếm
  khi chỉ 1 tế bào phân bào"; nhưng trên 36 phân bào có nhãn, các mốc tách
  **không cluster** (spread median 32 khung/phim).

### c) Cấu trúc nhãn GT (ảnh hưởng cách đọc metric)

- **Mọi cạnh GT nối đúng 1 khung** (25.661/25.661 — không có skip edge) →
  nội suy node ở khung mất (ver 2) là đúng hướng.
- Nhãn theo **segment, không theo lineage trọn đời**: 351/572 track bắt đầu
  sau frame 0, 391 kết thúc trước frame cuối, median 35 khung → 36 phân bào
  chỉ là **tập con được gắn nhãn** → phát hiện phân bào thật nơi GT không nhãn
  vẫn tính FP → **precision division quan trọng hơn recall**.

### d) Nguồn ngoài + tham chiếu ultrack

- **Dữ liệu ngoài KHỚP voxel Kaggle** (1,625/0,40625/0,40625 — đúng hệ):
  `https://public.czbiohub.org/royerlab/ultrack/zebrafish_embryo.ome.zarr/`
  — shape (522, 1, 505, 2170, 2217) uint16, cùng chế độ chụp → ứng viên
  train detector phân bào (cần tải thành Kaggle Dataset, kiểm tra rules).
  ⚠️ Bộ ZSNS001–005 (single-objective) có voxel 1,24/0,439/0,439 — KHÁC Kaggle.
- Config ultrack zebrafish: `max_distance 10.0`, `max_neighbors 5`, penalty
  appear/disappear/division rất nhỏ (0,001–0,1); fork công khai chỉnh
  division 1,2 / disappear 1,5 **không bao giờ tối ưu** được.
- Tool xem dữ liệu: napari (crop ROI quanh node t−10..t+10); focus3d hỗ trợ
  human-in-the-loop annotation. "Lặp lại thí nghiệm Figure 6 của paper ultrack
  là chìa khóa" (hengck23).

### e) Áp dụng vào pipeline của ta

| Hành động | Lý do |
|---|---|
| `SIBLING_GATE` 12 → **14,5µm** | max quan sát 14,65 — gate 12 bỏ lỡ ~10% cặp chị em |
| `PARENT_GATE` 10 → **12µm** | bắt p99 (10,6) bước mẹ→con |
| **Mới — kiểm tra "ổn định khối lượng mẹ"**: khối lượng blob mẹ tại khung tách ≤ ~1,7× baseline riêng của nó | merge-split giả: blob gộp 2 tế bào ≈ 2× đơn; phân bào thật chỉ sáng lên nhẹ (AUC 0,73) |
| Giữ nội suy + xác nhận động học | GT 100% cạnh liền khung; base rate 24:1 |
| Phân bổ công lực: 90% cho adjEJ (trọng số 1,0) — division chỉ 0,1 | Kể cả hạng 40 cũng hỏi "tín hiệu gì chạy được division > 0" |

## ver 7 — Port monolith Reyhan 0.947 + Phase B official eval (PUBLIC LB 0.947 ✓)

- 14/09/2026 · submission ref **56217216** → **PUBLIC LB = 0.947 CHÍNH XÁC KỲ VỌNG (+0.002 so với ver-6)** · hạng 342/3523 (cụm 401 đội 0.947, hạng 106–506) · kernel `vietnguyen130593/biohub-ver7`
- Port nguyên khối monolith LB 0.947 của Reyhan (vá 5 nhóm path pilkwang), TTA 3 view, PPSWEEP tight55 — không đổi thuật toán, chỉ verify từng bước theo `ver-7-planning/PORT-CHECKLIST.md`
- Run T4×2 117 phút (21:40→23:36) · 0 lỗi · submission.csv 241.356 dòng (sha256 `d34533806b3153dd…`) · retention guard sạch (metric_hack=False)
- **Phase B rà soát (checklist A–H)**: official eval self 8 video held-out → adjEJ micro **0.9345** (div 0/0/12) · baseline ver-6 chấm lại bằng mini-kernel CPU `biohub-eval-v6` 4 video → adjEJ micro **0.9201** (xác nhận double-reading divJ 0.2 của rule cũ) · `eval/compare.py` paired A/B trên 4 video chung: ΔadjEJ **+0.0000** (CI95 ±0.0001), guards 5/5 → không regression
- 3 bug phát hiện & vá trong rà soát: (1) eval cell path mount `datasets/<owner>/<slug>`; (2) compare.py G3 so node budget trên stem chung; (3) mini-kernel gắn support-pack + pip offline `--no-index --no-deps`
- File: `ver-7/cell-monolith.py` · `ver-7/make-ver7-ipynb.py` · `download/ver7-cell-tracking.ipynb` · `ver-7-planning/{VER7-PLAN, PORT-CHECKLIST, REVIEW-PHASE-B}.md` · `eval/{cell-eval-official.py, compare.py}` · `eval/reports/ver7-vs-ver6-official.md`
- **ver-7b (Phase C)** — DivNet RANK-ONLY W=15µm + nới gate tau 0.6→1.2 / diverge 2.25→1.0: div_tp 3→4 nhưng div_fp 1→21 → proxy 0.9511→0.9380 = regression → **KHÔNG nộp** (phán quyết `eval/reports/ver7b-phase-c-verdict.md`; hướng v2: giữ gate gốc + RANK-ONLY)
- **Mục tiêu ver-8: ≥ 0.948** (cụm 40 đội hạng 66–105) — nghiên cứu đầy đủ `ver-8-planning/VER8-RESEARCH.md` (phát hiện chính: đỉnh 0.966+ là hoá thạch lỗi metric đã vá 17/7 — megayak; điều khoản division đáng +0.100, hiện 0 TP/12 FN; ràng buộc là RANKING không phải gates; cụm 0.948 là private tweaks)

## ver 6 — Ensemble 2 lượt phát hiện + retention guard (LB 0.945 ×2 deterministic)

- 13/09/2026 · đã submit ×2: ref **56207468** (13:03) + **56210873** (16:18) — đều **0.945 COMPLETE**, khớp tuyệt đối → deterministic
- 2 lượt phát hiện độc lập (seed khác nhau) → fusion theo src → Hungarian 7,2µm → safe-div động học → retention guard 3,6 + 0,4×gap
- Validator proxy 0.9430 · adj_edge_jaccard 0.9230 · division_jaccard 0.2000 (điểm yếu đã biết → ver-7b nhắm đúng div_fn=12)
- Retention worst 0.453 @ video 44b6_0b24845f frame 95 · 65/400 frame fallback
- File: `ver-6/` (cell1..10code.py + README — **phục hồi byte-exact từ kernel Kaggle 14/9** sau khi rollback xoá local) · `download/ver6-cell-tracking.ipynb` (sha256 `22bbd49af25c87af…`)
- Bài học: hai lần chạy deterministic cùng ra 0.945 — tín hiệu tin được; mọi artifact quan trọng phải sống trên Kaggle (kernel + dataset + submission), local chỉ là bản sao

## ver 5 — Fork giải pháp ML 0.945 (nghiên cứu cell 5) + VER 5.1 nâng cấp cell 5

- **Nguồn**: `ver-5/` · notebook gốc: `pawanmali/biohub-942proxy-fork-v1` (public 0.945,
  GPU T4×2, 36 phút, internet tắt) — **bản sao mổ xẻ của public work 0.923
  "Dual-Seed + Harmonic Bidirectional Fusion"**, nâng qua v28 (0.942) → v29 → v30.
  Pipeline: TemporalUNet3D + Node Transformer + ILP (pyscipopt) + DeepCenter veto +
  dual-seed (seed 314159) + TTA 8 hướng + bidirectional harmonic fusion.
- **Tài liệu**: `ver-5/CELL5-TRIEN-KHAI.md` — triển khai đầy đủ section 5 (patch suy
  luận + dự đoán song song 2 GPU): 6 bản vá string-patch, CSDL env, bảng cải tiến xếp
  hạng (PPSWEEP / VALIDATOR_N_PER_TYPE / true logit-TTA / division model / fp16 /
  bền hóa patch chain) + **mục 9: bản nâng cấp ver 5.1**.
- **Nền đã copy**: `original-biohub-942proxy-fork-v1.ipynb` (nguyên vẹn 29 cell) ·
  `cell5-foundation-verbatim.py` (section 5 nguyên văn — đã diff khớp notebook gốc
  từng byte) · `original-analysis-notes.md` (lịch sử thí nghiệm v10→v30).
- **VER 5.1 (15/09, Task 21) — `cell5code.py` bản nâng cấp cell 5**, chỉ thay đổi phần
  điều phối, **payload 6 patch giữ nguyên từng byte** (trích bằng AST khỏi file nền,
  test T2 chứng minh file vá ra giống hệt bản nền):
  1. **Hai pha verify-then-write** — anchor hỏng thì dừng TRƯỚC KHI GHI (bản nền ghi
     đĩa tuần tự, hỏng giữa chừng để file vá dở — đối chứng test T5); patch 1 được
     fail-fast hoá như 5 patch kia.
  2. **Re-run an toàn** — script đã vá đủ (6 marker) thì bỏ qua khối vá, chạy thẳng
     dự đoán (không cần chạy lại S4).
  3. **Tôn trọng env S1** — 4 env (`RETENTION`, `EDGE_FEATURE_TTA`, 2 secondary) đổi từ
     ghi đè cứng sang `setdefault`; tune giờ chỉ cần sửa S1 (bản nền bỏ qua giá trị S1
     — đối chứng test T8).
  4. **Preflight manifest** (cấu hình hiệu dụng trước khi chạy) + **tổng hợp retention
     guard** ngay trong cell (không đợi S7) + throughput.
  - Kiểm chứng: `ver-5/test-ver5-cell5.py` — **57/57 ĐẠT** (mock dựng từ anchor thật,
    torch/subprocess giả, luồng 1 GPU + 2 GPU đầy đủ).
  - Tool lắp ráp: `ver-5/make-ver5-upgrade.py` (giữ vĩnh viễn, tái sinh được).
- **Hội tụ với ver-3/4 của ta**: SAFE_DIV_SISTER 14µm ↔ DIV_SIBLING_GATE 14.5 ·
  parent mid-track ↔ C1 · SYMMETRY_TAU/mass ↔ mass-stability · GAP_CLOSE ↔ stitching.
- **Bước tiếp theo**: Copy & Edit notebook gốc trên Kaggle → Add 4 Input (competition +
  3 dataset `pilkwang`) → GPU T4×2 → **thay cell "## 5." bằng `ver-5/cell5code.py`
  (ver 5.1)** → Save & Run All (~36 phút) → Submit. Kỳ vọng ≈ 0.94x (ver-1 = 0.198).
  Sau đó mới thêm `BIOHUB_VALIDATOR_N_PER_TYPE=4` + PPSWEEP theo tài liệu §6/§8.

## ver 4 — Stitching hậu kiểm (nối lại track đứt)

- **Nguồn**: `ver-4/` · **kiểm chứng**: `ver-4/test-ver4-synth.py` — **ĐẠT TẤT CẢ
  28+3** (đối chứng stitch TẮT: 3 kịch bản đứt đều hỏng; +3 kiểm tự chứa sau
  hotfix 14/09) + `ver-4/test-ver4-train-eval.py`
  — E2E chạy notebook `download/ver4-train-eval.ipynb` trên synthetic có nhãn
  .geff: **score 1.100/1.100** (EJ 1.0 · divJ 1.0 · recall 1.0)
- **Bối cảnh**: chẩn đoán ver 3 trên test — trung vị 2–3 node/track (GT: 35
  khung/track) · ~20% node mở đầu track · 3 cơ chế nối có sẵn đều bỏ sót:
  1. gate thích ứng bị kẹp [5,14] — p99 bước GT = 6,9 µm → min 5 giết bước hợp lệ
  2. frame-skip chỉ ≤ MAX_SKIP khung VÀ dự đoán pos+vel·gap phải ≤ SKIP_GATE 12 µm
     — tế bào quẹo khi mờ làm dự đoán trượt
  3. blob gộp > MAX_SKIP khung: track bạn đồng hành chết hẳn (pending hết hạn)
- **Nâng cấp**:
  1. `GATE_MIN_UM 5 → 7` (p99 bước GT) · `MAX_SKIP_FRAMES 2 → 3`.
  2. **MỚI — `stitch_tracks()` chạy sau mỗi dataset**: mọi track kết thúc ở
     khung t (node không có cạnh ra) + track mở đầu ở khung t+gap (node không
     có cạnh vào) trong gate `10 + 2·(gap−1) µm` (gap ≤ 5) và
     `|ln khối lượng| ≤ 1,1` (~3×) → **Hungarian toàn cục theo nhóm** → gap ≥ 2
     chèn node nội suy, nối chuỗi cạnh **LIỀN KHUNG** (không bao giờ cạnh nhảy).
  3. `STITCH_COLLISION_UM = 0` (tắt kiểm tra đụng node trên đường nội suy):
     hành lang nối blob-break đi đúng qua node CoM của track bạn đồng hành;
     metric tự merge-collapse cạnh trùng nên chuỗi song song không tạo FP cạnh,
     node thừa chỉ bị phạt nhẹ (hệ số 0,1).
- **Vì sao an toàn**: stitch không bao giờ tạo fork (end có out-degree 0 → 1,
  start có in-degree 0 → 1) · chỉ chạy khi 2 đầu hợp gate + khối lượng ·
  cạnh nhảy không tồn tại (chuỗi nội suy) · con của phân bào đã xác nhận có
  cạnh vào nên không bị nối nhầm.
- **Dùng**: dán 4 cell `ver-4/` vào notebook Kaggle, hoặc Import
  `download/ver4-cell-tracking.ipynb`. Từ hotfix 14/09, **dán đè đơn lẻ cell 3
  cũng chạy** (tự import + cấu hình mặc định ver-4). Đo điểm offline: Import
  `download/ver4-train-eval.ipynb` (cell 2 đã trỏ `DATA_DIR` vào train,
  chạy xong tự chấm bằng port metric chính thức — xem mục Local scorer).

## ver 3 — Phân bào theo profile độ sáng (từ discussion #740573)

- **Nguồn**: `ver-3/` · **kiểm chứng**: `ver-3/test-ver3-synth.py` — **21/21 ĐẠT**,
  kèm đối chứng ver 2 trên cùng dữ liệu: ver 2 xác nhận nhầm merge-split khéo
  (FP) và bỏ sót phân bào chị-em-xa; ver 3 chặn cái đầu (mass) bắt cái sau
  (gate 14,5)
- Tri thức mới (đo trên nhãn train thật — xem mục Insight ở trên):
  1. **`DIV_SIBLING_GATE_UM` 12 → 14,5**: sister separation p99 = 13,9, max
     = 14,65µm — gate cũ bỏ lỡ ~10% cặp chị em thật.
  2. **`DIV_PARENT_GATE_UM` 10 → 12**: bắt p99 bước mẹ→con (10,6, max 12,3);
     khoảng cách chỉ còn là *cửa sổ tìm kiếm*, không phải tín hiệu (base rate
     24:1 — filter thật là sáng + động học + bảo toàn).
  3. **Mới — "ổn định khối lượng mẹ"** (`DIV_MOM_MAX_RISE = 1,7`): track theo
     dõi khối lượng (mass) từng node; baseline = trung vị ~8 giá trị gần nhất
     (loại 2 khung cuối — đúng lúc sáng lên). Blob mẹ tại khung tách mà
     ≥ 1,7× baseline riêng = **blob gộp 2 tế bào** (merge-split ≈ 2×) → từ
     chối ứng viên phân bào. Phân bào thật chỉ sáng lên nhẹ (AUC 0,73) và
     blob gộp FULL cũng không tách được bằng đỉnh → đây là cửa chặn chính.
     Track non < 4 khung (chưa đủ baseline) → bỏ qua kiểm tra này.
  4. **Mới — "mẹ sáng lên" ưu tiên ứng viên** (`DIV_MOM_BRIGHT_BONUS`): ứng
     viên có mẹ sáng dần (mass tại tách / baseline ≥ 1,05) xếp trước trong
     danh sách cạnh tranh — tín hiệu appearance (AUC 0,73) mạnh hơn hình học.
  5. **Bug fix khi kiểm chứng — con kế thừa vận tốc MẸ** (không phải vectơ
     mẹ→con): vectơ mẹ→con làm dự đoán khung sau vọt xa → con không match →
     ứng viên chết "lost" và bị đề xuất lại MỖI KHUNG (vòng lặp vô hạn trên
     dữ liệu kiểm chứng). Latent bug này cũng có trong ver 2 nhưng bị che bởi
     gate hẹp (10µm) — trên Kaggle nó âm thầm giết các ứng viên phân bào.
  6. Giữ nguyên lõi ver 2: tách blob theo đỉnh + xác nhận động học ≥3 khung
     + nội suy khung mất + P90/MAX 3000 + gate 5–14µm + skip 2 khung.
- Kỳ vọng: bắt thêm phân bào chị-em-xa (ver 2 bỏ sót) và chặn thêm
  merge-split khéo (2 tế bào đi ra xa dần sau khi tách — vượt được kiểm tra
  động học của ver 2 nhưng blob mẹ ≈ 2× đơn bị bắt bởi mass stability).

## ver 2 — Chống gộp blob + phân bào xác nhận (soạn thảo, đã kiểm chứng synthetic)

- **Nguồn**: `ver-2/` (đồng bộ `download/ver2-cell-tracking.ipynb`) · **kiểm chứng**:
  `ver-2/test-ver2-synth.py` — **16/16 ĐẠT** trên Zarr tổng hợp
- 6 nâng cấp so với ver 1 (theo 4 nguyên tắc trên):
  1. **P92 → P90, MAX_NVOXELS 1000 → 3000**: tăng recall (đòn bẩy r²), phạt node
     thừa chỉ 0.1 nên đáng đổi
  2. **Tách blob gộp "eo"**: component > 90 voxel có ≥ 2 đỉnh
     `maximum_filter` cách ≥ 4 voxel ds → cắt thành 2+ node (CoM riêng từng vùng,
     gán voxel → đỉnh gần nhất). Lưu ý: blob "gộp đầy" (2 Gaussian chồng lấp
     < ~2.4σ, vùng giữa sáng hơn đỉnh yếu) KHÔNG tách được — phải chờ tế bào
     đi ra hoặc dùng watershed/DoG (Stage 1)
  3. **MAX_SKIP_FRAMES 1 → 2 + SKIP_GATE 12 µm**: phục hồi track đứt dài hơn
     (nội suy node giữa → cạnh liền khung, không bao giờ cạnh nhảy)
  4. **GATE_MAX 12 → 14 µm, BASE 8 → 9**: bắt tế bào nhanh
  5. **Phân bào xác nhận động học** (cốt lõi): cạnh divergence được HOÃN; chỉ
     ghi khi 2 con cùng sống ≥ 3 khung (`DIV_CONFIRM_FRAMES`) VÀ khoảng cách
     tăng ≥ 15% (`DIV_SEP_GROWTH`) so với lúc "sinh". Merge-split giả (2 "con"
     ở xa ngay từ đầu, đứng yên) bị từ chối → chặn division FP. Cạnh vẫn là
     cạnh liền khung (mẹ t−1 → con t) khi được xác nhận
  6. **Chẩn đoán mỗi dataset**: %node không cạnh vào, số track, trung vị độ dài
     track, phân bào xác nhận/từ chối — so trực tiếp với số liệu ver 1
- Bug đã sửa khi kiểm chứng: xác nhận phân bào từng bị reject ngay trong chính
  step tạo candidate (c1/c2 chưa từng là "prev" → `succ` rỗng) — vá bằng đếm tuổi
  riêng cho candidate vừa tạo
- Kỳ vọng (chưa đo): tăng recall + giảm phân bào giả → mục tiêu 0.3+; cần
  local scorer (dưới) đo chính xác TRƯỚC khi submit

## Local scorer — công cụ đo lường chính (kaggle/scorer/)

- **Nguồn**: `scorer/scorer1..3code.py` (đồng bộ `download/local-scorer.ipynb`) ·
  **kiểm chứng**: `scorer/test-scorer-synth.py` — **31/31 ĐẠT**, khớp 100% điểm
  tính tay trên 2 submission (tốt = 1.100 max; xấu = 0.648 đúng từng thành phần)
- Port trung thành metric chính thức từ repo BTC (không cần tracksdata/geff/zarr —
  chỉ numpy/scipy/pandas/blosc2):
  * Đọc `.geff` zarr **v2 + v3** (đã xác minh blosc2.decompress đọc được chunk blosc1)
  * Ghép node **per-timepoint** Hungarian ≤ 7 µm (như tracksdata DistanceMatching)
  * Edge metric: bỏ cạnh nhảy → collapse merge (giữ 1 cạnh/cặp GT) → cap out-degree 2 →
    TP/FP/FN với **FP có điều kiện** (nguồn/đích bám GT-có-cạnh)
  * adjEJ = EJ·(1 − 0.1·ratio) với `estimated_number_of_nodes` đọc từ geff `.zattrs extra`
  * **Division metric đầy đủ**: window grandparent→divider→children→grandchildren,
    matching per-window, strongly-connected topology, cross-component /
    malformed branches, bipartite pairing — port `division_metrics.py`
  * Micro-average + weight-averaged adjEJ đúng `summarise()`
- Cách dùng (Kaggle notebook mới + Add Input competition):
  1. Chạy notebook pipeline ver 2 → có `submission.csv`
  2. Mở notebook scorer (3 cell) → Run All → bảng điểm per-dataset + tổng
  3. Tune tham số ở cell2code của pipeline → chạy lại → so điểm **offline**,
     không đốt quota 5 submit/ngày

## ver 1 — Stage 0+2 (đã submit · 0.198)

- **Ngày**: 2026-09-13 submit · **điểm Kaggle: 0.198** · nguồn `ver-1/`
- Nâng cấp so với ver 0: CoM theo cường độ · 26-conn · motion model EMA ·
  gate thích ứng 5–12 µm · phân bào 10/12 µm + bảo toàn độ sáng · nội suy khung mất
- **Kết quả chạy test (4 dataset, 12/09/2026)**:

  | dataset | nodes | edges | phân bào | thời gian |
  |---|---:|---:|---:|---:|
  | 44b6_0113de3b | 3771 | 2944 | 68 | 8s |
  | 44b6_0b24845f | 1419 | 833 | 4 | 8s |
  | 6bba_05b6850b | 458 | 328 | 0 | 6s |
  | 6bba_05db0fb1 | 3909 | 2835 | 94 | 8s |
  | **tổng** | **9557** | **6940** | **166** | **~30s / 12h** |

- **Chẩn đoán từ 0.198**: ước tính adjEJ ≈ 0.185–0.19, divJ ≈ 0.05–0.15 → điểm
  gần như toàn bộ đến từ adjEJ; 3 điểm nghẽn: (1) node recall thấp — nhân mờ bỏ
  sót + blob gộp; (2) track đứt — 21–41% node không có cạnh vào; (3) phân bào
  giả merge-split ở 2 dataset dày (68/94). Xem phân tích đầy đủ trên website
  (Phòng đo lường & quy chuẩn → Máy tính điểm, preset "ver 1" khớp 0.197)

## ver 0 — Baseline (notebook gốc Kaggle, không lưu file)

- Notebook "getting started" của ban tổ chức: P90 · 6-conn · tâm hình học ·
  Hungarian gate 15 µm · không phân bào · không frame-skip.
- Chỉ mang tính quy chiếu — không tự viết lại.

## Template cho ver 3+

```
## ver N — <tên>
- Ngày · trạng thái (draft / đã chạy Kaggle / đã submit, điểm LB)
- Nâng cấp so với ver N-1 (từng ý, ngắn gọn)
- Điểm local scorer (trước khi submit!) + điểm Kaggle (sau khi submit)
- Kết quả chạy Kaggle (bảng số liệu như trên)
- Nhận xét / hướng tune tiếp theo
```

Lộ trình sau ver 3: (a) chạy pipeline ver 3 + local scorer trên train để
đo trước khi submit; (b) Stage 1 thật sự (ngưỡng cục bộ thích ứng + DoG +
watershed cho blob gộp đầy); (c) division detector học từ patch thời gian
trên `zebrafish_embryo.ome.zarr` (voxel khớp Kaggle); (d) Stage 3 (U-Net
nhẹ + transformer linking như baseline BTC).
