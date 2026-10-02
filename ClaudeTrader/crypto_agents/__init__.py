"""
Per-asset RL signal agents with iMessage notification.

Each coin in the portfolio gets its own :class:`~crypto_agents.agent.AssetAgent`:
its own candle cache, Q-learning model, position state, paper track record and
notification thread. :mod:`crypto_agents.runner` drives them all.

Signals only - nothing here places orders.
"""

from .assets import AssetSpec, Portfolio, load_portfolio

__all__ = ["AssetSpec", "Portfolio", "load_portfolio"]
