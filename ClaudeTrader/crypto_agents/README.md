# crypto_agents — one RL signal agent per coin, delivered by iMessage

Each coin in `configs/portfolio.yaml` gets its **own** agent: candle cache, Q-learning model, position
state, paper track record, and message thread. They reuse `strategies/rl` (SuperTrend/RSI/momentum/
volatility state → tabular Q-learning) unchanged.

**Signals only. Nothing places orders.**

## Each cycle, per coin
1. **Pull** closed candles (Binance.US → Binance → Kraken → Coinbase fallback) into an on-disk cache; the
   still-forming candle is discarded so signals never flicker mid-bar. CoinGecko adds 24h change/volume as message colour.
2. **Learn** (every 24h): train on the older 75% of the window, run the greedy policy on the newest 25% it
   never saw, charged with trading costs. Only if that out-of-sample return is positive is the model retrained
   on the full window and deployed. A failed retrain keeps the last validated model for up to 14 days, then the
   agent is **benched**: it keeps watching but sends no trade signals (the daily check-in says so).
3. **Decide** once per closed bar. The agent tracks a virtual spot position seeded from your real holding
   (cost basis included). It messages only on a *transition* (BUY / SELL), after gates: confidence, cooldown
   bars, daily cap.
4. **Notify** through a durable outbox: if iMessage is down the message stays queued and is retried in order.

## Setup (on the Mac that is signed in to iMessage)
```bash
cd ClaudeTrader && python3 -m venv .venv && .venv/bin/pip install numpy pandas pyyaml requests
cp configs/notifier.example.yaml configs/notifier.yaml     # add your number; gitignored
.venv/bin/python -m crypto_agents train --dry-run          # fetch + learn + validate; sends nothing
.venv/bin/python -m crypto_agents status                   # per-coin: armed? out-of-sample vs buy&hold
.venv/bin/python -m crypto_agents test-notify              # one test iMessage per coin
# then schedule it: deploy/com.dascient.cryptoagents.plist (launchd) or `run --loop`
```
First send: macOS will ask to let Terminal/Python control Messages (System Settings → Privacy → Automation).

## Per-coin threads
iMessage can't label a sender per bot, so each message is titled `🐸 PEPE-Bot · BUY`. For truly separate
threads, make one group chat per coin and set that asset's `recipient:` to its chat guid.
To run the agents off-Mac, run a BlueBubbles server on the Mac and use the `bluebubbles` notifier.

## Reading the output honestly
* `status` shows each coin's out-of-sample return next to buy-and-hold. A benched coin means the learner found no edge after costs — that is a result, not a bug.
* Set `rl_defaults.transaction_cost` to your venue's real spread + fee. Retail spreads often exceed 0.5% and decide whether 1h trading can work at all.
* With ~$17 across six coins, ETH/ETC are dust and every fee dwarfs any gain; treat those agents as watchers.
* Q-learning on ~1,500 bars is a small-data method. The validation gate reduces, not removes, the chance of acting on noise.
