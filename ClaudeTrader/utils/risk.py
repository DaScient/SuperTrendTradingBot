"""
Risk Management & Entry/Exit Protocols

Implements modern, best-practice entry and exit protocols used by systematic
trading desks:

* Volatility (ATR) based stop-loss and take-profit placement.
* Fixed-fractional and volatility-adjusted position sizing.
* Trailing stop management (both percentage and ATR based).
* Risk/reward (R-multiple) helpers.

These helpers are deliberately framework-agnostic so they can be reused by the
backtesting engine, the live strategies and the integration layer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ExitLevels:
    """Computed stop-loss and take-profit levels for a position."""

    entry_price: float
    stop_loss: float
    take_profit: float
    risk_per_unit: float
    reward_per_unit: float
    risk_reward_ratio: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "risk_per_unit": self.risk_per_unit,
            "reward_per_unit": self.reward_per_unit,
            "risk_reward_ratio": self.risk_reward_ratio,
        }


def compute_exit_levels(
    entry_price: float,
    direction: str,
    atr: float,
    atr_stop_multiplier: float = 2.0,
    risk_reward_ratio: float = 2.0,
) -> ExitLevels:
    """Compute ATR-based stop-loss and take-profit levels.

    Args:
        entry_price: Price at which the position is opened.
        direction: ``'long'`` or ``'short'``.
        atr: Current Average True Range value (absolute price units).
        atr_stop_multiplier: How many ATRs away to place the protective stop.
        risk_reward_ratio: Target reward expressed as a multiple of risk.

    Returns:
        An :class:`ExitLevels` instance with absolute price levels.
    """
    direction = direction.lower()
    if direction not in ("long", "short"):
        raise ValueError("direction must be 'long' or 'short'")
    if entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if atr < 0:
        raise ValueError("atr must be non-negative")

    stop_distance = atr * atr_stop_multiplier
    target_distance = stop_distance * risk_reward_ratio

    if direction == "long":
        stop_loss = entry_price - stop_distance
        take_profit = entry_price + target_distance
    else:
        stop_loss = entry_price + stop_distance
        take_profit = entry_price - target_distance

    return ExitLevels(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_per_unit=stop_distance,
        reward_per_unit=target_distance,
        risk_reward_ratio=risk_reward_ratio,
    )


def position_size_fixed_fractional(
    account_balance: float,
    risk_per_trade: float,
    entry_price: float,
    stop_loss: float,
) -> float:
    """Size a position so that hitting the stop loses exactly ``risk_per_trade``.

    Args:
        account_balance: Total capital available.
        risk_per_trade: Fraction of capital to risk (e.g. 0.02 for 2%).
        entry_price: Planned entry price.
        stop_loss: Planned stop-loss price.

    Returns:
        The position size in units of the asset (>= 0).
    """
    if account_balance <= 0 or entry_price <= 0:
        return 0.0
    risk_amount = account_balance * max(risk_per_trade, 0.0)
    per_unit_risk = abs(entry_price - stop_loss)
    if per_unit_risk <= 0:
        return 0.0
    return risk_amount / per_unit_risk


def position_size_volatility_adjusted(
    account_balance: float,
    risk_per_trade: float,
    atr: float,
    atr_stop_multiplier: float = 2.0,
) -> float:
    """Size a position based on ATR volatility rather than a fixed stop price.

    The stop distance is ``atr * atr_stop_multiplier``; the resulting size risks
    ``risk_per_trade`` of the account if that distance is hit.
    """
    if account_balance <= 0 or atr <= 0:
        return 0.0
    risk_amount = account_balance * max(risk_per_trade, 0.0)
    per_unit_risk = atr * atr_stop_multiplier
    if per_unit_risk <= 0:
        return 0.0
    return risk_amount / per_unit_risk


def update_trailing_stop(
    direction: str,
    current_price: float,
    current_stop: float,
    trail_distance: float,
) -> float:
    """Ratchet a trailing stop in the favorable direction only.

    Args:
        direction: ``'long'`` or ``'short'``.
        current_price: Latest market price.
        current_stop: The currently active stop price.
        trail_distance: Absolute distance to maintain between price and stop.

    Returns:
        The updated stop price. For longs the stop only moves up; for shorts it
        only moves down. It never loosens.
    """
    direction = direction.lower()
    if trail_distance < 0:
        raise ValueError("trail_distance must be non-negative")

    if direction == "long":
        candidate = current_price - trail_distance
        return max(current_stop, candidate)
    if direction == "short":
        candidate = current_price + trail_distance
        return min(current_stop, candidate)
    raise ValueError("direction must be 'long' or 'short'")


def r_multiple(
    entry_price: float,
    exit_price: float,
    initial_stop: float,
    direction: str = "long",
) -> float:
    """Express a realized trade outcome in R-multiples (profit / initial risk)."""
    direction = direction.lower()
    initial_risk = abs(entry_price - initial_stop)
    if initial_risk == 0:
        return 0.0
    if direction == "long":
        pnl = exit_price - entry_price
    else:
        pnl = entry_price - exit_price
    return pnl / initial_risk


def check_exit(
    direction: str,
    price_high: float,
    price_low: float,
    stop_loss: float,
    take_profit: float,
) -> Optional[str]:
    """Determine whether an intrabar stop or target was triggered.

    Uses a conservative assumption: if both the stop and the target fall inside
    the bar's range, the stop is assumed to trigger first (worst case).

    Returns:
        ``'stop'``, ``'take_profit'`` or ``None``.
    """
    direction = direction.lower()
    if direction == "long":
        hit_stop = price_low <= stop_loss
        hit_target = price_high >= take_profit
    elif direction == "short":
        hit_stop = price_high >= stop_loss
        hit_target = price_low <= take_profit
    else:
        raise ValueError("direction must be 'long' or 'short'")

    if hit_stop:
        return "stop"
    if hit_target:
        return "take_profit"
    return None


if __name__ == "__main__":
    levels = compute_exit_levels(
        entry_price=100.0,
        direction="long",
        atr=2.5,
        atr_stop_multiplier=2.0,
        risk_reward_ratio=2.0,
    )
    print("Exit levels:", levels.to_dict())

    size = position_size_fixed_fractional(
        account_balance=10000,
        risk_per_trade=0.02,
        entry_price=levels.entry_price,
        stop_loss=levels.stop_loss,
    )
    print(f"Position size: {size:.4f} units")
