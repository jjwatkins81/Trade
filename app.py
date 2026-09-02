"""Simple market-sentiment dashboard: indicators, news sentiment, and gamma exposure.

Run with:  streamlit run app.py
"""

from datetime import datetime, timezone

import plotly.graph_objects as go
import streamlit as st

from src.config import GEX_TICKERS, INDICATORS
from src.gex import compute_gex, regime_label
from src.market_data import fetch_quotes, market_breadth_score, quotes_to_dataframe
from src.news import average_sentiment, fetch_headlines, sentiment_label
from src.sentiment import composite_sentiment

st.set_page_config(page_title="Market Sentiment Dashboard", layout="wide")

st.title("📊 Market Sentiment Dashboard")
st.caption(
    "Not financial advice. Quotes are delayed/best-effort from Yahoo Finance; "
    "gamma exposure is a modeled estimate, not exchange-reported dealer positioning."
)

# ---------------------------------------------------------------------------
# Controls that affect how the dashboard below runs -- kept outside the
# fragment so changing them triggers a full rerun (needed to pick up a new
# auto-refresh interval or ticker list).
# ---------------------------------------------------------------------------
if "custom_gex_tickers" not in st.session_state:
    st.session_state.custom_gex_tickers = []

control_col, ticker_col = st.columns([1, 2])

with control_col:
    auto_refresh = st.toggle("Auto-refresh every 1 min", value=False)

with ticker_col:
    with st.expander("➕ Track another ticker for Gamma Exposure"):
        new_ticker = st.text_input(
            "Ticker symbol", key="new_gex_ticker", placeholder="e.g. AAPL"
        ).strip().upper()
        if st.button("Add") and new_ticker:
            if new_ticker not in GEX_TICKERS and new_ticker not in st.session_state.custom_gex_tickers:
                st.session_state.custom_gex_tickers.append(new_ticker)

        if st.session_state.custom_gex_tickers:
            st.session_state.custom_gex_tickers = st.multiselect(
                "Currently tracking (uncheck to remove)",
                options=st.session_state.custom_gex_tickers,
                default=st.session_state.custom_gex_tickers,
            )
        st.caption(
            "Single-stock GEX is noisier than index GEX -- less liquid options "
            "mean thinner open interest and less consistent dealer hedging."
        )

all_gex_tickers = list(GEX_TICKERS) + [
    t for t in st.session_state.custom_gex_tickers if t not in GEX_TICKERS
]


@st.fragment(run_every=60 if auto_refresh else None)
def render_dashboard() -> None:
    if st.button("🔄 Refresh now"):
        st.cache_data.clear()

    # -------------------------------------------------------------------
    # Load data
    # -------------------------------------------------------------------
    with st.spinner("Loading market data..."):
        quotes = fetch_quotes()

    with st.spinner("Loading news..."):
        headlines = fetch_headlines()

    gex_results = {}
    with st.spinner("Loading options / gamma exposure..."):
        for sym in all_gex_tickers:
            gex_results[sym] = compute_gex(sym)

    # -------------------------------------------------------------------
    # Overall sentiment gauge
    # -------------------------------------------------------------------
    vix_quote = next((q for q in quotes if q.symbol == "^VIX"), None)
    primary_gex = gex_results.get(GEX_TICKERS[0])

    news_score = average_sentiment(headlines)
    breadth_score = market_breadth_score(quotes)
    composite = composite_sentiment(
        news_score=news_score,
        breadth_score=breadth_score,
        vix_level=vix_quote.price if vix_quote else float("nan"),
        vix_change_pct=vix_quote.change_pct if vix_quote else 0.0,
        net_gex=primary_gex.net_gex if primary_gex else None,
    )

    col_gauge, col_breakdown = st.columns([1, 2])

    with col_gauge:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=composite.score,
                number={"valueformat": ".2f"},
                title={"text": f"Overall Sentiment: {composite.label}"},
                gauge={
                    "axis": {"range": [-1, 1]},
                    "bar": {"color": "black"},
                    "steps": [
                        {"range": [-1, -0.15], "color": "#f4a3a3"},
                        {"range": [-0.15, 0.15], "color": "#f2e28a"},
                        {"range": [0.15, 1], "color": "#a6e3a1"},
                    ],
                },
            )
        )
        fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=10))
        st.plotly_chart(fig, width='stretch')

    with col_breakdown:
        st.subheader("What's driving it")
        st.markdown(
            f"""
- **News sentiment** ({news_score:+.2f}): average tone of the latest {len(headlines)} financial headlines
- **Market breadth** ({breadth_score:+.2f}): {"more" if breadth_score > 0 else "fewer"} tracked indexes up than down today
- **VIX** ({f"{vix_quote.price:.1f}" if vix_quote and vix_quote.price == vix_quote.price else "n/a"}): level + today's move
- **Gamma regime**: {regime_label(primary_gex.net_gex) if primary_gex else "unavailable"} on {GEX_TICKERS[0]}
            """
        )

    st.divider()

    # -------------------------------------------------------------------
    # Key indicators
    # -------------------------------------------------------------------
    st.header("Key Indicators")
    df = quotes_to_dataframe(quotes)
    cols = st.columns(4)
    for i, row in df.iterrows():
        with cols[i % 4]:
            st.metric(
                label=f"{row['Indicator']} ({row['Symbol']})",
                value=f"{row['Price']:.2f}" if row["Price"] == row["Price"] else "n/a",
                delta=f"{row['Change %']:+.2f}%" if row["Change %"] == row["Change %"] else None,
            )

    st.divider()

    # -------------------------------------------------------------------
    # Gamma exposure
    # -------------------------------------------------------------------
    st.header("Gamma Exposure (GEX)")
    st.markdown(
        """
**What this means:** Gamma Exposure estimates how much stock options dealers must
buy or sell to stay hedged as the underlying price moves.
- **Positive net GEX** → dealers are net long gamma → they buy dips and sell
  rallies → this hedging flow tends to *dampen* volatility.
- **Negative net GEX** → dealers are net short gamma → they must sell as price
  falls and buy as price rises → this hedging flow tends to *amplify*
  volatility, producing faster/bigger moves in both directions.
"""
    )

    gex_tabs = st.tabs(all_gex_tickers)
    for tab, sym in zip(gex_tabs, all_gex_tickers):
        with tab:
            result = gex_results.get(sym)
            if result is None:
                st.warning(f"Couldn't load options data for {sym} right now.")
                continue

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Spot", f"{result.spot:.2f}")
            m2.metric("Net GEX ($/1% move)", f"{result.net_gex:,.0f}")
            m3.metric("Regime", "Negative" if result.net_gex < 0 else "Positive")
            m4.metric(
                "Flip point",
                f"{result.flip_point:.1f}" if result.flip_point else "n/a",
                help="Approximate spot level where net gamma flips sign.",
            )

            bar_fig = go.Figure()
            bar_fig.add_bar(x=result.by_strike["strike"], y=result.by_strike["call_gex"], name="Call GEX")
            bar_fig.add_bar(x=result.by_strike["strike"], y=result.by_strike["put_gex"], name="Put GEX")
            bar_fig.add_vline(x=result.spot, line_dash="dash", annotation_text="Spot")
            if result.flip_point:
                bar_fig.add_vline(x=result.flip_point, line_dash="dot", line_color="purple", annotation_text="Flip")
            bar_fig.update_layout(
                barmode="relative",
                title=f"{sym} Gamma Exposure by Strike",
                xaxis_title="Strike",
                yaxis_title="Dollar Gamma ($/1% move)",
                height=400,
            )
            st.plotly_chart(bar_fig, width='stretch')

            st.caption(
                f"Based on {len(result.expiries_used)} expiration(s) within the near-dated window: "
                f"{', '.join(result.expiries_used)}"
            )

    st.divider()

    # -------------------------------------------------------------------
    # News
    # -------------------------------------------------------------------
    st.header("News & Sentiment")

    market_moving = [h for h in headlines if h.is_market_moving]
    if market_moving:
        st.subheader("⚡ Market-moving headlines")
        for h in market_moving[:10]:
            tone = "🟢" if h.sentiment > 0.15 else "🔴" if h.sentiment < -0.15 else "⚪"
            ts = h.published.strftime("%H:%M UTC") if h.published else ""
            st.markdown(f"{tone} [{h.title}]({h.link}) — *{h.source}* {ts}")

    st.subheader("Latest headlines")
    label_filter = st.selectbox("Filter by tone", ["All", "Bullish", "Neutral", "Bearish"])
    for h in headlines[:40]:
        tone_label = sentiment_label(h.sentiment)
        if label_filter != "All" and tone_label != label_filter:
            continue
        tone = "🟢" if h.sentiment > 0.15 else "🔴" if h.sentiment < -0.15 else "⚪"
        ts = h.published.strftime("%Y-%m-%d %H:%M UTC") if h.published else ""
        st.markdown(f"{tone} [{h.title}]({h.link}) — *{h.source}* {ts}")

    st.caption(f"Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")


render_dashboard()
