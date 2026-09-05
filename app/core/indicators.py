import pandas as pd
import numpy as np

class Indicators:
    @staticmethod
    def calculate_sma(series: pd.Series, period: int) -> pd.Series:
        return series.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False, min_periods=period).mean()

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)
        
        # Standard RSI using Wilders smoothing (Exponential Moving Average)
        avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        # Handle division by zero (if avg_loss is 0, RSI is 100)
        rsi = rsi.where(avg_loss != 0, 100)
        # First values will be NaN due to min_periods
        return rsi

    @staticmethod
    def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        # Wilder's smoothing for ATR
        atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
        return atr
