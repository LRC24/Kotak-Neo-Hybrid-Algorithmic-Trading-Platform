import datetime
from sqlalchemy import Column, String, Integer, Float, DateTime
from ..database import Base

class TickLog(Base):
    # Logs raw asset prices in real-time to generate post-market analysis charts
    __tablename__ = 'ticks_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, index=True)
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    def __repr__(self):
        return f"<TickLog {self.symbol} at {self.price}>"
