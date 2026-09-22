# V13 KIẾN TRÚC — Trọng tâm adjusted_edge_jaccard trên nền v12.1-knockout

> Ngày 22/9/2026 · Deadline 29/9 23:59 · GPU còn ~15.85h/30h · quota 5/ngày
> Nghiên cứu nền: `V13-ADJEJ-RESEARCH.md` (giải phẫu amanatar + 20 thuật toán 4 lớp)
> Tài liệu này = **kiến trúc triển khai** của code đã viết xong (build + verify PASS).

---

## §0. TL;DR — 1 màn hình

| Câu hỏi | Trả lời |
|---|---|
| V13 là gì? | **v12.1-knockout (LB 0.946) + 4 đề xuất P1-P4** chuyển trọng tâm sang **adjEJ** — trục đã chứng minh chuyển hóa 1:1 sang public LB |
| Code đã viết? | ✅ 6 file: `build-ver13-monolith.py` (delta-patch 9 thay đổi từ v12) · `cell-monolith.py` 5.637 dòng (build PASS, determinism PASS) · `v13lab.py` (selftest PASS + sweep offline) · `make-ver13-ipynb.py` (notebook 362KB) · ktool ver-13 · `submit-v13.py` |
| Điểm khác lớn nhất vs research ban đầu? | ⚠ **ĐÍNH CHÍNH P1**: v11 production dùng diverge **0.5** (grid mn_p85_div05 — env dòng 102 ghi đè dòng 64; guard phase_g xác nhận), KHÔNG phải 2.25 như research ghi. P1 revert về 0.5. Arm F riêng đo 2.25 để so |
| Kỳ vọng | LB ≈ **0.948** (v11 0.947 + P2 +0.0014 + P3 +0.0004; P1 trả về baseline; P4 divJ-recall không tốn adj) |
| Bước kế tiếp (0 GPU) | `replica-gate.py --restore-gt` (1 lần) → `v13lab.py sweep` (6 arm × ~3 phút CPU, cổng G1-G5) → user đọc kết quả |
| GPU + submit | 0.71h/run (validator OFF như v12.1) — **chỉ khi user duyệt**; replica-gate xác nhận adjEJ > 0.9010 trước khi đề xuất submit |

---

## §1. Vị trí trong dòng dõi

```
v6 0.933 → v7 0.934 → v7b → v8 0.939(rep) → v9 → v10 0.947(HOCT mode1) → v11 0.947(mutualnn-off+pdiv)
  → v12 0.946 (portfolio 4 trục: diverge âm + orphan + readmit/gapfill — THẤT BẠI adjEJ −0.0012)
  → v12.1-knockout 0.946 (tắt READMIT/GAPFILL/LOWDET — composite replica 0.9141 nhưng adjEJ 0.8998)
  → V13 = v12.1-knockout + P1-P4  ← BẢN NÀY (mục tiêu adjEJ > v11)
```

**Bài học v12/v12.1 đã trả giá**: composite replica +0.0131 KHÔNG chuyển hóa LB (+0.0002); chỉ phần adjEJ −0.0012 chuyển hóa (0.947 → 0.946). V13 quay directed investment 100% vào adjEJ; divJ chỉ nhận kênh "miễn phí" (P4).

---

## §2. Kiến trúc tổng thể (không đổi từ v12 — ghi để đối chiếu)

```
┌─ Kaggle kernel biohub-ver13 (T4×2, Internet OFF, 9 input — giữ nguyên v11/v12)
│   [S1 monolith 5.637 dòng — 1 code cell]
│   ├─ env-blocks Phase A→I (legacy → [ver12] → [ver13] CUỐI CÙNG thắng)
│   ├─ guard _EXPECTED_NUMERIC 13 hằng (drift → RuntimeError chặn chạy)
│   ├─ predict subprocess (dual-seed harmonic + ILP + SEF_TTA + lowdet-dump*)
│   │      └─ viết .geff RAW → tracking_repo/predictions/.../split_0/
│   ├─ post-chain filter_output_graph() ← toàn bộ adjEJ levers ở đây (xem §5)
│   ├─ write_test_submission() → submission.csv (INT, node sorted, t→t+1)
│   └─ guard report phase_i_v13_adjEJ + EXPERIMENT_TAG v13 + run_stats.csv
└─ *knockout: READMIT/GAPFILL/LOWDET = 0 → dump không chạy, giữ 0.71h GPU/run
```

Kiến trúc quan trọng giữ nguyên: **builder pattern** (build từ monolith v12 đã chạy thật LB 0.946 bằng 9 delta-patch có must_count/replace_once + final-env assertion — không rebuild từ đầu, không rủi ro phát sinh lại bug v11-era), **kỉ luật env-ordering** (block [ver13] chạy sau cùng; REVIEW-2 v12 từng bắt bug [ver8] ghi đè im lặng — nay assert 14 key cuối file).

---

## §3. Bốn đề xuất P1-P4 — chi tiết triển khai

### P1 · REVERT trục diverge — `SAFE_DIV_DIVERGE_UM −2.0 → 0.5` + `SAFE_DIV_ORPHAN_ADOPT 1 → 0`
- **Cơ chế**: trả lại phép đo "2 con phải tản ra" (0.5µm — giá trị grid v11 `mn_p85_div05`) + tắt nguồn miễn-divergence cho mồ côi (+23 fork 05db). Với cả 2 flag về giá trị v11, gate safe-div **hành xử nguyên vẹn như v11** — mã v12 chỉ kích hoạt khi flag bật.
- **ĐÍNH CHÍNH quan trọng**: research §5 P1 ghi revert về 2.25 — **SAI**. Bằng chứng 3 nguồn: (i) env ver-11 dòng 64 set 2.25 nhưng dòng 102 (block grid v11) **ghi đè 0.5** — block sau thắng; (ii) guard report phase_g ghi `safe_div_diverge_um: 0.5`; (iii) config ver-11 label `mn_p85_div05` + grid receipt "adjEJ 0.931790". amanatar dùng 2.25 nhưng trên stack khác — arm F sweep đo riêng 2.25 để có số liệu so.
- **Kỳ vọng**: +0.001 adjEJ (trở baseline 0.947) · mất divJ replica 0.1429 (không chuyển hóa LB — §2.2 research) · fork 05db −23.
- **Rủi ro**: ~0 (2 env knob, đúng giá trị đã chạy 0.947).

### P2 · VELOCITY 0.25 — `MOTION_RELINK_VELOCITY_WEIGHT 0.5 → 0.25` ⭐ lever lớn nhất
- **Cơ chế** (B4): motion-relink dự đoán điểm đến `predicted = pos + W×velocity`. Tế bào phôi đảo hướng liên tục (không quán tính) — W=0.5 làm predicted **OVERSHOOT** → relink nối nhầm node láng giềng → FP cạnh + thay cạnh đúng. W=0.25 dự báo thận trọng hơn.
- **Bằng chứng**: sweep amanatar dose-response rõ — vel025 **+0.0014 adj** / vel075 −0.0007; combo thắng 0.948 của họ gồm vel025. Knob có sẵn trong monolith (dòng 495 constant + 2442 usage) — **chỉ đổi env, không đổi code**.
- **Kỳ vọng**: +0.0014 adjEJ. **Rủi ro**: thấp (1 knob post-link; sweep arm E cách ly đo riêng).

### P3 · LEAF-PRUNE 0.30 — port nguyên văn amanatar (~60 dòng code mới DUY NHẤT)
- **Cơ chế** (D3): cắt node lá "đuôi rác" cuối track khi **đủ 4 điều kiện**: out-degree 0 (tracker không tiếp tục được) · đúng 1 cạnh vào (không phải con division mơ hồ) · không ở frame cuối (terminal thật hợp lệ) · cạnh vào có learned prob < **0.30**. Single-pass, không cascade — bảo thủ theo thiết kế gốc.
- **Miễn trừ cấu trúc**: cạnh `edge_prob=None` (con do safe-div thêm) không bao giờ bị prune → **không đe dọa divJ**.
- **Call-site**: sau `filter_short_track_components`, trước `linefit_smooth_output_graph` — đúng vị trí amanatar (notebook dòng 1635-1639).
- **Bằng chứng**: leaf030 +0.0003 / t55_leaf030 +0.0004 adj; census họ −71 cạnh yếu; receipt counter `leaf_prune_nodes/edges`.
- **Kỳ vọng**: +0.0004 adjEJ · census ~−70 cạnh.

### P4 · DIVWIDE + DCSD — cổng hình học rộng hơn + DC lỏng hơn, GIỮ divergence nghiêm ngặt
- **Env**: `SAFE_DIV_MAX_UM 9→11 · SISTER 14→16 · EXISTING_CHILD 10→12 · DEEPCENTER_SAFE_DIV 0.2→0.15`
- **Cơ chế**: recall division từ vùng "hình học đẹp + model deepcenter xác nhận" — **KHÔNG** qua trục "hội tụ bất thường" (diverge-relax đã chết 2 nguồn độc lập: v12.1 LB −0.001 + amanatar diverge150 FP nổ 1→6, divJ 0.2308→0.1667).
- **Bằng chứng**: sweep amanatar divwide/dcsd giữ adj **nguyên vẹn** + divJ nguyên; census họ fork +28/+12 phim thưa (0113/0b24 — nơi GT div còn FN của mình), −21 phim dày; run_stats DC-rejected 536 vs mình 3177 → cổng DC đang thắt ruột nhất funnel.
- **Kỳ vọng**: adjEJ ~0 · divJ +0.05–0.15 nếu GT div public nằm phim thưa → composite +0.005–0.015. Đây là cách giữ "divJ/Division TP ≥ v12" mà không lặp lại đánh đổi adjEJ.
- **Rủi ro**: TRUNG BÌNH (stack mình có HOCT mode1 + mutualnn-off khác họ) → bắt buộc qua sweep arm D (V13−P4) cách ly + cổng census fork.

### Giữ nguyên từ v12.1-knockout (không đụng)
READMIT=0 · GAPFILL=0 · LOWDET=0 (E1+RUN2: node thêm hại 2 stem thưa −0.0013 adj, TP division không phụ thuộc) · reparent EP=0.4 (NO-OP production đã chứng minh) · SEF_TTA 0.75 · VALIDATOR=0 (0.71h GPU/run) · HOCT veto mode 1 · tight hardcode 5.5/6.5.

---

## §4. Bảng env diff v12.1 → v13 (toàn bộ thay đổi)

| # | Env key | v12.1 | v13 | Đề xuất |
|---|---|---|---|---|
| 1 | BIOHUB_SAFE_DIV_DIVERGE_UM | −2.0 | **0.5** | P1 (revert grid v11) |
| 2 | BIOHUB_SAFE_DIV_ORPHAN_ADOPT | 1 | **0** | P1 (tắt +23 fork 05db) |
| 3 | BIOHUB_MOTION_RELINK_VELOCITY_WEIGHT | 0.5 (default) | **0.25** | P2 (+0.0014) |
| 4 | BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB | *(không tồn tại)* | **0.3** | P3 (code mới) |
| 5 | BIOHUB_SAFE_DIV_MAX_UM | 9.0 | **11.0** | P4a divwide |
| 6 | BIOHUB_SAFE_DIV_SISTER_MAX_UM | 14.0 | **16.0** | P4a divwide |
| 7 | BIOHUB_SAFE_DIV_EXISTING_CHILD_MAX_UM | 10.0 | **12.0** | P4a divwide |
| 8 | BIOHUB_DEEPCENTER_SAFE_DIV_THRESHOLD | 0.2 | **0.15** | P4b dcsd |
| — | *(35+ env còn lại)* | nguyên vẹn | nguyên vẹn | base không đổi |

**Vì sao an toàn về ordering**: block `[ver13]` chèn NGAY SAU print `[ver12]` — mọi assignment v13 là **cuối cùng** trong file → thắng mọi block legacy. Builder assert final-env 14 key (8 v13 + 6 knockout chống hồi quy).

---

## §5. Post-chain pipeline (nơi adjEJ sống) — đánh dấu thay đổi v13

```
filter_output_graph(nodes_by_id, raw_edges)      ← .geff RAW (25.822n/24.999e cho 0113)
 1. edge-filter (t→t+1, ≤14µm, multi-parent/child repair)
 2. motion-relink          ← ★P2: W 0.5→0.25 (predicted position bớt overshoot)
 3. gap-close density-adaptive (+620n/1.240e — chung lineage, không đổi)
 4. gap2 recovery
 5. safe-divisions post-link ← ★P1: diverge 0.5 + orphan OFF (trở hành xử v11)
    │                           ★P4a: cổng hình học 11/16/12 (đề xuất divwide)
    │                           ★P4b: DC veto 0.15 (lỏng hơn, model xác nhận)
    └─ HOCT consensus veto mode 1 (fork protected — không purge được)
 6. reparent phase D (EP 0.4 — no-op production, giữ)
 7. division-geometry filter + prune-isolated
 8. short-track filter (min 6, adaptive rescue)
 9. ★P3 LEAF-PRUNE 0.30 (MỚI — cắt đuôi rạc trước khi smooth; miễn trừ division/terminal)
10. linefit smoothing
    → submission.csv (INT · node sorted · z/y/x = max(0, round))
```

**Vị trí P3 là chủ đích**: cắt "đuôi rác" TRƯỚC khi linefit làm mượt (đúng amanatar); chạy SAU short-track filter nên chỉ xử lý node sống sót chọn lọc — cực kỳ bảo thủ.

---

## §6. Hệ thống guard (chống drift im lặng — 3 lớp)

1. **Guard runtime** `_EXPECTED_NUMERIC` 13 hằng: 5 gốc nguyên vẹn (DET 0.965 · ILP app 0.0/dis 2 · GAP_CLOSE 5.0 · MIN_TRACK 6.0 · BIDIR 0.15) + 8 v13 (SAFE_DIV_MAX 11 · DC 0.15 · SEF_TTA 0.75 · **VEL 0.25** · **LEAF 0.3** · SISTER 16 · EXIST 12). Mismatch → `RuntimeError('Configuration drift...')` chặn pipeline ngay.
2. **Final-env assertion builder** (14 key): mọi `os.environ[KEY] = 'V'` cuối file phải = config — chống bug ordering kiểu [ver8] ghi đè EP 0.4→0.25 mà REVIEW-2 v12 từng bắt.
3. **Guard report** `phase_i_v13_adjEJ` + `phase_i` dict ghi đủ P1-P4 + tag `secondary_deepcenter_tta_0947_reparent_hoct_v13_p1rev_p2vel025_p3leaf030_p4divwide` (xuất hiện trong run_stats.csv → submit-v13 cổng [TAG] đối chiếu).

---

## §7. Phòng lab `v13lab.py` — sweep offline 0 GPU (đã chạy được, ~3 phút/arm)

**Nguyên lý**: trích env-block + constants + post-chain + scoring **từ chính monolith v13** (single source of truth) → exec namespace sạch/arm với env override → replay trên **.geff RAW 4 phim test** (từ output v12.1 — prediction stage không đổi theo knockout) → CSV (mirror production format) → chấm **cùng engine replica-gate** (đã verify v11 0.9010 EXACT).

**⚠ Độ tin cậy — đọc trước khi diễn giải kết quả** (F3 semantic delta):
- p_div (DivNet) + DC (deepcenter) **không replay được local** (bundle mất theo sandbox reset; model cần image volumes) → mọi arm đặt MIN_PDIV=0 + DC-VETO=0 **như nhau**.
- Hệ quả 1: **fork census tuyệt đối không so thẳng production** (đo thực: arm A fork 591 vs production 144 — DC 0.2 production giết ~450 fork). Node/edges khá tin cậy (arm A: 123.041n vs 122.787n = +0.2%).
- Hệ quả 2: **P4b dcsd tàng hình** trong replay (DC đã bypass) — chỉ đo được P4a divwide. P4b dựa vào sweep amanatar + cổng replica production sau GPU.
- **Δ GIỮA CÁC ARM là chỉ số đáng tin** (mọi arm cùng semantic delta).

**6 arm**:
| Arm | Cấu hình | Vai trò |
|---|---|---|
| A v11geo | diverge 0.5 · orphan 0 · vel 0.5 · leaf 0 · geo 9/14/10 | neo baseline |
| B v121geo | diverge −2.0 · orphan 1 | hiệu chuẩn hướng (production −0.0012) |
| **C v13full** | P1+P2+P3+P4a | **ứng viên GPU** |
| D v13noP4 | P1+P2+P3 (geo cũ) | cách ly P4 |
| E v13vel | chỉ P2 | cách ly velocity |
| F v13div225 | C nhưng diverge 2.25 | so 0.5 vs 2.25 (amanatar) |

**Cổng lên GPU** (auto-đánh giá cuối sweep):
- **G1**: Δadj(C−A) ≥ +0.0008 (kỳ vọng P2+P3 = +0.0018 — chặn nửa cho an toàn)
- **G2**: Δadj(B−A) < 0 — replay phải thấy đúng dấu thất bại v12.1 (instrument hợp lệ)
- **G3**: census C node ∈ [120k, 126k] · G3b không purge (A−C ≤ 3.000 node)
- **G4** fallback: nếu G1 fail nhưng Δadj(D−A) ≥ +0.0008 → lên GPU với v13-noP4
- **G5**: leaf receipts C ∈ [30, 400] (amanatar 71 — ngoài khoảng = suspect)

**Selftest đã PASS**: UNIT leaf-prune (prune đúng 1 lá yếu; miễn trừ prob-None ×2 + terminal ✓) · INTEGRATION trong post-chain ✓ · hồi quy v12 machinery (readmit 1/gapfill 3) ✓ · CSV INT ✓.

---

## §8. Kế hoạch triển khai + ngân sách

```
[GPU WASTE CHECK] — V13 port code 22/9: GPU 0.0h tiêu thụ (toàn bộ CPU-local).
```

| Bước | Việc | Chi phí | Trạng thái |
|---|---|---|---|
| 1 | Port code + build + verify (builder/monolith/lab/ipynb/ktool/submit) | 0 GPU | ✅ XONG |
| 2 | `replica-gate.py --restore-gt` (84 file GT, 1 lần — Kaggle API read-only) | 0 GPU | chờ duyệt |
| 3 | `v13lab.py sweep` 6 arm (~20 phút CPU) + đọc cổng G1-G5 | 0 GPU | sweep census-only ĐANG CHẠY |
| 4 | **User đọc kết quả sweep + kiến trúc này → quyết định** | — | ← BẠN Ở ĐÂY |
| 5 | `ktool.py push --ver 13` → poll (~35-55') | **0.71h GPU** | chờ lệnh trực tiếp |
| 6 | replica-gate trên output thật: **adjEJ > 0.9010** (v11) → mới đề xuất submit | 0 GPU | auto sau GPU |
| 7 | `submit-v13.py` (cổng INT/DAG/CENS/TAG tự chạy trước) | quota 1 lượt | **chỉ khi user ra lệnh** |

**Ngân sách**: GPU 15.85h còn − 0.71h v13 = dư 14+ hàng cho 2-3 vòng lặp (v13.1 tắt P4 nếu hại / v13.2 chỉnh vel). Deadline còn 7 ngày.

**Cây quyết định sau điểm LB**:
- ≥ 0.948 → giữ + backlog đòn kế (SEF_TTA A/B, keep-rate 0b24) hướng 0.955 huy chương
- = 0.947 → A/B P4 riêng (tắt P4 → so) — 0.71h
- < 0.947 → v11 banked 0.947 vẫn selectable an toàn; phân tích census output trước khi lặp

---

## §9. Rủi ro đã nhận diện + biện pháp

| Rủi ro | Xác suất | Biện pháp |
|---|---|---|
| P4 divwide thêm FP fork trên stack mình (khác amanatar) | TB | arm D cách ly + cổng census fork ≤ v12.1+40 + cây quyết định tắt P4 |
| P2 vel025 không cộng dồn từ tight55 (tương tác knob) | TB | sweep arm E đo riêng trên chính dữ liệu mình |
| Replay delta ≠ production delta (semantic F3) | Có | cổng THẬT là replica-gate trên output GPU; sweep chỉ là filter hướng |
| Leaf-prune cắt nhầm đuôi thật (recall rơi) | Thấp | miễn trừ 4 điều kiện + receipts + arm D đối chứng |
| Bug env-ordering trở lại | Rất thấp | final-env assertion 14 key + guard 13 hằng runtime |
| GPU nondeterminism giữa các run (2 entry v12.1 lệch 2MB cùng điểm) | Đã biết | kỳ vọng ±0.000; điểm công bố 3 chữ số |

---

## §10. Artifacts đã tạo (22/9)

| File | Vai trò | Verify |
|---|---|---|
| `kaggle/ver-13/ver-13-config.json` | config P1-P4 + receipts + đính chính P1 | — |
| `kaggle/ver-13/build-ver13-monolith.py` | builder delta-patch 9 thay đổi từ v12 | build PASS |
| `kaggle/ver-13/cell-monolith.py` | monolith 5.637 dòng (+95 vs v12) | py_compile · AST · determinism (md5 f35ae16f) · final-env 14 key · guard 13 hằng |
| `kaggle/ver-13/v13lab.py` | lab: selftest + sweep 6 arm + replica | selftest PASS · sweep arm A 4 phim chạy 193s |
| `kaggle/ver-13/make-ver13-ipynb.py` | đóng gói notebook | 25 mấu + cell==monolith |
| `download/ver13-cell-tracking.ipynb` | notebook 362KB đẩy Kaggle | JSON hợp lệ |
| `kaggle/api/ktool.py` (+ver-13) | push/watch/output/score ver 13 | resolve PASS (9 dataset · slug biohub-ver13) |
| `kaggle/api/submit-v13.py` | nộp + cổng PRE-SUBMIT (INT/DAG/CENS/TAG + counters leaf_prune) | py_compile PASS |

KHÔNG đụng Kaggle, KHÔNG tiêu thụ GPU — mọi hành động push/submit chờ lệnh trực tiếp user.
