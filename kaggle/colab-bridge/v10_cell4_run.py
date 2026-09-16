# -*- coding: utf-8 -*-
# [bridge-adapt] prelude: restore env tu /content/v10_env.json (do cell 2 ghi) truoc khi chay
import json as _json
import os as _os
try:
    with open("/content/v10_env.json") as _fh:
        _env = _json.load(_fh)
    _os.environ.update(_env)
    print("[bridge-adapt] env restored:", sorted(_env))
except FileNotFoundError:
    print("[bridge-adapt] KHONG CO v10_env.json — dung fallback trong cell")

# v10-lab-colab S4 KẾT QUẢ — bảng + bootstrap CI 95% paired + upload Kaggle
import json
import os
import time
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
from IPython.display import display

_v10_wrk_env = (os.environ.get("V10_WORKING_ROOT") or "").strip()
if _v10_wrk_env and Path(_v10_wrk_env).is_dir():
    WORKING_DIR = Path(_v10_wrk_env)
elif Path("/kaggle/working").exists():
    WORKING_DIR = Path("/kaggle/working")
else:
    WORKING_DIR = Path(".")
if not (WORKING_DIR / "v10_lab_report.json").is_file():  # restart runtime giữa chừng → dò nơi có report
    for _alt in (Path("/content/kaggle/working"), Path(".")):
        if (_alt / "v10_lab_report.json").is_file():
            print(f"[v10-lab-result] report tìm thấy tại {_alt} (khác root mặc định)")
            WORKING_DIR = _alt
            break
REPORT_PATH = WORKING_DIR / "v10_lab_report.json"
ROWS_PATH = WORKING_DIR / "v10_lab_rows.csv"
assert REPORT_PATH.is_file(), f"thiếu {REPORT_PATH} — cell lab chưa chạy xong?"
assert ROWS_PATH.is_file(), f"thiếu {ROWS_PATH} — cell lab chưa chạy xong?"
REPORT = json.loads(REPORT_PATH.read_text())
ROWS = pd.read_csv(ROWS_PATH)
REF_LABEL = REPORT["meta"].get("ref_label")
print(f"[v10-lab-result] ref = {REF_LABEL!r} · {len(REPORT['meta']['stems'])} stems · "
      f"cache_loaded={REPORT['meta'].get('cache_loaded')} · cuda={REPORT['meta'].get('cuda')}")

# --- bảng tổng hợp mỗi config -------------------------------------------------------------------
_tbl = []
for _label, _e in REPORT["configs"].items():
    if _e.get("skipped"):
        _tbl.append({"config": _label, "adjEJ": np.nan, "d_adjEJ_vs_ref": np.nan, "proxy": np.nan,
                     "div_tp": np.nan, "div_fp": np.nan, "div_fn": np.nan,
                     "veto_edges_dropped": np.nan, "rlf_edges_dropped": np.nan,
                     "note": "SKIP: " + str(_e.get("skip_reason"))})
    else:
        _s = _e["summary"]
        _tbl.append({"config": _label, "adjEJ": round(_s["adjusted_edge_jaccard"], 6),
                     "d_adjEJ_vs_ref": round(_e["deltas_vs_ref"].get("adjusted_edge_jaccard", 0.0), 6),
                     "proxy": round(_s["proxy_score"], 6), "div_tp": _s["div_tp"], "div_fp": _s["div_fp"],
                     "div_fn": _s["div_fn"], "veto_edges_dropped": _e["veto_edges_dropped"],
                     "rlf_edges_dropped": _e["rlf_edges_dropped"], "note": ""})
SUMMARY_TABLE = pd.DataFrame(_tbl)
print("[v10-lab-result] BẢNG TỔNG HỢP:")
display(SUMMARY_TABLE)

# --- bootstrap CI 95% paired theo stem (10_000 resample, seed cố định) ---------------------------
N_BOOT = 10_000
BOOT_SEED = 20260916
_piv_adj = ROWS.pivot_table(index="stem", columns="config", values="adjusted_edge_jaccard")
_piv_proxy = ROWS.pivot_table(index="stem", columns="config", values="proxy_score")
_boot_rows = []
if REF_LABEL in _piv_adj.columns:
    _rng = np.random.default_rng(BOOT_SEED)
    _n = len(_piv_adj)
    _idx = _rng.integers(0, _n, size=(N_BOOT, _n))
    for _col in _piv_adj.columns:
        if _col == REF_LABEL:
            continue
        _d_adj = (_piv_adj[_col] - _piv_adj[REF_LABEL]).to_numpy()
        _d_prx = (_piv_proxy[_col] - _piv_proxy[REF_LABEL]).to_numpy()
        _m_adj = _d_adj[_idx].mean(axis=1)
        _m_prx = _d_prx[_idx].mean(axis=1)
        _boot_rows.append({"config": _col, "mean_d_adjEJ": float(_d_adj.mean()),
                           "ci95_d_adjEJ_lo": float(np.percentile(_m_adj, 2.5)),
                           "ci95_d_adjEJ_hi": float(np.percentile(_m_adj, 97.5)),
                           "mean_d_proxy": float(_d_prx.mean()),
                           "ci95_d_proxy_lo": float(np.percentile(_m_prx, 2.5)),
                           "ci95_d_proxy_hi": float(np.percentile(_m_prx, 97.5)),
                           "ci95_d_adjEJ_duong": bool(np.percentile(_m_adj, 2.5) > 0),
                           "ci95_d_adjEJ_am": bool(np.percentile(_m_adj, 97.5) < 0)})
BOOTSTRAP_TABLE = pd.DataFrame(_boot_rows)
print(f"[v10-lab-result] BOOTSTRAP CI 95% paired per-stem ({N_BOOT:,} resample, seed {BOOT_SEED}):")
display(BOOTSTRAP_TABLE if not BOOTSTRAP_TABLE.empty else pd.DataFrame([{"note": "chỉ có 1 config (ref) — không có cặp nào"}]))

# --- upload cache + kết quả về Kaggle dataset vietnguyen130593/biohub-v10-lab-cache ----------
UPLOAD_RESULTS = True
if UPLOAD_RESULTS:
    if not (os.environ.get("KAGGLE_API_TOKEN") or "").startswith("KGAT_"):
        print("[v10-lab-upload] CẢNH BÁO: thiếu KAGGLE_API_TOKEN (restart runtime?) — chạy lại Cell 2 để set token rồi upload")
    try:
        import subprocess as _sp
        import sys as _sys

        def _v10_sp_kaggle(args):
            # [v10-lab-upload] python -m kaggle (>=2.2); nếu thiếu __main__ (2.0.x) → console script
            _r = _sp.run([_sys.executable, "-m", "kaggle", *args], capture_output=True, text=True)
            if _r.returncode != 0 and "No module named kaggle.__main__" in ((_r.stdout or "") + (_r.stderr or "")):
                _bin = shutil.which("kaggle")
                if _bin:
                    print(f"[v10-lab-upload] python -m kaggle thiếu __main__ — dùng console script {_bin}")
                    _r = _sp.run([_bin, *args], capture_output=True, text=True)
            return _r

        _up = Path("/content/v10_lab_upload")
        shutil.rmtree(_up, ignore_errors=True)
        _up.mkdir(parents=True, exist_ok=True)
        if (WORKING_DIR / "v10_lab_cache").is_dir():
            shutil.copytree(WORKING_DIR / "v10_lab_cache", _up / "v10_lab_cache")
        for _f in ("v10_lab_report.json", "v10_lab_rows.csv", "validator_results.csv"):
            if (WORKING_DIR / _f).is_file():
                shutil.copy2(WORKING_DIR / _f, _up / _f)
        (_up / "dataset-metadata.json").write_text(json.dumps({
            "title": "biohub-v10-lab-cache",
            "id": "vietnguyen130593/biohub-v10-lab-cache",
            "licenses": [{"name": "CC0-1.0"}],
        }, indent=2))
        _r = _v10_sp_kaggle(["datasets", "create", "-p", str(_up)])
        _blob = (_r.stdout or "") + (_r.stderr or "")
        if _r.returncode == 0:
            print("[v10-lab-upload] ĐÃ TẠO dataset vietnguyen130593/biohub-v10-lab-cache (create OK)")
        elif "409" in _blob or "already exists" in _blob.lower() or "conflict" in _blob.lower():
            _iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            _r2 = _v10_sp_kaggle(["datasets", "version",
                                  "-p", str(_up), "-m", f"lab run {_iso}", "-r", "skip"])
            print(f"[v10-lab-upload] version -m 'lab run {_iso}' exit={_r2.returncode}")
            if _r2.returncode != 0:
                print((_r2.stdout or "")[-1500:])
                print((_r2.stderr or "")[-1500:])
                raise RuntimeError("kaggle datasets version thất bại")
            print("[v10-lab-upload] ĐÃ VERSION dataset biohub-v10-lab-cache")
        else:
            print(_blob[-1500:])
            raise RuntimeError(f"kaggle datasets create thất bại (exit {_r.returncode})")
    except Exception as _e:
        print(f"[v10-lab-upload] UPLOAD LỖI ({type(_e).__name__}: {_e}) — KHÔNG crash notebook.")
        print("[v10-lab-upload] TẢI MANUAL: bấm thư mục Files bên trái → chuột phải thư mục")
        print("                    /content/v10_lab_upload → Download → gửi file zip cho agent chính.")
else:
    print("[v10-lab-upload] UPLOAD_RESULTS = False — bỏ qua upload")
print("[v10-lab-result] XONG.")
