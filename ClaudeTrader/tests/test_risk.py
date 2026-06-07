"""Tests for utils.risk entry/exit protocols."""

import math

import pytest

from utils import risk


def test_compute_exit_levels_long():
    levels = risk.compute_exit_levels(100.0, "long", atr=2.0, atr_stop_multiplier=2.0, risk_reward_ratio=2.0)
    assert levels.stop_loss == 96.0  # 100 - 2*2
    assert levels.take_profit == 108.0  # 100 + 4*2
    assert levels.risk_reward_ratio == 2.0


def test_compute_exit_levels_short():
    levels = risk.compute_exit_levels(100.0, "short", atr=2.0, atr_stop_multiplier=2.0, risk_reward_ratio=3.0)
    assert levels.stop_loss == 104.0
    assert levels.take_profit == 88.0  # 100 - (4*3)


def test_compute_exit_levels_invalid_direction():
    with pytest.raises(ValueError):
        risk.compute_exit_levels(100.0, "sideways", atr=1.0)


def test_position_size_fixed_fractional():
    # Risk 2% of 10000 = 200; stop distance 5 -> size 40
    size = risk.position_size_fixed_fractional(10000, 0.02, entry_price=100, stop_loss=95)
    assert size == 40.0


def test_position_size_zero_when_no_stop_distance():
    assert risk.position_size_fixed_fractional(10000, 0.02, 100, 100) == 0.0


def test_position_size_volatility_adjusted():
    size = risk.position_size_volatility_adjusted(10000, 0.02, atr=2.5, atr_stop_multiplier=2.0)
    # risk 200 / (2.5*2=5) = 40
    assert size == 40.0


def test_trailing_stop_long_only_ratchets_up():
    stop = risk.update_trailing_stop("long", current_price=110, current_stop=100, trail_distance=5)
    assert stop == 105
    # Price falls; stop must not loosen
    stop2 = risk.update_trailing_stop("long", current_price=104, current_stop=105, trail_distance=5)
    assert stop2 == 105


def test_trailing_stop_short_only_ratchets_down():
    stop = risk.update_trailing_stop("short", current_price=90, current_stop=100, trail_distance=5)
    assert stop == 95
    stop2 = risk.update_trailing_stop("short", current_price=96, current_stop=95, trail_distance=5)
    assert stop2 == 95


def test_r_multiple():
    # entered 100, stop 95 (risk 5), exit 110 -> +2R
    assert risk.r_multiple(100, 110, 95, "long") == 2.0
    assert risk.r_multiple(100, 90, 95, "long") == -2.0


def test_check_exit_long():
    assert risk.check_exit("long", price_high=109, price_low=95, stop_loss=96, take_profit=108) == "stop"
    assert risk.check_exit("long", price_high=109, price_low=100, stop_loss=96, take_profit=108) == "take_profit"
    assert risk.check_exit("long", price_high=107, price_low=100, stop_loss=96, take_profit=108) is None


def test_check_exit_stop_priority_when_both_hit():
    # Both stop and target inside bar -> stop assumed first (conservative)
    assert risk.check_exit("long", price_high=120, price_low=90, stop_loss=96, take_profit=108) == "stop"
