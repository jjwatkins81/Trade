"""Central configuration for the trading dashboard: watchlist, news sources, weights."""

# Key indicators shown on the Market Overview panel.
# (display label, yfinance ticker symbol)
INDICATORS = [
    ("S&P 500", "^GSPC"),
    ("Nasdaq 100", "^NDX"),
    ("QQQ", "QQQ"),
    ("SPY", "SPY"),
    ("Dow Jones", "^DJI"),
    ("Russell 2000", "IWM"),
    ("VIX", "^VIX"),
    ("10Y Yield", "^TNX"),
]

# Underlyings we can compute gamma exposure for. Kept small since options
# chains are the heaviest thing this app fetches.
GEX_TICKERS = ["SPY", "QQQ"]

# Only pull expirations within this many days out, and cap how many we pull,
# to keep the dashboard responsive (gamma exposure is dominated by near-dated
# options anyway).
GEX_MAX_DAYS_OUT = 45
GEX_MAX_EXPIRIES = 6
GEX_RISK_FREE_RATE = 0.045

# Free, no-API-key financial news RSS feeds.
NEWS_FEEDS = {
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "CNBC Top News": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "MarketWatch Top Stories": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Investing.com": "https://www.investing.com/rss/news_301.rss",
}

MAX_HEADLINES_PER_FEED = 15

# How long fetched data stays cached (seconds).
CACHE_TTL_QUOTES = 60
CACHE_TTL_NEWS = 15 * 60
CACHE_TTL_OPTIONS = 10 * 60

# Composite sentiment score weights (must sum to 1.0).
SENTIMENT_WEIGHTS = {
    "news": 0.4,
    "breadth": 0.3,
    "vix": 0.2,
    "gamma": 0.1,
}
