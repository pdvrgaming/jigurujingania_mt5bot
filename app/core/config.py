import json
import os
from pathlib import Path

class Config:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.settings = {
            "mt5_default_symbol": "XAUUSD",
            "mt5_default_timeframe": "M15",
            "polling_interval_ms": 5000,
            "data_directory": "data",
            "log_directory": "logs"
        }
        self.load()

    def load(self):
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                try:
                    loaded = json.load(f)
                    self.settings.update(loaded)
                except json.JSONDecodeError:
                    pass
        else:
            self.save()

    def save(self):
        with open(self.config_path, "w") as f:
            json.dump(self.settings, f, indent=4)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save()

config = Config()
