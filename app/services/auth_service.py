import os
from ..kotak.client_manager import ClientManager
from ..kotak.api_wrapper import KotakAPIWrapper
from ..logging import api_logger

class AuthService:
    # Coordinates session authentication and credentials verification for Kotak Neo API.
    # Uses UCC, MPIN, and CONSUMER_KEY variables defined in the environment.
    
    def __init__(self):
        self.client_manager = ClientManager()

    def authenticate_session(self, session_id: str, totp_code: str) -> bool:
        # Runs the two-step Kotak authentication flow:
        # 1. Submits Mobile, UCC, and manual TOTP code.
        # 2. Submits MPIN to resolve edit_sid, edit_token, and serverId.
        mobile = os.getenv('MOBILE_NUMBER')
        ucc = os.getenv('UCC')
        mpin = os.getenv('MPIN')
        consumer_key = os.getenv('CONSUMER_KEY')
        
        if not all([mobile, ucc, mpin, consumer_key]):
            api_logger.error("Missing credentials in environment variables (.env). Ensure UCC, MPIN, MOBILE_NUMBER, and CONSUMER_KEY are configured.")
            return False
            
        try:
            # Create a raw SDK client instance
            sdk_client = self.client_manager.create_client(session_id, consumer_key)
            api_wrapper = KotakAPIWrapper(sdk_client)
            
            # Step 1: Submit TOTP
            api_wrapper.login_with_totp(mobile_number=mobile, ucc=ucc, totp=totp_code)
            
            # Step 2: Validate with MPIN
            api_wrapper.validate_totp(mpin=mpin)
            
            # Mark session as active and authenticated
            self.client_manager.set_logged_in(session_id, True)
            return True
            
        except Exception as e:
            api_logger.error(f"Authentication failed for session {session_id}: {e}")
            # Clean up client on failure
            self.client_manager.remove_client(session_id)
            return False

    def logout_session(self, session_id: str):
        # Disconnects the session wrapper and logs out from Kotak Neo
        self.client_manager.remove_client(session_id)
        
    def is_session_active(self, session_id: str) -> bool:
        # Checks validation state of active session key
        return self.client_manager.is_logged_in(session_id)
