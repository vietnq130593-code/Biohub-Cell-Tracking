# scorer · cell 1 — IMPORTS + CẤU HÌNH
# Notebook "LOCAL SCORER" — chấm submission trên dữ liệu TRAIN có ground-truth,
# đúng tinh thần metric chính thức (port từ repo royerlab/kaggle-cell-tracking-competition:
# metrics.py + division_metrics.py, không cần tracksdata/polars/geff).
#
# CÁCH DÙNG (Kaggle notebook mới, Add Input competition để có thư mục train):
#   1. Chạy cell này + cell 2 (định nghĩa engine).
#   2. Cell 3: đặt SUBMISSION_CSV = 'submission.csv' (file từ notebook pipeline
#      ver 2) hoặc None để tự chạy pipeline trực tiếp, rồi Run All.
#   3. Đọc bảng điểm per-dataset + tổng phân rã node recall / edge TP-FP-FN /
#      division TP-FP-FN + score = adjEJ + 0.1·divJ.
# ============================================================

import itertools
import json
import os
import time

import blosc2
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

# --- cấu hình ---
TRAIN_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/train'
SUBMISSION_CSV = 'submission.csv'   # None = bỏ qua (chỉ khi dùng chế độ khác)
MAX_DATASETS = 0                    # 0 = tất cả; >0 = giới hạn cho chạy nhanh
MAX_DISTANCE = 7.0                  # ngưỡng ghép node (µm) — đúng đề bài
SCALE = np.array([1.625, 0.40625, 0.40625], dtype=np.float64)

ADJUSTMENT_ALPHA = 0.1              # hệ số phạt node thừa (metric chính thức)
SCORE_DIVISION_WEIGHT = 0.1         # trọng số division trong điểm tổng
