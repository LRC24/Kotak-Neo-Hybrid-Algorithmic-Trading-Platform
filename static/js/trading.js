document.addEventListener('DOMContentLoaded', () => {
    // Local trackers
    let activeLogRunId = null;
    let refreshInterval = null;

    // UI elements lookup cache
    const elements = {
        cashMargin: document.getElementById('cash-margin-val'),
        pnlTotal: document.getElementById('pnl-total-val'),
        pnlBreakdown: document.getElementById('pnl-breakdown-sub'),
        breakerState: document.getElementById('breaker-state-text'),
        breakerRemaining: document.getElementById('breaker-remaining-text'),
        breakerCard: document.getElementById('circuit-breaker-card'),
        strategySelect: document.getElementById('select-strategy-cls'),
        activeRunsTable: document.getElementById('active-runs-table-body'),
        positionsTable: document.getElementById('open-positions-table-body'),
        ordersTable: document.getElementById('todays-orders-table-body'),
        logsModal: document.getElementById('logs-modal'),
        consoleLogs: document.getElementById('console-logs-container'),
        modalRunId: document.getElementById('modal-run-id')
    };

    // Initialize Page
    initDashboard();

    function initDashboard() {
        // Load configurations and dynamic dropdown options
        loadStrategiesDropdown();
        
        // Execute initial data pull
        refreshAllData();
        
        // Setup polling loop (every 3 seconds)
        refreshInterval = setInterval(refreshAllData, 3000);
        
        // Bind event listeners
        bindEventListeners();
        
        // Socket.IO Strategy log receiver
        if (window.NeoAlgo.socket) {
            window.NeoAlgo.socket.on('strategy_log', (data) => {
                if (data.run_id === activeLogRunId) {
                    appendConsoleLines(data.lines);
                }
            });
        }
    }

    function refreshAllData() {
        fetchLimits();
        fetchPnLSummary();
        fetchActiveRuns();
        fetchPositions();
        fetchOrdersBook();
    }

    function bindEventListeners() {
        // Strategy launch form submission
        document.getElementById('strategy-launch-form').addEventListener('submit', handleStrategyLaunch);
        
        // Manual orders BUY & SELL click listeners
        document.getElementById('btn-manual-buy').addEventListener('click', () => handleManualOrder('BUY'));
        document.getElementById('btn-manual-sell').addEventListener('click', () => handleManualOrder('SELL'));
        
        // Emergency overall kill override
        document.getElementById('btn-emergency-kill').addEventListener('click', triggerEmergencyKill);
        
        // Close modal console logs
        document.getElementById('btn-close-logs-modal').addEventListener('click', closeLogsConsole);
        document.getElementById('btn-close-console').addEventListener('click', closeLogsConsole);
        document.getElementById('btn-clear-console').addEventListener('click', () => {
            elements.consoleLogs.innerHTML = '';
        });
    }

    // Load Strategies options dynamically
    function loadStrategiesDropdown() {
        fetch('/api/algo/strategies')
            .then(res => res.json())
            .then(data => {
                if (data.success && elements.strategySelect) {
                    data.strategies.forEach(name => {
                        const opt = document.createElement('option');
                        opt.value = name;
                        opt.innerText = name;
                        elements.strategySelect.appendChild(opt);
                    });
                }
            })
            .catch(err => console.error("Failed to load strategies:", err));
    }

    // REST fetches
    function fetchLimits() {
        fetch('/api/trading/limits')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.limits) {
                    const cash = parseFloat(data.limits.cash || 0.0);
                    elements.cashMargin.innerText = `₹${cash.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
                }
            })
            .catch(err => console.error("Limits fetch failed:", err));
    }

    function fetchPnLSummary() {
        fetch('/api/trading/pnl-summary')
            .then(res => res.json())
            .then(data => {
                if (data.success && data.pnl) {
                    const realized = parseFloat(data.pnl.realized_pnl || 0.0);
                    const unrealized = parseFloat(data.pnl.unrealized_pnl || 0.0);
                    const total = parseFloat(data.pnl.total_pnl || 0.0);
                    const status = data.pnl.circuit_breaker || {};
                    
                    // Display Total P&L
                    elements.pnlTotal.innerText = `₹${total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
                    elements.pnlTotal.className = `metric-value ${total >= 0 ? 'status-normal' : 'status-triggered'}`;
                    elements.pnlBreakdown.innerText = `Realized: ₹${realized.toFixed(2)} | Unrealized: ₹${unrealized.toFixed(2)}`;
                    
                    // Display circuit breaker
                    const cbState = status.state || 'NORMAL';
                    elements.breakerState.innerText = cbState;
                    elements.breakerState.className = `metric-value status-${cbState.toLowerCase()}`;
                    elements.breakerRemaining.innerText = `Limit: ₹${parseFloat(status.max_loss_limit).toFixed(2)} | Remaining: ₹${parseFloat(status.remaining_margin).toFixed(2)}`;
                }
            })
            .catch(err => console.error("PnL summary fetch failed:", err));
    }

    function fetchActiveRuns() {
        fetch('/api/algo/runs')
            .then(res => res.json())
            .then(data => {
                if (data.success && elements.activeRunsTable) {
                    const runIds = Object.keys(data.runs);
                    if (runIds.length === 0) {
                        elements.activeRunsTable.innerHTML = `<tr><td colspan="9" class="empty-state">No automated strategies running currently.</td></tr>`;
                        return;
                    }
                    
                    let html = '';
                    runIds.forEach(id => {
                        const run = data.runs[id];
                        html += `
                            <tr>
                                <td><code>${id}</code></td>
                                <td><strong>${run.strategy_name}</strong></td>
                                <td><code>${run.symbol}</code></td>
                                <td>${run.lot_size}</td>
                                <td><span class="badge-direction ${run.position >= 0 ? 'badge-buy' : 'badge-sell'}">${run.position}</span></td>
                                <td class="${run.realized_pnl >= 0 ? 'status-normal' : 'status-triggered'}">₹${run.realized_pnl.toFixed(2)}</td>
                                <td class="${run.unrealized_pnl >= 0 ? 'status-normal' : 'status-triggered'}">₹${run.unrealized_pnl.toFixed(2)}</td>
                                <td>
                                    <button class="btn btn-outline-secondary btn-sm btn-open-logs" data-run-id="${id}">
                                        <i class="fa-solid fa-terminal"></i> Console
                                    </button>
                                </td>
                                <td>
                                    <button class="btn btn-danger btn-sm btn-stop-strategy" data-run-id="${id}">
                                        <i class="fa-solid fa-square"></i> Stop
                                    </button>
                                </td>
                            </tr>
                        `;
                    });
                    
                    elements.activeRunsTable.innerHTML = html;
                    
                    // Bind table action events
                    document.querySelectorAll('.btn-open-logs').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const runId = btn.getAttribute('data-run-id');
                            openLogsConsole(runId);
                        });
                    });
                    
                    document.querySelectorAll('.btn-stop-strategy').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const runId = btn.getAttribute('data-run-id');
                            stopStrategy(runId);
                        });
                    });
                }
            })
            .catch(err => console.error("Active runs fetch failed:", err));
    }

    function fetchPositions() {
        fetch('/api/trading/positions')
            .then(res => res.json())
            .then(data => {
                if (data.success && elements.positionsTable) {
                    if (data.positions.length === 0) {
                        elements.positionsTable.innerHTML = `<tr><td colspan="6" class="empty-state">No open positions.</td></tr>`;
                        return;
                    }
                    
                    let html = '';
                    data.positions.forEach(pos => {
                        const qty = parseInt(pos.quantity || pos.netQty || 0);
                        const buyPrice = parseFloat(pos.average_price || pos.buyAvgPrc || 0);
                        const rPnl = parseFloat(pos.realized_pnl || pos.rpnl || 0.0);
                        const uPnl = parseFloat(pos.unrealized_pnl || pos.urPnl || 0.0);
                        
                        html += `
                            <tr>
                                <td><strong>${pos.symbol || pos.trdSym}</strong></td>
                                <td><code>${pos.product || pos.prod}</code></td>
                                <td><span class="badge-direction ${qty >= 0 ? 'badge-buy' : 'badge-sell'}">${qty}</span></td>
                                <td>₹${buyPrice.toFixed(2)}</td>
                                <td class="${rPnl >= 0 ? 'status-normal' : 'status-triggered'}">₹${rPnl.toFixed(2)}</td>
                                <td class="${uPnl >= 0 ? 'status-normal' : 'status-triggered'}">₹${uPnl.toFixed(2)}</td>
                            </tr>
                        `;
                    });
                    elements.positionsTable.innerHTML = html;
                }
            })
            .catch(err => console.error("Positions fetch failed:", err));
    }

    function fetchOrdersBook() {
        fetch('/api/orders/report')
            .then(res => res.json())
            .then(data => {
                if (data.success && elements.ordersTable) {
                    if (data.orders.length === 0) {
                        elements.ordersTable.innerHTML = `<tr><td colspan="6" class="empty-state">No orders registered today.</td></tr>`;
                        return;
                    }
                    
                    let html = '';
                    // Display last 10 orders
                    data.orders.slice(-10).reverse().forEach(o => {
                        const side = o.direction || o.trnsTp || 'BUY';
                        const status = (o.status || o.ordSt || 'PENDING').toUpperCase();
                        
                        html += `
                            <tr>
                                <td><code>${o.order_id || o.nOrdNo || 'N/A'}</code></td>
                                <td><code>${o.symbol || o.trdSym}</code></td>
                                <td><span class="badge-direction ${side === 'BUY' ? 'badge-buy' : 'badge-sell'}">${side}</span></td>
                                <td>${o.quantity || o.qty}</td>
                                <td>₹${parseFloat(o.price || o.prc).toFixed(2)}</td>
                                <td><span class="badge-status status-${status.toLowerCase()}">${status}</span></td>
                            </tr>
                        `;
                    });
                    elements.ordersTable.innerHTML = html;
                }
            })
            .catch(err => console.error("Orders report failed:", err));
    }

    // Action Form submissions
    function handleStrategyLaunch(e) {
        e.preventDefault();
        
        const strategy_name = document.getElementById('select-strategy-cls').value;
        const symbol = document.getElementById('algo-symbol').value.trim();
        const lot_size = parseInt(document.getElementById('algo-lot-size').value);
        const stop_loss_pct = parseFloat(document.getElementById('algo-stop-loss').value);
        const take_profit_pct = parseFloat(document.getElementById('algo-take-profit').value);
        const target_pnl = document.getElementById('algo-target-pnl').value;
        
        if (!strategy_name || !symbol) return;
        
        const payload = {
            strategy_name,
            symbol,
            lot_size,
            user_params: {
                stop_loss_pct,
                take_profit_pct,
                target_pnl: target_pnl ? parseFloat(target_pnl) : null
            }
        };
        
        fetch('/api/algo/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.NeoAlgo.showAlert(`Strategy successfully started. Run ID: ${data.run_id}`);
                document.getElementById('strategy-launch-form').reset();
                refreshAllData();
            } else {
                window.NeoAlgo.showAlert(data.message, 'error');
            }
        })
        .catch(err => window.NeoAlgo.showAlert('Failed to contact starting endpoint.', 'error'));
    }

    function handleManualOrder(direction) {
        const symbol = document.getElementById('manual-symbol').value.trim();
        const qty = parseInt(document.getElementById('manual-qty').value);
        const price = parseFloat(document.getElementById('manual-price').value);
        const order_type = document.getElementById('manual-order-type').value;
        
        if (!symbol || !qty || !price) {
            window.NeoAlgo.showAlert('Fill symbol, quantity and price fields before ordering.', 'error');
            return;
        }
        
        const payload = { symbol, direction, quantity: qty, price, order_type };
        
        window.NeoAlgo.showAlert(`Sending manual ${direction} order...`);
        
        fetch('/api/orders/place', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.NeoAlgo.showAlert(`Manual order placed successfully on Exchange.`);
                refreshAllData();
            } else {
                window.NeoAlgo.showAlert(data.message, 'error');
            }
        })
        .catch(err => window.NeoAlgo.showAlert('Manual order routing failed.', 'error'));
    }

    function stopStrategy(runId) {
        if (!confirm(`Halt strategy execution for run ${runId}?`)) return;
        
        fetch('/api/algo/stop', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ run_id: runId })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                window.NeoAlgo.showAlert(`Strategy instance stopped successfully.`);
                refreshAllData();
            } else {
                window.NeoAlgo.showAlert(data.message, 'error');
            }
        });
    }

    function triggerEmergencyKill() {
        if (!confirm("CRITICAL WARNING: This will immediately shutdown all running automated execution instances and attempt to flatten all outstanding positions. Proceed?")) return;
        
        fetch('/api/algo/kill-all', { method: 'POST' })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    window.NeoAlgo.showAlert('Emergency Override Successful. Positions flattened.', 'error');
                    refreshAllData();
                } else {
                    window.NeoAlgo.showAlert(data.message, 'error');
                }
            });
    }

    // Modal Live log Console managers
    function openLogsConsole(runId) {
        activeLogRunId = runId;
        elements.modalRunId.innerText = runId;
        elements.consoleLogs.innerHTML = '<div class="console-line">Connecting to live console stream room...</div>';
        elements.logsModal.style.display = 'flex';
        
        // Fetch static history from backend first
        fetch(`/api/algo/logs/${runId}`)
            .then(res => res.json())
            .then(data => {
                if (data.success && data.logs) {
                    elements.consoleLogs.innerHTML = '';
                    appendConsoleLines(data.logs);
                }
            })
            .catch(err => console.error("Failed to load log history:", err));
            
        // Subscribe to live tail room
        if (window.NeoAlgo.socket) {
            window.NeoAlgo.socket.emit('join_strategy_log', { run_id: runId });
        }
    }

    function closeLogsConsole() {
        if (window.NeoAlgo.socket && activeLogRunId) {
            window.NeoAlgo.socket.emit('leave_strategy_log', { run_id: activeLogRunId });
        }
        activeLogRunId = null;
        elements.logsModal.style.display = 'none';
    }

    function appendConsoleLines(lines) {
        lines.forEach(l => {
            const row = document.createElement('div');
            row.className = 'console-line';
            row.innerText = l.replace('\n', '');
            elements.consoleLogs.appendChild(row);
        });
        // Auto scroll to bottom
        elements.consoleLogs.scrollTop = elements.consoleLogs.scrollHeight;
    }
});
