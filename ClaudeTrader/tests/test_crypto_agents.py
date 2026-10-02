"""Tests for the per-asset RL signal agents. No network: providers and notifiers are faked."""

import json
import math
import random
import subprocess

import pytest

from crypto_agents.agent import AssetAgent
from crypto_agents.assets import AssetSpec, LearningConfig, Portfolio, SignalConfig, load_portfolio
from crypto_agents.market_data import (BinanceProvider, CandleStore, CoinbaseProvider, KrakenProvider,
                                       Provider, ProviderError, fetch_with_fallback)
from crypto_agents.messages import fmt_price, signal_message
from crypto_agents.notifier import (BlueBubblesNotifier, FallbackNotifier, IMessageNotifier, Notifier,
                                    NotifierError)
from crypto_agents.runner import Runner

HOUR_MS = 3_600_000
T0 = 1_700_000_000_000 - (1_700_000_000_000 % HOUR_MS)


def synthetic_rows(n, start_price=4.5e-6, seed=1, t0=T0):
    """Regime-switching random walk: trends in both directions so an agent can learn something."""
    rng = random.Random(seed)
    price, drift, rows = start_price, 0.0, []
    for i in range(n):
        if i % 80 == 0:
            drift = rng.choice([-0.004, 0.004])
        o = price
        c = o * math.exp(drift + rng.gauss(0, 0.006))
        h, l = max(o, c) * 1.002, min(o, c) * 0.998
        rows.append([t0 + i * HOUR_MS, o, h, l, c, 1000.0])
        price = c
    return rows


class FakeProvider(Provider):
    name = "fake"

    def __init__(self, rows, fail=False):
        super().__init__()
        self.rows, self.fail = rows, fail

    def fetch(self, market, timeframe, bars):
        if self.fail:
            raise ProviderError("fake outage")
        return self.rows[-bars:]


class Recorder(Notifier):
    name = "recorder"

    def __init__(self, fail=False):
        self.sent, self.fail = [], fail

    def send(self, recipient, text):
        if self.fail:
            raise NotifierError("down")
        self.sent.append((recipient, text))


class Resp:
    def __init__(self, payload, status=200):
        self.payload, self.status_code, self.text = payload, status, json.dumps(payload)

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls = routes, []

    def get(self, url, params=None, **kw):
        self.calls.append((url, dict(params or {})))
        for needle, handler in self.routes.items():
            if needle in url:
                return handler(params) if callable(handler) else handler
        return Resp({}, 404)

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return self.routes["post"]


def make_portfolio(tmp_path, **over):
    asset = AssetSpec(symbol="PEPE", emoji="🐸", quantity=1_000_000, cost_usd=4.0, pairs={"fake": "PEPEUSD"})
    kw = dict(timeframe="1h", history_bars=1500, data_dir=str(tmp_path),
              providers=["fake"], assets=[asset],
              learning=LearningConfig(), signals=SignalConfig(heartbeat_hours=0, cooldown_bars=0, min_confidence=0.0),
              rl_defaults={"allow_short": False, "episodes": 60, "transaction_cost": 0.001})
    kw.update(over)
    return Portfolio(**kw)


# ----------------------------------------------------------------------------- providers
def test_binance_parses_and_pages_backwards():
    rows = synthetic_rows(1500)
    def klines(params):
        end = params.get("endTime", float("inf"))
        batch = [r for r in rows if r[0] <= end][-params["limit"]:]
        return Resp([[int(r[0]), *[str(x) for x in r[1:6]], 0, "0", 0, "0", "0", "0"] for r in batch])
    session = FakeSession({"/api/v3/klines": klines})
    got = BinanceProvider(session=session).fetch("PEPEUSDT", "1h", 1500)
    assert len(got) == 1500 and got[0][0] == rows[0][0] and got[-1][4] == pytest.approx(rows[-1][4])
    assert len(session.calls) == 2  # 1000 + 500


def test_kraken_and_coinbase_column_orders():
    kraken = Resp({"error": [], "result": {"XPEPEZUSD": [[1700000000, "1", "3", "0.5", "2", "1.5", "9", 4]],
                                           "last": 1}})
    k = KrakenProvider(session=FakeSession({"kraken": kraken}))
    assert k.fetch("PEPEUSD", "1h", 10) == [[1700000000000, 1.0, 3.0, 0.5, 2.0, 9.0]]
    c = CoinbaseProvider(session=FakeSession({"coinbase": Resp([[1700003600, 0.5, 3, 1, 2, 7], [1700000000, 0.4, 2, 1, 1.5, 6]])}))
    out = c.fetch("PEPE-USD", "1h", 2)
    assert [r[0] for r in out] == [1700000000000, 1700003600000]   # sorted oldest-first
    assert out[1][1:5] == [1.0, 3.0, 0.5, 2.0]                     # open, high, low, close


def test_client_errors_do_not_retry_and_fallback_moves_on():
    session = FakeSession({"api.binance.com": Resp({"msg": "Invalid symbol"}, 400)})
    with pytest.raises(ProviderError):
        BinanceProvider(session=session).fetch("NOPE", "1h", 10)
    assert len(session.calls) == 1
    good = FakeProvider(synthetic_rows(5))
    name, rows = fetch_with_fallback({"a": FakeProvider([], fail=True), "b": good}, {"a": "X", "b": "Y"}, "1h", 5)
    assert name == "b" and len(rows) == 5
    with pytest.raises(ProviderError):
        fetch_with_fallback({"a": good}, {}, "1h", 5)  # no pair configured anywhere


def test_candle_store_drops_forming_bar_and_roundtrips(tmp_path):
    rows = synthetic_rows(10)
    now = (rows[-1][0] + HOUR_MS // 2) / 1000           # mid-way through the last bar
    store = CandleStore(tmp_path / "c.json", "1h", clock=lambda: now)
    store.merge(rows, "fake")
    assert len(store) == 9
    again = CandleStore(tmp_path / "c.json", "1h", clock=lambda: now)
    assert again.ohlcv()["timestamp"] == store.ohlcv()["timestamp"] and again.provider == "fake"


# ----------------------------------------------------------------------------- notifier
def test_imessage_passes_text_as_argv_not_script():
    seen = {}
    def runner(cmd, **kw):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")
    nasty = 'BUY" & (do shell script "rm -rf ~") & "'
    IMessageNotifier(runner=runner).send("+15551234567", nasty)
    cmd = seen["cmd"]
    assert cmd[-2:] == ["+15551234567", nasty]            # data is the last argv items...
    assert all(nasty not in part for part in cmd[:-2])    # ...never inside script text
    IMessageNotifier(runner=runner).send("iMessage;+;chat1", "hi")
    assert any("chat id" in part for part in seen["cmd"])


def test_imessage_failure_and_missing_recipient():
    bad = lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "not authorized")
    with pytest.raises(NotifierError):
        IMessageNotifier(runner=bad).send("+1", "x")
    with pytest.raises(NotifierError):
        IMessageNotifier(runner=bad).send(None, "x")


def test_bluebubbles_and_fallback():
    session = FakeSession({"post": Resp({}, 200)})
    BlueBubblesNotifier("http://mac:1234/", "pw", session=session).send("+15551234567", "hello")
    url, kw = session.calls[0]
    assert url == "http://mac:1234/api/v1/message/text" and kw["json"]["chatGuid"] == "iMessage;-;+15551234567"
    rec = Recorder()
    FallbackNotifier([Recorder(fail=True), rec]).send("+1", "x")
    assert rec.sent
    with pytest.raises(NotifierError):
        FallbackNotifier([Recorder(fail=True)]).send("+1", "x")


# ----------------------------------------------------------------------------- messages
def test_price_formatting_keeps_sub_cent_precision():
    assert fmt_price(0.000004585) == "$0.000004585"
    assert fmt_price(2764.68) == "$2,764.68" and fmt_price(2.11) == "$2.110"


def test_quantity_formatting_keeps_dust_visible():
    from crypto_agents.messages import fmt_qty
    assert fmt_qty(1356940) == "1,356,940" and fmt_qty(2.3923) == "2.3923" and fmt_qty(0.00000043) == "4.3e-07"


def test_signal_message_mentions_holding_and_basis():
    asset = AssetSpec(symbol="PEPE", emoji="🐸", quantity=1356940, cost_usd=6.11)
    text = signal_message(asset, "SELL", 4.585e-6, 5, 0.62, [], None, {"change_24h_pct": 2.4}, "1h")
    assert "PEPE-Bot" in text and "SELL" in text and "+2.4% 24h" in text and "vs cost" in text
    assert "no order placed" in text


# ----------------------------------------------------------------------------- agent
def build_agent(tmp_path, rows, **over):
    pf = make_portfolio(tmp_path, **over)
    now = (rows[-1][0] + HOUR_MS) / 1000 + 1            # every bar in `rows` is closed
    clock = {"t": now}
    agent = AssetAgent(pf.assets[0], pf, {"fake": FakeProvider(rows)}, clock=lambda: clock["t"])
    return agent, clock


def test_agent_seeds_position_from_holding_and_cost_basis(tmp_path):
    agent, _ = build_agent(tmp_path, synthetic_rows(50))
    assert agent.state.position == 1 and agent.state.entry_price == pytest.approx(4.0 / 1_000_000)


def test_full_cycle_trains_validates_and_signals_only_on_transitions(tmp_path):
    rows = synthetic_rows(1500)
    agent, clock = build_agent(tmp_path, rows)
    agent.refresh_data()
    report = agent.learn_if_due()
    assert report["train_bars"] > 0 and report["holdout_bars"] > 0
    assert agent.store.model_path.exists()

    # Force the armed state so the transition logic is what's under test.
    agent.state.champion_valid_until = clock["t"] + 86400
    agent.evaluate()
    first = list(agent.state.outbox)
    assert agent.state.last_bar_ts == rows[-1][0]
    assert agent.evaluate() is None and agent.state.outbox == first   # same bar: no duplicate

    # Every queued signal alternates position, so no two identical calls in a row.
    sides = [m["text"].split("·")[1].split("—")[0].strip() for m in agent.state.outbox]
    assert all(s in ("BUY", "SELL") for s in sides)


def test_benched_agent_is_silent_until_validated(tmp_path):
    rows = synthetic_rows(1500)
    agent, clock = build_agent(tmp_path, rows)
    agent.refresh_data()
    agent.learn_if_due()
    agent.state.champion_valid_until = None            # never validated / expired
    agent.state.position = 1
    agent.model.q[:] = 0
    agent.model.visits[:] = 1
    # make "flat" strictly best everywhere so the agent wants to exit
    agent.model.q[:, 0] = 1.0
    agent.evaluate()
    assert agent.state.outbox == [] and agent.state.position == 1   # suppressed, position unchanged
    agent.state.champion_valid_until = clock["t"] + 1000
    agent.state.last_bar_ts = None
    agent.evaluate()
    assert agent.state.position == 0 and "SELL" in agent.state.outbox[0]["text"]
    assert len(agent.state.trades) == 1                # closed paper trade recorded


def test_cooldown_and_daily_cap(tmp_path):
    rows = synthetic_rows(1500)
    sig = SignalConfig(heartbeat_hours=0, cooldown_bars=10, min_confidence=0.0, max_per_day=1)
    agent, clock = build_agent(tmp_path, rows, signals=sig)
    agent.refresh_data(); agent.learn_if_due()
    agent.state.champion_valid_until = clock["t"] + 1000
    agent.model.visits[:] = 1
    agent.model.q[:] = 0; agent.model.q[:, 0] = 1.0     # always wants flat
    agent.evaluate()
    assert agent.state.position == 0
    agent.state.position, agent.state.last_bar_ts = 1, None   # simulate re-entry, same bar window
    agent.evaluate()
    assert agent.state.position == 1 and len(agent.state.outbox) == 1   # cooldown blocked 2nd SELL


def test_outbox_survives_notifier_outage_then_drains_in_order(tmp_path):
    agent, _ = build_agent(tmp_path, synthetic_rows(60))
    agent._enqueue("one", 1.0); agent._enqueue("two", 2.0)
    down = Recorder(fail=True)
    assert agent.flush_outbox(down.send, "+1") == 0 and len(agent.state.outbox) == 2
    agent.save()
    reloaded, _ = build_agent(tmp_path, synthetic_rows(60))
    up = Recorder()
    assert reloaded.flush_outbox(up.send, "+1") == 2
    assert [t for _, t in up.sent] == ["one", "two"]


def test_failure_alert_fires_once_per_streak(tmp_path):
    agent, _ = build_agent(tmp_path, synthetic_rows(60))
    assert agent.record_failure("boom") is None and agent.record_failure("boom") is None
    assert agent.record_failure("boom") is not None
    assert agent.record_failure("boom") is None          # not repeated
    agent.record_success()
    assert agent.state.consecutive_failures == 0 and not agent.state.failure_alerted


def test_heartbeat_when_silent(tmp_path):
    sig = SignalConfig(heartbeat_hours=24, cooldown_bars=0, min_confidence=0.0)
    agent, _ = build_agent(tmp_path, synthetic_rows(1500), signals=sig)
    agent.refresh_data(); agent.learn_if_due()
    agent.model.q[:] = 0                                 # no opinion: ties resolve to flat...
    agent.state.position = 0                             # ...which matches a flat agent: no transition
    agent.evaluate()
    assert len(agent.state.outbox) == 1 and "Check-in" in agent.state.outbox[0]["text"]


# ----------------------------------------------------------------------------- runner / config
def test_runner_isolates_failing_asset(tmp_path, monkeypatch):
    rows = synthetic_rows(1500)
    good = AssetSpec(symbol="PEPE", pairs={"fake": "A"}, quantity=1, cost_usd=1)
    bad = AssetSpec(symbol="SHIB", pairs={"fake": "B"}, quantity=1, cost_usd=1)
    pf = make_portfolio(tmp_path, assets=[bad, good])
    monkeypatch.setattr("crypto_agents.runner.fetch_details", lambda ids: {})
    monkeypatch.setattr("crypto_agents.runner.build_providers", lambda names: {"fake": FakeProvider(rows)})
    runner = Runner(pf, notifier=Recorder())
    runner.agents[0].providers = {"fake": FakeProvider([], fail=True)}   # SHIB's data is down
    report = runner.run_once()
    assert "error" in report["SHIB"] and "error" not in report["PEPE"]
    assert (tmp_path / "PEPE" / "state.json").exists()
    assert runner.status()[0]["failures"] == 1


def test_shipped_portfolio_config_is_valid():
    pf = load_portfolio()
    assert [a.symbol for a in pf.assets] == ["PEPE", "SHIB", "TRUMP", "XRP", "ETH", "ETC"]
    for a in pf.assets:
        assert set(a.pairs) <= {"binanceus", "binance", "kraken", "coinbase"} and a.pairs
        from strategies.rl import RLConfig
        RLConfig.from_params(pf.rl_params(a))


def test_unknown_config_keys_fail_loudly(tmp_path):
    cfg = tmp_path / "p.yaml"
    cfg.write_text("timeframe: 1h\nlearning: {retrain_hours: 3}\nassets: [{symbol: X}]\n")
    with pytest.raises(ValueError):
        load_portfolio(str(cfg), str(tmp_path / "none.yaml"))
