# V11-RESEARCH — Nghiên cứu & Kế hoạch ver-11: Kênh DIVISION

> Ngày 17/9/2026 (sau cleanup + tổng hợp nghiên cứu đối thủ từ `api/research/`).
> Chuẩn bị TRƯỚC khi quota GPU refresh 19/9 00:00 UTC — mọi phân tích dưới đây chạy được trên CPU với cache sẵn có, GPU chỉ cần 1 lab kernel + 1 production kernel.

---

## 0. TL;DR

| Câu hỏi | Trả lời |
|---|---|
| v11 xây trên nền nào? | **ver-10 production** (v3-fast + HOCT veto mode 1, đang chờ quota) — KHÔNG đụng phần đã bank |
| Trục tăng điểm gì? | **Kênh division** — trục DUY NHẤT có offline sign khớp LB (zhincez: 3/3 đúng, trục edge 0/3) |
| Thuật toán gì? | **Mở vừa gate phân bào (kể cả geo-sister 8.0µm — gate chặt nhất pipeline, phát hiện sau review) + DivNet rerank W=15 giữ + cap giữ nguyên** — thay vì mở hết (megayak: −0.017) |
| Gain kỳ vọng? | +0.002…+0.006 LB → 0.951–0.955 (zhincez 0.952 = hạng ~32) |
| Cần GPU bao nhiêu? | 1 lab kernel ~3–4h (dump theo-node p_div + proposals + HOCT pre-snap) + 1 production ~2.2h. Tổng ~6h/30h quota tuần mới |
| Rủi ro lớn nhất? | (1) Validator chỉ 12 GT division — sign nhiễu, cần gate D3/D4 khắt khe; (2) FP division bị phạt thẳng VÀ được mode-1 veto bảo vệ (không thể dựa HOCT dọn) — cap phải chặt; (3) domain-shift embryo-3. [Evaluator ×2: ĐÃ GIẢI QUYẾT sau review — validator lab dùng rule patched sẵn, xem §3.1] |
| Lộ trình? | 19/9: nộp v10 trước (bank 0.949x) → chạy v11-lab → grid CPU ~243 configs → build + nộp v11 ~20–21/9 → deadline 29/9 còn 8 ngày dư |

---

## 1. Hiện trạng & ngân sách điểm

### 1.1 Đã bank (đừng đụng vào)
- **0.947** = ver-8 v3-fast: 8 stems predict + harmonic fusion + relink tight 5.5 + DivNet rank-only W=15µm + re-parent Phase D + retention guard. *Nói cách khác: ranker DivNet đã được trả thưởng trong 0.947 — việc của v11 là phần CÒN LẠI của kênh division, không phải xây ranker từ đầu.*
- **v10 pending** (chờ quota 19/9): + HOCT veto mode 1 → validator adjEJ 0.9305 (+0.0018), div 4/1/8 giữ nguyên → kỳ vọng LB 0.9493–0.9497.

### 1.2 Ngân sách còn treo
- Validator (8 stems): division **4 TP / 1 FP / 8 FN** → 8/12 GT bị bỏ lở hoàn toàn. divJ 0.3076 — **đã xác minh sau review: số liệu theo rule PATCHED** (validator lab cài anchor + lineage-descendants, xem §3.1).
- Trần lý thuyết: divJ → 1.0 tức +0.069 điểm tổng. Thực tế (DivNet hits@5 = 56.9% của GT, top-2 sim divJ 0.226): kỳ vọng hợp lý +0.02–0.04 divJ = **+0.002–0.004 điểm tổng**; tươi hơn nếu gate mở đúng chỗ.
- LB: cụm 0.948 = 55 đội (hạng 89–143); 0.950 = hạng ~32 (zhincez); 0.952 = hạng ~31–32. → mỗi +0.001 ~ leo 5–25 hạng ở vùng này.

### 1.3 D5 đã chôn (giữ nguyên phán quyết ver-10)
- RLF (repeat-lineage filter): Δ 0.000000 trên stack mình (21 cạnh vô hại) — dead.
- tight sweep 4.5–7.0: toàn âm. tight 5.5 tối ưu.
- Single-knob ±0.001 kiểu secondary_edge_weight 0.15↔0.20: 2 đội 0.948-repro đọc cùng knob ra kết luận NGƯỢC nhau = noise. Không đuổi.

---

## 2. Tổng hợp nghiên cứu đối thủ (condensed — bản đầy đủ trong `api/research/`)

### 2.1 Phả hệ vùng 0.942–0.948
Toàn bộ là MỘT gia đình fork của stack harmonic (Pilkwang → nusrati → evendvorkin → Reyhan 0.947). Mình = port ver-8 đã đạt parity 0.947. Các nhánh:
- **sjlee101** "lf-hoctveto-div-b": + secondary edge-TTA (w=1.0) + DeepCenter TTA 8-view + DC safe-div 0.25→0.20 + **HOCT veto mode 2** → 0.947 (mode 2 của họ ≈ mode 1 của mình + veto cạnh chia; lab mình đã chứng minh mode 2 mất 1 div_tp → mode 1 thắng trên stack mình).
- **mtoshidesu** = sjlee KHÔNG HOCT → 0.947 (chứng minh bộ TTA tự nó đủ 0.947 — mình đã có).
- **caassicca** det 0.99 → 0.947 (ablation vô ích).
- **cloudssdut/zhuzhenghaomax** secondary_edge_weight 0.20 vs 0.15 → cùng 0.947 = noise.
- **zhincez** (Lê Quang Cảnh) = 0.952 — người duy nhất vượt cụm bằng **kênh division thuần**.

### 2.2 Bằng chứng quyết định cho hướng v11

**Sổ cái 6 submission của zhincez (offline sign ↔ LB):**

| trục | thay đổi | offline | LB | sign khớp? |
|---|---|---|---|---|
| edge | tắt relink | +0.0187 | 0.943→0.939 | ✗ |
| edge | edge-feature TTA | −0.0002 | 0.943→0.946 | ✗ |
| edge | nới division-CNN | −0.0058 | 0.946→0.946 | ✗ |
| **division** | per-node division cost | +0.0079 | 0.946→0.948 | ✓ |
| **division** | **raising division gate** | **+0.0118** | **0.948→0.950** | ✓ |
| division | đổi division network | −0.0058 | 0.950→0.949 | ✓ |

→ **Trục division: 3/3 sign đúng. Trục edge: 0/3.** Mọi công sức còn lại của mùa giải nên dồn vào division.

**Audit 151 GT division của megayak (gate đang ngồi ở đâu so với phân phối thật):**

| Gate của mình (hiện tại) | Vị trí trên phân phối GT thật | Hệ quả |
|---|---|---|
| `SAFE_DIV_MAX_UM = 9.0` (parent) | GT parent–daughter tới **10.4µm**; reachability 9.9µm→71%, 12µm→86%, 15µm→100% (zhincez N3) | giết ~29% reachability |
| `SAFE_DIV_SISTER_MAX_UM = 14.0` | GT sister max 13.7 (median 10.4, p90 13.0) | ~OK |
| `SAFE_DIV_DIVERGE_UM = 2.25` | **ngay MEDIAN phân phối thật** | **giết ~50% division thật** |
| `SYMMETRY_TAU = 0.6` | ≈ percentile 60 | giết ~40% |

**Nhưng mở gate KHÔNG đủ** (megayak end-to-end): mở toàn bộ (−999/off) → 541 fork proposals, 0/19 TP, **−0.017**; gate như ship + ranker hình học → 1 TP. Chẩn đoán: ngân sách fork ~5 slot/frame bị ranker hình học (`parent_dist + 0.15×sister_dist` — ưu tiên cặp SÁT NHAU = duplicate detections) tiêu hết trước khi division thật được xét. **Cặp "gate mở vừa + rank bằng evidence" là thứ chưa ai trong cụm 0.948 làm** (zhincez làm bằng per-node cost tự viết; mình có DivNet sẵn).

**Vật lý hiện tượng phân bào (zhincez EDA, đo paired-control):** volume bắt đầu co từ t−2 trước split (depth −0.27 tại t+3), peak intensity GIỮ NGUYÊN (con sáng bằng mẹ). → Feature "size-drop" là tín hiệu sớm đúng; mean-intensity là tín hiệu sai. DivNet của mình dùng lags (−1,0,+1,+2) + center marker — kiến trúc đã khớp cửa sổ −2→+6.

**Cảnh báo metric (megayak, NGHIÊM TRỌNG):** 6 notebook public 0.963–0.966 cũ là exploit "hub + fork giả" (nối mọi track vào 1 node t=−1000 ngoài volume + chuỗi fork giả → thỏa weakly-connected rule cũ của division metric). Kaggle **patch ngày 17/7/2026** (`aa65e90`): fork phải là parent được match HOẶC successor trực tiếp; 2 daughters phải trên 2 nhánh con trực tiếp phân biệt. Exploit chết — điểm cũ không thu hồi nhưng không tái tạo được. **Hệ quả gián tiếp: bản offline division metric trong tracksdata/public stack vẫn dùng rule weakly-connected → đọc GẤP ĐÔI official.** Tune gate theo la bàn đó = lái theo kim chỉ ×2.

**Phạt bất đối xứng (zhincez):** xóa node gần như free trên trục edge nhưng ĐẮT trên trục division (thử xóa node → 15 FP division mới → divJ −0.0409 = −0.0041 tổng). FP division bị phạt thẳng, unmatched predicted edge chỉ bị drop khỏi consideration. → v11 KHÔNG đụng node set; chỉ thêm cạnh chia.

---

## 3. Phân tích code mình: chỗ cần phẫu thuật

### 3.1 Evaluator: PHÁT HIỆN SAU REVIEW — validator lab ĐÃ dùng rule patched ✓

**Đối chiếu code:** `ver-10-lab/cell-monolith-v10lab.py` (dòng ~4596–4670) — bộ validator sinh ra số liệu 4/1/8 của grid v10 — đã cài **"patched division matching"**: union-find weakly-connected components chỉ để gom cụm, nhưng TP yêu cầu (a) anchor = GT parent được match HOẶC parent của nó, (b) lineage-descendants của từng daughter phải phủ 2 nhánh con phân biệt. Đây chính là tinh thần commit `aa65e90`. → Số liệu 4/1/8 + divJ 0.3076 của grid v10 **đã là số liệu theo rule official mới** — không bị thổi ×2.

Còn lo ngại ×2 chỉ áp dụng cho đường eval CŨ: `eval/cell-eval-official.py` (import `tracksdata` — library chưa xác minh version chứa patch hay chưa, và không cài trong sandbox local). Đường này KHÔNG dùng cho quyết định v11.

**Việc cần làm (thu hẹp từ 'port từ đầu' thành 'verify'):**
1. Trên lab kernel (Kaggle có tracksdata): in `tracksdata.__version__` + `inspect.getsource(score_divisions)` → xác nhận rule nào; so với mô tả metrics.md post-patch;
2. Chạy chéo 1 graph qua (a) validator lab patched, (b) tracksdata Kaggle → nếu khác nhau, điều tra trước khi tin số nào;
3. Từ đó về sau: MỌI quyết định gate dùng validator lab patched (đã có, đã sản xuất số liệu ver-9/ver-10).

### 3.2 Vị trí giải phẫu trong monolith (ver-10/cell-monolith.py) — CHUỖI HẬU XỬ LÝ THẬT (sau review)

Safe-division KHÔNG phải bước cuối — nó nằm giữa pipeline với **5 bước phía sau phụ thuộc vào kết quả của nó** (đọc trực tiếp từ code, dòng 3540–3600):

```
(1) close_single_frame_gaps        (gap-close + DeepCenter gate)
(2) recover_strict_gap2            (gap2)
(3) add_safe_divisions_postlink    (dòng 3545) ← V11 THAY ĐỔI Ở ĐÂY
(4) add_reparent_divisions_postlink (dòng 3546) ← Phase D — phụ thuộc (3), và tự query DivNet (pdiv_of dòng 3137)
(5) division_geometry_filter       (dòng ~3552) ← GATE SONG GIÁC — XEM CHÚ Ý ⚠️
(6) prune_isolated
(7) filter_short_track_components  (keep_division_components=1 → cạnh chia mới CỨU node)
(8) linefit_smooth_output_graph    (positions thay đổi theo edges)
(9) [hook write] _hv_apply_veto mode 1 (dòng 4122) — đã bank ver-10
```

**⚠️ PHÁT HIỆN SAU REVIEW — gate chị em chặt nhất pipeline nằm ở bước (5), KHÔNG nằm ở safe-div:**
`division_geometry_filter` (bước 5) xem xét node có ≥2 cạnh outgoing: giữ cặp top-2 chỉ khi
`max(d1,d2) ≤ DIV_PARENT_MAX_UM (10.5)` **VÀ** `sister ≤ DIV_SISTER_MAX_UM (8.0)` **VÀ** cả 2 con ở t+1 —
nếu không, `DIV_DROP_TO_SINGLE_IF_BAD=1` **GIẢM CẤP về 1 cạnh** (rơi hẳn cạnh con).
GT sister: median 10.4, p90 13.0, max 13.7 → **gate 8.0µm này chặn ~50–70% division thật** (4/12 TP ~ 33% trên validator khớp với chẩn đoán này). Đây khả năng lớn là nút thắt lớn nhất của kênh division — trục `DIV_SISTER_MAX_UM 8.0 → 12/14` phải vào grid.

Các hằng số khác đã xác minh từ code (dòng 460–542): `SAFE_DIV_FRAME_FRAC_CAP=0.008`, `SAFE_DIV_GLOBAL_FRAC_CAP=0.004`, `SAFE_DIV_REQUIRE_MUTUAL_NN=1`, `SAFE_DIV_EXISTING_CHILD_MAX_UM=10.0`, `DEEPCENTER_SAFE_DIV_VETO=1` + threshold **0.20** (env dòng 125–126).

Chi tiết phẫu thuật v11: **đổi ~5 hằng số env (4 gate safe-div + 1–2 gate geo-filter) + có thể W** — không code mới. Chọn giá trị nào = bài toán grid.

### 3.3 Tại sao cần lab kernel mới (không replay thuần CPU như v10) + thiết kế dump CHÍNH XÁC

Grid gate thay đổi → tập proposals thay đổi → cần p_div DivNet của NHỮNG proposal chưa từng được sinh ra ở gate hẹp (9/2.25 giết trước khi DivNet thấy). Ngoài ra bước (4) reparent **tự query DivNet theo node** (pdiv_of) — query phụ thuộc cạnh sinh ra ở (3) → chicken-and-egg. Giải quyết trọn vẹn bằng **dump theo NODE thay vì theo proposal**:

**Dump ở lab (một lần, gate rộng nhất):**
1. **Graph tại điểm (2)-xong/(3)-chưa-chạy** (sau gap2, trước safe-div): nodes + edges từng stem — đây là input trung thành cho mọi replay;
2. **p_div THEO NODE** (mọi node, mọi stem): 1 lần DivNet inference theo node (~25k node/stem × 64/batch ≈ vài phút GPU) — phủ được CẢ ranking proposals LẪN mọi query pdiv_of của reparent trong mọi config grid (query chỉ là vị trí node);
3. **Verdict DeepCenter theo node** (score safe-div veto 0.20) — để replay reproduces được gate DC mà không cần model;
4. **Proposals ở gate rộng nhất** (parent 15, sister 16, diverge −1.0, symmetry 1.5) với đầy đủ đặc trưng hình học (parent_dist, sister_dist, diverge, symmetry, mutual-NN flag, timing flag) — **format npz float32, KHÔNG truncate theo p_div** (truncate làm hỏng sweep W nhỏ; ~vài trăm nghìn proposals × 15 trường ≈ 30–60MB/stem — ổn cho dataset);
5. **HOCT pairs ĐÃ pre-snap** về node id pipeline (snap KD-tree là bất biến theo cạnh — làm 1 lần, mọi config dùng chung) → veto replay mỗi config = O(edges) mili-giây;
6. **Graph FINAL của config base** (chạy chuẩn production song song) — mỏ neo cho D2.

**CPU grid replay = mô phỏng lại chuỗi (3)→(8) + veto (9)** từ dump trên, với mọi tổ hợp gate. Bước (1)(2) không phụ thuộc gate chia → khỏi re-simulate. Cuối lab kernel: **verify top-3 configs bằng re-run chuỗi (3)→(9) thật** trong kernel (numpy CPU, ~phút/config) so với output mô phỏng — bằng chứng trung thực D2 mở rộng.

### 3.4 Kích thước không gian grid (định trước để không sa lầy)

| Tham số | Tập giá trị thử | Ghi chú |
|---|---|---|
| **`DIV_SISTER_MAX_UM` (geo-filter, bước 5)** | **8.0 (base) · 12.0 · 14.0** | **TRỤC MỚI SAU REVIEW — gate chặt nhất pipeline, chặn ~50–70% division thật** |
| `SAFE_DIV_MAX_UM` | 9.0 (base) · 10.5 · 12.0 | reachability 71→86–100% |
| `SAFE_DIV_DIVERGE_UM` | 2.25 (base) · 1.5 · 1.0 | hiện ở median |
| `SYMMETRY_TAU` | 0.6 (base) · 0.8 · 0.95 | hiện ~p60 |
| `W` (DivNet) | 15 (base) · 25 · 40 | tăng nặng phạt evidence thấp |
| `DIV_PARENT_MAX_UM` (geo-filter) | giữ 10.5 (theo dõi trong sim) | rộng hơn safe-div 9.0 — không binding |
| `SAFE_DIV_SISTER_MAX_UM` | **giữ cố định 14.0** | dead axis: GT max 13.7 → 14.0 đã phủ 100% |
| frame/global cap (0.008/0.004), mutual-NN, existing-child 10µm, timing t+2 | **giữ nguyên** | chống FP nổ; audit megayak: structural/timing ít gây hại |

≈ 3 (geo-sister) × 3×3×3×3 = **~243 configs** — mỗi config replay ~giây-vài-giây trên CPU nhờ pre-snap HOCT + node-level p_div dump. Phased: phase 1 sweep geo-sister × diverge (2 trục có by chứng mạnh nhất) với phần còn lại base; phase 2 refine quanh vùng thắng. Gate dừng (D-series, §6).

---

## 4. Phương án đã xem xét và LOẠI (để không quay lại)

| Phương án | Lý do loại |
|---|---|
| Hub/fork exploit (0.966 cũ) | Đã patch 17/7 — không cộng điểm nữa; 2 team 0.966 là fossil |
| Mở gate KHÔNG kèm ranker evidence | megayak đo −0.017 end-to-end |
| Det threshold 0.99 (caassicca) | 0.947 = không gain, cần re-inference |
| secondary_edge_weight 0.15↔0.20 | noise (2 đội đọc ngược nhau) |
| HOCT mode 2 | Lab v10: mất 1 div_tp, proxy −0.0060 — mode 1 thắng |
| RLF | D5 FAIL — Δ 0.000000 trên stack mình |
| Tight re-sweep | D5 FAIL — 4.5–7.0 toàn âm |
| Xóa node để nâng adjEJ | Đắt trên division (−0.0041) — cấm |
| Train model mới (SSL 199 wells kiểu tangai1) | <10 ngày còn lại + rủi ro; để mùa sau |

---

## 5. Kiến trúc triển khai v11 (3 kernel)

### 5.1 `v11-lab-gpu` (GPU ~3–4h, sau khi nộp v10)
Cùng hạ tầng v10-lab nhưng **dataset runners riêng `biohub-v11-lab-runners`** (copy runners v10 + patch cell3), chạy theo thứ tự:
1. Stage 8 validator stems (như v10-lab, cell2 pattern — giữ nguyên);
2. Pipeline chuẩn production (gate base) → dump **graph FINAL base** (mỏ neo D2) + chạy validator patched như v10-lab;
3. **Instrumentation V11_DUMP_MODE** (chèn vào `add_safe_divisions_postlink` + quanh nó):
   - dump graph tại điểm (2)-xong/(3)-chưa-chạy (nodes + edges);
   - dump p_div theo NODE (mọi node) + verdict DeepCenter theo node;
   - dump proposals gate rộng nhất (npz, đủ đặc trưng — xem §3.3);
4. HOCT predict + **pre-snap** pairs theo node id (1 lần, không phụ thuộc config);
5. In-lab: `tracksdata.__version__` + `inspect.getsource(score_divisions)` → log cho D1;
6. **Verify top-3 configs ngay trong lab**: re-run chuỗi (3)→(9) thật cho 3 config thắng tạm (nếu grid in-kernel kịp chạy) hoặc để CPU grid làm rồi verify bằng re-run cục bộ;
7. Push toàn bộ cache lên dataset `biohub-v11-lab-cache` (watchdog pattern giữ nguyên).

### 5.2 Grid CPU (local / Kaggle CPU kernel — 0 GPU)
1. `v11_grid.py`: nạp dump → mô phỏng chuỗi (3)→(8) + veto (9) cho từng config (pre-snap HOCT + node p_div tra bảng) → chấm patched divJ + adjEJ + div counts theo stem + weighted;
2. Phased (xem §3.4): phase 1 geo-sister × diverge, phase 2 refine + W;
3. Chọn config theo: Δdiv_tp (patched) > 0 AND ΔadjEJ ≥ −0.0002 AND Δdiv_fp ≤ +2 (validator 12 GT — FP budget cực nhỏ);
4. Verify top-3 bằng so khớp với re-run thật (bước 6 lab) nếu có — sai lệch nào phải giải thích được trước khi submit.

### 5.3 `biohub-ver11` production (GPU ~2.2h, Internet OFF)
= ver-10 production + **5–6 env đổi gate** (4 safe-div + DIV_SISTER_MAX_UM geo-filter + có thể W — không code mới). Notebook build bằng `build-ver10-monolith.py` đổi env (pattern phẫu thuật đã chứng minh). Runtime thêm chỉ là DivNet theo node (~vài phút GPU, 25k node × 5–7 hidden videos) — vô hại trước guard 7.5h.

### 5.4 Thứ tự + ngân hàng lượt nộp
```
19/9 07:00 VN  quota refresh
  ├─ (1) bash kaggle/api/v10-launch.sh        → bank 0.9493–0.9497  [2.2h GPU]
  ├─ (2) v11-lab-gpu                            → dump proposals      [3–4h GPU]
  ├─ (3) grid CPU + chọn config + build v11     [0.5 ngày, 0 GPU]
  └─ (4) push + submit v11                      [2.2h GPU]  ~20–21/9
Tổng GPU ~8h/30h. Nếu v11 dương → còn 8 ngày iterate (DivNet W, caps, thêm reparent sweep).
Nếu v11 âm → v10 vẫn là final. 5 lượt/ngày — dư.
```

---

## 6. GATES D1–D6 cho v11 (định trước, không nới sau)

| # | Gate | Tiêu chí |
|---|---|---|
| D1 | Evaluator đã verify | tracksdata Kaggle version + source log; validator lab patched chạy chéo với tracksdata trên 1 graph — khớp hoặc chênh lệch giải thích được |
| D2 | Base tái lập | Sim config base (9/14/8.0-geo/2.25/0.6/W15) reproduce validator 4/1/8 + adjEJ 0.928665; top-3 configs khớp re-run thật (edges/counts) |
| D3 | Tồn tại config thắng | Δdiv_tp (patched) ≥ +2 AND ΔadjEJ ≥ −0.0002 trên validator weighted. **Tier-2**: nếu chỉ đạt +1 TP với 0 FP mới + adjEJ ≥ −0.0001 → chỉ nộp khi còn ≥3 ngày & ≥2 lượt an toàn, ghi rõ là cược rủi ro |
| D4 | FP kiểm soát | Δdiv_fp ≤ +2 AND frame-cap không vượt; tổng fork thêm ≤ ~2.5× base. **CHÚ Ý: cạnh chia FP mới được mode-1 veto BẢO VỆ** (node ≥2 con) → D4 là hàng rào duy nhất chống FP division |
| D5 | Runtime | DivNet theo node ~vài phút + các bước cũ giữ nguyên; đo trong lab; tổng < 2.5h public (hidden ×2.5 < 7h < guard 7.5h) |
| D6 | Node set CHỈ ĐƯỢC PHÉP sinh thêm từ rescue | Không XÓA node nào so với ver-10 final; node mới chỉ đến từ việc cạnh chia cứu short-track/isolated node có sẵn trong graph (2) — đếm + log từng node; KHÔNG node id nào ngoài vũ trụ node của bước (2). Positions có thể dịch qua linefit (kỳ vọng, không phải vi phạm) |

---

## 7. Điểm nghẽn nhận diện & đối sách

| Nghẽn | Đối sách |
|---|---|
| Validator chỉ 12 GT division — sign yếu | (a) tin hiệu hiệu đúng thứ bậc: patched divJ > div_tp > adjEJ guard; (b) khắt khe D3/D4; (c) nếu biên mờ → chọn config bảo thủ nhất (chỉ mở geo-sister + diverge) |
| DivNet chưa từng thấy domain gate rộng (proposal xa hơn) | hits@k đo trên toàn GT (AUC 0.887 OOF) — nhưng vẫn thêm D4 cap |
| Mô phỏng replay không trung thực 100% | Sim phải tái tạo chuỗi (3)→(9) nguyên văn logic (copy code thật, không viết lại); D2 khớp base đến div counts + adjEJ; top-3 verify bằng re-run thật |
| **Veto-protection interplay**: FP division mới được mode-1 bảo vệ (node ≥2 con) — không thể dựa HOCT dọn | D4 FP cap là hàng rào duy nhất; chọn config có div_fp bằng 0 nếu có lựa chọn tương đương |
| **Domain shift embryo-3** (hidden ≠ 2 embryo validator): phân phối sister/diverge/symmetry có thể lệch | cap frame/global giữ nguyên triệt để; không chọn config ở biên thắng (margin < +1 TP); cân nhắc config an toàn giữa dải thắng |
| Reparent (bước 4) phản ứng lại cạnh chia mới theo cách phi tuyến | Sim giữ nguyên logic reparent (dùng p_div node dump); D2 chấm cả reparent_added — lệch lớn → điều tra |

---

## 8. Kết luận

Ver-11 = **ver-10 + 5–6 hằng số env** (`SAFE_DIV_MAX_UM`, `SAFE_DIV_DIVERGE_UM`, `SYMMETRY_TAU`, `W`, và trục mới sau review: `DIV_SISTER_MAX_UM` geo-filter 8.0 → 12/14) chọn bằng grid replay ~243 configs trên dump theo-node (p_div DivNet + verdict DeepCenter + HOCT pre-snap), chấm bằng validator patched (đã có sẵn, đã verify), cap FP giữ nguyên tuyệt đối. Toàn bộ hạ tầng (DivNet tích hợp, pattern lab/watchdog/dataset, build phẫu thuật monolith, launcher 1-lệnh) đã tồn tại và đã được chứng minh qua v10. Công việc mới thực sự: (1) instrumentation dump theo node + proposals, (2) grid sim (3)→(9) + verify top-3, (3) tracksdata version-check trên lab.

Trục division là trục duy nhất còn tín hiệu thật ở vùng 0.947+ (bằng chứng 3/3 của zhincez + audit gate của megayak + vật lý size-drop của zhincez). Trần thực dụng: 0.951–0.955.

---

## Phụ lục A — Biên bản review 17/9 (tự soát sau khi viết)

Đối chiếu tài liệu với code thật (`ver-10/cell-monolith.py` + `ver-10-lab/cell-monolith-v10lab.py`) — 6 sửa:
1. **§3.1 SAI → ĐÚNG lại**: validator lab ĐÃ cài patched division matching (anchor + lineage-descendants, dòng 4596+) — số liệu 4/1/8 là rule mới; lo ngại ×2 chỉ còn ở đường eval cũ `eval/cell-eval-official.py` (không dùng cho v11). D1 thu hẹp từ "port từ đầu" thành "verify + version-check".
2. **§3.2 BỎ SÓT NGHIÊM TRỌNG**: `division_geometry_filter` (bước 5) có `DIV_SISTER_MAX_UM=8.0` + `DIV_DROP_TO_SINGLE_IF_BAD=1` — gate chị em chặt nhất pipeline (GT median 10.4), nằm NGOÀI mọi trục grid ban đầu → thêm trục 8.0→12/14.
3. **§3.2 SAI CẤU TRÚC**: safe-div không phải bước cuối — 5 bước phía sau (reparent query DivNet theo node, geo-filter, prune, short-track, linefit) phụ thuộc nó → grid sim phải mô phỏng chuỗi (3)→(9), không chỉ safe-div + veto.
4. **§3.3 THIẾU dump then chốt**: reparent chicken-and-egg giải bằng p_div THEO NODE (phủ cả ranking + pdiv_of); DeepCenter verdict theo node; HOCT pre-snap (grid mỗi config = mili-giây); npz không truncate (truncate theo p_div làm hỏng sweep W nhỏ).
5. **§6 D6 bất khả thi như viết ban đầu**: prune_isolated + keep_division_components → cạnh chia mới CỨU node → node set được phép TĂNG (chỉ cấm xóa + cấm node id ngoài vũ trụ bước 2).
6. **§6 D3/D4 thêm**: tier-2 cho +1 TP; ghi nhận FP division mới được mode-1 veto bảo vệ → D4 là hàng rào duy nhất; thêm rủi ro domain-shift embryo-3 + reparent phi tuyến vào §7.
