import config
import ccxt
from multiprocessing import Process, Pipe


class BinanceMaster(ccxt.binanceus):
    
    def __init__(self, account_config=None, master_id=0):
        
        self.master_id = master_id
        self.connections = dict()
        
        if account_config is None or not self._validate_config(account_config):
            # will create super class but cannot fetch balance or create orders
            # must have valid config with API keys
            super().__init__()
        else:
            super().__init__(account_config)
            
    def _validate_config(self, config_dict):
        try:
            contains_api_key = 'apiKey' in config_dict.keys()
            contains_secret_key = 'secret' in config_dict.keys()
        except Exception:
            return False
        else:
            return contains_api_key and contains_secret_key
            
    def send_message(self, conn, message):
        conn.send(message)
        
    def run(self, connections):
        self.connections = connections
        for name, conn in self.connections.items():
            self.send_message(conn, f'{name} - Hello from the master!')
            conn.close()
            

class BinanceTrader(ccxt.binanceus):
    
    def __init__(self, name, user_config=None):
        
        self.user_name = name
        
        if user_config is None or not self._validate_config(user_config):
            # will create super class but cannot fetch balance or create orders
            # must have valid config with API keys
            super().__init__()
        else:
            super().__init__(user_config)
        
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
        print(conn.recv())
        
    def run(self, conn):
        self.recv_message(conn)
        

if __name__ == '__main__':
    
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