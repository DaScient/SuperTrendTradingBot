"""Tests for the RL strategy stack (features, environment, agent, strategy)."""

import math

import numpy as np
import pytest

from strategies import RLStrategy, SuperTrendStrategy, get_strategy
from strategies.rl import (
    FLAT,
    LONG,
    SHORT,
    FeatureConfig,
    QLearningAgent,
    RLConfig,
    TradingEnvironment,
    agent_state,
    compute_market_states,
    decode_market_state,
    train_agent,
)
from strategies.rl.features import N_MARKET_STATES, encode_market_state
from utils.backtest import Backtester, backtest_strategy

FAST = {"episodes": 30, "load_model": False}


def _ohlcv(n=400, seed=3, drift=0.0005, vol=0.02):
    rng = np.random.default_rng(seed)
    close = list(100 * np.cumprod(1 + rng.normal(drift, vol, n)))
    high = [c * (1 + abs(rng.normal(0, 0.004))) for c in close]
    low = [c * (1 - abs(rng.normal(0, 0.004))) for c in close]
    return {"open": list(close), "high": high, "low": low, "close": close}


def _trend(n=300, step=0.01):
    close = [100 * (1 + step) ** i for i in range(n)]
    return {"high": [c * 1.002 for c in close], "low": [c * 0.998 for c in close], "close": close}


# ---------------------------------------------------------------- features
def test_market_states_are_causal():
    data = _ohlcv(300)
    full = compute_market_states(data)
    for cut in (60, 120, 299):
        prefix = {k: v[:cut] for k, v in data.items()}
        assert compute_market_states(prefix) == full[:cut]


def test_market_states_warmup_and_range():
    config = FeatureConfig()
    states = compute_market_states(_ohlcv(200), config)
    assert all(s is None for s in states[: config.warmup])
    assert all(0 <= s < N_MARKET_STATES for s in states[config.warmup:])


def test_state_encoding_round_trip():
    for state in range(N_MARKET_STATES):
        parts = decode_market_state(state)
        assert encode_market_state(parts["trend"], parts["rsi"], parts["momentum"], parts["volatility"]) == state


def test_uptrend_reads_as_uptrend():
    states = [s for s in compute_market_states(_trend()) if s is not None]
    assert all(decode_market_state(s)["trend"] == 1 for s in states[-50:])


# ------------------------------------------------------------- environment
def test_environment_reward_and_costs():
    close = [100.0, 110.0, 99.0]
    env = TradingEnvironment(close, [0, 0, 0], transaction_cost=0.01)
    env.reset()
    step = env.step(LONG)
    assert step.reward == pytest.approx(math.log(1.1) - 0.01)
    assert env.position == 1 and not step.done
    step = env.step(FLAT)  # closing costs, earns nothing
    assert step.reward == pytest.approx(-0.01)
    assert step.done and step.state is None
    env.reset()
    env.step(SHORT)
    assert env.position == -1


def test_environment_rejects_short_when_disabled():
    env = TradingEnvironment([1.0, 2.0, 3.0], [0, 0, 0], allow_short=False)
    env.reset()
    with pytest.raises(ValueError):
        env.step(SHORT)


def test_environment_requires_defined_states():
    with pytest.raises(ValueError):
        TradingEnvironment([1.0, 2.0], [None, None])


# ------------------------------------------------------------------- agent
def test_agent_learns_to_be_long_in_a_steady_uptrend():
    result = train_agent(_trend(), RLConfig(episodes=50, transaction_cost=0.001))
    assert result.final_greedy_reward > 0
    env_states = [s for s in compute_market_states(_trend()) if s is not None]
    assert result.agent.greedy_action(agent_state(env_states[-1], 1)) == LONG


def test_training_is_reproducible_for_a_seed():
    data = _ohlcv(300)
    a = train_agent(data, RLConfig(episodes=10, seed=7)).agent
    b = train_agent(data, RLConfig(episodes=10, seed=7)).agent
    assert np.array_equal(a.q, b.q)


def test_training_end_limits_data_seen():
    data = _ohlcv(400)
    result = train_agent(data, RLConfig(episodes=5), end=250)
    assert result.train_end == 250
    shorter = train_agent({k: v[:250] for k, v in data.items()}, RLConfig(episodes=5)).agent
    assert np.array_equal(result.agent.q, shorter.q)


def test_agent_without_shorts_never_shorts():
    agent = train_agent(_ohlcv(300), RLConfig(episodes=10, allow_short=False)).agent
    assert all(agent.greedy_action(s) != SHORT for s in range(agent.n_states))
    assert not agent.visits[:, SHORT].any()


def test_agent_save_load_round_trip(tmp_path):
    agent = train_agent(_ohlcv(300), RLConfig(episodes=5)).agent
    path = agent.save(str(tmp_path / "nested" / "agent.json"))
    loaded = QLearningAgent.load(str(path))
    assert np.array_equal(loaded.q, agent.q)
    assert np.array_equal(loaded.visits, agent.visits)
    assert loaded.metadata["features"] == FeatureConfig().to_dict()


def test_agent_rejects_bad_hyperparameters():
    with pytest.raises(ValueError):
        QLearningAgent(learning_rate=0)
    with pytest.raises(ValueError):
        QLearningAgent(gamma=1.0)


# ------------------------------------------------------------------ config
def test_rl_config_from_params_flat_and_nested_features():
    cfg = RLConfig.from_params({"episodes": 12, "rsi_period": 21, "features": {"momentum_lookback": 3}})
    assert cfg.episodes == 12
    assert cfg.features.rsi_period == 21
    assert cfg.features.momentum_lookback == 3


@pytest.mark.parametrize("bad", [
    {"learning_rate": 1.5},
    {"gamma": 1.0},
    {"train_fraction": 1.0},
    {"epsilon_start": 0.1, "epsilon_end": 0.5},
    {"rsi_low": 70, "rsi_high": 30},
])
def test_rl_config_validation(bad):
    with pytest.raises(ValueError):
        RLConfig.from_params(bad)


def test_engine_config_parameters_reach_strategies():
    config = {"strategies": {"parameters": {
        "rl_agent": {"episodes": 17, "load_model": False},
        "supertrend": {"atr_period": 7, "multiplier": 2.5},
    }}}
    assert get_strategy("rl_agent", config).rl_config.episodes == 17
    st = get_strategy("supertrend", config)
    assert (st.atr_period, st.multiplier) == (7, 2.5)


def test_set_parameters_updates_derived_attributes():
    st = SuperTrendStrategy({"parameters": {}})
    st.set_parameters({"atr_period": 21})
    assert st.atr_period == 21
    rl = RLStrategy({"parameters": dict(FAST)})
    rl.set_parameters({"episodes": 3})
    assert rl.rl_config.episodes == 3


# ---------------------------------------------------------------- strategy
def test_untrained_strategy_holds():
    sig = RLStrategy({"parameters": dict(FAST)}).generate_signal(_ohlcv(100))
    assert sig.action == "hold" and sig.confidence == 0.0


def test_strategy_signal_mapping_uses_position():
    rl = RLStrategy({"parameters": dict(FAST)})
    data = _ohlcv(300)
    rl.train(data)
    market_state = compute_market_states(data)[-1]

    rl.agent.q[:] = 0.0
    rl.agent.visits[:] = 1
    rl.agent.q[agent_state(market_state, 1), FLAT] = 1.0   # long -> wants flat
    rl.agent.q[agent_state(market_state, 0), SHORT] = 1.0  # flat -> wants short

    assert rl.generate_signal({**data, "position": 1}).action == "exit"
    assert rl.generate_signal({**data, "position": 0}).action == "sell"


def test_strategy_save_and_load_compatibility(tmp_path):
    path = str(tmp_path / "rl.json")
    params = {**FAST, "model_path": path, "save_model": True}
    trained = RLStrategy({"parameters": params})
    trained.train(_ohlcv(300))

    reloaded = RLStrategy({"parameters": {**params, "load_model": True}})
    assert reloaded.is_trained
    assert np.array_equal(reloaded.agent.q, trained.agent.q)

    different = RLStrategy({"parameters": {**params, "load_model": True, "rsi_period": 21}})
    assert not different.is_trained  # trained with other features: ignored


def test_strategy_backtest_trades_only_out_of_sample():
    data = _ohlcv(600, seed=11)
    rl = RLStrategy({"parameters": dict(FAST)})
    bt_config = {}
    info = rl.before_backtest(data, bt_config)
    assert info["rl_model_source"] == "trained_in_sample"
    split = info["rl_split_index"]
    assert split == int(600 * 0.7) and bt_config["warmup"] == split

    out = backtest_strategy(rl, data, bt_config)
    assert all(t["entry_index"] >= split for t in out["trades"])
    # Deterministic for a fixed seed.
    again = RLStrategy({"parameters": dict(FAST)})
    again.before_backtest(data, {})
    assert backtest_strategy(again, data, bt_config)["final_capital"] == out["final_capital"]


def test_strategy_requires_enough_training_data():
    with pytest.raises(ValueError):
        RLStrategy({"parameters": dict(FAST)}).before_backtest(_ohlcv(100), {})


def test_cached_states_match_fresh_computation():
    data = _ohlcv(300)
    rl = RLStrategy({"parameters": dict(FAST)})
    rl.prepare(data)
    fresh = compute_market_states(data)
    for n in (60, 200, 300):
        assert rl._market_state({k: v[:n] for k, v in data.items()}) == fresh[n - 1]


# ------------------------------------------------- backtester contract
def test_backtester_exit_action_and_position_in_window():
    seen = []

    def signal(window):
        i = len(window["close"]) - 1
        seen.append((i, window["position"]))
        return {15: "buy", 20: "exit"}.get(i, "hold")

    n = 30
    flat = {"open": [100.0] * n, "high": [100.5] * n, "low": [99.5] * n, "close": [100.0] * n}
    result = Backtester(slippage_pct=0.0, commission_pct=0.0).run(flat, signal)

    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "signal" and result.trades[0].exit_index == 20
    # Exactly one decision per bar, with the position held at that moment.
    assert [i for i, _ in seen] == list(range(15, n))
    assert dict(seen)[16] == 1 and dict(seen)[21] == 0


def test_backtest_retrains_in_memory_agent_but_keeps_loaded_one(tmp_path):
    data = _ohlcv(600, seed=11)
    rl = RLStrategy({"parameters": dict(FAST)})
    rl.train(data)  # trained on everything, including the future test bars
    info = rl.before_backtest(data, {})
    assert info["rl_model_source"] == "trained_in_sample"
    assert rl.training_summary["train_range"][1] == info["rl_split_index"]

    path = str(tmp_path / "rl.json")
    rl.save(path)
    loaded = RLStrategy({"parameters": {**FAST, "model_path": path, "load_model": True}})
    q_before = loaded.agent.q.copy()
    assert loaded.before_backtest(data, {})["rl_model_source"] == "loaded"
    assert np.array_equal(loaded.agent.q, q_before)


def test_invalid_set_parameters_leaves_strategy_unchanged():
    rl = RLStrategy({"parameters": dict(FAST)})
    with pytest.raises(ValueError):
        rl.set_parameters({"gamma": 2.0})
    assert "gamma" not in rl.parameters
    assert rl.rl_config.gamma == RLConfig().gamma
