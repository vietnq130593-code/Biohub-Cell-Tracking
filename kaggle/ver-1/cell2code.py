# ver 1 · cell 2 — SIÊU THAM SỐ (mọi núm tune nằm ở đây)
# Dán đè Cell 2 của notebook Kaggle.
# ============================================================

TEST_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/test'

# Thang vật lý (Z, Y, X) — µm/voxel, theo đề bài
SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)

# --- Tầng 1 · DETECTION ---
DS_Z, DS_Y, DS_X = 2, 4, 4       # downsample bất đối xứng: z giữ kỹ hơn
SMOOTH_SIZE = 3                   # uniform_filter, trong không gian downsample
PERCENTILE = 92.0                 # ngưỡng sáng — QUÉT 88/90/92/94/96
MIN_NVOXELS = 4                   # bỏ component li ti (nhiễu)
MAX_NVOXELS = 1000                # bỏ blob khổng lồ (merge/nền)
CONN26 = True                     # liên kết 26-ô: chống tách nhân giữa các lát z

# --- Tầng 2 · LINKING (motion model + gate thích ứng) ---
BASE_GATE_UM = 8.0                # gate khi chưa đủ thống kê bước đi
GATE_MEDIAN_MULT = 2.5            # gate = mult × trung vị bước đi gần nhất
GATE_MIN_UM, GATE_MAX_UM = 5.0, 12.0
VEL_SMOOTH = 0.5                  # vận tốc EMA: v ← 0.5·mới + 0.5·cũ
BRIGHT_WEIGHT = 0.0               # phạt chênh độ sáng trong cost (0 = tắt; thử 0.05–0.15)

# --- Frame-skip + nội suy ---
ALLOW_FRAME_SKIP = True           # nối lại track khi mất 1 khung
SKIP_GATE_UM = 10.0
MAX_SKIP_FRAMES = 1
INTERPOLATE_MISSED_FRAMES = True  # chèn node nội suy + 2 cạnh liền khung tại khung mất
TIME_LIMIT_HOURS = 11.0           # dừng sớm ghi nốt submission (giới hạn Kaggle 12h)

# --- Tầng 3 · PHÂN BÀO ---
DIVISION_ENABLED = True
DIV_PARENT_GATE_UM = 10.0         # mẹ → con thứ hai
DIV_SIBLING_GATE_UM = 12.0        # 2 con mới sinh hay bị ngưỡng gộp tới ~8–10 µm
DIV_MIN_CHILD_FRAC = 0.15         # con thứ 2 phải ≥ 15% độ sáng mẹ (chặn nhiễu li ti)
DIV_BRIGHTNESS_CHECK = True       # bảo toàn độ sáng: I(con1)+I(con2) ≈ I(mẹ)
DIV_BRIGHTNESS_RATIO = (0.55, 1.8)

# --- Soát bằng mắt (vẽ 1 khung đầu tiên) ---
RUN_PREVIEW = True

NODE_ID = itertools.count(1)      # node_id duy nhất toàn cục
BIG = 1e9
