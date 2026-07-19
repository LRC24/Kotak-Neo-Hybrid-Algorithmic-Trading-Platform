import os
import json
import logging
import datetime
from sqlalchemy.orm import joinedload
from ..database.db_manager import get_db_session
from ..models.strategy_run import StrategyRun, StrategyParam
from ..models.order import Order
from ..models.trade import TradeFill
from ..models.pnl_history import PnLHistory
from ..models.tick_log import TickLog

logger = logging.getLogger(__name__)

class BaseReport:
    # Computes performance metrics (win rates, profits, slippages) and compiles a beautiful, self-contained HTML report with Chart.js plots.
    
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.run_details = {}
        self.parameters = {}
        self.metrics = {}
        self.chart_data = {}
        self.orders_list = []
        self.fills_list = []
        
        self._load_data()
        self._calculate_metrics()

    def _load_data(self):
        # Loads execution statistics and price history from database models
        db = get_db_session()
        try:
            # 1. Fetch Run details
            run = db.query(StrategyRun).filter_by(run_id=self.run_id).first()
            if not run:
                raise ValueError(f"Strategy run ID '{self.run_id}' not found.")
                
            self.run_details = {
                'run_id': run.run_id,
                'strategy_name': run.strategy_name,
                'symbol': run.symbol,
                'lot_size': run.lot_size,
                'status': run.status,
                'start_time': run.start_time.strftime('%Y-%m-%d %H:%M:%S') if run.start_time else 'N/A',
                'end_time': run.end_time.strftime('%Y-%m-%d %H:%M:%S') if run.end_time else 'N/A',
            }
            
            # 2. Fetch parameters
            params = db.query(StrategyParam).filter_by(run_id=self.run_id).all()
            self.parameters = {
                'frontend': {p.param_name: p.param_value for p in params if p.scope == 'FRONTEND'},
                'backend': {p.param_name: p.param_value for p in params if p.scope == 'BACKEND'}
            }
            
            # 3. Fetch orders and execution fills
            orders = db.query(Order).filter_by(run_id=self.run_id).options(joinedload(Order.fills)).all()
            
            for o in orders:
                self.orders_list.append({
                    'order_id': o.order_id,
                    'direction': o.direction,
                    'price': o.price,
                    'quantity': o.quantity,
                    'status': o.status,
                    'signal_time': o.signal_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    'placed_time': o.placed_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] if o.placed_time else 'N/A',
                    'rejection_reason': o.rejection_reason
                })
                
                for f in o.fills:
                    self.fills_list.append({
                        'trade_id': f.trade_id,
                        'order_id': f.order_id,
                        'direction': o.direction,
                        'execution_price': f.execution_price,
                        'executed_quantity': f.executed_quantity,
                        'fill_time': f.fill_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                        'slippage': f.slippage,
                        'latency_ms': int((f.fill_time - o.signal_time).total_seconds() * 1000) if o.signal_time else 0
                    })
                    
            # 4. Fetch PnL History
            pnl_history = db.query(PnLHistory).filter_by(run_id=self.run_id).order_by(PnLHistory.timestamp).all()
            self.chart_data['pnl_timestamps'] = [p.timestamp.strftime('%H:%M:%S') for p in pnl_history]
            self.chart_data['realized_pnl'] = [p.realized_pnl for p in pnl_history]
            self.chart_data['unrealized_pnl'] = [p.unrealized_pnl for p in pnl_history]
            
            # 5. Fetch Tick Log
            if run.start_time:
                ticks_query = db.query(TickLog).filter(TickLog.symbol == run.symbol, TickLog.timestamp >= run.start_time)
                if run.end_time:
                    ticks_query = ticks_query.filter(TickLog.timestamp <= run.end_time)
                ticks = ticks_query.order_by(TickLog.timestamp).all()
                self.chart_data['tick_timestamps'] = [t.timestamp.strftime('%H:%M:%S') for t in ticks]
                self.chart_data['tick_prices'] = [t.price for t in ticks]
            else:
                self.chart_data['tick_timestamps'] = []
                self.chart_data['tick_prices'] = []
                
        finally:
            db.close()

    def _calculate_metrics(self):
        # Calculates win rates, gross profits, and execution latencies
        latencies = [f['latency_ms'] for f in self.fills_list]
        slippages = [f['slippage'] for f in self.fills_list]
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_slippage = sum(slippages) / len(slippages) if slippages else 0.0
        
        # Win-rate match via FIFO buy-sell pairs
        trades_pnl = []
        buys = [f for f in self.fills_list if f['direction'] == 'BUY']
        sells = [f for f in self.fills_list if f['direction'] == 'SELL']
        
        for b, s in zip(buys, sells):
            trades_pnl.append(s['execution_price'] - b['execution_price'])
            
        wins = [p for p in trades_pnl if p > 0]
        losses = [p for p in trades_pnl if p <= 0]
        
        win_rate = (len(wins) / len(trades_pnl)) * 100.0 if trades_pnl else 0.0
        profit_factor = sum(wins) / abs(sum(losses)) if losses and sum(losses) != 0 else (sum(wins) if wins else 1.0)
        
        self.metrics = {
            'total_orders': len(self.orders_list),
            'filled_orders': len(self.fills_list),
            'avg_latency_ms': int(avg_latency),
            'avg_slippage': round(avg_slippage, 4),
            'total_trades': len(trades_pnl),
            'win_rate': round(win_rate, 2),
            'profit_factor': round(profit_factor, 2),
            'total_pnl': round(self.chart_data['realized_pnl'][-1], 2) if self.chart_data.get('realized_pnl') else 0.0
        }

    def generate_html_report(self, output_path: str):
        # Generates self-contained HTML file
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>EOD Execution Report - {self.run_details['strategy_name']}</title>
    <meta charset="utf-8">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background-color: #0f172a;
            color: #f1f5f9;
            margin: 0;
            padding: 30px;
        }}
        .wrapper {{ max-width: 1200px; margin: 0 auto; }}
        header {{
            background: linear-gradient(135deg, #1e1b4b, #311042);
            padding: 24px;
            border-radius: 12px;
            border: 1px solid #4c1d95;
            margin-bottom: 24px;
        }}
        h1 {{ margin: 0; font-size: 26px; color: #a78bfa; }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background-color: #1e293b;
            padding: 20px;
            border-radius: 8px;
            border: 1px solid #334155;
        }}
        .card h3 {{ margin: 0; font-size: 13px; color: #94a3b8; text-transform: uppercase; }}
        .card .value {{ font-size: 28px; font-weight: bold; margin-top: 10px; color: #f8fafc; }}
        .value.profit {{ color: #10b981; }}
        .value.loss {{ color: #f43f5e; }}
        .chart-container {{
            background-color: #1e293b;
            padding: 24px;
            border-radius: 8px;
            border: 1px solid #334155;
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }}
        th {{ background-color: #0f172a; color: #94a3b8; }}
        tr:hover {{ background-color: #1e293b; }}
        .badge {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }}
        .badge.buy {{ background-color: #064e3b; color: #34d399; }}
        .badge.sell {{ background-color: #4c0519; color: #fb7185; }}
    </style>
</head>
<body>
    <div class="wrapper">
        <header>
            <h1>EOD Execution Summary - {self.run_details['strategy_name']}</h1>
            <p style="margin: 5px 0 0 0; color: #94a3b8;">Run ID: {self.run_details['run_id']} | Symbol: {self.run_details['symbol']}</p>
        </header>
        
        <div class="metrics-grid">
            <div class="card">
                <h3>Total Realized P&L</h3>
                <div class="value {('profit' if self.metrics['total_pnl'] >= 0 else 'loss')}">₹{self.metrics['total_pnl']}</div>
            </div>
            <div class="card">
                <h3>Win Rate</h3>
                <div class="value">{self.metrics['win_rate']}%</div>
            </div>
            <div class="card">
                <h3>Profit Factor</h3>
                <div class="value">{self.metrics['profit_factor']}</div>
            </div>
            <div class="card">
                <h3>Slippage Latency</h3>
                <div class="value">{self.metrics['avg_latency_ms']} ms</div>
            </div>
        </div>

        <div class="chart-container">
            <h3 style="margin-top:0; color:#94a3b8;">LTP Price and Realized PnL Timeline</h3>
            <canvas id="performanceChart" style="max-height: 380px;"></canvas>
        </div>

        <div style="display:grid; grid-template-columns: 2fr 1fr; gap:20px;">
            <div class="card" style="overflow-x:auto;">
                <h3>Executed Trades</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Fill Time</th>
                            <th>Side</th>
                            <th>Executed Price</th>
                            <th>Qty</th>
                            <th>Slippage</th>
                            <th>Latency</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f"<tr><td>{f['fill_time']}</td><td><span class='badge {f['direction'].lower()}'>{f['direction']}</span></td><td>₹{f['execution_price']}</td><td>{f['executed_quantity']}</td><td>₹{f['slippage']:.2f}</td><td>{f['latency_ms']} ms</td></tr>" for f in self.fills_list])}
                    </tbody>
                </table>
            </div>
            
            <div class="card">
                <h3>Execution Parameters</h3>
                <h4 style="margin:10px 0 5px 0; color:#a78bfa;">User Inputs</h4>
                <ul style="padding-left:18px; margin:0;">
                    {"".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in self.parameters['frontend'].items()])}
                </ul>
                <h4 style="margin:20px 0 5px 0; color:#818cf8;">Backend Configs</h4>
                <ul style="padding-left:18px; margin:0;">
                    {"".join([f"<li><strong>{k}:</strong> {v}</li>" for k, v in self.parameters['backend'].items()])}
                </ul>
            </div>
        </div>
    </div>

    <script>
        const ctx = document.getElementById('performanceChart').getContext('2d');
        const labels = {json.dumps(self.chart_data.get('tick_timestamps', []))};
        const prices = {json.dumps(self.chart_data.get('tick_prices', []))};
        const pnl = {json.dumps(self.chart_data.get('realized_pnl', []))};
        
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [
                    {{
                        label: 'LTP (Price)',
                        data: prices,
                        borderColor: '#6366f1',
                        yAxisID: 'yPrice',
                        tension: 0.1,
                        pointRadius: 0
                    }},
                    {{
                        label: 'Realized P&L (₹)',
                        data: pnl,
                        borderColor: '#10b981',
                        borderWidth: 2,
                        yAxisID: 'yPnL',
                        tension: 0.1,
                        pointRadius: 1,
                        fill: false
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{
                    yPrice: {{
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: {{ color: '#334155' }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    yPnL: {{
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: {{ drawOnChartArea: false }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    x: {{
                        grid: {{ color: '#334155' }},
                        ticks: {{ color: '#94a3b8', maxTicksLimit: 12 }}
                    }}
                }},
                plugins: {{
                    legend: {{ labels: {{ color: '#f1f5f9' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
        logger.info(f"Report generated successfully: {output_path}")
