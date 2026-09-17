# -*- coding: utf-8 -*-
# launch_cell4.py — chạy TRÊN VM: cell 4 (bảng + bootstrap + upload Kaggle) background
import subprocess

logf = open("/content/v10_cell4.log", "w")
p = subprocess.Popen(
    ["python3", "-u", "/content/v10_cell4_run.py"],
    stdout=logf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
    start_new_session=True, cwd="/content",
)
print("LAUNCHED_PID", p.pid)
