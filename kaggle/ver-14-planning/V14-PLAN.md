# V14-PLAN.md — Đẩy adjEJ vượt trần 0.947 (Phase K)

> Ngày draft: 2026-09-23 (sáng, khi v13.2 đang chạy kernel). Cập nhật 18:30 UTC sau khi submit v13.2.
> **Kiến trúc chi tiết: `V14-ARCHITECTURE.md` (cùng thư mục) — đã REVIEW #1 (§5.5 guard-placement/env-ordering)
> + REVIEW #2 (§5.6 receipt-integrity: patch D + số học R5); plan này giữ vai trò menu lever + GO/NO-GO.**
> Trạng thái: **DRAFT — chờ (1) điểm LB v13.2 (ref 56492596 — SUBMITTED 12:06 UTC 23/9,
> PENDING 6h+ do queue metric Kaggle chậm), (2) phê duyệt user** cho GPU spend (E1 là
> lever KHÔNG replay offline được — override luật replay-proof cần lệnh trực tiếp).

## 0. Điều kiện tiên quyết (không thương lượng)

1. **v13.2 LB ∈ [0.946, 0.948]** — xác nhận carrier division-restored + GC3/leaf.
   Nếu v13.2 < 0.945 → KHÔNG xây v14 trên base này; quay lại v13.3 tách lever
   (GC3 hoặc leaf đứng một mình, mỗi biến 1 submission).
2. **machinery-audit v14 = 0 FAIL** + mọi knob mới phân loại `hypothesis-ackable`
   phải được ack tường minh trong submit script.
3. Máy division giữ nguyên v11-exact như v13.2 (L13c: không đụng).

## 1. Menu lever adjEJ (thứ tự ưu tiên)

| # | Lever | Cơ chế | Bằng chứng | Độ tin | GPU |
|---|---|---|---|---|---|
| **E1** | `BIOHUB_DUAL_SEED_EDGE_THRESHOLD` 0.48→**0.40** | hạ ngưỡng cạnh ứng viên → ILP/fusion thấy thêm cạnh TP (giảm FN edge = tăng recall adjEJ) | trục adjEJ là trục chuyển hóa duy nhất đã chứng minh (v12.1: adjEJ −0.0012 → LB −0.001); KHÔNG có offline replay (cạnh sinh lúc inference) | trung-khả (khám phá) | 0.7h |
| P2 | `MOTION_RELINK_VELOCITY_WEIGHT` 0.5→0.25 | sweep amanatar +0.0014 adj | **L14d: lever ngoài transfer 0/3** — chưa tự đo trên GT-replica | thấp | 0.7h |
| P4 | divwide 11/16/12 + dcsd 0.15 | recall division (không tốn adj) | sweep census-only | thấp | 0.7h |

**Khuyến nghị: v14 = v13.2 + E1 đơn lever** (attribution sạch — mọi kết quả
đọc được ngay: cạnh tăng giúp hay hại). P2/P4 chỉ sau khi có GT-replica tự đo
(replica-gate --pull khôi phục test-gt 84 file — đã có tool).

## 2. Build spec v14 (4 delta-patch — chi tiết V14-ARCHITECTURE §4 + §5.5/§5.6)

- Base: `kaggle/ver-13-2/cell-monolith.py` (md5 9a0e872a…).
- **(A)** Block `[ver14]` (marker print + set E1='0.40') chèn sau block [ver132]
  TRƯỚC guard — bắt buộc set-trước-guard (REVIEW §5.5-1).
- **(B)** `_EXPECTED_NUMERIC` thêm `'BIOHUB_DUAL_SEED_EDGE_THRESHOLD': 0.4`.
- **(C)** Line ~1173 `'0.48'` → `'0.40'` — bắt buộc đổi (env-ordering: block sau
  thắng; bỏ qua = E1 chết im lặng — REVIEW #1 §5.5-2 + parser-proof REVIEW #2 §5.6-2).
- **(D)** Line ~5637 `'edge_candidate_threshold': 0.48` → đọc env
  `float(os.environ.get('BIOHUB_DUAL_SEED_EDGE_THRESHOLD', '0.48'))` — receipt
  `_guard_report['configuration']` phải phản chiếu giá trị chạy thật (REVIEW #2 §5.6-1).
- `_guard_report` phase_k + EXPERIMENT_TAG `v132_restore_division_gc3_leaf_e1_edge040`.
- Notebook: make-ver14-ipynb.py — cell == monolith byte-exact (L1/L2).
- ktool: VER14_NOTEBOOK/SLUG `biohub-ver14`, datasets = VER132_DATASETS.
- submit-v14.py: kagglesdk **create_code_submission** (route ĐÃ CHỨNG MINH — ref
  56492596; route CLI file-submit bị 400 từ chối — code competition) + ack mặc định
  `BIOHUB_DUAL_SEED_EDGE_THRESHOLD`.

## 3. Cổng receipt kỳ vọng v14 (điều chỉnh từ ledger — chi tiết ARCHITECTURE §5)

- Máy division: GIỮ NGUYÊN v13.2 — safe_divisions_added Σ ∈ [40,160] (kỳ vọng ~85-100)
  · reparent ~71 · forks ∈ [100,200] (kỳ vọng 141-165).
- **Cạnh**: edges sẽ TĂNG theo thiết kế (đó là toàn bộ điểm của E1). Audit R5 phán
  theo banked 118,332 ±5% = [112,416, 124,248] (REVIEW #2 đính chính số học);
  nếu edges vượt band → R5 FAIL (HARD, không ack) → submit tự hủy — xem
  FP-risk trước khi nghĩ override.
- Leaf-prune KHÔNG chặn cạnh E1 (≥0.40 > ngưỡng prune 0.3 — REVIEW §5.5-3):
  receipt leaf_pruned kỳ vọng GIỮ ~81 ± vài.
- Tag: `v132_restore_division_gc3_leaf_e1_edge040`.

## 4. Rủi ro & giới hạn

- **Rủi ro chính**: cạnh FP tràn vào graph → precision giảm > recall tăng →
  adjEJ rơi. Mitigation: đơn lever; banked 0.947 selectable nên downside bị
  chặn (giống v13.2 — chỉ mất 0.7h GPU + 1 slot).
- **Instrument**: replica chỉ đo được adjEJ delta giữa 2 build CÙNG máy BẬT —
  v14 vs v13.2 là cặp so sánh HỢP LỆ (L13c). Chạy replica-gate trên output v14
  TRƯỚC submit nếu thời gian cho phép (verdict = điều kiện cần, không đủ).
- E1 = 0.40 là mũi probe đơn điểm (không sweep được offline); nếu adjEJ replica
  v14 < v13.2 → quay lại 0.44 làm bước trung gian.
- **Lưới an toàn thật của E1** (REVIEW #1 đĩnh chính): chỉ caps max_children/max_parents
  + census gates (R4 forks [100,200] + R5 edges band) — leaf-prune và
  MIN_CANDIDATE_RETENTION đều không chặn E1.

## 5. Kịch bản sau v14

- v14 ≥ 0.948 → banked mới; v15 = E1 tinh chỉnh (0.36/0.44) hoặc P2 tự đo.
- v14 = 0.946-0.947 → E1 trung tính trên public; v15 đổi trục (P2/P4 với
  GT-replica tự đo trước).
- v14 < 0.945 → E1 hại (FP tràn) → revert về v13.2 config làm banked mới nếu
  nó ≥ 0.947.
