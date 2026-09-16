#!/usr/bin/env python3
"""Sinh lại 2 notebook ver-4 vào /home/z/my-project/download từ cell code.

Nguồn sự thật:
  - cell1..4code.py  (đúng nguyên văn file .py)
  - kaggle/scorer/scorer2code.py + scorer3code.py (2 cell chấm điểm cuối)
  - markdown + phép biến đổi cell 2 bản chạy-train: nhúng tại đây.

Chạy:  python3 kaggle/ver-4/make-ver4-ipynb.py
(hotfix 14/09: thêm sau sự cố Kaggle NameError maximum_filter — cell 3 đã tự
 chứa import + cấu hình mặc định; script này được giữ lại vĩnh viễn trong repo)
"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DL = '/home/z/my-project/download'
SCORER = os.path.join(os.path.dirname(BASE), 'scorer')

MD_SUBMIT = '''# Biohub — Cell Tracking · ver 4 (stitching hậu kiểm)

Ver 4 nhắm thẳng **điểm nghẽn số 1** của điểm 0.198: **track đứt** (trung vị 2–3 node/track trên test trong khi GT là 35 khung/track):

- **`GATE_MIN_UM` 5 → 7 µm** — p99 bước GT = 6,9 µm, gate dưới đó giết cả bước hợp lệ
- **`MAX_SKIP_FRAMES` 2 → 3** — tế bào mờ 3 khung vẫn nối lại được
- **MỚI — Stitching hậu kiểm**: chạy hết dataset rồi mới nối mọi track kết thúc ở khung *t* với track mở đầu ở khung *t+gap* nếu nằm trong gate (10 + 2·(gap−1) µm) + khối lượng tương thích (~3×); gap ≥ 2 thì **chèn node nội suy** — chỉ tạo cạnh liền khung (cạnh nhảy bị metric bỏ hẳn). Chữa 3 tình huống mà Hungarian/frame-skip không với tới:
  1. blob gộp > 3 khung làm track bạn đồng hành chết hẳn,
  2. tế bào mờ > 3 khung,
  3. tế bào quẹo khi mờ → dự đoán pos+vel·gap trượt khỏi SKIP_GATE.
- Phát hiện / phân bào giữ nguyên ver 3 (mass stability đã chặn 2/2 merge-split trong kiểm chứng).

Kiểm chứng synthetic (`kaggle/ver-4/test-ver4-synth.py`): **ĐẠT TẤT CẢ 28/28 + 3 kiểm tự chứa** — 3 kịch bản đứt đều được nối lại (đối chứng stitch TẮT thì đứt), node nội suy đúng vị trí ≤ 3 µm, phân bào D duy nhất được xác nhận, không phân bào giả, mọi cạnh liền khung; chỉ dán đè cell 3 vào notebook có cell 1/2 cũ vẫn cho kết quả y hệt.

**Cách dùng**: File → Import Notebook vào Kaggle, Add Input competition, Save & Run All, Submit `submission.csv`. (Hoặc dán đè từng cell — cell 3 tự chứa hoàn toàn kể từ hotfix 14/09.)
'''

MD_TRAIN = '''# Biohub — Cell Tracking · ver 4 chạy trên TRAIN + chấm local scorer

Mục đích: **đo điểm offline** trước khi submit — pipeline ver 4 chạy trên thư mục `train` (có nhãn `.geff`) rồi chấm bằng port trung thành của metric chính thức (adjEJ + 0,1·divJ). Không tốn quota 5 submit/ngày.

**Cách dùng**: File → Import Notebook, Add Input competition, Save & Run All. Cell 2 đã trỏ `DATA_DIR` vào `train`; muốn đổi núm (PERCENTILE, STITCH_*, DIV_*) thì sửa cell 2 rồi Run All lại. So sánh nhanh: ver 1 = 0.198 trên Kaggle, top 1 ≈ 0.97.

Lưu ý: bản notebook NỘP BÀI là `ver4-cell-tracking.ipynb` (đọc `test`, không có cell chấm điểm).
'''

# ---- phép biến đổi cell 2 → bản chạy-train (khớp diff của bản ipynb cũ) ----
OLD_DATADIR = 'DATA_DIR = TEST_DIR'
NEW_DATADIR = (
    "TRAIN_DIR = '/kaggle/input/competitions/biohub-cell-tracking-during-development/train'\n"
    'DATA_DIR = TRAIN_DIR          # bản chạy-train: đọc train (có nhãn .geff)'
)
OLD_PREVIEW = '# --- Soát bằng mắt (vẽ 1 khung đầu tiên) ---\nRUN_PREVIEW = True'
NEW_PREVIEW = (
    '# --- Cấu hình LOCAL SCORER (các cell cuối notebook dùng) ---\n'
    "SUBMISSION_CSV = 'submission.csv'   # cell 4 vừa ghi\n"
    'MAX_DATASETS = 0                    # 0 = tất cả dataset train; >0 = chạy nhanh\n'
    'MAX_DISTANCE = 7.0                   # ngưỡng ghép node (µm) — đúng đề bài\n'
    'ADJUSTMENT_ALPHA = 0.1               # hệ số phạt node thừa (metric chính thức)\n'
    'SCORE_DIVISION_WEIGHT = 0.1         # trọng số division trong điểm tổng\n'
    '\n'
    '# --- Soát bằng mắt (vẽ 1 khung đầu tiên) ---\n'
    'RUN_PREVIEW = False'
)


def read(name):
    with open(os.path.join(BASE, name), encoding='utf-8') as f:
        return f.read()


def to_lines(src):
    return src.splitlines(keepends=True)


def code_cell(src):
    return {'cell_type': 'code', 'execution_count': None, 'metadata': {},
            'outputs': [], 'source': to_lines(src)}


def md_cell(src):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': to_lines(src)}


def build(c2_train):
    return {
        'cells': None,
        'metadata': {
            'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
            'language_info': {'name': 'python', 'version': '3.10.12'},
        },
        'nbformat': 4,
        'nbformat_minor': 4,
    }


def main():
    c1, c2, c3, c4 = (read(f'cell{i}code.py') for i in (1, 2, 3, 4))
    for name, src in (('cell1', c1), ('cell2', c2), ('cell3', c3), ('cell4', c4)):
        compile(src, name, 'exec')  # đảm bảo cú pháp hợp lệ trước khi đóng gói

    assert OLD_DATADIR in c2 and OLD_PREVIEW in c2, 'cell2code.py đổi dạng — cập nhật make-ver4-ipynb.py'
    c2t = c2.replace(OLD_DATADIR, NEW_DATADIR).replace(OLD_PREVIEW, NEW_PREVIEW)
    assert c2t != c2 and 'TRAIN_DIR' in c2t and 'RUN_PREVIEW = False' in c2t

    s2 = open(os.path.join(SCORER, 'scorer2code.py'), encoding='utf-8').read()
    s3 = open(os.path.join(SCORER, 'scorer3code.py'), encoding='utf-8').read()

    nb = build(c2t)
    nb['cells'] = [md_cell(MD_SUBMIT), code_cell(c1), code_cell(c2), code_cell(c3), code_cell(c4)]
    with open(os.path.join(DL, 'ver4-cell-tracking.ipynb'), 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    nb['cells'] = [md_cell(MD_TRAIN), code_cell(c1), code_cell(c2t), code_cell(c3),
                   code_cell(c4), code_cell(s2), code_cell(s3)]
    with open(os.path.join(DL, 'ver4-train-eval.ipynb'), 'w', encoding='utf-8') as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)

    print(f'OK — đã sinh 2 notebook vào {DL}:')
    print('  ver4-cell-tracking.ipynb  (5 cell: md + 4 code)')
    print('  ver4-train-eval.ipynb     (7 cell: md + cell2 TRAIN + cell3 + cell4 + scorer 2+3)')


if __name__ == '__main__':
    main()
