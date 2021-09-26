import ccxt,schedule,warnings,time,ast,config
warnings.filterwarnings('ignore')
from dateutil.tz import tzlocal
from datetime import datetime
from random import randint
from random import seed
import pandas as pd
import numpy as np
from rich import print, pretty
pretty.install()

# login
ccxt.binanceus({ 'options':{ 'adjustForTimeDifference':True}})

# {random key generator}
# for reference see config.py
value = randint(2,199)
print(f"randint: {value}\n\n...")
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
ticker = tick+"/"+input("Enter denomination (examples: USD, USDT, BUSD, BTC): ").upper()
timeframe = input("Candlestick intervals (1m,5m,15m,30m,1h,2h,6h,1d): ").capitalize()
order_size = float(input("Order size in "+tick+": "))
og_size = order_size
in_position = ast.literal_eval(input("Already in desired holding position? - True/False: ").capitalize())

# it's good to have a higher min_sell_price value
min_sell_price = float(input("Minimum sell price: %"))

# having a very minimal max_loss threshold is beneficial
max_loss = 0.001 # float(input("Max loss: %"))/100

# it's not a bad idea to let this be higher
# the longer the bot will wait to sell
min_gain = float(input("Min gain: %"))/100

# randomizer for schedule. I know it's weird, but somehow it works nicely for me. 
# feel free to remove randint(a,b) downstairs, and just let schedule(a).minutes..
# also, volatilities might be okay as presets for now

if timeframe == "1m":
    a = 55
    b = 60
    
elif timeframe == "5m":
    a = 275
    b = 300
    
elif timeframe == "15m":
    a = 850
    b = 900
    
elif timeframe == "30m":
    a = 1775
    b = 1800
    
elif timeframe == "1h":
    a = 3575
    b = 3600

# https://medium.com/codex/algorithmic-trading-with-the-keltner-channel-in-python-9c272051d43d
# might be worth a try
volatility = 0.003545454
#volatility = 0.54545454

period = 42 #int(input("Enter the rolling average period (7 - 42): "))

print(f"Loading...\nPlease allow for {timeframe} until initial results are printed.")

# supertrend
# (tr) the true range indicator is taken as the greatest of the following: current high less the current low; the absolute value of the current high less the previous close; and the absolute value of the current low less the previous close
def tr(data):
    data['previous_close'] = data['close'].shift(1)
    data['high-low'] = abs(data['high'] - data['low'])
    data['high-pc'] = abs(data['high'] - data['previous_close'])
    data['low-pc'] = abs(data['low'] - data['previous_close'])
    tr = data[['high-low','high-pc','low-pc']].max(axis=1)
    return tr

# tr rolling average
def atr(data, period):
    data['tr'] = tr(data)
    atr = data['tr'].rolling(period).mean()
    return atr

# https://www.tradingfuel.com/supertrend-indicator-formula-and-calculation/ #It's important to treat the atr_multiplier as a variable. See supertrend_visualizer_parquet.py to see how atr_mult affects indication. Volatility rate varies from 0.0001 - 3. Smaller numbers for 1m intervals. Larger number for day or swing trades.

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

# analysis & decision making. This part could be extracted out into it's own class.
def check_buy_sell_signals(df):
    
    # Establish bot parameters
    global in_position, ticker, timeframe, min_sell_price, max_loss, min_gain, order_size
    print(f"\nCalculating {ticker} data...")
    print(df.tail(3)[["timestamp", "volume", 'in_uptrend']])
        
    # extract last row for df
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1 
    
    # most recent 'full' candlestick - ohlc
    open_price = df.reset_index(drop=True)['open'][0]
    high_price = df.reset_index(drop=True)['high'][0]
    low_price = df.reset_index(drop=True)['low'][0]
    close_price = df.reset_index(drop=True)['close'][0]
    
    # i wanted to create a separate frame of reference from a mini-1m timeframe
    # this might be able to calculate a downtrend during an immediate peak_sell event
    # thus allowing for more conditions be met
    bars_2 = exchange.fetch_ohlcv(f'{ticker}', timeframe="1m", limit=7)
    #df_2 = pd.DataFrame(bars_2[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    #trying different
    df_2 = pd.DataFrame(bars_2, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_2['timestamp'] = pd.to_datetime(df_2['timestamp'], unit='ms').dt.tz_localize(tz = "America/Los_Angeles")#tz = "America/Los_Angeles")

    # calculates most recent 1-minute trend
    # used to decide "volatility_sell"
    df_2 = supertrend(df_2)

    # creates a mini_timeframe analysis of trend - if downtrend, then it's a sign of immediate bearish market
    mini_downtrend = ~df_2[["in_uptrend"]].reset_index().in_uptrend[0]
    mini_uptrend = df_2[["in_uptrend"]].reset_index().in_uptrend[0]

    # {start of peak & trough - analysis}

    # i wanted to see if it's possible to catch a massive drop from which to sell
    # so i took the highest low in df & current_low:
    #max_low = df.max()['low'] * (1 - max_loss)

    # an honest max_low
    max_low = min_sell_price * (1 + max_loss)

    # a sell point from peak could be identified when low price goes above max_low * (1 + max_loss): 
    #peak_sell = max_low * (1 + max_loss) < low_price

    # or  a sell point from peak could be identified when low_price goes above max_low
    peak_sell = max_low < low_price

    # prints data
    print(f"\nLow price: {low_price} Max low: {max_low}")
    print(f"Close price: {close_price} Peak breached (downtrend-sell): {peak_sell}")

    # a sell point from trough could be identified when low price goes above min_sell_price(1 + min_gain): 
    trough_sell = min_sell_price * (1 + min_gain) < low_price

    # check if min_sell_price < low_price - which would thus execute a sell
    print(f"High price: {high_price} Trough breached (downtrend-sell): {trough_sell}")

    print(f"\nMinimum sell price: {min_sell_price}")
    # {end of peak & trough - analysis}

    ## {near-real-time volatility analysis} ##
    # another sell variable can be identified if trend in 1m timeframe changes
    # if mini_downtrend is identified, sophie trigger sells (see mini_downtrend above)
    if mini_downtrend and (min_sell_price * (1 + min_gain) < low_price):
        volatility_sell = True
    else:
        volatility_sell = False

    print(f"\nMini-timeframe downtrend identified - selling signal: {volatility_sell}")
    print(f"Mini-timeframe uptrend identified - buying signal: {not in_position and not mini_downtrend}")
    ## {end of near-real-time volatility analysis} ##


    # this part is only applicable to tradeable-user
    # here we consider conditions set above (peak_sell, trough_sell, & volatility_sell), as well as, 
    # other conditions in an uptrend for which we could execute an order

    # sells during a "1m timeframe" uptrend, when volitile_sell is triggered, 
    #and also respecting the above trough & peak selling conditions
    if df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:

        # under special circumstances, selling points can be found as stated below:
        if in_position and (min_sell_price * (1 + min_gain) < low_price) and (volatility_sell or peak_sell or trough_sell):

            # SELL - send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)
            time.sleep(2)
            print("\n Unless... it's actually a volitile mini-peakage. Oh! no | (• ◡•)|\n ......... Let's catch the next uphill.")

            print(f"\nStatus: {order['info']['status']},\
                  \nPrice: {order['trades'][0]['info']['price']},\
                  \nQuantity: {order['info']['executedQty']},\
                  \nType: {order['info']['side']}")

            # just catching how many i caught
            quant = float(order['info']['executedQty'])

            # notes sale data
            min_sell_price = float(order['trades'][0]['info']['price'])
            print(f"Sold @ ${min_sell_price:n}, for ${min_sell_price * quant:n}")     

            # calculates loss/gain = 1 - (last_purchase_price/sold_purchase_price)
            print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")

            # we are no longer in_position
            in_position = False

            # reduces order size to mitigate Insufficient Funds error
            order_size = order_size*(1-0.05)

            # limits the size reduction from above
            if order_size < og_size * 0.85:
                order_size = og_size
            else:
                pass

        # buys when it finds an immediate uptrend opportunity
        # also forces in_position = True, which can be very nice 
        # during positive trends/negative trends alike
        elif not in_position and not mini_downtrend:
            # BUY 
            # send binance buy order
            order = exchange.create_market_buy_order(f'{ticker}', order_size)

            # i really should just output this as a dataframe()
            print(f"\nStatus: {order['info']['status']},\
                  \nPrice: {order['trades'][0]['info']['price']},\
                  \nQuantity: {order['info']['executedQty']},\
                  \nType: {order['info']['side']}")

            # just catching how many i caught
            quant = float(order['info']['executedQty'])

            # replaces min_sell_price by purchase_price
            min_sell_price = float(order['trades'][0]['info']['price'])

            # we are now in_position
            in_position = True
            print(f"Purchased @ ${min_sell_price:n} for ${min_sell_price * quant:n}")   

    # check for downtrend - if in_uptrend goes from True to False
    if (df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]):
        
        # only sells if price is greater than 
        #(min_sell_price)*(markup)*(max_loss) or peak_sell = True or volatility_sell = True
        if in_position and (trough_sell or peak_sell):
            print("\nPotential trough/peak sell-off.")
            # SELL
            # send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)

            print(f"\nStatus: {order['info']['status']},\
                  \nPrice: {order['trades'][0]['info']['price']},\
                  \nQuantity: {order['info']['executedQty']},\
                  \nType: {order['info']['side']}")

            # just catching how many i caught
            quant = float(order['info']['executedQty'])

            print(f"Sold @ ${min_sell_price:n} for ${min_sell_price * quant:n}")        

            # we are no longer in_position
            in_position = False

            # reduces order size to mitigate Insufficient Funds error
            order_size = order_size*(1-0.1)

            # limits the size reduction from above
            if order_size < og_size * 0.95:
                order_size = og_size
            else:
                pass

            # calculates loss/gain = 1 - (last_purchase_price/sold_purchase_price)
            print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")

        # i just can't help with these lol
        elif in_position and not (trough_sell or peak_sell):
            print("Currently safe from trough/peak selling points.")


    # for the tradeable-user if we are in an uptrend & low_price stays above our min_sell, 
    # the bot will sell when trough_sell or peak_sell are triggered
    if (df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index] and min_sell_price * (1 + min_gain) < low_price):


        # only sells if price is greater than (min_sell_price)*(markup)*(max_loss) 
        #or peak_sell = True or volatility_sell = True
        if in_position and (trough_sell or peak_sell):

            # SELL
            # send binance sell order
            order = exchange.create_market_sell_order(f'{ticker}',order_size)

            print(f"\nStatus: {order['info']['status']},\
                  \nPrice: {order['trades'][0]['info']['price']},\
                  \nQuantity: {order['info']['executedQty']},\
                  \nType: {order['info']['side']}")

            # just catching how many i caught
            quant = float(order['info']['executedQty'])

            print(f"Sold @ ${min_sell_price:n}, for ${min_sell_price * quant:n}")         

            # we are no longer in_position
            in_position = False

            # reduces order size to mitigate Insufficient Funds error
            order_size = order_size*(1-0.1)

            # limits the size reduction from above
            if order_size < og_size * 0.85:
                order_size = og_size
            else:
                pass

            # calculates loss/gain = 1 - (last_purchase_price/sold_purchase_price)
            print(f"Loss/gain: {1-float(min_sell_price)/float(order['trades'][0]['info']['price'])}")

    # check for uptrend - if in_uptrend goes from False to True
    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:

        print("\nChanged to uptrend! | (• ◡•)| Mathematical!")

        # enter position when in_uptrend True
        if not in_position:

            # BUY -  send binance buy order
            order = exchange.create_market_buy_order(f'{ticker}', order_size)

            # i really should just output this as a dataframe()
            print(f"\nStatus: {order['info']['status']},\
                  \nPrice: {order['trades'][0]['info']['price']},\
                  \nQuantity: {order['info']['executedQty']},\
                  \nType: {order['info']['side']}")

            # just catching how many i caught
            quant = float(order['info']['executedQty'])

            # replaces min_sell_price by purchase_price
            min_sell_price = float(order['trades'][0]['info']['price'])

            # we are now in_position
            in_position = True

            print(f"Purchased @ ${min_sell_price:n}, for ${min_sell_price * quant:n}")       

        else:
            print(f"This could be a GREAT time to increase your position in {tick}, boom-shaka! ┌( ಠ_ಠ)┘ ")

############################# 
# do it... just do it
def run_bot():
    print()
    print("##~##  ┌( ಠ_ಠ)┘  ##~##")
    print(datetime.now(tzlocal()).isoformat())

    # hi
    print(f"Generating market indications for {name}.")
    
    # pulls in df to be used for calculations
    bars = exchange.fetch_ohlcv(f'{ticker}', timeframe=timeframe, limit=150)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize(tz = "America/Los_Angeles")#tz = "America/Los_Angeles")
        
    # application of supertrend formula
    supertrend_data = supertrend(df)
    
    # decides & executes orders
    check_buy_sell_signals(supertrend_data)
    
    # determined initially by tradeable-user
    print(f"\nIn position: {in_position}\nTimeframe: {timeframe}\n")

    # used to get balance of ticker. For future use; allow order_size to be dynamic variable.
    bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
    bal['free'] = pd.to_numeric(bal['free'])
    bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop = True)
    bal = bal[bal['asset']==ticker[:4].replace('/','')].reset_index(drop = True).free[0]

    # printouts 
    print(f"Balance:${bal * bars[-1][1]:n} Position: {bal:n}")
    print(f"Order size: {order_size} Volatility: {volatility}")
    print(f"Min gain: {min_gain} Max loss:{max_loss}")

"""
Run Bot, To the Moon
"""
schedule.every(randint(a,b)).seconds.do(run_bot)
# variable assigned to exercising the bot
bot = True
while bot:
    schedule.run_pending()
    time.sleep(0)
#NOTES
#############################