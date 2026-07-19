import os
import logging
from flask import Blueprint, request, jsonify, session
from ..services.algo_service import AlgoService
from ..kotak.client_manager import ClientManager

logger = logging.getLogger(__name__)
algo_bp = Blueprint('algo', __name__)

client_manager = ClientManager()
algo_service = AlgoService()

@algo_bp.route('/strategies', methods=['GET'])
def get_strategies():
    # Lists dynamically discovered strategy class names
    strategies = list(algo_service.strategy_classes.keys())
    return jsonify({'success': True, 'strategies': strategies})

@algo_bp.route('/start', methods=['POST'])
def start_strategy():
    # Spawns an active strategy daemon thread runner
    session_id = session.get('session_id')
    if not session_id or not client_manager.is_logged_in(session_id):
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    data = request.get_json() or {}
    strategy_name = data.get('strategy_name')
    symbol = data.get('symbol')
    lot_size = int(data.get('lot_size', 1))
    user_params = data.get('user_params', {})
    
    if not strategy_name or not symbol:
        return jsonify({'success': False, 'message': 'Missing strategy_name or symbol'}), 400
        
    try:
        run_id = algo_service.start_run(
            strategy_name=strategy_name,
            symbol=symbol,
            lot_size=lot_size,
            user_params=user_params
        )
        return jsonify({'success': True, 'run_id': run_id})
    except Exception as e:
        logger.error(f"Failed to start strategy {strategy_name}: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@algo_bp.route('/stop', methods=['POST'])
def stop_strategy():
    # Stops an active strategy runner thread
    data = request.get_json() or {}
    run_id = data.get('run_id')
    
    if not run_id:
        return jsonify({'success': False, 'message': 'Missing run_id'}), 400
        
    try:
        algo_service.stop_run(run_id)
        return jsonify({'success': True, 'message': f"Strategy run {run_id} stopped."})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@algo_bp.route('/kill-all', methods=['POST'])
def kill_all():
    # Triggers global emergency stop override
    try:
        algo_service.kill_all_runs()
        return jsonify({'success': True, 'message': 'All strategy runners killed and positions flattened.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@algo_bp.route('/runs', methods=['GET'])
def get_active_runs():
    # Returns active runner session details
    runs = {}
    for r_id, r_data in algo_service.active_runs.items():
        strategy = r_data['strategy']
        runs[r_id] = {
            'strategy_name': strategy.__class__.__name__,
            'symbol': r_data['symbol'],
            'lot_size': strategy.lot_size,
            'position': strategy.position,
            'realized_pnl': strategy.realized_pnl,
            'unrealized_pnl': strategy.unrealized_pnl
        }
    return jsonify({'success': True, 'runs': runs})

@algo_bp.route('/logs/<run_id>', methods=['GET'])
def get_strategy_logs(run_id: str):
    # Reads the last 100 lines of logs/strategy_{strategy_name}_{run_id}.log and returns them as a JSON list.
    
    # Fetch active strategy run metadata
    strategy_name = None
    for r_id, r_data in algo_service.active_runs.items():
        if r_id == run_id:
            strategy_name = r_data['strategy'].__class__.__name__
            break
            
    # Fallback to scan log directory if strategy thread stopped but files remain
    if not strategy_name:
        strategy_name = "EMACrossoverStrategy"  # Default fallback
        
    log_filename = f"strategy_{strategy_name}_{run_id}.log"
    workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    log_filepath = os.path.join(workspace_dir, 'logs', log_filename)
    
    if not os.path.exists(log_filepath):
        return jsonify({'success': False, 'message': 'Log file not found.'}), 404
        
    try:
        with open(log_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        # Return last 100 lines
        slice_lines = lines[-100:]
        return jsonify({'success': True, 'logs': slice_lines})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
