import logging
from config import get_config
from ..logging import engine_logger

config = get_config()

class CircuitBreaker:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self.max_daily_loss = config.MAX_DAILY_LOSS
        self.state = 'NORMAL'  # NORMAL, WARNING, TRIGGERED
        self.current_loss = 0.0
        self._initialized = True
        engine_logger.info(f"CircuitBreaker initialized. Max Daily Loss limit: ₹{self.max_daily_loss}")

    def check_pnl(self, realized_pnl: float, unrealized_pnl: float) -> str:
        # Updates the circuit breaker state based on the current aggregate P&L. Losses are represented as negative P&L values.
        
        total_pnl = realized_pnl + unrealized_pnl
        loss = -total_pnl if total_pnl < 0 else 0.0
        self.current_loss = loss
        
        if self.state == 'TRIGGERED':
            return self.state
            
        if loss >= self.max_daily_loss:
            self.state = 'TRIGGERED'
            engine_logger.critical(f"RISK TRIGGERED: Daily loss (₹{loss:.2f}) exceeded threshold (₹{self.max_daily_loss:.2f}). Trading locked!")
        elif loss >= (0.8 * self.max_daily_loss):
            self.state = 'WARNING'
            engine_logger.warning(f"RISK WARNING: Daily loss (₹{loss:.2f}) is approaching threshold (80%+ of ₹{self.max_daily_loss:.2f}).")
        else:
            self.state = 'NORMAL'
            
        return self.state

    def is_triggered(self) -> bool:
        # Returns True if the circuit breaker has breached the safety threshold (80% warning or 100% triggered
        return self.state in ('WARNING', 'TRIGGERED')

    def get_status(self) -> dict:
        # Returns a snapshot of the current circuit state
        return {
            'state': self.state,
            'current_loss': self.current_loss,
            'max_loss_limit': self.max_daily_loss,
            'remaining_margin': max(0.0, self.max_daily_loss - self.current_loss)
        }

    def reset_breaker(self):
        # Resets the circuit breaker state (typically executed on next day boot
        self.state = 'NORMAL'
        self.current_loss = 0.0
        engine_logger.info("CircuitBreaker reset successfully.")
