import pytest
import pandas as pd
import numpy as np
from app.core.indicators import Indicators

def test_sma():
    data = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    sma = Indicators.calculate_sma(data, period=3)
    
    assert np.isnan(sma[0])
    assert np.isnan(sma[1])
    assert sma[2] == 2.0
    assert sma[9] == 9.0

def test_ema():
    data = pd.Series([1, 2, 3, 4, 5])
    ema = Indicators.calculate_ema(data, period=3)
    
    assert np.isnan(ema[0])
    assert np.isnan(ema[1])
    assert not np.isnan(ema[2])

def test_rsi():
    # Simple uptrend
    data = pd.Series(range(1, 20))
    rsi = Indicators.calculate_rsi(data, period=14)
    
    assert np.isnan(rsi[0])
    # Constant uptrend should push RSI to 100 over time
    assert rsi.iloc[-1] == 100.0

def test_atr():
    high = pd.Series([10, 11, 12, 13, 14])
    low = pd.Series([9, 10, 11, 12, 13])
    close = pd.Series([9.5, 10.5, 11.5, 12.5, 13.5])
    
    atr = Indicators.calculate_atr(high, low, close, period=3)
    assert np.isnan(atr[0])
    assert np.isnan(atr[1])
    assert not np.isnan(atr[2])
