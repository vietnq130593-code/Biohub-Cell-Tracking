# VER-7 — CHECKLIST RÀ SOÁT TOÀN BỘ TẠI CỔNG PHASE B

> Được kích hoạt theo yêu cầu: *"ver-7 triển khai đến phase B thì tiến hành rà soát lại toàn bộ
> xem có lỗi, vấn đề, thiếu sót gì không thì khắc phục nếu có rồi mới triển khai các bước tiếp theo."*
> Thực thi NGAY SAU khi run ver-7 COMPLETE và output đã được kéo về local.
> (Bản tái tạo sau rollback — nội dung giống hệt bản viết trước rollback.)

## A. Tính toàn vẹn port (nguồn: PORT-CHECKLIST.md §1)
- [ ] Notebook kéo về từ Kaggle (`kernels pull`) == notebook local (cell source từng ký tự)
- [ ] `grep -c reyhanksatria ver-7/cell-monolith.py` = 0
- [ ] `py_compile` PASS
- [ ] Khôi phục `api/research/reyhan-947-full.py` (khối monolith trừ 3 dòng header + 5 nhóm path)
      → diff kiểm tra chỉ chạm đúng các dòng đó

## B. Sức khoẻ run (log `biohub-ver7.log`)
- [ ] 0 dòng ERROR / Traceback
- [ ] Tag kỳ vọng xuất hiện: `EXPERIMENT_TAG='secondary_deepcenter_tta_0947'`; `EDGE_TTA_ACTIVE views=8`;
      `SECONDARY_EDGE_TTA_ACTIVE views=8`; `DEEPCENTER_TTA_ACTIVE views=8`; `PPSWEEP` chọn config
      với MAX_ADJ_LOSS=0.0005 / SELECT_MARGIN=0.001
- [ ] Dòng kết thúc: `PRODUCTION SUBMISSION PIPELINE: COMPLETE`
- [ ] Run-time trong dải 40–75 phút T4×2

## C. submission.csv (output/latest/submission.csv)
- [ ] Số dòng ~241k (dải 235k–248k — 4 phim test; ver-6 = 241.761)
- [ ] Header đúng format (so khớp ver-6)
- [ ] 4 dataset test đều có node
- [ ] Ghi sha256 vào hồ sơ (đối chiếu nếu re-run)

## D. Audit (dual_seed_frame_retention_guard_report.json)
- [ ] `ground_truth_accessed: false` (hoặc tương đương — guard report không có dấu hiệu đọc GT)
- [ ] Audit SHA256 weights/repo PASS (trong log S1)
- [ ] Fallback frames ở mức thấp (ver-6: 65/400 worst) — không phim nào sụp primary thuần

## E. Phase B — official eval
- [ ] `eval_report_error.json` KHÔNG tồn tại (nếu có → đọc lỗi, khắc phục, cân nhắc re-run)
- [ ] Self report: đủ stems (kỳ vọng 8 = 4/type × 2 prefix)
- [ ] Baseline v6 report: ≥ 4 stems chung với self
- [ ] Preview A/B trong log: Δproxy, ΔadjEJ, div_fn/div_fp
- [ ] t_true stem chung KHỚP giữa 2 report (guard G5)

## F. compare.py local
- [ ] Verdict + CI95 bootstrap + 5 guard (G1 div_fn, G2 div_fp, G3 node budget, G4 sụt per-video,
      G5 paired integrity)
- [ ] Gate: `adjEJ_official ≥ 0.942` HOẶC `proxy_official ≥ 0.945` trên tập TOÀN BỘ stems của self
- [ ] Verdict ≥ LIKELY-UPGRADE trước khi submit (INCONCLUSIVE/REGRESSION → KHÔNG submit, điều tra)

## G. Hạ tầng & quy trình
- [ ] 7 nguồn input gắn đúng (3 pilkwang + scorer + cv-pack + v6-preds + competition)
- [ ] GPU quota sau run còn đủ cho ver-7b (≥ 1 run ~50 phút)
- [ ] Quota submit còn (5/ngày)
- [ ] state.json trỏ đúng ref + version

## H. Phán quyết cổng (chỉ được đi tiếp khi A–G sạch)
- [ ] **ĐI TIẾP Phase C** (push ver-7b + submit ver-7 nếu gate F đạt)
- [ ] Ghi mọi phát hiện + cách khắc phục vào worklog Task 35

## Lưu ý đã biết (KHÔNG phải lỗi)
- FutureWarning dask/skimage (io.py:6) — vô hại, KHÔNG sửa (phá audit SHA256, wheel pin offline)
- Validator nội bộ + PPSWEEP của Reyhan dùng divJ rule cũ — cố ý giữ nguyên (0.947 LB-verified)
- Điểm chấm submission mất 6–12h — bình thường (hidden test ≈ training size)
- Run-time dài hơn ver-6 là KỲ VỌNG (TTA 8-view nhiều lớp + validator 8 video + eval cell 12 lần chấm)
