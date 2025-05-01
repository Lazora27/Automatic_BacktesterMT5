import os
from pathlib import Path
import logging
from datetime import datetime
import shutil

class IniDeleter:
    def __init__(self):
        self.logger = self._setup_logger()
        self.mt5_path = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts")
        
    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File Handler
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(
            log_dir / f"ini_deleter_{datetime.now():%Y%m%d_%H%M}.log"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
        
    def delete_ini_files(self, start_batch: int = 1, end_batch: int = 60):
        """Delete all INI files in EA directories."""
        try:
            deleted_count = 0
            
            # Process each batch
            for batch_num in range(start_batch, end_batch + 1):
                batch_dir = self.mt5_path / f"Batch_{batch_num:04d}"
                
                # Skip if batch directory doesn't exist
                if not batch_dir.exists():
                    continue
                    
                # Get all EA directories in this batch
                for ea_dir in batch_dir.iterdir():
                    if not ea_dir.is_dir() or ea_dir.name == "ini":
                        continue
                        
                    # Delete ini directory if it exists
                    ini_dir = ea_dir / "ini"
                    if ini_dir.exists():
                        try:
                            shutil.rmtree(ini_dir)
                            deleted_count += 1
                            self.logger.info(f"Deleted INI directory: {ini_dir}")
                        except Exception as e:
                            self.logger.error(f"Error deleting {ini_dir}: {str(e)}")
                            
            self.logger.info(f"Successfully deleted {deleted_count} INI directories")
            
        except Exception as e:
            self.logger.error(f"Error deleting INI files: {str(e)}")
            
def main():
    deleter = IniDeleter()
    deleter.delete_ini_files()
    
if __name__ == "__main__":
    main()
