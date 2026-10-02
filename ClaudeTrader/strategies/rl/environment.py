"""
Trading environment for the RL agent.

A minimal, gym-style episodic environment over a precomputed sequence of market
states. Actions are *target positions*:

* ``FLAT``  (0) - hold no position
* ``LONG``  (1) - hold a long position
* ``SHORT`` (2) - hold a short position (masked out when shorting is disabled)

At bar ``t`` the agent picks a target position, which is then held from the
close of bar ``t`` to the close of bar ``t + 1``. The reward is the log return
earned by that position minus a proportional cost for every unit of position
change. This mirrors how the backtester fills signals at the bar close.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

FLAT, LONG, SHORT = 0, 1, 2
N_ACTIONS = 3
ACTION_NAMES = {FLAT: "flat", LONG: "long", SHORT: "short"}
ACTION_TO_POSITION = {FLAT: 0, LONG: 1, SHORT: -1}
POSITION_TO_INDEX = {0: FLAT, 1: LONG, -1: SHORT}
N_POSITIONS = 3


def agent_state(market_state: int, position: int) -> int:
    """Combine a market state with the current position (-1, 0, 1)."""
    return market_state * N_POSITIONS + POSITION_TO_INDEX[position]


def valid_actions(allow_short: bool) -> List[int]:
    return [FLAT, LONG, SHORT] if allow_short else [FLAT, LONG]


@dataclass
class StepResult:
    state: Optional[int]
    reward: float
    done: bool


class TradingEnvironment:
    """Episodic environment over bars ``[start, end)`` of a price series."""

    def __init__(
        self,
        close: Sequence[float],
        market_states: Sequence[Optional[int]],
        transaction_cost: float = 0.0015,
        allow_short: bool = True,
        start: Optional[int] = None,
        end: Optional[int] = None,
    ):
        if len(close) != len(market_states):
            raise ValueError("close and market_states must have the same length")
        self.close = [float(c) for c in close]
        self.market_states = list(market_states)
        self.transaction_cost = transaction_cost
        self.allow_short = allow_short

        first_valid = next((i for i, s in enumerate(self.market_states) if s is not None), None)
        if first_valid is None:
            raise ValueError("no bar has a defined market state (series too short for warmup)")
        self.start = max(first_valid, start or 0)
        self.end = min(len(self.close), end if end is not None else len(self.close))
        if self.end - self.start < 2:
            raise ValueError("need at least two bars with defined states to form an episode")

        self.t = self.start
        self.position = 0

    @property
    def num_steps(self) -> int:
        return self.end - 1 - self.start

    def reset(self) -> int:
        self.t = self.start
        self.position = 0
        return self.current_state()

    def current_state(self) -> int:
        return agent_state(self.market_states[self.t], self.position)

    def step(self, action: int) -> StepResult:
        if action == SHORT and not self.allow_short:
            raise ValueError("short action is disabled for this environment")

        target = ACTION_TO_POSITION[action]
        cost = self.transaction_cost * abs(target - self.position)
        prev, nxt = self.close[self.t], self.close[self.t + 1]
        log_return = math.log(nxt / prev) if prev > 0 and nxt > 0 else 0.0
        reward = target * log_return - cost

        self.position = target
        self.t += 1
        done = self.t >= self.end - 1
        state = None if done else self.current_state()
        return StepResult(state=state, reward=reward, done=done)

    def run_policy(self, policy) -> Tuple[float, int]:
        """Run a deterministic ``policy(state) -> action`` for one episode.

        Returns:
            (total reward, number of position changes)
        """
        state = self.reset()
        total, changes = 0.0, 0
        while True:
            before = self.position
            result = self.step(policy(state))
            total += result.reward
            changes += int(self.position != before)
            if result.done:
                return total, changes
            state = result.state
