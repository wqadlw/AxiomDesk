#!/usr/bin/env bash
# AxiomDesk 一键启动 (macOS / Linux / Git Bash)
# 自动定位目录、避免端口冲突、后台起服务并打开浏览器。
set -euo pipefail

PORT=8137
HOST=127.0.0.1
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python

URL="http://${HOST}:${PORT}/"

is_up() {
  command -v curl >/dev/null 2>&1 && curl -fsS -o /dev/null "$URL/api/health" 2>/dev/null
}

if is_up; then
  echo "AxiomDesk 已在运行: $URL"
else
  echo "正在启动 AxiomDesk (端口 $PORT) ..."
  nohup "$PY" -m uvicorn server.app:app --host "$HOST" --port "$PORT" >/dev/null 2>&1 &
  for _ in $(seq 1 30); do
    sleep 1
    if is_up; then break; fi
  done
fi

echo "打开: $URL"
(command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL") \
  || (command -v open >/dev/null 2>&1 && open "$URL") \
  || (command -v start >/dev/null 2>&1 && start "$URL") \
  || echo "请手动打开: $URL"
