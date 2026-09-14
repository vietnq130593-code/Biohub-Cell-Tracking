#!/usr/bin/env bash
# PM2 startup wrapper — Biohub Cell Tracking web UI (Next.js dev, port 3000)
# Mục đích:
#   1. Tự dọn port 3000 nếu có process mồ côi (từ lần crash/kill -9 trước) còn giữ port
#      → tránh EADDRINUSE khiến PM2 restart lặp vòng.
#   2. exec next dev trực tiếp bằng node (không qua bun/bash pipeline)
#      → PM2 quản lý đúng process tree, SIGINT lan tới next-server.
set -u
cd /home/z/my-project

# --- Dọn port 3000 nếu bị chiếm bởi process mồ côi ---
PIDS=$(ss -tlnpH 'sport = :3000' 2>/dev/null | grep -oP 'pid=\K[0-9]+' | sort -u || true)
if [ -n "${PIDS:-}" ]; then
  echo "[pm2-start] Dọn port 3000 — kill pid mồ côi: $(echo "$PIDS" | tr '\n' ' ')"
  for p in $PIDS; do
    kill -9 "$p" 2>/dev/null || true
  done
  sleep 1
fi

# --- Khởi động Next.js dev server (exec: thay thế shell, PM2 quản lý trực tiếp) ---
exec /usr/bin/node /home/z/my-project/node_modules/next/dist/bin/next dev -p 3000
