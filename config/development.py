import os
from .base import Config

class DevelopmentConfig(Config):
    # Development Environment configuration
    DEBUG = True
    FLASK_ENV = 'development'
    
    # Development override for risk tolerances (tighter limits for testing)
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', 5000.0))
    MAX_ORDER_VALUE = float(os.getenv('MAX_ORDER_VALUE', 25000.0))
