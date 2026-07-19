import logging
import time
from threading import RLock
from neo_api_client import NeoAPI
from ..logging import api_logger

class ClientManager:
    # Manages active instances of the Kotak Neo API Client. Thread-safe implementation using RLock.
    
    _instance = None
    _lock = RLock()
    
    def __new__(cls):
        # Singleton pattern implementation
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
        self.clients = {}  # session_id -> { 'client': NeoAPI, 'logged_in': bool, ... }
        self.clients_lock = RLock()
        self._initialized = True
        api_logger.info("Kotak ClientManager singleton initialized.")

    def create_client(self, session_id: str, consumer_key: str, environment: str = 'prod') -> NeoAPI:
        # Instantiates a new NeoAPI client and registers it under session_id
        with self.clients_lock:
            if session_id in self.clients:
                api_logger.warning(f"Client already exists for session ID: {session_id}")
                return self.clients[session_id]['client']
                
            try:
                # Create raw SDK instance
                client = NeoAPI(
                    consumer_key=consumer_key,
                    environment=environment,
                    access_token=None,
                    neo_fin_key=None
                )
                
                self.clients[session_id] = {
                    'client': client,
                    'environment': environment,
                    'logged_in': False,
                    'last_activity': time.time()
                }
                
                api_logger.info(f"Instantiated NeoAPI client for session: {session_id}")
                return client
            except Exception as e:
                api_logger.error(f"Failed to instantiate NeoAPI client: {e}", exc_info=True)
                raise

    def get_client(self, session_id: str) -> NeoAPI:
        # Retrieves active client instance and updates its activity timestamp
        with self.clients_lock:
            client_data = self.clients.get(session_id)
            if client_data:
                client_data['last_activity'] = time.time()
                return client_data['client']
            return None

    def get_client_data(self, session_id: str) -> dict:
        # Returns metadata configuration of the registered client
        with self.clients_lock:
            return self.clients.get(session_id)

    def set_logged_in(self, session_id: str, logged_in: bool = True):
        # Marks connection status flag
        with self.clients_lock:
            if session_id in self.clients:
                self.clients[session_id]['logged_in'] = logged_in
                api_logger.info(f"Session {session_id} logged_in status updated to: {logged_in}")

    def is_logged_in(self, session_id: str) -> bool:
        # Checks if a session is currently authorized
        with self.clients_lock:
            client_data = self.clients.get(session_id)
            return client_data.get('logged_in', False) if client_data else False

    def remove_client(self, session_id: str):
        # Disconnects session and logs out from Kotak Neo servers
        with self.clients_lock:
            if session_id in self.clients:
                client_data = self.clients[session_id]
                client = client_data['client']
                if client_data['logged_in']:
                    try:
                        api_logger.info(f"Logging out from Kotak Neo API for session: {session_id}")
                        client.logout()
                    except Exception as e:
                        api_logger.warning(f"Error logging out during removal: {e}")
                del self.clients[session_id]
                api_logger.info(f"Removed client session: {session_id}")
                
    def get_all_sessions(self) -> list:
        # Returns list of all active session keys
        with self.clients_lock:
            return list(self.clients.keys())
