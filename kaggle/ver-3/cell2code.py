# ver 3 · cell 2 — SIÊU THAM SỐ (mọi núm tune nằm ở đây)
# Dán đè Cell 2 của notebook Kaggle.
# ============================================================
# Nguyên tắc ver 3 (rút từ discussion #740573 — đo trên 73 file nhãn TRAIN
# THẬT: 36 phân bào có nhãn, 25.661 cạnh continuation, 572 track):
#   1. KHOẢNG CÁCH MẸ→CON KHÔNG PHẢI TÍN HIỆU PHÂN BÀO: IQR bước phân bào
#      (3,3–6,2µm) nằm gần trọn trong vùng bước thường (p99 = 6,9). Gate
#      ≥5µm thu 722 bước thường / 30 bước phân bào = 24:1 base rate.
#      → khoảng cách chỉ còn là CỬA SỔ TÌM KIẾM; tín hiệu thật là:
#      sister separation + bảo toàn độ sáng + ĐỘNG HỌC + APPEARANCE.
#   2. SISTER SEPARATION là tín hiệu hình học mạnh nhất (median 8,85,
#      IQR 7,2–10,2, p99 13,9, MAX 14,65µm) → cổng 12 bỏ lỡ ~10% cặp.
#   3. MẸ SÁNG LÊN TRƯỚC KHI CHIA (peak intensity AUC 0,73 với tế bào
#      thường; hengck23: đường sáng mảnh anaphase xuất hiện VÀI KHUNG
#      TRƯỚC khung tách) → dùng làm (a) ưu tiên ứng viên, (b) chặn
#      merge-split qua "ổn định khối lượng mẹ": blob gộp 2 tế bào ≈ 2×
#      khối lượng đơn, còn mẹ thật chỉ sáng lên nhẹ (1,1–1,5×).
#   4. Mọi cạnh GT nối đúng 1 khung (25.661/25.661) → nội suy node tại
#      khung mất vẫn là bắt buộc (giữ từ ver 2).
#   5. GT chỉ gắn nhãn theo segment (median 35 khung/track) → phát hiện
#      phân bào nơi GT không nhãn vẫn tính FP → precision > recall.
# ============================================================

TEST_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/test'

# Thang vật lý (Z, Y, X) — µm/voxel, theo đề bài
SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)

# --- Tầng 1 · DETECTION (giữ nguyên ver 2) ---
DS_Z, DS_Y, DS_X = 2, 4, 4       # downsample bất đối xứng: z giữ kỹ hơn
SMOOTH_SIZE = 3                   # uniform_filter, trong không gian downsample
PERCENTILE = 90.0                 # bắt thêm nhân mờ (recall > precision)
MIN_NVOXELS = 4                   # bỏ component li ti (nhiễu)
MAX_NVOXELS = 3000                # blob gộp vẫn nhận, tách ở tầng 1b
CONN26 = True                     # liên kết 26-ô: chống tách nhân giữa các lát z

# --- Tầng 1b · TÁCH BLOB GỘP (giữ nguyên ver 2) ---
SPLIT_MIN_NVOXELS = 90            # component ds lớn hơn mới xét tách
PEAK_SIZE = (3, 5, 5)             # maximum_filter tìm đỉnh cục bộ (z,y,x ds)
MIN_PEAK_DIST_DS = 4.0            # 2 đỉnh cách ≥ 4 voxel ds
PEAK_MIN_BRIGHT = 1.15            # đỉnh sáng hơn ngưỡng ít nhất 15%

# --- Tầng 2 · LINKING (giữ nguyên ver 2) ---
BASE_GATE_UM = 9.0
GATE_MEDIAN_MULT = 2.5
GATE_MIN_UM, GATE_MAX_UM = 5.0, 14.0
VEL_SMOOTH = 0.5                  # vận tốc EMA: v ← 0.5·mới + 0.5·cũ
BRIGHT_WEIGHT = 0.0               # phạt chênh độ sáng trong cost (tắt)

# --- Frame-skip + nội suy (giữ nguyên ver 2) ---
ALLOW_FRAME_SKIP = True
SKIP_GATE_UM = 12.0
MAX_SKIP_FRAMES = 2
INTERPOLATE_MISSED_FRAMES = True  # GT 100% cạnh liền khung → nội suy bắt buộc
TIME_LIMIT_HOURS = 11.0

# --- Tầng 3 · PHÂN BÀO THEO PROFILE ĐỘ SÁNG (mới trong ver 3) ---
DIVISION_ENABLED = True
# Khoảng cách = cửa sổ tìm kiếm (base rate 24:1 — không phải tín hiệu):
DIV_PARENT_GATE_UM = 12.0         # 10 → 12: bắt p99 bước mẹ→con (10,6, max 12,3)
DIV_SIBLING_GATE_UM = 14.5       # 12 → 14,5: p99 sister sep 13,9, max 14,65
DIV_MIN_CHILD_FRAC = 0.15         # con thứ 2 phải ≥ 15% độ sáng mẹ
DIV_BRIGHTNESS_CHECK = True      # bảo toàn độ sáng: I(con1)+I(con2) ≈ I(mẹ)
DIV_BRIGHTNESS_RATIO = (0.55, 1.8)
DIV_CONFIRM_FRAMES = 3           # 2 con phải sống ≥ 3 khung sau khi "sinh"
DIV_SEP_GROWTH = 1.15            # khoảng cách 2 con tăng ≥ 15% sau 3 khung
# ... ver 3 mới: theo dõi khối lượng từng track qua các khung —
MASS_HISTORY = 12                 # số khung gần nhất đưa vào baseline (dài đủ
                                 # để blob gộp không ngập nửa cửa sổ)
MASS_SKIP_LAST = 2                # loại 2 khung cuối (đúng lúc mẹ sáng lên)
DIV_MOM_MAX_RISE = 1.7           # mẹ tại khung tách ≤ 1,7× baseline riêng nó
                                 # (blob gộp 2 tế bào ≈ 2×; mẹ thật 1,1–1,5×)
DIV_MOM_MIN_FRAC = 0.5           # mẹ phai quá (đetection lép) → nghi merge-split
DIV_MOM_BRIGHT_BONUS = 1.05      # ưu tiên ứng viên có mẹ sáng dần ≥ 5%
MASS_BASE_MIN_FRAMES = 4         # track non hơn → chưa đủ baseline, bỏ qua check

# --- Soát bằng mắt (vẽ 1 khung đầu tiên) ---
RUN_PREVIEW = True

# --- Chẩn đoán ---
DIAGNOSE = True

NODE_ID = itertools.count(1)      # node_id duy nhất toàn cục
BIG = 1e9
