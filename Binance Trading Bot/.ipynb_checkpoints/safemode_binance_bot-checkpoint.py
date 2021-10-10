###############################################
# safemode - 
# does not allow for sell at loss. expect longer trade activity intervals.
###############################################

import ccxt,schedule,warnings,time,ast,config
from IPython.display import clear_output
warnings.filterwarnings('ignore')
from dateutil.tz import tzlocal
from rich import print, pretty
from datetime import datetime
from random import randint
from random import seed
import pandas as pd
import numpy as np
pretty.install()

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

# set params
name = input("Input a name: ")
tick = input("Insert ticker: ").upper()
deno = input("Enter denomination (examples: USD, USDT, BUSD, BTC): ").upper()
ticker = tick+"/"+ deno
timeframe = input("Candlestick intervals (1m,5m,15m,30m,1h,2h,6h,1d): ").capitalize()
in_position = ast.literal_eval(input("Already in desired position? - True/False: ").capitalize())
autopilot = True # ast.literal_eval(input("Autopilot on? - True/False: ").capitalize())

# dynamic order_size - redundance?
bars = exchange.fetch_ohlcv(f'{ticker}', timeframe=timeframe, limit=2)
bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
bal['free'] = pd.to_numeric(bal['free'])
bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop = True)

# get deno balance really quick here
deno_bal = bal[bal.asset == deno]['free'].reset_index()['free'][0]

# determins if you want to enter a position
if not in_position:
    min_sell_price = bars[-1][3] # current low_price
    perc = float(input("Enter % of deno to be used for desired trading position: %"))/100
    order_size = int(deno_bal * perc / bars[-1][1])
    og_size = order_size

elif in_position: # it's good to have a higher min_sell_price value
    min_sell_price = float(input("Previous purchase price: $"))
    perc = float(input("Enter % of deno to be used for desired trading position: %"))/100
    order_size = int(deno_bal * perc)
    og_size = order_size

# it's more profitable to activate LESS stop-loss sells by increasing tolerance
max_loss = 7.77/100 # float(input("Enter max loss (ex: 2.5%): %"))/100

# it's not a bad idea to let this be higher; smaller amounts mean frequent trades
# the longer the bot will wait to sell
min_gain = 2.22/100 # float(input("Min gain (ex: 1.5%): %"))/100

# safemode on
safe = True # ast.literal_eval(input("Safemode on? - True/False: ").capitalize())

# stopp-loss
stop_loss = True # ast.literal_eval(input("Activate stop-loss sell? - True/False: ").capitalize())

# schedule randomizer
if timeframe == "1m":
    a = 55
    b = 65
    
elif timeframe == "5m":
    a = 275
    b = 305
    
elif timeframe == "15m":
    a = 850
    b = 905
    
elif timeframe == "30m":
    a = 1775
    b = 1805
    
elif timeframe == "1h":
    a = 3575
    b = 3605

period = 1 # int(input("Enter the rolling average period (7 - 42): "))
volatility = 0.005050608302615407 # initial temp volatility

print(f"\nLoading...\nPlease allow for {timeframe} until initial results are printed.")
print(f"\nProject started: {datetime.now(tzlocal())}")

# supertrend
def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])
    tr = data[['high-low','high-pc','low-pc']].max(axis=1)
    return tr

def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()
    return atr

def supertrend(df, period = period, atr_multiplier = volatility):
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

def check_buy_sell_signals(df):

    global in_position, ticker, timeframe, min_sell_price, min_gain, order_size, max_loss
    print(f"\nCalculating {ticker} data...")
    print(df.tail(3)[["timestamp", "volume", 'in_uptrend']])
    
    # first things first ############################
    # measure volatility
    # calculate {timeframe} logarithmic return
    df['returns'] = (np.log(df.close /
        df.close.shift(-1)))
    #df_volatility = df[df.returns != 0]
    volatility =  df['returns'].std()*(len(df)-1)**.5
    volatility_avg = df["returns"].mean()
    print(f"\nVolatility: {volatility} Volatility avg: {volatility_avg}")
    #################################################
    
    # dynamic order_size
    bars = exchange.fetch_ohlcv(f'{ticker}', timeframe=timeframe, limit=5)
    bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
    bal['free'] = pd.to_numeric(bal['free'])
    bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop = True)
    
    # get deno balance really quick here
    deno_bal = bal[bal.asset == deno]['free'].reset_index()['free'][0]
    
    # get {ticker} balance here
    bal = bal[bal['asset']==ticker[:4].replace('/','')].reset_index(drop = True).free[0]
    
    # re-establish order_size
    if not in_position:
        order_size = deno_bal * perc / bars[-1][4]
        
    # 
    if in_position:
        order_size = int(bal * perc)
    
    # updated info
    info_1 = []
    info_1.append({"inPosition":in_position, "positionBal":bal, f"{deno}bal":(bal * bars[-1][4]), "orderSize":order_size, "minGain %":min_gain * 100,
            "maxLoss %":max_loss * 100, "safeMode":safe,
            "stopLossActive":stop_loss})
    print()
    for k,v in pd.DataFrame(info_1).items():
        print(k, v.values)
    
    # pertinent df indexes
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1 
    triple_previous_row_index = previous_row_index - 1
    
    # most recent 'full' {timeframe} candles - ohlc for 
    open_price = df[-1:].reset_index(drop=True)['open'][0]
    high_price = df[-1:].reset_index(drop=True)['high'][0]
    low_price = df[-1:].reset_index(drop=True)['low'][0]
    close_price = df[-1:].reset_index(drop=True)['close'][0]
    
    # most recent 'full' 1m-candles - ohlc for 
    bars_2 = exchange.fetch_ohlcv(f'{ticker}', timeframe="1m", limit=100)
    df_2 = pd.DataFrame(bars_2[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])    
    df_2['timestamp'] = pd.to_datetime(df_2['timestamp'], unit='ms', utc=True).dt.tz_convert('US/Pacific')
    
    open_price_1m = df_2[-1:].reset_index(drop=True)['open'][0]
    high_price_1m = df_2[-1:].reset_index(drop=True)['high'][0]
    low_price_1m = df_2[-1:].reset_index(drop=True)['low'][0]
    close_price_1m = df_2[-1:].reset_index(drop=True)['close'][0]

    df_2 = supertrend(df_2)

    # presets for safe/unsafe liquidation
    max_low = min_sell_price * (1 + min_gain)

    safe_sell = max_low <= low_price_1m
    
    unsafe_sell = low_price_1m <= min_sell_price * (1 - max_loss)

    # updated info
    info_2 = []
    info_2.append({"open":open_price_1m, "high":high_price_1m, "low":low_price_1m,
            "close":close_price_1m, "stopLoss":min_sell_price * (1 - max_loss),
            "prevPurchPrice":min_sell_price, "maxLow":max_low,
            "timeframe":timeframe, "safeSell":safe_sell, "sL-breach":unsafe_sell, "returnSincePrev %":((close_price_1m / min_sell_price - 1) * 100)})
    print()
    for k,v in pd.DataFrame(info_2).items():
        print(k, v.values)

    # {~peak analysis~}
    # typically, peaks can be found when the high wick appears to be the highest point in your time window (ex. 500) note: this would be most effective when 500 <= timeframe. peak is found when current close_price_1m >= df.max()['high'], as shown:
    #peak = df.max()['high'] <= close_price_1m
    # or explicitly
    peak = df.max()['high'] < close_price_1m
    print(f"\n(500)-window peak sell @: {df.max()['high']}")
    print(f"Peak reached: {peak}")
    # bot should execute sell order when peak == True even when df_prev & df_last in_uptrend.
    # currently, it will identify a peak when low_price >= df.max() * (1 + 11%)
    if df['in_uptrend'][triple_previous_row_index] and df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        
        if in_position and peak and (df.max()['high'] <= low_price_1m):
            # SELL
            print("\nYo! Haha that's great we just reach a peakage (❍ᴥ❍ʋ) woah! ")
            print("\nI hear ya! Executing a profitable peakage sell order | (• ◡•)|")

            order = exchange.create_market_sell_order(f'{ticker}',order_size)

            print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")

            quant = float(order['info']['executedQty'])
            min_sell_price = float(order['trades'][0]['info']['price'])

            print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

            in_position = False

            order_size = order_size*(0.95)
            
            # pd.DataFrame(order)
            order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
            order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')
            print(order[['symbol','transactTime','executedQty','price_y','status','type','side','commission','commissionAsset']])

            # limits the size reduction from above
            if order_size < og_size * 0.93:
                order_size = og_size
        # {end peak analysis}

    # goes to downtrend
    # if df['in_uptrend'][triple_previous_row_index] and not df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
    # or 
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:

        if in_position and safe_sell:

            print("\nExecuting a profitable downtrend sell | (• ◡•)|")
            # SELL
            # send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)

            print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")
            
            quant = float(order['info']['executedQty'])
            min_sell_price = float(order['trades'][0]['info']['price'])

            print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

            in_position = False

            order_size = order_size*(0.95)
            
            # pd.DataFrame(order)
            order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
            order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')

            print(order[['symbol','transactTime','executedQty','price_y','status','type','side','commission','commissionAsset']])

            # limits the size reduction from above
            if order_size < og_size * 0.93:
                order_size = og_size
        
        if autopilot == True and safe == False and in_position and not safe_sell:
            
            print("\nExecuting autopilot downtrend sell | (• _•)|")

            # SELL
            # send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)

            print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")
            
            quant = float(order['info']['executedQty'])
            min_sell_price = float(order['trades'][0]['info']['price'])

            print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

            in_position = False

            order_size = order_size*(0.95)
            
            # pd.DataFrame(order)
            order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
            order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')

            print(order)

            if order_size < og_size * 0.93:
                order_size = og_size

        if autopilot == True and safe == True and in_position and not safe_sell:
            
            print("\nSafemode on, did not execute autopilot downtrend sell | (• ◡•)|")

        
        if autopilot == False and safe == True and in_position and not safe_sell:
            execute = input("Execute un-profitable sell? (y/n): ")

            if execute == "Yes" or "Y" or "y":
                
                print("Executing an approved un-profitable sell | (• ◡•)|")
                
                # SELL
                # send binance sell order
                order = exchange.create_market_sell_order(f'{ticker}',order_size)
                
                # calculates loss/gain = 1 - (last_purchase_price/sold_purchase_price)
                print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")

                quant = float(order['info']['executedQty'])
                min_sell_price = float(order['trades'][0]['info']['price'])

                print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

                in_position = False

                order_size = order_size*(0.95)
                
                # pd.DataFrame(order)
                order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
                order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')

                print(order[['symbol','transactTime','executedQty','price_y','status','type','side','commission','commissionAsset']])

                # limits the size reduction from above
                if order_size < og_size * 0.93:
                    order_size = og_size

            if execute == "No" or "N" or "n":
                print("No sell.")


    # goes to uptrend
    if not df['in_uptrend'][triple_previous_row_index] and df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:

        print("\nChanged to uptrend! | (• ◡•)| Mathematical!")

        # enter position when in_uptrend True
        if not in_position:
            print("Executing an uptrend purchase")

            # BUY
            order = exchange.create_market_buy_order(f'{ticker}', order_size)
            
            # just catching how many i caught
            quant = float(order['info']['executedQty'])

            # replaces min_sell_price by purchase_price
            min_sell_price = float(order['trades'][0]['info']['price']) 
            
            # we are now in_position
            in_position = True

            print(f"Purchased @ ${min_sell_price:n} for ${min_sell_price * quant:n}")       
            
            # reset min_sell_price to reflect 1 + min_gain for profit
            min_sell_price = float(order['trades'][0]['info']['price']) * (1 + min_gain)
            
            # pd.DataFrame(order)
            order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
            order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')

            print(order[['symbol','transactTime','executedQty','price_y','status','type','side','commission','commissionAsset']])
            
        else:
            print(f"\nThis is a mathematical opportunity to increase your position in {tick}, boom-shaka! ┌( ಠ_ಠ)┘ ")    
    
    # stop-loss
    if not df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        # safe sell
        if autopilot == True and safe == True and stop_loss == True and in_position and safe_sell:
                # SELL
                print("\nExecuting a profitable triple-downtrend sell.")
                order = exchange.create_market_sell_order(f'{ticker}',order_size)

                # calculates loss/gain = 1 - (last_purchase_price/sold_purchase_price)
                print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")

                quant = float(order['info']['executedQty'])
                min_sell_price = float(order['trades'][0]['info']['price'])

                print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

                in_position = False

                order_size = order_size*(0.95)
                
                # pd.DataFrame(order)
                order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
                order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')
                
                print(order[['symbol','transactTime','executedQty','price_y','status','type','side','commission','commissionAsset']])

                # limits the size reduction from above
                if order_size < og_size * 0.93:
                    order_size = og_size
        
        # unsafe sell: low_price_1m <= min_sell_price * (1 - max_loss)
        if autopilot == True and safe == True and stop_loss == True and in_position and unsafe_sell:
            
            print(f"\nExecuting an un-profitable sell | (• ◡•)|, stop-loss triggered @ -{max_loss}%")

            # SELL
            # send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)

            # calculates loss/gain = 1 - (last_purchase_price/sold_purchase_price)
            print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")
            
            quant = float(order['info']['executedQty'])
            min_sell_price = float(order['trades'][0]['info']['price'])

            print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

            in_position = False

            order_size = order_size*(0.95)
            
            # pd.DataFrame(order)
            order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
            order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')

            print(order[['symbol','transactTime','executedQty','price_y','status','type','side','commission','commissionAsset']])

            # limits the size reduction from above
            if order_size < og_size * 0.93:
                order_size = og_size

        if autopilot == True and safe == True and stop_loss == False and in_position and unsafe_sell:
            print("\nStop-loss alert triggered, but sell action NOT activated. Still in position.\n")

        if autopilot == True and safe == False and stop_loss == True and in_position and unsafe_sell:
            print(f"\nExecuting an un-profitable sell | (• ◡•)|, stop-loss triggered @ -{max_loss}%")

            # SELL
            # send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)
            
            quant = float(order['info']['executedQty'])
            min_sell_price = float(order['trades'][0]['info']['price'])

            print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

            in_position = False

            order_size = order_size*(0.95)
            
            # pd.DataFrame(order)
            order = pd.merge(pd.DataFrame.from_dict(order['info']).drop(columns='fills'),pd.DataFrame.from_dict(order['info']['fills']),on=pd.DataFrame.from_dict(order['info']).index)
            order['transactTime'] = pd.to_datetime(order['transactTime'], unit='ms', utc=True).dt.tz_convert('US/Pacific')

            print(order[['symbol','transactTime','executedQty','price_y','status','type','side','commission','commissionAsset']])

            # limits the size reduction from above
            if order_size < og_size * 0.93:
                order_size = og_size            
# end

############################# 
# do it... just do it
def run_bot():
    print()
    print("\n##~####~####~##  ┌( ಠ_ಠ)┘  ##~####~####~##\n")
    print(datetime.now(tzlocal()).isoformat())

    # hi
    print(f"\nGenerating market indications for {name}.")
    
    # pulls in df to be used for calculations
    bars = exchange.fetch_ohlcv(f'{ticker}', timeframe=timeframe, limit=500)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True).dt.tz_convert('US/Pacific')
        
    # application of supertrend formula
    supertrend_data = supertrend(df)
    
    # decides & executes orders
    check_buy_sell_signals(supertrend_data)
        
"""
Run Bot, To the Moon
"""
schedule.every(randint(a,b)).seconds.do(run_bot)
# variable assigned to exercising the bot
bot = True
while bot:
    schedule.run_pending()
    time.sleep(0)