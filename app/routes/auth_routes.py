import logging
from flask import Blueprint, request, jsonify, session
from ..services.auth_service import AuthService

logger = logging.getLogger(__name__)
auth_bp = Blueprint('auth', __name__)
auth_service = AuthService()

@auth_bp.route('/login', methods=['POST'])
def login():
    # Handles POST submissions for TOTP verification
    data = request.get_json() or {}
    totp_code = data.get('totp_code')
    
    if not totp_code or len(str(totp_code)) != 6:
        return jsonify({'success': False, 'message': 'Invalid TOTP format. Must be a 6-digit code.'}), 400
        
    # Generate unique session ID for the Flask session if not present
    import uuid
    if 'session_id' not in session:
        session['session_id'] = f"session_{uuid.uuid4().hex[:16]}"
        
    session_id = session['session_id']
    
    # Run auth steps
    success = auth_service.authenticate_session(session_id, str(totp_code))
    
    if success:
        session['logged_in'] = True
        logger.info(f"User login successful. Session ID: {session_id}")
        return jsonify({'success': True, 'message': 'Login successful.'})
    else:
        return jsonify({'success': False, 'message': 'Authentication failed. Please verify credentials.'}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    # Logs out and cleans up current session client
    session_id = session.get('session_id')
    if session_id:
        auth_service.logout_session(session_id)
        
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out.'})

@auth_bp.route('/status', methods=['GET'])
def status():
    # Returns active login validation state
    session_id = session.get('session_id')
    logged_in = session.get('logged_in', False)
    
    if logged_in and session_id and auth_service.is_session_active(session_id):
        return jsonify({'logged_in': True})
    else:
        return jsonify({'logged_in': False})
