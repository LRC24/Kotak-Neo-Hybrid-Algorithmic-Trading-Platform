import logging
from ..kotak.client_manager import ClientManager
from ..kotak.api_wrapper import KotakAPIWrapper
from ..logging import engine_logger

logger = logging.getLogger(__name__)

def run_session_heartbeat():

    # Periodic task running every 5 minutes to ping active broker sessions and verify credentials remain authorized.
    
    client_manager = ClientManager()
    sessions = client_manager.get_all_sessions()
    
    if not sessions:
        engine_logger.debug("No active session connections to ping.")
        return
        
    engine_logger.info(f"Running session heartbeat ping for {len(sessions)} active connections...")
    
    for session_id in sessions:
        if not client_manager.is_logged_in(session_id):
            continue
            
        client = client_manager.get_client(session_id)
        if not client:
            client_manager.set_logged_in(session_id, False)
            continue
            
        api_wrapper = KotakAPIWrapper(client)
        try:
            # Query limits as a low-overhead heartbeat ping
            api_wrapper.get_limits()
            engine_logger.info(f"Heartbeat succeeded for session: {session_id}")
        except Exception as e:
            engine_logger.error(f"Session heartbeat failed for {session_id} (connection lost): {e}")
            client_manager.set_logged_in(session_id, False)
