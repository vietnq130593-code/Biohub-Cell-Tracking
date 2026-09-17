# -*- coding: utf-8 -*-
# launch_cell2.py — chạy TRÊN VM: khởi động cell 2 background (detached, sống qua các lần exec)
import subprocess

logf = open("/content/v10_cell2.log", "w")
p = subprocess.Popen(
    ["python3", "-u", "/content/v10_cell2_run.py"],
    stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
    start_new_session=True, cwd="/content",
)
print("LAUNCHED_PID", p.pid)
