import pandas as pd
from typing import Dict, Any, List
from app.core.models import StrategyDef
from app.core.indicators import Indicators
from app.core.logger import setup_logger

logger = setup_logger("app.core.strategy_engine")

class StrategyEngine:
    def __init__(self):
        pass

    def _resolve_value(self, df: pd.DataFrame, item: Dict[str, Any], index: int) -> float:
        type_ = item.get("type")
        if type_ == "constant":
            return item.get("value", 0.0)
        elif type_ == "price":
            col = item.get("name", "close").lower()
            return df[col].iloc[index]
        elif type_ == "indicator":
            name = item.get("name")
            period = item.get("period")
            col_name = f"{name}_{period}"
            if col_name not in df.columns:
                self._calculate_indicator(df, name, period)
            return df[col_name].iloc[index]
        return 0.0

    def _calculate_indicator(self, df: pd.DataFrame, name: str, period: int):
        col_name = f"{name}_{period}"
        if name == "SMA":
            df[col_name] = Indicators.calculate_sma(df["close"], period)
        elif name == "EMA":
            df[col_name] = Indicators.calculate_ema(df["close"], period)
        elif name == "RSI":
            df[col_name] = Indicators.calculate_rsi(df["close"], period)
        elif name == "ATR":
            df[col_name] = Indicators.calculate_atr(df["high"], df["low"], df["close"], period)

    def _evaluate_rule(self, df: pd.DataFrame, rule: Dict[str, Any], index: int) -> tuple[bool, str]:
        if index < 1:
            return False, "Not enough data"
            
        left_val = self._resolve_value(df, rule["left"], index)
        right_val = self._resolve_value(df, rule["right"], index)
        op = rule["operator"]
        
        debug_str = f"{rule['left']} ({left_val:.4f}) {op} {rule['right']} ({right_val:.4f})"
        
        if op == ">":
            return left_val > right_val, debug_str
        elif op == "<":
            return left_val < right_val, debug_str
        elif op == "==" or op == "=":
            return left_val == right_val, debug_str
        elif op == ">=":
            return left_val >= right_val, debug_str
        elif op == "<=":
            return left_val <= right_val, debug_str
        elif op == "crosses_above":
            prev_left_val = self._resolve_value(df, rule["left"], index - 1)
            prev_right_val = self._resolve_value(df, rule["right"], index - 1)
            debug_str += f" [Prev: {prev_left_val:.4f} <= {prev_right_val:.4f}]"
            return prev_left_val <= prev_right_val and left_val > right_val, debug_str
        elif op == "crosses_below":
            prev_left_val = self._resolve_value(df, rule["left"], index - 1)
            prev_right_val = self._resolve_value(df, rule["right"], index - 1)
            debug_str += f" [Prev: {prev_left_val:.4f} >= {prev_right_val:.4f}]"
            return prev_left_val >= prev_right_val and left_val < right_val, debug_str
            
        return False, f"Unknown operator {op}"

    def evaluate(self, strategy: dict, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Evaluates closed candles. Output signals with debug details.
        Strategy format matches Phase 4 specification.
        """
        signals = []
        conditions = strategy.get("conditions", {})
        op = conditions.get("operator", "AND")
        rules = conditions.get("rules", [])

        # We evaluate closed candles, so up to len(df) - 1 (since the last might be open)
        # We assume the user passed only closed candles or we skip the last one if it's live data
        # For historical/backtest, all are closed. Let's evaluate all provided rows.
        for i in range(1, len(df)):
            rule_results = []
            debug_info = []
            for rule in rules:
                res, debug_str = self._evaluate_rule(df, rule, i)
                rule_results.append(res)
                debug_info.append(debug_str)
                
            if op == "AND":
                signal = all(rule_results) if rule_results else False
            elif op == "OR":
                signal = any(rule_results) if rule_results else False
            else:
                signal = False
                
            if signal:
                signals.append({
                    "index": i,
                    "timestamp": df.iloc[i]["time"] if "time" in df.columns else df.iloc[i].get("timestamp"),
                    "price": df.iloc[i]["close"],
                    "direction": strategy.get("direction", "BUY"),
                    "debug": debug_info
                })
        
        return signals
