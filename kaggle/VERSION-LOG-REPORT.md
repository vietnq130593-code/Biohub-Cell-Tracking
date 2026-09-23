# CROSS-VERSION LOG COMPARISON — chất lượng từ logs

> Sinh bởi `version-log-compare.py`. Nguồn: run_stats.csv (receipts) + submission.csv (census) + Kaggle submissions (LB).


## 1. Bảng chính — LB × census × máy division

| Bản | LB | nodes | edges | **forks** | safe_div | reparent | div_rej | divnet | HOCT | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| v11 | 0.947 | 122,787 | 118,332 | **144** | 82 | 77 | 2,812 | 391 | 144 | 🟢 vùng ổn định (luật fork) |
| v12.1 | 0.946 | 122,808 | 118,393 | **184** | 123 | 77 | 365 | 769 | 184 | 🟢 vùng ổn định (luật fork) |
| v13.1 | 0.911 | 122,363 | 117,721 | **0** | 0 | 0 | 0 | 0 | 0 | 🔴 MÁY DIVISION CHẾT (L13) |
| v8-v3fast | — | 122,812 | 118,543 | **188** | 127 | 80 | 4,147 | 152 | 0 | 🟢 vùng ổn định (luật fork) |
| v8-v1 | — | 122,792 | 118,538 | **188** | 124 | 78 | 4,172 | 149 | 0 | 🟢 vùng ổn định (luật fork) |

## 2. Luật fork (định luật thực nghiệm từ LB)

| forks | LB | mẫu |
|---|---|---|
| 188 | 0.947 | v10 |
| 144 | 0.947 | v11 (banked) |
| 184 | 0.946 | v12.1 |
| **0** | **0.911** | **variant A + v13.1 (2 mẫu độc lập)** |

→ Đọc receipt `safe_divisions_added` + census `forks` là **đoán được LB trước khi nộp**.

## 3. Fingerprint đầy đủ (receipts)

| receipt | v11 | v12.1 | v13.1 | v8-v3fast | v8-v1 |
|---|---|---|---|---|---|
| safe_divisions_added | 82 | 123 | 0 | 127 | 124 |
| reparent_added | 77 | 77 | 0 | 80 | 78 |
| safe_division_divergence_rejected | 2,812 | 365 | 0 | 4,147 | 4,172 |
| divnet_proposals_scored | 391 | 769 | 0 | 152 | 149 |
| hoct_veto_divisions_before | 144 | 184 | 0 | 0 | 0 |
| hoct_veto_divisions_after | 144 | 184 | 0 | 0 | 0 |
| gap_added_nodes | 620 | 620 | 455 | 620 | 610 |
| gap2_added_nodes | 286 | 286 | 294 | 286 | 290 |
| leaf_prune_nodes | 0 | 0 | 74 | 0 | 0 |
| readmitted_nodes | 0 | 0 | 0 | 0 | 0 |
| gapfill_added_nodes | 0 | 0 | 0 | 0 | 0 |
| experiment_tag | secondary_deepcenter_tta_0947_reparent_hoct_v11_mn_p85_div05 | secondary_deepcenter_tta_0947_reparent_hoct_v12_portfolio_d2 | secondary_deepcenter_tta_0947_reparent_hoct_v131_sr0gc3_nodi | secondary_deepcenter_tta_0947_reparent_v8_3fast | secondary_deepcenter_tta_0947_reparent_v8 |

## 4. Tín hiệu log nào nói gì (hướng dẫn đọc)


| Họ log | File | Chất lượng đo được | Độ tin cậy |
|---|---|---|---|
| Submission log | Kaggle API `submissions` | Điểm LB cuối cùng — chân lý | ★★★ tuyệt đối (nhưng đã muộn) |
| Run receipts | `run_stats.csv` per kernel | Máy nào FIRED bao nhiêu lần → phát hiện máy chết (v13.1: 5 tầng = 0) | ★★★ (trước submit!) |
| Output census | `submission.csv` | forks/nodes/edges/DAG → đoán LB qua luật fork | ★★☆ (vùng ổn định, không phải điểm chính xác) |
| Kernel stdout log | `biohub-*.log` | config dump + guard + timeline run | ★★★ (audit độc lập — md5, env) |
| Replica-gate log | GT 84-file local | delta adjEJ giữa build CÙNG máy BẬT | ★☆☆ adjEJ-only, mù divJ/fork (L13b) |
| GPU sổ | quota | chi phí/tháng — tránh L2/L8 | ★★★ |

**Kết luận cho câu hỏi "logs có giúp so sánh chất lượng không?": CÓ.**
Nhận diện version tốt/xấu mà không tốn submission: (1) receipts cho biết máy sống hay chết;
(2) census fork → khoảng LB; (3) LB lịch sử cho version đã nộp. Công cụ này gộp cả 3.

