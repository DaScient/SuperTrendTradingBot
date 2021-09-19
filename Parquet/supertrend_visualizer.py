#Importation
import ccxt,schedule,warnings,time,ast
warnings.filterwarnings('ignore')
import matplotlib.pyplot as plt
from dateutil.tz import tzlocal
from datetime import datetime
import pyarrow.parquet as pq
import seaborn as sns

from PIL import Image
import pandas as pd
import numpy as np

#Supertrend Formula
def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])
    tr = data[['high-low', 'high-pc', 'low-pc']].max(axis=1)
    return tr
def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()
    return atr
def supertrend(df, period=7, atr_multiplier=3):
    hl2 = (df['high'] + df['low']) / 2
    df['atr'] = atr(df, period)
    df['upperband'] = hl2 + (atr_multiplier * df['atr'])
    df['lowerband'] = hl2 - (atr_multiplier * df['atr'])
    df['in_uptrend'] = True
    for current in range(1, len(df.index)):
        previous = current - 1
        if df['close'][current] > df['upperband'][previous]:
            df['in_uptrend'][current] = True
        elif df['close'][current] < df['lowerband'][previous]:
            df['in_uptrend'][current] = False
        else:
            df['in_uptrend'][current] = df['in_uptrend'][previous]
            if df['in_uptrend'][current] and df['lowerband'][current] < df['lowerband'][previous]:
                df['lowerband'][current] = df['lowerband'][previous]
            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]
    return df

#Set user variables
ticker=input("Insert the prefix of your ticker of choice: (example: LTC-USDT) ")

#Read in historical data.
df  = pq.read_table(f'{ticker}.parquet').to_pandas().reset_index(drop=False)
df = df.set_index('open_time')['close'].resample('1m').ohlc().reset_index(drop=False)

#Apply supertrend formula
supertrend_data= supertrend(df)

#Set plot() params
fig, ax = plt.subplots(figsize=(20, 8))

#Signals 1.1
xcoords_sell = supertrend_data.head(500)[supertrend_data.in_uptrend == False].index
xcoords_buy = supertrend_data.head(500)[supertrend_data.in_uptrend == True].index

#Signals 1.2
for xc in xcoords_sell:
    plt.axvline(x=xc,c='r')
for xc in xcoords_buy:
    plt.axvline(x=xc,c='g')

#Plot close price
ax.plot(supertrend_data.head(500).close, color = 'black', label = 'Line 1')

#Plot bollinger bands
#ax.plot(supertrend_data.tail(5000).upperband, color = 'lime', label = 'upperband')
#ax.plot(supertrend_data.tail(5000).lowerband, color = 'pink', label = 'lowerband')

#PLot outputs
ax.legend(loc = 'upper left')
plt.savefig(f'supertrend_visual_{ticker}.jpg')
plt.show()

#Open .jpg
Image.open("supertrend_visual_{ticker}.jpg")