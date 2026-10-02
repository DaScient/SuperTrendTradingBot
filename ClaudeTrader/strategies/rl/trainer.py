"""
Training entry point for the RL agent.

:class:`RLConfig` collects every tunable variable (learning, exploration,
costs, feature definitions, persistence) with validated defaults, and
:func:`train_agent` trains a :class:`QLearningAgent` on an OHLCV series.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .agent import QLearningAgent, epsilon_schedule
from .environment import TradingEnvironment
from .features import FeatureConfig, compute_market_states

logger = logging.getLogger(__name__)


@dataclass
class RLConfig:
    """All RL strategy variables, with defaults."""

    # Learning
    learning_rate: float = 0.1
    gamma: float = 0.95
    episodes: int = 200
    epsilon_start: float = 1.0
    epsilon_end: float = 0.05
    epsilon_decay_fraction: float = 0.8
    seed: Optional[int] = 42

    # Trading environment
    transaction_cost: float = 0.0015  # per unit of position change (commission + slippage)
    allow_short: bool = True

    # Train/test split used by backtest(): train on the first fraction only
    train_fraction: float = 0.7
    min_train_bars: int = 200

    # Persistence
    model_path: Optional[str] = "models/trained/rl_agent.json"
    load_model: bool = True   # load model_path at startup if it exists and matches
    save_model: bool = False  # write model_path after training

    features: FeatureConfig = field(default_factory=FeatureConfig)

    @classmethod
    def from_params(cls, params: Optional[Dict[str, Any]]) -> "RLConfig":
        """Build from a flat parameter dict (as in ``default_config.yaml``).

        Feature parameters may be given flat or under a ``features`` key.
        Unknown keys are ignored with a warning.
        """
        params = dict(params or {})
        own = {f.name for f in fields(cls)} - {"features"}
        feature_names = {f.name for f in fields(FeatureConfig)}

        feature_params = dict(params.pop("features", None) or {})
        kwargs: Dict[str, Any] = {}
        for key, value in params.items():
            if key in own:
                kwargs[key] = value
            elif key in feature_names:
                feature_params[key] = value
            else:
                logger.warning(f"Ignoring unknown rl_agent parameter: {key}")

        config = cls(features=FeatureConfig.from_params(feature_params), **kwargs)
        config.validate()
        return config

    def validate(self) -> None:
        checks = [
            (0 < self.learning_rate <= 1, "learning_rate must be in (0, 1]"),
            (0 <= self.gamma < 1, "gamma must be in [0, 1)"),
            (self.episodes >= 1, "episodes must be >= 1"),
            (0 <= self.epsilon_end <= self.epsilon_start <= 1, "need 0 <= epsilon_end <= epsilon_start <= 1"),
            (0 < self.epsilon_decay_fraction <= 1, "epsilon_decay_fraction must be in (0, 1]"),
            (self.transaction_cost >= 0, "transaction_cost must be >= 0"),
            (0 < self.train_fraction < 1, "train_fraction must be in (0, 1)"),
            (self.min_train_bars >= 2, "min_train_bars must be >= 2"),
            (self.features.momentum_lookback >= 1, "momentum_lookback must be >= 1"),
            (self.features.volatility_lookback >= 2, "volatility_lookback must be >= 2"),
            (self.features.rsi_low < self.features.rsi_high, "rsi_low must be below rsi_high"),
        ]
        for ok, message in checks:
            if not ok:
                raise ValueError(f"Invalid RL config: {message}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingResult:
    agent: QLearningAgent
    episode_rewards: List[float]
    train_start: int
    train_end: int
    final_greedy_reward: float
    final_greedy_trades: int

    def summary(self) -> Dict[str, Any]:
        rewards = self.episode_rewards
        tail = rewards[-max(1, len(rewards) // 10):]
        return {
            "episodes": len(rewards),
            "train_bars": self.train_end - self.train_start,
            "train_range": [self.train_start, self.train_end],
            "mean_reward_last_10pct": sum(tail) / len(tail),
            "greedy_log_return": self.final_greedy_reward,
            "greedy_position_changes": self.final_greedy_trades,
        }


def train_agent(
    ohlcv: Dict[str, Sequence[float]],
    config: Optional[RLConfig] = None,
    end: Optional[int] = None,
    market_states: Optional[Sequence[Optional[int]]] = None,
) -> TrainingResult:
    """Train a Q-learning agent on bars ``[0, end)`` of ``ohlcv``.

    Args:
        ohlcv: OHLCV dict (``high``/``low``/``close`` required).
        config: RL configuration (defaults if omitted).
        end: Exclusive bar index to stop training at (defaults to all bars).
            Pass the train/test split here so evaluation data is never seen.
        market_states: Precomputed states for ``ohlcv`` (computed if omitted).

    Returns:
        A :class:`TrainingResult` with the trained agent and statistics.
    """
    config = config or RLConfig()
    config.validate()
    close = list(ohlcv.get("close", []))
    if market_states is None:
        market_states = compute_market_states(ohlcv, config.features)

    env = TradingEnvironment(
        close,
        market_states,
        transaction_cost=config.transaction_cost,
        allow_short=config.allow_short,
        end=end,
    )
    agent = QLearningAgent(
        learning_rate=config.learning_rate,
        gamma=config.gamma,
        allow_short=config.allow_short,
        seed=config.seed,
    )

    episode_rewards: List[float] = []
    for episode in range(config.episodes):
        epsilon = epsilon_schedule(
            episode, config.episodes, config.epsilon_start, config.epsilon_end, config.epsilon_decay_fraction
        )
        state = env.reset()
        total = 0.0
        while True:
            action = agent.act(state, epsilon)
            result = env.step(action)
            agent.update(state, action, result.reward, result.state)
            total += result.reward
            if result.done:
                break
            state = result.state
        episode_rewards.append(total)

    greedy_reward, greedy_trades = env.run_policy(agent.greedy_action)
    agent.metadata.update({
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "features": config.features.to_dict(),
        "transaction_cost": config.transaction_cost,
        "episodes": config.episodes,
        "train_bars": env.end - env.start,
    })

    result = TrainingResult(
        agent=agent,
        episode_rewards=episode_rewards,
        train_start=env.start,
        train_end=env.end,
        final_greedy_reward=greedy_reward,
        final_greedy_trades=greedy_trades,
    )
    logger.info(f"RL training complete: {result.summary()}")
    return result
