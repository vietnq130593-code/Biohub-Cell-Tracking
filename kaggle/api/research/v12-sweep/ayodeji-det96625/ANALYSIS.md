# ayodeji-det96625 — "v929 v909 det96625 r1"

**Nguồn:** /home/z/v11-recovery/research/ayodeji-det96625/biohub-v929-v909-det96625-r1.ipynb (12 cell; V33 one-direction candidate harness)
**Nhãn: THEO DÕI — receipt trục DET micro-step, không có điểm candidate**

## Kiến trúc 1 câu
Chuẩn xác "exact scored V909 core + one named direction": V929 = family V909 (ayodejiibrahimlateef, preset v900_flex_record_next5_v1, public 0.915) với duy nhất DET_THRESHOLD 0.9671875 → **0.96625**; kèm harness V33 fail-closed (parent notebook SHA c635…, parent submission SHA 9f1fc6…, submission_ref 56182642, config guard + audit cell).

## V909 core (base của họ, so stack mình)
- DET **0.9671875** (mình 0.965); bidir(reverse-time) **0.30** (mình 0.15); SAFE_DIV_DIVERGE **3.1875** (mình 2.25); DC SAFE_DIV **0.25** (mình 0.20); HOCT_VETO=0; short-track rescue ON (giống howonkang/newwang12 → lớp này phổ biến trong family 0.915+)
- Secondary blend rất mạnh: SECONDARY_DETECTION_WEIGHT 0.80, SECONDARY_EDGE_WEIGHT 0.15, LINK_MODE low_margin_consensus (LOW_MARGIN_MAX 0.35), DUAL_SEED_EDGE_THRESHOLD 0.48, DC d4 TTA + SECONDARY_EDGE_FEATURE_TTA w0.75 (khớp mình)
- Lineage minh bạch: harmonic fusion từ **flexonafft/biohub-harmonic-fusion@348830051**; "leaderboard_feedback_used_for_configuration": True

## Giá trị cho v12
- Trục DET: họ đang sweep micro-step quanh 0.966-0.9675 (V929 = 0.96625 đi XUỐNG từ 0.9671875). Kết hợp mình 0.965 → DET plateau nằm đâu đó 0.965-0.9675; không có receipt điểm candidate (status "candidate_unverified_quality") → không thể quy đổi.
- Family base 0.915 << mình 0.947 → khác basin, giá trị chuyển nhược; chỉ lấy thông tin "trục đang được người khác khai thác quanh đâu".
- Pattern V33 (parent SHA + output SHA + axis + status + fail-closed audit) = protocol A/B sạch, mình đã có tương đương (receipts v2int) — không cần port.

## Receipts điểm
- Parent V909 public **0.915** (comment cell 8: "reproduces 0.915"); submission_ref 56182642. Candidate V929: KHÔNG có điểm (unverified).
