import os

class Config:
    # Base Configuration class containing shared parameters
    SECRET_KEY = os.getenv('SECRET_KEY', 'algo_kotak_neo_default_secret_key')
    
    # Resolve absolute path for database file
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_DIR = os.path.join(BASE_DIR, 'database')
    os.makedirs(DB_DIR, exist_ok=True)
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(DB_DIR, 'algo_trading.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session Configuration
    SESSION_PERMANENT = True
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', 21600))  # 6 hours default
    
    # Risk Management Defaults
    MAX_DAILY_LOSS = float(os.getenv('MAX_DAILY_LOSS', 10000.0))  # ₹10,000 limit
    MAX_ORDER_VALUE = float(os.getenv('MAX_ORDER_VALUE', 50000.0))  # ₹50,000 limit
    AUTO_LOGOUT_TIME = os.getenv('AUTO_LOGOUT_TIME', '15:30')      # 3:30 PM IST market close
    
    # Scrip Master Configurations
    SCRIP_DIR = os.path.join(BASE_DIR, 'scrip_data')
    os.makedirs(SCRIP_DIR, exist_ok=True)
    
    # App Logging Options
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
