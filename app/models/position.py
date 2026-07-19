from sqlalchemy import Column, String, Integer, Float, ForeignKey
from ..database import Base

class Position(Base):
    # Stores active trade positions, average entry prices, and running P&L metrics
    __tablename__ = 'positions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, unique=True)
    product = Column(String(20), default='NRML')  # NRML, MIS
    quantity = Column(Integer, default=0)         # Net quantity (long positive, short negative)
    average_price = Column(Float, default=0.0)    # Cost basis
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    run_id = Column(String(50), ForeignKey('strategy_runs.run_id', ondelete='SET NULL'), nullable=True) # Null = MANUAL

    def __repr__(self):
        return f"<Position {self.symbol} Qty: {self.quantity} AvgPrice: {self.average_price}>"
