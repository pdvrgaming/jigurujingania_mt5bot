import json
from pathlib import Path

strategies = [
    {
        "name": "SMC_Choch_Buy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "price", "name": "close"}, "operator": ">", "right": {"type": "price", "name": "high"}}
            ]
        }
    },
    {
        "name": "Price_Action_Pinbar_Buy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "price", "name": "close"}, "operator": ">", "right": {"type": "price", "name": "open"}},
                {"left": {"type": "indicator", "name": "RSI", "period": 14}, "operator": "<", "right": {"type": "constant", "value": 30.0}}
            ]
        }
    },
    {
        "name": "Trend_Continuation_Buy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "price", "name": "close"}, "operator": ">", "right": {"type": "indicator", "name": "EMA", "period": 50}},
                {"left": {"type": "indicator", "name": "EMA", "period": 20}, "operator": ">", "right": {"type": "indicator", "name": "EMA", "period": 50}}
            ]
        }
    },
    {
        "name": "SMC_Liquidity_Sweep_Sell",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "SELL",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "price", "name": "high"}, "operator": ">", "right": {"type": "indicator", "name": "ATR", "period": 14}},
                {"left": {"type": "price", "name": "close"}, "operator": "<", "right": {"type": "price", "name": "open"}}
            ]
        }
    },
    {
        "name": "RSI_Overbought_Sell",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "SELL",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "indicator", "name": "RSI", "period": 14}, "operator": ">", "right": {"type": "constant", "value": 70.0}},
                {"left": {"type": "price", "name": "close"}, "operator": "<", "right": {"type": "price", "name": "open"}}
            ]
        }
    },
    {
        "name": "EMA_Cross_Buy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "indicator", "name": "EMA", "period": 9}, "operator": ">", "right": {"type": "indicator", "name": "EMA", "period": 21}}
            ]
        }
    },
    {
        "name": "EMA_Cross_Sell",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "SELL",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "indicator", "name": "EMA", "period": 9}, "operator": "<", "right": {"type": "indicator", "name": "EMA", "period": 21}}
            ]
        }
    },
    {
        "name": "Breakout_High_Buy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "price", "name": "close"}, "operator": ">", "right": {"type": "price", "name": "high"}}
            ]
        }
    },
    {
        "name": "Breakout_Low_Sell",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "direction": "SELL",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "price", "name": "close"}, "operator": "<", "right": {"type": "price", "name": "low"}}
            ]
        }
    },
    {
        "name": "Mean_Reversion_Buy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "direction": "BUY",
        "conditions": {
            "operator": "AND",
            "rules": [
                {"left": {"type": "price", "name": "close"}, "operator": "<", "right": {"type": "indicator", "name": "SMA", "period": 200}},
                {"left": {"type": "indicator", "name": "RSI", "period": 14}, "operator": "<", "right": {"type": "constant", "value": 25.0}}
            ]
        }
    }
]

def main():
    strat_dir = Path(r"d:\webapps\jugurujinganiya bot\data\strategies")
    strat_dir.mkdir(parents=True, exist_ok=True)
    
    for strat in strategies:
        filepath = strat_dir / f"{strat['name']}_v{strat['version']}.json"
        with open(filepath, 'w') as f:
            json.dump(strat, f, indent=4)
        print(f"Created {filepath.name}")

if __name__ == "__main__":
    main()
