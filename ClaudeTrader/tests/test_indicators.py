"""Tests for utils.indicators edge cases and ADX."""

import numpy as np

from utils import indicators


def test_atr_handles_single_bar():
    assert indicators.calculate_atr([101.0], [99.0], [100.0]) == [2.0]
    assert indicators.calculate_atr([], [], []) == []


def test_rsi_short_series_is_neutral():
    assert indicators.calculate_rsi([1.0, 2.0, 3.0], period=14) == [50.0, 50.0, 50.0]


def test_adx_is_bounded_and_price_scale_independent():
    rng = np.random.default_rng(1)
    close = list(100 + np.cumsum(rng.normal(0.3, 1.0, 200)))
    high = [c + 0.5 for c in close]
    low = [c - 0.5 for c in close]
    adx = indicators.calculate_adx(high, low, close)
    assert len(adx) == len(close)
    assert all(0 <= v <= 100 for v in adx)

    scaled = indicators.calculate_adx([h * 1000 for h in high], [l * 1000 for l in low], [c * 1000 for c in close])
    assert np.allclose(adx, scaled)


def test_adx_strong_trend_reads_high():
    close = [100.0 + i for i in range(100)]
    adx = indicators.calculate_adx([c + 0.5 for c in close], [c - 0.5 for c in close], close)
    assert adx[-1] > 50
