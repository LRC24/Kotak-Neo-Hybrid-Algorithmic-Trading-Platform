import datetime
import uuid
from abc import ABC, abstractmethod
from ..logging import get_strategy_logger
from ..models import Order, TradeFill, PnLHistory

class BaseStrategy(ABC):
    # Abstract Base Class for all automated trading strategies.
    # Defines event hooks for tick feeds and order notifications, and exposes database-backed transaction wrapper methods.
    
    def __init__(self, run_id: str, symbol: str, lot_size: int, user_params: dict, db_session_factory, broker_manager):
        self.run_id = run_id
        self.symbol = symbol
        self.lot_size = lot_size
        self.user_params = user_params
        
        # dynamic strategy logger
        self.logger = get_strategy_logger(self.__class__.__name__, run_id)
        
        self.db_session_factory = db_session_factory
        self.broker_manager = broker_manager
        
        self.backend_params = self.get_backend_params()
        self.is_active = True
        self.position = 0  # Net contracts/shares held
        self.realized_pnl = 0.0
        self.unrealized_pnl = 0.0
        self.last_pnl_log_time = datetime.datetime.utcnow()
        
        self.logger.info(f"Initialized strategy {self.__class__.__name__} for {symbol} | Lots: {lot_size}")
        self.logger.info(f"Frontend Configurations: {user_params} | Backend Configs: {self.backend_params}")

    @classmethod
    @abstractmethod
    def get_backend_params(cls) -> dict:
        # Define hardcoded parameters that can only be changed via code files.
        pass

    @abstractmethod
    def on_tick(self, tick: dict):
        # Callback triggered for every price update tick of the symbol
        pass

    @abstractmethod
    def on_order_update(self, order_details: dict):
        # Callback triggered when an order execution event is updated by broker
        pass

    def get_db(self):
        # Returns a database session instance
        return self.db_session_factory()

    def place_order(self, direction: str, price: float, quantity: int, order_type: str = "LIMIT") -> str:
        # Registers a pending trade in the database and queues it to the Broker Manager. Automatically stamps decision/signal times.
        signal_time = datetime.datetime.utcnow()
        local_order_id = f"LOCAL_{uuid.uuid4().hex[:12].upper()}"
        
        self.logger.info(f"SIGNAL: {direction} {quantity} {self.symbol} at {price:.2f}. ID: {local_order_id}")
        
        db = self.get_db()
        try:
            db_order = Order(
                order_id=local_order_id,
                run_id=self.run_id,
                symbol=self.symbol,
                direction=direction.upper(),
                price=price,
                quantity=quantity,
                status='PENDING',
                signal_time=signal_time,
                placed_time=datetime.datetime.utcnow()
            )
            db.add(db_order)
            db.commit()
        except Exception as e:
            self.logger.error(f"Failed to record signal order in DB: {e}")
            db.rollback()
        finally:
            db.close()
            
        # Queue the order execution to the centralized manager
        self.broker_manager.submit_order(
            local_order_id=local_order_id,
            run_id=self.run_id,
            symbol=self.symbol,
            direction=direction,
            price=price,
            quantity=quantity,
            order_type=order_type,
            strategy_callback=self._handle_order_placement_response
        )
        return local_order_id

    def _handle_order_placement_response(self, local_order_id: str, success: bool, api_response: dict, error_msg: str = None):
        # Callback triggered when broker manager receives order placement reply
        db = self.get_db()
        try:
            db_order = db.query(Order).filter_by(order_id=local_order_id).first()
            if db_order:
                if success:
                    broker_id = api_response.get("orderId") or api_response.get("data", {}).get("orderId")
                    db_order.status = 'PLACED'
                    if broker_id:
                        db_order.rejection_reason = f"BrokerID:{broker_id}"
                        self.logger.info(f"Placed successfully on exchange. Broker ID: {broker_id}")
                else:
                    db_order.status = 'REJECTED'
                    db_order.rejection_reason = error_msg or "API error response"
                    self.logger.error(f"API placement failed: {db_order.rejection_reason}")
                
                db_order.placed_time = datetime.datetime.utcnow()
                db.commit()
        except Exception as e:
            self.logger.error(f"Error updating order response in DB: {e}")
            db.rollback()
        finally:
            db.close()

    def record_trade_fill(self, order_id: str, trade_id: str, exec_price: float, exec_qty: int, fill_time: datetime.datetime):
        # Records an execution fill in the database, updating position size and realized P&L
        db = self.get_db()
        try:
            # Prevent duplicate fills
            exists = db.query(TradeFill).filter_by(trade_id=trade_id).first()
            if exists:
                return

            db_order = db.query(Order).filter_by(order_id=order_id).first()
            signal_price = db_order.price if db_order else exec_price
            
            # Compute execution slippage
            if db_order and db_order.direction == 'BUY':
                slippage = exec_price - signal_price
            elif db_order and db_order.direction == 'SELL':
                slippage = signal_price - exec_price
            else:
                slippage = 0.0

            db_fill = TradeFill(
                trade_id=trade_id,
                order_id=order_id,
                execution_price=exec_price,
                executed_quantity=exec_qty,
                fill_time=fill_time,
                slippage=slippage
            )
            db.add(db_fill)
            
            if db_order:
                db_order.status = 'FILLED'
                direction_multiplier = 1 if db_order.direction == 'BUY' else -1
                old_pos = self.position
                
                is_adding = (old_pos >= 0 and direction_multiplier > 0) or (old_pos <= 0 and direction_multiplier < 0)
                
                if is_adding:
                    new_pos = old_pos + direction_multiplier * exec_qty
                    if new_pos != 0:
                        self.average_entry = (abs(old_pos) * self.average_entry + exec_qty * exec_price) / abs(new_pos)
                    else:
                        self.average_entry = 0.0
                    self.position = new_pos
                    self.logger.info(f"Position increased: {old_pos} -> {self.position}. Average entry: {self.average_entry:.2f}")
                else:
                    closed_qty = min(abs(old_pos), exec_qty)
                    if old_pos > 0:
                        trade_pnl = (exec_price - self.average_entry) * closed_qty
                    else:
                        trade_pnl = (self.average_entry - exec_price) * closed_qty
                        
                    self.realized_pnl += trade_pnl
                    self.position += direction_multiplier * exec_qty
                    
                    remaining_qty = exec_qty - closed_qty
                    if remaining_qty > 0:
                        self.average_entry = exec_price
                    elif self.position == 0:
                        self.average_entry = 0.0
                        
                    self.logger.info(f"Position updated: {old_pos} -> {self.position}. Cumulative Realized P&L: ₹{self.realized_pnl:.2f}")

            db.commit()
            self.logger.info(f"EXECUTION COMPLETED: Trade ID {trade_id} | Price: {exec_price} | Qty: {exec_qty} | Slippage: {slippage:.2f}")
        except Exception as e:
            self.logger.error(f"Failed to record execution fill in database: {e}")
            db.rollback()
        finally:
            db.close()

    def update_live_pnl(self, current_price: float):
        # Computes current unrealized P&L and registers snapshots every 5 seconds
        if self.position == 0:
            self.unrealized_pnl = 0.0
        else:
            if self.position > 0:
                self.unrealized_pnl = self.position * (current_price - self.average_entry)
            else:
                self.unrealized_pnl = abs(self.position) * (self.average_entry - current_price)
            
        now = datetime.datetime.utcnow()
        if (now - self.last_pnl_log_time).total_seconds() >= 5.0:
            db = self.get_db()
            try:
                pnl_snap = PnLHistory(
                    run_id=self.run_id,
                    timestamp=now,
                    unrealized_pnl=self.unrealized_pnl,
                    realized_pnl=self.realized_pnl
                )
                db.add(pnl_snap)
                db.commit()
                self.last_pnl_log_time = now
                self.logger.debug(f"P&L History Snapshot saved: Realized={self.realized_pnl} | Unrealized={self.unrealized_pnl}")
            except Exception as e:
                db.rollback()
            finally:
                db.close()

    def shutdown(self):
        # Executes exit routine when strategy thread is stopped
        self.is_active = False
        self.logger.info(f"Strategy runner thread shutdown completed for run: {self.run_id}")
