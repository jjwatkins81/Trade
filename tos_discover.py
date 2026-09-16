"""Windows-only diagnostic: dump thinkorswim's UI Automation control tree.

Run this with thinkorswim open to find the automation id / control type of
whichever symbol box you want to track (e.g. the Quote panel's symbol
field, or a linked Chart's symbol field), then put those values into
TOS_SYMBOL_CONTROL in src/config.py.

If this only prints the top-level window with no children, thinkorswim's
Java Access Bridge probably isn't enabled -- see the README's
"thinkorswim setup" section.

Usage:
    python tos_discover.py
"""

import sys

if sys.platform != "win32":
    raise SystemExit("This tool only works on Windows, against a running thinkorswim.")

from pywinauto import Desktop

from src.config import TOS_WINDOW_TITLE_RE


def main() -> None:
    windows = Desktop(backend="uia").windows(title_re=TOS_WINDOW_TITLE_RE)
    if not windows:
        print(f"No window matching {TOS_WINDOW_TITLE_RE!r} found. Is thinkorswim running?")
        return

    for w in windows:
        print(f"=== {w.window_text()!r} ===")
        try:
            w.print_control_identifiers(depth=12)
        except Exception as exc:
            print(f"(couldn't walk this window's controls: {exc})")
        print()


if __name__ == "__main__":
    main()
