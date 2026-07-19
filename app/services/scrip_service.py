import os
import shutil
import logging
import pandas as pd
from threading import RLock
from config import get_config

logger = logging.getLogger(__name__)

class ScripService:
    # Service for loading and querying Kotak Neo Scrip Master CSV files. Resolves trading symbols to instrument tokens and vice versa.
    
    _instance = None
    _lock = RLock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        self.config = get_config()
        self.scrip_dir = self.config.SCRIP_DIR
        self.df_cache = None
        self.symbol_to_token = {}
        self.token_to_symbol = {} # (token, segment) -> symbol
        self.lot_sizes = {} # symbol -> lot_size
        
        # Check and load scrip master data
        self.ensure_scrip_files()
        self.load_scrip_master()
        self._initialized = True

    def ensure_scrip_files(self):
        # Ensures the scrip files exist, copying them from parent workspace if necessary
        os.makedirs(self.scrip_dir, exist_ok=True)
        
        for segment in ['nse_fo', 'nse_cm']:
            csv_name = f"{segment}.csv"
            local_path = os.path.join(self.scrip_dir, csv_name)
            
            if not os.path.exists(local_path) or os.path.getsize(local_path) < 100000:
                # Attempt to find the scrip master file in the parent workspace's data folder
                parent_data_dir = os.path.abspath(os.path.join(self.config.BASE_DIR, "data"))
                parent_path = os.path.join(parent_data_dir, csv_name)
                
                if os.path.exists(parent_path):
                    logger.info(f"Copying pre-existing scrip file {csv_name} from parent folder...")
                    try:
                        shutil.copy(parent_path, local_path)
                    except Exception as e:
                        logger.error(f"Failed to copy scrip master from parent: {e}")
                else:
                    logger.warning(f"Scrip file {csv_name} is missing and could not be found at {parent_path}.")

    def load_scrip_master(self):
        # Loads scrip master files into memory for fast lookup
        dfs = []
        for segment in ['nse_fo', 'nse_cm']:
            csv_name = f"{segment}.csv"
            local_path = os.path.join(self.scrip_dir, csv_name)
            
            if os.path.exists(local_path):
                try:
                    logger.info(f"Loading scrip master CSV: {local_path}")
                    # Only read columns we care about to keep memory low
                    cols = ['pSymbol', 'pExchSeg', 'pTrdSymbol', 'lLotSize']
                    # Verify cols exist first by checking first row
                    header_df = pd.read_csv(local_path, nrows=1)
                    actual_cols = [c for c in cols if c in header_df.columns]
                    
                    df = pd.read_csv(local_path, usecols=actual_cols)
                    dfs.append(df)
                except Exception as e:
                    logger.error(f"Failed to load {local_path}: {e}")
                    
        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            self.df_cache = combined
            
            # Build fast lookup indexes
            for _, row in combined.iterrows():
                symbol = row.get('pTrdSymbol')
                token = str(row.get('pSymbol'))
                segment = row.get('pExchSeg')
                lot_size = row.get('lLotSize')
                
                if symbol and token and segment:
                    self.symbol_to_token[symbol] = {
                        'instrument_token': token,
                        'exchange_segment': segment
                    }
                    self.token_to_symbol[(token, segment)] = symbol
                    
                if symbol and lot_size is not None:
                    try:
                        self.lot_sizes[symbol] = int(lot_size)
                    except ValueError:
                        pass
                        
            logger.info(f"Scrip master loaded successfully: {len(self.symbol_to_token)} symbols indexed.")
        else:
            logger.error("No scrip master files could be loaded.")

    def resolve_symbol_to_token(self, symbol: str) -> dict:
        # Resolves symbol string to token and exchange segment dict
        return self.symbol_to_token.get(symbol)

    def resolve_token_to_symbol(self, token: str, segment: str) -> str:
        # Resolves token and segment back to symbol string
        return self.token_to_symbol.get((str(token), segment))

    def get_lot_size(self, symbol: str, default: int = 50) -> int:
        # Retrieves lot size for a symbol
        return self.lot_sizes.get(symbol, default)
