import config
import ccxt
import multiprocessing
from multiprocessing import Process, Pipe, Manager
import threading
import logging
import logging.handlers
import pandas_ta as ta
import json
from copy import copy, deepcopy
import pandas as pd
import numpy as np
import schedule
from message import *
import os
import time

# just for me 
import warnings
warnings.filterwarnings("ignore")


rootLogger = logging.getLogger('')
rootLogger.setLevel(logging.INFO)
socketHandler = logging.handlers.SocketHandler('localhost', logging.handlers.DEFAULT_TCP_LOGGING_PORT)
rootLogger.addHandler(socketHandler)


def wait_until_complete(manager):
    processes = multiprocessing.active_children()
    while processes:
        if len(processes) == 1 and processes[0].name.startswith('SyncManager'):
            manager.shutdown()
        processes = multiprocessing.active_children()


class BinanceMaster(ccxt.binanceus):

    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 100
    RSI_OVERSOLD = 30
    TEST_SYMBOL = 'DOGE/USDT'
    
    def __init__(self, account_config=None, master_id=0, duration=500, interval=30):
        
        self.master_id = master_id
        self.connections = dict()
        self.ohlcv_limit = 100
        self._kill_run = False
        self.duration = duration
        self.interval = interval
        
        if account_config is None or not self._validate_config(account_config):
            self.config = {}
        else:
            self.config = account_config
            
    def _validate_config(self, config_dict):
        try:
            contains_api_key = 'apiKey' in config_dict.keys()
            contains_secret_key = 'secret' in config_dict.keys()
        except Exception:
            return False
        else:
            return contains_api_key and contains_secret_key
            
    def send_message(self, message, close=False):
        for name, conn in self.connections.items():
            conn.send(message)
            if close:
                conn.close()
        
    def _fetch_prices(self):
        
        data = self.fetch_ohlcv(self.TEST_SYMBOL, timeframe="1m", limit=self.ohlcv_limit)
        
        # grab elements of every OHLCV list for O,H,L,C prices
        opens = np.array([record[1] for record in data])
        highs = np.array([record[2] for record in data])
        lows = np.array([record[3] for record in data])
        closes = np.array([record[4] for record in data])
        
        return opens, highs, lows, closes
    
    
    
    # Calculations and Signal Verification #######################################################

    def calculate_indicator(self, opens, highs, lows, closes):
        
        # could stay as series for better comp-eff?
        df = pd.DataFrame({"open":opens, "high":highs, "low":lows, "close":closes})
        
        close = df['close'][len(df)-1]

        # conditions passed          
        ema_33 = df.ta.ema(33)[-1:].reset_index(drop=True)[0]
        ema_99 = df.ta.ema(99)[-1:].reset_index(drop=True)[0]
        ema_crossover = ema_33 > ema_99
        
        isa_9 = df.ta.ichimoku()[1]['ISA_9'].tail(1).values[0] # help(ta.ichimoku)
        isb_26 = df.ta.ichimoku()[1]['ISB_26'].tail(1).values[0]
        
        amat = (df.ta.amat()['AMATe_LR_8_21_2'].tail(1).values[0] == 1)
        
        rsi = df.ta.rsi()[len(df)-1]
        rsi_buy = rsi < 35
        rsi_sell = rsi > 65
            
        try: 
            chop = "{:.2f}".format(df.ta.chop()[len(df.ta.chop())-1]) 
        except RunTimeWarning:
            chop = 0
        

        #if ((close*1.1 < isa_9) or (close*1.1 < isb_26)) & amat & ema_crossover & rsi_buy: # wants all true
        #    ind = "BUY"
        #elif ((close*1.1 > isa_9) or (close*1.1 > isb_26)) & ~amat & ~ema_crossover & rsi_sell:
        #    ind = "SELL"  

        return isa_9, isb_26, chop, amat, ema_crossover, rsi


    def _execute_loop(self, status_table=None):
        logger = logging.getLogger(f'maestro-{self.master_id}')
        
        # prices
        opens = self._fetch_prices()[0]
        highs = self._fetch_prices()[1]
        lows = self._fetch_prices()[2]
        closes = self._fetch_prices()[3]
        
        logger.info(f"Close price: {closes[-1:]}")
        
        # indicators
        indicator = self.calculate_indicator(opens, highs, lows, closes)
        
        logger.info(f"Ichimoku Senkou A9: {indicator[0]}")
        logger.info(f"Ichimoku Senkou B26: {indicator[1]}")
        logger.info(f"Choppiness Idx: {indicator[2]}%")
        
        if indicator[3]:
            direction = "Up"
        else:
            direction = "Down"
        logger.info(f"Archer MA Trend: {direction}")
        
        if indicator[4]:
            cross = "Below"
        else:
            cross = "Above"
            
        logger.info(f"EMA Crossover 33_99: {cross}") 
        
        logger.info(f"RSI: {indicator[5]}") 
        
        #logger.info(f"Indicator: {indicator[0]}")
        
        logger.info("------------------------------") 
        
        
        #message = MessageData(ORDER_MSG)
        #message.name = f'maestro-{self.master_id}'
        #message.body.symbol = self.TEST_SYMBOL
        #message.body.indicator = 'RSI'
        
        # messenger
        #if rsi > self.RSI_OVERBOUGHT:
        #    message.body.action = 'SELL'
        #    self.send_message(message.to_json())
        #elif rsi < self.RSI_OVERSOLD:
        #    message.body.action = 'BUY'
        #    self.send_message(message.to_json())
        #else:
        #    logger.info('RSI ACTION: NONE')
       
    
    
        self.log_status_table(status_table)
    #
    # End of Calculations and Signal Verification
    
    def run(self, connections, status_table):
        super().__init__(self.config)
        self.connections = connections
        self._pid = os.getpid()
        status_table[self._pid] = 'up'
        
        timer = threading.Thread(target=self._timer_thread, daemon=False)
        timer.start()
        
        schedule.every(self.interval).seconds.do(self._execute_loop, status_table=status_table).tag('indicator')
        
        while True:
            schedule.run_pending()
            if self._kill_run:
                self.send_message('END TRADING', close=True)
                schedule.clear('indicator')
                break
                
        status_table[self._pid] = 'down'
        self.log_status_table(status_table)
        
    def _timer_thread(self):
        time.sleep(self.duration)
        self._kill_run = True
        
    def log_status_table(self, status_table):
        logger = logging.getLogger(f'maestro-{self.master_id}-stat')
        try:
            d = dict(status_table)
        except Exception as e:
            logger.info(str(e))
        else:
            logger.info(json.dumps(d))
            

class BinanceTrader(ccxt.binanceus):
    
    def __init__(self, name, user_config=None):
        
        self.user_name = name
        
        if user_config is None or not self._validate_config(user_config):
            self.config = {}
        else:
            self.config = user_config
        
    def _validate_config(self, config_dict):
        try:
            contains_api_key = 'apiKey' in config_dict.keys()
            contains_secret_key = 'secret' in config_dict.keys()
        except Exception:
            return False
        else:
            return contains_api_key and contains_secret_key
        
    def get_user_name(self):
        return self.user_name
        
    def recv_message(self, conn):
        logger = logging.getLogger(f'{self.get_user_name()}')
        while True:
            message = conn.recv()
            logger.info(message)
            if message == 'END TRADING':
                conn.close()
                break
        
    def run(self, conn, status_table):
        super().__init__(self.config)
        self._pid = os.getpid()
        status_table[self._pid] = 'up'
        self.recv_message(conn)
        status_table[self._pid] = 'down'
        self.log_status_table(status_table)

    def log_status_table(self, status_table):
        logger = logging.getLogger(f'{self.get_user_name()}-stat')
        try:
            d = dict(status_table)
        except Exception as e:
            logger.info(str(e))
        else:
            logger.info(json.dumps(d))
        

if __name__ == '__main__':
    
    logging.info('\n\nstarting log')    
    group = ['trader1']
    master_connections = dict()
    traders = []
    
    manager = Manager()
    status_table = manager.dict()
    
    for name in group:
        parent_conn, child_conn = Pipe(duplex=True)
        master_connections[name] = parent_conn
        trader = BinanceTrader(name)
        p = Process(target=trader.run, args=(child_conn, status_table), daemon=False)
        traders.append(p)

    master_config = {'apiKey': config.apiKey,
                     'secret': config.secret,
                     'enableRateLimit': True,
                     'options' : {'adjustForTimeDifference': True}}
    
    master = BinanceMaster(account_config=master_config)
    p = Process(target=master.run, args=(master_connections, status_table), daemon=False)
    p.start()
        
    for trader in traders:
        trader.start()
    
    wait_until_complete(manager)