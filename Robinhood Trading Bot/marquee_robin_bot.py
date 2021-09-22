import schedule,warnings,time,ast,config
warnings.filterwarnings('ignore')
from dateutil.tz import tzlocal
from datetime import datetime
from random import randint
import robin_stocks as r
from random import seed
import pandas as pd
import numpy as np

#Robinhood login (ONLY NEED TO RUN THIS PART ONCE)
login = r.authentication.login(username=config.rh_username,password=config.rh_password,store_session=True)
access_token=login['access_token']
token_type=login['token_type']

# Analysis & decision making. This part could be extracted out into it's own class.
# Set user variables
tick = "DOGE"#input("Insert ticker: ")
interval = "5minute"#input("Insert desired time intervals: ")
span = "day"
volatility=0.5555555#float(input("Volatility rate: "))

# Supertrend
# (TR) The true range indicator is taken as the greatest of the following: current high less the current low; the absolute value of the current high less the previous close; and the absolute value of the current low less the previous close
def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])
    tr = data[['high-low','high-pc','low-pc']].max(axis=1)
    return tr

#TR rolling average
def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()
    return atr

# https://www.tradingfuel.com/supertrend-indicator-formula-and-calculation/ #It's important to treat the atr_multiplier as a variable. See supertrend_visualizer_parquet.py to see how atr_mult affects indication. Volatility rate varies from 0.0001 - 3. Smaller numbers for 1m intervals. Larger number for day or swing trades.
def supertrend(df, period = 7, atr_multiplier = volatility):
    hl2 = (df['high'] + df['low'])/2
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
            if (df['in_uptrend'][current]) and (df['lowerband'][current] < df['lowerband'][previous]):
                df['lowerband'][current] = df['lowerband'][previous]
            if not df['in_uptrend'][current] and df['upperband'][current] > df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]
    return df


#Signal
def check_buy_sell_signals(df):
    global tick,interval,span
    print("Analyzing",tick,"data... ")
    print(df.tail(3)[['timestamp','close','volume','in_uptrend']])
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1 
    # check for uptrend - if in_uptrend goes from False to True
    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        
        # no executions, just signals.
        print("\n############################")
        print("# Changed to uptrend - Buy #")
        print("############################")
    
    # check for downtrend - if in_uptrend goes from True to False
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        
        # no executions, just signals.
        print("\n###############################")
        print("# Changed to downtrend - Sell #")
        print("###############################")
# run_bot()
#Execution            
def run_bot():
    print(f"\n{datetime.now(tzlocal()).isoformat()}")
    print("\nTimeframe:",timeframe,"\n")
    
    # pulls in rh ticker data
    df=pd.DataFrame.from_dict(r.crypto.get_crypto_historicals(tick, interval=interval, span=span, bounds='24_7', info=None))
    df['timestamp']=pd.to_datetime(df['begins_at'], format='%Y-%m-%d').dt.tz_localize(None)
    df['open'] = df.apply(lambda x : float(x['open_price']),axis=1)
    df['high'] = df.apply(lambda x : float(x['high_price']),axis=1)
    df['low'] = df.apply(lambda x : float(x['low_price']),axis=1)
    df['close'] = df.apply(lambda x : float(x['close_price']),axis=1)
    df=df.drop(columns=['open_price','high_price','low_price'])
    df=df[:-1][['timestamp','open','high','low','close','volume']]
    
    df.tail(10)
                            
    supertrend_data = supertrend(df)
    check_buy_sell_signals(supertrend_data)
    
    #print("Minimum sell price:",min_sell_price,", Order size:",order_size)

"""
Run Bot, To the Moon
"""
schedule.every(5).minutes.do(run_bot)
while True:
    schedule.run_pending()
    time.sleep(0)



