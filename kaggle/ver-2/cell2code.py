# ver 2 · cell 2 — SIÊU THAM SỐ (mọi núm tune nằm ở đây)
# Dán đè Cell 2 của notebook Kaggle.
# ============================================================
# Nguyên tắc ver 2 (rút từ điểm Kaggle 0.198 của ver 1 + đọc kỹ metric
# chính thức trong repo royerlab/kaggle-cell-tracking-competition):
#   1. RECALL LÀ ĐÒN BẨY LỚN NHẤT — TP ~ r² (cả 2 đầu cạnh đều phải khớp),
#      còn phạt node thừa rất nhẹ: adjEJ = EJ·(1 − 0.1·(N_pred−N_true)/N_true).
#      → hạ ngưỡng, mở gate, nối lại track rách nhiều hơn.
#   2. Cạnh FP CHỶ tính khi bám node GT (nguồn có cạnh ra / đích có cạnh vào);
#      cạnh giữa tế bào chưa được chú thích bị bỏ qua → cứ nối khắp nơi,
#      miễn là KHÔNG chặn node GT của track khác.
#   3. Cạnh nhảy t→t+k bị metric BỎ HẲN (không TP) → phải nội suy node giữa.
#   4. Fork (≥2 cạnh ra) là phân bào theo metric; fork giả = division FP
#      → phải xác nhận bằng động học (khoảng cách 2 con tăng dần).
# ============================================================

TEST_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/test'

# Thang vật lý (Z, Y, X) — µm/voxel, theo đề bài
SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)

# --- Tầng 1 · DETECTION ---
DS_Z, DS_Y, DS_X = 2, 4, 4       # downsample bất đối xứng: z giữ kỹ hơn
SMOOTH_SIZE = 3                   # uniform_filter, trong không gian downsample
PERCENTILE = 90.0                 # 92 → 90: bắt thêm nhân mờ (recall > precision)
MIN_NVOXELS = 4                   # bỏ component li ti (nhiễu)
MAX_NVOXELS = 3000                # 1000 → 3000: blob gộp vẫn nhận, sẽ tách ở dưới
CONN26 = True                     # liên kết 26-ô: chống tách nhân giữa các lát z

# --- Tầng 1b · TÁCH BLOB GỘP (mới trong ver 2) ---
SPLIT_MIN_NVOXELS = 90            # component ds lớn hơn mới xét tách (~2.9 µm³/node trung vị)
PEAK_SIZE = (3, 5, 5)             # maximum_filter tìm đỉnh cục bộ (z,y,x ds)
MIN_PEAK_DIST_DS = 4.0            # 2 đỉnh phải cách ≥ 4 voxel ds (~6.5 µm ngang, ~13 µm dọc)
PEAK_MIN_BRIGHT = 1.15            # đỉnh phải sáng hơn ngưỡng ít nhất 15% (chống đỉnh nhiễu)

# --- Tầng 2 · LINKING (motion model + gate thích ứng) ---
BASE_GATE_UM = 9.0                # 8 → 9: gate khi chưa đủ thống kê bước đi
GATE_MEDIAN_MULT = 2.5            # gate = mult × trung vị bước đi gần nhất
GATE_MIN_UM, GATE_MAX_UM = 5.0, 14.0   # 12 → 14: bắt tế bào nhanh
VEL_SMOOTH = 0.5                  # vận tốc EMA: v ← 0.5·mới + 0.5·cũ
BRIGHT_WEIGHT = 0.0               # phạt chênh độ sáng trong cost (0 = tắt; thử 0.05–0.15)

# --- Frame-skip + nội suy ---
ALLOW_FRAME_SKIP = True           # nối lại track khi mất khung
SKIP_GATE_UM = 12.0                # 10 → 12
MAX_SKIP_FRAMES = 2               # 1 → 2: phục hồi track đứt dài hơn
INTERPOLATE_MISSED_FRAMES = True  # chèn node nội suy + 2 cạnh liền khung tại khung mất
TIME_LIMIT_HOURS = 11.0           # dừng sớm ghi nốt submission (giới hạn Kaggle 12h)

# --- Tầng 3 · PHÂN BÀO (xác nhận động học học — mới trong ver 2) ---
DIVISION_ENABLED = True
DIV_PARENT_GATE_UM = 10.0         # mẹ → con thứ hai
DIV_SIBLING_GATE_UM = 12.0        # 2 con mới sinh hay bị ngưỡng gộp tới ~8–10 µm
DIV_MIN_CHILD_FRAC = 0.15         # con thứ 2 phải ≥ 15% độ sáng mẹ (chặn nhiễu li ti)
DIV_BRIGHTNESS_CHECK = True       # bảo toàn độ sáng: I(con1)+I(con2) ≈ I(mẹ)
DIV_BRIGHTNESS_RATIO = (0.55, 1.8)
DIV_CONFIRM_FRAMES = 3            # phân bào phải sống ≥ 3 khung sau khi "sinh"
DIV_SEP_GROWTH = 1.15             # khoảng cách 2 con phải tăng ≥ 15% sau 3 khung
#    (merge-split giả: 2 "con" ở xa nhau ngay từ đầu, khoảng cách gần như đứng yên;
#     phân bào thật: 2 con gần nhau lúc sinh rồi tách dần ra)

# --- Soát bằng mắt (vẽ 1 khung đầu tiên) ---
RUN_PREVIEW = True

# --- Chẩn đoán (mới trong ver 2): in thêm số liệu健康 mỗi dataset ---
DIAGNOSE = True

NODE_ID = itertools.count(1)      # node_id duy nhất toàn cục
BIG = 1e9
