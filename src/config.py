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

# Default underlyings for gamma exposure: the most liquid broad-market
# proxies, where the GEX estimate is most reliable (deep open interest,
# consistent dealer hedging). Users can add any other ticker in the app;
# single-stock GEX is noisier the less liquid the options market is.
GEX_TICKERS = ["SPY", "QQQ", "IWM"]

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

# Volatility screener: NYSE stocks under SCREENER_MAX_PRICE whose average
# true range over the lookback is at least SCREENER_MIN_MOVE dollars.
SCREENER_MAX_PRICE = 500.0
SCREENER_MIN_MOVE = 10.0
SCREENER_LOOKBACK_DAYS = 30
CACHE_TTL_SCREENER = 30 * 60

# Liquid NYSE-listed large caps to scan. Anything over the price cap is
# simply filtered out, so it's fine for this list to include pricier names
# (they'll show up if they split or pull back). Listings occasionally move
# between exchanges; the screener re-checks each match's exchange live.
SCREENER_UNIVERSE = [
    # Industrials / aerospace / defense
    "CAT", "DE", "GE", "GEV", "BA", "LMT", "NOC", "GD", "RTX", "HON",
    "UNP", "PH", "ETN", "TT", "ROK", "EME", "URI", "VRT", "HWM", "FDX",
    # Financials
    "GS", "JPM", "MS", "AXP", "V", "MA", "SPGI", "MCO", "MSCI", "BLK",
    "TRV", "CB", "PGR", "MMC", "AON", "AMP", "COF",
    # Health care
    "UNH", "ELV", "CI", "HUM", "HCA", "TMO", "DHR", "SYK", "LLY", "JNJ",
    "ABBV", "MRK", "ZTS", "MCK", "COR",
    # Tech / communication (NYSE-listed)
    "IBM", "ORCL", "CRM", "NOW", "ANET", "ACN", "SNOW", "HUBS", "DELL",
    "TSM", "BABA", "SPOT", "MSI", "DIS",
    # Consumer
    "HD", "LOW", "MCD", "TGT", "DECK", "RCL", "NKE", "CVNA",
    # Energy / materials
    "CVX", "XOM", "COP", "SHW", "APD", "ECL", "NUE", "MLM", "VMC",
]
