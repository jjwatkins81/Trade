"""Gamma Exposure (GEX) estimation from live options chains.

GEX approximates how much stock dealers must buy/sell to stay delta-hedged
as the underlying moves, which is a good proxy for expected volatility:

- Positive net GEX: dealers are net long gamma. As price rises they sell
  into strength, and as it falls they buy the dip -> hedging flow dampens
  moves -> lower realized volatility ("pinning").
- Negative net GEX: dealers are net short gamma. They must sell as price
  falls and buy as price rises -> hedging flow amplifies moves -> higher
  realized volatility, bigger/faster swings in both directions.

This is the common retail approximation (e.g. as popularized by
SqueezeMetrics/SpotGamma-style trackers): it assumes dealers are long
gamma from calls and short gamma from puts, which is not always literally
true but is a reasonable, well-known heuristic -- treat GEX as a regime
indicator, not a precise dealer-position readout.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import yfinance as yf
from scipy.stats import norm

from src.config import (
    CACHE_TTL_OPTIONS,
    GEX_MAX_DAYS_OUT,
    GEX_MAX_EXPIRIES,
    GEX_RISK_FREE_RATE,
)

CONTRACT_MULTIPLIER = 100


@dataclass
class GexResult:
    symbol: str
    spot: float
    net_gex: float
    call_gex: float
    put_gex: float
    by_strike: pd.DataFrame  # columns: strike, call_gex, put_gex, net_gex
    flip_point: float | None  # approximate strike where net GEX crosses zero
    expiries_used: list[str]
    as_of: datetime


def _bs_gamma(spot: float, strike: float, t_years: float, iv: float, r: float) -> float:
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (r + 0.5 * iv**2) * t_years) / (iv * math.sqrt(t_years))
    return norm.pdf(d1) / (spot * iv * math.sqrt(t_years))


def _dollar_gamma(row, spot: float, t_years: float, r: float, sign: int) -> float:
    iv = row.get("impliedVolatility", 0.0) or 0.0
    oi = row.get("openInterest", 0.0) or 0.0
    if oi <= 0 or iv <= 0:
        return 0.0
    gamma = _bs_gamma(spot, row["strike"], t_years, iv, r)
    # Dollar gamma exposure per 1% move in the underlying.
    return sign * gamma * oi * CONTRACT_MULTIPLIER * spot**2 * 0.01


@st.cache_data(ttl=CACHE_TTL_OPTIONS, show_spinner=False)
def compute_gex(symbol: str) -> GexResult | None:
    ticker = yf.Ticker(symbol)

    try:
        spot = float(ticker.fast_info["last_price"])
    except Exception:
        return None

    try:
        all_expiries = ticker.options
    except Exception:
        return None
    if not all_expiries:
        return None

    now = datetime.now(timezone.utc)
    usable_expiries = []
    for exp in all_expiries:
        exp_date = datetime.strptime(exp, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days_out = (exp_date - now).days
        if 0 <= days_out <= GEX_MAX_DAYS_OUT:
            usable_expiries.append((exp, exp_date))
    usable_expiries = usable_expiries[:GEX_MAX_EXPIRIES]
    if not usable_expiries:
        return None

    strike_rows: dict[float, dict[str, float]] = {}
    call_gex_total = 0.0
    put_gex_total = 0.0

    for exp, exp_date in usable_expiries:
        try:
            chain = ticker.option_chain(exp)
        except Exception:
            continue

        t_years = max((exp_date - now).total_seconds(), 3600) / (365 * 24 * 3600)

        for _, row in chain.calls.iterrows():
            g = _dollar_gamma(row, spot, t_years, GEX_RISK_FREE_RATE, sign=1)
            call_gex_total += g
            bucket = strike_rows.setdefault(row["strike"], {"call_gex": 0.0, "put_gex": 0.0})
            bucket["call_gex"] += g

        for _, row in chain.puts.iterrows():
            g = _dollar_gamma(row, spot, t_years, GEX_RISK_FREE_RATE, sign=1)
            put_gex_total += g
            bucket = strike_rows.setdefault(row["strike"], {"call_gex": 0.0, "put_gex": 0.0})
            bucket["put_gex"] += g

    if not strike_rows:
        return None

    # Dealers assumed long gamma via calls, short gamma via puts.
    net_gex = call_gex_total - put_gex_total

    by_strike = (
        pd.DataFrame(
            [
                {"strike": k, "call_gex": v["call_gex"], "put_gex": -v["put_gex"]}
                for k, v in strike_rows.items()
            ]
        )
        .sort_values("strike")
        .reset_index(drop=True)
    )
    by_strike["net_gex"] = by_strike["call_gex"] + by_strike["put_gex"]

    flip_point = _estimate_flip_point(by_strike)

    return GexResult(
        symbol=symbol,
        spot=spot,
        net_gex=net_gex,
        call_gex=call_gex_total,
        put_gex=-put_gex_total,
        by_strike=by_strike,
        flip_point=flip_point,
        expiries_used=[exp for exp, _ in usable_expiries],
        as_of=now,
    )


def _estimate_flip_point(by_strike: pd.DataFrame) -> float | None:
    """Linear-interpolate the strike where cumulative net GEX crosses zero."""
    if by_strike.empty:
        return None
    cum = by_strike["net_gex"].cumsum()
    signs = cum > 0
    for i in range(1, len(signs)):
        if signs.iloc[i] != signs.iloc[i - 1]:
            x0, x1 = by_strike["strike"].iloc[i - 1], by_strike["strike"].iloc[i]
            y0, y1 = cum.iloc[i - 1], cum.iloc[i]
            if y1 == y0:
                return x1
            return x0 + (0 - y0) * (x1 - x0) / (y1 - y0)
    return None


def regime_label(net_gex: float) -> str:
    return "Negative Gamma (higher volatility expected)" if net_gex < 0 else "Positive Gamma (volatility dampened)"
