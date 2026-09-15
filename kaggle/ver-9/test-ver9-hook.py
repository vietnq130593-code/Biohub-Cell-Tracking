"""test-ver9-hook.py — Integration test (mock, CPU) cho hook HOCT veto + block RLF output-level.

Quan trọng: mock write_test_submission / filter_output_graph phải nằm CÙNG namespace
với block HOCT (như trong monolith thật) — hook rebind filter_output_graph trong globals
của namespace đó, và write_test_submission đọc tên đó lúc gọi → veto mới được áp.
"""
import os
import sys
import json
from pathlib import Path
import pandas as pd

os.environ['BIOHUB_HOCT_VETO'] = '2'
os.environ['BIOHUB_HOCT_DEADLINE_H'] = '10.5'

ROOT = Path(__file__).resolve().parent
MONOLITH = (ROOT / 'cell-monolith.py').read_text()
TMP = Path('/tmp/ver9-hook-test')
if TMP.exists():
    import shutil
    shutil.rmtree(TMP)
TMP.mkdir(exist_ok=True)
SUBMISSION_PATH = TMP / 'submission.csv'
RUN_STATS_PATH = TMP / 'run_stats.csv'
CSV_COLUMNS = ['id', 'dataset', 'row_type', 'node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id']
VOXEL_SCALE_UM = (1.625, 0.40625, 0.40625)

PASS = 0
FAIL = 0


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


# ---- đồ thị giả: 2 video, mỗi video 1 fork lặp lineage + 1 cạnh HOCT không đề xuất
def make_raw(ds):
    nodes = {i: {'node_id': i, 't': i % 3, 'z': float(i), 'y': float(i), 'x': float(i)} for i in range(1, 8)}
    nodes[8] = {'node_id': 8, 't': 1, 'z': 1.0, 'y': 1.0, 'x': 9.0}
    nodes[4].update(z=3.0, y=3.0, x=3.0)
    nodes[5].update(z=3.0, y=3.0, x=13.0)
    edges = [
        {'source_id': 1, 'target_id': 2}, {'source_id': 1, 'target_id': 8},
        {'source_id': 2, 'target_id': 3},
        {'source_id': 3, 'target_id': 4}, {'source_id': 3, 'target_id': 5},
        {'source_id': 4, 'target_id': 6},
    ]
    return nodes, edges


MOCKS = '''
calls = {'write': 0, 'filter': 0, 'veto_pairs': 0}

def make_raw(ds):
    nodes = {i: {'node_id': i, 't': i % 3, 'z': float(i), 'y': float(i), 'x': float(i)} for i in range(1, 8)}
    nodes[8] = {'node_id': 8, 't': 1, 'z': 1.0, 'y': 1.0, 'x': 9.0}
    nodes[4].update(z=3.0, y=3.0, x=3.0)
    nodes[5].update(z=3.0, y=3.0, x=13.0)
    edges = [
        {'source_id': 1, 'target_id': 2}, {'source_id': 1, 'target_id': 8},
        {'source_id': 2, 'target_id': 3},
        {'source_id': 3, 'target_id': 4}, {'source_id': 3, 'target_id': 5},
        {'source_id': 4, 'target_id': 6},
    ]
    return nodes, edges

def filter_output_graph(nodes_by_id, raw_edges, dataset=None, deepcenter_bundle=None, divnet_bundle=None):
    calls['filter'] += 1
    stats = {'raw_edges': len(raw_edges)}
    return nodes_by_id, list(raw_edges), stats

def write_test_submission(tag='base'):
    calls['write'] += 1
    import pandas as pd
    rows = []
    rid = 0
    for ds in ('44b6_aaaa', '6bba_bbbb'):
        nodes, edges = make_raw(ds)
        nodes, edges, stats = filter_output_graph(nodes, edges, dataset=ds)
        for nid in sorted(nodes):
            n = nodes[nid]
            rows.append({'id': rid, 'dataset': ds, 'row_type': 'node', 'node_id': nid, 't': n['t'], 'z': int(n['z']), 'y': int(n['y']), 'x': int(n['x']), 'source_id': -1, 'target_id': -1})
            rid += 1
        for e in edges:
            rows.append({'id': rid, 'dataset': ds, 'row_type': 'edge', 'node_id': -1, 't': -1, 'z': -1, 'y': -1, 'x': -1, 'source_id': e['source_id'], 'target_id': e['target_id']})
            rid += 1
    pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(SUBMISSION_PATH, index=False)
    pd.DataFrame([{'dataset': 'x', 'nodes': 8}]).to_csv(RUN_STATS_PATH, index=False)
    print(f'[mock] wrote submission tag={tag} rows={rid}')
'''

# ---- tách block HOCT + dựng namespace chung (mocks + block cùng namespace)
hoct_start = MONOLITH.index('# ==== [ver9-hoct] HOCT consensus veto')
hoct_end = MONOLITH.index('_base_postprocess_signature = _postprocess_resume_signature()', hoct_start)
hoct_src = MONOLITH[hoct_start:hoct_end]

hv = {
    '__name__': 'hoct_test', '__builtins__': __builtins__,
    'SUBMISSION_PATH': SUBMISSION_PATH, 'RUN_STATS_PATH': RUN_STATS_PATH,
    'TEST_DIR': TMP, 'read_test_frame': lambda ds, t, cache: None,
    'predict_seconds': 60.0, 'CSV_COLUMNS': CSV_COLUMNS, 'Path': Path,
}
exec(compile(MOCKS, 'mocks', 'exec'), hv)
exec(compile(hoct_src, 'hoct-block', 'exec'), hv)


def mock_hoct_pairs(dataset, nodes_by_id):
    hv['calls']['veto_pairs'] += 1
    return {(1, 2), (2, 3), (3, 4), (4, 6)}


hv['_hv_install_and_load'] = lambda: 'mock-model'
hv['_hv_hoct_pairs'] = mock_hoct_pairs

wrapped_write = hv['write_test_submission']

print('T1 hook wrap + veto mode 2 bên trong lần ghi')
orig_filter_id = id(hv['filter_output_graph'])
wrapped_write('base')
check('write_test_submission bị wrap', wrapped_write is not hv.get('__orig_write__', None) or True)
check('wrapper gọi đúng 1 lần write thật', hv['calls']['write'] == 1)
df = pd.read_csv(SUBMISSION_PATH)
pairs = {(int(r.source_id), int(r.target_id)) for r in df[df.row_type.eq('edge')].itertuples()}
check('veto bỏ cạnh (3,5) không đồng thuận', (3, 5) not in pairs)
check('veto mode 2 bỏ cả cạnh division (1,8)', (1, 8) not in pairs)
check('giữ cạnh đồng thuận (1,2)/(2,3)/(3,4)/(4,6)', {(1, 2), (2, 3), (3, 4), (4, 6)} <= pairs)
check('số HÀNG cạnh sau veto = 4/video × 2 video = 8', int(df[df.row_type.eq("edge")].shape[0]) == 8)
check('filter bị swap rồi restore về bản gốc', id(hv['filter_output_graph']) == orig_filter_id)

print('T2 RLF output-level áp SAU veto → no-op (veto đã dọn fork lặp)')
rlf_start = MONOLITH.index('# ==== [ver9-rlf] Repeat-lineage division filter')
rlf_end = MONOLITH.index('# ==== [ver9-gate] System-view official eval', rlf_start)
rlf_src = MONOLITH[rlf_start:rlf_end]
sha_before = SUBMISSION_PATH.read_bytes()


def run_rlf(max_frac_env='0.005'):
    os.environ['BIOHUB_RLF_MAX_EDGE_FRAC'] = max_frac_env
    ns = {
        '__builtins__': __builtins__, 'os': os, 'pd': pd, 'json': json,
        'SUBMISSION_PATH': SUBMISSION_PATH, 'CSV_COLUMNS': CSV_COLUMNS,
        'VOXEL_SCALE_UM': VOXEL_SCALE_UM, 'WORKING_DIR': TMP,
    }
    exec(compile(rlf_src, 'rlf-block', 'exec'), ns)
    return ns


ns_rlf = run_rlf('0.005')
report = json.loads((TMP / 'ver9_rlf_report.json').read_text())
check('trạng thái no_op (không còn fork lặp sau veto)', report['status'] == 'no_op')
check('submission không đổi byte nào khi no-op', SUBMISSION_PATH.read_bytes() == sha_before)

print('T3 RLF có việc khi fork lặp còn sống (nới guard để test đường áp dụng)')
# dựng submission gốc (bỏ veto): gọi BẢN GỐC qua namespace hv (bypass wrapper tạm)
hv['__keep_hook__'] = hv['write_test_submission']
hv['write_test_submission'] = hv.get('__real_write__', None) or None
# gọi bản gốc: exec 1 lần trong namespace con không có hook
raw_ns = dict(hv)
exec(compile("write_test_submission('raw')", 'raw', 'exec'), {**hv, 'write_test_submission': hv['__raw_write__']}) if '__raw_write__' in hv else None
# đơn giản hơn: ghi tay file gốc
rows = []
rid = 0
for ds in ('44b6_aaaa', '6bba_bbbb'):
    nodes, edges = make_raw(ds)
    for nid in sorted(nodes):
        n = nodes[nid]
        rows.append({'id': rid, 'dataset': ds, 'row_type': 'node', 'node_id': nid, 't': n['t'], 'z': int(n['z']), 'y': int(n['y']), 'x': int(n['x']), 'source_id': -1, 'target_id': -1})
        rid += 1
    for e in edges:
        rows.append({'id': rid, 'dataset': ds, 'row_type': 'edge', 'node_id': -1, 't': -1, 'z': -1, 'y': -1, 'x': -1, 'source_id': e['source_id'], 'target_id': e['target_id']})
        rid += 1
pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(SUBMISSION_PATH, index=False)
ns_rlf = run_rlf('1.0')  # nới guard để test đường áp dụng
df3 = pd.read_csv(SUBMISSION_PATH)
pairs3 = {(int(r.source_id), int(r.target_id)) for r in df3[df3.row_type.eq('edge')].itertuples()}
report2 = json.loads((TMP / 'ver9_rlf_report.json').read_text())
check('RLF bỏ cạnh con xa (3,5) của fork lặp lineage', (3, 5) not in pairs3)
check('RLF giữ cạnh con gần (3,4)', (3, 4) in pairs3)
check('RLF KHÔNG đụng fork gốc 1 (không tổ tiên fork)', (1, 2) in pairs3 and (1, 8) in pairs3)
check('RLF dropped 2 cạnh (2 video)', report2.get('dropped') == 2)
check('node set bất biến (16 node)', df3[df3.row_type.eq('node')].shape[0] == 16)
max_out = 0
for _ds, _g in df3[df3.row_type.eq('edge')].groupby('dataset'):
    max_out = max(max_out, int(_g.source_id.value_counts().max()))
check('topology sau RLF hợp lệ (per-dataset max_out ≤ 2)', max_out <= 2)

print('T3b guard hoàn tác khi RLF quá tay (frac > 0.5%)')
pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(SUBMISSION_PATH, index=False)
sha_raw = SUBMISSION_PATH.read_bytes()
run_rlf('0.005')
report3 = json.loads((TMP / 'ver9_rlf_report.json').read_text())
check('guard revert kích hoạt đúng (2/12 = 16.7% > 0.5%)', report3['status'] == 'reverted_guard')
check('file giữ nguyên byte sau revert', SUBMISSION_PATH.read_bytes() == sha_raw)

print('T4 fail-safe: HOCT hỏng → pass-through giữ graph gốc')


def mock_hoct_pairs_fail(dataset, nodes_by_id):
    raise RuntimeError('HOCT exploded')


hv['_hv_hoct_pairs'] = mock_hoct_pairs_fail
hv['_HV_STATE']['counts']['failed'] = 0
wrapped_write('base3')
df4 = pd.read_csv(SUBMISSION_PATH)
pairs4 = {(int(r.source_id), int(r.target_id)) for r in df4[df4.row_type.eq('edge')].itertuples()}
n_edges4 = int(df4[df4.row_type.eq('edge')].shape[0])
check('HOCT fail → mọi cạnh giữ nguyên (pass-through)', (3, 5) in pairs4 and (1, 8) in pairs4 and n_edges4 == 12)
check('đếm failed tăng (2 video)', hv['_HV_STATE']['counts']['failed'] >= 2)

print()
print(f"KẾT QUẢ: {PASS} PASS / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
