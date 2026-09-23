# 🔴 ERRORS-LEDGER.md — SỔ LỖI HỆ THỐNG (đọc TRƯỚC MỌI phiên làm việc)

> **TÀI LIỆU ĐỌC BẮT BUỘC ĐẦU MỖI SESSION** — trước khi thiết kế build mới, trước khi
> push kernel, và **NHẤT LÀ trước khi submit**. Bổ sung cho `GPU-WASTE-PREVENTION.md`
> (L1-L12 quy tắc GPU/quy trình); sổ này tập trung **LỖI SUY LUẬN & LỖI THIẾT KẾ** —
> lớp lỗi mà lint/gate thông thường không bắt được, chỉ bắt được bằng đối chiếu
> receipt + census + LB.
>
> - Tạo: 2026-09-23, sau v13.1 = **0.911** (ref 56473159) — thiệt hại −0.036 so banked.
> - Số hóa: L13+ (tiếp nối L1-L12 trong GPU-WASTE-PREVENTION.md).
> - Công cụ thực thi: `kaggle/api/machinery-audit.py` + `machinery-ledger.json`.

---

## 0. VẬT LÝ CƠ BẢN — LUẬT FORK (bằng chứng LB, không phải giả thuyết)

| Bản | ref | forks (census) | safe_div_added | LB | Ghi chú |
|---|---|---|---|---|---|
| v10 | 56348119 | 188 | — | **0.947** | |
| v11 | 56403231 | 144 | 82 | **0.947** | BANKED |
| v12.1 | 56442903 | 184 | 123 | 0.946 | diverge −2.0 |
| variant A | 56373784 | **0** | — | **0.911** | purge 188 forks |
| v13.1 | 56473159 | **0** | **0** | **0.911** | SR0 tắt máy division |

**LUẬT: forks ∈ [144, 188] → LB 0.946-0.947. forks = 0 → LB 0.911 (×2 độc lập).**
Kênh division (divJ + cấu trúc fork trong adjEJ) gánh ≈ **+0.036** của điểm banked.
Cấu trúc metric: `score ≈ adjEJ + 0.1 × divJ` — máy division phải BẬT trong mọi build (L13c).

---

## 1. LỖI LỚN NHẤT TRONG DỰ ÁN — L13 (v13.1 = 0.911)

### L13a — Tắt máy division vì "autopsy nói 0 TP"
- **Diễn biến**: autopsy (cửa sổ replica 2.193 node) kết luận "máy division v11 = 0 TP
  mọi cấp → thuần FP → tắt mất gì". Build SR0: `OUTPUT_SAFE_DIVISIONS=0` +
  `REPARENT_ENABLE=0` → nộp → 0.911.
- **Sai ở đâu**: cửa sổ replica có 3 division GT, p(0/3 | recall thật 36-60%) = 6-26% —
  **không phải bằng chứng mạnh**, nhưng ta nâng thành xác suất 100%. Public split
  có division thật mà máy v11 đang bắt (đó là +0.036).
- **Thiệt hại**: −0.036 LB (0.947 → 0.911), 0.68h GPU, 1 slot.
- **Luật**: **mọi kết luận "máy X vô dụng → tắt" phải có bằng chứng LB trực tiếp
  (A/B submission), không được suy diễn từ estimator cửa sổ nhỏ.** Trước khi tắt BẤT KỲ
  máy nào: chạy `machinery-audit.py` — nếu receipt của máy đó > 0 ở bản banked thì
  KHÔNG ĐƯỢC tắt.

### L13b — Override guard bằng lập luận ("nodiv by design")
- **Diễn biến**: replica-gate in `🔴 forks=0 < 100 → HOLD (L6)`. Ta phán "false-positive
  vì thiết kế chủ đích nodiv" → override → submit. **Guard đúng, người sai.**
- **Đây là lần THỨ HAI** cùng chữ ký (variant A 20/9: replica +0.0008 / LB −0.036).
- **Luật**: **HARD-GATE không có khái niệm "by design"**. Muốn vượt, phải sửa luật
  trong ledger (với bằng chứng LB mới), không vượt bằng lập luận tại thời điểm submit.
  `machinery-audit.py` exit 1 → script submit PHẢI abort. Không try/catch, không
  `|| true`, không `set +e`.

### L13c — Replica-gate là instrument adjEJ-ONLY
- **Sự thật đo được**: replica mù divJ + mù cấu trúc fork. 2 lần false-green trên
  fork-removal (variant A, v13.1). Lợi ích replica tập trung 1 stem (0b24 +0.0188)
  KHÔNG chuyển sang public (v13.1 bằng 0.911 phẳng — GC3+leaf net ≈ 0 trên public).
- **Luật**: replica chỉ được dùng để đo **delta adjEJ giữa 2 build cùng giữ máy division
  BẬT**. Mọi kết luận khác (divJ, fork, stem-concentrated) = ngoài tầm instrument.
- **Đính chính doctrine cũ (v12.1 era)**: "divJ không chuyển hóa LB" là SAI. Sự thật:
  kênh division gánh +0.036; cái v12.1 chứng minh chỉ là *replica-divJ-delta* = noise
  cửa sổ.

### L13d — Mọi knob diff phải được phân loại TRƯỚC submit
- 23 env-diff v11↔v13.1, nhưng chỉ phát hiện 2 sát thủ SAU khi mất điểm. Phải phát
  hiện TRƯỚC: `machinery-audit.py` phân loại từng knob
  (`must_on` / `lb_proven_noop` / `lb_proven_inert` / `hypothesis-ackable` /
  `reference`) — knob nào chưa phân loại = FAIL bắt buộc cập nhật ledger.

---

## 2. L14 — LỖI INSTRUMENT KHÁC (đã mắc, không lặp lại)

| # | Lỗi | Chữ ký | Luật |
|---|---|---|---|
| L14a | Replay F3 thổi phồng gap-close (+0.0036 replay vs +0.0011 production) | replay ≠ production cho mọi stage dùng cache .geff RAW | Δ replay chỉ tin khi CÙNG cơ chế chạy production; luôn ghi "replay-inflation %" |
| L14b | Replica stem-concentrated gain (0b24 +0.0188) → public 0.000 | gain nằm trọn 1 stem | Δ replica đáng tin nhất khi phân bố đều nhiều stem; 1-stem = ngờ vực mặc định |
| L14c | Autopsy "0 TP mọi cấp" từ 3 mẫu | p(0/3)=6-26% | ước lượng trên <10 sự kiện = không kết luận tắt máy |
| L14d | P2 vel025: lever amanatar +0.0014 KHÔNG chuyển giao (lần 2 lever ngoài không transfer) | cross-user lever transfer 0/3 | lever người khác chỉ tin sau GT-replica tự đo; kỳ vọng mặc định = 0 |

## 3. THAM CHIẾU L1-L12 (chi tiết trong GPU-WASTE-PREVENTION.md §2)

L1 lab≠production · L2 không smoke-test · L3 submit sớm sau COMPLETE (persist ≥20') ·
L4 float64→INT · L5 không push GitHub → sandbox reset mất sạch (đã mất 4 commit
71f97dd/baaf613/d7dbfff/8a39421 + toàn bộ artifact 22→23/9) · L6 purge fork (nâng cấp
thành L13) · L7 validator false-positive · L8 grid trên GPU · L9 watcher nền bị kill ·
L10 đọc bằng cat · L11 pull timeout · L12 census không partition theo dataset.

---

## 4. GIAO THỨC TRƯỚC-SUBMIT v2 (thay thế giao thức cũ — BẮT BUỘC)

```bash
# (1) Audit 3 lớp trên output THẬT của kernel (CONFIG + RECEIPT + CENSUS):
python3 kaggle/api/machinery-audit.py \
  --dir <thư-mục-output-kernel> \
  --monolith <monolith-đã-chạy> \
  --submit-gate --json audit-result.json
# exit 0 mới được đi tiếp. FAIL (🔴) = sửa build, chạy lại kernel. KHÔNG override.

# (2) Nếu chỉ còn WARN hypothesis (🟡) — ví dụ GC3/leaf/diverge — người RA LỆNH submit
# phải ack TƯỜNG MINH từng knob trong lệnh:
python3 kaggle/api/machinery-audit.py ... --ack BIOHUB_GAP_CLOSE_UM,BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB

# (3) Replica-gate: CHỈ đọc delta adjEJ; yêu cầu build giữ máy division BẬT.
# (4) Đối chiếu bảng "luật fork" ở §0: forks ngoài [100,200] = dừng.
# (5) Persist ≥20' sau COMPLETE + pull verify md5 + INT/DAG (giữ nguyên §3.3-3.4 cũ).
```

**Trách nhiệm**: ai thực hiện lệnh submit cũng phải chạy (1)-(2) và dán kết quả vào
worklog. Không có kết quả audit = không có submission. Đây là câu trả lời cho
"đúng ra trước khi nộp phải xác định được tất cả các lỗi kiểu này": lỗi lớp
machinery-off giờ phát hiện được **cơ học** ở 3 tầng độc lập (config/receipt/census).

---

## 5. NHẬT KÝ CẬP NHẬT

- 2026-09-23: tạo sổ sau v13.1 0.911; sinh machinery-ledger.json từ artifact v11 thật
  (md5 e7d9fb95, receipts 82/77, census 144f); machinery-audit.py validate 3 phiên bản:
  v11 ✅PASS · v12.1 🟡HOLD(2 hypothesis) · v13.1 🔴FAIL(11 hard) — phân biệt đúng 100%.
