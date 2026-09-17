# -*- coding: utf-8 -*-
# v10-lab TRIAL kernel — chạy trên TÀI KHOẢN THỬ NGHIỆM (T4x2, internet ON, 12h)
#
# Khác biệt so với kernel chính (vietnguyen130593/v10-lab-gpu-t4):
#   + DATA: competition gắn TRỰC TIẾP vào kernel (competition_sources) → pre-stage
#     8 stems từ mount local (~54s, 0 API call) — không phụ thuộc dataset
#     stems8 riêng của tài khoản chính.
#   + TOKEN: token của chính tài khoản này (watchdog đẩy checkpoint lên 2 dataset
#     PRIVATE dưới namespace tài khoản này — không đụng tài khoản chính).
#   + RUNNERS: bản copy của biohub-v10-lab-runners đã được patch slug + token
#     cho tài khoản này.
#
# Luồng: pre-stage stems → cell 2 (verify + 9 dataset) → repair → watchdog → cell 3.

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

B_USER = "{{B_USER}}"
B_TOKEN = "{{B_TOKEN}}"
COMP = "biohub-cell-tracking-during-development"
STEMS = ["44b6_12dfb391", "44b6_267148e4", "44b6_2a2eff9f", "44b6_341df25f",
         "6bba_062c8d37", "6bba_07e24132", "6bba_085bf656", "6bba_09961292"]

print("[trial] python", sys.version, flush=True)
r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True)
print("[trial] GPU:", (r.stdout or r.stderr).strip()[:300], flush=True)

RUN = Path("/kaggle/working")
os.makedirs("/content", exist_ok=True)  # cell 2 / watchdog hardcode vài path /content
RUN.mkdir(parents=True, exist_ok=True)
os.environ["KAGGLE_API_TOKEN"] = B_TOKEN

# --- dò thư mục runners (bản copy dưới tài khoản này; layout Kaggle mới/cũ) ---
_CANDS = [
    Path("/kaggle/input/biohub-v10-lab-runners"),
    Path(f"/kaggle/input/datasets/{B_USER}/biohub-v10-lab-runners"),
    Path("/kaggle/input/datasets/biohub-v10-lab-runners"),
    Path("/kaggle/input/v10-lab-runners"),
]
SRC = next((c for c in _CANDS if (c / "v10_cell2_run.py").is_file()), None)
if SRC is None:
    for hit in Path("/kaggle/input").rglob("v10_cell2_run.py"):
        SRC = hit.parent
        break
if SRC is None:
    raise SystemExit("[trial] KHÔNG TÌM THẤY runners (dataset %s/biohub-v10-lab-runners chưa attach/ready?)" % B_USER)
print("[trial] runners:", SRC, flush=True)

for f in ["v10_cell2_run.py", "v10_cell3_run.py", "repair_deps.py", "v10_ckpt_watchdog.py"]:
    shutil.copy(SRC / f, RUN / f)

# --- env roots ---
IN_ROOT = RUN / "v10input"
os.environ["V10_INPUT_ROOT"] = str(IN_ROOT)
os.environ["V10_WORKING_ROOT"] = str(RUN)
os.environ["V10_CKPT_CELL3_LOG"] = str(RUN / "v10_cell3.log")
os.environ["V10_CKPT_CELL2_LOG"] = str(RUN / "v10_cell2.log")
print("[trial] V10_INPUT_ROOT =", os.environ["V10_INPUT_ROOT"], flush=True)

# --- pre-stage 8 stems (.zarr + .geff) từ competition mount — layout TRAIN_DEST của cell 2 ---
_mount = next((m for m in [Path("/kaggle/input/competitions") / COMP, Path("/kaggle/input") / COMP]
               if (m / "train").is_dir()), None)
TRAIN_DST = IN_ROOT / COMP / "train"
if _mount is None:
    print("[trial] CẢNH BÁO: không thấy competition mount — cell 2 sẽ tự tải (nếp B/C)", flush=True)
else:
    _t0 = time.time()
    _n = 0
    for s in STEMS:
        for suf in (".zarr", ".geff"):
            src = _mount / "train" / (s + suf)
            dst = TRAIN_DST / (s + suf)
            if src.exists() and not dst.exists():
                TRAIN_DST.mkdir(parents=True, exist_ok=True)
                subprocess.run(["cp", "-r", "-n", str(src), str(dst)], check=True)
                _n += 1
    print("[trial] pre-stage %d mục từ competition mount (%.0fs)" % (_n, time.time() - _t0), flush=True)

PY = sys.executable


def stage(name, script, log_name, timeout_s):
    log = RUN / log_name
    print("[trial] STAGE %s START → %s (timeout %ds)" % (name, log, timeout_s), flush=True)
    t0 = time.time()
    with open(log, "a") as lf:
        try:
            r = subprocess.run([PY, "-u", str(RUN / script)], stdout=lf, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, timeout=timeout_s, cwd=str(RUN))
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = -9
    print("[trial] STAGE %s END rc=%d (%.0fs)" % (name, rc, time.time() - t0), flush=True)
    return rc


# ---- 1) cell 2: data (thấy stems đã pre-stage → verify nhanh, không tải lại) ----
if Path("/content/v10_cell2.done").exists():
    print("[trial] cell 2 marker đã có — SKIP", flush=True)
    rc2 = 0
else:
    rc2 = stage("cell2", "v10_cell2_run.py", "v10_cell2.log", 5400)
if rc2 != 0 and not Path("/content/v10_cell2.done").exists():
    raise SystemExit("[trial] cell 2 rc=%d VÀ không có marker — DỪNG (không chạy cell 3 thiếu data)" % rc2)

# ---- 2) repair deps (py3.12 image: hầu hết no-op) ----
stage("repair", "repair_deps.py", "repair_run.log", 2400)

# ---- 3) watchdog: background, đẩy checkpoint lên dataset private CỦA TÀI KHOẢN NÀY ----
if subprocess.run(["pgrep", "-f", "v10_ckpt_watchdog.py"], capture_output=True).returncode != 0:
    with open(RUN / "v10_ckpt_stdout.log", "a") as lf:
        subprocess.Popen([PY, "-u", str(RUN / "v10_ckpt_watchdog.py")], stdout=lf,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True, cwd="/content")
    print("[trial] watchdog launched", flush=True)
else:
    print("[trial] watchdog đang chạy — skip", flush=True)

# ---- 4) cell 3: validator + grid + dump cache ----
rc3 = stage("cell3", "v10_cell3_run.py", "v10_cell3.log", 39600)

# ---- 5) tổng kết ----
print("[trial] ============ TỔNG KẾT TRIAL ============", flush=True)
for f in ["v10_lab_rows.csv", "v10_lab_report.json", "validator_results.csv",
          "ppsweep_results.csv", "v10_lab_cache/raw_graphs.json", "v10_lab_cache/gt_bundle.json"]:
    p = RUN / f
    sz = p.stat().st_size if p.exists() else 0
    print("  %-42s %-7s %s bytes" % (f, "OK" if p.exists() else "MISSING", format(sz, ",")), flush=True)
try:
    import json
    rep = json.loads((RUN / "v10_lab_report.json").read_text())
    for label, c in sorted(rep.get("configs", {}).items()):
        if c.get("skipped"):
            print("  [grid] %-10s SKIPPED (%s)" % (label, c.get("skip_reason")), flush=True)
        elif c.get("summary"):
            s = c["summary"]
            d = c.get("deltas_vs_ref", {}).get("adjusted_edge_jaccard", 0.0)
            print("  [grid] %-10s adjEJ=%.6f d=%+.6f proxy=%.6f" % (label, s["adjusted_edge_jaccard"], d, s["proxy_score"]), flush=True)
except Exception as e:
    print("  (report chưa sẵn:", e, ")", flush=True)

print("[trial] chờ watchdog đẩy nốt checkpoint (180s)...", flush=True)
time.sleep(180)
print("[trial] KERNEL_DONE rc3=%d" % rc3, flush=True)
