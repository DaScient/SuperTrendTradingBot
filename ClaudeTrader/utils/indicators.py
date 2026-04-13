"""
Technical Indicators Utility

Comprehensive collection of technical indicators for trading analysis.
"""

import numpy as np
from typing import List, Tuple


def calculate_sma(prices: List[float], period: int) -> List[float]:
    """Calculate Simple Moving Average"""
    sma = []
    for i in range(len(prices)):
        if i < period - 1:
            sma.append(np.mean(prices[:i+1]))
        else:
            sma.append(np.mean(prices[i-period+1:i+1]))
    return sma


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average"""
    ema = [prices[0]]
    multiplier = 2 / (period + 1)

    for price in prices[1:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])

    return ema


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """Calculate Relative Strength Index"""
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gains = []
    avg_losses = []

    # Initial averages
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    avg_gains.append(avg_gain)
    avg_losses.append(avg_loss)

    # Smoothed averages
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        avg_gains.append(avg_gain)
        avg_losses.append(avg_loss)

    # Calculate RSI
    rsi = []
    for avg_gain, avg_loss in zip(avg_gains, avg_losses):
        if avg_loss == 0:
            rsi.append(100)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))

    # Pad with initial values
    rsi = [50] * period + rsi

    return rsi


def calculate_macd(
    prices: List[float],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9
) -> Tuple[List[float], List[float], List[float]]:
    """Calculate MACD, Signal line, and Histogram"""

    # Calculate EMAs
    fast_ema = calculate_ema(prices, fast_period)
    slow_ema = calculate_ema(prices, slow_period)

    # MACD line
    macd_line = [fast - slow for fast, slow in zip(fast_ema, slow_ema)]

    # Signal line
    signal_line = calculate_ema(macd_line, signal_period)

    # Histogram
    histogram = [macd - signal for macd, signal in zip(macd_line, signal_line)]

    return macd_line, signal_line, histogram


def calculate_bollinger_bands(
    prices: List[float],
    period: int = 20,
    std_dev: float = 2.0
) -> Tuple[List[float], List[float], List[float]]:
    """Calculate Bollinger Bands"""

    middle_band = calculate_sma(prices, period)
    upper_band = []
    lower_band = []

    for i in range(len(prices)):
        if i < period - 1:
            std = np.std(prices[:i+1])
        else:
            std = np.std(prices[i-period+1:i+1])

        upper_band.append(middle_band[i] + std_dev * std)
        lower_band.append(middle_band[i] - std_dev * std)

    return upper_band, middle_band, lower_band


def calculate_atr(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> List[float]:
    """Calculate Average True Range"""

    tr_list = []

    for i in range(1, len(close)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
        tr_list.append(tr)

    # Calculate ATR as SMA of TR
    atr = []
    for i in range(len(tr_list)):
        if i < period - 1:
            atr.append(np.mean(tr_list[:i+1]))
        else:
            atr.append(np.mean(tr_list[i-period+1:i+1]))

    # Pad with first value
    atr = [atr[0]] + atr

    return atr


def calculate_stochastic(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> Tuple[List[float], List[float]]:
    """Calculate Stochastic Oscillator (%K and %D)"""

    k_values = []

    for i in range(len(close)):
        if i < period - 1:
            period_high = max(high[:i+1])
            period_low = min(low[:i+1])
        else:
            period_high = max(high[i-period+1:i+1])
            period_low = min(low[i-period+1:i+1])

        if period_high == period_low:
            k_values.append(50)
        else:
            k = 100 * (close[i] - period_low) / (period_high - period_low)
            k_values.append(k)

    # %D is 3-period SMA of %K
    d_values = calculate_sma(k_values, 3)

    return k_values, d_values


def calculate_adx(
    high: List[float],
    low: List[float],
    close: List[float],
    period: int = 14
) -> List[float]:
    """Calculate Average Directional Index"""

    # Simplified ADX calculation
    # Full implementation would include +DI, -DI, and DX

    tr_list = []
    for i in range(1, len(close)):
        tr = max(
            high[i] - low[i],
            abs(high[i] - close[i-1]),
            abs(low[i] - close[i-1])
        )
        tr_list.append(tr)

    atr = calculate_sma(tr_list, period)

    # Simplified ADX (placeholder)
    adx = [min(max(val * 0.5, 0), 100) for val in atr]

    return [25] + adx  # Pad with neutral value


def calculate_obv(close: List[float], volume: List[float]) -> List[float]:
    """Calculate On-Balance Volume"""

    obv = [volume[0]]

    for i in range(1, len(close)):
        if close[i] > close[i-1]:
            obv.append(obv[-1] + volume[i])
        elif close[i] < close[i-1]:
            obv.append(obv[-1] - volume[i])
        else:
            obv.append(obv[-1])

    return obv


def calculate_vwap(
    high: List[float],
    low: List[float],
    close: List[float],
    volume: List[float]
) -> List[float]:
    """Calculate Volume-Weighted Average Price"""

    vwap = []
    cumulative_tpv = 0
    cumulative_volume = 0

    for i in range(len(close)):
        typical_price = (high[i] + low[i] + close[i]) / 3
        tpv = typical_price * volume[i]

        cumulative_tpv += tpv
        cumulative_volume += volume[i]

        vwap.append(cumulative_tpv / cumulative_volume if cumulative_volume > 0 else typical_price)

    return vwap


if __name__ == "__main__":
    # Example usage
    prices = [100 + i + np.random.randn() for i in range(100)]

    sma = calculate_sma(prices, 20)
    ema = calculate_ema(prices, 20)
    rsi = calculate_rsi(prices, 14)

    print(f"Latest SMA: {sma[-1]:.2f}")
    print(f"Latest EMA: {ema[-1]:.2f}")
    print(f"Latest RSI: {rsi[-1]:.2f}")
