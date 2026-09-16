# -*- coding: utf-8 -*-
# poll_probe.py — chạy TRÊN VM qua colab exec: log tail + tiến trình + số file + disk
import os
import subprocess
import time

for p in ["/content/v10_cell2.log", "/content/v10_cell3.log"]:
    if os.path.exists(p):
        txt = open(p, errors="ignore").read()
        lines = [l for l in txt.strip().splitlines() if l.strip()]
        print("=== %s (%d lines, tail 14):" % (p, len(lines)))
        for l in lines[-14:]:
            print("   " + l[:150])
    else:
        print("=== %s: (chua co)" % p)

r = subprocess.run(["pgrep", "-af", "v10_cell"], capture_output=True, text=True)
print("=== PROCS:", r.stdout.strip() or "(khong con)")

for marker in ["/content/v10_cell2.done", "/content/v10_env.json"]:
    print("   marker %s: %s" % (marker, "CO" if os.path.exists(marker) else "chua"))

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
print("=== TRAIN: %d/984 file · %.2f GB · newest_age=%ds" % (
    n, total / 1e9, int(time.time() - last_mtime) if last_mtime else -1))

inp = "/content/kaggle/input"
if os.path.isdir(inp):
    print("=== INPUT_DS (%d):" % len(os.listdir(inp)), sorted(os.listdir(inp))[:12])
df = subprocess.run(["df", "-h", "/content"], capture_output=True, text=True).stdout.strip().splitlines()[-1]
print("=== DISK:", df)
