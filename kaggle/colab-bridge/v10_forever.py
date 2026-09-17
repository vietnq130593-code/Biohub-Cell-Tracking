# -*- coding: utf-8 -*-
# v10_forever.py — CHẠY NGAY TRONG KERNEL (colab exec -f /content/v10_forever.py --timeout 43200)
#
# ★ FIX AUTO-STOP (bài học f37bae chết 01:42 UTC sau 3h38m):
#   cell 3 chạy subprocess.Popen nền → kernel Jupyter IDLE toàn bộ thời gian →
#   Colab idle-reaper giết VM dù keep-alive ping 200 OK mỗi 70s.
#   Idle-detect của Colab dựa trên KERNEL EXECUTION — một execution đang chạy
#   (kể cả sleep loop) = kernel busy = không idle.
#
# Script này giữ kernel busy bằng vòng sleep + heartbeat, trong khi:
#   - recovery master (subprocess setsid — sống sót nếu kernel chết) chạy chuỗi
#     cell2 → repair → watchdog + cell3
#   - heartbeat mỗi 60s in trạng thái (master/cell3/watchdog sống?, artefact,
#     GPU util) → stream về log exec phía sandbox để monitor không cần poll thêm
#   - tail log cell 3 mỗi 10 phút
#   - thoát khi master + cell3 đều kết thúc, hoặc sau KEEP_BUSY_H (mặc định 10.5h
#     — chừa margin trước tường 12h)

import json
import subprocess
import sys
import time
from pathlib import Path

KEEP_BUSY_H = float(__import__("os").environ.get("V10_KEEP_BUSY_H", "10.5"))


def alive(pattern):
    return subprocess.run(["pgrep", "-f", pattern], capture_output=True).returncode == 0


def workdir():
    try:
        return Path(json.loads(Path("/content/v10_env.json").read_text())["V10_WORKING_ROOT"])
    except Exception:
        return Path("/content/kaggle/working")


# ---- 1) launch recovery master nếu chưa chạy ----
if not alive("v10_recovery_master.py"):
    _logf = open("/content/v10_recovery.log", "a")
    _p = subprocess.Popen([sys.executable, "-u", "/content/v10_recovery_master.py"],
                         stdout=_logf, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True, cwd="/content")
    print("[forever] master launched pid=%d" % _p.pid, flush=True)
else:
    print("[forever] master already running", flush=True)

# ---- 2) keep kernel busy ----
_t0 = time.time()
_beat = 0
while (time.time() - _t0) < KEEP_BUSY_H * 3600:
    _beat += 1
    _wd = workdir()
    _c3 = alive("v10_cell3_run.py")
    _mst = alive("v10_recovery_master.py")
    _wdg = alive("v10_ckpt_watchdog.py")
    _rows = (_wd / "v10_lab_rows.csv").exists()
    _raw = (_wd / "v10_lab_cache" / "raw_graphs.json").exists()
    _gpu = "n/a"
    try:
        _gpu = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        pass
    print("[forever +%5ds] master=%d cell3=%d wd=%d rows=%d raw=%d gpu=[%s]" % (
        int(time.time() - _t0), _mst, _c3, _wdg, _rows, _raw, _gpu), flush=True)
    if not _c3 and not _mst:
        print("[forever] master + cell3 đều đã kết thúc — thoát keep-busy", flush=True)
        break
    if _beat % 10 == 0:
        try:
            _lines = [l for l in open("/content/v10_cell3.log", errors="ignore").read().splitlines() if l.strip()]
            print("[forever] --- cell3 tail (%d lines) ---" % len(_lines), flush=True)
            for l in _lines[-4:]:
                print("    " + l[:150], flush=True)
        except OSError:
            print("[forever] --- (chưa có v10_cell3.log) ---", flush=True)
    time.sleep(60)

print("[forever] DONE sau %ds" % int(time.time() - _t0), flush=True)
