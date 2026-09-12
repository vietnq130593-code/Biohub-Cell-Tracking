# scorer · cell 3 — CHẠY CHẤM ĐIỂM
# ============================================================

if not os.path.isdir(TRAIN_DIR):
    hint = os.listdir('/kaggle/input') if os.path.isdir('/kaggle/input') else 'không có /kaggle/input'
    raise FileNotFoundError(f'Không thấy {TRAIN_DIR} — Add Input competition. /kaggle/input: {hint}')

if SUBMISSION_CSV and not os.path.isfile(SUBMISSION_CSV):
    raise FileNotFoundError(f'Không thấy {SUBMISSION_CSV} — chạy notebook pipeline trước rồi thử lại')

geff_names = sorted(f[:-5] for f in os.listdir(TRAIN_DIR) if f.endswith('.geff'))
if not geff_names:
    raise RuntimeError(f'Không tìm thấy .geff nào trong {TRAIN_DIR}')
if MAX_DATASETS > 0:
    geff_names = geff_names[:MAX_DATASETS]
print(f'{len(geff_names)} dataset có GT: {geff_names[:8]}{"..." if len(geff_names) > 8 else ""}')

pred_graphs = load_submission_graphs(SUBMISSION_CSV) if SUBMISSION_CSV else {}

rows = []
t0 = time.time()
for name in geff_names:
    if name not in pred_graphs:
        print(f'  SKIP {name}: không có trong submission')
        continue
    gt = Graph(read_geff(os.path.join(TRAIN_DIR, name + '.geff')))
    pred = pred_graphs[name]
    r = evaluate_one(pred, gt)
    r['dataset'] = name
    rows.append(r)
    print(f"  {name}: EJ={r['edge_jaccard']:.4f} adjEJ={r['adj_edge_jaccard']:.4f} "
          f"edge {r['edge_tp']}/{r['edge_fp']}/{r['edge_fn']} "
          f"div {r['division_tp']}/{r['division_fp']}/{r['division_fn']} "
          f"recall={r['node_recall']:.3f} n_pred={r['num_pred_nodes']}", flush=True)

s = summarise(rows)
print(f'\n=== TỔNG ({len(rows)} dataset, {time.time() - t0:.0f}s) ===')
if s:
    print(f"score                = {s['score']:.4f}")
    print(f"adj_edge_jaccard     = {s['adj_edge_jaccard']:.4f}   (edge J = {s['edge_jaccard']:.4f})")
    print(f"division_jaccard     = {s['division_jaccard']:.4f}   "
          f"(TP={s['division_tp']} FP={s['division_fp']} FN={s['division_fn']})")
    print(f"node_recall          = {s['node_recall']:.4f}")
    print(f"edge TP/FP/FN        = {s['edge_tp']}/{s['edge_fp']}/{s['edge_fn']}")
    print(f"số node dự đoán      = {s['num_pred_nodes']}")
    print()
    print('So sánh nhanh: ver 1 Kaggle = 0.198 · top 1 = 0.97')
    if s['edge_fn'] > s['edge_tp']:
        print('→ FN cạnh trội TP: ưu tiên TĂNG RECALL (hạ ngưỡng, mở gate, '
              'nối lại track đứt, nội suy).')
    if s['edge_fp'] > 0.3 * s['edge_tp']:
        print('→ FP cạnh đáng kể: kiểm tra cạnh chéo giữa 2 track gần nhau, '
              'coi chừng gán nhầm sau nội suy.')
    if s['division_fn'] > 2 * s['division_tp'] and s['division_fn'] > 0:
        print('→ bỏ sót phân bào: giảm DIV_CONFIRM_FRAMES hoặc nới gate.')
    if s['division_fp'] > s['division_tp'] and s['division_fp'] > 0:
        print('→ phân bào giả: tăng DIV_CONFIRM_FRAMES / DIV_SEP_GROWTH.')

# bảng chi tiết ra DataFrame để dễ xem
detail = pd.DataFrame(rows).set_index('dataset') if rows else None
detail
