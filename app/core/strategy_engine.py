import pandas as pd
from typing import Dict, Any, List, Tuple
from app.core.models import StrategyDef
from app.core.indicators import Indicators
from app.core.logger import setup_logger

logger = setup_logger("app.core.strategy_engine")


class StrategyEngine:
    def __init__(self):
        pass

    def _resolve_value(self, df: pd.DataFrame, item: Dict[str, Any], index: int) -> float:
        """
        Resolve a rule value (left or right side) at a given bar index.

        period semantics for type='price':
            period=0 → current bar (index)
            period=1 → previous bar (index - 1)
            period=N → N bars ago (index - N)
        """
        type_ = item.get("type")

        if type_ == "constant":
            return float(item.get("value", 0.0))

        elif type_ == "price":
            # Support both 'field' and legacy 'name' keys
            col = (item.get("field") or item.get("name") or "close").lower()
            period = int(item.get("period", 0))
            target_index = index - period
            if target_index < 0 or target_index >= len(df):
                return 0.0
            if col not in df.columns:
                logger.warning(f"Column '{col}' not found in data. Available: {list(df.columns)}")
                return 0.0
            return float(df[col].iloc[target_index])

        elif type_ == "indicator":
            name = item.get("name", "")
            period = int(item.get("period", 14))
            col_name = f"{name}_{period}"
            if col_name not in df.columns:
                self._calculate_indicator(df, name, period)
            if col_name not in df.columns:
                return 0.0
            offset = int(item.get("offset", 0))
            target_index = index - offset
            if target_index < 0 or target_index >= len(df):
                return 0.0
            return float(df[col_name].iloc[target_index])

        return 0.0

    def _calculate_indicator(self, df: pd.DataFrame, name: str, period: int):
        col_name = f"{name}_{period}"
        try:
            if name == "SMA":
                df[col_name] = Indicators.calculate_sma(df["close"], period)
            elif name == "EMA":
                df[col_name] = Indicators.calculate_ema(df["close"], period)
            elif name == "RSI":
                df[col_name] = Indicators.calculate_rsi(df["close"], period)
            elif name == "ATR":
                df[col_name] = Indicators.calculate_atr(df["high"], df["low"], df["close"], period)
            else:
                logger.warning(f"Unknown indicator: {name}")
        except Exception as e:
            logger.error(f"Error calculating indicator {name}_{period}: {e}")

    def _max_lookback(self, rules: list) -> int:
        """
        Determine the minimum bar index at which evaluation can safely start.

        - price period=0 → needs index >= 0 (always ok from index 1+)
        - price period=1 → needs index >= 1
        - indicator period=14 → needs index >= 14 for warmup
        - crosses_above/below → additionally needs index >= 1 for the prior bar
        """
        max_period = 1  # always need at least index 1
        for rule in rules:
            op = rule.get("operator", "")
            if op in ("crosses_above", "crosses_below"):
                max_period = max(max_period, 1)  # need at least 1 prior bar
            for side in ["left", "right"]:
                item = rule.get(side, {})
                if item.get("type") == "price":
                    period = int(item.get("period", 0))
                    max_period = max(max_period, period)
                elif item.get("type") == "indicator":
                    period = int(item.get("period", 14))
                    # indicator needs `period` bars of history for warmup
                    max_period = max(max_period, period)
        return max_period

    def _evaluate_rule(self, df: pd.DataFrame, rule: Dict[str, Any], index: int) -> Tuple[bool, str]:
        try:
            left_val = self._resolve_value(df, rule["left"], index)
            right_val = self._resolve_value(df, rule["right"], index)
            op = rule["operator"]

            left_desc = f"{rule['left'].get('field') or rule['left'].get('name', '?')}[{rule['left'].get('period', 0)}]"
            right_desc = f"{rule['right'].get('field') or rule['right'].get('name', '?')}[{rule['right'].get('period', 0)}]"
            debug_str = f"{left_desc}({left_val:.5f}) {op} {right_desc}({right_val:.5f})"

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
                prev_left = self._resolve_value(df, rule["left"], index - 1)
                prev_right = self._resolve_value(df, rule["right"], index - 1)
                debug_str += f" [prev: {prev_left:.5f} <= {prev_right:.5f}]"
                return prev_left <= prev_right and left_val > right_val, debug_str
            elif op == "crosses_below":
                prev_left = self._resolve_value(df, rule["left"], index - 1)
                prev_right = self._resolve_value(df, rule["right"], index - 1)
                debug_str += f" [prev: {prev_left:.5f} >= {prev_right:.5f}]"
                return prev_left >= prev_right and left_val < right_val, debug_str

            return False, f"Unknown operator: {op}"

        except Exception as e:
            return False, f"Rule error: {e}"

    def evaluate(self, strategy: dict, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Evaluates candles chronologically and returns entry signals.
        
        period semantics:
            period=0 → current candle being evaluated
            period=1 → the candle before it
            period=N → N candles before the current one
        """
        signals = []
        conditions = strategy.get("conditions", {})
        op = conditions.get("operator", "AND").upper()
        rules = conditions.get("rules", [])

        if not rules:
            logger.warning("Strategy has no rules defined.")
            return signals

        min_index = self._max_lookback(rules)
        logger.info(f"Evaluating strategy '{strategy.get('name')}' on {len(df)} bars. Min lookback: {min_index}")

        for i in range(min_index, len(df)):
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
                ts_col = "time" if "time" in df.columns else "timestamp"
                ts = df.iloc[i].get(ts_col, i)
                signals.append({
                    "index": i,
                    "timestamp": ts,
                    "price": float(df.iloc[i]["close"]),
                    "open": float(df.iloc[i].get("open", 0)),
                    "high": float(df.iloc[i].get("high", 0)),
                    "low": float(df.iloc[i].get("low", 0)),
                    "direction": strategy.get("direction", "BUY"),
                    "debug": debug_info
                })

        return signals

    def run_backtest(self, strategy: dict, df: pd.DataFrame,
                     initial_balance: float = 10000.0,
                     lot_size: float = 0.01,
                     sl_pips: float = 0.0,
                     tp_pips: float = 0.0) -> Dict[str, Any]:
        """
        Full backtest with P&L simulation.
        Returns summary metrics and trade log.
        """
        signals = self.evaluate(strategy, df)
        direction = strategy.get("direction", "BUY")

        pip_value = 0.1  # for XAUUSD: 1 pip = $0.10 per 0.01 lot approx
        if "JPY" in strategy.get("symbol", ""):
            pip_value = 0.01

        balance = initial_balance
        trades = []
        equity_curve = [(0, balance)]

        # Simple simulation: enter on signal candle close, exit on next candle close
        # (or on SL/TP if defined)
        for sig in signals:
            idx = sig["index"]
            if idx + 1 >= len(df):
                continue  # No next candle to exit on

            entry_price = sig["price"]
            exit_candle = df.iloc[idx + 1]
            ts_col = "time" if "time" in df.columns else "timestamp"
            exit_time = exit_candle.get(ts_col, idx + 1)
            exit_price = float(exit_candle["close"])

            # SL/TP simulation on next candle
            if sl_pips > 0 or tp_pips > 0:
                if direction == "BUY":
                    sl_price = entry_price - sl_pips * 0.01 if sl_pips > 0 else None
                    tp_price = entry_price + tp_pips * 0.01 if tp_pips > 0 else None
                    candle_low = float(exit_candle.get("low", exit_price))
                    candle_high = float(exit_candle.get("high", exit_price))
                    if sl_price and candle_low <= sl_price:
                        exit_price = sl_price
                        reason = "SL"
                    elif tp_price and candle_high >= tp_price:
                        exit_price = tp_price
                        reason = "TP"
                    else:
                        reason = "Close"
                else:  # SELL
                    sl_price = entry_price + sl_pips * 0.01 if sl_pips > 0 else None
                    tp_price = entry_price - tp_pips * 0.01 if tp_pips > 0 else None
                    candle_high = float(exit_candle.get("high", exit_price))
                    candle_low = float(exit_candle.get("low", exit_price))
                    if sl_price and candle_high >= sl_price:
                        exit_price = sl_price
                        reason = "SL"
                    elif tp_price and candle_low <= tp_price:
                        exit_price = tp_price
                        reason = "TP"
                    else:
                        reason = "Close"
            else:
                reason = "Next Bar Close"

            # Calculate profit
            price_diff = (exit_price - entry_price) if direction == "BUY" else (entry_price - exit_price)
            # For metals: 1 unit diff = $1 per lot (simplified)
            profit = price_diff * lot_size * 100

            balance += profit
            trades.append({
                "signal_index": idx,
                "entry_time": str(sig["timestamp"]),
                "exit_time": str(exit_time),
                "direction": direction,
                "entry_price": round(entry_price, 5),
                "exit_price": round(exit_price, 5),
                "lots": lot_size,
                "profit": round(profit, 2),
                "balance": round(balance, 2),
                "reason": reason
            })
            equity_curve.append((idx + 1, round(balance, 2)))

        # Summary metrics
        net_profit = balance - initial_balance
        wins = [t for t in trades if t["profit"] > 0]
        losses = [t for t in trades if t["profit"] <= 0]
        gross_profit = sum(t["profit"] for t in wins)
        gross_loss = abs(sum(t["profit"] for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")
        win_rate = (len(wins) / len(trades) * 100) if trades else 0.0

        # Max drawdown
        peak = initial_balance
        max_dd = 0.0
        running_bal = initial_balance
        for t in trades:
            running_bal = t["balance"]
            if running_bal > peak:
                peak = running_bal
            dd = (peak - running_bal) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return {
            "summary": {
                "initial_balance": initial_balance,
                "final_balance": round(balance, 2),
                "net_profit": round(net_profit, 2),
                "total_trades": len(trades),
                "winning_trades": len(wins),
                "losing_trades": len(losses),
                "win_rate_pct": round(win_rate, 2),
                "gross_profit": round(gross_profit, 2),
                "gross_loss": round(gross_loss, 2),
                "profit_factor": round(profit_factor, 2) if profit_factor != float("inf") else "∞",
                "max_drawdown_pct": round(max_dd, 2),
                "avg_profit": round(gross_profit / len(wins), 2) if wins else 0,
                "avg_loss": round(gross_loss / len(losses), 2) if losses else 0,
                "largest_win": round(max((t["profit"] for t in wins), default=0), 2),
                "largest_loss": round(min((t["profit"] for t in trades), default=0), 2),
                "signals_total": len(signals),
            },
            "signals": signals,
            "trades": trades,
            "equity_curve": equity_curve
        }
