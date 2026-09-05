import pytest
import os
from unittest.mock import MagicMock
from app.core.historical_data import HistoricalDataManager
from app.core.mt5_provider import MT5Provider
import pandas as pd
import numpy as np

def test_export_candles(tmp_path):
    provider = MagicMock(spec=MT5Provider)
    
    # Mock data with proper columns
    data = {
        'time': [pd.Timestamp('2023-01-01', tz='UTC')],
        'open': [1800.0],
        'high': [1805.0],
        'low': [1795.0],
        'close': [1802.0],
        'tick_volume': [100],
        'spread': [10],
        'real_volume': [0]
    }
    df = pd.DataFrame(data)
    provider.get_candles.return_value = df
    
    manager = HistoricalDataManager(provider)
    manager.data_dir = tmp_path
    
    filepath = manager.export_candles("XAUUSD", "M15", 1)
    
    assert os.path.exists(filepath)
    
    exported_df = pd.read_csv(filepath)
    assert len(exported_df) == 1
    assert 'timestamp' in exported_df.columns
    assert 'symbol' in exported_df.columns
    assert 'timeframe' in exported_df.columns
    assert exported_df['symbol'].iloc[0] == "XAUUSD"
    assert exported_df['timeframe'].iloc[0] == "M15"
