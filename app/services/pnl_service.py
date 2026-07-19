import datetime
import logging
from ..database import get_db_session
from ..models import Position, PnLHistory
from .circuit_breaker import CircuitBreaker
from ..logging import db_logger

class PnLService:
    
    # Computes aggregate account P&L (realized & unrealized) across all positions, saves timeline snapshots, and updates the risk Circuit Breaker status.
    
    
    def __init__(self):
        self.circuit_breaker = CircuitBreaker()

    def update_and_evaluate_pnl(self, session_id: str, current_prices: dict) -> dict:
        """
        Queries all active positions from the database, computes unrealized PnL based on
        current market prices, updates the database, and checks against the Circuit Breaker.
        
        Args:
            session_id: The active session key.
            current_prices (dict): { 'symbol': current_ltp }
            
        Returns:
            dict: { 'realized': X, 'unrealized': Y, 'total': Z, 'circuit_state': 'NORMAL' }
        """
        db = get_db_session()
        try:
            positions = db.query(Position).all()
            
            total_realized = 0.0
            total_unrealized = 0.0
            
            for pos in positions:
                # Update unrealized PnL if we have a fresh price update
                if pos.quantity != 0:
                    ltp = current_prices.get(pos.symbol)
                    if ltp is not None:
                        # Unrealized = Qty * (LTP - AvgEntryPrice)
                        pos.unrealized_pnl = pos.quantity * (ltp - pos.average_price)
                        db.add(pos)
                        
                total_realized += pos.realized_pnl
                total_unrealized += pos.unrealized_pnl
                
            db.commit()
            
            total_pnl = total_realized + total_unrealized
            
            # Feed to risk Circuit Breaker
            circuit_state = self.circuit_breaker.check_pnl(total_realized, total_unrealized)
            
            # Save historical snapshot in pnl_history
            pnl_snap = PnLHistory(
                run_id=None,  # Null represents the global/manual account snapshot
                timestamp=datetime.datetime.utcnow(),
                unrealized_pnl=total_unrealized,
                realized_pnl=total_realized
            )
            db.add(pnl_snap)
            db.commit()
            
            return {
                'realized_pnl': total_realized,
                'unrealized_pnl': total_unrealized,
                'total_pnl': total_pnl,
                'circuit_state': circuit_state
            }
            
        except Exception as e:
            db.rollback()
            db_logger.error(f"Error executing PnL update: {e}", exc_info=True)
            return {
                'realized_pnl': 0.0,
                'unrealized_pnl': 0.0,
                'total_pnl': 0.0,
                'circuit_state': self.circuit_breaker.state
            }
        finally:
            db.close()
            
    def get_account_pnl_summary(self) -> dict:
        # Returns current aggregate values from database positions
        db = get_db_session()
        try:
            positions = db.query(Position).all()
            realized = sum(p.realized_pnl for p in positions)
            unrealized = sum(p.unrealized_pnl for p in positions)
            return {
                'realized_pnl': realized,
                'unrealized_pnl': unrealized,
                'total_pnl': realized + unrealized,
                'circuit_breaker': self.circuit_breaker.get_status()
            }
        finally:
            db.close()
