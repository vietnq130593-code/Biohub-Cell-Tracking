# ANALYSIS — evgendvorkin "0.942 LB PROXY_SCORE=0.9417" (106 votes, chạy hôm nay)

## 0. Metadata
- **Nguồn:** `/home/z/v11-recovery/research/evgendvorkin-proxy942/biohub-0-942-lb-proxy-score-0-9417.ipynb` (29 cells: 15 markdown tiếng Nga docs đầy đủ + 12 code).
- **Output đã pull đầy đủ:** submission.csv 241.761 rows (INT ✓), run_stats.csv, **validator_results.csv**, retention guard reports, val predictions geff (2 phim), kernel log. Receipts nhỏ copy vào đây.
- **Định vị:** **tổ tiên trực tiếp của toàn dòng public 0.942→0.947** — markdown trong notebook là bộ lịch sử tiến hóa đầy đủ nhất từng thấy: v2 0.808 (DoG+Hungarian) → v6 0.860 → v28 0.942 (SAFE_DIV 9/14 + τ0.6, từ rishabhr0y 0.938) → v29 0.945 (EDGE_FEATURE_TTA + tight 5.5 + DC 0.26, từ rogerrogerroger3r 0.944 / redoctopusk 0.946) → v30 target 0.948 (TTA-fusion link logits + SEF_TTA w0.75 + DC TTA, từ sjlee101/biohub-lf-dctta) → v31 hiện tại = dual-seed harmonic (raykkretzschmar lineage). Kernel hiện tại preset `v29_edge_tta_tight55`.

## 1. Kiến trúc (1 câu)
Chính là "đường ray" public mà stack mình đang đứng: dual-seed harmonic fusion + full TTA pack (EDGE_FEATURE_TTA 8 views, SEF_TTA w0.75, DC TTA, low_margin_consensus 0.20/0.80/0.35, threshold 0.480) + ILP + post-chain chuẩn + **validator holdout N=2/type chạy inline + proxy score công thức official**.

**Verify từ log:** EDGE_TTA_ACTIVE views=8 (mean_abs_feat_delta ~0.33), SECONDARY_EDGE_TTA_ACTIVE views=8 weight=0.75, "Secondary model: edge weight=0.200 | detection weight=0.800 | link mode=low_margin_consensus | low-margin max=0.350" → **cấu hình TTA/secondary TRÙNG HỆT ver-8/v10 mình** (mình port đúng gốc).

**Census submission (verify CSV):** 122.975 node / 118.786 edge / **200 fork** (62/51/9/78) — fork NHIỀU NHẤT trong các bản đã đo (mình 188, haideptry 96, alfonso 92→2). Nguyên nhân: `DEEPCENTER_SAFE_DIV_VETO=0` (tắt veto) + DC threshold 0.26.

## 2. Env-knob diff vs stack mình
| Knob | Mình | evgendvorkin | Ghi chú |
|---|---|---|---|
| (toàn bộ khung SAFE_DIV/TTA/bidir/ILP/caps/rescue/linefit) | — | — | GIỐNG (mình là hậu duệ trực tiếp) |
| GAP_CLOSE_UM | 5.0 | **5.8** | khác nhẹ, chưa có receipt độc lập |
| DEEPCENTER_SAFE_DIV_THRESHOLD | 0.20 | **0.26** | họ cao nhất cụm (hội tụ hướng 0.25+) |
| DEEPCENTER_SAFE_DIV_VETO | 1 | **0 (OFF)** | lệch lớn nhất — lý do fork 200; và LB vẫn 0.942 → thêm 1 bằng chứng fork-count НЕ quyết định divJ ở vùng 90-200 |
| MOTION_RELINK_TIGHT_UM | 5.5+per-prefix | 5.5 | GIỐNG |
| DIVERGE_UM | 2.25 | không set (default 2.25) | GIỐNG |

## 3. Đánh giá PROXY SCORER (câu hỏi trung tâm của task)

### 3.1 Cấu tạo proxy
- Val set: N=2/type, division-aware selection (ưu tiên phim có GT division) → 4 phim holdout: 44b6_12dfb391, 44b6_267148e4, 6bba_062c8d37, 6bba_07e24132 (receipt validator_results.csv + log "4 contain a GT division").
- Công thức: `proxy = weighted_adjEJ + 0.1 × divJ` (weight = TP+FP+FN mỗi phim) — đúng công thức official summarise().
- **Điểm proxy run hiện tại (log):** `n=4 adjusted_edge_jaccard=0.9230 division_jaccard=0.2000 PROXY_SCORE=0.9430`. Title claim PROXY 0.9417 ↔ LB 0.942 (version trước).
- Lịch sử mapping proxy↔LB (từ markdown): v28: proxy 0.9417 ↔ LB 0.942 (Δ −0.0003); v27-era: proxy 0.9384 ↔ LB 0.934 (Δ +0.0044). → **mapping ỔN ĐỊNH ±0.005, không phải ±0.001** — tốt hơn không có gì, kém xa "hiệu chuẩn chính xác".

### 3.2 ★★★ Vì sao proxy của họ chỉ ổn ±0.005 — và cách mình làm tốt hơn hẳn
1. Val set của họ = 4 phim KHÁC (holdout thuần), đo trên GT thưa (~6% node được annotate — receipt: 44b6_12dfb391 có t_true 58.672 nhưng GT edges chỉ ~773!) → nhiễu sampling lớn.
2. DivJ đo bằng **bản component-based (2x official)** — "compass reads double" (megayak). Trục divJ của proxy mọi phiên bản đều thổi phồng.
3. **Đường lối tốt hơn cho mình (kết hợp phát hiện codezzzsleep):** local LB replica trên CHÍNH 4 phim test (GT từ train/) + division_metrics post-patch. Nếu verify thành công trên submission 0.947 đã biết điểm → mình có scorer chính xác bậc ±0.001, vượt xa proxy 4-film-holdout kiểu evgendvorkin.

### 3.3 ★★★ Receipt dữ liệu hiếm trong validator_results.csv (GT thưa + bonus under-prediction)
- **GT train là annotation thưa (~6%)**: 44b6_12dfb391: edge TP 746/FP 33/FN 27 trên t_true 58.672 → toàn bộ adjEJ bị chi phối bởi vài trăm cạnh annotate; div_fp hầu như không bao giờ tăng vì fork nodes phần lớn unmatched. Giải thích trọn vẹn vì sao fork 92 vs 188 vs 200 cho divJ gần nhau trên LB.
- **Adjusted bonus khi under-predict:** 44b6_12dfb391: t_pred 45.018 < t_true 58.672 → adjEJ = edgeJ × 1.0233 (0.9256→0.9471!). Công thức `max(0, J×(1−0.1×ratio))` với ratio âm → thưởng tới +0.02 adjEJ cho phim detect ít hơn GT-estimate. Trục "DET threshold ↔ node budget" có một khu vực thưởng nghịch lý mà chưa ai trong cụm khai thác có chủ đích — đo trong LB replica trước khi đụng.

### 3.4 ★ Lineage map + receipts LB công khai (markdown)
Bảng receipts 10 phiên bản (0.808→0.945) + nguồn gốc từng cơ chế (rishabhr0y 0.938 → div geometry; rogerrogerroger3r 0.944 → EDGE_FEATURE_TTA; redoctopusk 0.946 → tight 5.5; sjlee101 → DC TTA/SEF_TTA). Trùng/khớp bảng batch C (gautiermarti-dc-training là bản sao docs này). Không thêm gì mới cho mình — nhưng khẳng định: **SEF_TTA w0.75 là món "v30 target 0.948" của chính dòng họ** — tức trục E-7 (nghi vấn keep-rate 0b24) đang là điểm không đồng thuận lớn nhất giữa "niềm tin public" (+0.001~0.002) và bằng chứng keep-rate mình (67.5% vs 71.2%). A/B SEF_TTA {0.75, 1.0, OFF} vẫn là experiment số 1 của v11-lab.

### 3.5 ★ "Frozen frame-retention probe" audit + manifest (cell 20/26)
Label-free audit submission + guard logs (contract use_primary, fallback counts, min/median retention per phim) — tương đương audit layer mình đã có trong harness (D2 anchor). Không port thêm.

## 4. Claim điểm + bằng chứng
- Claim "0.942 LB" với 106 votes: **đáng tin** (đây là public notebook 0.942 nổi tiếng mà dòng reyhanksatria 0.947 — nguồn stack mình — xây trên; các mốc 0.934/0.942/0.945 trong markdown nhất quán với independent receipts batch C).
- KHÔNG có receipt nào cho "proxy dự đoán LB chặt hơn ±0.005" — claim 0.9417↔0.942 là 1 điểm dữ liệu.

## 5. Nguy cơ / caveat
1. Proxy dùng divJ component-based → mọi kết luận sweep divJ của họ (kể cả "tight55 +0.0021 proxy") cần re-đo bằng official metric.
2. Val set 4 phim nhỏ → nhiễu; N_PER_TYPE=2 vs 4 (raunakdey) vs 8 (analyticaobscura) — mỗi nhà một con số, không ai hiệu chuẩn được.
3. GT thưa làm mọi phép đo local có floor noise ~±0.003-0.005 — càng lý do phải đo TRÊN 4 phim test (đúng phân phối LB) thay vì holdout.

## 6. Verdict cho v12
**Không port code** (mình là hậu duệ đầy đủ của pipeline này + đã có mọi cơ chế tốt hơn). **Giá trị thật:** (1) ★★★ khối dữ liệu + phương pháp validator cho thấy proxy holdout chỉ tin được ±0.005 → thay bằng LB-replica trên 4 test stems (codezzzsleep discovery); (2) ★★★ receipt GT thưa 6% + bonus under-prediction + tính "mù" của divJ với fork count 92-200 → dồn effort v12 vào EDGE axis đúng như kế hoạch; (3) ★ xác nhận cấu hình TTA mình = chuẩn gốc của cả cụm (không sai bản sao); (4) ★ kho receipts tiến hóa public dùng đối chiếu mọi khi cần truy nguồn một knob.
