#!/usr/bin/env bash
# Builds dist/MarketDashboard: a standalone executable for the OS you run
# this on (macOS or Linux -- for a Windows .exe, run build_windows.bat on
# Windows instead; PyInstaller does not cross-compile between OSes).
set -euo pipefail
cd "$(dirname "$0")/.."

python3 -m pip install -r requirements.txt -r packaging/requirements-build.txt

python3 -m PyInstaller --noconfirm --onefile --name MarketDashboard \
  --add-data "app.py:." \
  --add-data "src:src" \
  --collect-all streamlit \
  --copy-metadata streamlit \
  --collect-all vaderSentiment \
  --collect-all plotly \
  --collect-all yfinance \
  --collect-all feedparser \
  launcher.py

echo
echo "Done. Your executable is at dist/MarketDashboard"
echo "Run it from a terminal (./dist/MarketDashboard) -- it starts a local"
echo "server and opens your browser automatically."
