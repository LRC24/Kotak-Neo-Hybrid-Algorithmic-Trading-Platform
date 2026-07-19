import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class Order(Base):
    # Tracks orders placed by strategies or manually via the trading desk UI
    __tablename__ = 'orders'
    
    order_id = Column(String(100), primary_key=True)  # Local order ID or broker order ID
    run_id = Column(String(50), ForeignKey('strategy_runs.run_id', ondelete='SET NULL'), nullable=True) # Null = MANUAL
    symbol = Column(String(50), nullable=False)
    direction = Column(String(10), nullable=False)  # BUY, SELL
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)
    status = Column(String(20), default='PENDING')  # PENDING, PLACED, FILLED, REJECTED, CANCELLED
    signal_time = Column(DateTime, default=datetime.datetime.utcnow)  # Algorithm trigger or UI click
    placed_time = Column(DateTime, nullable=True)  # Actual timestamp when sent to API
    rejection_reason = Column(String(255), nullable=True)
    
    # Relationships
    run = relationship("StrategyRun", back_populates="orders")
    fills = relationship("TradeFill", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Order {self.order_id} - {self.direction} {self.symbol} ({self.status})>"
