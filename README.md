# SuperTrendTradingBot
A [DaScient Capital, LP](https://dascientcapital.us) proprietary program &amp; non-ML approach to the application of the SuperTrend indicator designed to execute buy &amp; sell orders to Binance.US using python.

Through our model of the SuperTrend algorithm we incorporate social sentiment analyses, sophisticated technical indicators, and pre-built strategies to autonomously trade your assets for you. Requiring only little to no supervision by you. We even allow our users to mirror peers' portfolios. Meaning you can create your own or join other people's and group's portfolio allocations! This opens the possibilities of imitating some of the most lucrative strategies our community have found. See more under Trends!

Our ultimate mission is to leverage mathematical modeling, data science, business & strategic intelligence, and ml to provide reliable, intellectually resourceful, and totally open source user-friendly products. 

Find value in our project? Want to help us expand or contribute to code? Even if it's just to say thanks - please feel free to contact us.

---

### SuperTrend - Trends! :computer:

This special feature allows users to fully, or partially, imitate other user's portfolio allocations. The Trends enhancement allows users to become more exposed and informed of the SuperTrends trading community. Users can search openly for groups and strategies that they feel are more suitable for their level of risk. Users can also create, share, and update their own portfolios to the community as well, meaning whatever new allocations the group leader decides will change everyone's portfolios to reflect it! You can let your imagination wander. 

---

## The Bot - Our SuperTrend Nutshell :robot:

The purpose of this repository is to document the development of our very first trading bot. The bot will be broken out into 3 broad classes:

1. Data Class
2. Trade Strategy Class
3. Execution Class

---

### What's Needed?

Although our team is working very hard to get the fully user-friendly app developed & deployed, there will still be plenty of time to test the bot on your own as we work through our goals and plans for the future. Feel free to fork, star, and/or watch for any of our updates here on GitHub. 

Here's what you'll currently need in order to execute the bot locally on your machine. (An introductory Python crash course probably wouldn't hurt.) If you do run with it we seek your inputs, suggestions, and ideas that you can prove have a place in our code. Whether it's to help the bot run more efficiently or how we can better scale our project. Your thoughts are welcome! This program is far from perfect, but your support and growing interest we give us the encouragement we need to get this released and trading as smoothly as we possibly can. Don't hesitate to send us an email if there's anything we can do to help: contact@dascient.com

---

#### Requirements
1. [Python (Latest +3.9.7)](https://www.python.org/ftp/python/3.9.7/python-3.9.7-macosx10.9.pkg)
2. Jupyter Notebook - Anaconda ([mini-conda will certainly suffice](https://docs.conda.io/en/latest/miniconda.html))
3. Binance.US crypto brokerage account. (API_KEY, API_SECRET) 
4. Lastly, you'll need this repository cloned somewhere easy to find. (i.e ./Desktop/GitHub will do.)

Don't have Binance.US? [Sign up here!](https://accounts.binance.us/en/register?ref=52441695)
1. After login, go to the menu settings and find API MANAGEMENT.
2. Create an API and follow approval directives.
3. Save and KEEP ULTRA SAFE your api.key & api.secret (in a config.py, follow format.)
4. Then go into your terminal, locate safemode_binance_bot.py, then execute by typing: >>python safemode_binance_bot.py 
 
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


