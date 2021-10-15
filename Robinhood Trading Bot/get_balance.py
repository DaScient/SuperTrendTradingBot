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

# {login} (ONLY NEED TO RUN THIS PART ONCE)
user = "user1"

login = r.authentication.login(username=config.rh_username,password=config.rh_password,store_session=True)

access_token=login['access_token']
token_type=login['token_type']
# {end of login}

print()
bal = pd.DataFrame(r.crypto.get_crypto_positions()).sort_values('quantity',ascending=False)
bal['quantity'] = pd.to_numeric(bal['quantity'])
bal['quantity_available'] = pd.to_numeric(bal['quantity_available'])
bal['asset'] = bal['currency'].apply(lambda x: x['code'])
bal['name'] = bal['currency'].apply(lambda x: x['name'])
bal = bal[bal.quantity > 0].reset_index(drop=True)

print(bal[['asset', 'quantity', 'quantity_available']])

profile = r.profiles.load_account_profile()
deno_bal =  pd.to_numeric(profile['crypto_buying_power'])
print("Crypto buying power: ", deno_bal)
print()