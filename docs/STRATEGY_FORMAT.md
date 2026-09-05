# Strategy Format

Strategies are stored in JSON.

```json
{
    "name": "EMA RSI Gold",
    "version": 1,
    "symbol": "XAUUSD",
    "timeframe": "M15",
    "conditions": {
        "operator": "AND",
        "rules": [
            {
                "left": {
                    "type": "indicator",
                    "name": "EMA",
                    "period": 20
                },
                "operator": "crosses_above",
                "right": {
                    "type": "indicator",
                    "name": "EMA",
                    "period": 50
                }
            }
        ]
    }
}
```
