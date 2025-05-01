import logging
from pathlib import Path
import re

class IniController:
    def __init__(self):
        self.base_path = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts")
        self.timeframes = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1']
        self.symbols = [
            "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD", "CADCHF", "CADJPY",
            "CHFJPY", "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURNZD",
            "EURUSD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD", "GBPUSD",
            "NZDCAD", "NZDCHF", "NZDJPY", "NZDUSD", "USDCAD", "USDCHF", "USDJPY",
            "XAGUSD", "XAUUSD", "US30", "US100", "US500", "DE30", "UK100", "FR40",
            "AUS200", "STOXX50", "NL25", "ES35", "IT40", "JP225"
        ]
        
    def is_valid_ini_name(self, filename: str) -> bool:
        """Check if the ini filename follows the pattern: EANAME-Symbol-Timeframe.ini"""
        if not filename.endswith('.ini'):
            return False
            
        # Split the filename into parts
        parts = filename[:-4].split('-')  # Remove .ini and split by hyphen
        if len(parts) < 3:
            return False
            
        # Check if the last part is a valid timeframe
        if parts[-1] not in self.timeframes:
            return False
            
        # Check if the second-to-last part is a valid symbol
        if parts[-2] not in self.symbols:
            return False
            
        return True
        
    def clean_ini_files(self):
        """Delete all ini files that don't follow the naming convention."""
        total_deleted = 0
        total_valid = 0
        
        for batch_num in range(1, 61):
            batch_folder = self.base_path / f"Batch_{batch_num:04d}"
            if not batch_folder.exists():
                continue
                
            logging.info(f"Processing Batch_{batch_num:04d}")
            
            # Process each EA folder
            for ea_folder in batch_folder.iterdir():
                if not ea_folder.is_dir():
                    continue
                    
                ini_dir = ea_folder / "ini"
                if not ini_dir.exists():
                    continue
                    
                ea_name = ea_folder.name
                deleted_count = 0
                valid_count = 0
                
                # Check each ini file
                for ini_file in ini_dir.glob("*.ini"):
                    if not self.is_valid_ini_name(ini_file.name):
                        logging.warning(f"Deleting invalid ini file: {ini_file}")
                        ini_file.unlink()
                        deleted_count += 1
                    else:
                        valid_count += 1
                
                if deleted_count > 0:
                    logging.info(f"{ea_name}: Deleted {deleted_count} invalid ini files, {valid_count} valid files remain")
                
                total_deleted += deleted_count
                total_valid += valid_count
        
        logging.info(f"Cleanup complete. Deleted {total_deleted} invalid ini files. {total_valid} valid files remain.")
        return total_deleted, total_valid

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('ini_controller.log'),
            logging.StreamHandler()
        ]
    )
    
    controller = IniController()
    deleted, valid = controller.clean_ini_files()
    
    # Run the analyzer after cleanup
    import subprocess
    logging.info("Running ini_analyzer.py...")
    subprocess.run(["python", "ini_analyzer.py"])

if __name__ == "__main__":
    main()
