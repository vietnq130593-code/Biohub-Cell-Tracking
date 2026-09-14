#!/usr/bin/env python3
"""build-wave1.py — lắp wave1-sweep.py từ:
  - wave1-driver.py       (phần 1: header + env + bootstrap, kết thúc bằng # @@SLICES@@)
  - SLICE NGUYÊN VĂN từ kaggle/ver-7b/cell-monolith.py (bảng SLICES bên dưới —
    biên đã được xác minh từng dòng ngày 14/9/2026)
  - wave1-driver-part2.py (phần 2: audit collector + replay + E0/E1/E2/E3)

Sau khi build:
  1) py_compile wave1-sweep.py
  2) kiểm tra AST: mọi Name load trong file phải được định nghĩa (builtins/driver/slices)
  3) in đầu/cuối mỗi slice để đối chiếu tay
"""
from __future__ import annotations
import ast
import builtins
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MONOLITH = HERE.parent / 'ver-7b' / 'cell-monolith.py'
PART1 = HERE / 'wave1' / 'wave1-driver.py'
PART2 = HERE / 'wave1' / 'wave1-driver-part2.py'
OUT = HERE / 'wave1' / 'wave1-sweep.py'

# (tên, dòng_bắt_đầu, dòng_kết_thúc) — 1-index, inclusive — ver-7b/cell-monolith.py
SLICES = [
    ('constants', 403, 496),    # DET_THRESHOLD ... DEEPCENTER_SCORE_CACHE_MAX_FRAMES
    ('graph_geo', 1769, 1802),  # VOXEL_SCALE_UM ... _next_node_id
    ('frames', 1804, 1868),     # read_test_frame + refine_synthetic_midpoint
    ('deepcenter', 1870, 2181),  # _dc_pool_frame_xy ... deepcenter_accept_repair_point
    ('relink', 2183, 2298),     # _position_um + motion_relink_edges
    ('gaps', 2299, 2476),       # close_single_frame_gaps
    ('maps_gap2', 2477, 2629),  # _single_successor_map/_single_predecessor_map + recover_strict_gap2
    ('divnet', 2631, 2906),     # [ver7b] DivNet block + _divnet_rerank_proposals
    ('safediv', 2907, 3055),    # add_safe_divisions_postlink (NGUYÊN VĂN — không đụng)
    ('shorttrack', 3057, 3184),  # filter_short_track_components
    ('linefit', 3185, 3255),    # linefit_smooth_output_graph
    ('fog', 3257, 3386),        # filter_output_graph
    ('scoring', 3668, 3919),    # match_nodes_bipartite ... aggregate_official
]

MARKER = '# @@SLICES@@'


def main() -> int:
    monolith_lines = MONOLITH.read_text().splitlines()
    part1_text = PART1.read_text()
    part2_text = PART2.read_text()
    assert MARKER in part1_text, 'thiếu marker trong part1'

    header = part1_text.split(MARKER)[0]
    chunks = [header.rstrip() + '\n']
    print('=== CÁC SLICE (dòng đầu/cuối để đối chiếu) ===')
    for name, lo, hi in SLICES:
        block = '\n'.join(monolith_lines[lo - 1:hi]).rstrip('\n')
        first = block.splitlines()[0][:100]
        last = block.splitlines()[-1][:100]
        print(f'  {name:11s} L{lo}-{hi}: {first!r}')
        print(f'  {"":13s}-> {last!r}')
        chunks.append(f'\n# ---- [wave1-slice:{name}] monolith ver-7b L{lo}-{hi} (NGUYÊN VĂN) ----\n')
        chunks.append(block + '\n')
    chunks.append('\n\n' + part2_text)
    assembled = '\n'.join(chunks)
    OUT.write_text(assembled)
    print(f'\nĐÃ GHI {OUT} ({len(assembled.splitlines())} dòng)')

    # 1) py_compile
    import py_compile
    py_compile.compile(str(OUT), doraise=True)
    print('py_compile: OK')

    # 2) kiểm tra tên chưa định nghĩa (AST)
    tree = ast.parse(assembled)
    defined = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defined.add(node.name)
            defined.update(a.arg for a in getattr(node.args, 'args', []))
            defined.update(a.arg for a in getattr(node.args, 'kwonlyargs', []))
            if node.args.vararg:
                defined.add(node.args.vararg.arg)
            if node.args.kwarg:
                defined.add(node.args.kwarg.arg)
        elif isinstance(node, ast.ClassDef):
            defined.add(node.name)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
        elif isinstance(node, (ast.Import,)):
            for a in node.names:
                defined.add((a.asname or a.name).split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                defined.add(a.asname or a.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            defined.add(node.name)
        elif isinstance(node, (ast.comprehension,)):
            for t in ast.walk(node.target):
                if isinstance(t, ast.Name):
                    defined.add(t.id)
        elif isinstance(node, ast.Global):
            defined.update(node.names)
    # global + nonlocal trong hàm xử riêng: names trong hàm được coi là local scope —
    # kiểm tra thô: mọi Name load phải thuộc defined
    missing = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id not in defined:
                missing.add(node.id)
    # loại các tên chỉ xuất hiện trong annotation chuỗi / typeddict false-positive
    known_ok = {'Self', 'Any', 'type', 'biohub_tracking'}
    missing -= known_ok
    if missing:
        print('CẢNH BÁO — tên có thể chưa định nghĩa (cần rà tay):')
        for name in sorted(missing):
            print('   -', name)
    else:
        print('AST name-check: OK (không có tên thiếu)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
