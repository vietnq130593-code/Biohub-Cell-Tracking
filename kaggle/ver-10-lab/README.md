# V10-LAB — Bộ công cụ phòng thí nghiệm không-GPU

Định hướng chiến lược: xem `V10-LAB-PLAN.md`. Repo này chứa **công cụ chạy được** — đã qua
**87/87 unit test** (chạy lại bất cứ lúc nào: `python3 test-v10-lab.py`).

## Artifacts

| File | Vai trò |
|---|---|
| `cell-monolith-v10lab.py` | Monolith ver-9 + patch LAB: bỏ predict-test/submission/audit (LAB_MODE), bypass CUDA (LAB_NO_CUDA), load cache thay predict (LAB_VAL_CACHE_DIR), dump raw graphs + GT, grid replay + official scoring |
| `lab-grid-block.py` | Nguồn block `[v10-lab-grid]` (grid sweep, `v10_score_config`) — build script inject vào monolith |
| `build-v10-lab.py` | Dựng lại monolith + 2 notebook (offline, không đụng Kaggle): `python3 build-v10-lab.py` |
| `test-v10-lab.py` | 87 unit test: py_compile, env behavior, LAB_MODE guard (AST + hành vi), dump/load roundtrip, dispatch tight/veto/RLF, grid đầy đủ + skip logic, CUDA bypass, 2 notebook JSON + monolith nhúng nguyên văn, sha256 ver-9 gốc không đổi |
| `download/v10-lab-colab.ipynb` | ★ Notebook chạy trên **Google Colab T4** — do USER upload + Run all |
| `download/v10-lab-cpu.ipynb` | Notebook cho **Kaggle CPU kernel** (tôi push sau khi có cache dataset) — replay không veto |

## User chạy Colab — 5 bước

1. `colab.research.google.com` → File → Upload notebook → chọn `download/v10-lab-colab.ipynb`.
2. Runtime → Change runtime type → **T4 GPU** → Save.
3. Cell 2 (setup): dán token `KGAT_...` vào biến `KAGGLE_API_TOKEN` **hoặc** thêm Colab Secret
   tên `KAGGLE_API_TOKEN` (icon 🔑 bên trái) và để nguyên placeholder.
4. Runtime → **Run all**.
5. Chờ ~4-8h (giữ tab mở — Colab ngắt idle). Kết quả: bảng so sánh in ở cell 4 + cache + report
   **tự upload** về dataset `vietnguyen130593/biohub-v10-lab-cache` (tôi đọc từ đó).

Notebook tự: cài kaggle CLI → tải 9 dataset → tải file train của đúng 8 stems validator (phân trang
`competitions files` + 4 luồng) → chạy monolith LAB_MODE (predict 8 stems trên T4, DEADLINE 9h) →
dump cache → grid replay (ref/tight 4.5-7.0/rlf/veto1/veto2/veto2rlf) → bootstrap CI 95% paired →
upload (có fallback `datasets version` nếu dataset đã tồn tại; lỗi upload không crash).

## Env vars (bản LAB thêm vào)

| Env | Mặc định | Ý nghĩa |
|---|---|---|
| `BIOHUB_LAB_MODE` | 0 | 1 = bỏ predict-test + submission + audit cuối; chỉ validator + dump + grid |
| `BIOHUB_LAB_NO_CUDA` | 0 | 1 = bypass hard-require CUDA (kernel CPU) |
| `BIOHUB_VAL_CACHE_DIR` | '' | đường dẫn cache → load raw graphs thay vì predict |
| `BIOHUB_V10_GRID` | grid 9 config | JSON grid (sai cú pháp → fallback mặc định + warning) |
| `BIOHUB_V10_SKIP_VETO` | 0 | 1 = skip mọi config `needs_gpu` (CPU không chạy HOCT) |
| `BIOHUB_LAB_FORCE_DUMP` | 0 | 1 = cho phép đè cache cũ khi dump |

Grid mặc định (label · tight_override · veto_mode · apply_rlf):
`ref`, `tight_45/50/55/60/70` (global override), `rlf_only`, `veto1`, `veto2`, `veto2rlf`.
`ref` = tight hardcode 5.5/6.5 như v3-fast — **cổng kiểm chứng**: số ref phải tái lập
gate report cũ (adjEJ 0.9287 / proxy 0.9594 / div 4/1/8) thì cache mới được tin.

## Cơ chế kỹ thuật chính

- **tight override**: `v10_score_config` đè `globals()['MOTION_RELINK_TIGHT_UM']` + mọi giá trị
  `MOTION_RELINK_TIGHT_PER_PREFIX` (global override) rồi restore — `filter_output_graph` đọc
  module globals lúc gọi nên tác dụng tức thời (test T5 chứng minh bằng call-time mock).
- **veto mode dispatch**: đè `globals()['_HV_MODE']` 0/1/2 trước `_hv_veto_video`, restore sau;
  HOCT pair-cache theo (stem, node-set) nên veto1/veto2/veto2rlf tái dùng inference, không tốn GPU thêm.
- **RLF replay**: `ver9_rlf_edges` (graph-level, port nguyên văn block [ver9-rlf] của ver-9).
- **Cache dump**: `raw_graphs.json` + `gt_bundle.json` + `meta.json` trong `WORKING_DIR/v10_lab_cache`
  (`V10_LAB_ROWS_PATH`/`V10_LAB_REPORT_PATH` tôn trọng giá trị inject cho harness).
- Các block [ver9-rlf]/[ver9-gate] submission-level KHÔNG được inject vào bản LAB (static check).

## Giả định kỹ thuật & rủi ro

1. **Chưa chạy thử trên GPU/data thật** (sandbox không có GPU, không tải được data competition ~GB):
   mọi gì GPU-dependence (UNet predict, HOCT inference, path layout `/kaggle/input` trên Colab) đã
   được đối chiếu tĩnh với monolith ver-9 nhưng lần chạy đầu trên Colab là lần verify thật.
   Điểm cần để mắt: layout `/kaggle/input/<slug>/` do cell setup tự dựng (symlink thư mục tải về).
2. Thời lượng notebook ước 4-8h: download ~vài GB (8 stems + 9 dataset) 30-60' + predict 8 stems
   trên T4 đơn ~1-2h (Kaggle T4×2 từng ~1h cho phần này) + grid ~2-3h (veto dùng cache pair).
3. `v10_score_config` tái dùng `PP_RESULTS['base']` làm `validator_base_summary` trong meta report
   (cổng kiểm chứng ref); nếu predict cache-load thì giá trị này đến từ cache dump.
4. Ref config trong grid mặc định KHÔNG đè tight — đúng ngữ nghĩa v3-fast (5.5/6.5 hardcode từ env
   block [ver9] gốc, dòng ~96-97 monolith).

## Quy trình tái build sau khi sửa block

```bash
python3 build-v10-lab.py      # dựng lại monolith + 2 notebook (static check tự chạy)
python3 test-v10-lab.py       # 87/87 PASS mới được coi là xong
```

KHÔNG push gì lên Kaggle từ repo này — kernel CPU sẽ do agent chính đẩy bằng `kaggle/api/ktool.py`
sau khi dataset `biohub-v10-lab-cache` tồn tại (từ notebook Colab).
