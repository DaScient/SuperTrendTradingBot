####################################################
# A Bolder Approach: No min_sell_price conditions. #
####################################################
import ccxt,schedule,warnings,time,ast,config
warnings.filterwarnings('ignore')
from dateutil.tz import tzlocal
from datetime import datetime
from random import randint
from random import seed
import pandas as pd
import numpy as np

ccxt.binanceus({ 'options':{ 'adjustForTimeDifference':True}})
exchange = ccxt.binanceus({
"apiKey": config.BINANCE_KEY,
"secret": config.BINANCE_SECRET,
'enableRateLimit': True})


name=input("Enter name: ")
tick=input("Insert ticker: ")
ticker=tick+"/"+input("USD or USDT? ")
timeframe = input("Enter desired candlestick intervals, 1m,5m,15m,1h,1d: ")
order_size = order_size = float(input("Order size in "+tick+": "))
og_size = order_size
in_position = ast.literal_eval(input("Aleady in desired holding position? - True/False: ").capitalize())
volatility = float(input("Volatility rate: "))

# Randomizer for schedule. I know it's weird, but somehow it works nicely for me. 
#Feel free to remove randint(a,b) downstairs, and just let schedule(a).minutes.. 
if timeframe == "1m":
    a = 55
    b = 60
if timeframe == "5m":
    a = 275
    b = 300
if timeframe == "15m":
    a = 850
    b = 900
if timeframe == "30m":
    a = 1775
    b = 1800
if timeframe == "1h":
    a = 3575
    b = 3600

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

# super!
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
            if not df['in_uptrend'][current] and df['upperband'][current]>df['upperband'][previous]:
                df['upperband'][current] = df['upperband'][previous]
    return df

# Analysis & decision making. This part could be extracted out into it's own class.
def check_buy_sell_signals(df):
    
    # Establish bot parameters
    global in_position,ticker,timeframe,min_sell_price,markup,prev_purch_price,max_loss
    print("Calculating", ticker ,"data...")
    print(df.tail(5)[['timestamp','close','low','in_uptrend']])
    
    # extract last row for df
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1 

    # check for uptrend - if in_uptrend goes from False to True
    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("Changed to uptrend - Buy.")

        # enter position when in_uptrend True
        if not in_position:

            # send binance buy order
            order = exchange.create_market_buy_order(f'{ticker}', order_size)
            
            print('\nStatus:' + order['info']['status'],
                  'Price:' + order['trades'][0]['info']['price'],
                  'Quantity:' + order['info']['executedQty'],
                  'Type:' + order['info']['side'])
            # back in baby
            in_position = True
        else:
            # otherwise 
            print("Already in trading position. No fun.")
    
    # check for downtrend - if in_uptrend goes from True to False
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        
        # current low price = df[-1:].reset_index(drop=True)['low'][0]
        price = df[-1:].reset_index(drop=True)['low'][0]
        print("Changed to downtrend - Sell. Price:",price)
        
        # only sells if price is greater than (min_sell_price)*(markup)*(max_loss)
        if in_position:# and (min_sell_price*(1-max_loss)<price or prev_purch_price*(markup)<price):
            
            # send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)
            
            # i really should just output this as a dataframe()
            print('Status:' + order['info']['status'],
                  'Price:' + order['trades'][0]['info']['price'],
                  'Quantity:' + order['info']['executedQty'],
                  'Type:' + order['info']['side'])
            
            # we are no longer in_position
            in_position = False
            
            # reduces order size to mitigate Insufficient Funds error
            order_size = order_size*(1-0.1428)
            
            # limits the size reduction from above
            if order_size < og_size/4:
                order_size = og_size
            else:
                pass
        else:
            print("Did not find an opportunity to sell, no task.")  

def run_bot():
    print("\n\n",datetime.now(tzlocal()).isoformat())
    print("In position:", in_position,"\tTimeframe:",timeframe,"\n")
    
    # pulls in df to be used for calculations
    bars = exchange.fetch_ohlcv(f'{ticker}', timeframe=timeframe, limit=50)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')#.dt.tz_localize(None)
    
    supertrend_data = supertrend(df)
    check_buy_sell_signals(supertrend_data)

"""
Run Bot, To the Moon
"""
schedule.every(randint(a,b)).seconds.do(run_bot)
while True:
    schedule.run_pending()
    time.sleep(0)