# V11-RESEARCH — Nghiên cứu & Kế hoạch ver-11: Kênh DIVISION

> Ngày 17/9/2026 (sau cleanup + tổng hợp nghiên cứu đối thủ từ `api/research/`).
> Chuẩn bị TRƯỚC khi quota GPU refresh 19/9 00:00 UTC — mọi phân tích dưới đây chạy được trên CPU với cache sẵn có, GPU chỉ cần 1 lab kernel + 1 production kernel.

---

## 0. TL;DR

| Câu hỏi | Trả lời |
|---|---|
| v11 xây trên nền nào? | **ver-10 production** (v3-fast + HOCT veto mode 1, đang chờ quota) — KHÔNG đụng phần đã bank |
| Trục tăng điểm gì? | **Kênh division** — trục DUY NHẤT có offline sign khớp LB (zhincez: 3/3 đúng, trục edge 0/3) |
| Thuật toán gì? | **Mở vừa gate phân bào + DivNet rerank (đã có sẵn W=15) + cap giữ nguyên** — thay vì mở hết (megayak: −0.017) |
| Gain kỳ vọng? | +0.002…+0.006 LB → 0.951–0.955 (zhincez 0.952 = hạng ~32) |
| Cần GPU bao nhiêu? | 1 lab kernel ~3–4h (dump proposal + DivNet scores + HOCT pairs) + 1 production ~2.2h. Tổng ~6h/30h quota tuần mới |
| Rủi ro lớn nhất? | (1) Evaluator division offline đang đọc ×2 như public stack — phải vá trước khi tune; (2) FP division bị phạt trực tiếp (không như FP edge được tha) — cap phải chặt |
| Lộ trình? | 19/9: nộp v10 trước (bank 0.949x) → chạy v11-lab → grid CPU → build + nộp v11 ~20–21/9 → deadline 29/9 còn 8 ngày dư |

---

## 1. Hiện trạng & ngân sách điểm

### 1.1 Đã bank (đừng đụng vào)
- **0.947** = ver-8 v3-fast: 8 stems predict + harmonic fusion + relink tight 5.5 + DivNet rank-only W=15µm + re-parent Phase D + retention guard. *Nói cách khác: ranker DivNet đã được trả thưởng trong 0.947 — việc của v11 là phần CÒN LẠI của kênh division, không phải xây ranker từ đầu.*
- **v10 pending** (chờ quota 19/9): + HOCT veto mode 1 → validator adjEJ 0.9305 (+0.0018), div 4/1/8 giữ nguyên → kỳ vọng LB 0.9493–0.9497.

### 1.2 Ngân sách còn treo
- Validator (8 stems): division **4 TP / 1 FP / 8 FN** → 8/12 GT bị bỏ lở hoàn toàn. divJ 0.3076 (nếu evaluator đọc ×2 thì thật ~0.15 — xem §3.1).
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

### 3.1 Evaluator phải vá TRƯỚC (điều kiện tiên quyết)

`eval/cell-eval-official.py` dùng `tracksdata` `score_divisions` — cùng họ public stack đang nghi đọc ×2. File còn tự in cảnh báo khi 2 cách tính lệch nhau (`evaluate()` vs `score_divisions()`) — chứng tích của sự mơ hồ này.

**Việc cần làm:** port rule đã patch thành hàm evaluator riêng (mô tả từ nghiên cứu megayak/sjlee — đã có code tham khảo trong `api/research/0948-research/megayak-the-0-966-notebooks-used-a-patched-metric-bug.ipynb` và sjlee output):
1. GT division TP ⟺ parent được match VÀ fork (node 2 outgoing) là parent-match hoặc successor TRỰC TIẾP của nó, VÀ 2 daughters nằm trên 2 nhánh con trực tiếp phân biệt của fork.
2. Chạy song song cả 2 bản (cũ + patch) trên cùng prediction → hiệu số cho biết mình đang bị thổi phồng bao nhiêu (megayak đo: 0.2500 cũ vs 0.1250 official).
3. Từ đó về sau: MỌI quyết định gate dùng bản patch.

### 3.2 Vị trí giải phẫu trong monolith (ver-10/cell-monolith.py)

```
add_safe_divisions_postlink()  (dòng ~2959)  ← ĐÚNG CHỖ NÀY
  ├─ sinh proposals: parent ≤ SAFE_DIV_MAX_UM(9.0), sister ≤ 14.0
  ├─ gate: diverge ≥ 2.25, symmetry ≤ 0.6, existing_child ≤ 10µm, timing t+2
  ├─ _divnet_rerank_proposals() (dòng ~2942): score = parent + 0.15×sister − W×p_div, W=15
  ├─ budget: frame_frac_cap / global_frac_cap
  └─ thêm cạnh {'safe_division': 1}
add_reparent_divisions_postlink() (dòng ~3115)  ← Phase D re-parent — GIỮ NGUYÊN
_hv_apply_veto() mode 1 (dòng ~3887)  ← đã bank ver-10 — GIỮ NGUYÊN
```

Chi tiết phẫu thuật v11: **chỉ đổi 4 hằng số gate + có thể W** — toàn bộ hạ tầng DivNet/reparent/veto đã sẵn. Nhưng chọn giá trị nào = bài toán grid.

### 3.3 Tại sao cần lab kernel mới (không replay thuần CPU như v10)

Grid gate thay đổi → tập proposals thay đổi → cần p_div DivNet của NHỮNG proposal chưa từng được sinh ra ở gate hẹp (9/2.25 giết trước khi DivNet thấy). Giải pháp theo đúng pattern thành công của v10-lab:

**Dump LẦN ĐỦ ở gate RỘNG NHẤT, replay CPU mọi gate hẹp hơn:**
- Lab kernel chạy 8 validator stems với gate nới tối đa (parent 15, sister 16, diverge 0.5, symmetry 1.5 — mọi thứ DivNet có thể nhìn thấy), DivNet bật;
- Dump per-proposal: `(source_id, candidate_id, parent_dist, sister_dist, diverge, symmetry, p_div, các đặc trưng hình học khác)` — kể cả proposal bị gate giết (instrumentation trước gate, không sau);
- Dump song song: HOCT pairs cache (như v10-lab), base edges + nodes trước safe-division (đã có pattern raw_graphs);
- → CPU grid: mô phỏng lại `add_safe_divisions_postlink` với mọi tổ hợp (parent_max, sister_max, diverge, tau, W, caps) trên dump → ghép graph → veto mode 1 replay → chấm bằng evaluator ĐÃ PATCH → chọn config.

### 3.4 Kích thước không gian grid (định trước để không sa lầy)

| Tham số | Tập giá trị thử | Ghi chú |
|---|---|---|
| `SAFE_DIV_MAX_UM` | 9.0 (base) · 10.5 · 12.0 | reachability 71→86–100% |
| `SAFE_DIV_DIVERGE_UM` | 2.25 (base) · 1.5 · 1.0 | hiện ở median |
| `SYMMETRY_TAU` | 0.6 (base) · 0.8 · 0.95 | hiện ~p60 |
| `W` (DivNet) | 15 (base) · 25 · 40 | tăng nặng phạt evidence thấp |
| `frame/global cap` | giữ nguyên | chống FP nổ |
| Sister max | giữ 14.0–16.0 | chưa phải nút thắt |

≈ 3×3×3×3 = 81 configs (tự thêm base) — mỗi config replay ~giây trên CPU. Gate dừng (D-series, §6).

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
Giống hệt hạ tầng v10-lab (dataset runners đã có — chỉ thêm 1 runner):
1. Stage 8 validator stems (như v10-lab, cell2 pattern);
2. **Patch tạm gate tối rộng** qua env: `V11_DUMP_MODE=1` → `add_safe_divisions_postlink` sinh proposals ở gate max + gọi DivNet cho TẤT cả + dump JSON proposals (không thêm cạnh, chỉ quan sát);
3. Chạy pipeline CHUẨN (gate production) song song để có base graph như v10;
4. Dump HOCT pairs (mode 1) như v10-lab;
5. Push cache lên dataset `biohub-v11-proposals` (giữ nguyên watchdog pattern).

### 5.2 Grid CPU (local / Kaggle CPU kernel — 0 GPU)
1. `v11_eval_patched.py`: evaluator division rule-patch + so sánh với bản cũ trên cùng file → báo cáo hệ số thổi phồng;
2. `v11_grid.py`: nạp proposals dump → mô phỏng gate × W → ghép graph → veto1 replay → chấm patched divJ + adjEJ + div counts;
3. Chọn config theo: Δdiv_tp (patched) > 0 AND ΔadjEJ ≥ −0.0002 AND Δdiv_fp ≤ +2 (validator 12 GT — FP budget cực nhỏ).

### 5.3 `biohub-ver11` production (GPU ~2.2h, Internet OFF)
= ver-10 production + 4 env đổi gate (không thêm code mới ngoài hằng số) + guard giữ nguyên. Notebook build bằng chính `build-ver10-monolith.py` đổi env (pattern phẫu thuật đã chứng minh).

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
| D1 | Evaluator patch hợp lệ | 2 bản (cũ/patch) chạy cùng prediction, khác nhau có giải thích được; patched khớp mô tả rule aa65e90 |
| D2 | Base tái lập | Grid config base (9/14/2.25/0.6/W15) reproduce validator 4/1/8 + adjEJ 0.928665 (bằng chứng mô phỏng replay trung thực) |
| D3 | Tồn tại config thắng | Δdiv_tp (patched) ≥ +2 AND ΔadjEJ ≥ −0.0002 trên validator weighted |
| D4 | FP kiểm soát | Δdiv_fp ≤ +2 AND frame-cap không vượt; tổng fork thêm ≤ ~2.5× base |
| D5 | Runtime | Production không thêm inference mới (DivNet đã có, chỉ gọi thêm ~2–3× proposals — đo thời gian trong lab, vẫn trong guard 7.5h) |
| D6 | Không đụng node set | nodes.json hash GIỐNG HỆT ver-10 (chỉ edges đổi) |

---

## 7. Điểm nghẽn nhận diện & đối sách

| Nghẽn | Đối sách |
|---|---|
| Validator chỉ 12 GT division — sign yếu | (a) tin hiệu hiệu đúng thứ bậc: patched divJ > div_tp > adjEJ guard; (b) khắt khe D3/D4; (c) nếu biên mờ → chọn config bảo thủ nhất (chỉ mở diverge) |
| DivNet chưa từng thấy domain gate rộng (proposal xa hơn) | hits@k đo trên toàn GT (AUC 0.887 OOF) — nhưng vẫn thêm D4 cap |
| Proposal dump có thể rất lớn (gate max × 8 stems) | ước ~vài chục nghìn proposals × ~15 trường = vài MB JSON — OK; nếu nổ thì cap dump 20k/stem ưu tiên theo p_div |
| Mô phỏng replay không trung thực 100% (thứ tự cạnh, interplay với gap2/linefit) | D2 bắt buộc khớp base đến div counts + adjEJ; nếu lệch → fix mô phỏng trước khi tin grid |

---

## 8. Kết luận

Ver-11 = **ver-10 + 4 hằng số** (`SAFE_DIV_MAX_UM`, `SAFE_DIV_DIVERGE_UM`, `SYMMETRY_TAU`, có thể `W`) chọn bằng grid replay trên dump proposal rộng, chấm bằng evaluator division ĐÃ VÁ, với cap FP giữ nguyên. Toàn bộ hạ tầng (DivNet tích hợp, pattern lab/watchdog/dataset, build phẫu thuật monolith, launcher 1-lệnh) đã tồn tại và đã được chứng minh qua v10. Công việc mới thực sự: (1) evaluator patch, (2) instrumentation dump proposals, (3) grid + gate logic.

Trục division là trục duy nhất còn tín hiệu thật ở vùng 0.947+ (bằng chứng 3/3 của zhincez + audit gate của megayak + vật lý size-drop của zhincez). Trần thực dụng: 0.951–0.955.
