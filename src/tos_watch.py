"""Windows-only: read the ticker symbol currently shown/selected in thinkorswim.

thinkorswim doesn't expose "which symbol is on screen right now" over DDE or
any API -- DDE only lets you pull live fields (LAST, BID, MARK, ...) for a
symbol you already know (e.g. Excel's `=TOS|AAPL!LAST`). To read the symbol
itself, we go through Windows UI Automation instead -- the same
accessibility layer screen readers use to read an app's controls.

thinkorswim is a Java/Swing application, and Swing apps are invisible to
Windows UI Automation by default -- Windows can only see a single opaque
window with no children -- unless the Java Access Bridge is bridging Swing's
own accessibility tree into it. See the README "thinkorswim setup" section
for how to turn that on. Once it's on, `tos_discover.py` dumps the control
tree so you can find the automation id of whichever symbol box you want to
track (Quote panel, a linked Chart, Active Trader, ...) and put it in
TOS_SYMBOL_CONTROL in src/config.py.
"""

import re
import sys

from src.config import TOS_SYMBOL_CONTROL, TOS_WINDOW_TITLE_RE

_PYWINAUTO_AVAILABLE = sys.platform == "win32"
if _PYWINAUTO_AVAILABLE:
    try:
        from pywinauto import Desktop
    except ImportError:
        _PYWINAUTO_AVAILABLE = False

# Loose ticker shape: equities/ETFs (AAPL, BRK.B), futures (/ES), indexes (^SPX).
_SYMBOL_RE = re.compile(r"^[/^]?[A-Z]{1,6}(?:[./][A-Z]{1,4})?$")


def is_supported() -> bool:
    """Whether symbol watching can work in this environment at all."""
    return _PYWINAUTO_AVAILABLE


def get_current_symbol() -> str | None:
    """Best-effort read of the symbol in the configured thinkorswim control.

    Returns None if thinkorswim isn't running, the configured control can't
    be found (most commonly: Java Access Bridge isn't enabled, or
    TOS_SYMBOL_CONTROL doesn't match your layout -- run tos_discover.py),
    or the text found doesn't look like a ticker.
    """
    if not _PYWINAUTO_AVAILABLE:
        return None

    try:
        windows = Desktop(backend="uia").windows(title_re=TOS_WINDOW_TITLE_RE)
        if not windows:
            return None
        control = windows[0].child_window(**TOS_SYMBOL_CONTROL)
        text = control.window_text().strip().upper()
    except Exception:
        return None

    if not text or not _SYMBOL_RE.match(text):
        return None
    return text
