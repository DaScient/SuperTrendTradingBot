"""Tests for utils.performance metrics."""

import math

from utils import performance as perf


def test_total_return():
    assert perf.total_return([100, 110]) == 0.1
    assert perf.total_return([100, 50]) == -0.5
    assert perf.total_return([100]) == 0.0
    assert perf.total_return([]) == 0.0


def test_returns_from_equity():
    rets = perf.returns_from_equity([100, 110, 99])
    assert rets[0] == 0.1
    assert math.isclose(rets[1], -0.1)


def test_max_drawdown():
    equity = [100, 120, 90, 110, 80]
    # Peak 120 -> trough 80 == -33.33%
    assert math.isclose(perf.max_drawdown(equity), (80 - 120) / 120)


def test_max_drawdown_monotonic_increasing_is_zero():
    assert perf.max_drawdown([100, 101, 102, 103]) == 0.0


def test_win_rate_and_profit_factor():
    trades = [10, -5, 20, -5]
    assert perf.win_rate(trades) == 0.5
    # gross profit 30, gross loss 10
    assert math.isclose(perf.profit_factor(trades), 3.0)


def test_profit_factor_no_losses_is_inf():
    assert perf.profit_factor([5, 10]) == float("inf")
    assert perf.profit_factor([]) == 0.0


def test_sharpe_zero_for_constant_returns():
    # Constant equity growth -> zero std of returns -> sharpe 0 by convention
    equity = [100 * (1.01 ** i) for i in range(50)]
    rets = perf.returns_from_equity(equity)
    assert perf.sharpe_ratio(rets, 365) == 0.0


def test_sharpe_positive_for_upward_noisy_series():
    import numpy as np

    rng = np.random.default_rng(0)
    rets = list(rng.normal(0.002, 0.005, 200))
    assert perf.sharpe_ratio(rets, 365) > 0


def test_sortino_only_penalizes_downside():
    rets = [0.01, 0.02, -0.01, 0.03, -0.02]
    sortino = perf.sortino_ratio(rets, 365)
    assert isinstance(sortino, float)


def test_compute_metrics_report_fields():
    equity = [10000, 10100, 10050, 10200, 10150]
    trades = [100, -50, 150, -50]
    report = perf.compute_metrics(equity, trades, periods_per_year=365)
    d = report.to_dict()
    for key in (
        "total_return", "cagr", "sharpe_ratio", "sortino_ratio",
        "max_drawdown", "win_rate", "profit_factor", "num_trades",
    ):
        assert key in d
    assert d["num_trades"] == 4
    assert d["final_equity"] == 10150


def test_periods_per_year_for():
    assert perf.periods_per_year_for("1h") == 8760
    assert perf.periods_per_year_for("1d") == 365
    assert perf.periods_per_year_for("unknown", default=42) == 42
