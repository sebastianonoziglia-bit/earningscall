#!/bin/bash
# ── Run the app locally ──────────────────────────────────────────
# Creates/uses a virtual environment so pip doesn't conflict with macOS
set -e
cd "$(dirname "$0")"

VENV_DIR="venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate and install deps
source "$VENV_DIR/bin/activate"
echo "Installing dependencies..."
pip install -r app/requirements.txt --quiet

# Run Streamlit
cd app
streamlit run Welcome.py \
  --server.port 8501 \
  --server.headless false \
  --browser.gatherUsageStats false \
  --server.fileWatcherType none
