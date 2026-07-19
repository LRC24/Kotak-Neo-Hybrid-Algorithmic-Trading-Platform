import logging
from ..services.pnl_service import PnLService
from ..services.algo_service import AlgoService
from ..logging import engine_logger

# In-memory global price cache updated by WebSocket ticker
LTP_CACHE = {}

def run_pnl_updater(session_id: str):
    # Periodic task running during market hours to calculate position valuation and monitor circuit breaker limits.

    pnl_service = PnLService()
    algo_service = AlgoService()
    
    # Update and evaluate against limits
    pnl_data = pnl_service.update_and_evaluate_pnl(session_id, LTP_CACHE)
    state = pnl_data.get('circuit_state', 'NORMAL')
    
    if state == 'TRIGGERED':
        engine_logger.critical("Circuit Breaker has TRIGGERED! Shutting down active strategy threads.")
        # Trigger emergency flattening of all positions and halt threads
        algo_service.kill_all_runs()
