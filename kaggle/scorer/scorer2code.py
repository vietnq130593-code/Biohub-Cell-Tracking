# scorer · cell 2 — ENGINE: ĐỌC .GEFF + METRIC CHÍNH THỨC (port)
# ============================================================
# Port từ royerlab/kaggle-cell-tracking-competition:
#   src/tracking_cellmot/metrics.py        (edge metric + adj + summarise)
#   src/tracking_cellmot/division_metrics.py (division metric đầy đủ)
#   tracksdata DistanceMatching (ghép node per-timepoint, Hungarian ≤ 7 µm)
# Chỉ dùng numpy/scipy/pandas/blosc2 — không cần tracksdata/geff/zarr.

# ---------- 1) ĐỌC ZARR (v2 + v3) ----------
def _read_zarr_array(arr_path):
    """Đọc mảng zarr v2 (.zarray + chunk i.j.k) hoặc v3 (zarr.json + chunk c/i/j/k).
    Hỗ trợ 1D/2D, nhiều chunk, nén blosc hoặc không nén."""
    v2 = os.path.join(arr_path, '.zarray')
    if os.path.isfile(v2):
        with open(v2) as f:
            meta = json.load(f)
        dt = np.dtype(meta['dtype'])
        shape = [int(s) for s in meta['shape']]
        chunks = [int(c) for c in meta['chunks']]
        compressed = bool(meta.get('compressor'))
        prefix, sep = '', '.'
    else:
        with open(os.path.join(arr_path, 'zarr.json')) as f:
            meta = json.load(f)
        dt = np.dtype(meta['data_type'])
        shape = [int(s) for s in meta['shape']]
        chunks = [int(c) for c in
                  meta['chunk_grid']['configuration']['chunk_shape']]
        compressed = True
        prefix, sep = os.path.join('c', ''), '.'

    arr = np.zeros(shape, dtype=dt)
    grids = [range((s + c - 1) // c) for s, c in zip(shape, chunks)]
    for idx in itertools.product(*grids):
        fname = os.path.join(arr_path, prefix + sep.join(str(i) for i in idx))
        if not os.path.isfile(fname):
            continue
        with open(fname, 'rb') as f:
            raw = f.read()
        data = blosc2.decompress(raw) if compressed else raw
        block = np.frombuffer(data, dtype=dt)
        need = int(np.prod(chunks))
        block = block[:need].reshape(chunks)
        sl = tuple(
            slice(i * c, min((i + 1) * c, s))
            for i, c, s in zip(idx, chunks, shape)
        )
        inner = tuple(slice(0, s.stop - s.start) for s in sl)
        arr[sl] = block[inner]
    return arr


def read_geff(path):
    """Đọc .geff → dict:
    t, z, y, x (mảng node), node_ids, edges (E×2: source, target),
    n_total (estimated_number_of_nodes từ metadata, NaN nếu không có)."""
    v2attrs = os.path.join(path, '.zattrs')
    if os.path.isfile(v2attrs):
        with open(v2attrs) as f:
            attrs = json.load(f)
    else:
        with open(os.path.join(path, 'zarr.json')) as f:
            attrs = json.load(f).get('attributes', {})
    geff_meta = attrs.get('geff', {})

    node_ids = _read_zarr_array(os.path.join(path, 'nodes', 'ids')).astype(np.int64)
    n = len(node_ids)

    def prop(name, default):
        p = os.path.join(path, 'nodes', 'props', name, 'values')
        if not (os.path.isdir(p) or os.path.isfile(os.path.join(p, '.zarray'))
                or os.path.isfile(os.path.join(p, 'zarr.json'))):
            return np.full(n, default)
        a = _read_zarr_array(p)
        return a.astype(np.float64)

    t = prop('t', 0.0)
    z = prop('z', 0.0)
    y = prop('y', 0.0)
    x = prop('x', 0.0)

    epath = os.path.join(path, 'edges', 'ids')
    if (os.path.isfile(os.path.join(epath, '.zarray'))
            or os.path.isfile(os.path.join(epath, 'zarr.json'))):
        edges = _read_zarr_array(epath).astype(np.int64).reshape(-1, 2)
    else:
        edges = np.zeros((0, 2), dtype=np.int64)

    extra = geff_meta.get('extra', {}) or {}
    n_total = float(extra.get('estimated_number_of_nodes', np.nan))
    if not (n_total == n_total):  # NaN
        n_total = float('nan')

    return {'ids': node_ids, 't': t, 'z': z, 'y': y, 'x': x,
            'edges': edges, 'n_total': n_total}


# ---------- 2) CẤU TRÚC GRAPH NHẸ ----------
class Graph:
    __slots__ = ('pos', 't', 'edges', 'succ', 'pred', 'out_deg', 'in_deg',
                 'n_total')

    def __init__(self, g):
        self.pos = np.stack([g['z'], g['y'], g['x']], axis=1) * SCALE  # µm
        self.t = g['t'].astype(np.int64)
        # remap node_id gốc → chỉ số nội bộ 0..N-1 (giống csv_to_geffs
        # của BTC gán id mới — matching theo vị trí, không theo id)
        id2idx = {int(nid): i for i, nid in enumerate(g['ids'])}
        self.edges = []
        for s, d in g['edges']:
            s, d = int(s), int(d)
            if s not in id2idx or d not in id2idx:
                continue  # cạnh treo lơ lửng — bỏ (metric cũng bỏ)
            self.edges.append((id2idx[s], id2idx[d]))
        self.n_total = g['n_total']
        self.succ, self.pred = {}, {}
        self.out_deg, self.in_deg = {}, {}
        for s, d in self.edges:
            self.succ.setdefault(s, []).append(d)
            self.pred.setdefault(d, []).append(s)
            self.out_deg[s] = self.out_deg.get(s, 0) + 1
            self.in_deg[d] = self.in_deg.get(d, 0) + 1

    def successors(self, n):
        return self.succ.get(n, [])

    def predecessors(self, n):
        return self.pred.get(n, [])

    def dividing_nodes(self):
        return [n for n in self.succ if len(self.succ[n]) >= 2]

    def num_nodes(self):
        return len(self.t)

    def num_edges(self):
        return len(self.edges)


# ---------- 3) GHÉP NODE PER-TIMEPOINT (như tracksdata DistanceMatching) ----------
def match_nodes(pred, gt, max_distance=MAX_DISTANCE, gt_subset=None):
    """Ghép node pred ↔ gt theo từng mốc thời gian bằng Hungarian, ≤ max_distance.
    gt_subset: nếu cho, chỉ ghép với các node GT trong tập này (cho division window).
    Trả về dict pred_node → gt_node."""
    gt_idx = np.arange(gt.num_nodes())
    if gt_subset is not None:
        gt_idx = np.array(sorted(gt_subset), dtype=np.int64)
    gt_by_t = {}
    for i in gt_idx:
        gt_by_t.setdefault(int(gt.t[i]), []).append(int(i))

    matched = {}
    used_pred_by_t = {}
    for i in range(pred.num_nodes()):
        used_pred_by_t.setdefault(int(pred.t[i]), []).append(i)

    for tt, pidx in used_pred_by_t.items():
        gidx = gt_by_t.get(tt, [])
        if not gidx or not pidx:
            continue
        P = pred.pos[pidx]
        G = gt.pos[gidx]
        D = np.linalg.norm(P[:, None, :] - G[None, :, :], axis=2)
        ok = D <= max_distance
        if not ok.any():
            continue
        cost = np.where(ok, D, 1e9)
        ri, ci = linear_sum_assignment(cost)
        for r, c in zip(ri, ci):
            if D[r, c] <= max_distance:
                matched[pidx[r]] = gidx[c]  # gidx đã là chỉ số toàn cục
    return matched


# ---------- 4) EDGE METRIC (port metrics.py) ----------
def _evaluate_edge_counts(pred, gt, matched):
    """Đếm edge TP/FP/FN đúng thuật toán chính thức:
    1. bỏ cạnh không liền khung (t_dst == t_src + 1)
    2. bỏ cạnh trùgn map vào cùng cạnh GT (merge collapse) — giữ edge thấp nhất
    3. cap out-degree ≤ 2 (giữ 2 cạnh thấp nhất theo thứ tự)
    4. pred_valid: nguồn khớp GT-có-cạnh-ra HOẶC đích khớp GT-có-cạnh-vào
    5. TP = cạnh hai đầu khớp + GT có cạnh tương ứng; FP = valid − TP; FN = GT − TP
    """
    tpos = {i: int(pred.t[i]) for i in range(pred.num_nodes())}
    pred_edges = []
    for ei, (s, d) in enumerate(pred.edges):
        if s not in tpos or d not in tpos:
            continue
        if tpos[d] - tpos[s] != 1:
            continue  # metric bỏ hẳn cạnh nhảy
        pred_edges.append((ei, s, d))

    # collapse merge: cùng cặp (matched_source, matched_target)
    seen_pairs = {}
    kept = []
    for ei, s, d in pred_edges:
        ms = matched.get(s, -1)
        md = matched.get(d, -1)
        if ms >= 0 and md >= 0:
            key = (ms, md)
            if key in seen_pairs:
                continue
            seen_pairs[key] = ei
        kept.append((ei, s, d))

    # cap out-degree ≤ 2 theo thứ tự edge id
    out_count = {}
    capped = []
    for ei, s, d in kept:
        out_count[s] = out_count.get(s, 0) + 1
        if out_count[s] <= 2:
            capped.append((ei, s, d))

    gt_edge_set = set((int(a), int(b)) for a, b in gt.edges)

    tp = 0
    valid = 0
    for ei, s, d in capped:
        ms = matched.get(s, -1)
        md = matched.get(d, -1)
        src_ok = ms >= 0 and gt.out_deg.get(ms, 0) > 0
        dst_ok = md >= 0 and gt.in_deg.get(md, 0) > 0
        if src_ok or dst_ok:
            valid += 1
        if ms >= 0 and md >= 0 and (ms, md) in gt_edge_set:
            tp += 1
    fn = gt.num_edges() - tp
    fp = valid - tp
    return tp, fp, fn


# ---------- 5) DIVISION METRIC (port division_metrics.py) ----------
def _bipartite_max_matching(left, edges):
    """Maximum-cardinality bipartite matching (DFS augmenting path).
    edges: left → set(right). Trả về dict left→right."""
    match_r, match_l = {}, {}

    def augment(u, seen):
        for v in edges.get(u, ()):
            if v in seen:
                continue
            seen.add(v)
            if v not in match_r or augment(match_r[v], seen):
                match_l[u] = v
                match_r[v] = u
                return True
        return False

    for u in left:
        augment(u, set())
    return match_l


def _gt_weak_components(gt):
    comp = {}
    for seed in range(gt.num_nodes()):
        if seed in comp:
            continue
        comp[seed] = seed
        stack = [seed]
        while stack:
            cur = stack.pop()
            for nb in list(gt.successors(cur)) + list(gt.predecessors(cur)):
                if nb not in comp:
                    comp[nb] = seed
                    stack.append(nb)
    return comp


def _extract_divisions(gt):
    """div_node → {'parents', 'children', 'grandchildren', 'keep'}."""
    out = {}
    for div in gt.dividing_nodes():
        parents = list(gt.predecessors(div))
        children = list(gt.successors(div))
        grandchildren = [g for c in children for g in gt.successors(c)]
        out[div] = {'parents': parents, 'children': children,
                    'grandchildren': grandchildren,
                    'keep': set(parents) | {div} | set(children) | set(grandchildren)}
    return out


def _branch_component_evidence(pred, pred_div, child, pred_to_gt, gt_comp):
    """(component, malformed) cho một nhánh con của fork."""
    if set(pred.predecessors(child)) != {pred_div}:
        return None, True
    if child in pred_to_gt:
        return gt_comp[pred_to_gt[child]], False
    grandchildren = pred.successors(child)
    for g in grandchildren:
        if set(pred.predecessors(g)) != {child}:
            return None, True
    comps = {gt_comp[pred_to_gt[g]] for g in grandchildren if g in pred_to_gt}
    if len(comps) == 1:
        return next(iter(comps)), False
    return None, False


def _is_strongly_connected(pred, pred_div, parent_ids, daughter_ids):
    pred_parent_ids = {pred_div, *pred.predecessors(pred_div)}
    if pred_parent_ids.isdisjoint(parent_ids):
        return False
    pred_lineages = [{c, *pred.successors(c)} for c in pred.successors(pred_div)]
    edges = {
        gi: {li for li, pl in enumerate(pred_lineages) if not ids.isdisjoint(pl)}
        for gi, ids in enumerate(daughter_ids)
    }
    return len(_bipartite_max_matching(list(edges), edges)) >= 2


def evaluate_divisions(pred, gt, max_distance=MAX_DISTANCE):
    """Trả về (tp, fp, fn) cho division — port đầy đủ topology chính thức."""
    if gt.num_edges() == 0 or gt.num_nodes() == 0 or pred.num_nodes() == 0:
        return 0, 0, 0
    divs = _extract_divisions(gt)
    pred_div_nodes = set(pred.dividing_nodes())

    # fork sets từ full matching
    full_match = match_nodes(pred, gt, max_distance)
    evaluable_forks = {
        p for p in pred_div_nodes
        if p in full_match and gt.out_deg.get(full_match[p], 0) >= 1
    }
    gt_comp = _gt_weak_components(gt)
    cross_component, malformed = set(), set()
    for p in pred_div_nodes:
        branch_evidence = []
        broke = False
        for child in pred.successors(p):
            comp, bad = _branch_component_evidence(pred, p, child, full_match, gt_comp)
            if bad:
                malformed.add(p)
                broke = True
                break
            if comp is not None:
                branch_evidence.append(comp)
        if not broke and len(set(branch_evidence)) >= 2:
            cross_component.add(p)
    invalid_forks = cross_component | malformed

    candidates = {}
    considered = set()
    for div, info in divs.items():
        m = match_nodes(pred, gt, max_distance, gt_subset=info['keep'])
        node_to_gt = {p: g for p, g in m.items()}
        children = info['children']
        if len(children) < 2:
            candidates[div] = set()
            continue
        parent_side = {div, *info['parents']}
        parent_ids = {p for p, g in node_to_gt.items() if g in parent_side}
        daughter_ids = [
            {p for p, g in node_to_gt.items() if g in {c, *gt.successors(c)}}
            for c in children
        ]
        if not parent_ids or sum(bool(x) for x in daughter_ids) < 2:
            candidates[div] = set()
            continue
        local_nodes = set(parent_ids)
        for p in list(parent_ids):
            local_nodes.update(pred.successors(p))
        local_forks = local_nodes & pred_div_nodes
        considered |= local_forks
        candidates[div] = {
            f for f in local_forks - invalid_forks
            if _is_strongly_connected(pred, f, parent_ids, daughter_ids)
        }

    pairing = _bipartite_max_matching(list(candidates), candidates)
    tp = sum(1 for d in candidates if d in pairing)
    fn = len(candidates) - tp
    fp_forks = (considered | evaluable_forks | invalid_forks) - set(pairing.values())
    return tp, fn, len(fp_forks)


# ---------- 6) ĐÁNH GIÁ 1 CẶP + TỔNG HỢP ----------
def node_recall(pred, gt, matched):
    matched_gt = set(matched.values())
    return len(matched_gt) / max(1, gt.num_nodes())


def evaluate_one(pred, gt):
    if pred.num_edges() == 0 or pred.num_nodes() == 0:
        edge_tp, edge_fp = 0, 0
        edge_fn = gt.num_edges()
        matched = {}
    else:
        matched = match_nodes(pred, gt)
        edge_tp, edge_fp, edge_fn = _evaluate_edge_counts(pred, gt, matched)
    dtp, dfn, dfp = evaluate_divisions(pred, gt)
    recall = node_recall(pred, gt, matched)
    n_pred = pred.num_nodes()

    ej_den = edge_tp + edge_fp + edge_fn
    ej = edge_tp / ej_den if ej_den > 0 else float('nan')
    dj_den = dtp + dfp + dfn
    divj = dtp / dj_den if dj_den > 0 else float('nan')
    n_total = gt.n_total
    if ej == ej and n_total == n_total and n_total > 0:
        ratio = (n_pred - n_total) / n_total
        adj = max(0.0, ej * (1 - ADJUSTMENT_ALPHA * ratio))
    else:
        adj = float('nan')
    return {'edge_tp': edge_tp, 'edge_fp': edge_fp, 'edge_fn': edge_fn,
            'division_tp': dtp, 'division_fp': dfp, 'division_fn': dfn,
            'num_pred_nodes': n_pred, 'node_recall': recall,
            'n_total': n_total, 'edge_jaccard': ej, 'adj_edge_jaccard': adj,
            'division_jaccard': divj,
            'score': adj + SCORE_DIVISION_WEIGHT * divj if dj_den > 0 else adj}


def summarise(rows):
    valid = [r for r in rows if r['edge_tp'] == r['edge_tp']]
    if not valid:
        return None
    tot = {k: sum(r[k] for r in valid) for k in
           ('edge_tp', 'edge_fp', 'edge_fn', 'division_tp', 'division_fp',
            'division_fn', 'num_pred_nodes')}

    def jac(tp, fp, fn):
        d = tp + fp + fn
        return tp / d if d > 0 else float('nan')

    adj_rows = [r for r in valid if r['adj_edge_jaccard'] == r['adj_edge_jaccard']]
    if adj_rows:
        tw = sum(r['edge_tp'] + r['edge_fp'] + r['edge_fn'] for r in adj_rows)
        adj = sum((r['edge_tp'] + r['edge_fp'] + r['edge_fn']) * r['adj_edge_jaccard']
                  for r in adj_rows) / tw
    else:
        adj = float('nan')

    div_total = tot['division_tp'] + tot['division_fp'] + tot['division_fn']
    divj = jac(tot['division_tp'], tot['division_fp'], tot['division_fn']) if div_total > 0 else float('nan')
    score = adj + SCORE_DIVISION_WEIGHT * divj if div_total > 0 else adj
    return {'n': len(valid),
            'edge_jaccard': jac(tot['edge_tp'], tot['edge_fp'], tot['edge_fn']),
            'adj_edge_jaccard': adj, 'division_jaccard': divj, 'score': score,
            **tot,
            'node_recall': sum(r['node_recall'] for r in valid) / len(valid)}


# ---------- 7) NẠP SUBMISSION → DICT GRAPH THEO DATASET ----------
def load_submission_graphs(csv_path):
    df = pd.read_csv(csv_path,
                     usecols=['dataset', 'row_type', 'node_id', 't', 'z', 'y', 'x',
                              'source_id', 'target_id'])
    graphs = {}
    for name, g in df.groupby('dataset', sort=True):
        nd = g[g['row_type'] == 'node']
        ed = g[g['row_type'] == 'edge']
        geff = {
            'ids': nd['node_id'].to_numpy(np.int64),
            't': nd['t'].to_numpy(np.float64),
            'z': nd['z'].to_numpy(np.float64),
            'y': nd['y'].to_numpy(np.float64),
            'x': nd['x'].to_numpy(np.float64),
            'edges': np.stack([ed['source_id'].to_numpy(np.int64),
                               ed['target_id'].to_numpy(np.int64)], axis=1)
            if len(ed) else np.zeros((0, 2), dtype=np.int64),
            'n_total': float('nan'),
        }
        graphs[name] = Graph(geff)
    return graphs
