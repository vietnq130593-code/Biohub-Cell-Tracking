# ANALYSIS — thtennant/biohub-frontier947-readmit-v1 (re-admission detection bị vứt)

**Task ID:** 5-b · **Ngày:** 20/9 · **Loại:** SUBMISSION KERNEL — biến thể readmit của family frontier947 (xem ANALYSIS thtennant-gapfill để biết cấu trúc family + base env).
**Nguồn:** /home/z/v11-recovery/research/thtennant-readmit/biohub-frontier947-readmit-v1.ipynb + output pull 20/9.

## 1. Biến thí nghiệm (cô lập bằng diff)

= gapfill-v1 + 2 env (`BIOHUB_READMIT_RADIUS_UM=4`, `BIOHUB_READMIT_MIN_SCORE=0.965`) + hàm `readmit_discarded_detections()` (~54 dòng, cell5) + call-site sau motion-relink đầu tiên. Còn lại byte-identical gapfill-v1 (đã verify md5 từng cell).

## 2. Cơ chế — "rescue" của họ khác rescue của mình

- Pool: lại dùng `load_low_detections` (peak ≥0.5, cách node hiện có >2 µm — tức **peak mạnh chưa từng được admit**).
- **Anchor:** node tại t **không có cạnh ra** (track end) → anchor tại t+1; node tại t **không có cạnh vào** (track start) → anchor tại t−1. (Cạnh lấy từ lần motion-relink đầu.)
- Điều kiện re-admit: peak cách anchor ≤ **4 µm** VÀ score ≥ **0.965** (= đúng DET_THRESHOLD — nghĩa là những detection ĐỦ SỨC nhưng bị pipeline vứt: ILP disappearance-weight 2 + edge-filter/prune).
- Sau khi thêm node (flag `readmitted`), **chạy lại `motion_relink_edges` trên node set mở rộng** — node mới được nối hoặc để isolated rồi bị prune (non-fatal toàn bộ).

Khác "rescue" của mình (short-track-rescue giữ component ngắn có edge_prob cao; cytokinesis-rescue của alfonso hồi fork): readmit hồi **chính detection node** quanh điểm gãy track — tấn công `edges_lost_to_detection` (79/stem validator) + fragmentation (133), không đụng division.

## 3. Receipt chạy thật (hidden test)

| phim | readmitted | gapfill (sau đó) | FINAL node/edge |
|---|---|---|---|
| 44b6_0113de3b | 85 | +3/+4 | 25.728 / 24.993 |
| 44b6_0b24845f | 317 | +92/+135 | 21.452 / 20.184 |
| 6bba_05b6850b | 63 | +3/+4 | 6.257 / 6.062 |
| 6bba_05db0fb1 | 366 | +32/+45 | 70.809 / 68.799 |
| **Tổng** | **831** | +130/+188 | **124.246 / 120.038** |

- Diff submission vs gapfill-v1 (cùng base, chỉ khác readmit): **+1.180 node / −166 node, +3.100 cạnh / −2.098 cạnh ⇒ ròng +1.014 node, +1.002 cạnh** — quy mô ~6× gapfill.
- Readmit ăn phần pool của gapfill (peak ≥0.965 nằm trong pool ≥0.5): gapfill tụt 167→130 node khi readmit bật — 2 cơ chế cộng dồn không nhân đôi.
- **Mỏ neo đo được:** 05db0fb1 có GT (lượt-5): FINAL readmit 70.809 node vs GT 70.300 (+509 spurious) và 68.799 cạnh vs GT 68.207 (+592) — node recall gần chạm trần phim dày nhất hidden; đây là kênh đối chiếu offline trực tiếp khi port.

## 4. Rủi ro & lưu ý port

- Node precision: thêm ~1k node/spurious thêm — validator đã ~183k spurious; node-multiplier có thể đã bão hòa nhưng phải đo.
- Anchor tính từ cạnh của motion-relink ĐẦU (trước gap-close) — đúng vị trí ngữ nghĩa "đang hở"; khi port vào chuỗi mình (có HOCT/reparent/retention-guard) phải đặt cùng vị trí tương đối (sau relink đầu, trước gap-close/safe-div).
- Min-score = DET_THRESHOLD ⇒ đụng độ tự nhiên với dual-seed fusion node set (mình dùng fusion 2 seed; peak bị vứt của mình cần lấy từ phía nào? — đọc trực tiếp lowdet dump của hai seed rồi intersect/union theo đúng luật fusion của mình).

## 5. Verdict cho v12

**PORT (A/B validator + LB, ưu tiên sau gapfill hoặc ghép chung):** quy mô hiệu ứng lớn nhất batch B (+1k node/+1k cạnh trên hidden), cơ chế sạch 54 dòng, tái dùng đúng infra dump lowdet của gapfill, tấn công trục edge (trục chính theo alfonso) qua node recall. Kỳ vọng đo được ngay trên validator (missed_gt_nodes 63, edges_lost_to_detection 79) + mỏ neo 05db.
