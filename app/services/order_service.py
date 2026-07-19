import logging
from typing import Optional
from ..database import get_db_session
from ..models import Order, Position
from .circuit_breaker import CircuitBreaker
from config import get_config
from ..kotak.client_manager import ClientManager
from ..kotak.api_wrapper import KotakAPIWrapper
from ..logging import api_logger

config = get_config()

class OrderService:
    # Validates pre-trade risk thresholds (daily loss limit, max order value) and formats trades using a Marketable Limit (Slippage Shield) offset.
    
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()
        self.client_manager = ClientManager()

    def process_order_placement(self, session_id: str, run_id: Optional[str], symbol: str, 
                                direction: str, ltp: float, quantity: int, order_type: str) -> dict:
        """
        Conducts risk checks, applies marketable offsets, and forwards order to Kotak Neo API.
        
        Args:
            session_id: Active login session key.
            run_id: The strategy instance ID (Null if manual order).
            symbol: Trading instrument.
            direction: BUY / SELL.
            ltp: Last traded price of the symbol.
            quantity: Number of shares/contracts.
            order_type: LIMIT / MARKET / MARKETABLE_LIMIT.
        """
        # 1. Pre-Trade Risk: Check Circuit Breaker
        if self.circuit_breaker.is_triggered():
            api_logger.error("Order rejected: Central Circuit Breaker is TRIGGERED. Trading is locked.")
            raise ValueError("Order placement blocked: Central Circuit Breaker is triggered.")
            
        # 2. Pre-Trade Risk: Check Max Order Value
        order_value = ltp * quantity
        if order_value > config.MAX_ORDER_VALUE:
            api_logger.error(f"Order rejected: Order value (₹{order_value:.2f}) exceeds max allowed limit (₹{config.MAX_ORDER_VALUE:.2f}).")
            raise ValueError(f"Order value exceeds maximum allowed order limit of ₹{config.MAX_ORDER_VALUE}.")
            
        # 3. Apply Slippage Shield (Marketable Limit logic)
        target_price = ltp
        final_order_type = order_type
        
        if order_type.upper() == 'MARKETABLE_LIMIT':
            final_order_type = 'LIMIT'
            if direction.upper() == 'BUY':
                target_price = ltp * 1.005  # Buy up to 0.5% higher
                api_logger.info(f"Slippage Shield active. Adjusting BUY target limit: {ltp} -> {target_price:.2f} (0.5% premium)")
            else:
                target_price = ltp * 0.995  # Sell down to 0.5% lower
                api_logger.info(f"Slippage Shield active. Adjusting SELL target limit: {ltp} -> {target_price:.2f} (0.5% discount)")
                
        # 4. Fetch Client
        sdk_client = self.client_manager.get_client(session_id)
        if not sdk_client:
            raise ValueError("No active Kotak API connection found. Please log in.")
            
        api_wrapper = KotakAPIWrapper(sdk_client)
        
        # Format parameters for API Wrapper
        tx_type = "B" if direction.upper() == "BUY" else "S"
        o_type = "L" if final_order_type.upper() == "LIMIT" else "M"
        
        order_params = {
            "trading_symbol": symbol,
            "exchange_segment": "nse_fo",
            "product": "NRML",
            "price": str(round(target_price, 2)),
            "quantity": str(quantity),
            "transaction_type": tx_type,
            "order_type": o_type,
            "validity": "DAY",
            "tag": str(run_id or "MANUAL")
        }
        
        try:
            # Place order on exchange
            response = api_wrapper.place_order(**order_params)
            return response
        except Exception as e:
            api_logger.error(f"Order execution crashed: {e}")
            raise
            
    def update_position_book(self, symbol: str, direction: str, price: float, quantity: int, run_id: Optional[str] = None):
        # Updates local SQLite positions cache for session persistence
        db = get_db_session()
        try:
            pos = db.query(Position).filter_by(symbol=symbol).first()
            
            # Match direction multiplier
            multiplier = 1 if direction.upper() == 'BUY' else -1
            change_qty = multiplier * quantity
            
            if not pos:
                # Create position if new
                pos = Position(
                    symbol=symbol,
                    product='NRML',
                    quantity=change_qty,
                    average_price=price,
                    realized_pnl=0.0,
                    unrealized_pnl=0.0,
                    run_id=run_id
                )
                db.add(pos)
                api_logger.info(f"Established new positions entry for {symbol}: Qty {change_qty} at Avg {price}")
            else:
                old_qty = pos.quantity
                new_qty = old_qty + change_qty
                
                if new_qty == 0:
                    # Flattened position: compute final realized profit
                    if old_qty > 0:
                        pos.realized_pnl += (price - pos.average_price) * abs(old_qty)
                    else:
                        pos.realized_pnl += (pos.average_price - price) * abs(old_qty)
                    pos.average_price = 0.0
                    pos.unrealized_pnl = 0.0
                elif (old_qty > 0 and change_qty < 0) or (old_qty < 0 and change_qty > 0):
                    # Partially closing position
                    closed_qty = min(abs(old_qty), quantity)
                    if old_qty > 0:
                        pos.realized_pnl += (price - pos.average_price) * closed_qty
                    else:
                        pos.realized_pnl += (pos.average_price - price) * closed_qty
                else:
                    # Adding to position: recalculate average cost basis
                    total_cost = (pos.average_price * abs(old_qty)) + (price * quantity)
                    pos.average_price = total_cost / abs(new_qty)
                    
                pos.quantity = new_qty
                pos.run_id = run_id
                db.add(pos)
                api_logger.info(f"Updated position {symbol}: Qty {old_qty} -> {new_qty} | Avg cost {pos.average_price:.2f}")
                
            db.commit()
        except Exception as e:
            db.rollback()
            api_logger.error(f"Failed to update database position entry: {e}")
        finally:
            db.close()
