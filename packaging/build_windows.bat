@echo off
setlocal

rem Builds dist\MarketDashboard.exe: a standalone Windows executable that
rem needs no Python install to run. Must be run ON WINDOWS (PyInstaller
rem does not cross-compile) with Python 3.11+ available as "python".

cd /d "%~dp0.."

python -m pip install -r requirements.txt -r packaging\requirements-build.txt
if errorlevel 1 goto :error

python -m PyInstaller --noconfirm --onefile --name MarketDashboard ^
  --add-data "app.py;." ^
  --add-data "src;src" ^
  --collect-all streamlit ^
  --copy-metadata streamlit ^
  --collect-all vaderSentiment ^
  --collect-all plotly ^
  --collect-all yfinance ^
  --collect-all feedparser ^
  launcher.py
if errorlevel 1 goto :error

echo.
echo Done. Your executable is at dist\MarketDashboard.exe
echo Double-click it, or run it from a terminal, to launch the dashboard --
echo it starts a local server and opens your browser automatically.
goto :eof

:error
echo.
echo Build failed -- see the output above.
exit /b 1
