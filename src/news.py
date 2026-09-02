"""Headline fetching + sentiment scoring for the news panel."""

from dataclasses import dataclass
from datetime import datetime, timezone
from time import mktime

import feedparser
import streamlit as st
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from src.config import CACHE_TTL_NEWS, MAX_HEADLINES_PER_FEED, NEWS_FEEDS

_analyzer = SentimentIntensityAnalyzer()

# VADER's general-purpose lexicon misses a lot of finance-specific vocabulary
# (e.g. "rally", "plunge", "selloff" aren't scored at all) and scores some
# words in a way that's misleading for markets (e.g. "cut" reads as
# generically negative, even in a bullish "rate cut" headline). Patch in a
# small finance-domain lexicon to make headline scoring more meaningful.
_FINANCE_LEXICON = {
    # bullish
    "rally": 2.3, "rallies": 2.3, "rallying": 2.3,
    "surge": 2.5, "surges": 2.5, "surging": 2.5,
    "soar": 2.6, "soars": 2.6, "soaring": 2.6,
    "rebound": 1.8, "rebounds": 1.8, "rebounding": 1.8,
    "rebounded": 1.8,
    "beat": 1.5, "beats": 1.5, "outperform": 1.8, "outperforms": 1.8,
    "upgrade": 1.6, "upgrades": 1.6, "upgraded": 1.6,
    "bullish": 2.0, "record high": 2.0,
    # bearish
    "plunge": -2.5, "plunges": -2.5, "plunging": -2.5,
    "tumble": -2.2, "tumbles": -2.2, "tumbling": -2.2,
    "slump": -2.0, "slumps": -2.0, "slumping": -2.0,
    "selloff": -2.2, "sell-off": -2.2,
    "rout": -2.3, "slide": -1.6, "slides": -1.6, "sliding": -1.6,
    "miss": -1.5, "misses": -1.5, "underperform": -1.8, "underperforms": -1.8,
    "downgrade": -1.6, "downgrades": -1.6, "downgraded": -1.6,
    "bearish": -2.0, "layoffs": -2.0, "default": -1.8,
    # ambiguous without context -- neutralize rather than mis-signal
    "cut": 0.0, "cuts": 0.0, "cutting": 0.0,
}
_analyzer.lexicon.update(_FINANCE_LEXICON)

# Headlines mentioning these are surfaced as "market moving" regardless of
# sentiment score, since Fed/rate/inflation news drives volatility either way.
MARKET_MOVING_KEYWORDS = [
    "fed", "federal reserve", "rate cut", "rate hike", "interest rate",
    "inflation", "cpi", "ppi", "jobs report", "nonfarm payroll", "unemployment",
    "recession", "gdp", "tariff", "earnings", "fomc", "powell", "treasury",
    "yield", "shutdown", "war", "geopolitical", "opec", "oil price",
]


@dataclass
class Headline:
    title: str
    source: str
    link: str
    published: datetime | None
    sentiment: float  # VADER compound score, [-1, 1]
    is_market_moving: bool


def _score(title: str) -> float:
    return _analyzer.polarity_scores(title)["compound"]


def _is_market_moving(title: str) -> bool:
    lowered = title.lower()
    return any(kw in lowered for kw in MARKET_MOVING_KEYWORDS)


def _parse_published(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        value = entry.get(field)
        if value:
            return datetime.fromtimestamp(mktime(value), tz=timezone.utc)
    return None


@st.cache_data(ttl=CACHE_TTL_NEWS, show_spinner=False)
def fetch_headlines() -> list[Headline]:
    headlines: list[Headline] = []
    for source, url in NEWS_FEEDS.items():
        try:
            parsed = feedparser.parse(url)
        except Exception:
            continue
        for entry in parsed.entries[:MAX_HEADLINES_PER_FEED]:
            title = entry.get("title", "").strip()
            if not title:
                continue
            headlines.append(
                Headline(
                    title=title,
                    source=source,
                    link=entry.get("link", ""),
                    published=_parse_published(entry),
                    sentiment=_score(title),
                    is_market_moving=_is_market_moving(title),
                )
            )

    headlines.sort(key=lambda h: h.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return headlines


def average_sentiment(headlines: list[Headline]) -> float:
    """Mean VADER compound score across headlines, in [-1, 1]. 0.0 if none."""
    if not headlines:
        return 0.0
    return sum(h.sentiment for h in headlines) / len(headlines)


def sentiment_label(score: float) -> str:
    if score >= 0.15:
        return "Bullish"
    if score <= -0.15:
        return "Bearish"
    return "Neutral"
