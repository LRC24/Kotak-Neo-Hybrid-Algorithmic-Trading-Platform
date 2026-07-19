// Unified namespace for client-side controllers
window.NeoAlgo = {
    socket: null,
    
    initializeSocket: function() {
        // Instantiate socket instance connection
        this.socket = io();
        
        const dot = document.getElementById('socket-status-dot');
        const text = document.getElementById('socket-status-text');
        
        this.socket.on('connect', () => {
            if (dot) {
                dot.className = 'status-dot connected';
                text.innerText = 'Connected';
            }
        });
        
        this.socket.on('disconnect', () => {
            if (dot) {
                dot.className = 'status-dot disconnected';
                text.innerText = 'Disconnected';
            }
            this.showAlert('WebSocket connection severed. Attempting reconnection...', 'error');
        });
    },
    
    showAlert: function(message, type = 'success') {
        const container = document.getElementById('alerts-container');
        if (!container) return;
        
        const banner = document.createElement('div');
        banner.className = `alert-banner ${type}`;
        
        const icon = type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation';
        banner.innerHTML = `
            <i class="fa-solid ${icon}"></i>
            <span>${message}</span>
        `;
        
        container.appendChild(banner);
        
        // Auto-dismiss alert banner after 5 seconds
        setTimeout(() => {
            banner.style.opacity = '0';
            banner.style.transform = 'translateY(-10px)';
            banner.style.transition = 'all 0.3s';
            setTimeout(() => banner.remove(), 300);
        }, 5000);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    window.NeoAlgo.initializeSocket();
    
    // Bind global logout button if present
    const logoutBtn = document.getElementById('btn-global-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', () => {
            fetch('/api/auth/logout', { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.success) {
                        window.location.href = '/login';
                    }
                })
                .catch(err => console.error("Logout failed:", err));
        });
    }
});
