"""Tests for core.engine signal generation (mock LLM, mock market data)."""

from datetime import datetime

import pytest

from core.engine import ClaudeTrader, TradingSignal
from strategies import StrategySignal


@pytest.fixture
def trader(monkeypatch, tmp_path):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    return ClaudeTrader(str(tmp_path / "missing.yaml"))  # falls back to defaults


def test_get_signals_returns_trading_signals(trader):
    trader.config["strategies"] = {"enabled": ["supertrend", "multi_factor"]}
    signals = trader.get_signals("BTC/USD", "1h")
    assert len(signals) == 2
    assert all(isinstance(s, TradingSignal) for s in signals)
    assert {s.strategy for s in signals} == {"supertrend", "multi_factor"}
    assert all(s.symbol == "BTC/USD" for s in signals)


def test_to_trading_signal_adds_atr_exit_levels(trader):
    sig = StrategySignal(
        action="buy", confidence=0.8, price=100.0, timestamp=datetime.now(),
        indicators={"atr": 2.0}, reasoning="flip",
    )
    out = trader._to_trading_signal(sig, "ETH/USD", "supertrend")
    assert out.stop_loss == 96.0
    assert out.take_profit == 108.0
    assert out.reasoning == "flip"
