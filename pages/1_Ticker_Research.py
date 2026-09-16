"""Quick-research panel for a single ticker: price/fundamentals, analyst
ratings, and recent news -- either typed in manually, or auto-detected from
whichever symbol is currently selected in thinkorswim (Windows only).

Run with:  streamlit run app.py   (this page is picked up automatically)
"""

import streamlit as st

from src.config import TOS_POLL_INTERVAL_SECONDS
from src.ticker_research import get_snapshot
from src.tos_watch import get_current_symbol, is_supported

st.set_page_config(page_title="Ticker Research", layout="wide")
st.title("🔎 Ticker Research")
st.caption(
    "Not financial advice. Price, fundamentals, and analyst estimates are "
    "delayed/best-effort from Yahoo Finance."
)

if "manual_symbol" not in st.session_state:
    st.session_state.manual_symbol = "AAPL"
if "watch_tos" not in st.session_state:
    st.session_state.watch_tos = False

control_col, symbol_col = st.columns([1, 2])

with control_col:
    if is_supported():
        st.session_state.watch_tos = st.toggle(
            "🔗 Watch thinkorswim",
            value=st.session_state.watch_tos,
            help=(
                "Auto-detects the symbol from the control configured in "
                "src/config.py (TOS_SYMBOL_CONTROL). Run tos_discover.py "
                "first if you haven't set that up yet -- see the README."
            ),
        )
    else:
        st.session_state.watch_tos = False
        st.info(
            "thinkorswim auto-detection needs Windows + `pywinauto` "
            "(`pip install pywinauto`). Type a symbol manually for now."
        )

with symbol_col:
    manual = st.text_input(
        "Symbol",
        value=st.session_state.manual_symbol,
        disabled=st.session_state.watch_tos,
    ).strip().upper()
    if manual:
        st.session_state.manual_symbol = manual


@st.fragment(run_every=TOS_POLL_INTERVAL_SECONDS if st.session_state.watch_tos else None)
def render() -> None:
    if st.session_state.watch_tos:
        symbol = get_current_symbol()
        if symbol is None:
            st.warning(
                "Couldn't read a symbol from thinkorswim. Make sure it's "
                "running, the Java Access Bridge is enabled, and "
                "TOS_SYMBOL_CONTROL in src/config.py matches your layout "
                "(run `python tos_discover.py` to check)."
            )
            return
        st.caption(f"Auto-detected from thinkorswim: **{symbol}**")
    else:
        symbol = st.session_state.manual_symbol
        if not symbol:
            st.info("Type a ticker above to see research.")
            return

    with st.spinner(f"Loading {symbol}..."):
        snap = get_snapshot(symbol)

    if snap.error:
        st.error(f"Couldn't load data for {symbol}: {snap.error}")
        return

    st.subheader(f"{snap.name or snap.symbol} ({snap.symbol})")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Price",
        f"{snap.price:.2f}" if snap.price is not None else "n/a",
        delta=f"{snap.change_pct:+.2f}%" if snap.change_pct is not None else None,
    )
    m2.metric("Market Cap", f"${snap.market_cap / 1e9:.1f}B" if snap.market_cap else "n/a")
    m3.metric("P/E (TTM)", f"{snap.pe_ratio:.1f}" if snap.pe_ratio else "n/a")
    m4.metric(
        "52w Range",
        f"{snap.week52_low:.0f}–{snap.week52_high:.0f}"
        if snap.week52_low and snap.week52_high
        else "n/a",
    )

    if snap.sector:
        st.caption(snap.sector + (f" — {snap.industry}" if snap.industry else ""))

    st.divider()
    st.markdown("#### Analyst View")
    a = snap.analyst
    if a.num_analysts:
        c1, c2, c3 = st.columns(3)
        c1.metric("Consensus", (a.recommendation or "n/a").replace("_", " ").title())
        c2.metric("Avg. Price Target", f"{a.target_mean:.2f}" if a.target_mean else "n/a")
        c3.metric(
            "Target Range",
            f"{a.target_low:.0f}–{a.target_high:.0f}" if a.target_low and a.target_high else "n/a",
        )
        st.caption(f"Based on {a.num_analysts} analyst(s).")
    else:
        st.caption("No analyst coverage data available for this ticker.")

    st.divider()
    st.markdown("#### Recent News")
    if not snap.news:
        st.caption("No recent news found for this ticker.")
    for item in snap.news:
        tone = "🟢" if item.sentiment > 0.15 else "🔴" if item.sentiment < -0.15 else "⚪"
        flag = " ⚡" if item.is_market_moving else ""
        st.markdown(f"{tone} [{item.title}]({item.link}) — *{item.publisher}*{flag}")


render()
