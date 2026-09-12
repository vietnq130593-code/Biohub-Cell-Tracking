# ver 4 · cell 2 — SIÊU THAM SỐ (mọi núm tune nằm ở đây)
# Dán đè Cell 2 của notebook Kaggle.
# ============================================================
# Mục tiêu ver 4 — NỐI LẠI TRACK ĐỨT (điểm nghẽn số 1 của điểm 0.198):
# chẩn đoán ver 3 trên test: trung vị 2–3 node/track trong khi GT là
# 35 khung/track; ~20% node mở đầu track mới. Ba nguyên nhân + ba cách vá:
#   1. GATE_MIN_UM 5 → 7: p99 bước GT = 6,9µm — gate dưới đó giết cả bước
#      hợp lệ (gate thích ứng = 2,5×median từng vùng, bị kẹp [GATE_MIN, 14]).
#   2. MAX_SKIP_FRAMES 2 → 3: tế bào mờ 3 khung vẫn nối lại được.
#   3. MỚI — STITCHING HẬU KIỂM: chạy hết dataset rồi mới nối mọi track
#      kết thúc ở khung t với track mở đầu ở khung t+gap nếu nằm trong
#      gate + khối lượng tương thích; gap ≥ 2 thì CHÈN NODE NỘI SUY
#      (chỉ tạo cạnh liền khung — cạnh nhảy bị metric bỏ hẳn).
# Phần phát hiện / phân bào giữ nguyên ver 3 (đã kiểm chứng 21/21).
# ============================================================

TEST_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/test'
# Cell 3 đọc DATA_DIR — bản nộp bài giữ = TEST_DIR; bản chạy trên train
# (để chấm bằng local scorer) đổi thành TRAIN_DIR của competition.
DATA_DIR = TEST_DIR

# Thang vật lý (Z, Y, X) — µm/voxel, theo đề bài
SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)

# --- Tầng 1 · DETECTION (giữ nguyên ver 3) ---
DS_Z, DS_Y, DS_X = 2, 4, 4       # downsample bất đối xứng: z giữ kỹ hơn
SMOOTH_SIZE = 3                   # uniform_filter, trong không gian downsample
PERCENTILE = 90.0                 # bắt thêm nhân mờ (recall > precision)
MIN_NVOXELS = 4                   # bỏ component li ti (nhiễu)
MAX_NVOXELS = 3000                # blob gộp vẫn nhận, tách ở tầng 1b
CONN26 = True                     # liên kết 26-ô: chống tách nhân giữa các lát z

# --- Tầng 1b · TÁCH BLOB GỘP (giữ nguyên ver 3) ---
SPLIT_MIN_NVOXELS = 90            # component ds lớn hơn mới xét tách
PEAK_SIZE = (3, 5, 5)             # maximum_filter tìm đỉnh cục bộ (z,y,x ds)
MIN_PEAK_DIST_DS = 4.0            # 2 đỉnh cách ≥ 4 voxel ds
PEAK_MIN_BRIGHT = 1.15            # đỉnh sáng hơn ngưỡng ít nhất 15%

# --- Tầng 2 · LINKING (ver 4: GATE_MIN 5 → 7) ---
BASE_GATE_UM = 9.0
GATE_MEDIAN_MULT = 2.5
GATE_MIN_UM, GATE_MAX_UM = 7.0, 14.0   # p99 bước GT 6,9µm — min 5 giết bước hợp lệ
VEL_SMOOTH = 0.5                  # vận tốc EMA: v ← 0.5·mới + 0.5·cũ
BRIGHT_WEIGHT = 0.0               # phạt chênh độ sáng trong cost (tắt)

# --- Frame-skip + nội suy (ver 4: MAX_SKIP 2 → 3) ---
ALLOW_FRAME_SKIP = True
SKIP_GATE_UM = 12.0
MAX_SKIP_FRAMES = 3
INTERPOLATE_MISSED_FRAMES = True  # GT 100% cạnh liền khung → nội suy bắt buộc
TIME_LIMIT_HOURS = 11.0

# --- MỚI ver 4 · STITCHING HẬU KIỂM (chạy trong cell 3) ---
STITCH_ENABLED = True
STITCH_GAP_MAX = 5                    # nối lại track đứt cách ≤ 5 khung
STITCH_GATE_UM = 10.0                 # gate tại gap=1: bắt bước 7–10µm
STITCH_GATE_PER_GAP = 2.0             # gate(g) = 10 + 2·(g−1) µm (g=5 → 18)
STITCH_MAX_LOGMASS = 1.1              # |ln(m_start/m_end)| ≤ 1,1 (~3×)
STITCH_COLLISION_UM = 0.0             # 0 = tắt: hành lang nối blob-break đi đúng
                                      # qua node CoM của track bạn đồng hành

# --- Tầng 3 · PHÂN BÀO THEO PROFILE ĐỘ SÁNG (giữ nguyên ver 3) ---
DIVISION_ENABLED = True
DIV_PARENT_GATE_UM = 12.0         # cửa sổ tìm kiếm (base rate 24:1)
DIV_SIBLING_GATE_UM = 14.5       # p99 sister sep 13,9, max 14,65
DIV_MIN_CHILD_FRAC = 0.15
DIV_BRIGHTNESS_CHECK = True
DIV_BRIGHTNESS_RATIO = (0.55, 1.8)
DIV_CONFIRM_FRAMES = 3
DIV_SEP_GROWTH = 1.15
MASS_HISTORY = 12
MASS_SKIP_LAST = 2
DIV_MOM_MAX_RISE = 1.7
DIV_MOM_MIN_FRAC = 0.5
DIV_MOM_BRIGHT_BONUS = 1.05
MASS_BASE_MIN_FRAMES = 4

# --- Soát bằng mắt (vẽ 1 khung đầu tiên) ---
RUN_PREVIEW = True

# --- Chẩn đoán ---
DIAGNOSE = True

NODE_ID = itertools.count(1)      # node_id duy nhất toàn cục
BIG = 1e9
