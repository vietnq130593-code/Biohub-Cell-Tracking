#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""poll.py — đọc trạng thái tiến trình v10 trên Colab qua bridge (1 lệnh)."""
import sys
sys.path.insert(0, "/home/z/my-project/kaggle/colab-bridge")
import colabctl  # noqa: E402

URL = "https://tee-guests-src-superior.trycloudflare.com"
TOKEN = "MTgcrx_38kT-oVT8_Ceq-eZFSHA"

CODE = r'''
import os, subprocess
logs = ["/content/v10_cell2.log", "/content/v10_cell3.log"]
for p in logs:
    if os.path.exists(p):
        txt = open(p, errors="ignore").read()
        lines = [l for l in txt.strip().splitlines() if l.strip()]
        print("=== %s (%d lines, tail 18):" % (p, len(lines)))
        for l in lines[-18:]:
            print("   " + l[:160])
r = subprocess.run(["pgrep", "-af", "v10_cell"], capture_output=True, text=True)
print("=== PROCS:", (r.stdout.strip() or "(KHONG CON TIEN TRINH NAO)"))
for marker in ["/content/v10_cell2.done", "/content/v10_env.json", "/content/v10_cell3.done"]:
    print("   marker %s: %s" % (marker, "CO" if os.path.exists(marker) else "chua"))
df = subprocess.run(["df", "-h", "/content"], capture_output=True, text=True).stdout.strip().splitlines()[-1]
print("=== DISK:", df)
import glob
wd = "/kaggle/working"
if os.path.isdir(wd):
    outs = [os.path.basename(x) for x in glob.glob(wd + "/v10_lab*")]
    print("=== WORKING v10_lab*:", outs or "(chua co)")
'''

status, obj = colabctl._request(URL, TOKEN, "/exec", {"code": CODE}, timeout=120)
out = obj.get("stdout") or ""
err = obj.get("stderr") or ""
if out:
    print(out)
if err:
    print("STDERR:", err[-800:])
print("ok=%s" % obj.get("ok"))
