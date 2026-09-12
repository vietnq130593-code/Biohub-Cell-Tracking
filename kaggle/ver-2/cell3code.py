# ver 2 · cell 3 — PIPELINE: ĐỌC ZARR → DETECTION (+TÁCH BLOB) → TRACKING → PHÂN BÀO XÁC NHẬN
# Dán đè Cell 3 của notebook Kaggle (toàn bộ thuật toán nằm ở đây).
# ============================================================

STRUCT26 = np.ones((3, 3, 3), dtype=bool)
T_START = time.time()


def _over_time_budget():
    return (time.time() - T_START) > TIME_LIMIT_HOURS * 3600.0


# ---------- 1) ĐỌC DỮ LIỆU (giữ nguyên ver 1) ----------
def read_zarr_meta(zarr_path):
    """Đọc shape/dtype/chunk grid từ zarr.json của mảng (như notebook gốc)."""
    with open(os.path.join(zarr_path, '0', 'zarr.json')) as f:
        meta = json.load(f)
    shape = tuple(int(v) for v in meta['shape'])            # (T, Z, Y, X)
    dtype = np.dtype(meta['data_type'])
    chunk = meta.get('chunk_grid', {}).get('configuration', {}).get('chunk_shape')
    if not chunk or len(chunk) != 4:
        chunk = [1, shape[1], shape[2], shape[3]]
    return shape, dtype, [int(c) for c in chunk]


def load_volume(zarr_path, t, shape, dtype, chunk):
    """Đọc khung t → (Z, Y, X). Chunk 0/0/0 là đường nhanh như notebook gốc;
    nếu khung được chia nhiều chunk thì lắp ghép đủ các chunk có mặt."""
    T, Z, Y, X = shape
    _, cZ, cY, cX = chunk
    croot = os.path.join(zarr_path, '0', 'c', str(t))
    if not os.path.isdir(croot):
        raise FileNotFoundError(f'không tìm thấy khung t={t}: {croot}')

    def read_chunk(cz, cy, cx):
        p = os.path.join(croot, str(cz), str(cy), str(cx))
        with open(p, 'rb') as f:
            return np.frombuffer(blosc2.decompress(f.read()), dtype=dtype)

    # Đường nhanh: metadata nói 1 chunk chứa cả khung
    if (cZ, cY, cX) == (Z, Y, X):
        try:
            arr = read_chunk(0, 0, 0)
            if arr.size == Z * Y * X:
                return arr.reshape(Z, Y, X)
        except Exception:
            pass  # rơi xuống đường đa chunk bên dưới

    vol = np.zeros((Z, Y, X), dtype=dtype)
    placed = 0
    for cz in range((Z + cZ - 1) // cZ):
        for cy in range((Y + cY - 1) // cY):
            for cx in range((X + cX - 1) // cX):
                p = os.path.join(croot, str(cz), str(cy), str(cx))
                if not os.path.isfile(p):
                    continue
                try:
                    arr = read_chunk(cz, cy, cx)
                except Exception:
                    continue
                vz = min(cZ, Z - cz * cZ)
                vy = min(cY, Y - cy * cY)
                vx = min(cX, X - cx * cX)
                if vz <= 0 or vy <= 0 or vx <= 0:
                    continue
                if arr.size >= cZ * cY * cX:      # chunk đầy (zarr v3 pad theo fill)
                    block = arr[:cZ * cY * cX].reshape(cZ, cY, cX)[:vz, :vy, :vx]
                elif arr.size >= vz * vy * vx:     # biến thể chunk gọn ở biên
                    block = arr[:vz * vy * vx].reshape(vz, vy, vx)
                else:
                    continue
                vol[cz * cZ:cz * cZ + vz, cy * cY:cy * cY + vy, cx * cX:cx * cX + vx] = block
                placed += 1
    if placed == 0:
        raise FileNotFoundError(f'khung t={t}: không đọc được chunk nào từ {croot}')
    return vol


# ---------- 2) DETECTION + TÁCH BLOB GỘP (mới: đỉnh cục bộ) ----------
def _com(coords, w):
    """Center-of-mass theo cường độ của tập voxel (z,y,x ds, float)."""
    s = w.sum()
    if s <= 0:
        return coords.mean(axis=0)
    return (coords * w[:, None]).sum(axis=0) / s


def detect_nodes(vol):
    """Trả về list dict: z, y, x (voxel gốc, int — đúng format đề bài) và
    zf, yf, xf (float — cho tracking), mass (tổng cường độ), nvox.

    ver 2: component lớn được TÁCH theo các đỉnh cục bộ (maximum_filter)
    — 2 tế bào bị ngưỡng gộp thành 1 blob sẽ tách thành 2 node nếu có
    ≥ 2 đỉnh sáng cách nhau ≥ MIN_PEAK_DIST_DS."""
    ds = vol[::DS_Z, ::DS_Y, ::DS_X].astype(np.float32)
    if ds.size == 0:
        return []
    smoothed = uniform_filter(ds, size=SMOOTH_SIZE)
    thr = np.percentile(smoothed, PERCENTILE)
    mask = smoothed > thr
    labeled, n = label(mask, structure=STRUCT26 if CONN26 else None)
    if n == 0:
        return []

    # đỉnh cục bộ (tính 1 lần cả khung): voxel = max trong lân cận PEAK_SIZE
    # và sáng hơn ngưỡng ít nhất PEAK_MIN_BRIGHT (chống đỉnh nhiễu)
    mf = maximum_filter(smoothed, size=PEAK_SIZE)
    is_peak = (smoothed == mf) & mask & (smoothed >= thr * PEAK_MIN_BRIGHT)

    lab_flat = labeled.ravel()
    counts = np.bincount(lab_flat, minlength=n + 1)
    wsums = np.bincount(lab_flat, weights=smoothed.ravel(), minlength=n + 1).astype(np.float64)
    coms = center_of_mass(smoothed, labeled, index=range(1, n + 1))

    # trọng số khoảng cách trong không gian ds: z gấp đôi (bước z dài gấp đôi)
    ZW = np.array([2.0, 1.0, 1.0])

    nodes = []
    for i in range(1, n + 1):
        nv = int(counts[i])
        if nv < MIN_NVOXELS or nv > MAX_NVOXELS:
            continue

        split_done = False
        if nv > SPLIT_MIN_NVOXELS:
            comp = np.argwhere(labeled == i)                # (N, 3) z,y,x
            pk_mask = is_peak[comp[:, 0], comp[:, 1], comp[:, 2]]
            peaks = comp[pk_mask]
            if len(peaks) >= 2:
                # giữ các đỉnh sáng nhất, bỏ đỉnh quá gần một đỉnh đã giữ
                vals = smoothed[peaks[:, 0], peaks[:, 1], peaks[:, 2]]
                order = np.argsort(-vals)
                kept = []
                for idx in order:
                    p = peaks[idx].astype(np.float64)
                    too_close = False
                    for q in kept:
                        if np.linalg.norm((p - q) * ZW) < MIN_PEAK_DIST_DS:
                            too_close = True
                            break
                    if not too_close:
                        kept.append(p)
                if len(kept) >= 2:
                    # gán mỗi voxel component → đỉnh gần nhất; CoM riêng từng vùng
                    P = np.array(kept)
                    D = cdist(comp.astype(np.float64) * ZW, P * ZW)
                    assign = D.argmin(axis=1)
                    w_all = smoothed[comp[:, 0], comp[:, 1], comp[:, 2]].astype(np.float64)
                    for k in range(len(kept)):
                        sel = assign == k
                        sub = comp[sel]
                        w = w_all[sel]
                        if sub.shape[0] < MIN_NVOXELS:
                            continue
                        cz, cy, cx = _com(sub.astype(np.float64), w)
                        nodes.append({
                            'z': int(round(cz * DS_Z)), 'y': int(round(cy * DS_Y)),
                            'x': int(round(cx * DS_X)),
                            'zf': cz * DS_Z, 'yf': cy * DS_Y, 'xf': cx * DS_X,
                            'mass': float(w.sum()), 'nvox': int(sub.shape[0]),
                        })
                    split_done = True
        if split_done:
            continue

        cz, cy, cx = coms[i - 1]
        nodes.append({
            'z': int(round(cz * DS_Z)), 'y': int(round(cy * DS_Y)), 'x': int(round(cx * DS_X)),
            'zf': cz * DS_Z, 'yf': cy * DS_Y, 'xf': cx * DS_X,
            'mass': float(wsums[i]), 'nvox': nv,
        })
    return nodes


# ---------- 3) TRACKER (ver 2: phân bào xác nhận + skip 2 khung) ----------
class Tracker:
    """Hungarian + motion model + tách blob + PHÂN BÀO XÁC NHẬN ĐỘNG HỌC.

    Mỗi khung gồm 5 bước:
      (a) Hungarian giữa node khung trước (đặt tại vị trí DỰ ĐOÁN) và node
          khung hiện tại, gate thích ứng
      (b) phân bào ỨNG VIÊN: mẹ vừa match nhận thêm con thứ 2 — cạnh
          divergence ĐƯỢC HOÃN, chờ xác nhận động học ở bước (e)
      (c) frame-skip: nối lại track mất ≤ 2 khung + nội suy node giữa
      (d) dọn dẹp: node chưa ai nhận thành track mới, track mất vào pending
      (e) xác nhận phân bào: ứng viên phải sống đủ DIV_CONFIRM_FRAMES khung
          và khoảng cách 2 con tăng ≥ DIV_SEP_GROWTH lần so với lúc "sinh"
          → mới ghi cạnh + division.
          Merge-split giả (blob gộp–tách) bị từ chối vì 2 "con" ở xa nhau
          ngay từ đầu và khoảng cách gần như đứng yên; phân bào thật thì
          2 con sát nhau lúc sinh rồi tách dần.

    Lưu ý metric: node có ≥ 2 cạnh ra là predicted fork (phân bào). Fork giả
    = division FP, nên mỗi fork phải xứng đáng. Cạnh bị hoãn vẫn là cạnh
    liền khung (mẹ t-1 → con t) nên hợp lệ khi được xác nhận.
    """

    def __init__(self):
        self.active = {}        # nid → dict(pos µm, vel µm/khung, mass)
        self.pending = {}       # nid → dict(pos, vel, mass, missed)
        self.recent_steps = []  # bước đi (µm) của các match gần đây
        self.div_pending = []   # ứng viên phân bào chờ xác nhận
        self.n_div_confirmed = 0
        self.n_div_rejected = 0

    def _gate(self):
        if len(self.recent_steps) < 5:
            return BASE_GATE_UM
        med = float(np.median(self.recent_steps))
        return float(np.clip(GATE_MEDIAN_MULT * med, GATE_MIN_UM, GATE_MAX_UM))

    def step(self, dets, t):
        """Xử lý khung t. Trả về (nodes, edges, divisions, interp_nodes)."""
        nodes = [(next(NODE_ID), d) for d in dets]
        ids = [nid for nid, _ in nodes]
        pos = np.array(
            [[d['zf'], d['yf'], d['xf']] for _, d in nodes], dtype=np.float64,
        ).reshape(-1, 3) * SCALE
        mass = [float(d['mass']) for _, d in nodes]

        edges, divisions, interp_nodes = [], [], []
        matched_curr = {}   # curr_idx → prev nid
        succ = {}           # prev nid → nid khung này (nối mạch cho bước (e))

        # ---- (a) matching chính: Hungarian trên vị trí DỰ ĐOÁN ----
        prev_ids = list(self.active.keys())
        if prev_ids and ids:
            pred = np.array(
                [self.active[p]['pos'] + self.active[p]['vel'] for p in prev_ids],
            )
            D = np.linalg.norm(pred[:, None, :] - pos[None, :, :], axis=2)
            gate = self._gate()
            cost = D
            if BRIGHT_WEIGHT > 0:
                mp = np.maximum(
                    np.array([self.active[p]['mass'] for p in prev_ids])[:, None], 1e-9)
                mc = np.maximum(np.array(mass)[None, :], 1e-9)
                cost = D * (1.0 + BRIGHT_WEIGHT * np.abs(np.log(mc / mp)))
            cost = np.where(D <= gate, cost, BIG)
            ri, ci = linear_sum_assignment(cost)
            for r, c in zip(ri, ci):
                if D[r, c] > gate:
                    continue
                p = prev_ids[r]
                matched_curr[c] = p
                succ[p] = ids[c]
                edges.append((p, ids[c]))
                self.recent_steps.append(
                    float(np.linalg.norm(pos[c] - self.active[p]['pos'])))
            if len(self.recent_steps) > 200:
                del self.recent_steps[:100]

        new_active = {}
        for c, p in matched_curr.items():
            a = self.active[p]
            disp = pos[c] - a['pos']
            vel = VEL_SMOOTH * disp + (1.0 - VEL_SMOOTH) * a['vel']
            new_active[ids[c]] = {'pos': pos[c], 'vel': vel, 'mass': mass[c]}

        # ---- (b) phân bào ỨNG VIÊN (cạnh divergence hoãn chờ bước (e)) ----
        unmatched = [j for j in range(len(ids)) if j not in matched_curr]
        if DIVISION_ENABLED and matched_curr:
            cands = []
            for c, p in matched_curr.items():
                P, mP = self.active[p]['pos'], self.active[p]['mass']
                C1, mC1 = pos[c], mass[c]
                for j in unmatched:
                    B2, mB2 = pos[j], mass[j]
                    dP = float(np.linalg.norm(P - B2))
                    if dP > DIV_PARENT_GATE_UM:
                        continue
                    dS = float(np.linalg.norm(C1 - B2))
                    if dS > DIV_SIBLING_GATE_UM:
                        continue
                    if mP > 0:
                        if mB2 < DIV_MIN_CHILD_FRAC * mP:
                            continue
                        if DIV_BRIGHTNESS_CHECK:
                            ratio = (mC1 + mB2) / mP
                            if not (DIV_BRIGHTNESS_RATIO[0] <= ratio <= DIV_BRIGHTNESS_RATIO[1]):
                                continue
                    cands.append((dP, p, c, j))
            cands.sort()
            used_p, used_j = set(), set()
            for dP, p, c, j in cands:
                if p in used_p or j in used_j:
                    continue
                used_p.add(p)
                used_j.add(j)
                P = self.active[p]['pos']
                # con thứ 2 khởi động như track mới; cạnh p→ids[j] HOÃN,
                # chỉ ghi nếu được xác nhận ở bước (e) của các khung sau
                new_active[ids[j]] = {'pos': pos[j], 'vel': pos[j] - P, 'mass': mass[j]}
                self.div_pending.append({
                    't': t, 'mother': p,
                    'c1': ids[c], 'c2': ids[j], 'c2_start': ids[j],
                    'd0': float(np.linalg.norm(pos[c] - pos[j])), 'age': 0,
                })
            unmatched = [j for j in unmatched if j not in used_j]

        # ---- (c) frame-skip: nối lại track mất ≤ MAX_SKIP_FRAMES khung ----
        if ALLOW_FRAME_SKIP and self.pending and unmatched:
            pend_ids = list(self.pending.keys())
            pred = np.array([
                self.pending[q]['pos'] + self.pending[q]['vel'] * (self.pending[q]['missed'] + 1)
                for q in pend_ids
            ])
            C = pos[np.array(unmatched, dtype=int)]
            D = np.linalg.norm(pred[:, None, :] - C[None, :, :], axis=2)
            cost = np.where(D <= SKIP_GATE_UM, D, BIG)
            ri, ci = linear_sum_assignment(cost)
            for r, c in zip(ri, ci):
                if D[r, c] > SKIP_GATE_UM:
                    continue
                q, j = pend_ids[r], unmatched[c]
                Q = self.pending[q]
                gap = Q['missed'] + 1
                if INTERPOLATE_MISSED_FRAMES and gap >= 2:
                    # Chèn node nội suy tại các khung bị mất rồi nối các cạnh
                    # LIỀN KHUNG — node nằm giữa 2 node đã khớp nên khả năng
                    # khớp GT ≤ 7 µm cao (cạnh nhảy t→t+2 bị metric bỏ hẳn).
                    chain = q
                    for k in range(1, gap):
                        pm = Q['pos'] + (pos[j] - Q['pos']) * (k / gap)  # µm
                        vf = pm / SCALE
                        mid = next(NODE_ID)
                        interp_nodes.append((mid, t - gap + k, {
                            'z': int(round(vf[0])), 'y': int(round(vf[1])), 'x': int(round(vf[2])),
                            'zf': float(vf[0]), 'yf': float(vf[1]), 'xf': float(vf[2]),
                            'mass': (Q['mass'] + mass[j]) / 2.0, 'nvox': 0,
                        }))
                        edges.append((chain, mid))
                        chain = mid
                    edges.append((chain, ids[j]))
                new_active[ids[j]] = {
                    'pos': pos[j],
                    'vel': (pos[j] - Q['pos']) / gap,
                    'mass': mass[j],
                }
                succ[q] = ids[j]
                self.pending.pop(q, None)
            unmatched = [j for j in unmatched if ids[j] not in new_active]

        # ---- (d) dọn dẹp ----
        for q in list(self.pending.keys()):
            self.pending[q]['missed'] += 1
            if self.pending[q]['missed'] > MAX_SKIP_FRAMES:
                del self.pending[q]

        matched_prev = set(matched_curr.values())
        for p in prev_ids:
            if p in matched_prev:
                continue
            a = self.active[p]
            self.pending[p] = {'pos': a['pos'], 'vel': a['vel'],
                               'mass': a['mass'], 'missed': 1}

        for j in unmatched:
            if ids[j] not in new_active:
                new_active[ids[j]] = {'pos': pos[j], 'vel': np.zeros(3), 'mass': mass[j]}

        # ---- (e) xác nhận phân bào: đủ tuổi + khoảng cách 2 con tăng ----
        still_pending = []
        for cand in self.div_pending:
            if cand['age'] == 0:
                # candidate vừa tạo ở bước (b) của CHÍNH step này — c1/c2 là
                # node của khung hiện tại, chưa bao giờ là "prev" nên chưa
                # có trong succ; chỉ tăng tuổi và chờ step sau
                cand['age'] = 1
                still_pending.append(cand)
                continue
            c1 = succ.get(cand['c1'])
            c2 = succ.get(cand['c2'])
            if c1 is None or c2 is None:
                self.n_div_rejected += 1          # một "con" biến mất → bỏ
                continue
            cand['c1'], cand['c2'] = c1, c2
            cand['age'] += 1
            if cand['age'] > DIV_CONFIRM_FRAMES:
                a1, a2 = new_active.get(c1), new_active.get(c2)
                if a1 is not None and a2 is not None:
                    d_now = float(np.linalg.norm(a1['pos'] - a2['pos']))
                    if d_now >= DIV_SEP_GROWTH * cand['d0']:
                        # XÁC NHẬN: ghi cạnh hoãn (mẹ t-1 → con thứ 2 t) —
                        # vẫn là cạnh liền khung vì mẹ/con1/con2 sinh cùng lượt
                        edges.append((cand['mother'], cand['c2_start']))
                        divisions.append((cand['mother'], cand['c2_start']))
                        self.n_div_confirmed += 1
                        continue
                self.n_div_rejected += 1          # không tách ra → merge-split giả
                continue
            still_pending.append(cand)
        self.div_pending = still_pending

        self.active = new_active
        return nodes, edges, divisions, interp_nodes


# ---------- 4) CHẠY TOÀN BỘ TEST SET + CHẨN ĐOÁN ----------
def diagnose(rows):
    """Thống kê "sức khoẻ" submission — phát hiện sớm lỗi cấu trúc.
    Trả về chuỗi log để in cùng kết quả dataset."""
    nd = [r for r in rows if r['row_type'] == 'node']
    ed = [r for r in rows if r['row_type'] == 'edge']
    if not nd:
        return 'không có node'
    node_ids = {r['node_id'] for r in nd}
    has_in = {r['target_id'] for r in ed if r['target_id'] in node_ids}
    has_out = {r['source_id'] for r in ed if r['source_id'] in node_ids}
    n_no_in = sum(1 for r in nd if r['node_id'] not in has_in)
    forks = {}
    for r in ed:
        if r['source_id'] in node_ids:
            forks[r['source_id']] = forks.get(r['source_id'], 0) + 1
    n_div = sum(1 for v in forks.values() if v >= 2)
    # track = thành phần liên thông yếu
    parent = {i: i for i in node_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for r in ed:
        s, d = r['source_id'], r['target_id']
        if s in parent and d in parent:
            parent[find(s)] = find(d)
    from collections import Counter
    sizes = Counter(find(i) for i in node_ids)
    med_track = float(np.median(list(sizes.values()))) if sizes else 0.0
    t_lo = min(r['t'] for r in nd)
    t_hi = max(r['t'] for r in nd)
    frames = t_hi - t_lo + 1
    return (f"{len(nd)} node · {len(ed)} cạnh · {n_div} phân bào · "
            f"{n_no_in}/{len(nd)} node không cạnh vào ({100.0 * n_no_in / len(nd):.0f}%) · "
            f"{len(sizes)} track · trung vị {med_track:.0f} node/track · "
            f"{len(nd) / max(1, frames):.1f} node/khung · "
            f"xác nhận/từ chối phân bào: {TRK.n_div_confirmed}/{TRK.n_div_rejected}")


if not os.path.isdir(TEST_DIR):
    hint = os.listdir('/kaggle/input') if os.path.isdir('/kaggle/input') else 'không có /kaggle/input'
    raise FileNotFoundError(f'Không thấy {TEST_DIR} — hãy Add Input competition. /kaggle/input: {hint}')

test_folder_names = sorted(
    d.replace('.zarr', '') for d in os.listdir(TEST_DIR) if d.endswith('.zarr')
)
if not test_folder_names:
    raise RuntimeError(f'Không tìm thấy thư mục .zarr nào trong {TEST_DIR}: {os.listdir(TEST_DIR)[:10]}')
print(f'{len(test_folder_names)} dataset: {test_folder_names}')

all_rows = []
summary = []
STOPPED_EARLY = False

for folder_name in test_folder_names:
    zarr_path = os.path.join(TEST_DIR, folder_name + '.zarr')
    shape, dtype, chunk = read_zarr_meta(zarr_path)
    n_t = shape[0]

    TRK = Tracker()
    ds_rows = []
    n_nodes = n_edges = n_div = 0
    t0 = time.time()

    for t in range(n_t):
        if _over_time_budget():
            print(f'!! Gần hết ngân sách {TIME_LIMIT_HOURS}h — dừng tại {folder_name} t={t}')
            STOPPED_EARLY = True
            break
        try:
            vol = load_volume(zarr_path, t, shape, dtype, chunk)
        except (FileNotFoundError, ValueError) as e:
            print(f'  [{folder_name}] lỗi đọc khung {t}: {e} — bỏ qua')
            continue
        dets = detect_nodes(vol)
        nodes, edges, divisions, interp_nodes = TRK.step(dets, t)

        for nid, d in nodes:
            ds_rows.append({
                'dataset': folder_name, 'row_type': 'node', 'node_id': nid,
                't': t, 'z': d['z'], 'y': d['y'], 'x': d['x'],
                'source_id': -1, 'target_id': -1,
            })
        for nid, tk, d in interp_nodes:
            ds_rows.append({
                'dataset': folder_name, 'row_type': 'node', 'node_id': nid,
                't': tk, 'z': d['z'], 'y': d['y'], 'x': d['x'],
                'source_id': -1, 'target_id': -1,
            })
        for src, dst in edges:
            ds_rows.append({
                'dataset': folder_name, 'row_type': 'edge', 'node_id': -1,
                't': -1, 'z': -1, 'y': -1, 'x': -1,
                'source_id': src, 'target_id': dst,
            })
        n_nodes += len(nodes) + len(interp_nodes)
        n_edges += len(edges)
        n_div += len(divisions)

        if (t + 1) % 50 == 0 or t == n_t - 1:
            print(f'  [{folder_name}] {t + 1}/{n_t} khung · {n_nodes} node · '
                  f'{n_edges} cạnh · {n_div} phân bào · {time.time() - t0:.0f}s', flush=True)

    all_rows.extend(ds_rows)
    if DIAGNOSE:
        print(f'  [chẩn đoán {folder_name}] {diagnose(ds_rows)}', flush=True)
    summary.append((folder_name, n_nodes, n_edges, n_div))
    print(f'== {folder_name}: {n_nodes} nodes · {n_edges} edges · {n_div} phân bào '
          f'({time.time() - t0:.0f}s)', flush=True)
    if STOPPED_EARLY:
        break

if STOPPED_EARLY:
    print('CẢNH BÁO: dừng sớm do ngân sách thời gian — kết quả chỉ một phần!')

# ---------- 5) SOÁT BẰNG MẮT (tuỳ chọn) ----------
if RUN_PREVIEW and test_folder_names:
    import matplotlib.pyplot as plt

    zarr_path = os.path.join(TEST_DIR, test_folder_names[0] + '.zarr')
    shape, dtype, chunk = read_zarr_meta(zarr_path)
    vol = load_volume(zarr_path, 0, shape, dtype, chunk)
    dets = detect_nodes(vol)

    zc = shape[1] // 2
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax in axes:
        ax.imshow(vol[zc], cmap='gray')
        ax.set_xticks([])
        ax.set_yticks([])
    axes[0].set_title(f'{test_folder_names[0]} · t=0 · lát z={zc}')
    for d in dets:
        axes[1].plot(d['x'], d['y'], 'o', mfc='none', mec='lime', ms=9, mew=1.2)
    axes[1].set_title(f'phát hiện: {len(dets)} node (ver 2: P{PERCENTILE:g} + tách blob)')
    plt.tight_layout()
    plt.show()
