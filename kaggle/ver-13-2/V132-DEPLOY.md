# V132-DEPLOY.md — Runbook triển khai ver-13.2 (RESTORE máy division)

> **Tình trạng: BUILD-READY, CHƯA PUSH** — chờ lệnh trực tiếp user (luật bất biến:
> GPU chỉ tiêu khi cổng local pass + user duyệt; submit chỉ theo lệnh trực tiếp).
> Ngày build: 2026-09-23. Trọng tài lỗi: `kaggle/ERRORS-LEDGER.md` (L13).

## 0. Vì sao có v13.2

v13.1 (LB 0.911, ref 56473159) tắt máy division theo autopsy sai. LB phán 2 lần
độc lập: **forks=0 → 0.911** (variant A 56373784 + v13.1) vs **forks 144-188 →
0.946-0.947**. v13.2 = v13.1 + 3 dòng env phục hồi v11-exact division:
`OUTPUT_SAFE_DIVISIONS=1` · `REPARENT_ENABLE=1` · `REPARENT_EDGE_PROB=0.25`.

Giữ nguyên từ v13.1: GC3 `GAP_CLOSE_UM=3.0` · leaf `0.3` · vel `0.5` ·
diverge `0.5` · orphan `0` · knockout READMIT/GAPFILL/LOWDET (inert).

## 1. Artifact đã build (0 GPU)

| File | Verify |
|---|---|
| `kaggle/ver-13-2/cell-monolith-v131-base.py` | md5 `c21e82f2…` == kernel pull (byte-exact) |
| `kaggle/ver-13-2/build-ver132-monolith.py` | 8 patch deterministic; build ×2 cùng md5 |
| `kaggle/ver-13-2/cell-monolith.py` | md5 `9a0e872a…` · 5.643 dòng · py_compile PASS |
| `download/ver132-cell-tracking.ipynb` | 365 KB · cell == monolith BYTE-EXACT |
| `kaggle/api/submit-v132.py` | gate cứng cơ học (audit exit-code tuyệt đối) |

**Audit config (machinery-audit.py)**: R1 division-ON ✅✅ · 0 FAIL ·
2 WARN hypothesis (GC3, leaf) — ack lúc submit:
`--ack BIOHUB_GAP_CLOSE_UM,BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB`.

## 2. GPU WASTE CHECK (§4 GPU-WASTE-PREVENTION)

- L1 lab≠prod: kernel production, competition source ✓ (ktool push --ver 132)
- L2 smoke-test: py_compile + determinism + audit-config PASS ✓; kernel guard
  `_EXPECTED_TEXT` giờ khóa cứng OUTPUT_SAFE_DIVISIONS='1' + REPARENT_ENABLE='1'
  (crash nếu drift — in-kernel enforcement L13c)
- L8 GPU-CPU: toàn bộ logic thay đổi là 3 dòng env đã có bằng chứng LB từ v11 —
  không cần thí nghiệm mới. Replica local KHÔNG cần (L13b: chỉ đo adjEJ giữa
  build cùng máy BẬT; ở đây mục tiêu là trở về đúng vùng 144-188 forks).
- Kỳ vọng GPU: **~0.7h** (giống v13.1 46'). Sổ: 16.53h/30h → còn 13.47h (refresh 26/9).

## 3. Chuỗi lệnh khi user duyệt

```bash
cd kaggle/api
python3 ktool.py push --ver 132          # Save & Run All, T4×2, Internet OFF
python3 ktool.py watch --ver 132          # poll ~46'
# kernel COMPLETE → đừng vội (L3 persist ≥20'):
python3 submit-v132.py \
  --ack BIOHUB_GAP_CLOSE_UM,BIOHUB_LEAF_PRUNE_MIN_EDGE_PROB \
  --message "ver-13.2 restore-division (L13c: v11-exact div + GC3 + leaf) — fork target 144-188"
python3 ktool.py score                    # poll điểm
```

## 4. Kỳ vọng & phán quyết

- **Cổng trong submit-v132 (RECEIPT)**: safe_divisions_added Σ ∈ [40,160]
  (kỳ vọng ~82 như v11) · reparent ~77 · forks ∈ [100,200] (kỳ vọng ~144 ± leaf-prune
  ảnh hưởng nhẹ) — FAIL bất kỳ = không nộp, quay về audit.
- Kỳ vọng LB: **0.946-0.947** (trở lại vùng banked; GC3+leaf là ±0.001-class
  theo replica/estimates — không kỳ vọng vượt 0.947).
- Nếu LB < 0.945: GC3/leaf có tương tác xấu với division-restored → v13.3 tách
  từng lever (mỗi biến 1 submission — chỉ khi user duyệt).
- Banked v11 = 0.947 KHÔNG đổi dù kết quả gì (fail-safe đã có từ v13.1).
