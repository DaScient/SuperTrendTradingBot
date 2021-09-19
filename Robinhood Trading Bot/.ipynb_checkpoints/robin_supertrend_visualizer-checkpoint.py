import schedule,warnings,time,ast,config
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt
from dateutil.tz import tzlocal
from datetime import datetime
from random import randint
import robin_stocks as r
from random import seed
import seaborn as sns
from PIL import Image
import pandas as pd
import numpy as np


#Robinhood login
login = r.authentication.login(username=config.rh_username,password=config.rh_password,store_session=True)
access_token=login['access_token']
token_type=login['token_type']


#Doge data
ticker=input("Enter crypto ticker: ").upper()
timeframe=intput('Interval must be "15second","5minute","10minute","hour","day",or "week": ')
span = input('Span must be "hour","day","week","month","3month","year",or "5year": ')

df=pd.DataFrame.from_dict(r.crypto.get_crypto_historicals(ticker, interval=timeframe, span=span, bounds='24_7', info=None))
df['timestamp']=pd.to_datetime(df['begins_at'], format='%Y-%m-%d').dt.tz_localize(None)
df['open'] = df.apply(lambda x : float(x['open_price']),axis=1)
df['high'] = df.apply(lambda x : float(x['high_price']),axis=1)
df['low'] = df.apply(lambda x : float(x['low_price']),axis=1)
df['close'] = df.apply(lambda x : float(x['close_price']),axis=1)
df=df.drop(columns=['open_price','close_price','high_price','low_price'])
df=df[:-25][['timestamp','open','high','low','close','volume']]
supertrend_data = supertrend(df)

#Set plot() params
fig, ax = plt.subplots(figsize=(20, 8))

#Signals 1.1
xcoords_sell = supertrend_data[supertrend_data.in_uptrend == False].index
xcoords_buy = supertrend_data[supertrend_data.in_uptrend == True].index

#Signals 1.2
for xc in xcoords_sell:
    plt.axvline(x=xc,c='r')
for xc in xcoords_buy:
    plt.axvline(x=xc,c='g')

#Plot close price
ax.plot(supertrend_data.close, color = 'black', label = 'Line 1')

#Plot bollinger bands
#ax.plot(supertrend_data.upperband, color = 'lime', label = 'upperband')
#ax.plot(supertrend_data.lowerband, color = 'pink', label = 'lowerband')

#PLot outputs
ax.legend(loc = 'upper left')
plt.savefig(f'supertrend_visual_{ticker}.jpg')
plt.show()