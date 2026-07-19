import os
import inspect
import importlib
import datetime
import uuid
import queue
from threading import Thread, Event, RLock
from ..logging import engine_logger
from ..database import get_db_session
from ..models import StrategyRun, StrategyParam, TickLog
from ..engine.base_strategy import BaseStrategy
from ..engine.broker_manager import BrokerManager
from ..kotak.client_manager import ClientManager

class StrategyRunner(Thread):
    
    # Background worker thread running a single strategy instance. Feeds ticks from an isolated queue into the strategy's tick callback hook.
    
    def __init__(self, strategy_instance, tick_queue: queue.Queue):
        super().__init__(name=f"Runner_{strategy_instance.run_id}", daemon=True)
        self.strategy = strategy_instance
        self.tick_queue = tick_queue
        self.stop_event = Event()
        
    def run(self):
        self.strategy.logger.info(f"Strategy runner thread loop started. ID: {self.strategy.run_id}")
        while not self.stop_event.is_set():
            try:
                # Poll tick updates
                tick = self.tick_queue.get(timeout=0.5)
                self.strategy.on_tick(tick)
                self.tick_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                self.strategy.logger.error(f"Error in strategy tick loop: {e}", exc_info=True)
                
        self.strategy.shutdown()
        self.strategy.logger.info(f"Strategy runner thread loop stopped. ID: {self.strategy.run_id}")

    def stop(self):
        self.stop_event.set()


class AlgoService:
    # Orchestrates the running algorithmic strategy threads.
    # Scans strategies directory, registers runs, maps active sessions, handles WebSocket ticks routing, and provides emergency kills.
    
    _instance = None
    _lock = RLock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
        
    def __init__(self, api_wrapper=None, mock_mode: bool = True):
        if self._initialized:
            return
            
        self.lock = RLock()
        self.mock_mode = mock_mode
        self.api_wrapper = api_wrapper
        
        # Instantiate Broker Manager
        self.broker_manager = BrokerManager(api_wrapper=api_wrapper, mock_mode=mock_mode)
        self.broker_manager.start()
        
        # Auto-discover strategies
        self.strategy_classes = {}
        self.discover_strategies()
        
        # Active sessions maps: run_id -> { 'strategy': BaseStrategy, 'runner': StrategyRunner, 'queue': queue.Queue }
        self.active_runs = {}
        self.ws_handlers = {}  # session_id -> KotakWebSocketHandler
        self.client_manager = ClientManager() # Store singleton reference
        self._initialized = True
        
        engine_logger.info("AlgoService initialized successfully.")

    def discover_strategies(self):
        # Scans strategies package and registers classes inheriting from BaseStrategy
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        strategies_dir = os.path.join(current_dir, 'strategies')
        
        if not os.path.exists(strategies_dir):
            engine_logger.warning(f"Strategies directory missing: {strategies_dir}")
            return
            
        for filename in os.listdir(strategies_dir):
            if filename.endswith('.py') and filename != '__init__.py':
                module_name = filename[:-3]
                try:
                    base_package = ".".join(__package__.split(".")[:-1]) if __package__ else "app"
                    module_path = f"{base_package}.strategies.{module_name}"
                    module = importlib.import_module(module_path)
                    
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if issubclass(obj, BaseStrategy) and obj is not BaseStrategy:
                            self.strategy_classes[name] = obj
                            engine_logger.info(f"Registered strategy logic class: {name}")
                except Exception as e:
                    engine_logger.error(f"Failed to load strategy module {module_name}: {e}", exc_info=True)

    def start_run(self, strategy_name: str, symbol: str, lot_size: int, user_params: dict) -> str:
        # Starts strategy thread and registers config parameters snapshot in database
        with self.lock:
            if strategy_name not in self.strategy_classes:
                raise ValueError(f"Strategy '{strategy_name}' is not registered.")
                
            # Dynamic live / mock detection
            sessions = self.client_manager.get_all_sessions()
            active_session = None
            for s in sessions:
                if self.client_manager.is_logged_in(s):
                    active_session = s
                    break
                    
            if active_session:
                from ..kotak.api_wrapper import KotakAPIWrapper
                client = self.client_manager.get_client(active_session)
                self.api_wrapper = KotakAPIWrapper(client)
                self.broker_manager.api_wrapper = self.api_wrapper
                self.broker_manager.mock_mode = False
                self.mock_mode = False
                engine_logger.info(f"Active session {active_session} detected. Switching engine to LIVE mode.")
            else:
                self.api_wrapper = None
                self.broker_manager.api_wrapper = None
                self.broker_manager.mock_mode = True
                self.mock_mode = True
                engine_logger.info("No active sessions detected. Operating in MOCK mode.")

            run_id = f"RUN_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:4].upper()}"
            engine_logger.info(f"Spawning {strategy_name} on {symbol} (Lots: {lot_size}). ID: {run_id}")
            
            strategy_cls = self.strategy_classes[strategy_name]
            
            # Save configuration snapshot in database
            db = get_db_session()
            try:
                db_run = StrategyRun(
                    run_id=run_id,
                    strategy_name=strategy_name,
                    symbol=symbol,
                    lot_size=lot_size,
                    status='RUNNING',
                    start_time=datetime.datetime.utcnow()
                )
                db.add(db_run)
                
                # Snapshot user inputs
                for k, v in user_params.items():
                    db_param = StrategyParam(run_id=run_id, param_name=k, param_value=str(v), scope='FRONTEND')
                    db.add(db_param)
                    
                # Snapshot hardcoded defaults
                backend_defaults = strategy_cls.get_backend_params()
                for k, v in backend_defaults.items():
                    db_param = StrategyParam(run_id=run_id, param_name=k, param_value=str(v), scope='BACKEND')
                    db.add(db_param)
                    
                db.commit()
            except Exception as e:
                db.rollback()
                engine_logger.error(f"Failed to record strategy run parameters: {e}")
                raise
            finally:
                db.close()
                
            # Crash Recovery: load active position and average entry price from positions table
            recovered_qty = 0
            recovered_avg = 0.0
            db = get_db_session()
            try:
                from ..models.position import Position
                db_pos = db.query(Position).filter_by(symbol=symbol).first()
                if db_pos and db_pos.quantity != 0:
                    recovered_qty = db_pos.quantity
                    recovered_avg = db_pos.average_price
                    engine_logger.info(f"State Recovery: Restoring symbol {symbol} position: {recovered_qty} at average: {recovered_avg:.2f}")
            except Exception as e:
                engine_logger.error(f"Failed to recover position state from DB: {e}")
            finally:
                db.close()

            # Instantiate strategy & spawn daemon runner thread
            tick_queue = queue.Queue()
            try:
                # We use get_db_session as factory to avoid locked sqlite threads
                strategy_instance = strategy_cls(
                    run_id=run_id,
                    symbol=symbol,
                    lot_size=lot_size,
                    user_params=user_params,
                    db_session_factory=get_db_session,
                    broker_manager=self.broker_manager
                )
                
                # Restore recovered states
                strategy_instance.position = recovered_qty
                strategy_instance.average_entry = recovered_avg
                
                runner = StrategyRunner(strategy_instance, tick_queue)
                runner.start()
                
                self.active_runs[run_id] = {
                    'strategy': strategy_instance,
                    'runner': runner,
                    'queue': tick_queue,
                    'symbol': symbol
                }
                
                # Start and subscribe WebSocket handler if live
                if active_session:
                    from ..kotak.websocket_handler import KotakWebSocketHandler
                    from .scrip_service import ScripService
                    scrip_service = ScripService()
                    
                    token_info = scrip_service.resolve_symbol_to_token(symbol)
                    if token_info:
                        token = token_info['instrument_token']
                        segment = token_info['exchange_segment']
                        
                        if active_session not in self.ws_handlers:
                            def on_tick(tick):
                                tk = str(tick.get('instrument_token') or tick.get('tk'))
                                seg = tick.get('exchange_segment') or tick.get('e')
                                resolved_symbol = scrip_service.resolve_token_to_symbol(tk, seg) or symbol
                                self.feed_tick_update(resolved_symbol, tick)
                                
                            def on_disconnect():
                                engine_logger.critical("WebSocket disconnected. Pausing running strategies.")
                                self.kill_all_runs()
                                
                            ws_handler = KotakWebSocketHandler(
                                client=client,
                                on_tick_callback=on_tick,
                                on_disconnect_callback=on_disconnect
                            )
                            self.ws_handlers[active_session] = ws_handler
                            
                        engine_logger.info(f"Subscribing to live websocket quote feed for {symbol} (Token: {token})")
                        self.ws_handlers[active_session].subscribe([{'instrument_token': token, 'exchange_segment': segment}])
                    else:
                        engine_logger.warning(f"Could not subscribe to {symbol} WebSocket feed: Symbol not found in Scrip Master.")

                engine_logger.info(f"Runner thread successfully spawned for run: {run_id}")
                return run_id
            except Exception as e:
                engine_logger.error(f"Runner instantiation crashed: {e}")
                # Revert run state in DB
                db = get_db_session()
                db_run = db.query(StrategyRun).filter_by(run_id=run_id).first()
                if db_run:
                    db_run.status = 'ERROR'
                    db_run.end_time = datetime.datetime.utcnow()
                    db.commit()
                db.close()
                raise

    def stop_run(self, run_id: str, status: str = 'STOPPED'):
        # Stops active runner, flattens position, and records EOD state in DB
        with self.lock:
            if run_id not in self.active_runs:
                return
                
            run_data = self.active_runs[run_id]
            symbol = run_data['symbol']
            engine_logger.info(f"Halting strategy run ID: {run_id} (State: {status})")
            
            # Stop tick queue processing
            runner = run_data['runner']
            runner.stop()
            runner.join(timeout=2.0)
            
            # Unsubscribe from WebSocket if active
            sessions = self.client_manager.get_all_sessions()
            active_session = None
            for s in sessions:
                if self.client_manager.is_logged_in(s):
                    active_session = s
                    break
            if active_session and active_session in self.ws_handlers:
                from .scrip_service import ScripService
                scrip_service = ScripService()
                token_info = scrip_service.resolve_symbol_to_token(symbol)
                if token_info:
                    self.ws_handlers[active_session].un_subscribe([{
                        'instrument_token': token_info['instrument_token'],
                        'exchange_segment': token_info['exchange_segment']
                    }])
            
            # Update DB run log
            db = get_db_session()
            try:
                db_run = db.query(StrategyRun).filter_by(run_id=run_id).first()
                if db_run:
                    db_run.status = status
                    db_run.end_time = datetime.datetime.utcnow()
                    db.commit()
            except Exception as e:
                db.rollback()
                engine_logger.error(f"Failed to update database status for run {run_id}: {e}")
            finally:
                db.close()
                
            del self.active_runs[run_id]
            engine_logger.info(f"Strategy run ID {run_id} cleaned up.")

    def kill_all_runs(self):
        # Emergency Kill Override: immediately flattens open positions and terminates threads
        engine_logger.warning("EMERGENCY GLOBAL OVERRIDE TRIGGERED. Flattening positions...")
        with self.lock:
            active_ids = list(self.active_runs.keys())
            for r_id in active_ids:
                try:
                    strategy = self.active_runs[r_id]['strategy']
                    if strategy.position != 0:
                        engine_logger.warning(f"Strategy {r_id} holds position of {strategy.position}. Flattening...")
                        exit_direction = "SELL" if strategy.position > 0 else "BUY"
                        strategy.place_order(direction=exit_direction, price=0.0, quantity=abs(strategy.position), order_type="MARKET")
                    self.stop_run(r_id, status='KILLED')
                except Exception as e:
                    engine_logger.error(f"Failed to flatten run {r_id}: {e}")
            engine_logger.warning("Global emergency override completed.")

    def feed_tick_update(self, symbol: str, tick: dict):
        # Dispatches ticks to database and forwards to strategy queue buffers
        # Save tick in database asynchronously
        db = get_db_session()
        try:
            db_tick = TickLog(
                symbol=symbol,
                price=float(tick.get('ltp', 0.0)),
                timestamp=datetime.datetime.utcnow()
            )
            db.add(db_tick)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
            
        # Push tick to queues
        with self.lock:
            for run_id, run_data in self.active_runs.items():
                if run_data['symbol'] == symbol:
                    try:
                        run_data['queue'].put_nowait(tick)
                    except queue.Full:
                        engine_logger.warning(f"Queue overflow for strategy run: {run_id}")

    def shutdown(self):
        # Terminates engine queues and daemon workers
        self.kill_all_runs()
        
        # Clean up all websocket connections
        for ws_handler in list(self.ws_handlers.values()):
            try:
                ws_handler.unsubscribe_all()
            except Exception as e:
                engine_logger.warning(f"Error unsubscribing websocket on shutdown: {e}")
        self.ws_handlers.clear()
        
        self.broker_manager.shutdown()
        self.broker_manager.join(timeout=2.0)
        engine_logger.info("AlgoService terminated.")
