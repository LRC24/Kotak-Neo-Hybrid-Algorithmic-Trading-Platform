document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('login-form');
    const submitBtn = document.getElementById('btn-login-submit');
    const errorAlert = document.getElementById('login-error-alert');
    const errorMsg = document.getElementById('login-error-message');
    
    if (!loginForm) return;
    
    loginForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        const totpInput = document.getElementById('totp_code');
        const totp_code = totpInput.value.trim();
        
        if (totp_code.length !== 6 || isNaN(totp_code)) {
            showError("TOTP must be a 6-digit number.");
            return;
        }
        
        // Update button status
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Establishing session...`;
        errorAlert.style.display = 'none';
        
        fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ totp_code })
        })
        .then(res => res.json().then(data => ({ status: res.status, data })))
        .then(({ status, data }) => {
            if (status === 200 && data.success) {
                window.location.href = '/';
            } else {
                showError(data.message || "Failed to authenticate session.");
                submitBtn.disabled = false;
                submitBtn.innerHTML = `<span>Verify & Establish Session</span><i class="fa-solid fa-chevron-right btn-arrow"></i>`;
            }
        })
        .catch(err => {
            console.error("Auth request error:", err);
            showError("Network connection error. Please try again.");
            submitBtn.disabled = false;
            submitBtn.innerHTML = `<span>Verify & Establish Session</span><i class="fa-solid fa-chevron-right btn-arrow"></i>`;
        });
    });
    
    function showError(msg) {
        errorMsg.innerText = msg;
        errorAlert.style.display = 'flex';
    }
});
