#!/bin/bash
set -e

APP_DIR="/Users/sebbo/Desktop/Replit revival/Replit"
PID_FILE="$APP_DIR/.streamlit.pid"
PORT_FILE="$APP_DIR/.streamlit.port"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if ps -p "$PID" >/dev/null 2>&1; then
    kill "$PID"
    echo "Stopped Streamlit (PID $PID)."
  else
    echo "No running process for PID $PID."
  fi
  rm -f "$PID_FILE" "$PORT_FILE"
else
  if pkill -f "streamlit run Welcome.py" >/dev/null 2>&1; then
    echo "Stopped Streamlit instances for Welcome.py."
  else
    echo "No Streamlit process found."
  fi
fi
