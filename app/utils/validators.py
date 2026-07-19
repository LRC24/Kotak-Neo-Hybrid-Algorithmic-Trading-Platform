def validate_order_inputs(symbol: str, quantity: int, price: float = None) -> bool:
    """Validates basic parameters for placed orders"""
    if not symbol or not isinstance(symbol, str):
        return False
    if quantity <= 0:
        return False
    if price is not None and price <= 0.0:
        return False
    return True

def validate_strategy_params(params: dict) -> bool:
    """Validates the input constraints for strategy parameter settings"""
    try:
        sl = float(params.get('stop_loss_pct', 0))
        tp = float(params.get('take_profit_pct', 0))
        
        if sl <= 0 or sl > 100:
            return False
        if tp <= 0 or tp > 100:
            return False
        return True
    except (ValueError, TypeError):
        return False
