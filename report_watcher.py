import os
import shutil
import time
import json
from datetime import datetime
from typing import Dict, Set, Optional, List
from pathlib import Path

class ReportWatcher:
    def __init__(self):
        # Base MT5 path
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C")
        
        # Report source paths
        self.report_sources = [
            self.mt5_base / "Reports",  # Main reports folder
            self.mt5_base / "MQL5" / "Experts"  # Base for batch folders
        ]
        
        # Core paths
        self.ini_folder = Path(r"C:\Users\nikol\Desktop\#3 Test Good")
        self.base_output_folder = Path(r"C:\Users\nikol\Desktop\#3 Test Good")
        
        # Batch folders to monitor (0001 to 0060)
        self.batch_folders = [f"Batch_{str(i).zfill(4)}" for i in range(1, 61)]
        
        # Tracking
        self.processed_files: Set[str] = set()
        self.failed_tests: Dict[str, str] = {}  # key: EA_Symbol_TF, value: reason
        self.check_interval = 5  # seconds
        
        # Create log directory
        self.log_dir = self.base_output_folder / "Logs"
        self.log_dir.mkdir(exist_ok=True)
        
        # Initialize log file
        self.log_file = self.log_dir / f"backtest_failures_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
        
    def get_all_report_paths(self) -> List[Path]:
        """Get all paths that need to be monitored for reports."""
        paths = []
        
        # Add main reports folder
        paths.append(self.report_sources[0])
        
        # Add all batch report folders
        experts_path = self.report_sources[1]
        for batch in self.batch_folders:
            batch_path = experts_path / batch
            if batch_path.exists():
                # Look for EA folders in this batch
                for ea_dir in batch_path.iterdir():
                    if ea_dir.is_dir():
                        report_dir = ea_dir / "Reports"
                        if report_dir.exists():
                            paths.append(report_dir)
        
        return paths
        
    def process_report(self, file_path: Path, source_type: str) -> bool:
        """Process a single report file."""
        try:
            filename = file_path.name
            ea, symbol, tf = self.extract_info_from_filename(filename)
            
            if not all([ea, symbol, tf]):
                self.log_failure("Unknown", "Unknown", "Unknown", f"Could not parse filename: {filename}")
                return False
            
            # Create target directories and copy to both locations
            
            # 1. Desktop location
            desktop_dir = self.base_output_folder / ea / "Reports" / symbol / tf
            desktop_dir.mkdir(parents=True, exist_ok=True)
            
            # 2. Batch location (if from main Reports folder)
            if source_type == "main":
                # Find appropriate batch folder
                for batch in self.batch_folders:
                    batch_dir = self.report_sources[1] / batch / ea / "Reports" / symbol / tf
                    if batch_dir.exists() or not any(b.exists() for b in [self.report_sources[1] / x / ea for x in self.batch_folders]):
                        batch_dir.mkdir(parents=True, exist_ok=True)
                        break
            
            # Generate new filename with timestamp
            now = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_filename = f"{ea}_{symbol}_{tf}_Report_{now}{file_path.suffix}"
            
            # Copy/move files
            if source_type == "main":
                # Copy to both locations
                shutil.copy2(str(file_path), str(desktop_dir / new_filename))
                if 'batch_dir' in locals():
                    shutil.move(str(file_path), str(batch_dir / new_filename))
            else:
                # Copy to desktop, keep in batch
                shutil.copy2(str(file_path), str(desktop_dir / new_filename))
            
            # Mark as successful
            key = f"{ea}_{symbol}_{tf}"
            if key in self.failed_tests:
                del self.failed_tests[key]
            
            print(f"✅ Processed: {filename} → {new_filename}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing {file_path}: {str(e)}")
            if ea and symbol and tf:
                self.log_failure(ea, symbol, tf, str(e))
            return False
    
    def log_failure(self, ea: str, symbol: str, timeframe: str, reason: str):
        """Log a failed backtest attempt."""
        key = f"{ea}_{symbol}_{timeframe}"
        self.failed_tests[key] = reason
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] FAILED: {key} - Reason: {reason}\n")
            
    def extract_info_from_filename(self, filename: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract EA, Symbol and Timeframe from filename."""
        try:
            name = Path(filename).stem
            parts = name.split("_")
            
            # Handle different filename formats
            if len(parts) >= 2:
                symbol = next((p for p in parts if p in self.get_valid_symbols()), None)
                timeframe = next((p for p in parts if p in self.get_valid_timeframes()), None)
                
                if symbol and timeframe:
                    # Find EA name from ini files
                    ea = self.find_ea_name(symbol, timeframe)
                    return ea, symbol, timeframe
                    
            return None, None, None
            
        except Exception as e:
            print(f"Error parsing filename {filename}: {str(e)}")
            return None, None, None
            
    def get_valid_symbols(self) -> set[str]:
        """Get set of valid symbols."""
        return {
            "EURUSD", "GBPUSD", "USDCHF", "USDJPY", "USDCAD", "AUDUSD", "AUDNZD", 
            "AUDCAD", "AUDCHF", "AUDJPY", "NZDUSD", "NZDCAD", "EURCAD", "CADJPY",
            "EURJPY", "EURGBP", "EURCHF", "EURAUD", "EURNZD", "GBPCHF", "GBPJPY",
            "GBPAUD", "GBPCAD", "EURNOK", "NOKSEK", "XBRUSD", "XNGUSD", "XTIUSD",
            "XAUUSD", "XAGUSD", "STOXX50", "F40", "JP225", "AUS200", "UK100",
            "US30", "DE40", "US500", "USTEC", "CA60", "USDSEK", "USDNOK"
        }
        
    def get_valid_timeframes(self) -> set[str]:
        """Get set of valid timeframes."""
        return {"M5", "M15", "M30", "H1", "H4", "D1"}
        
    def find_ea_name(self, symbol: str, timeframe: str) -> str:
        """Find EA name from ini files."""
        try:
            # Search in all EA folders
            for ea_dir in self.ini_folder.iterdir():
                if ea_dir.is_dir():
                    ini_dir = ea_dir / "ini"
                    if ini_dir.exists():
                        for ini_file in ini_dir.glob("*.ini"):
                            if symbol in ini_file.name and timeframe in ini_file.name:
                                return ini_file.name.split("_")[0]
        except Exception as e:
            print(f"Error finding EA name: {str(e)}")
            
        return "UnknownEA"
        
    def watch(self):
        """Main watch loop."""
        print("🔍 Report Watcher started. Press Ctrl+C to exit.")
        print(f"📝 Logging failures to: {self.log_file}")
        
        try:
            while True:
                # Get all paths to monitor
                report_paths = self.get_all_report_paths()
                
                for report_path in report_paths:
                    source_type = "main" if report_path == self.report_sources[0] else "batch"
                    
                    for file in report_path.glob("*"):
                        if file.suffix.lower() in {".xml", ".html", ".csv", ".png"}:
                            file_id = f"{file.parent}_{file.name}"  # Include path in ID to handle duplicates
                            if file_id not in self.processed_files:
                                if self.process_report(file, source_type):
                                    self.processed_files.add(file_id)
                
                # Write current status
                self.write_status()
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            self.write_status()
            
    def write_status(self):
        """Write current status to JSON file."""
        status = {
            "last_update": datetime.now().isoformat(),
            "processed_files": len(self.processed_files),
            "failed_tests": self.failed_tests
        }
        
        status_file = self.log_dir / "watcher_status.json"
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)

if __name__ == "__main__":
    watcher = ReportWatcher()
    watcher.watch()
