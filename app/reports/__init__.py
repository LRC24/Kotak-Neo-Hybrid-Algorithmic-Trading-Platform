import os
import logging
from ..database.db_manager import get_db_session
from ..models.strategy_run import StrategyRun
from .base_report import BaseReport
from .ema_crossover_report import EMACrossoverReport

logger = logging.getLogger(__name__)

def generate_report(run_id: str, output_path: str = None) -> str:
    """
    Factory helper that selects the correct reporting generator
    based on the strategy type and compiles the HTML dashboard.
    """
    db = get_db_session()
    try:
        run = db.query(StrategyRun).filter_by(run_id=run_id).first()
        if not run:
            raise ValueError(f"No strategy run logs found for Run ID: {run_id}")
        strategy_name = run.strategy_name
    finally:
        db.close()
        
    # Set default EOD log report path
    if output_path is None:
        workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        logs_dir = os.path.join(workspace_dir, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        output_path = os.path.join(logs_dir, f"report_{run_id}.html")
        
    if strategy_name == "EMACrossoverStrategy":
        logger.info(f"Selecting EMACrossoverReport compiler for run: {run_id}")
        generator = EMACrossoverReport(run_id)
    else:
        logger.info(f"Selecting BaseReport compiler for run: {run_id}")
        generator = BaseReport(run_id)
        
    generator.generate_html_report(output_path)
    return output_path
