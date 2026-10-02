"""
Tabular Q-learning agent.

The state space is small (market state x current position), so a Q-table is
learned exactly, needs no deep-learning dependency, trains in well under a
second on thousands of bars, and is fully reproducible for a given seed. The
table is saved as JSON alongside the feature configuration it was trained with.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from .environment import N_ACTIONS, N_POSITIONS, valid_actions
from .features import N_MARKET_STATES

logger = logging.getLogger(__name__)

MODEL_FORMAT_VERSION = 1


class QLearningAgent:
    """Epsilon-greedy tabular Q-learning agent."""

    def __init__(
        self,
        learning_rate: float = 0.1,
        gamma: float = 0.95,
        allow_short: bool = True,
        n_states: int = N_MARKET_STATES * N_POSITIONS,
        seed: Optional[int] = None,
    ):
        if not 0 < learning_rate <= 1:
            raise ValueError("learning_rate must be in (0, 1]")
        if not 0 <= gamma < 1:
            raise ValueError("gamma must be in [0, 1)")
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.allow_short = allow_short
        self.n_states = n_states
        self.actions = valid_actions(allow_short)
        self.q = np.zeros((n_states, N_ACTIONS))
        self.visits = np.zeros((n_states, N_ACTIONS), dtype=np.int64)
        self.rng = np.random.default_rng(seed)
        self.metadata: Dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Acting
    # ------------------------------------------------------------------ #
    def greedy_action(self, state: int) -> int:
        """Best known action; ties (including unseen states) prefer the first
        valid action, i.e. staying flat."""
        values = self.q[state, self.actions]
        return self.actions[int(np.argmax(values))]

    def act(self, state: int, epsilon: float) -> int:
        if self.rng.random() < epsilon:
            return int(self.rng.choice(self.actions))
        return self.greedy_action(state)

    def confidence(self, state: int) -> float:
        """Confidence in the greedy action, in [0, 1].

        Zero for a state never visited in training; otherwise the margin of the
        best action over the runner-up, relative to their magnitudes.
        """
        if self.visits[state].sum() == 0:
            return 0.0
        values = np.sort(self.q[state, self.actions])[::-1]
        best, second = values[0], values[1]
        scale = abs(best) + abs(second)
        if scale <= 1e-12:
            return 0.0
        return float(min(max((best - second) / scale, 0.0), 1.0))

    def q_values(self, state: int) -> Dict[int, float]:
        return {a: float(self.q[state, a]) for a in self.actions}

    # ------------------------------------------------------------------ #
    # Learning
    # ------------------------------------------------------------------ #
    def update(self, state: int, action: int, reward: float, next_state: Optional[int]) -> None:
        """One Q-learning update. ``next_state`` is ``None`` at episode end."""
        target = reward
        if next_state is not None:
            target += self.gamma * float(np.max(self.q[next_state, self.actions]))
        self.q[state, action] += self.learning_rate * (target - self.q[state, action])
        self.visits[state, action] += 1

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_version": MODEL_FORMAT_VERSION,
            "algorithm": "tabular_q_learning",
            "learning_rate": self.learning_rate,
            "gamma": self.gamma,
            "allow_short": self.allow_short,
            "n_states": self.n_states,
            "q": self.q.tolist(),
            "visits": self.visits.tolist(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QLearningAgent":
        if data.get("format_version") != MODEL_FORMAT_VERSION:
            raise ValueError(f"unsupported model format: {data.get('format_version')}")
        agent = cls(
            learning_rate=data["learning_rate"],
            gamma=data["gamma"],
            allow_short=data["allow_short"],
            n_states=data["n_states"],
        )
        q = np.asarray(data["q"], dtype=float)
        visits = np.asarray(data["visits"], dtype=np.int64)
        if q.shape != agent.q.shape or visits.shape != agent.visits.shape:
            raise ValueError("model table shape does not match the state/action space")
        agent.q, agent.visits = q, visits
        agent.metadata = dict(data.get("metadata", {}))
        return agent

    def save(self, path: str) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        self.metadata.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
        tmp = out.with_suffix(out.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict()))
        tmp.replace(out)  # atomic: never leaves a half-written model
        logger.info(f"Saved RL agent to {out}")
        return out

    @classmethod
    def load(cls, path: str) -> "QLearningAgent":
        return cls.from_dict(json.loads(Path(path).read_text()))


def epsilon_schedule(episode: int, episodes: int, start: float, end: float, decay_fraction: float) -> float:
    """Linear decay from ``start`` to ``end`` over the first ``decay_fraction``
    of training, then constant."""
    decay_episodes = max(1, int(episodes * decay_fraction))
    progress = min(episode / decay_episodes, 1.0)
    return start + (end - start) * progress
