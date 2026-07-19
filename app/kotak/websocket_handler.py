import time
import logging
from threading import Thread, Event
from ..logging import ws_logger

class KotakWebSocketHandler:
    # Manages Kotak Neo API WebSocket client streams.
    
    def __init__(self, client, on_tick_callback=None, on_disconnect_callback=None):
        self.client = client
        self.on_tick_callback = on_tick_callback
        self.on_disconnect_callback = on_disconnect_callback
        
        self.connected = False
        self.subscribed_tokens = set()  # Set of "token_segment" strings
        
        # Connection loss safety tracking
        self.last_disconnect_time = None
        self.disconnect_check_thread = None
        self.stop_check_event = Event()
        
        # Bind raw SDK connection callbacks
        self.client.on_message = self._handle_message
        self.client.on_error = self._handle_error
        self.client.on_close = self._handle_close
        self.client.on_open = self._handle_open

        ws_logger.info("WebSocket Handler initialized.")

    def _handle_message(self, message):
        # Processes incoming price updates from WebSocket
        try:
            if self.on_tick_callback and isinstance(message, dict):
                # Kotak Neo API returns list or dict tick payloads
                self.on_tick_callback(message)
        except Exception as e:
            ws_logger.error(f"Error executing tick callback: {e}")

    def _handle_error(self, error):
        ws_logger.error(f"WebSocket Client encountered error: {error}")

    def _handle_close(self, message):
        ws_logger.warning(f"WebSocket connection closed: {message}")
        self.connected = False
        
        # Start connection loss timeout tracking
        self.last_disconnect_time = time.time()
        self.stop_check_event.clear()
        
        if self.disconnect_check_thread is None or not self.disconnect_check_thread.is_alive():
            self.disconnect_check_thread = Thread(target=self._connection_loss_timeout_loop, daemon=True)
            self.disconnect_check_thread.start()

    def _handle_open(self, message):
        ws_logger.info("WebSocket connection established successfully.")
        self.connected = True
        self.last_disconnect_time = None
        self.stop_check_event.set()  # Stop connection loss tracking loop

    def _connection_loss_timeout_loop(self):
        # Monitors socket disconnection state, alerting engine after 15 seconds
        ws_logger.info("Connection-loss safety checker thread started.")
        while not self.stop_check_event.is_set():
            if self.last_disconnect_time:
                elapsed = time.time() - self.last_disconnect_time
                if elapsed >= 15.0:
                    ws_logger.critical(f"WebSocket disconnected for {elapsed:.1f}s (exceeded 15s limit). Triggering safety pause.")
                    if self.on_disconnect_callback:
                        try:
                            self.on_disconnect_callback()
                        except Exception as e:
                            ws_logger.error(f"Failed to execute safety pause callback: {e}")
                    # Stop checking once safety trigger completes
                    break
            time.sleep(1.0)
        ws_logger.info("Connection-loss safety checker thread terminated.")

    def subscribe(self, instrument_tokens: list, isIndex: bool = False, isDepth: bool = False) -> bool:
        # Subscribes to list of symbol tokens.Example: instrument_tokens=[{'instrument_token': '12345', 'exchange_segment': 'nse_fo'}]
        try:
            ws_logger.info(f"Sending subscription request for {len(instrument_tokens)} symbols...")
            self.client.subscribe(
                instrument_tokens=instrument_tokens,
                isIndex=isIndex,
                isDepth=isDepth
            )
            
            # Record subscribed tokens locally
            for t in instrument_tokens:
                key = f"{t['instrument_token']}_{t['exchange_segment']}"
                self.subscribed_tokens.add(key)
                
            ws_logger.info(f"Subscribed successfully. Active count: {len(self.subscribed_tokens)}")
            return True
        except Exception as e:
            ws_logger.error(f"Failed to subscribe to symbols: {e}")
            return False

    def un_subscribe(self, instrument_tokens: list, isIndex: bool = False, isDepth: bool = False) -> bool:
        # Unsubscribes from symbol tokens
        try:
            ws_logger.info(f"Sending unsubscription request for {len(instrument_tokens)} symbols...")
            self.client.un_subscribe(
                instrument_tokens=instrument_tokens,
                isIndex=isIndex,
                isDepth=isDepth
            )
            
            # Remove from local tracker
            for t in instrument_tokens:
                key = f"{t['instrument_token']}_{t['exchange_segment']}"
                self.subscribed_tokens.discard(key)
                
            ws_logger.info(f"Unsubscribed successfully. Active count: {len(self.subscribed_tokens)}")
            return True
        except Exception as e:
            ws_logger.error(f"Failed to unsubscribe from symbols: {e}")
            return False

    def unsubscribe_all(self):
        # Gracefully removes all active subscriptions
        if not self.subscribed_tokens:
            return True
            
        # Parse token keys back to payload formats
        tokens_payload = []
        for key in list(self.subscribed_tokens):
            parts = key.split('_', 1)
            if len(parts) == 2:
                tokens_payload.append({
                    'instrument_token': parts[0],
                    'exchange_segment': parts[1]
                })
                
        success = self.un_subscribe(tokens_payload)
        if success:
            self.subscribed_tokens.clear()
        return success
        
    def is_connected(self) -> bool:
        # Returns active socket connection state flag
        return self.connected
