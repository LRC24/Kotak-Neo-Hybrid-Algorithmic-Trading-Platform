from .auth_routes import auth_bp
from .trading_routes import trading_bp
from .order_routes import order_bp
from .algo_routes import algo_bp

def register_routes(app):
    """Registers all API blueprints with URL prefixes"""
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(trading_bp, url_prefix='/api/trading')
    app.register_blueprint(order_bp, url_prefix='/api/orders')
    app.register_blueprint(algo_bp, url_prefix='/api/algo')
