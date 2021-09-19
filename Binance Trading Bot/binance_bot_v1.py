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

#Supertrend formula
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

#Instance parameters
name=input("Enter name: ")
tick=input("Insert ticker: ")
ticker=tick+"/"+input("USD or USDT?")
timeframe="5m" #1m,5m,15m,30m,1h,2h,6h,1d
order_size = float(input("Order size in "+tick+": "))
in_position = ast.literal_eval(input("Do not accumulate until next buy signal? - True/False: ").capitalize())
min_sell_price=float(input("Minimum sell price: "))
perc=float(input("Enter percentage of desired markup: "+"%"))
markup=1+perc/100

#Analysis & decision making
def check_buy_sell_signals(df):
    global in_position,order_size,ticker,timeframe,trade_amount,min_sell_price,markup
    print("Analyzing",ticker,"data... \n")
    print(df.tail(3)[['timestamp','close','volume','in_uptrend']])
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1 
    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        print("Changed to uptrend. Attempting purchase.")
        if not in_position:
            order = exchange.create_market_buy_order(f'{ticker}',order_size)
            print('\nStatus:'+order['info']['status'],
                  'Price:'+order['trades'][0]['info']['price'],
                  'Quantity:'+order['info']['executedQty'],
                  'Type:'+order['info']['side'])
            min_sell_price = float(order['trades'][0]['info']['price'])*markup
            in_position = True
            print("Purchased @ $",str(min_sell_price))
        else:
            print("Already in desired trading position, no task.")
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        bar = exchange.fetch_ohlcv(f'{ticker}', timeframe="1m", limit=1)
        price = float(bar[-1][3]) #identifies current low price
        print("Changed to downtrend. Attempting sale.")
        if in_position and price > min_sell_price:
            order = exchange.create_market_sell_order(f'{ticker}',order_size)
            print('Status:'+order['info']['status'],
                  'Price:'+order['trades'][0]['info']['price'],
                  'Quantity:'+order['info']['executedQty'],
                  'Type:'+order['info']['side'])
            in_position = False
            print('Sold @',str(order['trades'][0]['info']['price']),', Loss/gain ',str(1-float(1-order['trades'][0]['info']['price'])/min_sell_price),'%.')
        else:
            print("Did not find an opportunity to sell, no task.")  

def run_bot():
    print(f"\nFetching new bars for {datetime.now(tzlocal()).isoformat()}")
    print("In position:", in_position,";\nTimeframe: ",timeframe,"\n")
    bars = exchange.fetch_ohlcv(f'{ticker}', timeframe=timeframe, limit=100)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize(None)
    supertrend_data = supertrend(df)
    check_buy_sell_signals(supertrend_data,in_position,order_size,ticker,timeframe,min_sell_price,markup)
    bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
    bal['free'] = pd.to_numeric(bal['free'])
    bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop=True)
    bal = bal[bal['asset']==ticker[:4].replace('/','')].reset_index(drop=True).free[0]
    print("\nBalance: $",bal*bars[-1][1],", Position:",bal)
    print("Minimum sell price:",min_sell_price,", Order size:",order_size)
    print(name,"'s Markup set to:",markup,"%")
schedule.every(randint(800,900)).seconds.do(run_bot)
while True:
    schedule.run_pending()
    time.sleep(1)