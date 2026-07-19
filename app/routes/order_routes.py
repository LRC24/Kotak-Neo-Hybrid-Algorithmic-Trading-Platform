import logging
from flask import Blueprint, request, jsonify, session
from ..services.order_service import OrderService
from ..kotak.client_manager import ClientManager
from ..kotak.api_wrapper import KotakAPIWrapper
from ..utils.validators import validate_order_inputs

logger = logging.getLogger(__name__)
order_bp = Blueprint('orders', __name__)

order_service = OrderService()
client_manager = ClientManager()

@order_bp.route('/place', methods=['POST'])
def place_manual_order():
    # Places a manual order submitted from the UI dashboard form
    session_id = session.get('session_id')
    if not session_id or not client_manager.is_logged_in(session_id):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json() or {}
    symbol = data.get('symbol')
    direction = data.get('direction')
    quantity = int(data.get('quantity', 0))
    price = float(data.get('price', 0.0))
    order_type = data.get('order_type', 'LIMIT')
    
    # 1. Validate inputs
    if not validate_order_inputs(symbol, quantity, price):
        return jsonify({'success': False, 'message': 'Invalid input parameters.'}), 400
        
    try:
        # 2. Forward manual order (run_id is set to None for manual)
        response = order_service.process_order_placement(
            session_id=session_id,
            run_id=None,
            symbol=symbol,
            direction=direction,
            ltp=price,
            quantity=quantity,
            order_type=order_type
        )
        
        # 3. Update local position cache
        order_service.update_position_book(
            symbol=symbol,
            direction=direction,
            price=price,
            quantity=quantity,
            run_id=None
        )
        
        return jsonify({'success': True, 'response': response})
    except Exception as e:
        logger.error(f"Failed to place manual order: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@order_bp.route('/cancel', methods=['POST'])
def cancel_manual_order():
    # Cancels a pending order by ID
    session_id = session.get('session_id')
    if not session_id or not client_manager.is_logged_in(session_id):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json() or {}
    order_id = data.get('order_id')
    
    if not order_id:
        return jsonify({'success': False, 'message': 'Missing order_id'}), 400
        
    client = client_manager.get_client(session_id)
    wrapper = KotakAPIWrapper(client)
    
    try:
        response = wrapper.cancel_order(order_id=order_id)
        return jsonify({'success': True, 'response': response})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@order_bp.route('/report', methods=['GET'])
def get_order_book():
    # Returns the main order book log list
    session_id = session.get('session_id')
    if not session_id or not client_manager.is_logged_in(session_id):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    client = client_manager.get_client(session_id)
    wrapper = KotakAPIWrapper(client)
    
    try:
        orders = wrapper.get_orders()
        return jsonify({'success': True, 'orders': orders})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
