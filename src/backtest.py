"""Strategy backtesting: historical data, indicators, signal generation, and trade simulation.

Supports a handful of common rule-based strategies (moving-average crossovers,
RSI mean reversion, MACD, Bollinger Bands) plus a buy-and-hold benchmark. Each
strategy produces a daily position series (1.0 = fully invested, 0.0 = flat);
`run_backtest` turns that into an equity curve, a trade log, and performance
metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from src.config import CACHE_TTL_HISTORY

TRADING_DAYS_PER_YEAR = 252


@st.cache_data(ttl=CACHE_TTL_HISTORY, show_spinner=False)
def fetch_history(ticker: str, start: date, end: date, interval: str = "1d") -> pd.DataFrame:
    """Fetch daily OHLCV history for a single ticker, adjusted for splits/dividends."""
    df = yf.download(
        ticker, start=start, end=end, interval=interval, auto_adjust=True, progress=False
    )
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(how="all")


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series]:
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line


def bollinger_bands(
    series: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    mid = sma(series, window)
    std = series.rolling(window).std()
    return mid - num_std * std, mid, mid + num_std * std


def rolling_vwap(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Rolling volume-weighted average price over a trailing window of bars.

    Uses the typical price (H+L+C)/3 per bar, weighted by that bar's volume.
    This is a *rolling* VWAP (not a session-anchored intraday VWAP), which is
    the sensible reading of "VWAP" on daily bars.
    """
    typical_price = (df["High"] + df["Low"] + df["Close"]) / 3
    price_volume = typical_price * df["Volume"]
    return price_volume.rolling(window).sum() / df["Volume"].rolling(window).sum()


def rolling_poc(df: pd.DataFrame, window: int = 20, bins: int = 24) -> pd.Series:
    """Rolling volume-profile Point of Control: the price bin with the most
    traded volume over a trailing window of bars, recomputed at each bar
    using only data available up to (and including) that bar.
    """
    close = df["Close"]
    volume = df["Volume"]
    poc = pd.Series(np.nan, index=df.index)

    for i in range(window - 1, len(df)):
        prices = close.iloc[i - window + 1 : i + 1].to_numpy()
        vols = volume.iloc[i - window + 1 : i + 1].to_numpy()
        lo, hi = prices.min(), prices.max()
        if hi == lo:
            poc.iloc[i] = lo
            continue
        edges = np.linspace(lo, hi, bins + 1)
        bin_idx = np.clip(np.digitize(prices, edges) - 1, 0, bins - 1)
        vol_by_bin = np.bincount(bin_idx, weights=vols, minlength=bins)
        top_bin = vol_by_bin.argmax()
        poc.iloc[i] = (edges[top_bin] + edges[top_bin + 1]) / 2

    return poc


# ---------------------------------------------------------------------------
# Strategies -- each returns a position series: 1.0 = fully long, 0.0 = flat
# ---------------------------------------------------------------------------


def strategy_sma_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> pd.Series:
    close = df["Close"]
    position = (sma(close, fast) > sma(close, slow)).astype(float)
    return position.where(sma(close, slow).notna(), 0.0)


def strategy_ema_crossover(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.Series:
    close = df["Close"]
    position = (ema(close, fast) > ema(close, slow)).astype(float)
    return position


def strategy_rsi_mean_reversion(
    df: pd.DataFrame, window: int = 14, oversold: float = 30, overbought: float = 70
) -> pd.Series:
    r = rsi(df["Close"], window)
    position = pd.Series(np.nan, index=df.index)
    position[r < oversold] = 1.0
    position[r > overbought] = 0.0
    return position.ffill().fillna(0.0)


def strategy_macd_crossover(
    df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.Series:
    macd_line, signal_line = macd(df["Close"], fast, slow, signal)
    return (macd_line > signal_line).astype(float)


def strategy_bollinger_reversion(
    df: pd.DataFrame, window: int = 20, num_std: float = 2.0
) -> pd.Series:
    close = df["Close"]
    lower, mid, _ = bollinger_bands(close, window, num_std)
    position = pd.Series(np.nan, index=df.index)
    position[close < lower] = 1.0
    position[close > mid] = 0.0
    return position.ffill().fillna(0.0)


def strategy_vwap_poc_crossover(
    df: pd.DataFrame, vwap_window: int = 20, profile_window: int = 20, bins: int = 24
) -> pd.Series:
    vwap = rolling_vwap(df, vwap_window)
    poc = rolling_poc(df, profile_window, bins)
    return (vwap > poc).astype(float)


def strategy_buy_and_hold(df: pd.DataFrame) -> pd.Series:
    return pd.Series(1.0, index=df.index)


# UI metadata for each strategy: the function, its tunable params
# (key -> (label, min, max, default)), and a one-line description.
STRATEGIES: dict[str, dict] = {
    "SMA Crossover": {
        "fn": strategy_sma_crossover,
        "params": {
            "fast": ("Fast SMA window (days)", 5, 100, 20),
            "slow": ("Slow SMA window (days)", 10, 250, 50),
        },
        "description": (
            "Buy when the fast simple moving average crosses above the slow one "
            "(a 'golden cross'); sell when it crosses back below."
        ),
    },
    "EMA Crossover": {
        "fn": strategy_ema_crossover,
        "params": {
            "fast": ("Fast EMA span (days)", 3, 60, 12),
            "slow": ("Slow EMA span (days)", 10, 200, 26),
        },
        "description": (
            "Buy when the fast exponential moving average is above the slow one; "
            "sell when it drops below. Reacts faster than an SMA crossover."
        ),
    },
    "RSI Mean Reversion": {
        "fn": strategy_rsi_mean_reversion,
        "params": {
            "window": ("RSI window (days)", 5, 50, 14),
            "oversold": ("Buy when RSI drops below", 5, 45, 30),
            "overbought": ("Sell when RSI rises above", 55, 95, 70),
        },
        "description": (
            "Buy when RSI signals oversold conditions; sell once it recovers "
            "past the overbought line."
        ),
    },
    "MACD Crossover": {
        "fn": strategy_macd_crossover,
        "params": {
            "fast": ("Fast EMA (days)", 5, 30, 12),
            "slow": ("Slow EMA (days)", 15, 60, 26),
            "signal": ("Signal EMA (days)", 3, 20, 9),
        },
        "description": "Buy when the MACD line crosses above its signal line; sell on the reverse cross.",
    },
    "Bollinger Band Reversion": {
        "fn": strategy_bollinger_reversion,
        "params": {
            "window": ("Band window (days)", 5, 60, 20),
            "num_std": ("Std. deviations", 1.0, 3.5, 2.0),
        },
        "description": (
            "Buy when price closes below the lower band (oversold vs. its own "
            "range); sell once it closes back above the middle band."
        ),
    },
    "VWAP / Volume Profile POC Crossover": {
        "fn": strategy_vwap_poc_crossover,
        "params": {
            "vwap_window": ("VWAP lookback (days)", 5, 100, 20),
            "profile_window": ("Volume profile lookback (days)", 10, 100, 20),
            "bins": ("Volume profile price bins", 10, 50, 24),
        },
        "description": (
            "Buy when the rolling VWAP crosses above the rolling volume-profile "
            "Point of Control (the price level with the most traded volume over "
            "the lookback window); sell when VWAP crosses back below it."
        ),
    },
    "Buy & Hold (benchmark)": {
        "fn": strategy_buy_and_hold,
        "params": {},
        "description": "Always fully invested. Useful as a baseline to see whether an active strategy beats simply holding.",
    },
}


# ---------------------------------------------------------------------------
# Backtest engine
# ---------------------------------------------------------------------------


@dataclass
class Trade:
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    return_pct: float


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    benchmark_curve: pd.Series
    position: pd.Series
    trades: list[Trade]
    total_return_pct: float
    cagr_pct: float
    max_drawdown_pct: float
    sharpe: float
    win_rate_pct: float
    num_trades: int
    benchmark_return_pct: float


def run_backtest(
    df: pd.DataFrame,
    position: pd.Series,
    initial_capital: float = 10_000.0,
    commission_pct: float = 0.0,
) -> BacktestResult:
    """Simulate trading a position series against daily closes.

    Signals are executed on the *next* bar's return (position is shifted by
    one day) so the backtest doesn't trade on information not yet available
    at the close that generated the signal.
    """
    close = df["Close"]
    daily_return = close.pct_change().fillna(0.0)

    executed_position = position.shift(1).fillna(0.0)
    position_change = executed_position.diff().abs()
    position_change.iloc[0] = executed_position.iloc[0]

    strategy_return = executed_position * daily_return - position_change * (commission_pct / 100)

    equity_curve = initial_capital * (1 + strategy_return).cumprod()
    benchmark_curve = initial_capital * (1 + daily_return).cumprod()

    trades = _extract_trades(close, executed_position)

    total_return_pct = (equity_curve.iloc[-1] / initial_capital - 1) * 100
    benchmark_return_pct = (benchmark_curve.iloc[-1] / initial_capital - 1) * 100

    num_years = (close.index[-1] - close.index[0]).days / 365.25
    cagr_pct = (
        ((equity_curve.iloc[-1] / initial_capital) ** (1 / num_years) - 1) * 100
        if num_years > 0
        else 0.0
    )

    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    max_drawdown_pct = float(drawdown.min() * 100)

    sharpe = _sharpe_ratio(strategy_return)

    wins = [t for t in trades if t.return_pct > 0]
    win_rate_pct = (len(wins) / len(trades) * 100) if trades else 0.0

    return BacktestResult(
        equity_curve=equity_curve,
        benchmark_curve=benchmark_curve,
        position=executed_position,
        trades=trades,
        total_return_pct=float(total_return_pct),
        cagr_pct=float(cagr_pct),
        max_drawdown_pct=max_drawdown_pct,
        sharpe=sharpe,
        win_rate_pct=win_rate_pct,
        num_trades=len(trades),
        benchmark_return_pct=float(benchmark_return_pct),
    )


def _extract_trades(close: pd.Series, position: pd.Series) -> list[Trade]:
    """Turn a 0/1 position series into a list of discrete round-trip trades."""
    trades: list[Trade] = []
    in_position = False
    entry_date = None
    entry_price = None

    for dt, pos in position.items():
        if pos > 0 and not in_position:
            in_position = True
            entry_date = dt
            entry_price = close.loc[dt]
        elif pos == 0 and in_position:
            in_position = False
            exit_price = close.loc[dt]
            trades.append(
                Trade(
                    entry_date=entry_date,
                    exit_date=dt,
                    entry_price=float(entry_price),
                    exit_price=float(exit_price),
                    return_pct=float((exit_price / entry_price - 1) * 100),
                )
            )

    if in_position:
        exit_price = close.iloc[-1]
        trades.append(
            Trade(
                entry_date=entry_date,
                exit_date=close.index[-1],
                entry_price=float(entry_price),
                exit_price=float(exit_price),
                return_pct=float((exit_price / entry_price - 1) * 100),
            )
        )

    return trades


def _sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.0) -> float:
    excess = daily_returns - risk_free_rate / TRADING_DAYS_PER_YEAR
    std = excess.std()
    if not std or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(TRADING_DAYS_PER_YEAR))
