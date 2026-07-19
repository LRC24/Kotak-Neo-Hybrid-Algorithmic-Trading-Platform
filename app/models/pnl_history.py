import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class PnLHistory(Base):
    # Periodically records realized and unrealized PnL snapshots of active runs or the whole account
    __tablename__ = 'pnl_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey('strategy_runs.run_id', ondelete='CASCADE'), nullable=True) # Null = Manual/Global
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    
    # Relationships
    run = relationship("StrategyRun", back_populates="pnl_history")

    def __repr__(self):
        return f"<PnLHistory run_id: {self.run_id} Realized: {self.realized_pnl} Unrealized: {self.unrealized_pnl}>"
