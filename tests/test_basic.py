import pytest
from app.core.config import config
from app.core.logger import setup_logger

def test_config_initialization():
    assert config is not None
    assert config.get("mt5_default_symbol") == "XAUUSD"

def test_logger_creation():
    logger = setup_logger("test_logger")
    assert logger is not None
    assert logger.name == "test_logger"
