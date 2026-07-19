import os
import shutil
import datetime
import logging
from ..logging import db_logger

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_DIR = os.path.join(WORKSPACE_DIR, 'database')
BACKUP_DIR = os.path.join(DB_DIR, 'backups')

def run_db_backup():
    # Saves a copy of the active SQLite trading database to the backups folder, and removes old backup archives to prevent disk bloat.
    
    db_file = os.path.join(DB_DIR, 'algo_trading.db')
    if not os.path.exists(db_file):
        db_logger.warning("Active database file not found. Backup skipped.")
        return
        
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = os.path.join(BACKUP_DIR, f"algo_trading_{timestamp}.db")
    
    try:
        # Perform safe copy
        shutil.copy2(db_file, backup_file)
        db_logger.info(f"Database backed up successfully to: {backup_file}")
        
        # Clean up files older than 30 days
        _cleanup_old_backups()
    except Exception as e:
        db_logger.error(f"Failed to backup trading database: {e}")

def _cleanup_old_backups():
    # Prunes database backup archives older than 30 days
    now = time.time()
    cutoff = now - (30 * 86400)  # 30 days in seconds
    
    if not os.path.exists(BACKUP_DIR):
        return
        
    for filename in os.listdir(BACKUP_DIR):
        filepath = os.path.join(BACKUP_DIR, filename)
        if os.path.isfile(filepath) and filename.startswith('algo_trading_') and filename.endswith('.db'):
            file_mtime = os.path.getmtime(filepath)
            if file_mtime < cutoff:
                try:
                    os.remove(filepath)
                    db_logger.info(f"Pruned old database backup file: {filename}")
                except Exception as e:
                    db_logger.warning(f"Failed to delete old backup {filename}: {e}")

import time
