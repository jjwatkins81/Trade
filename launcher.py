"""Desktop entry point: runs the dashboard's Streamlit server in-process and
opens it in the default browser. This is the script PyInstaller freezes into
the standalone .exe -- see packaging/README.md for how to build it.
"""

import os
import sys
import threading
import time
import webbrowser

# app.py and src/ are bundled as data files (Streamlit's own script runner
# executes them at runtime), so PyInstaller's static import analysis --
# which only walks imports reachable from this entry script -- never sees
# their imports and would otherwise leave these packages out of the build.
# Import them here, unused, purely so PyInstaller bundles them.
import feedparser  # noqa: F401
import numpy  # noqa: F401
import pandas  # noqa: F401
import plotly.graph_objects  # noqa: F401
import scipy.stats  # noqa: F401
import vaderSentiment.vaderSentiment  # noqa: F401
import yfinance  # noqa: F401


def _resource_path(relative: str) -> str:
    """Resolve a path next to this script, whether frozen by PyInstaller or not."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def _open_browser_when_ready(url: str) -> None:
    import urllib.request

    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            time.sleep(0.5)
    webbrowser.open(url)


def main() -> None:
    from streamlit import config as st_config
    from streamlit.web import bootstrap

    # PyInstaller freezes streamlit's own __file__ to a path that doesn't
    # contain "site-packages"/"dist-packages", so Streamlit's own heuristic
    # for global.developmentMode defaults to True when frozen -- which skips
    # mounting the static frontend assets and makes every page 404. Force it
    # off explicitly rather than relying on flag_options translation.
    st_config.set_option("global.developmentMode", False)

    app_path = _resource_path("app.py")
    port = "8501"
    url = f"http://localhost:{port}"

    threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    sys.argv = ["streamlit", "run", app_path]
    bootstrap.run(
        app_path,
        False,
        [],
        {
            "server.port": port,
            "server.headless": False,
            "server.address": "localhost",
            "browser.gatherUsageStats": False,
        },
    )


if __name__ == "__main__":
    main()
