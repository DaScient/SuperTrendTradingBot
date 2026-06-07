"""Tests for strategy signal generation and the SuperTrend fix."""

import numpy as np

from strategies import SuperTrendStrategy, get_strategy, list_strategies


def test_list_strategies_registry():
    names = list_strategies()
    assert "supertrend" in names
    assert "multi_factor" in names


def test_get_strategy_unknown_raises():
    import pytest

    with pytest.raises(ValueError):
        get_strategy("does_not_exist", {})


def test_supertrend_aligned_arrays_have_same_length():
    n = 60
    high = [100 + i for i in range(n)]
    low = [99 + i for i in range(n)]
    close = [99.5 + i for i in range(n)]
    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})
    supertrend, direction, atr = strat._calculate_supertrend(high, low, close)
    assert len(supertrend) == n
    assert len(direction) == n
    assert len(atr) == n


def test_supertrend_uptrend_detected():
    # Strictly rising series should be in an uptrend at the latest bar.
    n = 60
    high = [100 + i for i in range(n)]
    low = [99 + i for i in range(n)]
    close = [99.5 + i for i in range(n)]
    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})
    _, direction, _ = strat._calculate_supertrend(high, low, close)
    assert direction[-1] == 1


def test_supertrend_emits_buy_on_flip():
    # Construct a down-then-up series to force a bullish flip on the last bar.
    down = [100 - i for i in range(30)]
    up = [70 + i * 3 for i in range(1, 12)]
    close = down + up
    high = [c + 1 for c in close]
    low = [c - 1 for c in close]
    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 2.0}})

    actions = []
    for i in range(15, len(close)):
        sig = strat.generate_signal({"high": high[: i + 1], "low": low[: i + 1], "close": close[: i + 1]})
        if sig:
            actions.append(sig.action)
    # The recovery should generate at least one buy signal somewhere.
    assert "buy" in actions
