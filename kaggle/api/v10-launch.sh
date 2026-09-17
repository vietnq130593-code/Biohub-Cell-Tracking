#!/usr/bin/env bash
# v10-launch.sh — Nộp bài ver-10 THEO KHUYẾN NGHỊ V10-RESULTS.md §6, một lệnh duy nhất:
#   (1) chờ GPU quota (tuỳ chọn --wait — poll đến khi refresh 19/9 00:00 UTC)
#   (2) push kernel biohub-ver10 (T4×2, Internet OFF, 9 dataset)
#   (3) watch đến COMPLETE (~2.0–2.2h; timeout 5h) + tải output
#   (4) submit kernel version vào competition (kagglesdk create_code_submission)
#   (5) liệt kê submissions + điểm
#
# Chạy:  bash kaggle/api/v10-launch.sh            # push ngay (fail nếu quota cạn)
#        bash kaggle/api/v10-launch.sh --wait     # poll quota mỗi 5' đến khi có quota rồi tự chạy
set -uo pipefail
cd "$(dirname "$0")"

export KAGGLE_ACCESS_TOKEN="$(cat ~/.kaggle/access_token 2>/dev/null)"
if [ -z "${KAGGLE_ACCESS_TOKEN}" ]; then echo "Thiếu ~/.kaggle/access_token"; exit 1; fi

WAIT=0
[ "${1:-}" = "--wait" ] && WAIT=1

quota_remaining() {
  python3 -m kaggle quota 2>/dev/null | awk '/^GPU/ {print $3}'
}

if [ "$WAIT" = "1" ]; then
  echo "== [v10-launch] chờ GPU quota (poll 300s) =="
  for i in $(seq 1 400); do   # tối đa ~33h
    REM="$(quota_remaining)"
    echo "  [$(date -u '+%H:%M:%S')] GPU remaining: ${REM:-?}"
    if [ -n "${REM:-}" ] && [ "${REM%h*}" != "0.00" ] 2>/dev/null; then
      OK=1
      python3 - <<'PY' && break || true
rem = None
import subprocess
out = subprocess.run(['python3', '-m', 'kaggle', 'quota'], capture_output=True, text=True).stdout
for ln in out.splitlines():
    if ln.startswith('GPU'):
        rem = ln.split()[2]
        raise SystemExit(0 if float(rem.rstrip('h')) >= 0.5 else 1)
raise SystemExit(1)
PY
    fi
    sleep 300
  done
fi

echo "== [v10-launch] kiểm tra quota trước push =="
python3 - <<'PY' || { echo "Quota GPU cạn — dùng --wait hoặc chạy lại sau refresh (xem dòng refreshAt)."; exit 2; }
import subprocess
out = subprocess.run(['python3', '-m', 'kaggle', 'quota'], capture_output=True, text=True).stdout
print(out.strip())
for ln in out.splitlines():
    if ln.startswith('GPU'):
        rem = ln.split()[2]
        if float(rem.rstrip('h')) < 0.5:
            raise SystemExit(1)
raise SystemExit(0)
PY

echo "== [v10-launch] 1/4 PUSH biohub-ver10 =="
python3 ktool.py push --ver 10 || exit 3

echo "== [v10-launch] 2/4 WATCH (poll 60s, tối đa 5h) =="
python3 ktool.py watch --ver 10 --poll 60 || exit 4

echo "== [v10-launch] 3/4 SUBMIT kernel version =="
python3 submit-v10.py || exit 5

echo "== [v10-launch] 4/4 SCORE =="
python3 ktool.py score || true

echo "== [v10-launch] HOÀN TẤT — xem điểm chấm trên leaderboard trong 6-12h tới =="
