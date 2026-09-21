# andnyu/biohub-density-adaptive-0-948-reproduction — ANALYSIS (23/9)

- Public 21/9 (ANDREW YU, 15h trước lúc đọc, 32 views), T4×2, **21m47s**, điểm thật **0.945 V1**
  (title claim 0.948 reproduction — KHÔNG đạt).
- Cùng họ harmonic_v3_division_wide; config ≈ ver-10 ta (tight55, SAFE_DIV 9/14/τ0.6/2.25,
  GAP2=1, GAP_DENSITY_ADAPTIVE=1, DC 0.25/0.25, DC_TTA=1, bonus 1.0, SEF_TTA w0.75, bidir 0.15
  harmonic, ILP 0/2/1.2, rescue identical) — nhưng THIẾU reparent Phase D + mn_p85_div05 + p_div floor.
- **DivNet 3D mitosis veto = DEAD CODE**: `BIOHUB_OUTPUT_DIVISION_GEOMETRY_FILTER` không set
  (mặc định '0') → `divnet_score_division()` 1 call-site trong block bị gate OFF — model load
  nhưng không bao giờ gọi (lần 2, trùng haideptry receipt batch-A). KHÔNG port veto.
- **Density-group overrides** (low 7.25/11/3/0.5 · mid 6.5/9/6/0 · high 5.5/10/1/0 theo
  node/frame <120/<400) = bản giản lược của haideptry — reproduction này cho data point âm
  (0.945 < 0.947). Giữ backlog A/B đơn-knob 05b6→7.25, không default-on.
- **Đáng giá nhất: `BIOHUB_VALIDATOR_ENABLE='0'`** ("Fast Submission Mode: Disable 90-minute
  offline training validation sweep") — ver-11/v12 ta validator mặc định ON nhưng PP_CANDIDATES={}
  → no-op thuần túy ~90' GPU/run. ĐÃ PORT vào v12 (REVIEW-3, 23/9): diff monolith 1 env + 1 print,
  submission byte-identical, GPU/run 2.2h → ~0.5-0.75h.
- Dual-GPU sharding ta đã có; batch 8 + CUDNN_CONV_WSCAP_DBG=1024 không chắc byte-identical → bỏ.
- Kết luận: không có kỹ thuật scoring mới thắng v12; giá trị = waste-elimination + receipt runtime.
