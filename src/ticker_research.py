"""On-demand "quick research" snapshot for a single ticker: price/fundamentals,
analyst ratings, and recent news -- all free via yfinance, no API key needed.
"""

from dataclasses import dataclass

import streamlit as st
import yfinance as yf

from src.config import CACHE_TTL_TICKER_RESEARCH
from src.news import is_market_moving, score_headline


@dataclass
class AnalystView:
    recommendation: str | None       # e.g. "buy", "hold" (yfinance's recommendationKey)
    num_analysts: int | None
    target_mean: float | None
    target_high: float | None
    target_low: float | None


@dataclass
class NewsItem:
    title: str
    publisher: str
    link: str
    sentiment: float
    is_market_moving: bool


@dataclass
class TickerSnapshot:
    symbol: str
    name: str | None
    price: float | None
    change_pct: float | None
    market_cap: float | None
    pe_ratio: float | None
    week52_high: float | None
    week52_low: float | None
    sector: str | None
    industry: str | None
    analyst: AnalystView
    news: list[NewsItem]
    error: str | None = None


def _empty_analyst() -> AnalystView:
    return AnalystView(recommendation=None, num_analysts=None, target_mean=None, target_high=None, target_low=None)


def _extract_news(raw_news: list[dict]) -> list[NewsItem]:
    """yfinance's Ticker.news schema has shifted across versions (flat dict vs
    nested under "content"); handle both rather than pinning a version."""
    items: list[NewsItem] = []
    for entry in raw_news[:10]:
        content = entry.get("content", entry)
        title = (content.get("title") or entry.get("title") or "").strip()
        if not title:
            continue
        link = (content.get("canonicalUrl") or {}).get("url") or entry.get("link", "")
        publisher = (content.get("provider") or {}).get("displayName") or entry.get("publisher", "")
        items.append(
            NewsItem(
                title=title,
                publisher=publisher,
                link=link,
                sentiment=score_headline(title),
                is_market_moving=is_market_moving(title),
            )
        )
    return items


@st.cache_data(ttl=CACHE_TTL_TICKER_RESEARCH, show_spinner=False)
def get_snapshot(symbol: str) -> TickerSnapshot:
    symbol = symbol.strip().upper()
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        fast = ticker.fast_info

        price = fast.get("last_price")
        prev_close = fast.get("previous_close")
        change_pct = ((price - prev_close) / prev_close * 100) if price and prev_close else None

        analyst = AnalystView(
            recommendation=info.get("recommendationKey"),
            num_analysts=info.get("numberOfAnalystOpinions"),
            target_mean=info.get("targetMeanPrice"),
            target_high=info.get("targetHighPrice"),
            target_low=info.get("targetLowPrice"),
        )

        return TickerSnapshot(
            symbol=symbol,
            name=info.get("longName") or info.get("shortName"),
            price=float(price) if price is not None else None,
            change_pct=change_pct,
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            week52_high=info.get("fiftyTwoWeekHigh"),
            week52_low=info.get("fiftyTwoWeekLow"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            analyst=analyst,
            news=_extract_news(ticker.news or []),
        )
    except Exception as exc:
        return TickerSnapshot(
            symbol=symbol, name=None, price=None, change_pct=None, market_cap=None,
            pe_ratio=None, week52_high=None, week52_low=None, sector=None, industry=None,
            analyst=_empty_analyst(), news=[], error=str(exc),
        )
