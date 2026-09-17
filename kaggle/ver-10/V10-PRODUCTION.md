# V10 — PRODUCTION: v3-fast + HOCT veto MODE 1 + guard mật độ chống TLE

Ngày 17/9/2026 · Trạng thái: **KERNEL BUILD XONG + TEST 65/65 — chờ quota GPU 19/9 00:00 UTC để push + nộp**
Kernel: `vietnguyen130593/biohub-ver10` v1 (T4×2 · Internet OFF · 9 dataset · 1 code cell S1)

Đây là bản ghi quyết định + hồ sơ kỹ thuật của kernel nộp bài ver-10, xây theo **đúng khuyến nghị
§6 `V10-RESULTS.md`** (phân tích lab 17/9). Mọi số liệu đối chiếu từ kernel `v10-lab-gpu-t4` v2
(8 stems validator, T4×2, replay deterministic khớp gate ver-9 6 chữ số).

---

## 1. QUYẾT ĐỊNH

| Cấu hình | adjEJ (weighted 8 stems) | Δ vs v3-fast | proxy | div tp/fp/fn | Nộp? |
|---|---|---|---|---|---|
| ref = ver-8 v3-fast (LB 0.947) | 0.928665 | — | 0.959434 | 4/1/8 | (đang giữ bạc) |
| **v10 = v3-fast + veto MODE 1** | **0.930492** | **+0.001828** | **0.961262 (+0.001828)** | **4/1/8 nguyên vẹn** | **★ ỨNG VIÊN DUY NHẤT** |
| veto MODE 2 (≡ ver-9) | 0.930328 | +0.001663 | 0.953405 (−0.0060) | 3/1/9 (mất 1 tp) | ✗ đã TLE |
| rlf_only | 0.928665 | ±0.000000 | 0.959434 | 4/1/8 | ✗ ≡ v3-fast |
| tight toàn cục 4.5/5/6/7 | 0.926–0.9282 | −0.0004…−0.0026 | — | — | ✗ toàn âm |

- **Vì sao mode 1**: khác mode 2 đúng 1 dòng (`_hv_apply_veto`: `if (s,t) in hoct_pairs or (mode==1
  and out_deg[s]>=2): keep`) — giữ nguyên cả 2 cạnh của mọi node cha ≥2 con → division KHÔNG BAO GIỜ
  bị đụng; toàn bộ delta là adjEJ thuần. Mode 2 (ver-9 đã nộp) mất 1 div_tp trên 44b6_267148e4 →
  proxy −0.0060 → gate FALLBACK, cộng thêm TLE hidden.
- **Vì sao bỏ RLF**: Δ 0.000000 trên mọi metric (21 cạnh bỏ không đổi gì — trùng field ver-9 chỉ bỏ
  được 2/118.061 cạnh). Chạy chỉ tốn thời gian + rủi ro.
- **Vì sao giữ tight per-prefix 5.5/6.5**: sweep 4 giá trị toàn cục toàn âm — v3-fast đã tối ưu cục bộ.

## 2. GUARD MẬT ĐỘ CHỐNG TLE (bài học ver-9 fail hidden runtime)

Vấn đề gốc: guard ver-9 dự đoán TUYẾN TÍNH theo tổng node (9s/1000 nodes) — không nhìn mật độ
node/frame, trong khi chi phí HOCT ~ bậc 2 theo mật độ (ILP nối từng cặp frame kề: ~T·d² = n·d).
embryo-3 hidden dày nhất → dự đoán lệch nhiều lần → TLE 12h.

**Mô hình v10**: `est = k · n · d_max + fixed`, hiệu chuẩn từ 8 stems đo thật (T4×2, 17/9):

| stem | n (final) | d_max | đo thực | est v10 | est/đo |
|---|---|---|---|---|---|
| 44b6_12dfb391 | 44955 | 527 | 315s | 576s | 1.83× |
| 44b6_267148e4 | 22270 | 286 | 130s | 194s | 1.49× |
| 44b6_2a2eff9f | 40120 | 498 | 257s | 498s | 1.94× |
| 44b6_341df25f | 8413 | 102 | 65s | 69s | 1.06× |
| 6bba_062c8d37 | 5857 | 71 | 58s | 59s | 1.02× |
| 6bba_07e24132 | 29184 | 365 | 162s | 289s | 1.78× |
| 6bba_085bf656 | 8292 | 126 | 64s | 73s | 1.14× |
| 6bba_09961292 | 29747 | 348 | 162s | 279s | 1.72× |

- `k = 2.2e-5 s/(node·node-frame)` (đầu trên vùng fit 1.27–2.12e-5 — cố tình thiên về an toàn),
  `fixed = 50s` (đọc volume + rasterize sphere + snap).
- **Ba lớp phòng thủ**:
  1. `MAX_VIDEO_S = 300s` (từ 900) — video dự đoán vượt cap bị skip, giữ graph gốc.
  2. `DEADLINE = 7.5h` (từ 10.5) — video nào không kịp trước deadline bị skip/abort.
  3. `×3` khi `d_max > 550 nodes/frame` (vùng NGOÀI hiệu chuẩn — nơi đã giết ver-9) +
     **abort giữa video** ở biên chunk (`_hvDeadlineAbort` — không retry, fail-safe pass-through).
- **Mô phỏng trên 8 stems validator**: 6/8 được veto — gồm cả hai stem sinh gain chính
  (6bba_09961292 est 279s, 6bba_07e24132 est 289s < 300). Hai video 44b6 khổng lồ bị skip đều
  vô hại (12dfb391 ±0.0000; 2a2eff9f −0.0045 — skip còn GỠ thiệt hại trên validator).

## 3. CẤU TRÚC KERNEL (phẫu thuật từ monolith ver-9 đã chạy thật)

- Nền: ver-9/cell-monolith.py (chính là notebook biohub-ver9 v1 đã chạy Kaggle 15/9) —
  giữ nguyên toàn bộ pipeline 0.947: dual-seed TTA + re-parent + DivNet RANK-ONLY +
  tight per-prefix hardcode + base validator eval.
- **Xóa 207 dòng**: block [ver9-rlf] + [ver9-gate] (validator replay ~45'/lần public ×5-7 hidden).
- **Thay block [ver10-hoct]** (609 dòng, từ `hoct-veto-block-v10.py`): mode 1 mặc định +
  estimator mật độ + abort giữa chunk + đếm `aborted_deadline` riêng trong summary.
- **Bỏ S2 eval cell** → notebook 1 code cell (strip validator replay theo khuyến nghị).
- Env: `BIOHUB_HOCT_VETO=1` · `DEADLINE_H=7.5` · `MAX_VIDEO_S=300` · tight 5.5/6.5 giữ nguyên.
- Ước lượng runtime: public ~2.0–2.2h (v3-fast 1.74h + HOCT ~30'), hidden ~4–5h < hạn 12h
  (worst case với guard ~8–9h).

## 4. KIỂM CHỨNG

- `test-ver10-blocks.py`: **65/65 PASS** (0 GPU) — ngữ nghĩa veto mode 1/2, công thức estimator,
  hiệu chuẩn 8 stems (est ≥ actual toàn bộ, tỷ số 1.0–1.94×), budget decision (run/skip_cap/
  skip_deadline + ×3 ngoài vùng), snap 1-1 KD-tree, `_hvDeadlineAbort` nảy giữa chunk +
  không bị retry + `_hv_veto_video` bắt riêng (status `aborted_deadline`, graph gốc giữ nguyên),
  solver-failure vẫn retry 3 chunk đúng thiết kế, mấu tích hợp (strip sạch ver-9, gate production
  tau 0.6 / diverge 2.25 / re-parent 0.25), thứ tự block (arming → base write → finalize → audit).
- `py_compile` PASS; make-ver10-ipynb verify cell khớp nguyên văn + JSON hợp lệ.
- Metadata push: 9 dataset (7 ver-8 + 2 HOCT) + competition, T4×2, Internet OFF, private.

## 5. QUY TRÌNH NỘP (bị chặn quota tại thời điểm build)

- 20:22 UTC 17/9: push bị Kaggle từ chối cứng — `"Maximum weekly GPU quota of 30.00 hours
  reached"` (30.93/30h; v10-lab đã chạy vượt 3.6h khi quota gần cạn). Quota refresh **19/9
  00:00 UTC (~07:00 giờ VN)**.
- Một lệnh sau refresh: `bash kaggle/api/v10-launch.sh [--wait]` → chờ quota (tuỳ chọn) →
  push → watch (poll 60s, tối đa 5h) → submit (kagglesdk `create_code_submission` — cuộc thi
  notebooks-only, CLI file submit bị 400) → liệt kê điểm.
- Deadline cuộc thi 29/9 — dư 12 ngày sau khi quota về.

## 6. KỲ VỌNG & RỦI RO

- Pass hidden: 0.9475-0.9479 + 0.0018 → **0.948-0.949** → vượt cụm 55 đội 0.948 (hạng 89-143)
  → bạc chắc chắn (hiện 165, cắt 180) + mở đường 0.949.
- Bằng chứng phía ngoài cùng bậc: sjlee101 (tác giả port HOCT) đo +0.0040 CI-dương trên
  20 video honest split.
- Fail TLE (đã phòng 3 lớp): mất 1 lượt trong 5 lượt/ngày — v3-fast 0.947 vẫn là final.
- Sau nộp: theo dõi `kaggle competitions submissions -c biohub-cell-tracking-during-development`
  (cửa sổ chấm 6–32h như các lần trước).

## 7. FILE

- `hoct-veto-block-v10.py` — block veto mode 1 + guard mật độ (nguồn của block trong monolith)
- `build-ver10-monolith.py` — builder (phẫu thuật ver-9 → ver-10, 7 bước + kiểm tra sau xây)
- `cell-monolith.py` — monolith ver-10 (5090 dòng; ver-9 gốc 5250)
- `make-ver10-ipynb.py` — đóng gói notebook (header + S1)
- `test-ver10-blocks.py` — 65 unit test
- `../../download/ver10-cell-tracking.ipynb` — notebook đẩy Kaggle
- `../api/v10-launch.sh` + `../api/submit-v10.py` + `../api/ktool.py --ver 10` — hạ tầng nộp
- Đối chiếu: `../ver-10-lab/V10-LAB-PLAN.md` + `../ver-10-lab/V10-RESULTS.md` (phân tích lab)
