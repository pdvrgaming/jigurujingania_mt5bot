import pytest
import os
from unittest.mock import MagicMock
from app.core.bot_observer import BotObserver
from app.core.mt5_provider import MT5Provider
import pandas as pd
from pathlib import Path

def test_bot_observer_csv_creation(tmp_path):
    provider = MagicMock(spec=MT5Provider)
    
    # Mock config to use tmp_path
    import app.core.config as cfg
    old_get = cfg.config.get
    cfg.config.get = lambda k, d=None: str(tmp_path) if k == "data_directory" else d
    
    observer = BotObserver(provider)
    
    assert os.path.exists(observer.csv_path)
    
    df = pd.read_csv(observer.csv_path)
    assert 'timestamp_utc' in df.columns
    assert 'event_type' in df.columns
    assert 'position_id' in df.columns
    
    cfg.config.get = old_get

def test_bot_observer_baseline_and_poll(tmp_path):
    provider = MagicMock(spec=MT5Provider)
    provider.is_connected.return_value = True
    provider.get_positions.return_value = []
    provider.get_history_deals.return_value = []
    provider.get_history_orders.return_value = []
    provider.get_current_price.return_value = {"last": 1800.0}
    
    import app.core.config as cfg
    old_get = cfg.config.get
    cfg.config.get = lambda k, d=None: str(tmp_path) if k == "data_directory" else d
    
    observer = BotObserver(provider)
    observer.establish_baseline()
    
    # No positions initially
    assert len(observer.known_positions) == 0
    
    # Now simulate a new position
    provider.get_positions.return_value = [{
        "ticket": 12345,
        "type": 0, # BUY
        "volume": 1.0,
        "price_open": 1800.0,
        "sl": 1790.0,
        "tp": 1820.0,
        "price_current": 1801.0,
        "profit": 100.0,
        "swap": 0.0,
        "magic": 999,
        "comment": "EA"
    }]
    
    observer.poll()
    
    assert len(observer.known_positions) == 1
    assert 12345 in observer.known_positions
    
    df = pd.read_csv(observer.csv_path)
    # 1 for Price snapshot, 1 for position opened
    assert len(df) == 2
    assert "PRICE_SNAPSHOT" in df['event_type'].values
    assert "POSITION_OPENED" in df['event_type'].values
    
    cfg.config.get = old_get
