"""
Create pre-defined strategies for MT5 Strategy Console.
Run from project root.
"""
import json
from pathlib import Path

strategies_dir = Path("data/strategies")
strategies_dir.mkdir(parents=True, exist_ok=True)

STRATEGIES = [

    # ── STRATEGY 1: Simple Close Above Previous (baseline test) ──────────────
    {
        "name": "CloseAbovePrevious",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "direction": "BUY",
        "description": "Buy when current candle close is above previous candle close. Simple momentum filter.",
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
    },

    # ── STRATEGY 2: Bullish Engulfing (price action) ────────────────────────
    {
        "name": "BullishEngulfing",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "BUY",
        "description": (
            "Price Action: Bullish engulfing pattern.\n"
            "Rule 1: Current candle is bullish (close > open)\n"
            "Rule 2: Previous candle was bearish (prev close < prev open)\n"
            "Rule 3: Current close > previous open (engulfs prev body)"
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "open",  "period": 0}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 1},
                    "operator": "<",
                    "right": {"type": "price", "field": "open",  "period": 1}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "open",  "period": 1}
                }
            ]
        }
    },

    # ── STRATEGY 3: Three Bullish Candles (3-candle confirmation) ──────────
    # This matches your hand-drawn sketch: "1m entry after 3 candles"
    {
        "name": "ThreeConsecutiveBullish",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "direction": "BUY",
        "description": (
            "SMC / Price Action: Enter after 3 consecutive bullish M1 candles confirm direction.\n"
            "Matches the hand-drawn strategy: 'entry after 3 candles'.\n"
            "Rule 1: close[0] > close[1] (current bullish)\n"
            "Rule 2: close[1] > close[2] (prev bullish)\n"
            "Rule 3: close[2] > close[3] (2 bars ago bullish)\n"
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "close", "period": 1}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 1},
                    "operator": ">",
                    "right": {"type": "price", "field": "close", "period": 2}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 2},
                    "operator": ">",
                    "right": {"type": "price", "field": "close", "period": 3}
                }
            ]
        }
    },

    # ── STRATEGY 4: Bearish Reversal (Three Consecutive Bearish Candles) ────
    {
        "name": "ThreeConsecutiveBearish",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M1",
        "direction": "SELL",
        "description": "Three consecutive bearish M1 candles. Sell-side version of the 3-candle confirmation.",
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": "<",
                    "right": {"type": "price", "field": "close", "period": 1}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 1},
                    "operator": "<",
                    "right": {"type": "price", "field": "close", "period": 2}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 2},
                    "operator": "<",
                    "right": {"type": "price", "field": "close", "period": 3}
                }
            ]
        }
    },

    # ── STRATEGY 5: Inside Bar Breakout (BUY side) ──────────────────────────
    {
        "name": "InsideBarBreakoutBuy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "BUY",
        "description": (
            "Price Action: An inside bar is followed by a bullish breakout.\n"
            "Bar 2 ago (period=2): Mother bar (large range)\n"
            "Bar 1 ago (period=1): Inside bar (high < mother high, low > mother low)\n"
            "Current bar (period=0): Breaks above mother bar's high\n"
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "high",  "period": 1},
                    "operator": "<",
                    "right": {"type": "price", "field": "high",  "period": 2}
                },
                {
                    "left":  {"type": "price", "field": "low",   "period": 1},
                    "operator": ">",
                    "right": {"type": "price", "field": "low",   "period": 2}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "high",  "period": 2}
                }
            ]
        }
    },

    # ── STRATEGY 6: Strong Bullish Momentum (Open near Low, Close near High) ─
    {
        "name": "StrongBullishMomentum",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M5",
        "direction": "BUY",
        "description": (
            "Price Action: Strong bullish candle where open is near low and close is near high.\n"
            "Rule 1: close > open (bullish)\n"
            "Rule 2: current close higher than 3-bar previous close (uptrend confirmation)\n"
            "Represents a high-momentum bar with minimal wick on top."
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "open",  "period": 0}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "close", "period": 3}
                }
            ]
        }
    },

    # ── STRATEGY 7: Higher High Higher Low (Uptrend Structure) ──────────────
    {
        "name": "HigherHighHigherLow",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "direction": "BUY",
        "description": (
            "SMC Market Structure: BUY when price forms Higher High and Higher Low.\n"
            "Rule 1: current high > previous high (HH)\n"
            "Rule 2: current low  > previous low  (HL)\n"
            "Rule 3: current close > current open (bullish close confirms)"
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "high",  "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "high",  "period": 1}
                },
                {
                    "left":  {"type": "price", "field": "low",   "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "low",   "period": 1}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "open",  "period": 0}
                }
            ]
        }
    },

    # ── STRATEGY 8: Lower Low Lower High (Downtrend / SELL) ─────────────────
    {
        "name": "LowerLowLowerHigh",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "direction": "SELL",
        "description": (
            "SMC Market Structure: SELL when price forms Lower Low and Lower High.\n"
            "Rule 1: current high < previous high (LH)\n"
            "Rule 2: current low  < previous low  (LL)\n"
            "Rule 3: current close < current open (bearish close confirms)"
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "high",  "period": 0},
                    "operator": "<",
                    "right": {"type": "price", "field": "high",  "period": 1}
                },
                {
                    "left":  {"type": "price", "field": "low",   "period": 0},
                    "operator": "<",
                    "right": {"type": "price", "field": "low",   "period": 1}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": "<",
                    "right": {"type": "price", "field": "open",  "period": 0}
                }
            ]
        }
    },

    # ── STRATEGY 9: Break of Structure BUY (SMC BOS) ────────────────────────
    {
        "name": "BreakOfStructureBuy",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "BUY",
        "description": (
            "SMC: Break of Structure (BOS) to the upside.\n"
            "Price breaks above a recent swing high (2 bars ago high) and closes above it.\n"
            "Also current bar must be bullish.\n"
            "This signals potential SMC bullish continuation."
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "high",  "period": 2}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": ">",
                    "right": {"type": "price", "field": "open",  "period": 0}
                }
            ]
        }
    },

    # ── STRATEGY 10: Break of Structure SELL (SMC BOS) ──────────────────────
    {
        "name": "BreakOfStructureSell",
        "version": 1,
        "symbol": "XAUUSD",
        "timeframe": "M15",
        "direction": "SELL",
        "description": (
            "SMC: Break of Structure (BOS) to the downside.\n"
            "Price breaks below a recent swing low (2 bars ago low) and closes below it.\n"
            "Also current bar must be bearish.\n"
            "This signals potential SMC bearish continuation."
        ),
        "conditions": {
            "operator": "AND",
            "rules": [
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": "<",
                    "right": {"type": "price", "field": "low",   "period": 2}
                },
                {
                    "left":  {"type": "price", "field": "close", "period": 0},
                    "operator": "<",
                    "right": {"type": "price", "field": "open",  "period": 0}
                }
            ]
        }
    },
]

# Write to source strategies dir
for strat in STRATEGIES:
    fname = f"{strat['name']}_v{strat['version']}.json"
    fpath = strategies_dir / fname
    with open(fpath, "w") as f:
        json.dump(strat, f, indent=2)
    print(f"Written: {fpath}")

# Also copy to release folder
release_strat_dirs = [
    Path("release/MT5_Strategy_Console/data/strategies"),
    Path("release/MT5_Strategy_Console/MT5_Strategy_Console/data/strategies"),
]
for rel_dir in release_strat_dirs:
    rel_dir.mkdir(parents=True, exist_ok=True)
    for strat in STRATEGIES:
        fname = f"{strat['name']}_v{strat['version']}.json"
        with open(rel_dir / fname, "w") as f:
            json.dump(strat, f, indent=2)
    print(f"Copied to: {rel_dir}")

print(f"\nDone. Created {len(STRATEGIES)} strategies.")
