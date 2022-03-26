#================================================================
#
#   File name   : indicators.py
#   Author      : PyLessons
#   Created date: 2021-02-25
#   Website     : https://pylessons.com/
#   GitHub      : https://github.com/pythonlessons/RL-Bitcoin-trading-bot
#   Description : Used to plot 5 indicators with OHCL bars and etc.
#
#================================================================
import pandas as pd
from ta.trend import SMAIndicator, macd, PSARIndicator
from ta.volatility import BollingerBands
from ta.momentum import rsi
from utils import Plot_OHCL
from ta import add_all_ta_features, add_trend_ta, add_volume_ta, add_volatility_ta, add_momentum_ta, add_others_ta
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

def AddIndicators(df):
    # Add Simple Moving Average (SMA) indicators
    a, b, c = 11, 25, 132
    df[f"sma{a}"] = SMAIndicator(close=df["Close"], window=a, fillna=True).sma_indicator()
    df[f"sma{b}"] = SMAIndicator(close=df["Close"], window=b, fillna=True).sma_indicator()
    df[f"sma{c}"] = SMAIndicator(close=df["Close"], window=c, fillna=True).sma_indicator()
    # Add Bollinger Bands indicator
    indicator_bb = BollingerBands(close=df["Close"], window=20, window_dev=2)
    df['bb_bbm'] = indicator_bb.bollinger_mavg()
    df['bb_bbh'] = indicator_bb.bollinger_hband()
    df['bb_bbl'] = indicator_bb.bollinger_lband()

    # Add Parabolic Stop and Reverse (Parabolic SAR) indicator
    indicator_psar = PSARIndicator(high=df["High"], low=df["Low"], close=df["Close"], step=0.02, max_step=2, fillna=True)
    df['psar'] = indicator_psar.psar()

    # Add Moving Average Convergence Divergence (MACD) indicator
    #df["MACD"] = macd(close=df["Close"], window_slow=26, window_fast=12, fillna=True) # mazas

    # Add Relative Strength Index (RSI) indicator
    df["RSI"] = rsi(close=df["Close"], window=14, fillna=True) # mazas
    
    return df

def DropCorrelatedFeatures(df, threshold, plot):
    df_copy = df.copy()

    # Remove OHCL columns
    df_drop = df_copy.drop(["Date", "Open", "High", "Low", "Close", "Volume"], axis=1)

    # Calculate Pierson correlation
    df_corr = df_drop.corr()

    columns = np.full((df_corr.shape[0],), True, dtype=bool)
    for i in range(df_corr.shape[0]):
        for j in range(i+1, df_corr.shape[0]):
            if df_corr.iloc[i,j] >= threshold or df_corr.iloc[i,j] <= -threshold:
                if columns[j]:
                    columns[j] = False
                    
    selected_columns = df_drop.columns[columns]

    df_dropped = df_drop[selected_columns]

    if plot:
        # Plot Heatmap Correlation
        fig = plt.figure(figsize=(8,8))
        ax = sns.heatmap(df_dropped.corr(), annot=True, square=True)
        ax.set_yticklabels(ax.get_yticklabels(), rotation=0) 
        ax.set_xticklabels(ax.get_xticklabels(), rotation=45, horizontalalignment='right')
        fig.tight_layout()
        plt.show()
    
    return df_dropped

def get_trend_indicators(df, threshold=0.5, plot=False):
    df_trend = df.copy()
    
    # add custom trend indicators
    a, b, c = 11, 25, 132
    df_trend[f"sma{a}"] = SMAIndicator(close=df["Close"], window=a, fillna=True).sma_indicator()
    df_trend[f"sma{b}"] = SMAIndicator(close=df["Close"], window=b, fillna=True).sma_indicator()
    df_trend[f"sma{c}"] = SMAIndicator(close=df["Close"], window=c, fillna=True).sma_indicator()

    df_trend = add_trend_ta(df_trend, high="High", low="Low", close="Close")

    return DropCorrelatedFeatures(df_trend, threshold, plot)

def get_volatility_indicators(df, threshold=0.5, plot=False):
    df_volatility = df.copy()
    
    # add custom volatility indicators
    # ...

    df_volatility = add_volatility_ta(df_volatility, high="High", low="Low", close="Close")

    return DropCorrelatedFeatures(df_volatility, threshold, plot)

def get_volume_indicators(df, threshold=0.5, plot=False):
    df_volume = df.copy()
    
    # add custom volume indicators
    # ...

    df_volume = add_volume_ta(df_volume, high="High", low="Low", close="Close", volume="Volume")

    return DropCorrelatedFeatures(df_volume, threshold, plot)

def get_momentum_indicators(df, threshold=0.5, plot=False):
    df_momentum = df.copy()
    
    # add custom momentum indicators
    # ...

    df_momentum = add_momentum_ta(df_momentum, high="High", low="Low", close="Close", volume="Volume")

    return DropCorrelatedFeatures(df_momentum, threshold, plot)

def get_others_indicators(df, threshold=0.5, plot=False):
    df_others = df.copy()
    
    # add custom indicators
    # ...

    df_others = add_others_ta(df_others, close="Close")

    return DropCorrelatedFeatures(df_others, threshold, plot)

def get_all_indicators(df, threshold=0.5, plot=False):
    df_all = df.copy()
    
    # add custom indicators
    # ...

    df_all = add_all_ta_features(df_all, open="Open", high="High", low="Low", close="Close", volume="Volume")

    return DropCorrelatedFeatures(df_all, threshold, plot)

def indicators_dataframe(df, threshold=0.5, plot=False):
    trend       = get_trend_indicators(df, threshold=threshold, plot=plot)
    volatility  = get_volatility_indicators(df, threshold=threshold, plot=plot)
    volume      = get_volume_indicators(df, threshold=threshold, plot=plot)
    momentum    = get_momentum_indicators(df, threshold=threshold, plot=plot)
    others      = get_others_indicators(df, threshold=threshold, plot=plot)
    #all_ind = get_all_indicators(df, threshold=threshold)

    final_df = [df, trend, volatility, volume, momentum, others]
    result = pd.concat(final_df, axis=1)

    return result

if __name__ == "__main__":   
        #Read in historical data.
    ticker='DOGE-USDT'
    df  = pq.read_table(f'{ticker}.parquet').to_pandas().reset_index(drop=False)
    df  = df[['open_time','open','close','high','low','volume']]
    df = df.rename(columns={'open_time':'Date','open':'Open','close':'Close','high':'High','low':'Low','volume':'Volume'})
    df = df[df['Date'].astype(str).str.contains(' 12:00:00.*')==True].reset_index(drop=True)
    df = df.dropna()
    df = df.sort_values('Date')
    #df = AddIndicators(df)

    #test_df = df[-400:]

    #Plot_OHCL(df)
    get_others_indicators(df, threshold=0.5, plot=True)
