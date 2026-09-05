import pandas as pd
import time
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from app.core.mt5_provider import MT5Provider
from app.core.config import config
from app.core.logger import setup_logger

logger = setup_logger("app.core.bot_observer")

class BotObserver:
    def __init__(self, provider: MT5Provider):
        self.provider = provider
        self.running = False
        self.symbol = "XAUUSD"
        self.interval = config.get("polling_interval_ms", 5000) / 1000.0
        
        obs_dir = Path(config.get("data_directory", "data")) / "observations"
        obs_dir.mkdir(parents=True, exist_ok=True)
        self.csv_path = obs_dir / "xauusd_trial_activity.csv"
        
        self.known_positions = {}
        self.known_deals = set()
        self.known_orders = set()
        self.target_magic = None
        
        self._init_csv()

    def _init_csv(self):
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp_utc", "timestamp_ist", "event_type", "symbol", "ticket", "position_id", 
                    "order_id", "deal_id", "direction", "volume", "price", "sl", "tp", 
                    "current_price", "profit", "swap", "commission", "magic", "comment", 
                    "reason", "source"
                ])

    def _write_event(self, event_type: str, data: dict):
        timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        timestamp_ist = datetime.now(ist_tz).strftime("%Y-%m-%d %H:%M:%S")
        row = [
            timestamp_utc,
            timestamp_ist,
            event_type,
            data.get("symbol", self.symbol),
            data.get("ticket", ""),
            data.get("position_id", ""),
            data.get("order_id", ""),
            data.get("deal_id", ""),
            data.get("direction", ""),
            data.get("volume", ""),
            data.get("price", ""),
            data.get("sl", ""),
            data.get("tp", ""),
            data.get("current_price", ""),
            data.get("profit", ""),
            data.get("swap", ""),
            data.get("commission", ""),
            data.get("magic", ""),
            data.get("comment", ""),
            data.get("reason", ""),
            "OBSERVER"
        ]
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(row)
        logger.info(f"OBSERVED: {event_type} - {data}")

    def establish_baseline(self):
        logger.info("Establishing baseline for Bot Observer...")
        if not self.provider.is_connected():
            return
            
        positions = self.provider.get_positions(self.symbol)
        for p in positions:
            if self.target_magic is None or p.get("magic") == self.target_magic:
                self.known_positions[p["ticket"]] = p
            
        # Get history from last 24h
        now = datetime.now()
        yesterday = now - pd.Timedelta(days=1)
        
        deals = self.provider.get_history_deals(yesterday, now)
        for d in deals:
            if d.get("symbol") == self.symbol:
                if self.target_magic is None or d.get("magic") == self.target_magic:
                    self.known_deals.add(d["ticket"])
                
        orders = self.provider.get_history_orders(yesterday, now)
        for o in orders:
            if o.get("symbol") == self.symbol:
                if self.target_magic is None or o.get("magic") == self.target_magic:
                    self.known_orders.add(o["ticket"])

    def poll(self):
        if not self.provider.is_connected():
            return
            
        # 1. Price snapshot
        tick = self.provider.get_current_price(self.symbol)
        current_price = tick.get("last", tick.get("bid", "")) if tick else ""
        
        self._write_event("PRICE_SNAPSHOT", {"current_price": current_price})
        
        # 2. Open positions
        current_positions = self.provider.get_positions(self.symbol)
        current_tickets = set()
        
        for p in current_positions:
            if self.target_magic is not None and p.get("magic") != self.target_magic:
                continue
                
            ticket = p["ticket"]
            current_tickets.add(ticket)
            
            p_data = {
                "ticket": ticket,
                "position_id": p["ticket"],
                "direction": "BUY" if p["type"] == 0 else "SELL",
                "volume": p["volume"],
                "price": p["price_open"],
                "sl": p["sl"],
                "tp": p["tp"],
                "current_price": p["price_current"],
                "profit": p["profit"],
                "swap": p["swap"],
                "magic": p["magic"],
                "comment": p["comment"]
            }
            
            if ticket not in self.known_positions:
                self._write_event("POSITION_OPENED", p_data)
                self.known_positions[ticket] = p
            else:
                # Check for updates (SL/TP)
                old_p = self.known_positions[ticket]
                if old_p["sl"] != p["sl"] or old_p["tp"] != p["tp"] or old_p["volume"] != p["volume"]:
                    self._write_event("POSITION_UPDATED", p_data)
                    self.known_positions[ticket] = p
                    
        # Check closed positions
        for ticket in list(self.known_positions.keys()):
            if ticket not in current_tickets:
                self._write_event("POSITION_CLOSED", {"ticket": ticket, "position_id": ticket})
                del self.known_positions[ticket]
                
        # 3. Deals
        now = datetime.now()
        yesterday = now - pd.Timedelta(days=1)
        deals = self.provider.get_history_deals(yesterday, now)
        for d in deals:
            if d.get("symbol") == self.symbol and d["ticket"] not in self.known_deals:
                if self.target_magic is not None and d.get("magic") != self.target_magic:
                    continue
                self.known_deals.add(d["ticket"])
                self._write_event("DEAL_EXECUTED", {
                    "deal_id": d["ticket"],
                    "order_id": d.get("order"),
                    "position_id": d.get("position_id"),
                    "price": d.get("price"),
                    "volume": d.get("volume"),
                    "commission": d.get("commission"),
                    "swap": d.get("swap"),
                    "profit": d.get("profit"),
                    "magic": d.get("magic"),
                    "comment": d.get("comment")
                })
