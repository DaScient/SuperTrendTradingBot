"""
Performance Metrics Utility

Computes industry-standard trading performance and risk-adjusted return metrics
from an equity curve and/or a list of closed trades.

All functions are pure (no side effects) and operate on plain Python lists so
they have no hard dependency beyond numpy. Annualization is configurable through
``periods_per_year`` so the same helpers work for any timeframe (e.g. 252 for
daily bars, 8760 for hourly bars, 35040 for 15-minute bars).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

logger = logging.getLogger(__name__)

# Common annualization factors (number of bars in a trading year).
PERIODS_PER_YEAR = {
    "1m": 525600,
    "5m": 105120,
    "15m": 35040,
    "30m": 17520,
    "1h": 8760,
    "4h": 2190,
    "1d": 365,
    "1w": 52,
}


def periods_per_year_for(timeframe: str, default: float = 365.0) -> float:
    """Return the annualization factor for a timeframe string (e.g. ``'1h'``)."""
    return float(PERIODS_PER_YEAR.get(timeframe, default))


def returns_from_equity(equity_curve: Sequence[float]) -> List[float]:
    """Convert an equity curve into a list of simple period returns."""
    equity = [float(x) for x in equity_curve]
    if len(equity) < 2:
        return []
    returns = []
    for prev, curr in zip(equity[:-1], equity[1:]):
        if prev == 0:
            returns.append(0.0)
        else:
            returns.append((curr - prev) / prev)
    return returns


def total_return(equity_curve: Sequence[float]) -> float:
    """Total return over the full equity curve (e.g. 0.25 == +25%)."""
    equity = [float(x) for x in equity_curve]
    if len(equity) < 2 or equity[0] == 0:
        return 0.0
    return (equity[-1] - equity[0]) / equity[0]


def cagr(equity_curve: Sequence[float], periods_per_year: float) -> float:
    """Compound Annual Growth Rate derived from the equity curve."""
    equity = [float(x) for x in equity_curve]
    if len(equity) < 2 or equity[0] <= 0 or equity[-1] <= 0:
        return 0.0
    num_periods = len(equity) - 1
    years = num_periods / periods_per_year
    if years <= 0:
        return 0.0
    return (equity[-1] / equity[0]) ** (1 / years) - 1


def volatility(returns: Sequence[float], periods_per_year: float) -> float:
    """Annualized standard deviation of returns."""
    if len(returns) < 2:
        return 0.0
    return float(np.std(returns, ddof=1) * np.sqrt(periods_per_year))


def sharpe_ratio(
    returns: Sequence[float],
    periods_per_year: float,
    risk_free_rate: float = 0.0,
) -> float:
    """Annualized Sharpe ratio.

    Args:
        returns: Per-period simple returns.
        periods_per_year: Annualization factor.
        risk_free_rate: Annual risk-free rate (e.g. 0.04 for 4%).
    """
    if len(returns) < 2:
        return 0.0
    arr = np.asarray(returns, dtype=float)
    rf_per_period = risk_free_rate / periods_per_year
    excess = arr - rf_per_period
    std = np.std(excess, ddof=1)
    if std == 0:
        return 0.0
    return float(np.mean(excess) / std * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: Sequence[float],
    periods_per_year: float,
    risk_free_rate: float = 0.0,
) -> float:
    """Annualized Sortino ratio (penalizes only downside volatility)."""
    if len(returns) < 2:
        return 0.0
    arr = np.asarray(returns, dtype=float)
    rf_per_period = risk_free_rate / periods_per_year
    excess = arr - rf_per_period
    downside = excess[excess < 0]
    if downside.size == 0:
        return 0.0
    downside_std = np.sqrt(np.mean(np.square(downside)))
    if downside_std == 0:
        return 0.0
    return float(np.mean(excess) / downside_std * np.sqrt(periods_per_year))


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Maximum peak-to-trough drawdown as a negative fraction (e.g. -0.18)."""
    equity = [float(x) for x in equity_curve]
    if len(equity) < 2:
        return 0.0
    peak = equity[0]
    max_dd = 0.0
    for value in equity:
        if value > peak:
            peak = value
        if peak > 0:
            dd = (value - peak) / peak
            if dd < max_dd:
                max_dd = dd
    return max_dd


def calmar_ratio(equity_curve: Sequence[float], periods_per_year: float) -> float:
    """Calmar ratio: CAGR divided by the absolute maximum drawdown."""
    mdd = abs(max_drawdown(equity_curve))
    if mdd == 0:
        return 0.0
    return cagr(equity_curve, periods_per_year) / mdd


def win_rate(trade_returns: Sequence[float]) -> float:
    """Fraction of trades that were profitable (0..1)."""
    trades = [float(x) for x in trade_returns]
    if not trades:
        return 0.0
    wins = sum(1 for t in trades if t > 0)
    return wins / len(trades)


def profit_factor(trade_returns: Sequence[float]) -> float:
    """Gross profit divided by gross loss across all trades."""
    trades = [float(x) for x in trade_returns]
    gross_profit = sum(t for t in trades if t > 0)
    gross_loss = abs(sum(t for t in trades if t < 0))
    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0
    return gross_profit / gross_loss


def expectancy(trade_returns: Sequence[float]) -> float:
    """Average profit/loss per trade (in the same units as the inputs)."""
    trades = [float(x) for x in trade_returns]
    if not trades:
        return 0.0
    return float(np.mean(trades))


def average_win_loss(trade_returns: Sequence[float]) -> Dict[str, float]:
    """Return the average winning and losing trade amounts."""
    trades = [float(x) for x in trade_returns]
    wins = [t for t in trades if t > 0]
    losses = [t for t in trades if t < 0]
    return {
        "avg_win": float(np.mean(wins)) if wins else 0.0,
        "avg_loss": float(np.mean(losses)) if losses else 0.0,
    }


@dataclass
class PerformanceReport:
    """Container for a full set of performance metrics."""

    total_return: float = 0.0
    cagr: float = 0.0
    annualized_volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    num_trades: int = 0
    final_equity: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_metrics(
    equity_curve: Sequence[float],
    trade_returns: Optional[Sequence[float]] = None,
    periods_per_year: float = 365.0,
    risk_free_rate: float = 0.0,
) -> PerformanceReport:
    """Compute a full :class:`PerformanceReport` from an equity curve and trades.

    Args:
        equity_curve: Sequence of account values over time.
        trade_returns: Per-trade profit/loss values (absolute or percentage).
            Used for win rate, profit factor and expectancy. If omitted, those
            trade-based metrics are derived as zero.
        periods_per_year: Annualization factor (see :data:`PERIODS_PER_YEAR`).
        risk_free_rate: Annual risk-free rate used by Sharpe/Sortino.

    Returns:
        A populated :class:`PerformanceReport`.
    """
    equity = [float(x) for x in equity_curve] if equity_curve else []
    trades = [float(x) for x in trade_returns] if trade_returns else []
    period_returns = returns_from_equity(equity)
    win_loss = average_win_loss(trades)

    return PerformanceReport(
        total_return=total_return(equity),
        cagr=cagr(equity, periods_per_year),
        annualized_volatility=volatility(period_returns, periods_per_year),
        sharpe_ratio=sharpe_ratio(period_returns, periods_per_year, risk_free_rate),
        sortino_ratio=sortino_ratio(period_returns, periods_per_year, risk_free_rate),
        calmar_ratio=calmar_ratio(equity, periods_per_year),
        max_drawdown=max_drawdown(equity),
        win_rate=win_rate(trades),
        profit_factor=profit_factor(trades),
        expectancy=expectancy(trades),
        avg_win=win_loss["avg_win"],
        avg_loss=win_loss["avg_loss"],
        num_trades=len(trades),
        final_equity=equity[-1] if equity else 0.0,
    )


if __name__ == "__main__":
    # Example usage
    rng = np.random.default_rng(42)
    daily_returns = rng.normal(0.001, 0.02, 365)
    equity = [10000.0]
    for r in daily_returns:
        equity.append(equity[-1] * (1 + r))

    trades = list(rng.normal(50, 200, 40))
    report = compute_metrics(equity, trades, periods_per_year=365)
    for key, value in report.to_dict().items():
        print(f"{key}: {value}")
