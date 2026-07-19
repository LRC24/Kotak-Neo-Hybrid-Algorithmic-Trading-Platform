import os
import logging
from .log_formatter import get_console_formatter, get_file_formatter

# Determine workspace logging directory
WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(WORKSPACE_DIR, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Formatters
console_formatter = get_console_formatter()
file_formatter = get_file_formatter()

def _create_isolated_logger(name: str, log_filename: str, level=logging.INFO) -> logging.Logger:
    # Helper to instantiate a logger with custom file and console stream handlers
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False  # Keep logs private to this logger
    
    # Remove existing handlers (protects against duplicate entries on re-imports)
    if logger.handlers:
        for h in list(logger.handlers):
            logger.removeHandler(h)
            
    # File Handler
    log_filepath = os.path.join(LOG_DIR, log_filename)
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

# Expose pre-configured logs for the backend layers
engine_logger = _create_isolated_logger("app.engine", "engine.log")
api_logger = _create_isolated_logger("app.kotak_api", "kotak_api.log")
ws_logger = _create_isolated_logger("app.websocket", "websocket.log")
db_logger = _create_isolated_logger("app.db_operations", "db_operations.log")

def get_strategy_logger(strategy_name: str, run_id: str) -> logging.Logger:
    # Creates an isolated logging instance for a specific strategy run session.
    
    logger_name = f"strategy.{strategy_name}.{run_id}"
    strategy_logger = logging.getLogger(logger_name)
    
    if strategy_logger.handlers:
        return strategy_logger
        
    strategy_logger.setLevel(logging.INFO)
    strategy_logger.propagate = False
    
    # Set up dedicated strategy file
    strategy_filename = f"strategy_{strategy_name}_{run_id}.log"
    strategy_filepath = os.path.join(LOG_DIR, strategy_filename)
    
    file_handler = logging.FileHandler(strategy_filepath, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    strategy_logger.addHandler(file_handler)
    
    # Mirror output to colorized console for dynamic session debugging
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    strategy_logger.addHandler(console_handler)
    
    strategy_logger.info(f"Dynamic strategy logger initialized: {strategy_filepath}")
    return strategy_logger
