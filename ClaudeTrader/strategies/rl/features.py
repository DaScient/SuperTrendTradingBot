"""
State features for the RL trading agent.

Turns an OHLCV series into one discrete market state per bar. Every state is
causal: the state at bar ``t`` depends only on bars ``0..t``, so the same
series prefix always produces the same states (no look-ahead). Bars that do not
yet have enough history map to ``None``.

The market state combines four bucketed features:

* ``trend``      - SuperTrend direction (down / up)
* ``rsi``        - RSI zone (weak / neutral / strong)
* ``momentum``   - N-bar return relative to current volatility (down / flat / up)
* ``volatility`` - ATR% versus its rolling median (calm / elevated)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from utils.indicators import calculate_atr, calculate_rsi, calculate_supertrend

TREND_LEVELS = 2
RSI_LEVELS = 3
MOMENTUM_LEVELS = 3
VOLATILITY_LEVELS = 2
N_MARKET_STATES = TREND_LEVELS * RSI_LEVELS * MOMENTUM_LEVELS * VOLATILITY_LEVELS


@dataclass
class FeatureConfig:
    """Parameters that define the state space. A trained agent is only valid
    for the feature configuration it was trained with."""

    atr_period: int = 10
    supertrend_multiplier: float = 3.0
    rsi_period: int = 14
    rsi_low: float = 40.0
    rsi_high: float = 60.0
    momentum_lookback: int = 5
    momentum_threshold: float = 0.5  # in units of ATR% * sqrt(lookback)
    volatility_lookback: int = 50

    @classmethod
    def from_params(cls, params: Dict[str, Any]) -> "FeatureConfig":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in params.items() if k in names})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def warmup(self) -> int:
        """First bar index at which every feature is defined."""
        return max(
            self.atr_period + 1,
            self.rsi_period + 1,
            self.momentum_lookback,
            self.volatility_lookback,
        )


def encode_market_state(trend: int, rsi_zone: int, momentum: int, volatility: int) -> int:
    """Combine bucketed features into a single index in ``[0, N_MARKET_STATES)``."""
    return ((trend * RSI_LEVELS + rsi_zone) * MOMENTUM_LEVELS + momentum) * VOLATILITY_LEVELS + volatility


def decode_market_state(state: int) -> Dict[str, int]:
    """Inverse of :func:`encode_market_state`."""
    state, volatility = divmod(state, VOLATILITY_LEVELS)
    state, momentum = divmod(state, MOMENTUM_LEVELS)
    trend, rsi_zone = divmod(state, RSI_LEVELS)
    return {"trend": trend, "rsi": rsi_zone, "momentum": momentum, "volatility": volatility}


def compute_market_states(
    ohlcv: Dict[str, Sequence[float]],
    config: Optional[FeatureConfig] = None,
) -> List[Optional[int]]:
    """Compute the discrete market state for every bar of ``ohlcv``.

    Args:
        ohlcv: Dict with ``high``, ``low`` and ``close`` lists of equal length.
        config: Feature parameters (defaults if omitted).

    Returns:
        A list aligned with ``close``: an int state, or ``None`` during warmup.
    """
    config = config or FeatureConfig()
    close = [float(x) for x in ohlcv.get("close", [])]
    high = [float(x) for x in ohlcv.get("high", close)]
    low = [float(x) for x in ohlcv.get("low", close)]
    n = len(close)
    if n == 0:
        return []

    _, direction, _ = calculate_supertrend(
        high, low, close, config.atr_period, config.supertrend_multiplier
    )
    rsi = calculate_rsi(close, config.rsi_period)
    atr = calculate_atr(high, low, close, config.atr_period)

    close_arr = np.asarray(close)
    atr_pct = np.divide(
        np.asarray(atr), close_arr, out=np.zeros(n), where=close_arr > 0
    )

    states: List[Optional[int]] = [None] * n
    k = config.momentum_lookback
    for t in range(config.warmup, n):
        trend = 1 if direction[t] == 1 else 0

        if rsi[t] < config.rsi_low:
            rsi_zone = 0
        elif rsi[t] > config.rsi_high:
            rsi_zone = 2
        else:
            rsi_zone = 1

        threshold = config.momentum_threshold * atr_pct[t] * np.sqrt(k)
        past = close[t - k]
        ret = close[t] / past - 1 if past > 0 else 0.0
        if ret > threshold:
            momentum = 2
        elif ret < -threshold:
            momentum = 0
        else:
            momentum = 1

        window = atr_pct[t - config.volatility_lookback + 1 : t + 1]
        volatility = 1 if atr_pct[t] > np.median(window) else 0

        states[t] = encode_market_state(trend, rsi_zone, momentum, volatility)

    return states
