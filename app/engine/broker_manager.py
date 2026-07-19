import queue
import time
import uuid
import datetime
from threading import Thread, Event
from ..logging import api_logger

class BrokerManager(Thread):
    # Centralized, thread-safe execution manager thread.
    
    def __init__(self, api_wrapper=None, mock_mode: bool = True):
        super().__init__(name="BrokerManagerThread", daemon=True)
        self.api_wrapper = api_wrapper
        self.mock_mode = mock_mode
        self.order_queue = queue.Queue()
        self.stop_event = Event()
        
        api_logger.info(f"BrokerManager thread initialized. Mode: {'MOCK' if mock_mode else 'LIVE'}")

    def run(self):
        api_logger.info("BrokerManager loop started.")
        while not self.stop_event.is_set():
            try:
                # Read order queue
                request = self.order_queue.get(timeout=0.5)
                
                # Execute request
                self._process_request(request)
                
                self.order_queue.task_done()
                
                # Small rate limit buffer delay (100ms)
                time.sleep(0.1)
                
            except queue.Empty:
                continue
            except Exception as e:
                api_logger.error(f"Error in BrokerManager queue loop: {e}", exc_info=True)
                
        api_logger.info("BrokerManager loop stopped.")

    def submit_order(self, local_order_id: str, run_id: str, symbol: str, direction: str, 
                     price: float, quantity: int, order_type: str, strategy_callback):
        # Standard queue insertion interface for strategies
        request = {
            'action': 'PLACE',
            'local_order_id': local_order_id,
            'run_id': run_id,
            'symbol': symbol,
            'direction': direction,
            'price': price,
            'quantity': quantity,
            'order_type': order_type,
            'callback': strategy_callback,
            'timestamp': datetime.datetime.utcnow()
        }
        self.order_queue.put(request)
        api_logger.debug(f"Queued PLACE order {local_order_id} for strategy {run_id}")

    def submit_cancel(self, order_id: str, run_id: str, strategy_callback):
        # Standard queue cancellation interface
        request = {
            'action': 'CANCEL',
            'order_id': order_id,
            'run_id': run_id,
            'callback': strategy_callback,
            'timestamp': datetime.datetime.utcnow()
        }
        self.order_queue.put(request)
        api_logger.debug(f"Queued CANCEL order {order_id} for strategy {run_id}")

    def _process_request(self, req: dict):
        action = req['action']
        if action == 'PLACE':
            self._execute_place(req)
        elif action == 'CANCEL':
            self._execute_cancel(req)

    def _execute_place(self, req: dict):
        local_order_id = req['local_order_id']
        symbol = req['symbol']
        direction = req['direction']
        price = req['price']
        quantity = req['quantity']
        order_type = req['order_type']
        callback = req['callback']
        
        api_logger.info(f"Executing PLACE request {local_order_id}: {direction} {quantity} {symbol}")
        
        if self.mock_mode or self.api_wrapper is None:
            # Simulate network round-trip time (100ms)
            time.sleep(0.1)
            mock_broker_id = f"MOCK_{uuid.uuid4().hex[:10].upper()}"
            response = {"orderId": mock_broker_id, "stat": "Ok", "status": "success"}
            
            api_logger.info(f"Mock Fill. Broker ID: {mock_broker_id}")
            if callback:
                try:
                    callback(local_order_id, True, response)
                except Exception as e:
                    api_logger.error(f"Error in strategy order callback: {e}")
                    
            # Simulate asynchronous WebSocket client fill event
            try:
                import importlib
                def async_ws_fill():
                    time.sleep(0.05)  # Mimic short exchange matching delay
                    algo_mod = importlib.import_module("Algo Kotak Neo Trader.app.services.algo_service")
                    algo_svc = algo_mod.AlgoService()
                    run_id = req.get('run_id')
                    if run_id and run_id in algo_svc.active_runs:
                        strategy = algo_svc.active_runs[run_id]['strategy']
                        order_details = {
                            "order_id": local_order_id,
                            "status": "FILLED",
                            "price": price,
                            "quantity": quantity,
                            "trade_id": f"TR_{uuid.uuid4().hex[:10].upper()}",
                            "fill_time": datetime.datetime.utcnow()
                        }
                        strategy.on_order_update(order_details)
                        
                        # Sync global position tracker
                        order_svc_mod = importlib.import_module("Algo Kotak Neo Trader.app.services.order_service")
                        order_svc = order_svc_mod.OrderService()
                        order_svc.update_position_book(
                            symbol=symbol,
                            direction=direction,
                            price=price,
                            quantity=quantity,
                            run_id=run_id
                        )
                Thread(target=async_ws_fill, daemon=True).start()
            except Exception as e:
                api_logger.error(f"Failed to launch mock fill thread: {e}")
        else:
            try:
                tx_type = "B" if direction.upper() == "BUY" else "S"
                o_type = "L" if order_type.upper() == "LIMIT" else "M"
                
                order_params = {
                    "trading_symbol": symbol,
                    "exchange_segment": "nse_fo",
                    "product": "NRML",
                    "price": str(price),
                    "quantity": str(quantity),
                    "transaction_type": tx_type,
                    "order_type": o_type,
                    "validity": "DAY",
                    "tag": str(local_order_id)
                }
                
                api_logger.info(f"Sending REST payload to Kotak: {order_params}")
                response = self.api_wrapper.place_order(**order_params)
                
                if callback:
                    callback(local_order_id, True, response)
                    
            except Exception as e:
                api_logger.error(f"Failed to place order {local_order_id} via API: {e}")
                if callback:
                    callback(local_order_id, False, {}, str(e))

    def _execute_cancel(self, req: dict):
        order_id = req['order_id']
        callback = req['callback']
        
        api_logger.info(f"Executing CANCEL request for order: {order_id}")
        
        if self.mock_mode or self.api_wrapper is None:
            time.sleep(0.05)
            if callback:
                callback(order_id, True, {"status": "cancelled"})
        else:
            try:
                response = self.api_wrapper.cancel_order(order_id=order_id)
                if callback:
                    callback(order_id, True, response)
            except Exception as e:
                api_logger.error(f"Failed to cancel order {order_id} via API: {e}")
                if callback:
                    callback(order_id, False, {}, str(e))

    def shutdown(self):
        # Halts thread processing loop cleanly
        self.stop_event.set()
        api_logger.info("BrokerManager shutdown triggered.")
