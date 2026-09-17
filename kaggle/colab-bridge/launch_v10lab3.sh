#!/bin/bash
# launch_v10lab3.sh — auth xong rồi chạy script này: tạo T4 + upload + launch keep-busy chain
set -e
export PATH="/home/z/.venv/bin:$PATH"
CB=/home/z/my-project/kaggle/colab-bridge
S=v10lab3

echo "=== 1) create T4 session $S ==="
colab new --gpu T4 --session "$S"

echo "=== 2) upload artifacts ==="
for f in v10_cell2_run.py repair_deps.py v10_ckpt_watchdog.py v10_cell3_run.py v10_recovery_master.py v10_forever.py; do
  colab upload "$CB/$f" "/content/$f" -s "$S"
done

echo "=== 3) launch keep-busy chain (background, 12h timeout) ==="
setsid nohup colab exec -s "$S" -f /content/v10_forever.py --timeout 43200 \
  > /tmp/v10lab3_forever.log 2>&1 &
echo "forever exec pid: $!"
sleep 20
echo "=== 4) first heartbeat ==="
tail -5 /tmp/v10lab3_forever.log
echo "=== DONE — monitor: tail -f /tmp/v10lab3_forever.log ==="
