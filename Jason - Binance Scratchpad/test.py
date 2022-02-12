import config
import ccxt
from multiprocessing import Process, Pipe
import logging
import logging.handlers
import json
from copy import copy
import numpy as np
import schedule
from message import *


rootLogger = logging.getLogger('')
rootLogger.setLevel(logging.INFO)
socketHandler = logging.handlers.SocketHandler('localhost', logging.handlers.DEFAULT_TCP_LOGGING_PORT)
rootLogger.addHandler(socketHandler)


class BinanceMaster(ccxt.binanceus):

    RSI_PERIOD = 14
    RSI_OVERBOUGHT = 60
    RSI_OVERSOLD = 40
    TEST_SYMBOL = 'BTC/USDT'
    
    def __init__(self, account_config=None, master_id=0):
        
        self.master_id = master_id
        self.connections = dict()
        self.ohlcv_limit = 25
        
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
            
    def send_message(self, message):
        for name, conn in self.connections.items():
            conn.send(message)
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
        
    def _execute_loop(self):
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
            logger.info(message.to_json())
        elif rsi < self.RSI_OVERSOLD:
            message.body.action = 'BUY'
            self.send_message(message.to_json())
            logger.info(message.to_json())
        else:
            logger.info('RSI ACTION: NONE')        
        
    def run(self, connections):
        self.connections = connections
        super().__init__(self.config)
        schedule.every(60).seconds.do(self._execute_loop)
        while True:
            schedule.run_pending()
            

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
        logger = logging.getLogger(f'{self.user_name}')
        logger.info(conn.recv())
        
    def run(self, conn):
        super().__init__(self.config)
        self.recv_message(conn)


if __name__ == '__main__':
    
    logging.info('starting log')
    
    master_config = {'apiKey': config.API_KEY,
                     'secret': config.SECRET_KEY,
                     'enableRateLimit': True,
                     'options' : {'adjustForTimeDifference': True}}
                     
    master = BinanceMaster(account_config=master_config)
    
    group = ['trader1', 'trader2']
    master_connections = dict()
    traders = []
    
    for name in group:
        parent_conn, child_conn = Pipe(duplex=True)
        master_connections[name] = parent_conn
        trader = BinanceTrader(name)
        p = Process(target=trader.run, args=(child_conn,), daemon=False)
        traders.append(p)
        
    p = Process(target=master.run, args=(master_connections,), daemon=False)
    p.start()
        
    for trader in traders:
        trader.start()