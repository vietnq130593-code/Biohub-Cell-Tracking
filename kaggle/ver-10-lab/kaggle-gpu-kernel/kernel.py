# -*- coding: utf-8 -*-
# v10-lab-gpu-t4 — KERNEL Kaggle GPU (T4/P100, internet ON, 12h)
#
# Chạy toàn bộ v10-lab trên Kaggle GPU (quota Colab T4 chưa hồi, Kaggle GPU ĐÃ HỒI — probe OK):
#   1) cell 2   (v10_cell2_run.py)   — data: stems8 dataset 1-call + 9 deps (~5-10')
#   2) repair  (repair_deps.py)      — py3.12 image: gần như no-op, chạy cho chắc
#   3) watchdog (v10_ckpt_watchdog)  — background: đẩy checkpoint/raw graphs lên 2 dataset private
#   4) cell 3   (v10_cell3_run.py)    — validator predict 8 stems (GPU ~1-2h) + grid 9 config (~2-3h)
#                                      + dump raw_graphs cache → /kaggle/working/v10_lab_cache
#
# Input layout: /kaggle/input READ-ONLY trên kernel → V10_INPUT_ROOT=/kaggle/working/v10input
# (cell 2 v5 đã patch tôn trọng env override). Mọi artefact trong /kaggle/working được lưu
# thành kernel output khi hoàn tất + watchdog đẩy lên dataset trong lúc chạy (chống chết giữa chừng).

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

print("[kernel] python", sys.version, flush=True)
r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True)
print("[kernel] GPU:", (r.stdout or r.stderr).strip()[:300], flush=True)

# --- thư mục ---
RUN = Path("/kaggle/working")
os.makedirs("/content", exist_ok=True)  # cell 2 / watchdog hardcode vài path /content
RUN.mkdir(parents=True, exist_ok=True)

# --- dò thư mục runners (dataset gắn kèm; layout Kaggle mới/cũ) ---
_CANDS = [
    Path("/kaggle/input/biohub-v10-lab-runners"),
    Path("/kaggle/input/datasets/vietnguyen130593/biohub-v10-lab-runners"),
    Path("/kaggle/input/datasets/biohub-v10-lab-runners"),
    Path("/kaggle/input/v10-lab-runners"),
]
SRC = next((c for c in _CANDS if (c / "v10_cell2_run.py").is_file()), None)
if SRC is None:  # fallback: tìm sâu
    for hit in Path("/kaggle/input").rglob("v10_cell2_run.py"):
        SRC = hit.parent
        break
if SRC is None:
    raise SystemExit("[kernel] KHÔNG TÌM THẤY runners (dataset biohub-v10-lab-runners chưa attach/ready)")
print("[kernel] runners:", SRC, flush=True)

for f in ["v10_cell2_run.py", "v10_cell3_run.py", "repair_deps.py", "v10_ckpt_watchdog.py"]:
    shutil.copy(SRC / f, RUN / f)

# --- env roots (kernel: /kaggle/input read-only → input tree trong working, 20GB đủ) ---
os.environ["V10_INPUT_ROOT"] = str(RUN / "v10input")
os.environ["V10_WORKING_ROOT"] = str(RUN)
os.environ["KAGGLE_API_TOKEN"] = "KGAT_14164511bf6b0ba6b14ed9050ffdea66"
os.environ["V10_CKPT_CELL3_LOG"] = str(RUN / "v10_cell3.log")
os.environ["V10_CKPT_CELL2_LOG"] = str(RUN / "v10_cell2.log")
print("[kernel] V10_INPUT_ROOT =", os.environ["V10_INPUT_ROOT"], flush=True)
print("[kernel] V10_WORKING_ROOT =", os.environ["V10_WORKING_ROOT"], flush=True)

PY = sys.executable


def stage(name, script, log_name, timeout_s):
    log = RUN / log_name
    print(f"[kernel] STAGE {name} START → {log} (timeout {timeout_s}s)", flush=True)
    t0 = time.time()
    with open(log, "a") as lf:
        try:
            r = subprocess.run([PY, "-u", str(RUN / script)], stdout=lf, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, timeout=timeout_s, cwd=str(RUN))
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = -9
    print(f"[kernel] STAGE {name} END rc={rc} ({time.time() - t0:.0f}s)", flush=True)
    return rc


# ---- 1) cell 2: data ----
if Path("/content/v10_cell2.done").exists():
    print("[kernel] cell 2 marker đã có — SKIP", flush=True)
    rc2 = 0
else:
    rc2 = stage("cell2", "v10_cell2_run.py", "v10_cell2.log", 5400)
if rc2 != 0 and not Path("/content/v10_cell2.done").exists():
    raise SystemExit(f"[kernel] cell 2 rc={rc2} VÀ không có marker — DỪNG (không chạy cell 3 thiếu data)")

# ---- 2) repair deps (py3.12: hầu hết no-op) ----
stage("repair", "repair_deps.py", "repair_run.log", 2400)

# ---- 3) watchdog: background, đẩy checkpoint lên dataset private ----
if subprocess.run(["pgrep", "-f", "v10_ckpt_watchdog.py"], capture_output=True).returncode != 0:
    with open(RUN / "v10_ckpt_stdout.log", "a") as lf:
        subprocess.Popen([PY, "-u", str(RUN / "v10_ckpt_watchdog.py")], stdout=lf,
                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True, cwd="/content")
    print("[kernel] watchdog launched", flush=True)
else:
    print("[kernel] watchdog đang chạy — skip", flush=True)

# ---- 4) cell 3: validator + grid + dump cache ----
rc3 = stage("cell3", "v10_cell3_run.py", "v10_cell3.log", 39600)

# ---- 5) tổng kết ----
print("[kernel] ============ TỔNG KẾT ============", flush=True)
for f in ["v10_lab_rows.csv", "v10_lab_report.json", "validator_results.csv",
          "ppsweep_results.csv", "v10_lab_cache/raw_graphs.json", "v10_lab_cache/gt_bundle.json"]:
    p = RUN / f
    sz = p.stat().st_size if p.exists() else 0
    print(f"  {f:42s} {'OK' if p.exists() else 'MISSING':7s} {sz:,} bytes", flush=True)
try:
    import json
    rep = json.loads((RUN / "v10_lab_report.json").read_text())
    for label, c in sorted(rep.get("configs", {}).items()):
        if c.get("skipped"):
            print(f"  [grid] {label:10s} SKIPPED ({c.get('skip_reason')})", flush=True)
        elif c.get("summary"):
            s = c["summary"]
            d = c.get("deltas_vs_ref", {}).get("adjusted_edge_jaccard", 0.0)
            print(f"  [grid] {label:10s} adjEJ={s['adjusted_edge_jaccard']:.6f} d={d:+.6f} proxy={s['proxy_score']:.6f}", flush=True)
except Exception as e:
    print("  (report chưa sẵn:", e, ")", flush=True)

print("[kernel] chờ watchdog đẩy nốt checkpoint (180s)...", flush=True)
time.sleep(180)
print("[kernel] KERNEL_DONE rc3=%d" % rc3, flush=True)
