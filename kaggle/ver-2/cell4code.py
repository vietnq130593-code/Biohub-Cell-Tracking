# ver 2 · cell 4 — XUẤT SUBMISSION
# Dán đè Cell 4 của notebook Kaggle.
# ============================================================

COLS = ['dataset', 'row_type', 'node_id', 't', 'z', 'y', 'x', 'source_id', 'target_id']
submission = pd.DataFrame(all_rows, columns=COLS)
submission.index.name = 'id'
submission.to_csv('submission.csv')

n_nodes = int((submission['row_type'] == 'node').sum())
n_edges = int((submission['row_type'] == 'edge').sum())
n_div = sum(s[3] for s in summary)
print(f'Đã ghi submission.csv: {len(submission)} hàng '
      f'({n_nodes} node · {n_edges} cạnh · {n_div} phân bào)')
print(submission['row_type'].value_counts().to_string())
print(submission.head(8).to_string())
