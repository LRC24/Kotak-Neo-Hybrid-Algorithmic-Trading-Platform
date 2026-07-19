import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base

class StrategyRun(Base):
    # Tracks active and historical strategy execution instances
    __tablename__ = 'strategy_runs'
    
    run_id = Column(String(50), primary_key=True)
    strategy_name = Column(String(100), nullable=False)
    symbol = Column(String(50), nullable=False)
    lot_size = Column(Integer, nullable=False)
    status = Column(String(20), default='RUNNING')  # RUNNING, STOPPED, KILLED, ERROR
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    
    # Relationships
    params = relationship("StrategyParam", back_populates="run", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="run", cascade="all, delete-orphan")
    pnl_history = relationship("PnLHistory", back_populates="run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StrategyRun {self.strategy_name} on {self.symbol} - {self.status}>"


class StrategyParam(Base):
    # Stores a snapshot of all user and backend parameters at run startup
    __tablename__ = 'strategy_params'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(50), ForeignKey('strategy_runs.run_id', ondelete='CASCADE'), nullable=False)
    param_name = Column(String(100), nullable=False)
    param_value = Column(String(255), nullable=False)
    scope = Column(String(20), nullable=False)  # FRONTEND, BACKEND
    
    # Relationships
    run = relationship("StrategyRun", back_populates="params")

    def __repr__(self):
        return f"<StrategyParam {self.param_name}={self.param_value} ({self.scope})>"
