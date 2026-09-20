# ayodeji-bidir35 — "v928 v909 bidir35 r1"

**Nguồn:** /home/z/v11-recovery/research/ayodeji-bidir35/biohub-v928-v909-bidir35-r1.ipynb (12 cell; diff với det96625 chỉ đúng 3 nhóm: DET/BIDIR/CANDIDATE_ID)
**Nhãn: THEO DÕI — receipt trục bidir 0.30→0.35, không có điểm candidate**

## Kiến trúc 1 câu
Cùng V33 one-direction harness: V928 = V909 core (public 0.915) với duy nhất BIDIRECTIONAL_EDGE_WEIGHT 0.30 → **0.35** (DET giữ nguyên 0.9671875); mọi cell khác byte-giống det96625 (đã diff cell-by-cell xác nhận).

## Delta so stack mình
- Bidir (reverse-time harmonic) **0.35** vs mình **0.15** — gia đình này chạy base 0.30 và probe lên 0.35, tức trục reverse-time weight của họ ở vùng gấp đôi mình; family V909 còn có SECONDARY_EDGE_WEIGHT 0.15 + low_margin_consensus 0.35 + secondary detection blend 0.80 (blend phụ mạnh hơn hẳn cấu hình mình)
- Rest giống V909 core (xem card det96625): SAFE_DIV_DIVERGE 3.1875, DC 0.25, HOCT off, short rescue ON, TTA w0.75

## Giá trị cho v12
- Bidir axis: có bằng chứng người khác thao túng vùng 0.30-0.35 trên cùng engine harmonic; MÌNH đã A/B chọn 0.15 trên base mình (0.947 > 0.915 hẳn) → giữ 0.15, nhưng nếu v12 mở gate thử bidir 0.20-0.25 thì đây là dữ liệu "vùng đó không nổ" (0.915-family sống được với 0.30-0.35).
- Không port gì; không receipt điểm candidate (status unverified_quality), parent ref 56182642 = 0.915.

## Receipts điểm
- Parent V909 public 0.915; candidate V928 KHÔNG có điểm. Diff 2 notebook = A/B đơn biến thực thụ (chỉ DET + bidir + ID) → Receipts cấu trúc sạch nhất batch C.
