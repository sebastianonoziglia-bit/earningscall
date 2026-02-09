#!/bin/bash
source app/.venv/bin/activate
streamlit run app/Welcome.py --server.address localhost --server.runOnSave=false --server.fileWatcherType=none
