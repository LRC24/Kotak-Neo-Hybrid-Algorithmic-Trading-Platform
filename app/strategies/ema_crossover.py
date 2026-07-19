import datetime
import uuid
from ..engine.base_strategy import BaseStrategy

class EMACrossoverStrategy(BaseStrategy):
    """
    Algorithmic Crossover Strategy.
    Buys on Golden Cross (9 EMA crosses above 21 EMA).
    Sells on Death Cross (9 EMA crosses below 21 EMA).
    Incorporates Stop-Loss and Take-Profit checks.
    """
    
    @classmethod
    def get_backend_params(cls) -> dict:
        # Immutable backend strategy parameters
        return {
            'fast_period': 9,
            'slow_period': 21,
            'min_ticks_required': 30
        }

    def __init__(self, run_id: str, symbol: str, lot_size: int, user_params: dict, db_session_factory, broker_manager):
        super().__init__(run_id, symbol, lot_size, user_params, db_session_factory, broker_manager)
        
        # Historical prices and calculated indicator lists
        self.prices = []
        self.fast_ema = []
        self.slow_ema = []
        
        # Risk management multipliers
        self.stop_loss_pct = float(user_params.get('stop_loss_pct', 1.0)) / 100.0
        self.take_profit_pct = float(user_params.get('take_profit_pct', 2.0)) / 100.0
        self.average_entry = 0.0

    def _compute_ema(self, series: list, period: int) -> float:
        # Applies EMA smoothing formula over tick history
        if len(series) < period:
            return 0.0
        multiplier = 2.0 / (period + 1)
        # SMA for initial base
        val = sum(series[:period]) / period
        for price in series[period:]:
            val = ((price - val) * multiplier) + val
        return val

    def on_tick(self, tick: dict):
        if not self.is_active:
            return
            
        ltp = float(tick.get('ltp', 0.0))
        if ltp <= 0:
            return
            
        self.prices.append(ltp)
        if len(self.prices) > 100:
            self.prices.pop(0)
            
        min_ticks = self.backend_params['min_ticks_required']
        if len(self.prices) < min_ticks:
            return
            
        curr_fast = self._compute_ema(self.prices, self.backend_params['fast_period'])
        curr_slow = self._compute_ema(self.prices, self.backend_params['slow_period'])
        
        self.fast_ema.append(curr_fast)
        self.slow_ema.append(curr_slow)
        
        if len(self.fast_ema) > 2:
            self.fast_ema.pop(0)
            self.slow_ema.pop(0)
            
        # Check risk limits if holding open position
        if self.position != 0:
            self._check_risk_exits(ltp)
            self.update_live_pnl(ltp)
            return
            
        # Check signal crossovers
        if len(self.fast_ema) >= 2:
            prev_f, cur_f = self.fast_ema[-2], self.fast_ema[-1]
            prev_s, cur_s = self.slow_ema[-2], self.slow_ema[-1]
            
            # Fetch dynamic lot size from ScripService
            from ..services.scrip_service import ScripService
            scrip_service = ScripService()
            contract_multiplier = scrip_service.get_lot_size(self.symbol, default=50)
            
            # Fast crosses ABOVE slow -> Golden Cross (BUY)
            if prev_f <= prev_s and cur_f > cur_s:
                self.logger.info("GOLDEN CROSS SIGNAL GENERATED.")
                qty = self.lot_size * contract_multiplier
                self.place_order(direction="BUY", price=ltp, quantity=qty, order_type="MARKETABLE_LIMIT")
                
            # Fast crosses BELOW slow -> Death Cross (SELL)
            elif prev_f >= prev_s and cur_f < cur_s:
                self.logger.info("DEATH CROSS SIGNAL GENERATED.")
                qty = self.lot_size * contract_multiplier
                self.place_order(direction="SELL", price=ltp, quantity=qty, order_type="MARKETABLE_LIMIT")

    def _check_risk_exits(self, ltp: float):
        # Monitors position average cost against Stop-Loss and Take-Profit bounds
        if self.position == 0 or self.average_entry <= 0:
            return
            
        pnl_ratio = (ltp - self.average_entry) / self.average_entry
        
        if self.position > 0:  # Long
            if pnl_ratio <= -self.stop_loss_pct:
                self.logger.warning(f"Stop-Loss triggered (Long). Entry: {self.average_entry} | LTP: {ltp} | PnL: {pnl_ratio*100:.2f}%")
                self.place_order(direction="SELL", price=ltp, quantity=abs(self.position), order_type="MARKETABLE_LIMIT")
            elif pnl_ratio >= self.take_profit_pct:
                self.logger.info(f"Take-Profit triggered (Long). Entry: {self.average_entry} | LTP: {ltp} | PnL: {pnl_ratio*100:.2f}%")
                self.place_order(direction="SELL", price=ltp, quantity=abs(self.position), order_type="MARKETABLE_LIMIT")
        else:  # Short
            short_pnl = -pnl_ratio
            if short_pnl <= -self.stop_loss_pct:
                self.logger.warning(f"Stop-Loss triggered (Short). Entry: {self.average_entry} | LTP: {ltp} | PnL: {short_pnl*100:.2f}%")
                self.place_order(direction="BUY", price=ltp, quantity=abs(self.position), order_type="MARKETABLE_LIMIT")
            elif short_pnl >= self.take_profit_pct:
                self.logger.info(f"Take-Profit triggered (Short). Entry: {self.average_entry} | LTP: {ltp} | PnL: {short_pnl*100:.2f}%")
                self.place_order(direction="BUY", price=ltp, quantity=abs(self.position), order_type="MARKETABLE_LIMIT")

    def on_order_update(self, order_details: dict):
        status = order_details.get("status")
        local_id = order_details.get("order_id")
        
        self.logger.info(f"Order Notification: {local_id} status updated to {status}")
        
        if status == "FILLED":
            trade_id = order_details.get("trade_id", f"TR_{uuid.uuid4().hex[:10].upper()}")
            price = float(order_details.get("price", 0.0))
            qty = int(order_details.get("quantity", 0))
            fill_time = order_details.get("fill_time", datetime.datetime.utcnow())
            
            # Persist fill record in database
            self.record_trade_fill(
                order_id=local_id,
                trade_id=trade_id,
                exec_price=price,
                exec_qty=qty,
                fill_time=fill_time
            )
            
            # Adjust entry cost basis
            if self.position == qty or self.position == -qty:
                self.average_entry = price
                self.logger.info(f"Established average entry basis: {self.average_entry:.2f}")
            elif self.position == 0:
                self.average_entry = 0.0
                self.logger.info("Position flattened. Entry cost basis reset.")
