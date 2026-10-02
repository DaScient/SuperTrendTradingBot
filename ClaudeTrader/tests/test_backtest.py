"""Tests for the event-driven backtesting engine."""

import numpy as np

from utils.backtest import Backtester, backtest_strategy
from strategies import SuperTrendStrategy


def _synthetic_ohlcv(n=300, seed=11):
    rng = np.random.default_rng(seed)
    prices = [100.0]
    for _ in range(n):
        prices.append(prices[-1] * (1 + rng.normal(0.0005, 0.02)))
    close = prices[1:]
    high = [c * (1 + abs(rng.normal(0, 0.005))) for c in close]
    low = [c * (1 - abs(rng.normal(0, 0.005))) for c in close]
    return {"high": high, "low": low, "close": close, "open": close}


def test_empty_data_returns_flat_equity():
    bt = Backtester(initial_capital=5000)
    result = bt.run({"high": [], "low": [], "close": []}, lambda w: "hold")
    assert result.final_capital == 5000
    assert result.equity_curve == [5000]
    assert result.trades == []


def test_hold_only_strategy_makes_no_trades():
    ohlcv = _synthetic_ohlcv()
    bt = Backtester()
    result = bt.run(ohlcv, lambda window: "hold")
    assert len(result.trades) == 0
    # Equity stays at initial capital (no positions taken)
    assert result.final_capital == bt.initial_capital


def test_equity_curve_length_matches_bars():
    ohlcv = _synthetic_ohlcv(n=200)
    bt = Backtester()
    result = bt.run(ohlcv, lambda w: "hold")
    assert len(result.equity_curve) == len(ohlcv["close"])


def test_supertrend_backtest_produces_trades_and_metrics():
    ohlcv = _synthetic_ohlcv(n=400, seed=7)
    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})
    out = backtest_strategy(strat, ohlcv, {"trailing_stop": True})
    assert out["num_trades"] > 0
    perf = out["performance"]
    assert "sharpe_ratio" in perf
    assert "max_drawdown" in perf
    assert perf["max_drawdown"] <= 0
    assert out["final_capital"] > 0


def test_trades_are_serializable():
    ohlcv = _synthetic_ohlcv(n=300, seed=3)
    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})
    out = backtest_strategy(strat, ohlcv)
    for trade in out["trades"]:
        assert trade["direction"] in ("long", "short")
        assert trade["exit_index"] >= trade["entry_index"]
        assert "pnl" in trade


def test_no_short_when_disabled():
    ohlcv = _synthetic_ohlcv(n=300, seed=5)
    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})
    out = backtest_strategy(strat, ohlcv, {"allow_short": False})
    assert all(t["direction"] == "long" for t in out["trades"])


def test_commission_reduces_returns():
    ohlcv = _synthetic_ohlcv(n=400, seed=7)
    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})
    cheap = backtest_strategy(strat, ohlcv, {"commission_pct": 0.0, "slippage_pct": 0.0})
    pricey = backtest_strategy(strat, ohlcv, {"commission_pct": 0.01, "slippage_pct": 0.0})
    assert cheap["final_capital"] >= pricey["final_capital"]


def _flat_ohlcv(n=30):
    close = [100.0] * n
    return {
        "open": list(close),
        "high": [100.5] * n,
        "low": [99.5] * n,
        "close": close,
    }


def _buy_once_at(bar):
    # Window length is i + 1, so this emits "buy" on bar ``bar`` and "hold" after.
    return lambda w: "buy" if len(w["close"]) == bar + 1 else "hold"


def test_hold_signal_keeps_position_open():
    bt = Backtester(slippage_pct=0.0, commission_pct=0.0)
    result = bt.run(_flat_ohlcv(), _buy_once_at(15))
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_index == 15
    assert trade.exit_reason == "end_of_data"
    assert trade.exit_index == 29


def test_opposite_signal_closes_position():
    signals = {15: "buy", 20: "sell"}
    bt = Backtester(slippage_pct=0.0, commission_pct=0.0, allow_short=False)
    result = bt.run(_flat_ohlcv(), lambda w: signals.get(len(w["close"]) - 1, "hold"))
    assert result.trades[0].exit_reason == "signal"
    assert result.trades[0].exit_index == 20


def test_stop_gap_fills_at_open():
    ohlcv = _flat_ohlcv()
    # Bar 16 gaps down far below the ~98 stop.
    ohlcv["open"][16], ohlcv["high"][16], ohlcv["low"][16], ohlcv["close"][16] = 90.0, 91.0, 89.0, 90.5
    bt = Backtester(slippage_pct=0.0, commission_pct=0.0)
    result = bt.run(ohlcv, _buy_once_at(15))
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == 90.0


def test_trailing_stop_does_not_use_same_bar_close():
    ohlcv = _flat_ohlcv()
    # Bar 16 dips to 99 then rallies to close at 103. With a 2-ATR trail the
    # stop ratchets to ~101 only *after* the bar, so the 99 low must not stop us out.
    ohlcv["open"][16], ohlcv["high"][16], ohlcv["low"][16], ohlcv["close"][16] = 100.0, 103.2, 99.0, 103.0
    bt = Backtester(slippage_pct=0.0, commission_pct=0.0, trailing_stop=True, risk_reward_ratio=10.0)
    result = bt.run(ohlcv, _buy_once_at(15))
    assert result.trades[0].exit_index > 16
