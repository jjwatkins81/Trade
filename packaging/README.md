# Building a standalone executable

This packages the dashboard (via `launcher.py` + PyInstaller) into a single
executable that bundles Python and all dependencies -- no separate Python
install needed to *run* it. Building it still requires Python, and you must
build **on the OS you want to run it on** (PyInstaller does not cross-compile
-- build on Windows for a `.exe`, on macOS for a Mac app, etc).

## Windows

```
packaging\build_windows.bat
```

Produces `dist\MarketDashboard.exe`. Double-click it, or run it from a
terminal -- it starts a local web server and opens your browser to the
dashboard automatically. First launch takes a few seconds longer (it's
unpacking itself to a temp folder); later launches are faster.

Windows SmartScreen will likely warn about an unrecognized publisher, since
this isn't code-signed. Click "More info" -> "Run anyway".

**"Python was not found" / opens the Microsoft Store:** that's Windows'
built-in `python.exe` stub, not a real Python install shadowing it. Install
Python from https://www.python.org/downloads/windows/ and check "Add
python.exe to PATH" during setup, then run the script again. If Python is
already installed and you still see this, the stub is intercepting it first
-- turn it off under Settings > Apps > Advanced app settings > App execution
aliases (toggle off `python.exe` and `python3.exe`).

## macOS / Linux

```
./packaging/build.sh
```

Produces `dist/MarketDashboard`.

## Notes

- The build was validated (Linux ELF binary, same PyInstaller flags) to
  actually launch, serve the Streamlit frontend, and render the dashboard
  before these scripts were written -- but it hasn't been run through an
  actual Windows build, since that requires a Windows machine. If
  `build_windows.bat` errors, check the message; the most likely gap is a
  dependency's Windows-specific PyInstaller hook.
- The `.exe` still makes live network calls at runtime (Yahoo Finance
  quotes, options chains, RSS feeds) -- it's not bundling any data, just
  the Python runtime and libraries. You need internet access when you run
  it, same as `streamlit run app.py`.
- To change what the app does, edit `app.py`/`src/*.py` as usual and
  re-run the build script -- no separate packaging code to maintain.
