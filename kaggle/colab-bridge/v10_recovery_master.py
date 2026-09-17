# -*- coding: utf-8 -*-
# v10_recovery_master.py — chạy TRÊN Colab VM (background, qua colab exec).
#
# Tự hoá TOÀN BỘ relaunch sau khi session chết (f37bae mất 01:42 UTC):
#   1) cell 2  (v10_cell2_run.py)      — data nếp B dataset biohub-v10-stems8 (~4-6 phút)
#   2) repair  (repair_deps.py)         — vá Python 3.13 quirk (pydantic-core==2.46.5 ...)
#   3) watchdog (v10_ckpt_watchdog.py)  — background: upload checkpoint lên Kaggle
#   4) cell 3  (v10_cell3_run.py)       — background: validator 8 stems + grid 9 config
#
# Idempotent: cell 2 có resume per-file + marker; repair pip no-op khi đã đúng phiên bản.
# Log: /content/v10_recovery.log + log riêng từng giai đoạn (v10_cell2.log, repair.log,
# v10_cell3.log, v10_ckpt.log). Marker: /content/v10_cell2.done.

import os
import subprocess
import sys
import time
from pathlib import Path

LOG = open("/content/v10_recovery.log", "a")


def log(m):
    line = time.strftime("[%Y-%m-%d %H:%M:%S] ") + str(m)
    print(line, flush=True)
    LOG.write(line + "\n")
    LOG.flush()


def run_stage(name, cmd, log_path, timeout_s):
    """Chạy foreground, redirect stdout/stderr vào log_path riêng. Trả rc."""
    log("STAGE %s START: %s → %s (timeout %ds)" % (name, " ".join(cmd), log_path, timeout_s))
    with open(log_path, "a") as lf:
        try:
            r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT,
                               stdin=subprocess.DEVNULL, timeout=timeout_s)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = -9
            log("STAGE %s TIMEOUT sau %ds" % (name, timeout_s))
    log("STAGE %s END rc=%d" % (name, rc))
    return rc


def bg_launch(name, script, log_path):
    with open(log_path, "a") as lf:
        p = subprocess.Popen([sys.executable, "-u", script], stdout=lf, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True, cwd="/content")
    log("LAUNCH %s pid=%d → %s" % (name, p.pid, log_path))
    return p.pid


log("=== v10 recovery master start (pid %d) ===" % os.getpid())

# ---- 1) cell 2 — data (idempotent: marker + resume per-file) ----
if Path("/content/v10_cell2.done").exists():
    log("cell 2 marker đã có — SKIP cell 2")
else:
    rc = run_stage("cell2", [sys.executable, "-u", "/content/v10_cell2_run.py"],
                   "/content/v10_cell2.log", 5400)
    if rc != 0 and not Path("/content/v10_cell2.done").exists():
        log("!!! cell 2 rc=%d VÀ không có marker — dừng (không chạy cell 3 thiếu data)" % rc)
        sys.exit(2)

# ---- 2) repair deps (idempotent — pip no-op khi đúng phiên bản) ----
rc = run_stage("repair", [sys.executable, "-u", "/content/repair_deps.py"],
               "/content/repair_run.log", 2400)
if rc != 0:
    log("!!! repair rc=%d — thử tiếp (cell 3 có fallback wheels/PyPI riêng)" % rc)

# ---- 3) + 4) watchdog & cell 3 — background ----
if subprocess.run(["pgrep", "-f", "v10_ckpt_watchdog.py"], capture_output=True).returncode != 0:
    bg_launch("watchdog", "/content/v10_ckpt_watchdog.py", "/content/v10_ckpt_stdout.log")
else:
    log("watchdog đang chạy — skip launch")

if subprocess.run(["pgrep", "-f", "v10_cell3_run.py"], capture_output=True).returncode != 0:
    bg_launch("cell3", "/content/v10_cell3_run.py", "/content/v10_cell3.log")
else:
    log("cell 3 đang chạy — skip launch")

log("=== recovery master DONE (theo dõi: /content/v10_ckpt.log + v10_cell3.log) ===")
