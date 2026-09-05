import pytest
from unittest.mock import patch, MagicMock
from app.core.mt5_provider import MT5Provider
import pandas as pd

def test_mt5_provider_initialization():
    provider = MT5Provider()
    assert provider.connected == False

@patch("app.core.mt5_provider.mt5")
def test_mt5_provider_connect(mock_mt5):
    mock_mt5.initialize.return_value = True
    provider = MT5Provider()
    assert provider.connect() == True
    assert provider.is_connected() == True

@patch("app.core.mt5_provider.mt5")
def test_mt5_provider_disconnect(mock_mt5):
    provider = MT5Provider()
    provider.connected = True
    provider.disconnect()
    assert provider.is_connected() == False
    mock_mt5.shutdown.assert_called_once()

@patch("app.core.mt5_provider.mt5")
def test_mt5_provider_get_symbols(mock_mt5):
    mock_symbol = MagicMock()
    mock_symbol.name = "XAUUSD"
    mock_mt5.symbols_get.return_value = [mock_symbol]
    
    provider = MT5Provider()
    provider.connected = True
    symbols = provider.get_symbols()
    
    assert len(symbols) == 1
    assert symbols[0] == "XAUUSD"

@patch("app.core.mt5_provider.mt5")
def test_mt5_provider_get_candles(mock_mt5):
    import numpy as np
    mock_data = np.array([
        (1672531200, 1800.0, 1805.0, 1795.0, 1802.0, 100, 1, 0)
    ], dtype=[('time', 'i8'), ('open', 'f8'), ('high', 'f8'), ('low', 'f8'), ('close', 'f8'), ('tick_volume', 'i8'), ('spread', 'i4'), ('real_volume', 'i8')])
    mock_mt5.copy_rates_from_pos.return_value = mock_data
    
    provider = MT5Provider()
    provider.connected = True
    
    df = provider.get_candles("XAUUSD", "M15", 1)
    
    assert not df.empty
    assert 'time' in df.columns
    assert len(df) == 1
