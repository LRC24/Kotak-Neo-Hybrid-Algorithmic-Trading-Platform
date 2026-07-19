import os
from .base import Config
from .development import DevelopmentConfig

def get_config():
    """Factory to load configuration based on environment context"""
    env = os.getenv('FLASK_ENV', 'development').lower()
    
    if env == 'production':
        # Default to Config (which acts as production base)
        return Config
    else:
        return DevelopmentConfig
