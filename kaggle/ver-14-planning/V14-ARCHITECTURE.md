# V14 KIẾN TRÚC — Phase K: hạ ngưỡng cạnh ứng viên (E1) để đẩy adjEJ

> Ngày 23/9/2026 · Deadline 29/9 23:59 UTC · GPU 17.2h/30h đã dùng (còn ~12.8h, refresh 26/9) · quota 23/9: 1/5 đã dùng
> Nghiên cứu nền: `ver-14-planning/V14-PLAN.md` (menu lever + GO/NO-GO formal)
> Trọng tài lỗi: `kaggle/ERRORS-LEDGER.md` (L13-L14) · Cổng cơ học: `kaggle/api/machinery-audit.py`
> Tài liệu này = **kiến trúc thiết kế TRƯỚC build** (code chưa viết — khác V13-ARCHITECTURE viết sau code).

---

## §0. TL;DR — 1 màn hình

| Câu hỏi | Trả lời |
|---|---|
| V14 là gì? | **v13.2 (restore-division, ref 56492596 PENDING) + 1 lever duy nhất E1**: `BIOHUB_DUAL_SEED_EDGE_THRESHOLD` **0.48 → 0.40** |
| Vì sao E1? | Hạ ngưỡng cạnh ứng viên → graph builder thấy thêm cặp (i,j) xác suất ∈ (0.40, 0.48] → **recall cạnh tăng** = trục adjEJ duy nhất đã chứng minh chuyển hóa 1:1 sang LB (v12.1: adjEJ −0.0012 → LB −0.001) |
| Điều kiện tiên quyết | **v13.2 LB ≥ 0.946** (carrier sạch — đang PENDING). < 0.945 → hoãn v14, điều tra tương tác GC3/leaf (v13.3 tách lever) |
| Code phải viết | 6 file theo pattern v13.2: `build-ver14-monolith.py` (1 delta-patch) → `cell-monolith.py` · `make-ver14-ipynb.py` · ktool `--ver 14` · `submit-v14.py` · ledger classification |
| Chi phí | ~0.7h GPU/run · 1 slot submit · mọi cổng cơ học giữ nguyên (không có override mới) |
| Kỳ vọng | 0.947-0.952 (probe khám phá — E1 KHÔNG replay offline được; rủi ro FP-precision đối trọng) |

---

## §1. Vị trí trong dòng dõi

```
v10 0.947 → v11 0.947 BANKED (mutualnn-off + pdiv 0.85 — máy division Σ82 safe-div)
  → v12 0.946 (portfolio 4 trục — adjEJ −0.0012: bài học trục adjEJ là trục thật)
  → v12.1 0.946 (knockout READMIT/GAPFILL/LOWDET)
  → v13.1 0.911 ★THẢM HỌA SR0 (tắt máy division — L13a-d)
  → v13.2 restore-division ref 56492596 (12:06 UTC 23/9, PENDING — receipts Σ85/Σ71/141f = đúng vùng banked)
  → V14 = v13.2 + E1 edge 0.40  ← BẢN NÀY (mục tiêu: adjEJ VƯỢT 0.947 lần đầu)
```

**Vì sao đứng trên v13.2 chứ không v11?** E1 cần carrier có (a) máy division sống (L13c — v11 thỏa nhưng thiếu GC3/leaf để so attribution), (b) mọi lever v13.2 đã được LB định giá. Nếu v14 chạy trên v11, kết quả 0.948 không tách được công E1 vs GC3/leaf. Trên v13.2: **delta duy nhất = E1** → mọi ± điểm đọc thẳng.

---

## §2. Kiến trúc tổng thể (không đổi từ v13.2 — ghi để đối chiếu)

```
┌─ Kaggle kernel biohub-ver14 (T4×2, Internet OFF, 9 input — giữ nguyên v11→v132)
│   [S1 monolith ~5.643 dòng — 1 code cell, base = v13.2 md5 9a0e872a]
│   ├─ env-blocks Phase A→J-bis (legacy → … → [ver131] → [ver132]) + [ver14] CUỐI CÙNG
│   │      E1 duy nhất: BIOHUB_DUAL_SEED_EDGE_THRESHOLD '0.48' → '0.40' (line ~1173)
│   ├─ guard _EXPECTED_NUMERIC 12 hằng (+ E1: 0.4) · _EXPECTED_TEXT 7 hằng (giữ nguyên v132)
│   ├─ predict subprocess (dual-seed harmonic + ILP + SEF_TTA + lowdet-dump off)
│   │      └─ predict_unet_transformer.py line ~720: candidates = [(p,i,j) if p > cfg.threshold]
│   │           cfg.threshold ← env E1 (line ~842: cfg.threshold = edge_candidate_threshold)
│   ├─ post-chain filter_output_graph() (safe-div + reparent + GC3 + leaf-prune 0.3 — GIỮ NGUYÊN)
│   ├─ write_test_submission() → submission.csv (INT, node sorted, t→t+1)
│   └─ _guard_report phase_k_v14_e1_edge040 + EXPERIMENT_TAG + run_stats.csv
└─ Machinery-audit 3 lớp (CONFIG/RECEIPT/CENSUS) — submit-gate exit-code TUYỆT ĐỐI (L13b)
```

Builder pattern giữ nguyên: **1 delta-patch từ monolith v13.2 đã chạy thật trên Kaggle** (output md5-verified a8f71aa1) — không rebuild từ đầu. Luật env-ordering: block `[ver14]` đặt SAU `[ver132]` (block sau thắng); patch dùng `replace_once` + `must_count=1` (fail-fast nếu anchor drift).

---

## §3. Lever E1 — chi tiết triển khai

### 3.1 Cơ chế (line-level, đã verify trong code thật)

1. **Env-block** (monolith line 1173): `os.environ['BIOHUB_DUAL_SEED_EDGE_THRESHOLD'] = '0.48'` — patch thành `'0.40'` + print marker `[ver14] E1: edge candidate threshold 0.48 → 0.40 (Phase K)`.
2. **Read-point** (predict script line 818/monolith 1415): `edge_candidate_threshold = float(os.environ.get(...))` → line 842: `cfg.threshold = edge_candidate_threshold` (chỉ set khi secondary_weights tồn tại — luôn true trong production).
3. **Tác dụng** (predict script line 717-723):
   ```python
   candidates = sorted([(probs[i,j], i, j) for i,j ... if probs[i,j] > cfg.threshold], reverse=True)
   ```
   Mọi cặp source→target có xác suất ∈ (0.40, 0.48] giờ vào candidate list → greedy assignment (caps `max_children/max_parents` vẫn hạn chế bão) → cạnh thêm vào graph.
4. **probs là xác suất SAU fusion** — đã qua: bidirectional harmonic (w 0.15) + secondary edge blend (w 0.15, low_margin_consensus) + SEF_TTA 0.75 + mix temperature 1.0. Population nhắm tới = cặp khó (di chuyển nhanh / dày đặc) mà fusion vẫn chỉ đạt 0.40-0.48.

### 3.2 Tương tác 3 lớp (phải hiểu trước khi chạy)

| Lớp | Tương tác | Hướng |
|---|---|---|
| **Leaf-prune 0.3** (v13.2 giữ) | Cắt node-leaf có **cạnh vào prob < 0.3** (post-hoc edges: safe-div/reparent/gap-close). Cạnh E1 có prob ≥ 0.40 > 0.3 → **KHÔNG bị prune** — leaf-prune KHÔNG chặn E1 | **Không đối kháng** (REVIEW §3.2 đã đính chính). Receipt leaf_pruned kỳ vọng GIỮ ~81 ± vài (population E1 không qua cơ chế này) |
| **Máy division** (safe-div + reparent, v11-exact) | Cạnh E1 thêm parent candidates → đề xuất division tăng → safe-div gate (diverge 0.5µm, sister 14µm, pdiv 0.85) lọc như thường | **Cân bằng**: forks có thể tăng nhẹ (141 → 145-165?). Gate R4 [100,200] đủ rộng. KHÔNG tắt gate nào (L13c) |
| **MIN_CANDIDATE_RETENTION 0.90** | Guard fallback nếu candidates quá ít — E1 chỉ THÊM candidates | Không kích hoạt |

### 3.3 Kỳ vọng & rủi ro

- **Kỳ vọng**: +0.001-0.005 adjEJ nếu population (0.40, 0.48] giàu TP (GT edge mà fusion chấm thấp). LB 0.947-0.952.
- **Rủi ro chính**: population giàu FP → precision rơi > recall tăng → LB ≤ 0.945. **Downside bị chặn**: banked v11 0.947 selectable; mất tối đa 0.7h GPU + 1 slot.
- **Probe đơn điểm** (không sweep được offline — cạnh sinh lúc inference trên GPU): 0.40 là bước đà từ 0.48. Nếu replica v14 vs v13.2 cho adjEJ Δ < 0 → không submit (cổng replica-gate điều kiện cần), quay về probe 0.44 (bước trung gian).

---

## §4. Build spec (6 file, pattern v13.2 nguyên văn)

| # | File | Nội dung then chốt |
|---|---|---|
| 1 | `ver-14/build-ver14-monolith.py` | **3 delta-patch (REVIEW đã chính xác hóa — xem §5.5)**: (A) block `[ver14]` set E1='0.40' chèn sau block [ver132] TRƯỚC guard · (B) thêm `'BIOHUB_DUAL_SEED_EDGE_THRESHOLD': 0.4` vào `_EXPECTED_NUMERIC` · (C) line ~1173 `'0.48'`→`'0.40'` — bắt buộc, nếu không block 1173 (chạy SAU) ghi đè về 0.48 im lặng (bug env-ordering kiểu REVIEW-2 v12) · py_compile + determinism (build ×2 cùng md5) |
| 2 | `ver-14/cell-monolith.py` | Base `ver-13-2/cell-monolith.py` (md5 9a0e872a) + patch → kỳ vọng ~5.645 dòng |
| 3 | `ver-14/make-ver14-ipynb.py` | Notebook 1 code cell == monolith BYTE-EXACT (verify như v132: json load + so sánh chuỗi) |
| 4 | `kaggle/api/ktool.py` | + `VER14_NOTEBOOK / VER14_DATASETS (=VER132) / VER14_SLUG "biohub-ver14"` + 3 nhánh `--ver 14` (push/watch/status/score) + detect "ver14" trong ref-parser |
| 5 | `kaggle/api/submit-v14.py` | Copy submit-v132 (đường kagglesdk create_code_submission — route ĐÃ CHỨNG MINH ref 56492596; bỏ route CLI file-submit 400) + ack mặc định `BIOHUB_DUAL_SEED_EDGE_THRESHOLD` |
| 6 | `kaggle/api/machinery-ledger.json` | + classification E1: `hypothesis-ackable` (chưa từng đứng một mình trên LB — receipt sao? giống GC3/leaf class) |

**Guard mới — block `[ver14]` + 2 anchor (REVIEW đĩnh chính §5.5):**
- **(A)** Chèn block `[ver14]` ngay sau block `[ver132]` (trước guard line ~217): marker print `[ver14] E1: edge candidate threshold 0.48 → 0.40 (Phase K)` + `os.environ['BIOHUB_DUAL_SEED_EDGE_THRESHOLD'] = '0.40'`.
- **(B)** `_EXPECTED_NUMERIC` thêm `'BIOHUB_DUAL_SEED_EDGE_THRESHOLD': 0.4` — hợp lệ vì (A) đã set TRƯỚC guard (cùng pattern 3 knob restore v132).
- **(C)** Line ~1173: `'0.48'` → `'0.40'` — KHÔNG được bỏ (env-ordering: block sau thắng; để 0.48 sẽ ghi đè lại).
- `_guard_report` thêm block `phase_k: {'e1_edge_threshold': 0.40, 'from': 0.48, 'label': 'v14_e1_edge040', 'source': 'V14-PLAN §1 E1 + V14-ARCHITECTURE §3'}`.

**Ràng buộc any-change**: mọi env khác ở lại giá trị v13.2 (audit sẽ FAIL nếu diff ngoài E1 — ledger classification L13d).

---

## §5. Cổng & receipt kỳ vọng (submit-v14 tự hủy nếu vi phạm)

| Cổng | Kỳ vọng | Cơ sở |
|---|---|---|
| CONFIG audit | R1 division-ON ✅✅ · 3 ACKED (GC3, leaf, **E1**) · 0 FAIL | ledger + ack-fix b5f131e |
| RECEIPT | safe_divisions_added Σ ∈ [40,160] (kỳ vọng ~85-100, có thể cao hơn v13.2 một chút do E1 thêm parent candidates) · reparent ~71 · leaf_pruned ~81 ± vài (GIỮ — population E1 không qua leaf-prune, xem §5.5-3) · tag `v132_restore_division_gc3_leaf_e1_edge040` | receipts v13.2 + §3.2 |
| CENSUS | forks ∈ [100,200] (kỳ vọng 141-165) · nodes 122,372 ±5% · **edges theo audit R5: banked 118,332 ±5% = [112,215, 124,248]** — E1 tăng edges hợp lệ tới đó; vượt = WARN "E1 mở quá rộng" | machinery-audit R5 enforcing |
| REPLICA (0 GPU, sau COMPLETE) | adjEJ v14 vs v13.2 (0.9012): Δ ≥ +0.0005 mới SUBMIT-ELIGIBLE · Δ < 0 → HOLD | L13c: cặp so hợp lệ (cùng máy BẬT) |

## §5.5 REVIEW #1 — guard-placement & env-ordering (đính chính sau khi verify code)

REVIEW đã verify 3 điểm trong code v13.2: (i) các knob có trong guard đều được set **trước** guard (block [ver132] line 195-205 < guard line 217-243); (ii) EDGE_THRESHOLD được set ở line 1173 — **sau guard**; (iii) leaf-prune (line 3956+) chỉ cắt node-leaf có cạnh vào prob < 0.3.

Hệ quả bắt buộc cho build spec:
1. **Không thể chỉ thêm E1 vào `_EXPECTED_NUMERIC`** (guard sẽ chạy lúc env chưa set → 'missing' → RuntimeError sai).
2. **Không thể bỏ patch line 1173** (block sau thắng → '0.48' ghi đè lại → E1 chết im lặng — đúng kiểu bug env-ordering REVIEW-2 v12 từng bắt).
3. **Leaf-prune không phải lưới an toàn cho E1** — cạnh E1 (≥0.40) vượt ngưỡng prune 0.3. Rủi ro FP cạnh E1 đi thẳng vào output (chỉ còn caps max_children/max_parents + census gates). Đã cập nhật §3.2, §4, §5.

## §6. Kịch bản kết quả → quyết định

| LB v14 | Diễn giải | Hành động |
|---|---|---|
| ≥ 0.948 | E1 giàu TP trên public — **banked mới** | v15 = E1 tinh chỉnh 0.36 (probe tiếp cùng trục) hoặc P2 tự đo GT-replica |
| 0.946-0.947 | E1 trung tính trên public (FP≈TP cancel) | Giữ banked; v15 đổi trục (P2/P4 — tự đo replica trước) |
| ≤ 0.945 | E1 hại (FP tràn) | Revert v14; nếu v13.2 ≥ 0.947 thì banked v13.2 config; probe 0.44 chỉ khi quota/GPU dư |

## §7. Ngân sách & lịch

- GPU: 0.7h (run) — sổ 17.2/30h → còn ~12.8h (refresh 26/9). Đủ cho v14 + 2 lần tinh chỉnh + buffer.
- Quota: 4/5 còn hôm nay (23/9); ngày mai 5 fresh.
- Trình tự khi user duyệt: build (0 GPU, ~30') → audit + selftest → push `--ver 14` → watch (~46') → replica-gate → submit-v14 → poll.
- **Rào cản duy nhất hiện tại: điểm v13.2 còn PENDING (6h20'+, queue Kaggle chậm — kernel COMPLETE, không lỗi). Chờ điểm trước khi push v14** (điều kiện tiên quyết §0).
