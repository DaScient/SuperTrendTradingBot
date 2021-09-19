#Unpack necessities
import my_config,schedule,time,csv,ccxt
from dateutil.tz import tzlocal
from datetime import datetime
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

#Connect to exchange
ccxt.binanceus({ 'options':{'adjustForTimeDifference':True}})
exchange = ccxt.binanceus({
"apiKey": my_config.BINANCE_KEY,
"secret": my_config.BINANCE_SECRET,
'enableRateLimit': True})


#Get user balance data
bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
bal['free'] = pd.to_numeric(bal['free'])
bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop=True)
bal = bal.sort_values('free',ascending=False).reset_index(drop=True)
bal = bal[bal.free>0]

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
print(df)
print(bal)