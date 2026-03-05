#!/bin/bash
cd "$(dirname "$0")/app"
pip install -r ../requirements.txt --quiet
streamlit run Welcome.py \
  --server.port 8501 \
  --server.headless false \
  --browser.gatherUsageStats false \
  --server.fileWatcherType none
