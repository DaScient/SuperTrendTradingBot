"""
Reinforcement-learning components for ClaudeTrader.

* :mod:`.features`    - causal, discrete market-state features
* :mod:`.environment` - trading environment with backtester-consistent semantics
* :mod:`.agent`       - tabular Q-learning agent with JSON persistence
* :mod:`.trainer`     - :class:`RLConfig` and :func:`train_agent`

The strategy wrapper lives in :class:`strategies.RLStrategy`.
"""

from .agent import QLearningAgent
from .environment import ACTION_NAMES, FLAT, LONG, SHORT, TradingEnvironment, agent_state
from .features import FeatureConfig, compute_market_states, decode_market_state
from .trainer import RLConfig, TrainingResult, train_agent

__all__ = [
    "ACTION_NAMES",
    "FLAT",
    "LONG",
    "SHORT",
    "FeatureConfig",
    "QLearningAgent",
    "RLConfig",
    "TradingEnvironment",
    "TrainingResult",
    "agent_state",
    "compute_market_states",
    "decode_market_state",
    "train_agent",
]
