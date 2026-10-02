"""
Event-Driven Backtesting Engine

A lightweight, dependency-light backtester that walks an OHLCV series bar by
bar, asks a strategy for a signal on the data available *up to* each bar (no
look-ahead bias), and manages a single position with realistic execution
assumptions:

* Commission and slippage on every fill.
* ATR-based stop-loss / take-profit and optional trailing stops via
  :mod:`utils.risk`.
* Position sizing via fixed-fractional risk.

Accounting uses an explicit cash + position model so the equity curve is
internally consistent for both long and short trades:

* Long entry:  ``cash -= size * entry_price`` (+ commission); equity adds
  ``size * price``.
* Short entry: ``cash += size * entry_price`` (proceeds) - commission; equity
  subtracts ``size * price`` (the liability to buy back).

The result is a :class:`BacktestResult` containing the equity curve, the list of
closed trades and a full :class:`~utils.performance.PerformanceReport`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from utils import performance as perf
from utils import risk as risk_utils
from utils.indicators import calculate_atr

logger = logging.getLogger(__name__)

# A signal function receives a window dict (open/high/low/close/volume lists
# for bars 0..i plus ``position``: 1 long, -1 short, 0 flat) and returns either
# an action string or an object/dict exposing an ``action`` attribute/key.
# Actions: 'buy' / 'sell' open (or reverse into) a position, 'exit' closes any
# position without opening a new one, and 'hold' changes nothing.
SignalFunc = Callable[[Dict[str, Any]], Any]

EXIT_ACTIONS = ("exit", "close", "flat")


@dataclass
class Trade:
    """A single closed round-trip trade."""

    direction: str
    entry_index: int
    entry_price: float
    exit_index: int
    exit_price: float
    size: float
    pnl: float
    return_pct: float
    exit_reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direction": self.direction,
            "entry_index": self.entry_index,
            "entry_price": self.entry_price,
            "exit_index": self.exit_index,
            "exit_price": self.exit_price,
            "size": self.size,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
            "exit_reason": self.exit_reason,
        }


@dataclass
class BacktestResult:
    """Full output of a backtest run."""

    equity_curve: List[float] = field(default_factory=list)
    trades: List[Trade] = field(default_factory=list)
    performance: Optional[perf.PerformanceReport] = None
    initial_capital: float = 0.0
    final_capital: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "num_trades": len(self.trades),
            "performance": self.performance.to_dict() if self.performance else {},
            "trades": [t.to_dict() for t in self.trades],
            "equity_curve": self.equity_curve,
        }


def _extract_action(signal: Any) -> str:
    """Normalize a strategy signal into an action string."""
    if signal is None:
        return "hold"
    if isinstance(signal, str):
        return signal.lower()
    action = getattr(signal, "action", None)
    if action is None and isinstance(signal, dict):
        action = signal.get("action")
    return (action or "hold").lower()


class Backtester:
    """Single-position, long/short backtester with realistic costs."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        commission_pct: float = 0.001,
        slippage_pct: float = 0.0005,
        risk_per_trade: float = 0.02,
        atr_period: int = 14,
        atr_stop_multiplier: float = 2.0,
        risk_reward_ratio: float = 2.0,
        trailing_stop: bool = False,
        allow_short: bool = True,
        periods_per_year: float = 365.0,
        risk_free_rate: float = 0.0,
    ):
        self.initial_capital = initial_capital
        self.commission_pct = commission_pct
        self.slippage_pct = slippage_pct
        self.risk_per_trade = risk_per_trade
        self.atr_period = atr_period
        self.atr_stop_multiplier = atr_stop_multiplier
        self.risk_reward_ratio = risk_reward_ratio
        self.trailing_stop = trailing_stop
        self.allow_short = allow_short
        self.periods_per_year = periods_per_year
        self.risk_free_rate = risk_free_rate

    def run(
        self,
        ohlcv: Dict[str, Sequence[float]],
        signal_func: SignalFunc,
        warmup: Optional[int] = None,
    ) -> BacktestResult:
        """Run the backtest.

        Args:
            ohlcv: Dict with ``high``, ``low``, ``close`` (and optionally
                ``open``, ``volume``) lists of equal length.
            signal_func: Callable returning a signal for the data window ending
                at the current bar.
            warmup: Number of leading bars to skip before trading. Defaults to
                ``max(atr_period + 1, 2)``.

        Returns:
            A :class:`BacktestResult`.
        """
        high = [float(x) for x in ohlcv.get("high", [])]
        low = [float(x) for x in ohlcv.get("low", [])]
        close = [float(x) for x in ohlcv.get("close", [])]
        has_open = bool(ohlcv.get("open"))
        open_ = [float(x) for x in ohlcv["open"]] if has_open else list(close)
        volume = [float(x) for x in ohlcv.get("volume", [0.0] * len(close))]

        n = len(close)
        if n == 0 or not (len(high) == len(low) == n):
            logger.warning("Backtester received empty or misaligned OHLCV data")
            return BacktestResult(
                equity_curve=[self.initial_capital],
                trades=[],
                performance=perf.compute_metrics([self.initial_capital]),
                initial_capital=self.initial_capital,
                final_capital=self.initial_capital,
            )

        if warmup is None:
            warmup = max(self.atr_period + 1, 2)
        warmup = min(max(warmup, 1), n)

        atr_series = calculate_atr(high, low, close, self.atr_period)

        cash = self.initial_capital
        equity_curve: List[float] = []
        trades: List[Trade] = []
        trade_pnls: List[float] = []

        position: Optional[Dict[str, Any]] = None

        def equity_at(price: float) -> float:
            if position is None:
                return cash
            if position["direction"] == "long":
                return cash + position["size"] * price
            # short: cash already includes proceeds; subtract buy-back liability
            return cash - position["size"] * price

        def record_close(exit_index: int, fill: float, reason: str) -> None:
            nonlocal cash, position
            cash, pnl, ret = self._close_position(cash, position, fill)
            trades.append(
                Trade(
                    direction=position["direction"],
                    entry_index=position["entry_index"],
                    entry_price=position["entry_price"],
                    exit_index=exit_index,
                    exit_price=fill,
                    size=position["size"],
                    pnl=pnl,
                    return_pct=ret,
                    exit_reason=reason,
                )
            )
            trade_pnls.append(pnl)
            position = None

        for i in range(n):
            price = close[i]

            # --- Intrabar stop / target, against the levels in force at the open ---
            if position is not None:
                exit_reason = risk_utils.check_exit(
                    position["direction"], high[i], low[i],
                    position["stop_loss"], position["take_profit"],
                )
                if exit_reason is not None:
                    fill = self._exit_fill_price(
                        position["direction"], exit_reason, price,
                        position["stop_loss"], position["take_profit"],
                        open_[i] if has_open else None,
                    )
                    record_close(i, fill, exit_reason)

            # --- One strategy decision per bar, at the close ---
            action = "hold"
            if i >= warmup:
                current = 0 if position is None else (1 if position["direction"] == "long" else -1)
                action = _extract_action(
                    signal_func(self._window(open_, high, low, close, volume, i, current))
                )

            if position is not None:
                direction = position["direction"]
                # "hold" keeps the position (SuperTrend, for example, emits
                # buy/sell only on the bar the trend flips). An opposite signal
                # or an explicit exit closes it.
                if action in EXIT_ACTIONS or (
                    (direction == "long" and action == "sell")
                    or (direction == "short" and action == "buy")
                ):
                    record_close(i, self._exit_fill_price(direction, "signal", price, 0.0, 0.0), "signal")
                elif self.trailing_stop and atr_series[i] > 0:
                    # Ratchet only after the bar closes, so a bar's close never
                    # tightens the stop its own low was tested against.
                    trail_distance = atr_series[i] * self.atr_stop_multiplier
                    position["stop_loss"] = risk_utils.update_trailing_stop(
                        direction, price, position["stop_loss"], trail_distance
                    )

            # --- Entries (including a reversal on the bar an opposite signal closed) ---
            if position is None and action in ("buy", "sell") and atr_series[i] > 0:
                direction = "long" if action == "buy" else "short"
                if not (direction == "short" and not self.allow_short):
                    cash, position = self._open_position(cash, direction, price, atr_series[i], i)

            equity_curve.append(equity_at(price))

        # Force-close any open position at the last close.
        if position is not None:
            record_close(n - 1, self._apply_slippage(position["direction"], "exit", close[-1]), "end_of_data")
            equity_curve[-1] = cash

        if not equity_curve:
            equity_curve = [self.initial_capital]

        report = perf.compute_metrics(
            equity_curve=equity_curve,
            trade_returns=trade_pnls,
            periods_per_year=self.periods_per_year,
            risk_free_rate=self.risk_free_rate,
        )

        return BacktestResult(
            equity_curve=equity_curve,
            trades=trades,
            performance=report,
            initial_capital=self.initial_capital,
            final_capital=equity_curve[-1],
        )

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _window(
        open_: List[float],
        high: List[float],
        low: List[float],
        close: List[float],
        volume: List[float],
        i: int,
        position: int = 0,
    ) -> Dict[str, Any]:
        """Build a data window containing bars 0..i (inclusive), plus the
        current position (1 long, -1 short, 0 flat)."""
        end = i + 1
        return {
            "open": open_[:end],
            "high": high[:end],
            "low": low[:end],
            "close": close[:end],
            "volume": volume[:end],
            "position": position,
        }

    def _open_position(
        self, cash: float, direction: str, price: float, atr: float, index: int
    ):
        entry_price = self._apply_slippage(direction, "entry", price)
        levels = risk_utils.compute_exit_levels(
            entry_price=entry_price,
            direction=direction,
            atr=atr,
            atr_stop_multiplier=self.atr_stop_multiplier,
            risk_reward_ratio=self.risk_reward_ratio,
        )
        size = risk_utils.position_size_fixed_fractional(
            account_balance=cash,
            risk_per_trade=self.risk_per_trade,
            entry_price=entry_price,
            stop_loss=levels.stop_loss,
        )
        # No leverage: cap notional at available cash.
        max_size = cash / entry_price if entry_price > 0 else 0.0
        size = min(size, max_size)
        if size <= 0:
            return cash, None

        commission = self._commission(entry_price * size)
        if direction == "long":
            cash -= entry_price * size + commission
        else:  # short: receive proceeds, pay commission
            cash += entry_price * size - commission

        position = {
            "direction": direction,
            "entry_price": entry_price,
            "entry_index": index,
            "size": size,
            "stop_loss": levels.stop_loss,
            "take_profit": levels.take_profit,
            "initial_stop": levels.stop_loss,
            "entry_commission": commission,
        }
        return cash, position

    def _close_position(self, cash: float, position: Dict[str, Any], exit_price: float):
        direction = position["direction"]
        size = position["size"]
        entry_price = position["entry_price"]
        commission = self._commission(exit_price * size)
        # Round-trip cost: entry commission (already paid) plus exit commission.
        total_commission = position.get("entry_commission", 0.0) + commission

        if direction == "long":
            cash += size * exit_price - commission
            pnl = size * (exit_price - entry_price) - total_commission
        else:
            cash -= size * exit_price + commission
            pnl = size * (entry_price - exit_price) - total_commission

        notional = entry_price * size if entry_price > 0 else 0.0
        ret = (pnl / notional) if notional > 0 else 0.0
        return cash, pnl, ret

    def _commission(self, notional: float) -> float:
        return abs(notional) * self.commission_pct

    def _apply_slippage(self, direction: str, side: str, price: float) -> float:
        """Apply slippage adverse to the trader."""
        slip = self.slippage_pct
        if (direction == "long" and side == "entry") or (
            direction == "short" and side == "exit"
        ):
            return price * (1 + slip)
        return price * (1 - slip)

    def _exit_fill_price(
        self,
        direction: str,
        reason: str,
        price: float,
        stop_loss: float,
        take_profit: float,
        bar_open: Optional[float] = None,
    ) -> float:
        """Fill price for an exit. If the bar opened beyond the stop or target
        (a gap), the order fills at the open rather than at the level."""
        long = direction == "long"
        if reason == "stop":
            base = stop_loss
            if bar_open is not None:
                base = min(bar_open, stop_loss) if long else max(bar_open, stop_loss)
        elif reason == "take_profit":
            base = take_profit
            if bar_open is not None:
                base = max(bar_open, take_profit) if long else min(bar_open, take_profit)
        else:
            base = price
        return self._apply_slippage(direction, "exit", base)


def backtest_strategy(
    strategy: Any,
    ohlcv: Dict[str, Sequence[float]],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper that backtests a strategy object on OHLCV data.

    Args:
        strategy: An object exposing ``generate_signal(window) -> signal``.
        ohlcv: OHLCV dictionary.
        config: Optional dict of backtester parameters (commission_pct,
            slippage_pct, risk_per_trade, atr_period, atr_stop_multiplier,
            risk_reward_ratio, trailing_stop, initial_capital, periods_per_year,
            warmup).

    Returns:
        A serializable dict describing the backtest outcome.
    """
    config = config or {}
    backtester = Backtester(
        initial_capital=config.get("initial_capital", 10000.0),
        commission_pct=config.get("commission_pct", 0.001),
        slippage_pct=config.get("slippage_pct", 0.0005),
        risk_per_trade=config.get("risk_per_trade", 0.02),
        atr_period=config.get("atr_period", 14),
        atr_stop_multiplier=config.get("atr_stop_multiplier", 2.0),
        risk_reward_ratio=config.get("risk_reward_ratio", 2.0),
        trailing_stop=config.get("trailing_stop", False),
        allow_short=config.get("allow_short", True),
        periods_per_year=config.get("periods_per_year", 365.0),
        risk_free_rate=config.get("risk_free_rate", 0.0),
    )

    # Strategies that precompute features over the full series (causally) can
    # do so once here instead of on every bar.
    prepare = getattr(strategy, "prepare", None)
    if callable(prepare):
        prepare(ohlcv)

    result = backtester.run(ohlcv, strategy.generate_signal, warmup=config.get("warmup"))
    return result.to_dict()


if __name__ == "__main__":
    import numpy as np

    rng = np.random.default_rng(7)
    n = 400
    prices = [100.0]
    for _ in range(n):
        prices.append(prices[-1] * (1 + rng.normal(0.0005, 0.02)))
    close = prices[1:]
    high = [c * (1 + abs(rng.normal(0, 0.005))) for c in close]
    low = [c * (1 - abs(rng.normal(0, 0.005))) for c in close]
    ohlcv = {"high": high, "low": low, "close": close, "open": close}

    from strategies import SuperTrendStrategy

    strat = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})
    out = backtest_strategy(strat, ohlcv, {"trailing_stop": True})
    print("Final capital:", out["final_capital"])
    print("Trades:", out["num_trades"])
    print("Performance:", out["performance"])
