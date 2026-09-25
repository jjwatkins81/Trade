"""Intraday price history including pre-market and after-hours sessions.

US extended hours (Eastern Time), as Yahoo reports them:

- Pre-market:  4:00 - 9:30
- Regular:     9:30 - 16:00
- After-hours: 16:00 - 20:00

Yahoo only keeps fine-grained bars for a limited window, so the interval
caps how far back you can go: 1m -> ~7 days, 2m/5m/15m/30m -> ~60 days,
60m -> ~2 years. Extended-hours volume is thin, so pre-market prices can jump
around more than they would in the regular session.

Run from the command line with:

    python -m src.intraday CAT --days 5 --interval 5m
"""

import argparse
from datetime import time

import pandas as pd
import yfinance as yf

EASTERN = "America/New_York"
PRE_START, REGULAR_START, REGULAR_END, POST_END = time(4, 0), time(9, 30), time(16, 0), time(20, 0)

# Longest lookback (days) Yahoo serves for each intraday interval.
MAX_DAYS_BY_INTERVAL = {"1m": 7, "2m": 60, "5m": 60, "15m": 60, "30m": 60, "60m": 730}


def _session(ts: pd.Timestamp) -> str:
    t = ts.time()
    if PRE_START <= t < REGULAR_START:
        return "Pre-market"
    if REGULAR_START <= t < REGULAR_END:
        return "Regular"
    if REGULAR_END <= t < POST_END:
        return "After-hours"
    return "Overnight"


def fetch_intraday(symbol: str, days: int = 5, interval: str = "5m") -> pd.DataFrame:
    """Intraday bars incl. extended hours, indexed in Eastern Time with a Session column.

    Empty if data is unavailable.
    """
    days = min(days, MAX_DAYS_BY_INTERVAL.get(interval, 60))
    try:
        bars = yf.Ticker(symbol).history(period=f"{days}d", interval=interval, prepost=True)
    except Exception:
        return pd.DataFrame()
    if bars is None or bars.empty:
        return pd.DataFrame()

    idx = bars.index
    bars.index = idx.tz_localize("UTC").tz_convert(EASTERN) if idx.tz is None else idx.tz_convert(EASTERN)
    bars = bars[["Open", "High", "Low", "Close", "Volume"]].copy()
    bars["Session"] = [_session(ts) for ts in bars.index]
    return bars[bars["Session"] != "Overnight"]


def daily_session_summary(bars: pd.DataFrame) -> pd.DataFrame:
    """One row per trading day: how pre-market traded vs. the prior close and the open."""
    if bars.empty:
        return pd.DataFrame()

    rows = []
    prev_close = None
    for day, day_bars in bars.groupby(bars.index.date):
        pre = day_bars[day_bars["Session"] == "Pre-market"]
        reg = day_bars[day_bars["Session"] == "Regular"]
        post = day_bars[day_bars["Session"] == "After-hours"]

        row = {"Date": day, "Prior close": prev_close}
        if not pre.empty:
            row.update({
                "Pre open": pre["Open"].iloc[0],
                "Pre high": pre["High"].max(),
                "Pre low": pre["Low"].min(),
                "Pre last": pre["Close"].iloc[-1],
                "Pre volume": int(pre["Volume"].sum()),
            })
        if not reg.empty:
            row.update({
                "Open": reg["Open"].iloc[0],
                "High": reg["High"].max(),
                "Low": reg["Low"].min(),
                "Close": reg["Close"].iloc[-1],
            })
            prev_close = row["Close"]
        if not post.empty:
            row["After-hours last"] = post["Close"].iloc[-1]
        rows.append(row)

    df = pd.DataFrame(rows)
    if {"Open", "Prior close"} <= set(df.columns):
        df["Gap $"] = df["Open"] - df["Prior close"]
        df["Gap %"] = df["Gap $"] / df["Prior close"] * 100
    if {"Pre high", "Pre low"} <= set(df.columns):
        df["Pre range $"] = df["Pre high"] - df["Pre low"]
    if {"High", "Low"} <= set(df.columns):
        df["Day range $"] = df["High"] - df["Low"]
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("symbol")
    parser.add_argument("--days", type=int, default=5)
    parser.add_argument("--interval", default="5m", choices=list(MAX_DAYS_BY_INTERVAL))
    args = parser.parse_args()

    summary = daily_session_summary(fetch_intraday(args.symbol.upper(), args.days, args.interval))
    if summary.empty:
        print("No intraday data available right now.")
        return
    with pd.option_context("display.width", 250, "display.max_columns", None):
        print(summary.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
