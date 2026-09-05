import pytest
import pandas as pd
from app.core.strategy_engine import StrategyEngine

def test_strategy_engine():
    engine = StrategyEngine()
    
    # Create simple dataframe
    data = {
        'timestamp': [1, 2, 3, 4],
        'close': [100.0, 105.0, 95.0, 110.0],
        'high': [101.0, 106.0, 96.0, 111.0],
        'low': [99.0, 104.0, 94.0, 109.0],
        'open': [100.0, 100.0, 105.0, 95.0]
    }
    df = pd.DataFrame(data)
    
    strategy = {
        "name": "Test Strategy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left": {"type": "price", "name": "close"},
                    "operator": ">",
                    "right": {"type": "constant", "value": 100.0}
                }
            ]
        }
    }
    
    signals = engine.evaluate(strategy, df)
    
    assert len(signals) == 2
    assert signals[0]['index'] == 1 # close 105 > 100
    assert signals[1]['index'] == 3 # close 110 > 100

def test_strategy_crosses_above():
    engine = StrategyEngine()
    
    # We will test SMA crossing
    data = {
        'timestamp': [1, 2, 3, 4],
        'close': [10.0, 10.0, 20.0, 20.0]
    }
    df = pd.DataFrame(data)
    
    # Let's mock SMA logic directly in dataframe to bypass min_periods NaN issues in tests easily
    df['SMA_2'] = [12.0, 12.0, 12.0, 12.0] # Constant SMA 2
    
    strategy = {
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left": {"type": "price", "name": "close"},
                    "operator": "crosses_above",
                    "right": {"type": "indicator", "name": "SMA", "period": 2}
                }
            ]
        }
    }
    
    signals = engine.evaluate(strategy, df)
    
    assert len(signals) == 1
    assert signals[0]['index'] == 2 # 20 > 12, previous was 10 < 12
