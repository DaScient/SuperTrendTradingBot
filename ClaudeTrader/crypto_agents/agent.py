"""
One agent per coin.

``AssetAgent.run_cycle`` is the whole loop for a single asset:

    pull candles -> (re)learn if due -> evaluate the newest closed bar ->
    maybe emit a signal -> queue it in the durable outbox

The agent keeps a *virtual spot position* (holding / in cash), seeded from the
real holding, so every message is a transition - "SELL", then later "BUY" -
rather than a stream of repeated opinions. Nothing here places orders.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from strategies.rl import ACTION_NAMES, RLConfig, agent_state, compute_market_states
from strategies.rl.agent import QLearningAgent
from strategies.rl.environment import ACTION_TO_POSITION

from . import messages
from .assets import AssetSpec, Portfolio
from .learner import validate_and_train
from .market_data import CandleStore, Provider, fetch_with_fallback
from .store import AgentState, StateStore

logger = logging.getLogger(__name__)


def _today(now: float) -> str:
    return datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")


class AssetAgent:
    def __init__(self, asset: AssetSpec, portfolio: Portfolio, providers: Dict[str, Provider],
                 clock: Callable[[], float] = time.time):
        self.asset, self.portfolio, self.providers, self.clock = asset, portfolio, providers, clock
        directory = Path(portfolio.data_dir) / asset.symbol
        self.candles = CandleStore(directory / f"candles_{portfolio.timeframe}.json",
                                   portfolio.timeframe, clock=clock)
        self.store = StateStore(directory)
        self.state: AgentState = self.store.load()
        self.rl_config = RLConfig.from_params({**portfolio.rl_params(asset),
                                               "model_path": None, "load_model": False})
        self.model: Optional[QLearningAgent] = None
        if self.store.model_path.exists():
            try:
                self.model = QLearningAgent.load(str(self.store.model_path))
            except (ValueError, KeyError, OSError) as exc:
                logger.warning(f"{asset.symbol}: ignoring unreadable model ({exc})")
        if not self.state.initialized:
            self._initialise()

    def _initialise(self) -> None:
        held = self.asset.assume_holding and self.asset.quantity > 0
        self.state.position = 1 if held else 0
        self.state.entry_price = self.asset.cost_basis_per_unit if held else None
        self.state.initialized = True

    # ------------------------------------------------------------------ #
    def refresh_data(self) -> None:
        provider, rows = fetch_with_fallback(self.providers, self.asset.pairs, self.portfolio.timeframe,
                                             self.portfolio.history_bars)
        added = self.candles.merge(rows, provider)
        logger.info(f"{self.asset.symbol}: {added} new bar(s) from {provider}, {len(self.candles)} cached")

    def learn_if_due(self, force: bool = False) -> Optional[Dict[str, Any]]:
        """Retrain when stale. Returns the validation report dict if a retrain ran."""
        now = self.clock()
        cfg = self.portfolio.learning
        due = (force or self.model is None or self.state.last_train_ts is None
               or now - self.state.last_train_ts >= cfg.retrain_every_hours * 3600)
        if not due:
            return None
        result = validate_and_train(self.candles.ohlcv(), self.rl_config, cfg)
        self.state.last_train_ts = now
        self.state.validation = result.report.to_dict()
        if result.agent is not None:
            self.model = result.agent
            self.model.save(str(self.store.model_path))
            self.state.champion_valid_until = now + cfg.max_champion_age_days * 86400
        # a failed retrain leaves the previous champion (and its expiry) untouched
        logger.info(f"{self.asset.symbol}: retrain {'passed' if result.report.passed else 'failed'}: "
                    f"{result.report.reason}")
        return self.state.validation

    # ------------------------------------------------------------------ #
    def evaluate(self, details: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Evaluate the newest closed bar. Returns the queued message text, if any."""
        data = self.candles.ohlcv()
        ts, close = data["timestamp"], data["close"]
        if not ts or self.model is None:
            return None
        if ts[-1] == self.state.last_bar_ts:
            return self._maybe_heartbeat(close[-1], details)   # no new bar: nothing to decide

        states = compute_market_states(data, self.rl_config.features)
        market_state = states[-1]
        self.state.last_bar_ts = ts[-1]
        if market_state is None:
            return None

        now = self.clock()
        position = self.state.position
        s = agent_state(market_state, position)
        action = self.model.greedy_action(s)
        confidence = self.model.confidence(s)
        target = ACTION_TO_POSITION[action]
        if target < 0:  # spot holder cannot short: treat as "get out"
            target = 0
        if target == position:
            return self._maybe_heartbeat(close[-1], details)

        suppressed = self._suppress_reason(now, ts[-1], confidence)
        if suppressed:
            logger.info(f"{self.asset.symbol}: {ACTION_NAMES[action]} suppressed ({suppressed})")
            return self._maybe_heartbeat(close[-1], details)

        price = close[-1]
        side = "BUY" if target == 1 else "SELL"
        if side == "SELL" and self.state.entry_price:
            self.state.trades.append({
                "entry_ts": self.state.entry_ts, "exit_ts": ts[-1], "entry_price": self.state.entry_price,
                "exit_price": price,
                "pnl_pct": price / self.state.entry_price - 1 - 2 * self.rl_config.transaction_cost,
            })
            self.state.trades = self.state.trades[-200:]
        self.state.position = target
        self.state.entry_price = price if target == 1 else None
        self.state.entry_ts = ts[-1] if target == 1 else None
        self.state.last_signal_bar_ts = ts[-1]
        text = messages.signal_message(self.asset, side, price, market_state, confidence, self.state.trades,
                                       self.state.validation, details, self.portfolio.timeframe)
        self._enqueue(text, now, count_toward_cap=True)
        return text

    def _suppress_reason(self, now: float, bar_ts: int, confidence: float) -> Optional[str]:
        sig = self.portfolio.signals
        if not self.state.armed(now):
            return "benched: no validated edge"
        if confidence < sig.min_confidence:
            return f"confidence {confidence:.0%} < {sig.min_confidence:.0%}"
        if self.state.last_signal_bar_ts is not None:
            bars_since = (bar_ts - self.state.last_signal_bar_ts) // self.candles.bar_ms
            if bars_since < sig.cooldown_bars:
                return f"cooldown ({bars_since}/{sig.cooldown_bars} bars)"
        if self.state.sent_today.get(_today(now), 0) >= sig.max_per_day:
            return "daily cap reached"
        return None

    def _maybe_heartbeat(self, price: float, details: Optional[Dict[str, Any]]) -> Optional[str]:
        hours = self.portfolio.signals.heartbeat_hours
        now = self.clock()
        if hours <= 0 or now - self.state.last_message_ts < hours * 3600 or self.state.outbox:
            return None
        text = messages.heartbeat_message(self.asset, price, self.state.position, self.state.armed(now),
                                          self.state.validation, details)
        self._enqueue(text, now)
        return text

    def _enqueue(self, text: str, now: float, count_toward_cap: bool = False) -> None:
        self.state.outbox.append({"text": text, "created": now})
        if count_toward_cap:
            day = _today(now)
            self.state.sent_today = {day: self.state.sent_today.get(day, 0) + 1}

    # ------------------------------------------------------------------ #
    def flush_outbox(self, send: Callable[[Optional[str], str], None], recipient: Optional[str]) -> int:
        """Send queued messages in order; stop at the first failure so order is kept."""
        sent = 0
        while self.state.outbox:
            item = self.state.outbox[0]
            try:
                send(self.asset.recipient or recipient, item["text"])
            except Exception as exc:  # notifier errors must never lose the message
                logger.error(f"{self.asset.symbol}: send failed, will retry next cycle: {exc}")
                break
            self.state.outbox.pop(0)
            self.state.last_message_ts = self.clock()
            sent += 1
        return sent

    def save(self) -> None:
        self.store.save(self.state)

    def record_failure(self, error: str) -> Optional[str]:
        """Count a failed cycle; queue one alert when the streak crosses the threshold."""
        self.state.consecutive_failures += 1
        threshold = self.portfolio.signals.failure_alert_after
        if self.state.consecutive_failures >= threshold and not self.state.failure_alerted:
            self.state.failure_alerted = True
            text = messages.failure_message(self.asset, self.state.consecutive_failures, error)
            self._enqueue(text, self.clock())
            return text
        return None

    def record_success(self) -> None:
        self.state.consecutive_failures = 0
        self.state.failure_alerted = False
