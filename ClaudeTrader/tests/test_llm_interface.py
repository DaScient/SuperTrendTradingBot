"""Tests for models.llm_interface (no network calls)."""

from types import SimpleNamespace

import pytest

from models.llm_interface import DEFAULT_ANTHROPIC_MODEL, LLMInterface, MockLLMClient


@pytest.fixture(autouse=True)
def _no_anthropic_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)


def _message(text="hello", stop_reason="end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        model=DEFAULT_ANTHROPIC_MODEL,
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


class FakeClient:
    def __init__(self, message):
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._message = message

    def _create(self, **params):
        self.calls.append(params)
        return self._message


def test_falls_back_to_mock_without_api_key():
    llm = LLMInterface({"provider": "anthropic"})
    assert llm.is_mock
    assert isinstance(llm._client, MockLLMClient)
    assert llm.model == DEFAULT_ANTHROPIC_MODEL
    assert "SuperTrend" in llm.generate("supertrend strategy?")


def test_use_mock_overrides_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    llm = LLMInterface({"provider": "anthropic", "use_mock": True})
    assert llm.is_mock


def test_real_client_created_with_api_key(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    llm = LLMInterface({"provider": "anthropic"})
    assert not llm.is_mock


def test_anthropic_request_shape_and_text_extraction(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    llm = LLMInterface({"provider": "anthropic", "effort": "high"})
    fake = FakeClient(_message("Buy signal looks weak."))
    llm._client = fake

    assert llm.generate("Analyze BTC", system_prompt="sys", use_cache=False) == "Buy signal looks weak."
    params = fake.calls[0]
    assert params["model"] == DEFAULT_ANTHROPIC_MODEL
    assert params["system"] == "sys"
    assert params["output_config"] == {"effort": "high"}
    assert params["fallbacks"] == "default"
    assert "temperature" not in params


def test_refusal_returns_error_text(monkeypatch):
    pytest.importorskip("anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    llm = LLMInterface({"provider": "anthropic", "refusal_fallback": False})
    fake = FakeClient(_message("", stop_reason="refusal"))
    llm._client = fake

    out = llm.generate("x", use_cache=False)
    assert out.startswith("Error:") and "declined" in out
    assert "fallbacks" not in fake.calls[0]
