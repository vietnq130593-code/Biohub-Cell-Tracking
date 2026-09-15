# VER-9 — NGHIÊN CỨU TRI THỨC MỚI & PHÂN TÍCH NHÂN QUẢ

**Ngày 15/9/2026 (07:50 UTC)** · Sinh thời điểm v8-v1 PENDING chấm điểm, v8-v2 RUNNING
· ver-7 = 0.947 (đã biết) · GPU quota còn **8.68h** (refresh 19/9 +30h) · entry deadline **22/9**

> Nguồn: 5 notebook public mới kéo về (15/9) + 4 discussion thread đọc trực tiếp +
> leaderboard + phép đo trực tiếp trên submission ver8-v1. Toàn bộ lưu tại
> `kaggle/api/research/0949-research/`.

---

## 0. Tóm tắt điều hành — 6 phát hiện mới then chốt

| # | Phát hiện | Nguồn | Độ tin cậy |
|---|---|---|---|
| **N1** | **Divfix repeat-lineage**: GT 0/132 divisions lặp trong cùng lineage → mọi fork đứng sau fork khác cùng dòng gần như chắc chắn FP. Bộ lọc post-hoc (chỉ xóa cạnh con xa hơn) đo được **+0.0021** trên pipeline người khác | pawanmali (15/9, cha dòng 0.942) | Cao — code + số đo |
| **N2** | **Dataset synthetic CC0 18.5GB**: 165.267 divisions có nhãn (mitotic parents) / 4.056.226 nodes = **540× lượng giám sát divisions so với GT thật (~304)**. Vật lý (stride [::4,::4] đúng evaluator, detectability calibrated 0.89/0.76 vs real 0.91-0.94). Lưu ý: rate 4.07% vs 0.26% thật (reweight 15.7×), texture/contrast là trục yếu | José Freitas (discussion 732103, 61 votes) | Cao — CC0 + explorer live |
| **N3** | **Linker không bao giờ gắn con thứ 2**: đo trên 7 divisions thật (4 phim): parent + 2 con detect 7/7 (100%), nhưng cả 2 cạnh present **0/7**, out-degree parent luôn = 1. Reachability: gate 7µm→29% · 9.9µm→71% · 12µm→86% · **15µm→100%**. "Cell không tách dần — nó xuất hiện thành 2 thứ đã xa sẵn" (mẹ→con median 8.47µm) | Lê Quang Cảnh (hạng 31→0.952, discussion 732103) | Cao — đo trực tiếp GT |
| **N4** | **Nhân phân bào NHỎ ĐI, không MỜ ĐI**: volume (half-max) giảm -0.27 tại +3 khung sau tách, đã thấp hơn control tại -2/-1 TRƯỚC tách (chromatin ngưng tụ); đỉnh sáng GIỮ NGUYÊN (chỉ khung tách mới clearance). Mean intensity rơi là ảo ảnh hình học. Cửa sổ hiệu ứng: đỉnh +3, tàn +6 | Lê Quang Cảnh (notebook 13/9, bootstrap CI) | Cao — đo GT + CI |
| **N5** | **Motion-relink phá huỷ mọi fork ILP**: "public 0.938 pipeline family: motion-relink rebuilds edge list bằng 1-1 Hungarian trước safe-div → mọi fork ILP tạo ra bị phá tại đó. Division work upstream invisible" | Lê Quang Cảnh (discussion 732103) | Cao — đọc code + đo |
| **N6** | **Cảnh báo domain shift synthetic**: người dùng naive (classifier AP 0.98 trên synthetic held-out) gh vào pipeline → LB **rơi 0.910→0.906**. Phải pretrain + finetune real + calibration, không dùng thẳng | Juan Neira (1722nd) | Trung bình — n=1 nhưng đúng lý thuyết |

**Bổ trợ vận hành:** Hammad Farooq (741242): PPSWEEP chọn tight55 mọi rerun (3 nguồn độc lập xác nhận: ta + Hammad + 0.946-work) → hardcode được để tiết kiệm ~51 phút GPU/run. Áp cho ta mức THẤP (run 6.2h/12h, không có HOCT; hidden test ≈ train size nhưng vẫn dư ~5.8h).

**Xác nhận frontier:** zhincez "0.947 runnable" = Reyhan v5 chỉ đổi input paths → ver-7 của ta vẫn đúng frontier public. Cụm 0.948+ vẫn private tweaks. Lê Quang Cảnh đã leo lên **0.952 (hạng 32)** — bằng asymmetric gate + các thử nghiệm division anh ta công bố — nghĩa là đường division evidence ĐANG TRẢ THƯỞNG THẬT cho người khai thác.

---

## 1. BẬC NHÂN QUẢ — SUY DIỄN TỪ METRIC XUỐNG THAM SỐ

### Bậc 0 — Cấu trúc metric (bất biến)

`score = adjEJ + 0.1 × divJ`, `divJ = tp/(tp+fp+fn)`, match node ≤7µm.

- Trạng thái ta (LB 0.947): adjEJ ≈ 0.928 → 0.1×divJ ≈ 0.019 → **divJ ≈ 0.19 trên LB**
- Trần divJ = 1.0 → **+0.081 điểm còn treo** trên kênh division
- Mỗi TP fork thêm vào denominator hiện tại ≈ +0.1/(tp+fp+fn); mỗi FP bỏ khỏi denominator cũng vậy

### Bậc 1 — Phân bào chết ở đâu (chuỗi nguyên nhân)

```
GT division (151 thật / 304 ước tính)
  │
  ├─ [T1] Detector: tìm thấy parent + 2 con — 100% (N3: 7/7) ← KHÔNG phải nút thắt
  │
  ├─ [T2] Linking: cạnh con thứ 2 bị gate 1-1 từ chối — 0% qua (N3: 0/7)
  │     └─ Nguyên nhân gốc: motion-relink Hungarian 1-1 phá fork (N5)
  │        + gate linking (~5.5-6µm) < bước mẹ→con (median 8.47µm, max 13.65µm)
  │
  ├─ [T3] Safe-div post-hoc: rank key hình học tiêu budget ~5 fork/khung
  │     vào DUPLICATE (đã biết từ megayak) — chỉ 23-35/151 reachable
  │     └─ Divergence 2.25µm nằm median phân bố thật (giết 50%)
  │        Symmetry 0.6 = p60 — giết thêm ~40%
  │
  └─ [T4] DivNet ranker (ver-8): đã chạy đúng (rank_flips, p_added 0.21-0.70)
        nhưng chịu 2 giới hạn: (a) checkpoint học từ ít dữ liệu thật,
        (b) vẫn xếp HÌNH HỌC là chính, ML chỉ re-rank trong top
```

### Bậc 2 — Nhân quả của từng đòn sửa (kỳ vọng đo được)

| Đòn | Nguyên nhân nó tác động | Cơ chế | Kỳ vọng Δscore | Chi phí | Rủi ro |
|---|---|---|---|---|---|
| **D1. Re-parent mở edge_prob (v2 đang chạy)** | T2 | thêm cạnh con thứ 2 cho fork có bằng chứng DivNet | +0.001..+0.005 (Δproxy +0.0080 đã đo v1; v2 nhắm 3/6 ca còn chặn) | 0 (đang chạy) | div_fp nổ → cổng Phase B chặn |
| **D2. Divfix repeat-lineage** | T4 (FP) | xóa fork lặp lineage — đo TRỰC TIẾP trên submission ta: **19/188 forks = 10% là repeat** → xóa 19 cạnh | **+0.001..+0.003** (pawanmali +0.0021; thang: div_fp −15 → divJ +~0.03 → +0.003 tổng) | ~0 (CPU output-level) | ~0 (chỉ xóa cạnh, audit topology giữ nguyên) |
| **D3. DivNet-v2 pretrained synthetic** | T3 (thiếu dữ liệu học) | 165k divisions giám sát → ranker bằng chứng mạnh; finetune real 151 + calibration | +0.002..+0.008 (trần lớn nếu div_tp bùng) | 1 GPU run train (~1-2h) + 1 run inference | N6: domain shift → PHẢI finetune+calibrate; kết cấu pipeline không đổi |
| **D4. Feature volume-shrinkage** | T3 (rank key nghèo bằng chứng) | parent volume trajectory (ngưng tụ -2/-1 trước tách) + peak-brightness thay mean → đưa vào rank key/DivNet | +0.001..+0.003 | CPU (đọc frame tại vị trí candidate — đã có sẵn pattern gap-refine) | thấp (feature phụ, không gate) |
| **D5. Asymmetric daughter gate (~2× continuation)** | T2 | kênh riêng cho arc con: 9.9-12µm bắt 71-86% (N3) | gộp trong D1/D3 | 0 | div_fp nếu không kèm evidence |
| **D6. Hardcode tight55** | vận hành | tiết kiệm 51 phút GPU/run | 0 điểm (bảo vệ runtime) | 0 | 0 — nhưng ta đang dư giờ, ưu tiên thấp |

### Bậc 3 — Tương tác (cộng dồn hay triệt tiêu?)

1. **D2 + D1/D3 cộng dồn, không xung đột**: D2 chỉ xóa FP đã có (repeat forks), D1/D3 thêm TP chưa có. Trên thang divJ: tử số (tp) tăng từ D1/D3, mẫu số giảm từ D2 → nhân đôi tốc độ.
2. **D4 nuôi D3**: volume trajectory + peak là input features tự nhiên của DivNet-v2 — synthetic cũng sinh được 2 feature này (generator có ground truth hình dạng) → pretrain khớp schema.
3. **D5 KHÔNG nên làm thêm nếu D1 đã cho kết quả tốt** — cùng tác dụng (thêm arc con thứ 2), làm cả hai dễ double-count → div_fp. Nguyên tắc: một cơ chế một việc.
4. **N5 khẳng định triết architect của ver-8**: vì fork ILP bị relink phá, mọi division work phải POST-LINK (như ta) hoặc sửa relink giữ fork (sửa lớn, rủi ro cao, không làm gần deadline).

### Bậc 4 — Ràng buộc thời gian/quota (cái cửa thực)

- GPU 8.68h còn → **1 run train DivNet-v2 (~1.5h) + 1 run ver-9 inference (~6h) = 7.5h** → vừa vặn, không dự phòng → nếu 19/9 (+30h) còn dư thì v9.1
- 5 submit/ngày; v8-v1 đã dùng 1 hôm nay; v2 sẽ cần 1 khi xong
- **Entry deadline 22/9**: v9 phải push trước ~20/9 để có thời gian rerun nếu fail
- Refresh 19/9: +30h GPU → dư cho vòng v9.1/v10 sau

---

## 2. KẾ HOẠCH V9 — 3 WAVES THEO NHÂN QUẢ

### Wave α — CPU 0 GPU (NGAY HÔM NAY, song song chờ v2)

**α1. Port divfix repeat-lineage filter vào ver-8 monolith** như PP candidate `rlf`:
- Hàm `apply_repeat_lineage_filter(edges, pos, stats)` chạy SAU re-parent, TRƯỚC audit topology
- Walk predecessor bằng đồ thị gốc (transitive), xóa cạnh con XA nhất theo µm của fork có ancestor cũng là fork
- Assert node-set bất biến + re-audit (max_out 2, max_in 1, t+1 consecutive)
- Thêm `rlf` + `rlf-ep50` + `rlf-ep75` vào PP_CANDIDATES (tổ hợp với re-parent prob)
- **Đo trước bằng graph-cache mini-kernel (E5)**: áp filter lên 8 video held-out cache → official rule → kỳ vọng div_fp giảm ≥3, ΔadjEJ ≥ -0.0002 (cạnh bị xóa hầu hết FP)

**α2. Chế DivNet-v2 training data từ synthetic** (attach notebook output `josefreitasalvesneto/biohub-synthetic-dataset` làm input kernel):
- Parse seq_XXXX.npz: nodes (t,z,y,x,lineage_id), edges, divisions (mitotic parent indices)
- **CẢNH BẪY (tác giả cảnh báo)**: nodes[:,4] = lineage/clone id KHÔNG unique track — 2 con cùng track_id; lineage thật nằm trong edges; build candidate graph từ edges
- Positive: 165k mitotic parents + 2 con; Negative hard: duplicate pairs (2 detections sát nhau — đúng lớp FP budget đang tiêu), broken continuations (orphan 8.5-10µm — N5/Lê đo), fork giả ngẫu nhiên
- Features schema (khớp DivNet hiện tại + mới): parent_dist, sister_dist, symmetry, diverge, **peak-brightness parent/con (N4: dùng peak KHÔNG dùng mean)**, **volume trajectory parent (-2..0, +1..+3) (N4)**, motion history parent
- Loss: BCE với positive weight ×15.7 (reweight 4.07% → 0.26%)

### Wave β — 1 GPU run train (~1.5h, sau khi α xong)

**β1. Train DivNet-v2**: pretrain synthetic (2-3 epoch trên ~50k samples cân bằng lớp) → finetune real GT (151 divisions + hard negatives từ train, 20 epoch) → **calibration** (temperature scaling trên held-out real — đây là thứ Juan Neira thiếu, N6)
- Unit test 7/7 pattern như DivNet v1 + test calibration (ECE < 0.05)
- Artifact: dataset riêng `biohub-divnet-v2-weights` (kiểu divnet/v2/best_overall.pt hiện có)

### Wave γ — 1 GPU run ver-9 (~6h) + submit (khi v2 có kết quả + cổng)

**ver-9 = ver-8 + cấu hình thắng từ v2 + DivNet-v2 + rlf + volume/peak features:**
1. REPARENT config theo kết quả v2 (nếu rp-ep75 thắng cổng → mặc định 0.75)
2. DivNet-v2 thay checkpoint v1 trong `_divnet_rerank_proposals` (W_um theo E5)
3. `rlf` filter bật cố định (nếu E5 xanh) + PP candidate `rlf-*` để sweep kiểm chứng
4. Rank key: thêm `+ W×peak_ratio + W2×vol_shrink` vào geom key trước DivNet re-rank (feature rẻ, không cần gate)
5. VALIDATOR_N_PER_TYPE=4 giữ; official eval system-view giữ; **hardcode tight55** (xóa PPSWEEP 51 phút — thêm giờ dự phòng cho hidden test ~199 videos, mua bảo hiểm runtime cho private LB)

**Cổng submit Phase B v3 (siết thêm rlf):**
- ΔadjEJ ≥ -0.0005 (system-view official, 8 video)
- div_tp ≥ +2 HOẶC div_fp ≤ -3 (rlf đường D2)
- guards 5/5 như cũ + guard mới G6: số cạnh bị rlf xóa ∈ [10..40] trên toàn test (anomali nếu 0 = filter chết; >50 = quá tay)

### Cây quyết định theo kết quả v8 (chờ 2 tín hiệu)

```
v8-v1 điểm LB khi có:
├─ ≥ 0.948        → v9 = v8 + D2(rlf) + D4(features) — CONSERVATIVE (chỉ đòn 0-GPU-risk),
│                    DivNet-v2 thành v10 nếu quota refresh 19/9 cho phép
├─ 0.947..0.948   → v9 full stack (D2+D3+D4) — cần thêm div_tp
└─ < 0.947        → chẩn đoán regression qua so v2 rp-* candidates trước mọi push v9
v8-v2 kết quả PPSWEEP (khi COMPLETE ~08:00-09:00 UTC):
├─ rp-ep75 thắng cổng (Δproxy≥+0.005, div_fp≤+3) → REPARENT_EDGE_PROB=0.75 mặc định v9
├─ rp-ep50 thắng → 0.5
└─ rp-off thắng (re-parent hại) → bỏ D1, v9 = rlf + DivNet-v2 + features
```

---

## 3. SỐ LIỆU MỚI ĐO TRỰC TIẾP (ngày 15/9)

- Submission ver8-v1: **188 forks / 19 repeat-lineage (10%) / 19 cạnh xóa được** (44b6_0113de3b: 7, 44b6_0b24845f: 5, 6bba_05b6850b: 4, 6bba_05db0fb1: 3) — trần D2
- Leaderboard 3561 đội; top-50 0.951+; Lê Quang Cảnh 0.952 (hạng 32) — bằng chứng division-paying
- Kaggle API hoạt động; 4 submission hôm nay còn 4 (v8-v1 đã dùng 1); v8-v2 kernel RUNNING

## 4. File lưu trữ mới

| File | Nội dung |
|---|---|
| `api/research/0949-research/pawanmali_biohub-942tta-fork-divfix-v1/` | notebook divfix (báo cáo subagent kèm trong VER9-APPENDIX) |
| `api/research/0949-research/zhincez_a-dividing-nucleus-gets-smaller-not-dimmer/` | notebook đo N4 |
| `api/research/0949-research/binasalama_biohub-learned-unet-transformer-ilp-gap-recovery/` | notebook gap (kết luận: đã có trong stack ta; giá trị = profile clean-strict 0.985) |
| `api/research/0949-research/zhincez_biohub-0-947-lb-runnable-with-public-datasets/` | xác nhận = Reyhan v5 |
| `api/research/0949-research/caassicca_biohub-v5-thr099b/` | DET_THRESHOLD 0.99 probe |

## 5. Nguyên tắc mới (từ tri thức mới)

9. **Pretrain-synthetic phải finetune-real + calibrate** — không dùng thẳng (N6, -0.004 LB của Juan Neira)
10. **Dùng peak, không dùng mean, khi so sáng độ** (N4 — mean bị nhiễm kích thước)
11. **Một cơ chế một việc** — D1 (re-parent) và D5 (asymmetric gate) cùng tác dụng, không cộng lắp
12. **Divisions là bài toán RANKING-BY-EVIDENCE trong budget, không phải bài toán gate** (megayak + N3 + N5 cùng chỉ về một điểm: người thắng chỗ này là người rank bằng chứng tốt nhất — Lê 0.952 đang chứng minh)
