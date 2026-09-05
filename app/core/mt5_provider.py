import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timezone, timedelta
from app.core.logger import setup_logger

logger = setup_logger("app.core.mt5_provider")

class MT5Provider:
    def __init__(self):
        self.connected = False

    def connect(self) -> bool:
        if not mt5.initialize():
            logger.error(f"MT5 initialize() failed, error code = {mt5.last_error()}")
            self.connected = False
            return False
        self.connected = True
        logger.info("MT5 connection established.")
        return True

    def disconnect(self):
        mt5.shutdown()
        self.connected = False
        logger.info("MT5 disconnected.")

    def is_connected(self) -> bool:
        return self.connected

    def get_symbols(self) -> list:
        if not self.connected:
            return []
        symbols = mt5.symbols_get()
        if symbols is None:
            logger.error(f"Failed to get symbols, error code = {mt5.last_error()}")
            return []
        return [s.name for s in symbols]

    def get_candles(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        if not self.connected:
            return pd.DataFrame()
            
        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_M15)
        
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to get candles for {symbol}, error code = {mt5.last_error()}")
            return pd.DataFrame()
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        return df

    def get_historical_rates(self, symbol: str, timeframe: str, start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
        if not self.connected:
            return pd.DataFrame()

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        tf = tf_map.get(timeframe, mt5.TIMEFRAME_M15)

        # MT5 expects naive datetime objects or aware datetime in UTC, but to be safe, 
        # it's usually best to use naive datetime objects that represent UTC time in mt5 python api.
        # But copy_rates_range is flexible enough if you pass aware datetimes or use explicit timestamps.
        # However, passing int timestamp is safest.
        rates = mt5.copy_rates_range(symbol, tf, start_dt, end_dt)
        if rates is None or len(rates) == 0:
            logger.error(f"Failed to get historical rates for {symbol}, error code = {mt5.last_error()}")
            return pd.DataFrame()

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        return df

    def get_recent_rates(self, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(days=days)
        return self.get_historical_rates(symbol, timeframe, start_dt, end_dt)


    def get_current_price(self, symbol: str) -> dict:
        if not self.connected:
            return {}
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "last": tick.last,
            "time": tick.time
        }

    def get_positions(self, symbol: str = None) -> list:
        if not self.connected:
            return []
        if symbol:
            positions = mt5.positions_get(symbol=symbol)
        else:
            positions = mt5.positions_get()
            
        if positions is None:
            return []
            
        res = []
        for p in positions:
            res.append({
                "ticket": p.ticket,
                "time": p.time,
                "type": p.type,
                "magic": p.magic,
                "volume": p.volume,
                "price_open": p.price_open,
                "sl": p.sl,
                "tp": p.tp,
                "price_current": p.price_current,
                "swap": p.swap,
                "profit": p.profit,
                "symbol": p.symbol,
                "comment": p.comment,
            })
        return res

    def get_history_orders(self, date_from, date_to) -> list:
        if not self.connected:
            return []
        orders = mt5.history_orders_get(date_from, date_to)
        if orders is None:
            return []
        return [o._asdict() for o in orders]
        
    def get_history_deals(self, date_from, date_to) -> list:
        if not self.connected:
            return []
        deals = mt5.history_deals_get(date_from, date_to)
        if deals is None:
            return []
        return [d._asdict() for d in deals]

provider = MT5Provider()
