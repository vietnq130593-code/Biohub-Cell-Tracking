# V12-DEPLOY — Triển khai ver-12 (portfolio 4 trục)

## ⛽ GPU WASTE CHECK — bắt buộc (GPU-WASTE-PREVENTION.md §4)

- **GPU ước tính: ≤6.6h** (tối đa 3 lần production × 2.2h) + **0h thí nghiệm** — toàn bộ
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
  gapfill_*, safe_division_orphan_*) [ ] quota 5/ngày [ ] v10 banked 0.947 còn selectable
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
| `cell-monolith.py` | Monolith v12 đã build (5.539 dòng; ver-11: 5.107) |
| `make-ver12-ipynb.py` | Đóng gói notebook (23 mấu + guard 9 hằng) → download/ver12-cell-tracking.ipynb (354KB) |
| `v12lab.py` | **V12-LAB CPU-ONLY** (Phòng lab 1 REVIEW-1 redesign): selftest / validator / hidden --flips / replica |
| `V12-DEPLOY.md` | File này |

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
2. Chọn config thắng theo gates F1-F6 → ghi lại ver-12-config.json → python3 build-ver12-monolith.py
3. python3 make-ver12-ipynb.py → push Kaggle kernel biohub-ver12 (ktool push --ver 12)
4. Kernel ~2.2h GPU (READMIT/GAPFILL +CPU-phút) → poll ĐỒNG BỘ trong lệnh Bash (L9)
5. PRE-SUBMIT checklist (mục ⛽ trên) → CHỜ LỆNH SUBMIT CỦA USER
```

## 5. Sổ GPU (trung thực, cập nhật sau mỗi lần chạy)

| Ngày | Hạng mục | GPU |
|---|---|---|
| 20/9 (tích lũy) | ver-10/11 production + lab cũ | 15.1h/30h |
| **21/9 (hôm nay)** | **viết ver12 + v12-lab 3 lớp + replica** | **0.0h** ✅ |
| (dự phòu) | biohub-ver12 production ×1 + iterate ×≤2 | ≤6.6h |
