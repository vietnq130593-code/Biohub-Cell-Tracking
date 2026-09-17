# -*- coding: utf-8 -*-
# Probe qua colab exec: VM con song khong, download subprocess chay den dau
import os
import sys
import subprocess
import time

print("PROBE_OK py=%s cwd=%s" % (sys.version.split()[0], os.getcwd()))

for p in ["/content/v10_cell2.log", "/content/v10_cell2_run.py", "/content/v10_cell3_run.py",
          "/content/v10_env.json", "/content/v10_cell2.done", "/content/colab-bridge-cloudflared.log"]:
    print("  exists %-45s %s" % (p, os.path.exists(p)))

r = subprocess.run(["pgrep", "-af", "v10_cell"], capture_output=True, text=True)
print("PROCS:", r.stdout.strip() or "(khong con tien trinh v10)")

r2 = subprocess.run(["pgrep", "-af", "cloudflared"], capture_output=True, text=True)
print("CLOUDFLARED:", r2.stdout.strip() or "(chet)")

root = "/content/kaggle/input/biohub-cell-tracking-during-development/train"
n = 0
total = 0
last_mtime = 0
if os.path.isdir(root):
    for dp, dn, fn in os.walk(root):
        for f in fn:
            fp = os.path.join(dp, f)
            try:
                st = os.stat(fp)
                n += 1
                total += st.st_size
                if st.st_mtime > last_mtime:
                    last_mtime = st.st_mtime
            except OSError:
                pass
print("TRAIN_FILES: %d/984 · %.2f GB · newest_age_s=%d" % (n, total / 1e9, int(time.time() - last_mtime) if last_mtime else -1))

if os.path.exists("/content/v10_cell2.log"):
    txt = open("/content/v10_cell2.log", errors="ignore").read()
    lines = [l for l in txt.strip().splitlines() if l.strip()]
    print("=== LOG TAIL 12:")
    for l in lines[-12:]:
        print("   " + l[:150])

# datasets input root
inp = "/content/kaggle/input"
if os.path.isdir(inp):
    print("INPUT_DS:", sorted(os.listdir(inp)))
