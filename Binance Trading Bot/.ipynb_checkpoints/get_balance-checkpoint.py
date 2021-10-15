#Unpack necessities
import my_config,schedule,time,csv,ccxt
from dateutil.tz import tzlocal
from datetime import datetime
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# login
ccxt.binanceus({ 'options':{ 'adjustForTimeDifference':True}})

# {random key generator}
# for reference see config.py
value = randint(2,199)
print(f"\n\nRandomized KeyPair Identification: {value}\n\n...")
if 1 < value <= 25:
    key = config.BINANCE_KEY_v7
    secret = config.BINANCE_SECRET_v7

if 25 < value <= 50:
    key = config.BINANCE_KEY_v6
    secret = config.BINANCE_SECRET_v6

if 50 < value <= 75:
    key = config.BINANCE_KEY_v5
    secret = config.BINANCE_SECRET_v5

if 75 < value <= 100:
    key = config.BINANCE_KEY_v4
    secret = config.BINANCE_SECRET_v4
    
if 100 < value <= 125:
    key = config.BINANCE_KEY_v3
    secret = config.BINANCE_SECRET_v3

if 125 < value <= 150:
    key = config.BINANCE_KEY_v2
    secret = config.BINANCE_SECRET_v2

if 150 < value <= 175:
    key = config.BINANCE_KEY_v1
    secret = config.BINANCE_SECRET_v1
    
if 175 < value <= 200:
    key = config.BINANCE_KEY_v0
    secret = config.BINANCE_SECRET_v0
# {end of random key generator}

exchange = ccxt.binanceus({"apiKey": key, "secret": secret, "enableRateLimit": True})

#Get USD balance data
bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
bal['free'] = pd.to_numeric(bal['free'])
bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop=True)
bal = bal.sort_values('free',ascending=False).reset_index(drop=True)
bal = bal[bal.free>1]

assets=[]
for index,asset in bal.asset.items():
    try:
        info = exchange.fetch_ohlcv(str(asset+'/USD'), timeframe="1m", limit=1)
        assets.append({'asset':asset,'balance':bal.free[index],
                       'price':info[0][1],'balance_usd':bal.free[index]*info[0][1],
                       'trade_amount':int(bal.free[index]*info[0][1]-bal.free[index]*info[0][1]*.16),
                       'order_size':int(bal.free[index]*info[0][1]-bal.free[index]*info[0][1]*.16)/info[0][1]})
    except:
        pass

df = pd.DataFrame(assets).sort_values('balance_usd',ascending=False).reset_index(drop=True)
df = df[df.order_size>0]

print("\nUSD Wallet\n",df,"\nUSD Total balance:",df.balance_usd.sum())

############################################################################################################

#Get USDT balance data
bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
bal['free'] = pd.to_numeric(bal['free'])
bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop=True)
bal = bal.sort_values('free',ascending=False).reset_index(drop=True)
bal = bal[bal.free>0]

assets=[]
for index,asset in bal.asset.items():
    try:
        info = exchange.fetch_ohlcv(str(asset+'/USDT'), timeframe="1m", limit=1)
        assets.append({'asset':asset,'balance':bal.free[index],
                       'price':info[0][1],'balance_usd':bal.free[index]*info[0][1],
                       'trade_amount':int(bal.free[index]*info[0][1]-bal.free[index]*info[0][1]*.16),
                       'order_size':int(bal.free[index]*info[0][1]-bal.free[index]*info[0][1]*.16)/info[0][1]})
    except:
        pass
df = pd.DataFrame(assets).sort_values('balance_usd',ascending=False).reset_index(drop=True)
df = df[df.order_size>0]
print("\nUSDT Wallet\n",df,"\nUSDT Total balance:",df.balance_usd.sum())

############################################################################################################

#Get user balance data
acct = pd.DataFrame(exchange.fetch_balance()['info']['balances'], columns=['asset','free'])
acct['balance'] = pd.to_numeric(acct.free)
acct = acct[acct.balance > 0].drop(columns=['free'])
acct = acct.sort_values(by = ['balance'], ascending = False).reset_index(drop = True)
#acct

# fetch tradeable balance
assets = []
for index,asset in acct.asset.items():
    #print(index,asset)
    try: 
        info = exchange.fetch_ohlcv(str(asset+'/USDT'), timeframe="1m", limit=1)
        assets.append({'asset' : asset, 'balance': acct.balance[index],'price': info[0][1],
                      'sugg_trade_amt': float(acct.balance[index]*info[0][1] * (0.85)/info[0][1])})
    except:
        pass
assets = pd.DataFrame(assets)
assets = assets[assets.sugg_trade_amt > 0.5]
print("\n User tradeable balance.")
print(assets)