import os
import logging
from pathlib import Path
from collections import defaultdict

class SetFileAnalyzer:
    def __init__(self):
        self.base_path = Path(os.getenv('APPDATA')) / 'MetaQuotes' / 'Terminal' / '4B1CE69F577705455263BD980C39A82C' / 'MQL5'
        self.experts_path = self.base_path / 'Experts'
        self.tester_path = self.base_path / 'Profiles' / 'Tester'
        self.logger = self._setup_logger()
        
    def _setup_logger(self):
        """Setup logging configuration."""
        log_file = 'setfiles_analysis.log'
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        return logging.getLogger(__name__)
        
    def get_all_eas(self):
        """Get all EA folders from Batch_0001 to Batch_0060."""
        ea_dict = {}
        for i in range(1, 61):
            batch_folder = self.experts_path / f"Batch_{i:04d}"
            if batch_folder.exists():
                for ea_folder in batch_folder.iterdir():
                    if ea_folder.is_dir():
                        ea_dict[ea_folder.name] = ea_folder
        return ea_dict
        
    def get_standard_setfiles(self):
        """Get all standard set files."""
        return {f.stem.replace('_01_standard', ''): f 
                for f in self.tester_path.glob('*_01_standard.set')}
        
    def analyze_missing_setfiles(self):
        """Analyze which EAs are missing standard set files."""
        eas = self.get_all_eas()
        setfiles = self.get_standard_setfiles()
        
        missing_setfiles = {}
        for ea_name, ea_path in eas.items():
            sanitized_name = ea_name.replace(' ', '-')  # Basic sanitization
            if sanitized_name not in setfiles:
                batch_name = ea_path.parent.name
                if batch_name not in missing_setfiles:
                    missing_setfiles[batch_name] = []
                missing_setfiles[batch_name].append(ea_name)
                
        return missing_setfiles
        
    def generate_report(self):
        """Generate a report of missing set files."""
        missing_setfiles = self.analyze_missing_setfiles()
        
        self.logger.info("=== Missing Set Files Analysis Report ===")
        total_missing = 0
        
        for batch, eas in sorted(missing_setfiles.items()):
            self.logger.info(f"\n{batch}:")
            for ea in sorted(eas):
                self.logger.info(f"  - {ea}")
                total_missing += 1
                
        self.logger.info(f"\nTotal EAs missing standard set files: {total_missing}")
        
def main():
    analyzer = SetFileAnalyzer()
    analyzer.generate_report()
    
if __name__ == '__main__':
    main()
