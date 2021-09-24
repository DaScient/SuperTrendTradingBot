# SuperTrendTradingBot

## Initial run of the Sophie :robot:

To get started, clone this repository into an easy-to-find folder on your computer. Then use the terminal, or your command prompt, to get into the cloned folder. Once in the proper directory, you can run python like so: ../Desktop/SuperTrendTradingBot/Binance_Trading_Bot/ $ python first_meet_sophie.py


1. Data Class
2. Trade Strategy Class
3. Execution Class

## Our SuperTrend Nutshell :robot:

The purpose of this repository is to document the development of our very first trading bot. The bot will be broken out into 3 broad classes:

1. Data Class
2. Trade Strategy Class
3. Execution Class

---

#### Requirements
1. Python (Latest +3.9.7)
2. [Jupyter Notebook - Anaconda (mini-conda will certainly suffice) | https://docs.conda.io/en/latest/miniconda.html#macosx-installers]
3. [Binance.US](https://accounts.binance.us/en/register?ref=52441695) crypto brokerage account. [API_KEY, API_SECRET](https://www.binance.com/en/support/faq/360002502072)
4. Lastly, you'll need this repository cloned somewhere easy to find. (i.e ./Desktop/GitHub will work just fine.)

Don't have Binance.US? [Sign up here!](https://accounts.binance.us/en/register?ref=52441695)

1. After login, go to the menu settings and find API MANAGEMENT.
2. Create an API and follow approval directives.
3. Save and KEEP ULTRA SAFE your api.key & api.secret (in a config.py, follow format.)
4. Then go into your terminal, locate binance_bot.py, then execute by typing: >>python binance_bot.py 
 
 ---

### SuperTrend - Data :computer:

This class will consist of a CCXT connection into Binance.US WebSocket interface that will feed live cryptocurrency data in the form of candle sticks; Open, High, Low, Close (OHLC).

We also apply rolling averages, upper/lower Bollinger bands, and binary variables that evaluates uptrend/downtrend intervals. 

---

### Trade Strategy :chart_with_upwards_trend:

Like many things in life, sometimes one needs a little variety. There is no shortage of trade strategies to apply to our bot. With this in mind, the strategy class will be designed to be modular.
That is, it is to be developed with "plug-and-play" design in order to develop different trading strategies over time. As long as the strategy sends a buy/sell signal for the execution, it will function properly.

---

### Execution :moneybag:

Once the trade signal is sent, the execution class will send the order to Binance.US via ccxt.exchange.

Relax, have fun, and don't forget to drink plenty of water! :tada::rocket::full_moon:

---

### Resources & Repositories Used
[Part Time Larrys (hackingthemarkets)'s supertrend-crypto-bot](https://github.com/hackingthemarkets/supertrend-crypto-bot)

[Part Time Larrys (hackingthemarkets)'s binance-tutorials](https://github.com/hackingthemarkets/binance-tutorials)

[CCXT - BinanceUS](https://github.com/ccxt/ccxt)

[Binance Full History, 2017 - 2020](https://www.kaggle.com/jorijnsmit/binance-full-history)


