"""
Continual learning with a validation gate.

Each retrain does two things on the asset's latest candles:

1. **Validate the recipe.** Train on the older ``1 - holdout_fraction`` of the
   window, then run the greedy policy on the newest slice it never saw, charged
   with trading costs. This is the only number that says whether the strategy
   has an edge right now - in-sample reward from Q-learning is always flattering.
2. **Deploy the full-window model** (it also learns from the most recent bars)
   only if validation passed. A failed validation leaves the previous champion
   in place until it ages out, after which the asset is *benched*: it keeps
   watching but sends no trade signals.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Sequence

from strategies.rl import RLConfig, TradingEnvironment, compute_market_states, train_agent
from strategies.rl.agent import QLearningAgent

from .assets import LearningConfig

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    passed: bool
    reason: str
    train_bars: int
    holdout_bars: int
    holdout_return: float        # log return of the greedy policy after costs
    buy_hold_return: float       # log return of simply holding over the same bars
    holdout_trades: int
    validated_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def edge_vs_hold(self) -> float:
        return self.holdout_return - self.buy_hold_return


@dataclass
class LearnResult:
    agent: Optional[QLearningAgent]   # full-window model, None when validation could not run
    report: ValidationReport


def validate_and_train(
    ohlcv: Dict[str, Sequence[float]], rl_config: RLConfig, learning: LearningConfig
) -> LearnResult:
    close = list(ohlcv["close"])
    n = len(close)
    now = datetime.now(timezone.utc).isoformat()
    states = compute_market_states(ohlcv, rl_config.features)
    split = int(n * (1 - learning.holdout_fraction))
    usable_train = split - rl_config.features.warmup

    def fail(reason: str) -> LearnResult:
        return LearnResult(None, ValidationReport(False, reason, max(usable_train, 0), n - split,
                                                  0.0, 0.0, 0, now))

    if usable_train < rl_config.min_train_bars:
        return fail(f"only {max(usable_train, 0)} training bars (< {rl_config.min_train_bars})")

    candidate = train_agent(ohlcv, rl_config, end=split, market_states=states)
    holdout = TradingEnvironment(close, states, transaction_cost=rl_config.transaction_cost,
                                 allow_short=rl_config.allow_short, start=split, end=n)
    ret, trades = holdout.run_policy(candidate.agent.greedy_action)
    buy_hold = math.log(close[n - 1] / close[split]) if close[split] > 0 and close[n - 1] > 0 else 0.0

    if trades < learning.min_holdout_trades:
        passed, reason = False, f"made {trades} trade(s) on unseen data (< {learning.min_holdout_trades})"
    elif ret <= learning.min_holdout_return:
        passed, reason = False, f"holdout return {ret:+.2%} did not beat {learning.min_holdout_return:+.2%}"
    else:
        passed, reason = True, "positive out-of-sample return after costs"

    report = ValidationReport(passed, reason, split - candidate.train_start, n - split,
                              ret, buy_hold, trades, now)
    if not passed:
        logger.info(f"validation failed: {reason}")
        return LearnResult(None, report)

    final = train_agent(ohlcv, rl_config, market_states=states).agent
    final.metadata["validation"] = report.to_dict()
    return LearnResult(final, report)
