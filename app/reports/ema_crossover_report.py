import json
import logging
from .base_report import BaseReport

logger = logging.getLogger(__name__)

class EMACrossoverReport(BaseReport):
    
    # EMA Crossover Strategy Reporter.Overrides BaseReport to plot EMA_9 and EMA_21 lines.
    
    def __init__(self, run_id: str):
        super().__init__(run_id)
        self._calculate_indicators()

    def _calculate_indicators(self):
        prices = self.chart_data.get('tick_prices', [])
        fast_period = int(self.parameters['backend'].get('fast_period', 9))
        slow_period = int(self.parameters['backend'].get('slow_period', 21))
        
        self.chart_data['fast_ema'] = self._compute_ema_list(prices, fast_period)
        self.chart_data['slow_ema'] = self._compute_ema_list(prices, slow_period)

    def _compute_ema_list(self, prices, period) -> list:
        if len(prices) < period:
            return [0.0] * len(prices)
            
        ema_list = [0.0] * (period - 1)
        sma = sum(prices[:period]) / period
        ema_list.append(sma)
        
        multiplier = 2.0 / (period + 1)
        current_ema = sma
        
        for price in prices[period:]:
            current_ema = ((price - current_ema) * multiplier) + current_ema
            ema_list.append(current_ema)
            
        return ema_list

    def generate_html_report(self, output_path: str):
        html_template = f"""<!DOCTYPE html>
<html>
<head>
    <title>EOD Execution Report - EMA Crossover</title>
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
            <h1>EOD Execution Summary - EMA Crossover Strategy</h1>
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
            <h3 style="margin-top:0; color:#94a3b8;">LTP Price (with Indicators) vs Realized PnL Timeline</h3>
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
        
        const fastEma = {json.dumps(self.chart_data.get('fast_ema', []))};
        const slowEma = {json.dumps(self.chart_data.get('slow_ema', []))};
        
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
                        label: 'EMA 9 (Fast)',
                        data: fastEma,
                        borderColor: '#fbbf24',
                        borderWidth: 1.5,
                        yAxisID: 'yPrice',
                        tension: 0.1,
                        pointRadius: 0,
                        borderDash: [5, 5]
                    }},
                    {{
                        label: 'EMA 21 (Slow)',
                        data: slowEma,
                        borderColor: '#ec4899',
                        borderWidth: 1.5,
                        yAxisID: 'yPrice',
                        tension: 0.1,
                        pointRadius: 0,
                        borderDash: [3, 3]
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
        logger.info(f"EMA Custom Report generated: {output_path}")
