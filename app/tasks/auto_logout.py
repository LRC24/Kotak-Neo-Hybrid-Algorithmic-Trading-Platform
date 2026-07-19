import logging
from ..services.algo_service import AlgoService
from ..kotak.client_manager import ClientManager
from ..logging import engine_logger

def run_auto_logout():
    # Scheduled task running at 15:30 IST daily to flatten positions, shutdown strategy execution threads, and invalidate login sessions.
    
    engine_logger.warning("Market close time (15:30 IST) reached. Starting auto-logout sequence...")
    
    # 1. Terminate all active strategy runs and flatten positions
    algo_service = AlgoService()
    algo_service.shutdown()
    
    # 2. Logout and clean up all API client sessions
    client_manager = ClientManager()
    sessions = client_manager.get_all_sessions()
    
    for session_id in sessions:
        client_manager.remove_client(session_id)
        
    engine_logger.info("Auto-logout sequence completed successfully.")
