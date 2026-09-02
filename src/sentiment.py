"""Composite "overall market sentiment" score blending news, breadth, VIX and gamma."""

from dataclasses import dataclass

from src.config import SENTIMENT_WEIGHTS


@dataclass
class CompositeSentiment:
    score: float  # [-1, 1]
    label: str
    components: dict[str, float]


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def vix_component(vix_level: float, vix_change_pct: float) -> float:
    """Turn VIX level + day's move into a [-1, 1] sentiment contribution.

    Low, falling VIX -> bullish contribution. High, rising VIX -> bearish.
    """
    if vix_level != vix_level:  # NaN
        return 0.0
    # Level: <15 calm/bullish, >30 fearful/bearish, linear between 15-30 around 0.
    level_score = _clamp((22.5 - vix_level) / 12.5)
    move_score = _clamp(-vix_change_pct / 5.0)
    return _clamp(0.6 * level_score + 0.4 * move_score)


def gamma_component(net_gex: float | None) -> float:
    """Negative gamma isn't inherently bearish, but it does mean more expected
    volatility / larger swings, which we treat as a mild negative for a
    simple bull/bear-leaning composite score.
    """
    if net_gex is None:
        return 0.0
    return -0.3 if net_gex < 0 else 0.15


def composite_sentiment(
    news_score: float,
    breadth_score: float,
    vix_level: float,
    vix_change_pct: float,
    net_gex: float | None,
) -> CompositeSentiment:
    components = {
        "news": _clamp(news_score),
        "breadth": _clamp(breadth_score),
        "vix": vix_component(vix_level, vix_change_pct),
        "gamma": gamma_component(net_gex),
    }
    score = sum(components[k] * SENTIMENT_WEIGHTS[k] for k in components)
    score = _clamp(score)

    if score >= 0.15:
        label = "Bullish"
    elif score <= -0.15:
        label = "Bearish"
    else:
        label = "Neutral"

    return CompositeSentiment(score=score, label=label, components=components)
