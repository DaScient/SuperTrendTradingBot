###############################################
# safemode - 
# does not allow for sell at loss. expect longer trade activity intervals.
###############################################

from IPython.display import clear_output
import schedule,warnings,time,ast,config
warnings.filterwarnings('ignore')
from dateutil.tz import tzlocal
from datetime import datetime
from random import randint
import robin_stocks as r
from random import seed
import pandas as pd
import numpy as np
from rich import print, pretty
pretty.install()

# {login}
user = "user1"

login = r.authentication.login(username=config.rh_username,password=config.rh_password,store_session=True)

    
access_token=login['access_token']
token_type=login['token_type']
# {end of login}

# set params
name = "user1"

tick = input("Insert ticker: ").upper()

deno = "USD"

ticker = tick+"/"+ deno


interval = input('Candlestick intervals ("15second", "hour", "day", or "week"): ').lower()

in_position = ast.literal_eval(input("Already in desired position? - True/False: ").capitalize())

autopilot = True # ast.literal_eval(input("Autopilot on? - True/False: ").capitalize())

# dynamic order_size - redundance?
print()
bal = pd.DataFrame(r.crypto.get_crypto_positions()).sort_values('quantity',ascending=False)
bal['quantity'] = pd.to_numeric(bal['quantity'])
bal['quantity_available'] = pd.to_numeric(bal['quantity_available'])
bal['asset'] = bal['currency'].apply(lambda x: x['code'])
bal['name'] = bal['currency'].apply(lambda x: x['name'])
bal = bal[bal.quantity > 0].reset_index(drop=True)

print(bal[['asset', 'quantity', 'quantity_available']])

tick_bal = float(bal[bal.asset == tick].quantity_available[0])

# get deno balance really quick here
profile = r.profiles.load_account_profile()
deno_bal =  float(pd.to_numeric(profile['crypto_buying_power']))

print("Crypto buying power: ", deno_bal)
print(f"{tick} price: ",float(r.crypto.get_crypto_quote(tick)['mark_price']))
print()

# determines if you want to enter a position
if not in_position:
    min_sell_price = float(r.crypto.get_crypto_quote(tick)['low_price']) # current low_price

elif in_position: # it's good to have a higher min_sell_price value
    min_sell_price = float(input("Previous purchase price: $"))
    
order_size = float(input("Enter quantity for trade: "))

min_gain = float(input("Enter percentage of minimum expected gain: %"))/100

max_loss = float(input("Enter percentage for maximum loss: %"))/100

# safemode on
safe = True # ast.literal_eval(input("Safemode on? - True/False: ").capitalize())

# stop-loss
stop_loss = True # ast.literal_eval(input("Activate stop-loss sell? - True/False: ").capitalize())

if interval == "15second":
    a = 15
    span = 'hour'
    
if interval == "hour":
    a = 3600
    span = 'day'
    
if interval == "day":
    a = 86400
    span = 'month'

if interval == "week":
    a = 86400*7
    span = 'year'
    
period = 1 
volatility = 0.005050608302615407

print(f"\nLoading...\nPlease allow for {interval} until initial results are printed.")
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
    
    global in_position, tick, interval, min_sell_price, min_gain, order_size, max_loss, tick_bal
    print(f"\nCalculating {tick} data...")
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
    
    # order_size
    bal = pd.DataFrame(r.crypto.get_crypto_positions()).sort_values('quantity',ascending=False)
    bal['quantity'] = pd.to_numeric(bal['quantity'])
    bal['quantity_available'] = pd.to_numeric(bal['quantity_available'])
    bal['asset'] = bal['currency'].apply(lambda x: x['code'])
    bal['name'] = bal['currency'].apply(lambda x: x['name'])
    bal = bal[bal.quantity > 0].reset_index(drop=True)

    # get deno balance really quick here
    profile = r.profiles.load_account_profile()
    deno_bal =  pd.to_numeric(profile['crypto_buying_power'])

    # get {ticker} balance here
    tick_bal = float(bal[bal.asset == tick].quantity_available[0])

    # updated info
    info_1 = []
    info_1.append({"inPosition":in_position, "positionSize in USD":(tick_bal * float(r.crypto.get_crypto_quote(tick)['mark_price'])), f"buyingPower":deno_bal, "orderSize":order_size, "minGain %":min_gain * 100,
            "maxLoss %":max_loss * 100, "safeMode":safe,
            "stopLossActive":stop_loss})
    print()
    for k,v in pd.DataFrame(info_1).items():
        print(k, v.values)
    
    # pertinent df indexes
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1 
    triple_previous_row_index = previous_row_index - 1
    
    # most recent 'full' {timeframe} candles - ohlc for tick
    df_2 = r.crypto.get_crypto_quote(tick)
    df_2['timestamp'] = pd.Timestamp.now().tz_localize('US/Pacific')
    open_price_1m = float(df_2['open_price'])
    high_price_1m = float(df_2['high_price'])
    low_price_1m = float(df_2['low_price'])
    close_price_1m = float(df_2['mark_price'])
    
    # presets for safe/unsafe liquidation
    max_low = min_sell_price * (1 + min_gain)

    safe_sell = max_low <= low_price_1m
    
    unsafe_sell = low_price_1m <= min_sell_price * (1 - max_loss)

    # updated info
    info_2 = []
    info_2.append({"open":open_price_1m, "high":high_price_1m, "low":low_price_1m,
            "close":close_price_1m, "stopLoss":min_sell_price * (1 - max_loss),
            "prevPurchPrice":min_sell_price, "maxLow":max_low,
            "timeframe":interval, "safeSell":safe_sell, "sL-breach":unsafe_sell, "returnSincePrev %":((close_price_1m / min_sell_price - 1) * 100)})
    print()
    for k,v in pd.DataFrame(info_2).items():
        print(k, v.values)

    # {~peak analysis~}
    peak = float(df.max()['high']) <= low_price_1m
    print(f"\n(500)-window peak sell @: {float(df.max()['high'])}")
    print(f"Peak reached: {peak}")

    if df['in_uptrend'][triple_previous_row_index] and df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        
        if in_position and peak and safe_sell:
            print("\nExecuting a safe sell.")
            # sell
            sell = r.orders.order_sell_crypto_by_quantity(tick, order_size)

            timestamp, price, quant, side, kind = pd.to_datetime(sell['created_at'], utc=True).tz_convert('US/Pacific'), float(sell['price']), float(sell['quantity']), sell['side'], sell['type']

            print(f"Loss/gain: {1-min_sell_price/price}")

            min_sell_price = price

            print(f"Sold @ ${price:n} for ${price * quant:n}")        

            in_position = False
            
            print("\nTime: ", timestamp, "\nPrice: ", price, "\nQuantity: ", quant, "Side: ", side, "Kind: ", kind)
        # {end peak analysis}

    # goes to downtrend
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:

        if in_position and safe_sell:
            print("\nExecuting a safe sell.")
            
            # sell
            sell = r.orders.order_sell_crypto_by_quantity(tick, order_size)
            time.sleep(5)
            timestamp, price, quant, side, kind = pd.to_datetime(sell['created_at'], utc=True).tz_convert('US/Pacific'), float(sell['price']), float(sell['quantity']), sell['side'], sell['type']

            print(f"Loss/gain: {1-min_sell_price/price}")

            min_sell_price = price

            print(f"Sold @ ${price:n} for ${price * quant:n}")        

            in_position = False
            
            print("\nTime: ", timestamp, "\nPrice: ", price, "\nQuantity: ", quant, "Side: ", side, "Kind: ", kind)
        
        if autopilot == True and safe == False and in_position and not safe_sell:
            print("\nExecuting an unsafe sell.")
            
            # sell
            sell = r.orders.order_sell_crypto_by_quantity(tick, order_size)

            timestamp, price, quant, side, kind = pd.to_datetime(sell['created_at'], utc=True).tz_convert('US/Pacific'), float(sell['price']), float(sell['quantity']), sell['side'], sell['type']

            print(f"Loss/gain: {1-min_sell_price/price}")

            min_sell_price = price

            print(f"Sold @ ${price:n} for ${price * quant:n}")        

            in_position = False
            
            print("\nTime: ", timestamp, "\nPrice: ", price, "\nQuantity: ", quant, "Side: ", side, "Kind: ", kind)
                
        if autopilot == True and safe == True and in_position and not safe_sell:
            
            print("\nSafemode on, did not execute autopilot downtrend sell | (• ◡•)|")

        
        if autopilot == False and safe == True and in_position and not safe_sell:
            execute = input("Execute un-profitable sell? (y/n): ")

            if execute == "Yes" or "Y" or "y":
                
                # sell
                sell = r.orders.order_sell_crypto_by_quantity(tick, order_size)

                timestamp, price, quant, side, kind = pd.to_datetime(sell['created_at'], utc=True).tz_convert('US/Pacific'), float(sell['price']), float(sell['quantity']), sell['side'], sell['type']

                print(f"Loss/gain: {1-min_sell_price/price}")

                min_sell_price = price

                print(f"Sold @ ${price:n} for ${price * quant:n}")        

                in_position = False

                print("\nTime: ", timestamp, "\nPrice: ", price, "\nQuantity: ", quant, "Side: ", side, "Kind: ", kind)

                if execute == "No" or "N" or "n":
                    print("No sell.")

    # goes to uptrend
    if not df['in_uptrend'][triple_previous_row_index] and df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:

        # enter position when in_uptrend True
        if not in_position:
            print("Executing an uptrend purchase")

            # buy
            # get usd balance really quick here
            profile = r.profiles.load_account_profile()
            deno_bal =  float(pd.to_numeric(profile['crypto_buying_power']))
            
            buy = r.orders.order_buy_crypto_by_quantity(tick, order_size)
            
            timestamp, min_sell_price, quant, side, kind = pd.to_datetime(buy['created_at'], utc=True).tz_convert('US/Pacific'), float(buy['price']), float(buy['quantity']), buy['side'], buy['type']
            
            # we are now in_position
            in_position = True

            print(f"Purchased @ ${min_sell_price:n} for ${min_sell_price * quant:n}")  
            print("\nTime: ", timestamp, "\nPrice: ", min_sell_price, "\nQuantity: ", quant, "Side: ", side, "Kind: ", kind)
            
        else:
            print(f"\nThis is a mathematical opportunity to increase your position in {tick}, boom-shaka! ┌( ಠ_ಠ)┘ ")    
    
    # stop-loss
    if not df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        
        if autopilot == True and safe == True and stop_loss == True and in_position and safe_sell:
            print("\nExecuting a safe sell.")
            # safe sell
            sell = r.orders.order_sell_crypto_by_quantity(tick, order_size)
            
            timestamp, price, quant, side, kind = pd.to_datetime(sell['created_at'], utc=True).tz_convert('US/Pacific'), float(sell['price']), float(sell['quantity']), sell['side'], sell['type']

            print(f"Loss/gain: {1-min_sell_price/price}")

            min_sell_price = price

            print(f"Sold @ ${price:n} for ${price * quant:n}")        

            in_position = False
            
            print("\nTime: ", timestamp, "\nPrice: ", price, "\nQuantity: ", quant, "Side: ", side, "Kind: ", kind)

        if autopilot == True and safe == True and stop_loss == False and in_position and unsafe_sell:
            print("\nStop-loss alert triggered, but sell action NOT activated. Still in position.\n")

        if autopilot == True and safe == False and stop_loss == True and in_position and unsafe_sell:
            print(f"\nExecuting an un-profitable sell | (• ◡•)|, stop-loss triggered @ -{max_loss}%")

            # sell
            sell = r.orders.order_sell_crypto_by_quantity(tick, order_size)
            
            timestamp, price, quant, side, kind = pd.to_datetime(sell['created_at'], utc=True).tz_convert('US/Pacific'), float(sell['price']), float(sell['quantity']), sell['side'], sell['type']

            print(f"Loss/gain: {1-min_sell_price/price}")

            min_sell_price = price

            print(f"Sold @ ${price:n} for ${price * quant:n}")        

            in_position = False
            
            print("\nTime: ", timestamp, "\nPrice: ", price, "\nQuantity: ", quant, "Side: ", side, "Kind: ", kind)
                
# end

############################# 
# do it... just do it
def run_bot():
    print()
    print("\n##~####~####~####~####~####~##\n")
    print(datetime.now(tzlocal()).isoformat())

    # hi
    print(f"\nGenerating market indications for {name}.")
    
    # pulls in df to be used for calculations
    df=pd.DataFrame.from_dict(r.crypto.get_crypto_historicals(tick, interval=interval, span=span, bounds='24_7', info=None))
    df['timestamp']=pd.to_datetime(df['begins_at'], format='%Y-%m-%d').dt.tz_convert('US/Pacific')
    df['open'] = df.apply(lambda x : float(x['open_price']),axis=1)
    df['high'] = df.apply(lambda x : float(x['high_price']),axis=1)
    df['low'] = df.apply(lambda x : float(x['low_price']),axis=1)
    df['close'] = df.apply(lambda x : float(x['close_price']),axis=1)
    df=df.drop(columns=['open_price','high_price','low_price'])
    df=df[:-1][['timestamp','open','high','low','close','volume']]
    
    # application of supertrend formula
    supertrend_data = supertrend(df)
    
    # decides & executes orders
    check_buy_sell_signals(supertrend_data)
        
"""
Run Bot, To the Moon
"""
schedule.every(a).seconds.do(run_bot)
# variable assigned to exercising the bot
bot = True
while bot:
    schedule.run_pending()
    time.sleep(0)