"""Volatility screener: NYSE stocks under a price cap that routinely move $X a day.

"Moves up and down by $10" is measured three ways over a recent lookback
window, all in dollars (not percent), since a $10 swing is what matters for
this screen:

- ATR (14): average true range -- the standard "how far does it typically
  travel in a day" measure, counting overnight gaps.
- Avg daily range: average of (high - low) within each session.
- Avg |close-to-close|: average absolute change from one close to the next.

A stock passes when its latest price is under ``max_price`` and its ATR is at
least ``min_move``. Rule of thumb: a $10 daily move is ~2% on a $500 stock
but ~5% on a $200 stock, so cheaper names need to be much more volatile to
qualify.

Screening "all of NYSE" isn't practical with free data, so this scans a
curated universe of liquid, NYSE-listed large caps (below) and then confirms
each passing ticker's listing exchange from Yahoo's metadata, dropping any
that turn out to be listed elsewhere. Run it from the command line with:

    python -m src.screener --max-price 500 --min-move 10
"""

import argparse

import pandas as pd
import yfinance as yf

from src.config import (
    SCREENER_LOOKBACK_DAYS,
    SCREENER_MAX_PRICE,
    SCREENER_MIN_MOVE,
    SCREENER_UNIVERSE,
)

# Yahoo's exchange codes for the New York Stock Exchange.
NYSE_EXCHANGE_CODES = {"NYQ", "NYSE"}


def _daily_stats(bars: pd.DataFrame, min_move: float) -> dict | None:
    bars = bars.dropna(subset=["High", "Low", "Close"])
    if len(bars) < 15:
        return None

    prev_close = bars["Close"].shift(1)
    true_range = pd.concat(
        [
            bars["High"] - bars["Low"],
            (bars["High"] - prev_close).abs(),
            (bars["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return {
        "Price": float(bars["Close"].iloc[-1]),
        "ATR (14)": float(true_range.tail(14).mean()),
        "Avg daily range": float((bars["High"] - bars["Low"]).mean()),
        "Avg |close-to-close|": float(bars["Close"].diff().abs().mean()),
        "Days range >= min move": int(((bars["High"] - bars["Low"]) >= min_move).sum()),
        "Days in window": len(bars),
    }


def _exchange(symbol: str) -> str:
    try:
        return str(yf.Ticker(symbol).fast_info["exchange"])
    except Exception:
        return "?"


def screen(
    max_price: float = SCREENER_MAX_PRICE,
    min_move: float = SCREENER_MIN_MOVE,
    lookback_days: int = SCREENER_LOOKBACK_DAYS,
    universe: list[str] = SCREENER_UNIVERSE,
) -> pd.DataFrame:
    """Return universe tickers under ``max_price`` whose ATR is >= ``min_move``.

    Sorted by ATR, largest first. Empty if nothing passes or data is unavailable.
    """
    # Pull a little extra history so the 14-day ATR has a full window even
    # after weekends/holidays are dropped.
    data = yf.download(
        universe,
        period=f"{max(lookback_days, 14) * 2}d",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
    )
    if data is None or data.empty:
        return pd.DataFrame()

    rows = []
    for sym in universe:
        try:
            bars = data[sym].tail(lookback_days)
        except KeyError:
            continue
        stats = _daily_stats(bars, min_move)
        if stats is None:
            continue
        if stats["Price"] < max_price and stats["ATR (14)"] >= min_move:
            rows.append({"Symbol": sym, **stats})

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["ATR % of price"] = df["ATR (14)"] / df["Price"] * 100

    # Confirm listing exchange only for the (few) passing tickers, since it
    # costs one request each. Keep "?" (lookup failed) rather than silently
    # dropping a probably-fine curated ticker.
    df["Exchange"] = [_exchange(s) for s in df["Symbol"]]
    df = df[df["Exchange"].isin(NYSE_EXCHANGE_CODES | {"?"})]

    return df.sort_values("ATR (14)", ascending=False).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-price", type=float, default=SCREENER_MAX_PRICE)
    parser.add_argument("--min-move", type=float, default=SCREENER_MIN_MOVE)
    parser.add_argument("--lookback-days", type=int, default=SCREENER_LOOKBACK_DAYS)
    args = parser.parse_args()

    df = screen(args.max_price, args.min_move, args.lookback_days)
    if df.empty:
        print("No matches (or market data unavailable right now).")
        return
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(df.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
