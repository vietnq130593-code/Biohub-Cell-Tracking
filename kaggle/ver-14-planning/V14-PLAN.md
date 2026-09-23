# V14-PLAN.md — Đẩy adjEJ vượt trần 0.947 (Phase K)

> Ngày draft: 2026-09-23 (khi v13.2 đang chạy kernel biohub-ver132 v1).
> Trạng thái: **DRAFT — chờ (1) điểm LB v13.2 xác nhận carrier, (2) phê duyệt user**
> cho GPU spend (E1 là lever KHÔNG replay offline được — override luật replay-proof
> cần lệnh trực tiếp).

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

## 2. Build spec v14 (1 patch, pattern giống ver-13-2)

- Base: `kaggle/ver-13-2/cell-monolith.py` (md5 9a0e872a…).
- Patch: env-block `BIOHUB_DUAL_SEED_EDGE_THRESHOLD = '0.48'` → `'0.40'`
  (monolith line ~1163) + thêm vào `_EXPECTED_NUMERIC` guard (crash nếu drift)
  + print `[ver14]` marker + `_guard_report` phase_k.
- Notebook: make-ver14-ipynb.py — cell == monolith byte-exact (L1/L2).
- ktool: VER14_NOTEBOOK/SLUG `biohub-ver14`, datasets = VER132_DATASETS.
- submit-v14.py: copy submit-v132 + ack mặc định `BIOHUB_DUAL_SEED_EDGE_THRESHOLD`.

## 3. Cổng receipt kỳ vọng v14 (điều chỉnh từ ledger)

- Máy division: GIỮ NGUYÊN v13.2 — safe_divisions_added Σ ∈ [40,160] (kỳ vọng ~82)
  · reparent ~77 · forks ∈ [100,200].
- **Cạnh**: edges sẽ TĂNG theo thiết kế (đó là toàn bộ điểm của E1). R5 ±5%
  (tối đa ~124.2k) đủ rộng cho +1-3% cạnh; nếu edges vượt +5% → cảnh báo
  "E1 mở quá rộng" → xem FP-risk trước khi submit.
- Tag: `v132_restore_division_gc3_leaf_e1_edge040`.

## 4. Rủi ro & giới hạn

- **Rủi ro chính**: cạnh FP tràn vào graph → precision giảm > recall tăng →
  adjEJ rơi. Mitigation: đơn lever; banked 0.947 selectable nên downside bị
  chặn (giống v13.2 — chỉ mất 0.7h GPU + 1 slot).
- **Instrument**: replica chỉ đo được adjEJ delta giữa 2 build CÙNG máy BẬT —
  v14 vs v13.2 là cặp so sánh HỢP LỆ (L13c). Chạy replica-gate trên output v14
  TRƯỚC submit nếu thời gian cho phép (verdict = điều kiện cần, không đủ).
- E1 = 0.40 là mũi probe đơn điểm (không sweep được offline); nếuadjEJ replica
  v14 < v13.2 → quay lại 0.44 làm bước trung gian.

## 5. Kịch bản sau v14

- v14 ≥ 0.948 → banked mới; v15 = E1 tinh chỉnh (0.36/0.44) hoặc P2 tự đo.
- v14 = 0.946-0.947 → E1 trung tính trên public; v15 đổi trục (P2/P4 với
  GT-replica tự đo trước).
- v14 < 0.945 → E1 hại (FP tràn) → revert về v13.2 config làm banked mới nếu
  nó ≥ 0.947.
