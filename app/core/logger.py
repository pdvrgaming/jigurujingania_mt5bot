import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import config

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.DEBUG)
    
    log_dir = Path(config.get("log_directory", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    
    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=5*1024*1024, backupCount=3
    )
    file_handler.setLevel(logging.DEBUG)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
