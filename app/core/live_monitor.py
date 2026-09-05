import pandas as pd
from typing import Dict, Any, List, Optional
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer
import csv
from datetime import datetime, timezone

from app.core.strategy_engine import StrategyEngine
from app.core.mt5_provider import MT5Provider
from app.core.config import config
from app.core.logger import setup_logger

logger = setup_logger("app.core.live_monitor")

class LiveMonitor(QObject):
    signal_generated = Signal(dict)
    connection_changed = Signal(bool)
    
    def __init__(self, provider: MT5Provider):
        super().__init__()
        self.provider = provider
        self.engine = StrategyEngine()
        
        self.active_strategy = None
        self.running = False
        self.last_processed_time = None
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.poll)
        
        journal_dir = Path(config.get("data_directory", "data")) / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = journal_dir / "signals.csv"
        self._init_journal()

    def _init_journal(self):
        if not self.journal_path.exists():
            with open(self.journal_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "signal_id", "strategy_id", "strategy_version", "symbol", 
                    "timeframe", "timestamp", "direction", "price", "condition_results"
                ])

    def start(self, strategy: dict):
        self.active_strategy = strategy
        self.last_processed_time = None
        self.running = True
        interval = config.get("polling_interval_ms", 5000)
        self.timer.start(interval)
        logger.info(f"Started monitoring with strategy: {strategy.get('name')}")

    def stop(self):
        self.running = False
        self.timer.stop()
        self.active_strategy = None
        logger.info("Stopped monitoring.")

    def poll(self):
        if not self.running or not self.active_strategy:
            return
            
        was_connected = self.provider.is_connected()
        if not was_connected:
            self.provider.connect()
            self.connection_changed.emit(self.provider.is_connected())
            if not self.provider.is_connected():
                return
        
        symbol = self.active_strategy.get("symbol", "XAUUSD")
        tf = self.active_strategy.get("timeframe", "M15")
        
        # Get enough candles to evaluate logic (e.g. 200 for EMA200)
        df = self.provider.get_candles(symbol, tf, 200)
        if df.empty:
            return
            
        # StrategyEngine evaluate evaluates up to len(df)-1 (closed candles). 
        # But wait, in live monitoring, we only care about newly closed candles.
        # Let's get signals and filter by those newer than last_processed_time.
        signals = self.engine.evaluate(self.active_strategy, df)
        
        for s in signals:
            sig_time = s["timestamp"]
            if self.last_processed_time is None or sig_time > self.last_processed_time:
                # new signal!
                self._record_signal(s)
                self.signal_generated.emit({
                    "strategy": self.active_strategy,
                    "signal": s
                })
                self.last_processed_time = sig_time
                
        # If no signals, still update last processed time to the last closed candle time
        if len(df) > 1:
            last_closed_time = df.iloc[-2]["time"]
            if self.last_processed_time is None or last_closed_time > self.last_processed_time:
                self.last_processed_time = last_closed_time

    def _record_signal(self, sig: dict):
        import uuid
        sig_id = str(uuid.uuid4())
        strat_id = self.active_strategy.get("name", "Unknown")
        strat_ver = self.active_strategy.get("version", 1)
        sym = self.active_strategy.get("symbol", "")
        tf = self.active_strategy.get("timeframe", "")
        ts = sig["timestamp"]
        direction = sig["direction"]
        price = sig["price"]
        cond = " | ".join(sig["debug"])
        
        with open(self.journal_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                sig_id, strat_id, strat_ver, sym, tf, ts, direction, price, cond
            ])
