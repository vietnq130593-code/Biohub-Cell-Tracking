# V10-LAB — Phòng thí nghiệm không-GPU & lộ trình tấn công 0.948+

> Task gốc: BIO-STRATEGY-16 (16/9/2026) — trả lời câu hỏi của Mr. Architect:
> "Không dùng GPU Kaggle thì có con đường nào chạy thử các ver, xây công cụ đánh giá ver-8 vs ver-9
> làm nền tảng ver-10 (mục tiêu 0.948+)? Có nhất thiết cần GPU? Colab T4 thì sao?"

---

## 0. TL;DR

1. **KHÔNG bắt buộc GPU để đánh giá ver-8 vs ver-9.** Toàn bộ khác biệt giữa ver-8 ↔ ver-9 ↔ v10
   nằm ở **hậu xử lý (post-processing)** — chạy được thuần CPU. Phần nặng duy nhất (UNet detection)
   chỉ cần chạy **đúng 1 lần** để "đóng băng" raw graphs vào cache; sau đó mọi thí nghiệm đều replay
   CPU trong vài phút.
2. **GPU chỉ cần đúng 2 việc**: (a) 1 phiên dump raw graphs kiến trúc hiện tại — **Colab T4 free lo được**;
   (b) kernel production nộp bài — quota Kaggle GPU refresh **19/9**, deadline 29/9 → dư dả.
3. **Tôi không thể tự chạy Colab như Kaggle** (Google không có headless API, phải đăng nhập trình duyệt).
   Nhưng notebook được dựng tự chứa 100%: bạn upload → dán token → Run all (~30 giây công);
   notebook **tự upload kết quả về Kaggle dataset** → tôi đọc và tiếp tục tự động từ đó.
4. **Bài học ver-9 (TLE hidden test) chuyển thành nguyên tắc v10**: tách hẳn "phòng lab" (đánh giá
   đầy đủ, chạy bao lâu cũng được) khỏi "nhà máy" (kernel nộp bài tối thiểu tuyệt đối).

---

## 1. Sự thật nền — đã kiểm chứng 16/9 (UTC)

| Dữ kiện | Giá trị | Nguồn |
|---|---|---|
| Điểm public tốt nhất | **0.947** (ver-8 v3-fast, submission 56261360) | Kaggle API |
| Hạng / huy chương | **165/3602 → BẠC** (cắt top 180, dư 15 chỗ; vị 22/525 cụm 0.947 full-precision) | LB 16/9 10:39 |
| ver-9 (56261328) | **FAIL runtime hidden** (TLE) — không có điểm; KHÔNG phải vấn đề chất lượng | errorDescription |
| Resubmit 56276434 (10:29 16/9) | pending; **cùng scriptVersionId 350108883 = kernel v1 y nguyên** → deterministic, dự báo fail lần nữa | Kaggle API |
| Validator 8 stems (gate report) | veto2: adjEJ **+0.0017** (0.9287→0.9303) nhưng proxy **−0.006**, div_tp 4→3 → tín hiệu CHƯA kết luận được | ver9_gate_report.json |
| RLF | no-op trên validator (0 cạnh), 2/118.061 cạnh trên submission → **giá trị thực ≈ 0** | ver9_rlf_report.json |
| Quota GPU Kaggle | ~0.4h/30h còn — refresh **19/9 (T7)**; hôm nay T4 16/9; deadline **29/9** | worklog BIO-VERIFY-APP-16 |
| Cụm 0.948 (mục tiêu) | 55 đội (hạng 89-143) — cần thêm ~+0.001 full-precision so hiện tại | LB 16/9 |
| Hidden runtime ≈ | **5-7× public** (v8-v1: 6.2h public → TLE; v3-fast 1.74h → pass; ver-9 2.4h → TLE) | suy luận 3 điểm thực nghiệm |

**Kết luận về "chất lượng thật ver-9":** hiện KHÔNG thể biết từ LB (TLE cả 2 lần, lần 3 deterministic fail).
Nguồn thông tin duy nhất là validator 8 stems — đang mâu thuẫn (adjEJ +, proxy −). → Chính vì vậy
cần **lab mở rộng** thay vì đoán mò hoặc đốt lượt submission.

---

## 2. Có nhất thiết cần GPU? — Phân tích từng thành phần pipeline

| Thành phần | Cần GPU? | Chi phí thực đo | Ghi chú |
|---|---|---|---|
| UNet + edge prediction trên video mới | **CÓ** | T4×2: 1.74h cho 4 video public (v3-fast) | phần nặng nhất; hard-require CUDA trong monolith (dòng ~1094) |
| Hậu xử lý: tight threshold, re-parenting, DivNet rank, deepcenter veto, harmonic assoc | **KHÔNG** | ~17.5 phút/config cho 8 stems (đo từ ppsweep base 1049s) | DivNet 5.6MB, deepcenter nhỏ — CPU chạy tốt |
| HOCT consensus veto (transformer 6.25M tham số) | **NÊN CÓ** | T4×2: ~35 phút/8 stems; CPU ước 4-8h | mảnh duy nhất của post-processing cần GPU |
| Repeat-lineage filter (RLF) | **KHÔNG** | < 1 giây | thuần đồ thị |
| Official scoring (adjEJ, proxy, div_*) | **KHÔNG** | giây-level | thuần numpy |
| **Kernel production nộp bài** | **CÓ** (an toàn runtime) | 1.74h public ≈ 4-5h hidden (v3-fast) | 1 lần mỗi lần chốt version |

→ **Cho nghiên cứu/đánh giá: KHÔNG cần GPU Kaggle.** Cần đúng 1 phiên GPU bất kỳ nguồn nào
(Colab T4 hôm nay / Kaggle 19/9) để dump raw graphs của kiến trúc hiện tại; sau đó toàn bộ
không-GPU vĩnh viễn.

---

## 3. Kiến trúc V10-LAB: "1 lần dump — nhiều lần replay"

```
┌─ MỘT LẦN DUY NHẤT (GPU, ~1-2h) ────────────────────────────────────────────┐
│  Colab T4 (notebook v10-lab-colab.ipynb — user Run all)                     │
│  predict validator 8 stems bằng kiến trúc ver-9 thật (secondary TTA …)      │
│  → DUMP raw_graphs.json + gt_bundle.json (~vài chục MB)                     │
│  → replay grid đầu (ref / tight sweep / rlf / veto1 / veto2 / veto2rlf)     │
│  → UPLOAD toàn bộ về Kaggle dataset  vietnguyen130593/biohub-v10-lab-cache  │
└──────────────────────────────────────────────────────────────────────────────┘
              │ cache là dataset Kaggle của user
              ▼
┌─ NHIỀU LẦN TÙY Ý (CPU, không tốn quota GPU) ───────────────────────────────┐
│  • Kaggle CPU kernel (tôi tự động 100% qua API — quota CPU tách GPU):       │
│    attach lab-cache + scorer + divnet + deepcenter + support pack           │
│    → replay grid mở rộng, sweep mịn tight 4.5→7.0, tổ hợp config            │
│  • Sandbox (tôi, ngay tại đây): thống kê paired bootstrap, error analysis,  │
│    unit test mọi thay đổi code trước khi đưa vào kernel                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Tiền lệ đã được chứng minh** (không phải lý thuyết): ver-8 wave1 từng là CPU mini-kernel chạy
E0-E3 trên Kaggle **0 GPU** nhờ dataset `vietnguyen130593/biohub-v7-heldout-preds` (GEFF graphs
12MB) + `biohub-wave1-features`. V10-LAB chỉ là việc hiện đại hóa pattern đó cho stack hậu xử lý
ver-9 (deepcenter veto detector + DivNet rank + re-parent + HOCT veto + RLF).

**Nguyên tắc vàng rút ra từ 3 lần TLE (v8-v1, ver-9 ×2):**
> Kernel nộp bài KHÔNG chứa bất cứ thứ gì không cần cho việc sinh submission: không validator,
> không gate replay, không PPSWEEP, không audit mở rộng. Mọi đánh giá dời ra lab.
> (ver-9 đã TLE một phần vì ~2h validator + gate replay + HOCT 8 stems nằm trong notebook.)

---

## 4. Ba môi trường — ai làm gì, giới hạn gì

| | **Colab T4 (free)** | **Kaggle CPU kernel** | **Sandbox (máy này)** |
|---|---|---|---|
| Ai điều khiển | User: upload + dán token + Run all (~30s); tôi đọc kết quả qua dataset upload | **Tôi 100% tự động** (push/watch/pull qua API, như mọi ver trước) | **Tôi 100%** |
| Làm được gì | Predict mới (full-fidelity ver-9 graphs) + full grid **kể cả veto** + dump cache | Replay mọi config **không veto** (HOCT CPU quá chậm); sweep mịn | Unit test, thống kê paired/bootstrap, error analysis, soạn grid |
| Giới hạn | Không có API headless (Google bắt đăng nhập trình duyệt); session ~12h; ngắt nếu idle | Không predict được (CUDA hard-check + UNet CPU quá chậm); 12h/session | 2 vCPU/4GB RAM/7.5GB disk — không đủ tải data thật; cache JSON tải về được (~vài chục MB) |
| Dùng khi nào | **Hôm nay** (dump) + mỗi lần cần graphs mới (tăng N_PER_TYPE, kiến trúc đổi) | **Từ 17/9** — vòng lặp thí nghiệm chính | Luôn — vòng lặp phân tích & kiểm thử nhanh nhất |

Ghi chú quota Kaggle: **CPU kernel quota tách hoàn toàn khỏi GPU 30h/tuần** — wave1 đã chạy CPU
kernel khi GPU cạn, pattern chứng minh được. → 3 ngày chờ quota GPU (16-18/9) KHÔNG phải 3 ngày chết.

---

## 5. Thiết kế thí nghiệm — tách biến ver-8 vs ver-9

Mọi config replay trên cùng bộ raw graphs + GT (paired theo stem):

| Config | tight | veto | rlf | Trả lời câu hỏi |
|---|---|---|---|---|
| `ref` | 5.5/6.5 hardcode (chuẩn ver-8 v3-fast) | 0 | ✗ | baseline — chính là chất lượng v3-fast trên hệ đo |
| `tight_45…70` | global 4.5/5.0/6.0/7.0 | 0 | ✗ | tight tối ưu nằm đâu? (sweep từng bị cấm vì 86% runtime — trong lab CPU thì tự do) |
| `rlf_only` | mặc định | 0 | ✓ | RLF có thật sự giúp? (hiện tượng no-op dự kiến bị xác nhận/bác) |
| `veto1` / `veto2` | mặc định | 1 / 2 | ✗ | giá trị thật của HOCT veto; mode nào tốt hơn |
| `veto2rlf` | mặc định | 2 | ✓ | tái hiện ver-9 nguyên bản — so `ref` = đúng "ver-9 vs ver-8" |
| `veto2rlf+tightX` | best từ sweep | 2 | ✓ | **ứng viên ver-10** — tổ hợp thắng |

**Đo lường:** adjEJ (primary — 71k cạnh nên phân giải tốt), proxy_score, div_tp/fp/fn,
per-stem rows (bắt buộc lưu — gate ver-9 chỉ lưu aggregate nên không bootstrap được).

**Thống kê:** paired per-stem delta + bootstrap 95% CI (10k resample) mỗi config vs ref.
Độ phân giải hiện tại của 8 stems: per-stem adjEJ ∈ [0.815, 0.995], σ ≈ 0.07 → so unpaired
vô nghĩa; **paired là bắt buộc**; để resolve Δ ≈ 0.001 cần nâng `VALIDATOR_N_PER_TYPE`
(8 → 16 stems, chạy trên Colab, ~gấp đôi predict) hoặc phân tích per-edge.

**Sản phẩm đầu ra:** `v10_lab_report.json` + `v10_lab_rows.csv` + cache dataset —
nền tảng bằng chứng để chọn cấu hình ver-10.

**Cổng kiểm chứng cache (bắt buộc khi đọc kết quả Colab đầu tiên):** config `ref` phải tái lập
được số gate report cũ — adjEJ 0.9287 / proxy 0.9594 / div 4/1/8. Khớp → graphs faithful; lệch →
env lệch, dừng và audit trước khi tin bất kỳ config nào.

---

## 6. Cổng quyết định (đọc kỹ trước khi build ver-10)

- **D1 · tight sweep — EV cao nhất.** PPSWEEP từng chọn ppTight5565fb (proxy 0.9594) nhưng bị cắt
  khỏi production vì runtime. Sweep mịn per-prefix trong lab → nếu paired ΔadjEJ ≥ +0.001 CI-dương
  → đưa vào v10 với hardcode (chi phí runtime hidden = 0 vì vẫn không sweep trong kernel).
- **D2 · HOCT veto — chỉ giữ khi thỏa CẢ HAI:** (1) lab mở rộng (≥16 stems hoặc per-edge) xác nhận
  ΔadjEJ ≥ +0.002 CI-dương; (2) có phương án cắt runtime hidden xuống ≤ ~1h (budget cap cứng
  từng video + top-k candidate + bỏ validator). Thiếu 1 trong 2 → bỏ veto khỏi v10.
- **D3 · RLF — bỏ.** 0 cạnh validator / 2 cạnh submission / pawanmali đo trên pipeline khác.
  Chỉ giữ lại nếu lab 16-stems bắt được ≥ 20 cạnh repeat-lineage thật.
- **D4 · kernel production v10 = tối thiểu tuyệt đối:** v3-fast + đúng 1 cấu hình thắng,
  không validator, không gate, không sweep. Target runtime public ≤ 2h (≈ hidden ≤ 6h, biên 12h).
- **D5 · kỷ luật submission:** ≤ 2 lượt/ngày, mỗi lượt phải trả lời 1 câu hỏi đo lường trước
  (A/B tách biến), không nộp "hy vọng".

---

## 7. Lộ trình 16 → 29/9

| Ngày | Việc | Kết quả cần |
|---|---|---|
| **16/9 (T4)** | Build V10-LAB (plan + notebook Colab + CPU replay + tests). User chạy Colab T4 (~4-8h): predict + dump + grid đầu + upload cache | Cache dataset + báo cáo grid đầu |
| **17/9** | Tôi phân tích grid, push CPU kernel mở rộng (autonomous), sweep mịn; nếu Colab rảnh → run 16 stems | Bảng bằng chứng D1/D2/D3 |
| **18/9** | Chốt shortlist cấu hình v10 (≤ 3); build + test kernel production v10 local | Kernel v10 sẵn sàng push |
| **19/9 (T7)** | Quota GPU về → push kernel v10 GPU → verify runtime public ≤ 2h → **submit v10** | Điểm public v10 |
| **20-25/9** | Đọc điểm → iterate lab→production (mỗi vòng: lab chứng minh trước, submit sau) | Leo cụm 0.948 |
| **26-28/9** | Chốt 2 submission cuối: best-public + best-validator (đa dạng hóa rủi ro) | Slot an toàn |
| **29/9** | Deadline — chọn final submission | 🎯 0.948+ / bảo vệ bạc |

---

## 8. Rủi ro & giảm nhẹ

| Rủi ro | Xác suất | Giảm nhẹ |
|---|---|---|
| Colab ngắt idle giữa predict | TB | Notebook dump checkpoint từng stem; chạy lại chỉ predict stem còn thiếu (resume) |
| Upload dataset từ Colab fail | TB | try/except + hướng dẫn tải manual; user có thể treo file qua chat nếu cần |
| Cache graphs không faithful (env lệch) | Thấp | Notebook set env đúng hệ ver-9; meta.json ghi đủ env để audit; **cổng kiểm chứng ref = 0.9287/0.9594** (mục 5) |
| Tight sweep trên 8 stems nhiễu | TB | paired bootstrap + nâng 16 stems trên Colab nếu biên chưa rõ |
| CPU kernel 12h không đủ grid lớn | Thấp | mỗi config ~17-30 phút CPU; grid 10-15 config ≈ 3-7h — trong biên |
| Hết quota submit (5/ngày) | Thấp | D5 — kỷ luật 2 lượt/ngày có câu hỏi |

---

## 9. Artifacts build hôm nay (Task V10-LAB-1)

```
kaggle/ver-10-lab/
├── V10-LAB-PLAN.md              ← tài liệu này
├── cell-monolith-v10lab.py      ← monolith ver-9 + patch LAB_MODE (predict|cache) + dump + grid replay
├── lab-grid-block.py            ← block grid replay (nguồn inject vào monolith)
├── build-v10-lab.py             ← dựng 2 notebook từ monolith
├── test-v10-lab.py              ← unit test (pattern test-ver9-blocks.py)
└── README.md                    ← cách chạy + env + giả định kỹ thuật
download/
├── v10-lab-colab.ipynb          ← ★ USER CHẠY trên Colab T4 (token → download → predict → grid → upload)
└── v10-lab-cpu.ipynb            ← Kaggle CPU kernel cho tôi (replay trên cache, không veto)
```

**5 bước chạy Colab (cho user):**
1. Mở `colab.research.google.com` → File → Upload notebook → chọn `download/v10-lab-colab.ipynb`.
2. Runtime → Change runtime type → **T4 GPU** → Save.
3. Cell 2: dán Kaggle token (KGAT_…) vào dòng `KAGGLE_API_TOKEN = "..."`.
4. Runtime → **Run all** → xác nhận từng cell nếu Colab hỏi.
5. Đi làm việc khác ~4-8h (giữ tab mở). Xong: bảng kết quả in ra + cache tự upload về Kaggle
   dataset `biohub-v10-lab-cache` — tôi đọc và tiếp tục từ đó, không cần bạn làm gì thêm.

---

*Phụ tá: mọi con số truy vết được — submissions qua Kaggle API 16/9, gate report từ
`kaggle/api/output/latest/ver9_gate_report.json`, runtime từ ppsweep_state.json (base 1049.6s)
và run_stats các kernel trước.*
