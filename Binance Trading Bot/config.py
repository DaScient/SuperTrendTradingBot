#KEEP ULTRA SAFE

from random import seed
from random import randint

BINANCE_KEY=""
BINANCE_SECRET=""

#Overclocking mitigation
#Create multiple API Instances and have them random loop through class below.
#Still needs development.
value = randint(0, 25)
if value < 5:
    BINANCE_KEY=""
    BINANCE_SECRET=""
if 6 <= value <= 10:
    BINANCE_KEY=""
    BINANCE_SECRET=""
if 11 <= value <= 15:
    BINANCE_KEY=""
    BINANCE_SECRET=""
if 16 <= value <= 20:
    BINANCE_KEY=""
    BINANCE_SECRET=""        
if 21 <= value <= 25:
    BINANCE_KEY=""
    BINANCE_SECRET=""

#Robinhood
rh_username = ""
rh_password = ""

