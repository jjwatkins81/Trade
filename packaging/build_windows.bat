@echo off
setlocal

rem Builds dist\MarketDashboard.exe: a standalone Windows executable that
rem needs no Python install to run. Must be run ON WINDOWS (PyInstaller
rem does not cross-compile) with Python 3.11+ available as "python".

cd /d "%~dp0.."

rem Find a real Python. Plain "python" on a fresh Windows install is often a
rem stub that just opens the Microsoft Store -- try the "py" launcher first,
rem since that's what the official python.org installer registers.
set PY=
py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  python --version >nul 2>&1 && set PY=python
)
if not defined PY (
  echo.
  echo Python was not found.
  echo.
  echo Install it from https://www.python.org/downloads/windows/ -- during
  echo setup, check "Add python.exe to PATH" on the first screen -- then
  echo run this script again.
  echo.
  echo If you already installed Python and still see this message, Windows'
  echo "App execution alias" for python.exe is likely intercepting it first:
  echo Settings ^> Apps ^> Advanced app settings ^> App execution aliases ^>
  echo turn OFF the entries for python.exe and python3.exe.
  pause
  exit /b 1
)

%PY% -m pip install -r requirements.txt -r packaging\requirements-build.txt
if errorlevel 1 goto :error

%PY% -m PyInstaller --noconfirm --onefile --name MarketDashboard ^
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
pause
goto :eof

:error
echo.
echo Build failed -- see the output above.
pause
exit /b 1
