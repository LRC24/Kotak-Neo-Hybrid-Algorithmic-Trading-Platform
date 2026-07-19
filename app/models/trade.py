from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class TradeFill(Base):
    # Tracks individual trade execution fills returned by the broker API
    __tablename__ = 'trade_fills'
    
    trade_id = Column(String(100), primary_key=True)  # Kotak Neo trade_id
    order_id = Column(String(100), ForeignKey('orders.order_id', ondelete='CASCADE'), nullable=False)
    execution_price = Column(Float, nullable=False)
    executed_quantity = Column(Integer, nullable=False)
    fill_time = Column(DateTime, nullable=False)  # API execution timestamp
    slippage = Column(Float, default=0.0)  # Execution Price - Signal Price
    
    # Relationships
    order = relationship("Order", back_populates="fills")

    def __repr__(self):
        return f"<TradeFill {self.trade_id} - Price: {self.execution_price} Qty: {self.executed_quantity}>"
