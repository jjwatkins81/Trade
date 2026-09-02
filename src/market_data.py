"""Live quote fetching for the market-overview panel."""

from dataclasses import dataclass

import pandas as pd
import streamlit as st
import yfinance as yf

from src.config import CACHE_TTL_QUOTES, INDICATORS


@dataclass
class Quote:
    label: str
    symbol: str
    price: float
    change: float
    change_pct: float


@st.cache_data(ttl=CACHE_TTL_QUOTES, show_spinner=False)
def fetch_quotes() -> list[Quote]:
    """Fetch the latest price/change for every ticker in INDICATORS.

    Uses a single batched yf.Tickers download (fast_info) rather than one
    request per symbol, since Yahoo rate-limits per-request.
    """
    symbols = [sym for _, sym in INDICATORS]
    labels = {sym: label for label, sym in INDICATORS}

    quotes: list[Quote] = []
    tickers = yf.Tickers(" ".join(symbols))

    for sym in symbols:
        try:
            info = tickers.tickers[sym].fast_info
            price = float(info["last_price"])
            prev_close = float(info["previous_close"])
            change = price - prev_close
            change_pct = (change / prev_close * 100) if prev_close else 0.0
            quotes.append(Quote(labels[sym], sym, price, change, change_pct))
        except Exception:
            quotes.append(Quote(labels[sym], sym, float("nan"), float("nan"), float("nan")))

    return quotes


def quotes_to_dataframe(quotes: list[Quote]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Indicator": q.label,
                "Symbol": q.symbol,
                "Price": q.price,
                "Change": q.change,
                "Change %": q.change_pct,
            }
            for q in quotes
        ]
    )


def market_breadth_score(quotes: list[Quote]) -> float:
    """Fraction of tracked equity indexes/ETFs that are up on the day, in [-1, 1].

    VIX and the 10Y yield are excluded since "up" isn't bullish for those.
    """
    excluded = {"^VIX", "^TNX"}
    changes = [q.change_pct for q in quotes if q.symbol not in excluded and q.change_pct == q.change_pct]
    if not changes:
        return 0.0
    up = sum(1 for c in changes if c > 0)
    down = sum(1 for c in changes if c < 0)
    return (up - down) / len(changes)
