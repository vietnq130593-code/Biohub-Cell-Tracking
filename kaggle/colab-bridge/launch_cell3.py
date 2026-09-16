# -*- coding: utf-8 -*-
# launch_cell3.py — chạy TRÊN VM: khởi động cell 3 (monolith validator) background
import subprocess

logf = open("/content/v10_cell3.log", "w")
p = subprocess.Popen(
    ["python3", "-u", "/content/v10_cell3_run.py"],
    stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
    start_new_session=True, cwd="/content",
)
print("LAUNCHED_PID", p.pid)
