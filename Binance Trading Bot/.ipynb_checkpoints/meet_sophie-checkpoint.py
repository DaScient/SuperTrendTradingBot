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

ccxt.binanceus({ 'options':{ 'adjustForTimeDifference':True}})
exchange = ccxt.binanceus({
"apiKey": config.BINANCE_KEY,
"secret": config.BINANCE_SECRET,
'enableRateLimit': True})

# add a little bit of sentience hehehe
time.sleep(1)
print("\n\n...Welcome to Sophie,")

time.sleep(0)
print("\n....Our very first Sohpisticated trading bot.")

time.sleep(0)
q0 = input("\n.....Would you like to meet Sohpie before getting started? Yes/No: ").capitalize()

time.sleep(0)

# tradeable-user setting 
#################################################################
q1 = input("\n....Would you like Sophie to trade for you? (Yes/No): ").capitalize()

if q1 == "Yes":
    time.sleep(0)
    print(" \n.....Awesome! I'm sure you'll be happy with my performance.")

if q1 == "No":
    time.sleep(0)
    print(" \n....Great! I'll certainly keep a very close watch on your asset.")
    print(" \n..")
    print(" \n.")
#################################################################

if q0 == "Yes":
    #print("MEET SOPHIE!")
    print("""
 /$$   /$$ /$$         /$$     /$$                                     /$$              
| $$  | $$|__/        | $$    | $$                                    | $$              
| $$  | $$ /$$       /$$$$$$  | $$$$$$$   /$$$$$$   /$$$$$$   /$$$$$$ | $$              
| $$$$$$$$| $$      |_  $$_/  | $$__  $$ /$$__  $$ /$$__  $$ /$$__  $$| $$              
| $$__  $$| $$        | $$    | $$  \ $$| $$$$$$$$| $$  \__/| $$$$$$$$|__/              
| $$  | $$| $$        | $$ /$$| $$  | $$| $$_____/| $$      | $$_____/                  
| $$  | $$| $$        |  $$$$/| $$  | $$|  $$$$$$$| $$      |  $$$$$$$ /$$              
|__/  |__/|__/         \___/  |__/  |__/ \_______/|__/       \_______/|__/              
                                                                                        
                                                                                        
                                                                                        
 /$$$$$$ /$$                    /$$$$$$                      /$$       /$$           /$$
|_  $$_/| $/                   /$$__  $$                    | $$      |__/          | $$
  | $$  |_//$$$$$$/$$$$       | $$  \__/  /$$$$$$   /$$$$$$ | $$$$$$$  /$$  /$$$$$$ | $$
  | $$    | $$_  $$_  $$      |  $$$$$$  /$$__  $$ /$$__  $$| $$__  $$| $$ /$$__  $$| $$
  | $$    | $$ \ $$ \ $$       \____  $$| $$  \ $$| $$  \ $$| $$  \ $$| $$| $$$$$$$$|__/
  | $$    | $$ | $$ | $$       /$$  \ $$| $$  | $$| $$  | $$| $$  | $$| $$| $$_____/    
 /$$$$$$  | $$ | $$ | $$      |  $$$$$$/|  $$$$$$/| $$$$$$$/| $$  | $$| $$|  $$$$$$$ /$$
|______/  |__/ |__/ |__/       \______/  \______/ | $$____/ |__/  |__/|__/ \_______/|__/
                                                  | $$                                  
                                                  | $$                                  
                                                  |__/                                  
    """)
    print()
    ###########################################
    # meet sophie
    time.sleep(2)
    print("\n.")
    print("\n..Hi there! I'm Sophie, I'll be helping you trade your asset.")
    time.sleep(0)
    print("\n...Before we begin I have a few questions to help us get started.")
    time.sleep(0)
    ###########################################
else:
    pass

if q0 == "Yes":
    # introduce yourself to sophie
    name = input("\n......What would you like me to call you: ")
    time.sleep(0)
    print("\n.....Oh, what a wonderful name. Well, it's a pleasure doin' business with you",name,"!")
    time.sleep(0)
    print("\n....What is the prefix of the asset you want to trade?")
    time.sleep(0)
    tick = input("\n...Some popular ones are SHIB, DOGE, BTC, ETH, or VET: ").upper()
    time.sleep(0)
    print("\n..Nice! That's a great choice.")
    time.sleep(0)
    print("\n\n\n.What denomination do you want to trade",tick,"in?")
    ticker =  tick+"/"+input("\n..Maybe you have tradeable amounts of USD, BUSD, or USDT?: ")
    time.sleep(0)
    print("\n\n\n...This might be a silly question, but how often would you like to check up on this asset?")
    timeframe = input("\n....You can put anything like 1m, 5m, 15m, 30m, 1h, or 1d: ")
    
    if timeframe == "1m" or "5m":
        volatility = 0.654545454545454545454545454
        
    if timeframe == "15m" or "30m":
        volatility = 1.35454545454545454545454545454545
        
    else:
        volatility = 1.654545454545454545454545454
    time.sleep(0)
    
    print("\n\n\n.....Awesome! How many "+tick+" would you like me to continuously trade for you?")
    order_size = float(input("\n......Remember, all trades on Binance.US must be above $10: "))
    og_size = order_size
    time.sleep(0)
    
    q2 = str(input("\n\n\n.....Are you already holding ~10% more than this amount of "+tick+" in your portfolio? (Yes/No): ")).capitalize()
    if q2 == "Yes":
        in_position = True
        min_sell_price = float(input("\n....What was the price of "+tick+" when you bought them?: "))
    else:
        in_position = False
        min_sell_price = exchange.fetch_ohlcv('DOGE/USDT', timeframe="1m", limit=1)[0][4]
    
    time.sleep(0)
    
    max_loss = 0.5/100
    min_gain = 0.75/100
    
# tradeable-user
elif q1 == "Yes":
    # introduce yourself to bot
    name = input("\nEnter name: ")
    tick = input("\nInsert ticker: ")
    ticker=  tick+"/"+input("\nEnter the denomination of your trade, i.e. USD, BUSD, or USDT?: ")
    timeframe = input("\nYou can put anything like 1m, 5m, 15m, 30m, 1h, or 1d: ")
    
    # presets for volatility
    if timeframe == "1m" or "5m":
        volatility = 0.654545454545454545454545454
        
    if timeframe == "15m" or "30m":
        volatility = 1.35454545454545454545454545454545
        
    else:
        volatility = 1.654545454545454545454545454
    
    order_size = float(input("\nOrder size in "+tick+": "))
    og_size = order_size
    in_position = ast.literal_eval(input("\nAleady in desired holding position? - True/False: ").capitalize())
    
    min_sell_price = float(input("\nEnter average_price or most recent purchase price: "))
    max_loss = float(input("\nMax loss (example 0.51): "))/100
    min_gain = float(input("\nMin gain (example 1.05): "))/100

# let's start!
if q0 == "Yes":
    print("\n\nOkay! I have everything I need. Now you can just sit back and relax and watch me do what I do, I guess... you'll see my first analysis in",str(timeframe),".")

elif q1 == "Yes":
    print("\n\n Great! I'll start analyzing...")
    print("\tI'll get back to you in",str(timeframe)," with my first results.")

# non-tradeable user
elif q1 == "No":
    timeframe = input("Choose between - 1m, 5m, 15m, 30m, 1h, 1d: ")
    name = input("\nEnter name: ")
    tick = input("\nInsert ticker: ")
    ticker=  tick+"/"+input("\nEnter the denomination of your trade, i.e. USD, BUSD, or USDT?: ")
    volatility = 1.3535353535353535353535353535355335353535
    time.sleep(0)
    print("\n\n Great! I'll start analyzing...")
    print("\tI'll get back to you in",str(timeframe)," with my first results.")

print("\n#####  ┌( ಠ_ಠ)┘  #####")
time.sleep(2)

print("\n.......Beep Boop.")
time.sleep(0)

print("....\nBoop Boop.")
time.sleep(0)

print(".......\nBoop Beep Beep!") # bc why tf not?

# Randomizer for schedule. I know it's weird, but somehow it works nicely for me. 
# Feel free to remove randint(a,b) downstairs, and just let schedule(a).minutes.. 
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

# Analysis & decision making. This part could be extracted out into it's own class.
def check_buy_sell_signals(df):
    
    # Establish bot parameters
    global in_position, ticker, timeframe, min_sell_price, max_loss, min_gain, order_size
    print("\nCalculating", ticker , "data...")
    print(df.tail(3)[["timestamp", "volume", 'in_uptrend']])
        
    # extract last row for df
    last_row_index = len(df.index) - 1
    previous_row_index = last_row_index - 1 
    
    # most recent 'full' candlestick - ohlc
    open_price = df[-1:].reset_index(drop=True)['open'][0]
    high_price = df[-1:].reset_index(drop=True)['high'][0]
    low_price = df[-1:].reset_index(drop=True)['low'][0]
    close_price = df[-1:].reset_index(drop=True)['close'][0]
    
    # tradeable-user
    if q1 == "Yes":
        # {start of peak & trough - analysis}
        # i wanted to see if it's possible to catch a massive drop from which to sell
        # so i took the highest low in df & current_low:
        max_low = df.max()['low'] * (1 - max_loss)

        # a sell point from peak could be discovered when low price goes farther than recent max_low(1 - max_loss): 
        peak_sell = low_price < max_low

        print("\nLow price: ", str(low_price), "\tMax low: ", str(max_low))
        print("Close price: ", str(close_price), "\tPeak breached: ", str(peak_sell))

        # a sell point from trough could be discovered when low price goes above min_sell_price(1 + min_gain): 
        trough_sell = min_sell_price * (1 + min_gain) < low_price

        # check if min_sell_price < low_price - which would thus execute a sell
        print("High price", str(high_price), "\tTrough breached: ",trough_sell)

        print("\nMinimum sell price:", str(min_sell_price))
        # {end of peak & trough - analysis}
    
    # non-tradeable users
    elif q1 == "No":
        print("Open: ", open_price, "\tHigh:", high_price)
        print("Low: ", low_price, "Close: ", close_price)
        
    # check for uptrend - if in_uptrend goes from False to True
    if not df['in_uptrend'][previous_row_index] and df['in_uptrend'][last_row_index]:
        
        # all-user print out
        print("\nChanged to uptrend! | (• ◡•)| We can BUY here.")
        
        # tradeable-user
        if q1 == "Yes":
            # enter position when in_uptrend True
            if not in_position:
                # BUY 
                # send binance buy order
                order = exchange.create_market_buy_order(f'{ticker}', order_size)

                # i really should just output this as a dataframe()
                print('\nStatus:' + order['info']['status'],
                      '\nPrice:' + order['trades'][0]['info']['price'],
                      '\nQuantity:' + order['info']['executedQty'],
                      '\nType:' + order['info']['side'])

                # just catching how many i caught
                quant = float(order['info']['executedQty'])

                # replaces min_sell_price by purchase_price
                min_sell_price = float(order['trades'][0]['info']['price'])

                # we are now in_position
                in_position = True

                print("Purchased @ $",str(min_sell_price),"for $",str(min_sell_price * quant))
            else:
                print("Already in position ┌( ಠ_ಠ)┘ ")
        else:
            pass   
    
    # check for downtrend - if in_uptrend goes from True to False
    if df['in_uptrend'][previous_row_index] and not df['in_uptrend'][last_row_index]:
        print("\nChanged to downtrend... booo! (❍ᴥ❍ʋ) We can SELL here.")
        
        # tradeable-user
        if q1 == "Yes":
            # only sells if price is greater than (min_sell_price)*(markup)*(max_loss) or peak_sell = True
            if in_position and (trough_sell or peak_sell):

                # SELL
                # send binance sell order
                order = exchange.create_market_sell_order(f'{ticker}',order_size)

                print('\nStatus:' + order['info']['status'],
                      '\nPrice:' + order['trades'][0]['info']['price'],
                      '\nQuantity:' + order['info']['executedQty'],
                      '\nType:' + order['info']['side'])

                # we are no longer in_position
                in_position = False

                # reduces order size to mitigate Insufficient Funds error
                order_size = order_size*(1-0.0)

                # limits the size reduction from above
                if order_size < og_size * 0.85:
                    order_size = og_size
                else:
                    pass

                # calculates loss/gain = 1 - (last_purchase_price/sold_purchase_price)
                print("Loss/gain:",str(1-float(min_sell_price)/float(order['trades'][0]['info']['price'])))
            
            # i just can't help with these lol
            else:
                if randint(1,30) < 5:
                    print("\nI didn't find this to be an opportunity to sell (☞ﾟヮﾟ)☞ haha yay!")
                elif randint(1,15) < 4:
                    print("\n| (• ◡•)| 'Hey Jake! Should we sell here?' (❍ᴥ❍ʋ) \n\t\t'Yo, Finn! Whattup! No, definitely don't sell anything here yet.")
                else:
                    print("No selling opportunity.")
        else:
            pass

# do it... just do it
def run_bot():
    print()
    print("#####  ┌( ಠ_ಠ)┘  #####")
    print()
    print(datetime.now(tzlocal()).isoformat())
    
    # hi
    print("\nGenerating market indications for ",name)
    
    # pulls in df to be used for calculations
    bars = exchange.fetch_ohlcv(f'{ticker}', timeframe=timeframe, limit=50)
    df = pd.DataFrame(bars[:-1], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize(tz="America/Los_Angeles")
    
    print("\nApplying supertrend formula... ")
    supertrend_data = supertrend(df)
    check_buy_sell_signals(supertrend_data)
    
    # tradeable-user position data
    if q1 == "Yes":
        # determined initially by tradeable-user
        print("In position:", in_position, "\nTimeframe:", timeframe,"\n")

        # used to get balance of ticker. For future use; allow order_size to be dynamic variable.
        bal = pd.DataFrame(exchange.fetch_balance()['info']['balances'])
        bal['free'] = pd.to_numeric(bal['free'])
        bal = bal[bal.free!=0].drop(columns='locked').reset_index(drop=True)
        bal = bal[bal['asset']==ticker[:4].replace('/','')].reset_index(drop=True).free[0]

        # printouts 
        print("Balance:$", bal*bars[-1][1], "\tPosition:", bal)
        print("Order size:", str(order_size), "\tVolatility:", str(volatility))
        print("Min gain", str(min_gain), "\t\tMax loss:", str(max_loss))

"""
Run Bot, To the Moon
"""
schedule.every(randint(a,b)).seconds.do(run_bot)

# variable assigned to exercising the bot
bot = True
while bot:
    schedule.run_pending()
    time.sleep(0)