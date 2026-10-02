"""Tests for the SuperTrend bot integration's trade gating and sizing."""

from types import SimpleNamespace

import pytest

integration_mod = pytest.importorskip("integrations.supertrend_bot_integration")
SuperTrendBotIntegration = integration_mod.SuperTrendBotIntegration


def _integration(answer):
    obj = SuperTrendBotIntegration.__new__(SuperTrendBotIntegration)
    obj.claude_trader = SimpleNamespace(
        query=lambda q: SimpleNamespace(response=answer, confidence=0.8)
    )
    return obj


@pytest.mark.parametrize("answer, expected", [
    ("Looks good.\nDECISION: EXECUTE\nCONFIDENCE: 0.9", True),
    ("Too risky.\nDECISION: SKIP\nCONFIDENCE: 0.9", False),
    ("DECISION: EXECUTE\nCONFIDENCE: 0.5", False),  # below threshold
    ("No, do not take this trade.", False),  # unparseable -> fail closed
])
def test_execute_with_validation_respects_decision(answer, expected):
    result = _integration(answer).execute_with_validation({"symbol": "BTC/USD"}, 0.75)
    assert result["execute"] is expected


def test_position_sizing_is_capped_and_in_units():
    out = _integration("ok").get_position_sizing_advice(
        {"price": 100.0, "stop_loss_pct": 0.01}, account_balance=10000
    )
    assert out["position_notional"] == 10000  # 200 / 0.01 = 20000, capped
    assert out["position_units"] == 100
