import os
import time
from flask import Flask, render_template, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_session import Session
from config import get_config
from .database import init_db
from .routes import register_routes
from .logging import engine_logger

# Instantiate SocketIO with thread safety
socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

def create_app() -> Flask:
    """Flask Application Factory"""
    app = Flask(__name__, 
                template_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static'))
    
    # Load configuration
    config_obj = get_config()
    app.config.from_object(config_obj)
    
    # Configure filesystem session storage
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_FILE_DIR'] = os.path.join(config_obj.BASE_DIR, 'flask_sessions')
    os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)
    Session(app)
    
    # Bind blueprints
    register_routes(app)
    
    # Initialize Socket.IO
    socketio.init_app(app)
    
    # Initialize SQL tables
    with app.app_context():
        init_db()
        
    # Render main HTML files directly
    @app.route('/')
    def index():
        if not session.get('logged_in'):
            return render_template('login.html')
        return render_template('trading.html')
        
    @app.route('/login')
    def login_page():
        return render_template('login.html')
        
    # Initialize log streaming worker thread on startup
    _spawn_log_streamer()
    
    engine_logger.info("Flask-SocketIO server setup completed.")
    return app

# Log tail tracking storage: run_id -> last_file_position
_LOG_TAIL_POSITIONS = {}

def _spawn_log_streamer():
    """Spawns background daemon thread to stream strategy logs via SocketIO"""
    def log_watch_loop():
        workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(workspace_dir, 'logs')
        
        while True:
            # Sleep 1 second between tail reads
            time.sleep(1.0)
            
            if not os.path.exists(logs_dir):
                continue
                
            for filename in os.listdir(logs_dir):
                if filename.startswith('strategy_') and filename.endswith('.log'):
                    # Parse run_id: strategy_{strategy_name}_{run_id}.log
                    parts = filename[:-4].split('_')
                    if len(parts) >= 3:
                        run_id = "_".join(parts[2:])
                        filepath = os.path.join(logs_dir, filename)
                        
                        try:
                            # Open file and check for new lines
                            last_pos = _LOG_TAIL_POSITIONS.get(run_id, 0)
                            file_size = os.path.getsize(filepath)
                            
                            if file_size < last_pos:
                                # File was truncated / recreated
                                last_pos = 0
                                
                            if file_size > last_pos:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    f.seek(last_pos)
                                    new_lines = f.readlines()
                                    _LOG_TAIL_POSITIONS[run_id] = f.tell()
                                    
                                if new_lines:
                                    # Broadcast lines to strategy specific SocketIO room
                                    socketio.emit('strategy_log', {
                                        'run_id': run_id,
                                        'lines': new_lines
                                    }, to=run_id)
                        except Exception as e:
                            # Silent catch to prevent logging thread from crashing
                            pass

    t = Thread(target=log_watch_loop, name="LogStreamerThread", daemon=True)
    t.start()
    engine_logger.info("Background log streaming worker thread started.")

# Socket.IO Event Handlers
@socketio.on('join_strategy_log')
def on_join_log(data):
    """Allows UI client to subscribe to an isolated strategy's log feed"""
    run_id = data.get('run_id')
    if run_id:
        join_room(run_id)
        # Seed the last position to start of file if not present
        if run_id not in _LOG_TAIL_POSITIONS:
            _LOG_TAIL_POSITIONS[run_id] = 0
        engine_logger.info(f"Socket Client joined log stream room: {run_id}")
        emit('join_success', {'run_id': run_id})

@socketio.on('leave_strategy_log')
def on_leave_log(data):
    """Allows UI client to unsubscribe from strategy log room"""
    run_id = data.get('run_id')
    if run_id:
        leave_room(run_id)
        engine_logger.info(f"Socket Client left log stream room: {run_id}")

from threading import Thread
