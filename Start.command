#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$SCRIPT_DIR/app"
PID_FILE="$APP_DIR/.streamlit.pid"
PORT_FILE="$APP_DIR/.streamlit.port"
LOG_FILE="$APP_DIR/.streamlit.log"

if [ ! -d "$APP_DIR" ]; then
  echo "App folder not found: $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

if [ ! -d ".venv" ]; then
  echo "Virtualenv not found at $APP_DIR/.venv"
  exit 1
fi

PORT=8503
while lsof -i :"$PORT" >/dev/null 2>&1; do
  PORT=$((PORT + 1))
done

source .venv/bin/activate

nohup streamlit run Welcome.py --server.address localhost --server.port "$PORT" > "$LOG_FILE" 2>&1 &
PID=$!

echo "$PID" > "$PID_FILE"
echo "$PORT" > "$PORT_FILE"

echo "Started Streamlit (PID $PID) on port $PORT"
open "http://localhost:$PORT"
