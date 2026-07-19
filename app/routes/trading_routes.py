import logging
from flask import Blueprint, jsonify, session
from ..kotak.client_manager import ClientManager
from ..kotak.api_wrapper import KotakAPIWrapper
from ..services.pnl_service import PnLService

logger = logging.getLogger(__name__)
trading_bp = Blueprint('trading', __name__)

client_manager = ClientManager()
pnl_service = PnLService()

@trading_bp.route('/limits', methods=['GET'])
def get_limits():
    # Fetches funding limits and cash balances from broker
    session_id = session.get('session_id')
    if not session_id or not client_manager.is_logged_in(session_id):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    client = client_manager.get_client(session_id)
    wrapper = KotakAPIWrapper(client)
    
    try:
        limits = wrapper.get_limits()
        # Extract cash margin details
        cash_data = limits.get('data', {}) or limits
        return jsonify({'success': True, 'limits': cash_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@trading_bp.route('/positions', methods=['GET'])
def get_positions():
    # Fetches the position book list from Kotak
    session_id = session.get('session_id')
    if not session_id or not client_manager.is_logged_in(session_id):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    client = client_manager.get_client(session_id)
    wrapper = KotakAPIWrapper(client)
    
    try:
        positions = wrapper.get_positions()
        return jsonify({'success': True, 'positions': positions})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@trading_bp.route('/pnl-summary', methods=['GET'])
def get_pnl_summary():
    # Returns the current day's running realized and unrealized P&L
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    summary = pnl_service.get_account_pnl_summary()
    return jsonify({'success': True, 'pnl': summary})
