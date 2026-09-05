import pytest
import pandas as pd
from app.core.strategy_engine import StrategyEngine


def _make_df(closes, opens=None, highs=None, lows=None):
    n = len(closes)
    return pd.DataFrame({
        "time": list(range(n)),
        "close": closes,
        "open": opens or closes,
        "high": highs or [c + 1 for c in closes],
        "low": lows or [c - 1 for c in closes],
    })


def test_price_field_key():
    """Verify that 'field' key works (the format used in real strategy JSON files)."""
    engine = StrategyEngine()
    df = _make_df([100.0, 105.0, 95.0, 110.0])

    strategy = {
        "name": "Test",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "constant", "value": 100.0}
                }
            ]
        }
    }

    signals = engine.evaluate(strategy, df)
    # close[105] at index 1, close[110] at index 3 → 2 signals
    assert len(signals) == 2
    assert signals[0]["index"] == 1
    assert signals[1]["index"] == 3


def test_price_name_key_legacy():
    """Legacy 'name' key must still work for backward compat."""
    engine = StrategyEngine()
    df = _make_df([100.0, 105.0, 95.0])

    strategy = {
        "name": "LegacyTest",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "name": "close"},
                    "operator": ">",
                    "right": {"type": "constant", "value": 100.0}
                }
            ]
        }
    }

    signals = engine.evaluate(strategy, df)
    assert len(signals) == 1  # only index 1 (105 > 100)


def test_period_offset():
    """Period=1 should look back one bar."""
    engine = StrategyEngine()
    # close[0]=100, [1]=110, [2]=90, [3]=120
    df = _make_df([100.0, 110.0, 90.0, 120.0])

    strategy = {
        "name": "CloseAbovePrev",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "close", "period": 1}
                }
            ]
        }
    }

    signals = engine.evaluate(strategy, df)
    # Index 1: close[1]=110 > close[0]=100 ✓
    # Index 2: close[2]=90  > close[1]=110 ✗
    # Index 3: close[3]=120 > close[2]=90  ✓
    assert len(signals) == 2
    assert signals[0]["index"] == 1
    assert signals[1]["index"] == 3


def test_and_multiple_rules():
    """AND operator requires all rules true."""
    engine = StrategyEngine()
    df = _make_df([100.0, 110.0, 105.0], opens=[95.0, 100.0, 110.0])

    strategy = {
        "name": "BullishCandle",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "open", "period": 0}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "close", "period": 1}
                }
            ]
        }
    }

    signals = engine.evaluate(strategy, df)
    # Index 1: close(110)>open(100) ✓ AND close(110)>prev_close(100) ✓ → signal
    # Index 2: close(105)>open(110) ✗ → no signal
    assert len(signals) == 1
    assert signals[0]["index"] == 1


def test_or_operator():
    """OR operator fires if any rule is true."""
    engine = StrategyEngine()
    df = _make_df([100.0, 105.0, 90.0])

    strategy = {
        "name": "OR Test",
        "direction": "BUY",
        "conditions": {
            "operator": "OR",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "constant", "value": 104.0}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": "<",
                    "right": {"type": "constant", "value": 92.0}
                }
            ]
        }
    }

    signals = engine.evaluate(strategy, df)
    # Index 1: close(105) > 104 ✓
    # Index 2: close(90)  < 92 ✓
    assert len(signals) == 2


def test_crosses_above():
    """crosses_above fires exactly when crossing from below to above."""
    engine = StrategyEngine()
    df = _make_df([10.0, 10.0, 20.0, 20.0])
    df["SMA_2"] = [12.0, 12.0, 12.0, 12.0]

    strategy = {
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": "crosses_above",
                    "right": {"type": "indicator", "name": "SMA", "period": 2}
                }
            ]
        }
    }

    signals = engine.evaluate(strategy, df)
    assert len(signals) == 1
    assert signals[0]["index"] == 2  # 10→20 crossing above 12


def test_run_backtest_metrics():
    """Full backtest should return proper P&L."""
    engine = StrategyEngine()
    # Signal at index 1 (close 110), exit at index 2 (close 115)
    df = _make_df([100.0, 110.0, 115.0, 108.0])

    strategy = {
        "name": "BT Test",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "close", "period": 1}
                }
            ]
        }
    }

    result = engine.run_backtest(strategy, df, initial_balance=10000, lot_size=0.01)
    summary = result["summary"]

    assert summary["total_trades"] >= 1
    assert "net_profit" in summary
    assert "win_rate_pct" in summary
    assert "max_drawdown_pct" in summary
    assert len(result["trades"]) == summary["total_trades"]


def test_empty_rules():
    """Strategy with no rules should return no signals."""
    engine = StrategyEngine()
    df = _make_df([100.0, 110.0, 90.0])
    strategy = {"name": "Empty", "conditions": {"operator": "AND", "rules": []}}
    signals = engine.evaluate(strategy, df)
    assert signals == []
