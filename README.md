# Market Sentiment Dashboard

A simple, self-hosted dashboard for a quick daily read on market conditions:

- **Overall sentiment gauge** — a composite score blending news tone, market
  breadth, VIX, and the gamma regime.
- **Key indicators** — SPX, NDX, QQQ, SPY, DJI, IWM, VIX, 10Y yield.
- **Gamma Exposure (GEX)** — an estimate of dealer gamma positioning for
  SPY/QQQ/IWM by default, used as a volatility regime indicator (negative
  gamma = hedging flow tends to amplify moves; positive gamma = it tends to
  dampen them). Add any other ticker from the app to check GEX on a stock
  you actually trade -- just note single-stock GEX is noisier than index
  GEX, since less liquid options mean thinner open interest and less
  consistent dealer hedging.
- **News & sentiment** — recent financial headlines from free RSS feeds,
  scored with VADER sentiment, with a "market-moving" filter for
  Fed/inflation/jobs/earnings-type stories.

This is intentionally simple and self-contained: no accounts, no paid data
subscriptions, no database. Everything is fetched live each time you load
the page (and cached briefly to stay fast) -- or flip on "Auto-refresh every
1 min" to have it pull fresh data on a timer without you touching anything.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Then open the local URL Streamlit prints (usually http://localhost:8501).

### Or: run it as a standalone executable (no Python required)

See [`packaging/README.md`](packaging/README.md) to build a single `.exe`
(Windows) or binary (macOS/Linux) that bundles everything -- just
double-click it and it opens the dashboard in your browser.

## How it works

| Panel | Source | Notes |
|---|---|---|
| Indicators | `yfinance` | Delayed quotes, no API key needed |
| News | RSS feeds (Yahoo Finance, CNBC, MarketWatch, Investing.com) | See `src/config.py` to add/remove feeds |
| Sentiment | VADER (`vaderSentiment`) | Lightweight lexicon-based scoring of headlines |
| GEX | `yfinance` options chains + Black-Scholes gamma | See `src/gex.py` docstring for the methodology and its assumptions |

### On GEX specifically

Gamma exposure here is a **modeled estimate**, not exchange-reported dealer
positioning (that data is proprietary — e.g. SpotGamma, SqueezeMetrics). It
assumes dealers are net long gamma from calls and net short gamma from puts,
which is a common industry heuristic but not always literally true. Treat it
as a volatility-regime signal, not a precise read on positioning:

- **Positive net GEX**: dealers hedge by buying dips / selling rallies →
  tends to dampen realized volatility ("pinning").
- **Negative net GEX**: dealers hedge by selling into drops / buying into
  rallies → tends to amplify realized volatility → bigger, faster swings.

## Configuration

Edit `src/config.py` to change:

- `INDICATORS` — tickers shown in the Key Indicators panel
- `GEX_TICKERS` — underlyings to compute gamma exposure for
- `NEWS_FEEDS` — RSS sources
- `SENTIMENT_WEIGHTS` — how the composite score blends news/breadth/VIX/gamma
- cache TTLs, GEX expiration window, etc.

## Roadmap ideas

Kept out of this first pass on purpose, to keep things simple:

- Historical charts / trend lines instead of just current snapshot
- Watchlist for individual positions, not just index-level indicators
- Alerts (e.g. notify when gamma flips negative, or VIX crosses a threshold)
- Swap free RSS/yfinance for a paid data provider if reliability becomes an issue

## Disclaimer

This tool is for informational purposes only and is not financial advice.
Quotes may be delayed. Gamma exposure is a heuristic estimate, not verified
dealer positioning.
