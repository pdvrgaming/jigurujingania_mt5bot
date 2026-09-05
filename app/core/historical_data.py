import pandas as pd
from pathlib import Path
from app.core.mt5_provider import MT5Provider
from app.core.config import config
from app.core.logger import setup_logger

logger = setup_logger("app.core.historical_data")

class HistoricalDataManager:
    def __init__(self, provider: MT5Provider):
        self.provider = provider
        self.data_dir = Path(config.get("data_directory", "data")) / "candles"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def export_candles(self, symbol: str, timeframe: str, count: int = 1000) -> str:
        """
        Retrieves candles from MT5 and exports them to a normalized CSV.
        """
        logger.info(f"Exporting {count} {timeframe} candles for {symbol}...")
        
        df = self.provider.get_candles(symbol, timeframe, count)
        if df.empty:
            logger.warning("No data retrieved.")
            return ""
            
        # Normalize format
        # Required format: timestamp, symbol, timeframe, open, high, low, close, tick_volume, spread, real_volume
        df['symbol'] = symbol
        df['timeframe'] = timeframe
        
        # Rename columns to match requirements
        rename_map = {
            'time': 'timestamp',
            'tick_volume': 'tick_volume',
            'spread': 'spread',
            'real_volume': 'real_volume',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close'
        }
        df.rename(columns=rename_map, inplace=True)
        
        columns_order = [
            'timestamp', 'symbol', 'timeframe', 'open', 'high', 'low', 'close', 
            'tick_volume', 'spread', 'real_volume'
        ]
        
        # Keep only required columns that exist
        available_cols = [c for c in columns_order if c in df.columns]
        df = df[available_cols]
        
        filename = f"{symbol}_{timeframe}.csv"
        filepath = self.data_dir / filename
        
        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(df)} candles to {filepath}")
        
        return str(filepath)
