import config
import ccxt
import multiprocessing
from multiprocessing import Process, Pipe, Manager
import threading
import logging
import logging.handlers
import json
from copy import copy, deepcopy
import numpy as np
import schedule
from message import *
import os
import time


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
    RSI_OVERBOUGHT = 60
    RSI_OVERSOLD = 40
    TEST_SYMBOL = 'BTC/USDT'
    
    def __init__(self, account_config=None, master_id=0, duration=300, interval=30):
        
        self.master_id = master_id
        self.connections = dict()
        self.ohlcv_limit = 25
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
        
    def _fetch_close_prices(self):
        # using bitcoin ticker for testing
        data = self.fetch_ohlcv(self.TEST_SYMBOL, timeframe="1m", limit=self.ohlcv_limit)        
        # grab 2nd to last element of every OHLCV list for close prices
        return np.array([record[-2] for record in data][-(self.RSI_PERIOD+1):])        
            
    def calculate_rsi(self, closes):
        # https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/rsi
        close_deltas = np.diff(closes)
        avg_upward_delta = abs(np.mean(close_deltas[close_deltas >= 0]))
        avg_downward_delta = abs(np.mean(close_deltas[close_deltas < 0]))
        rsi = 100 - ( 100 / ( 1 + (avg_upward_delta / avg_downward_delta) ) )
        return rsi
        
    def _execute_loop(self, status_table=None):
        logger = logging.getLogger(f'maestro-{self.master_id}')
        close_prices = self._fetch_close_prices()
        rsi = self.calculate_rsi(close_prices)
        logger.info(f"RSI VALUE: {str(rsi)}")
        
        message = MessageData(ORDER_MSG)
        message.name = f'maestro-{self.master_id}'
        message.body.symbol = self.TEST_SYMBOL
        message.body.indicator = 'RSI'
        
        if rsi > self.RSI_OVERBOUGHT:
            message.body.action = 'SELL'
            self.send_message(message.to_json())
        elif rsi < self.RSI_OVERSOLD:
            message.body.action = 'BUY'
            self.send_message(message.to_json())
        else:
            logger.info('RSI ACTION: NONE')
        
        self.log_status_table(status_table)
        
    def run(self, connections, status_table):
        super().__init__(self.config)
        self.connections = connections
        self._pid = os.getpid()
        status_table[self._pid] = 'up'
        
        timer = threading.Thread(target=self._timer_thread, daemon=False)
        timer.start()
        
        schedule.every(self.interval).seconds.do(self._execute_loop, status_table=status_table).tag('rsi')
        
        while True:
            schedule.run_pending()
            if self._kill_run:
                self.send_message('END TRADING', close=True)
                schedule.clear('rsi')
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
    
    logging.info('starting log')    
    group = ['trader1', 'trader2']
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

    master_config = {'apiKey': config.API_KEY,
                     'secret': config.SECRET_KEY,
                     'enableRateLimit': True,
                     'options' : {'adjustForTimeDifference': True}}
    
    master = BinanceMaster(account_config=master_config)
    p = Process(target=master.run, args=(master_connections, status_table), daemon=False)
    p.start()
        
    for trader in traders:
        trader.start()
    
    wait_until_complete(manager)