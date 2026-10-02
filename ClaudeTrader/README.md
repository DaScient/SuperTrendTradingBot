# ClaudeTrader

**ClaudeTrader** is a Python trading-research toolkit that sits alongside the
SuperTrendTradingBot. It combines a SuperTrend strategy, an event-driven
backtester, risk and performance utilities, and an LLM layer (Anthropic Claude)
that explains signals, backtests and answers questions in natural language.

It is a decision-support and research tool. It does **not** place orders.

## What works today

| Area | Status | Where |
| --- | --- | --- |
| Claude LLM calls | ✅ Real Anthropic API calls when `ANTHROPIC_API_KEY` is set; canned mock responses otherwise | `models/llm_interface.py` |
| SuperTrend strategy | ✅ Implemented (signals on trend flips) | `strategies/__init__.py` |
| RL strategy | ✅ Tabular Q-learning agent with causal state features, in-sample training and out-of-sample backtests, JSON save/load | `strategies/rl/`, `strategies/__init__.py` |
| Event-driven backtester | ✅ Implemented: costs, ATR stops/targets, trailing stops, long/short | `utils/backtest.py` |
| Risk utilities | ✅ Implemented | `utils/risk.py` |
| Performance metrics | ✅ Implemented | `utils/performance.py` |
| Technical indicators | ✅ SMA, EMA, RSI, MACD, Bollinger, ATR, Stochastic, ADX, OBV, VWAP | `utils/indicators.py` |
| Engine (query, signals, strategy analysis/comparison) | ✅ Implemented on top of the above | `core/engine.py` |
| SuperTrend bot integration | ✅ Signal augmentation, AI trade gating, sizing | `integrations/supertrend_bot_integration.py` |
| Static web dashboard | ✅ Live public prices/news in the browser | `frontend/index.html` |
| Market data | ⚠️ **Mock** (synthetic random-walk OHLCV). The ccxt call is stubbed. | `utils/data_fetcher.py` |
| RAG / knowledge base | ⚠️ **In-memory mock**: a small built-in document set with mock embeddings; no vector DB | `models/rag_engine.py` |
| Multi-factor strategy | ⚠️ **Placeholder**: factor scores are constants | `strategies/__init__.py` |
| Hybrid strategy | ⚠️ Confidence-weighted vote of SuperTrend + multi-factor, so it inherits the placeholder | `strategies/__init__.py` |
| OpenAI / local LLM providers | ⚠️ Mock only | `models/llm_interface.py` |
| `generate_report` | ⚠️ Placeholder | `core/engine.py` |
| REST / WebSocket API | ❌ Not implemented. [`docs/API.md`](docs/API.md) is a design spec | — |

Because market data is synthetic, **backtest and signal results do not reflect real markets** until
`utils/data_fetcher.py` is wired to an exchange.

## Layout

```
ClaudeTrader/
├── core/engine.py                  # ClaudeTrader engine: query, get_signals, analyze/compare strategies
├── models/
│   ├── llm_interface.py            # Anthropic Claude client (+ mock fallback)
│   └── rag_engine.py               # In-memory retrieval over built-in trading docs (mock embeddings)
├── strategies/
│   ├── __init__.py                 # SuperTrend, RL, MultiFactor (placeholder), Hybrid + registry
│   └── rl/                         # RL features, environment, Q-learning agent, trainer
├── utils/
│   ├── backtest.py                 # Event-driven backtester
│   ├── risk.py                     # Exit levels, position sizing, trailing stops, R-multiples
│   ├── performance.py              # Sharpe, Sortino, Calmar, drawdown, win rate, ...
│   ├── indicators.py               # Technical indicators
│   └── data_fetcher.py             # Market data (currently mock)
├── integrations/
│   └── supertrend_bot_integration.py
├── configs/
│   ├── default_config.yaml
│   └── api_keys.example.yaml
├── frontend/index.html             # Static dashboard (no build step)
├── notebooks/demo_claudetrader.ipynb
├── docs/                           # API.md (design spec), README.md
├── tests/                          # pytest suite
├── requirements.txt
└── setup.py
```

## Quick start

Python 3.10+ is recommended (the `anthropic` 1.x SDK requires it).

```bash
cd ClaudeTrader
pip install -r requirements.txt

# Optional: enable real Claude responses (otherwise mock responses are used)
export ANTHROPIC_API_KEY=sk-ant-...

python -m core.engine        # sample query + signals
python -m utils.backtest     # sample SuperTrend backtest
pytest tests/
```

Modules use imports rooted at the `ClaudeTrader/` directory (`from utils import ...`),
so run them from inside `ClaudeTrader/` with `python -m`, not `python core/engine.py`.

```python
from core.engine import ClaudeTrader

trader = ClaudeTrader(config_path="configs/default_config.yaml")

answer = trader.query("What's a sensible SuperTrend setup for a volatile market?")
print(answer.response)

for s in trader.get_signals(symbol="BTC/USD", timeframe="1h"):
    print(s.strategy, s.action, s.confidence, s.stop_loss, s.take_profit)

analysis = trader.analyze_strategy(
    strategy="supertrend",
    symbol="ETH/USD",
    parameters={"atr_period": 10, "multiplier": 3.0},
    backtest_period="30d",
)
comparison = trader.compare_strategies(["supertrend", "hybrid"], backtest_period="90d")
print(comparison["ranking"])
```

## Claude integration

`models/llm_interface.py` calls the Anthropic Messages API through the official
`anthropic` SDK.

- **Mock fallback.** The real client is used only when `ANTHROPIC_API_KEY` (or the variable named
  by `llm.api_key_env`, `ANTHROPIC_AUTH_TOKEN`, or `llm.api_key`) is set and the `anthropic` package
  is installed. Otherwise it logs a warning and returns canned mock responses. Set `use_mock: true`
  to force the mock.
- **Model and effort.** The default model is `claude-opus-5-5`. `effort` (`low` … `max`) controls
  how much the model reasons. Sampling parameters such as `temperature` are not sent to Claude
  because current models reject them.
- **Refusal fallback.** `refusal_fallback: true` turns on the API's server-side fallback, which
  re-runs a declined request on another model. A refusal that still happens surfaces as an error
  message.
- **Errors and caching.** Errors are returned as `"Error: ..."` strings from `generate()` rather than
  raised. Identical prompts are cached in memory for one hour.

```yaml
llm:
  provider: "anthropic"
  model: "claude-opus-5-5"
  effort: "medium"
  max_tokens: 16000
  api_key_env: "ANTHROPIC_API_KEY"
  refusal_fallback: true
  use_mock: false
```

## Backtester (`utils/backtest.py`)

The backtester walks OHLCV bar by bar and asks the strategy for a signal on data up to and
including the current bar. Entries fill at that bar's close, with slippage.

- **Exits.** It checks ATR stop-loss and take-profit levels intrabar. If both are hit in the same
  bar, it assumes the stop hit first. If the bar opens beyond a level (a gap), the order fills at
  the open.
- **Signals.** The strategy is asked once per bar, at the close. Its window includes `position`
  (1 long, -1 short, 0 flat). `buy` / `sell` open a position. The opposite signal closes it and
  reverses on the same bar. `exit` closes without reversing, and `hold` leaves an open position
  alone.
- **Trailing stops** (optional) ratchet after each bar closes, so a bar never tightens its own stop.
- **Sizing** is fixed-fractional (`risk_per_trade` of equity lost at the stop), capped at available
  cash (no leverage).
- **Costs.** Commission and slippage apply on both sides.

```python
from strategies import SuperTrendStrategy
from utils.backtest import backtest_strategy
from utils.data_fetcher import fetch_market_data

data = fetch_market_data("BTC/USD", "1h", limit=2000)   # mock data for now
strategy = SuperTrendStrategy({"parameters": {"atr_period": 10, "multiplier": 3.0}})

result = backtest_strategy(strategy, data, {
    "commission_pct": 0.001,
    "slippage_pct": 0.0005,
    "risk_per_trade": 0.02,
    "atr_stop_multiplier": 2.0,
    "risk_reward_ratio": 2.0,
    "trailing_stop": True,
    "periods_per_year": 8760,  # hourly bars
})
print(result["performance"], result["num_trades"])
```

Each strategy also has `backtest(symbol, period)`, which fetches data and runs the engine.

## RL strategy (`strategies/rl/`)

`RLStrategy` (registry name `rl_agent`) is a tabular Q-learning agent. It needs only numpy.

- **State.** One of 36 market states, built from SuperTrend direction, RSI zone, N-bar momentum
  relative to ATR, and whether ATR% is above its rolling median. The agent combines this with its
  current position. Each bar's state uses only bars up to that point, so prefixes of a series give
  identical states.
- **Actions** are target positions: flat, long or short (short only if `allow_short`). They map to
  `buy`, `sell`, and `exit` (or `hold` when already flat).
- **Reward** is the log return of the position held into the next bar, minus `transaction_cost` for
  each unit of position change.
- **Training** is epsilon-greedy with linear decay. It is reproducible for a given `seed`.
- **Confidence** is the Q-value margin between the best and second-best action. A state the agent
  never saw in training yields `hold` with confidence 0.
- **Persistence.** `save()` writes JSON to `model_path`, and so does training when `save_model` is
  set. A saved model is loaded at startup when `load_model` is set and its feature settings match
  the current config; otherwise it is ignored.

`backtest()` trains on the first `train_fraction` of the data and trades only the remaining bars,
so results are out-of-sample. An agent trained earlier in memory is retrained for every backtest.
An agent loaded from disk is used as-is. The backtester's ATR stops and targets apply to RL
positions too, even though the training environment doesn't model them.

```python
from strategies import RLStrategy
from utils.backtest import backtest_strategy
from utils.data_fetcher import fetch_market_data

data = fetch_market_data("BTC/USD", "1h", limit=2000)
rl = RLStrategy({"parameters": {"episodes": 200, "seed": 42}})

bt_config = {"periods_per_year": 8760}
info = rl.before_backtest(data, bt_config)   # trains on the first 70%, sets warmup to the split
result = backtest_strategy(rl, data, bt_config)
print(info["rl_training"], result["performance"])

rl.train(data)          # or train on everything for live use
rl.save()               # -> models/trained/rl_agent.json (git-ignored)
signal = rl.generate_signal({**data, "position": 0})
```

All settings live under `strategies.parameters.rl_agent` in `configs/default_config.yaml`:
learning rate, gamma, episodes, the exploration schedule, seed, transaction cost, shorting, the
train/test split, persistence, and the feature definitions. Invalid values raise `ValueError`.

On the mock market data (a random walk) the agent has nothing real to learn, so expect in-sample
gains and out-of-sample losses until real data is connected.

## Risk and performance utilities

`utils/risk.py`:
- `compute_exit_levels`: ATR-scaled stop and target for a given risk/reward ratio.
- `position_size_fixed_fractional`, `position_size_volatility_adjusted`.
- `update_trailing_stop`: a stop that only tightens.
- `r_multiple`: outcome in units of initial risk.
- `check_exit`: intrabar stop/target detection that assumes the worse outcome.

`utils/performance.py`: total return, CAGR, annualized volatility, Sharpe, Sortino,
Calmar, max drawdown, win rate, profit factor, expectancy, average win/loss.
Annualization is set with `periods_per_year` (see `PERIODS_PER_YEAR`).

## SuperTrend bot integration

```python
from integrations.supertrend_bot_integration import SuperTrendBotIntegration

integration = SuperTrendBotIntegration("configs/default_config.yaml")

enhanced = integration.augment_signals(base_signals, llm_analysis=True, risk_assessment=True)

verdict = integration.execute_with_validation(signal, confidence_threshold=0.75)
# verdict["execute"] is True only if Claude answers "DECISION: EXECUTE" with
# "CONFIDENCE" >= threshold. Unparseable answers (including mock responses) are rejected.

sizing = integration.get_position_sizing_advice(
    {"price": 67000, "stop_loss_pct": 0.02}, account_balance=10000
)
# -> position_notional (capped at balance), position_units, risk_amount, reasoning
```

## Frontend dashboard

`frontend/index.html` is a single static page with no build step, suitable for GitHub Pages:

- Live spot prices from the public CoinGecko API.
- Headlines from public crypto RSS feeds.
- Reference material on the strategies and the backtest metrics.

It shows an explicit "unavailable" state rather than invented data. It does not talk to the
Python engine: its assistant panel is an offline heuristic, not Claude.

## Tests

```bash
cd ClaudeTrader
pytest tests/
```

The tests cover the backtester (including exit and fill rules), risk, performance, indicators,
strategies, the engine's signal pipeline, the integration's trade gating, and the LLM interface's
request shape and mock fallback. They make no network calls.

## Configuration

`configs/default_config.yaml` holds the LLM, RAG, trading, risk, strategy and backtesting
settings. If the file is missing, the engine falls back to built-in defaults.
`configs/api_keys.example.yaml` is a template. Copy it to `api_keys.yaml` (git-ignored); the code
does not read it yet, so use environment variables for keys.

## Roadmap

These are not implemented yet:
- Real market data via ccxt.
- A vector-DB-backed RAG engine.
- A REST / WebSocket API as specified in `docs/API.md`.
- A real multi-factor strategy.
- Performance reporting.
- OpenAI and local LLM providers.

---

**Disclaimer:** ClaudeTrader is a research and decision-support tool, not financial advice.
Trading involves risk of loss. Past (or simulated) performance does not guarantee future results.
