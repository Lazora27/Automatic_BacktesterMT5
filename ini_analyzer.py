import logging
from pathlib import Path
from typing import Dict, List, Tuple
import json
from datetime import datetime

class IniAnalyzer:
    def __init__(self):
        self.base_path = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts")
        self.set_path = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Profiles\Tester\optimized")
        self.expected_ini_count = 252  # 42 symbols × 6 timeframes
        self.results: Dict[str, Dict] = {}
        self.total_success = 0
        self.total_failed = 0
        self.total_eas = 0
        
    def check_set_file_exists(self, ea_name: str) -> Tuple[bool, str]:
        """Check if .set file exists for the EA and return reason if not found."""
        patterns = [
            f"{ea_name}_01*.set",
            f"{ea_name.replace(' ', '_')}_01*.set",
            f"{ea_name.replace('@', '_')}_01*.set",
            f"{ea_name.replace('%20', ' ')}_01*.set"
        ]
        
        for pattern in patterns:
            if list(self.set_path.glob(pattern)):
                return True, "Set file found"
        
        return False, "No matching .set file found"
        
    def analyze_batch(self, batch_num: int) -> None:
        """Analyze a specific batch folder."""
        batch_folder = self.base_path / f"Batch_{batch_num:04d}"
        if not batch_folder.exists():
            return
            
        batch_results = {}
        
        # Process each EA folder
        for ea_folder in batch_folder.iterdir():
            if not ea_folder.is_dir():
                continue
                
            ea_name = ea_folder.name
            ini_dir = ea_folder / "ini"
            
            # Check for potential issues
            issues = []
            
            # Check if ini directory exists
            if not ini_dir.exists():
                batch_results[ea_name] = {
                    "count": 0,
                    "status": "failed",
                    "reason": "No ini directory"
                }
                self.total_failed += 1
                continue
            
            # Check if .set file exists
            has_set, set_reason = self.check_set_file_exists(ea_name)
            if not has_set:
                issues.append(set_reason)
            
            # Count .ini files
            ini_files = list(ini_dir.glob("*.ini"))
            ini_count = len(ini_files)
            
            # Analyze potential issues
            if ini_count < self.expected_ini_count:
                if '@' in ea_name:
                    issues.append("EA name contains '@' character")
                if '%20' in ea_name:
                    issues.append("EA name contains URL-encoded spaces")
                if '+' in ea_name:
                    issues.append("EA name contains '+' character")
                if not issues:
                    issues.append("Unknown reason for missing ini files")
            
            # Determine status
            if ini_count >= self.expected_ini_count:
                status = "success"
                self.total_success += 1
            else:
                status = "failed"
                self.total_failed += 1
            
            batch_results[ea_name] = {
                "count": ini_count,
                "status": status,
                "reason": " | ".join(issues) if issues else f"Found {ini_count}/{self.expected_ini_count} ini files"
            }
            
            self.total_eas += 1
        
        if batch_results:
            self.results[f"Batch_{batch_num:04d}"] = batch_results
    
    def analyze_all_batches(self) -> None:
        """Analyze all batches from 1 to 60."""
        for batch_num in range(1, 61):
            self.analyze_batch(batch_num)
    
    def generate_report(self) -> None:
        """Generate analysis report."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = Path(f"ini_analysis_{timestamp}.log")
        
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=== INI File Analysis Report ===\n\n")
            
            # Write detailed results for each batch
            for batch_name, batch_results in self.results.items():
                if not batch_results:  # Skip empty batches
                    continue
                    
                f.write(f"\n{batch_name}:\n")
                f.write("-" * (len(batch_name) + 1) + "\n")
                
                # Sort EAs by status (failed first) and then by name
                sorted_eas = sorted(
                    batch_results.items(),
                    key=lambda x: (x[1]["status"] != "failed", x[0])
                )
                
                for ea_name, info in sorted_eas:
                    if info["status"] == "failed":
                        f.write(f"❌ {ea_name}: {info['count']} ini files ({info['reason']})\n")
                    elif info["count"] > self.expected_ini_count:
                        f.write(f"⚠️ {ea_name}: {info['count']} ini files (more than expected)\n")
                    else:
                        f.write(f"✅ {ea_name}: {info['count']} ini files\n")
                
            # Write summary statistics
            f.write("\n=== Summary Statistics ===\n")
            f.write(f"Total EAs processed: {self.total_eas}\n")
            f.write(f"Successfully created (252 ini files): {self.total_success}\n")
            f.write(f"Failed to create 252 ini files: {self.total_failed}\n")
            
            success_rate = (self.total_success / self.total_eas * 100) if self.total_eas > 0 else 0
            f.write(f"Success rate: {success_rate:.2f}%\n")
            
            logging.info(f"Analysis report written to {log_file}")

def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    analyzer = IniAnalyzer()
    logging.info("Starting analysis of all batches...")
    analyzer.analyze_all_batches()
    analyzer.generate_report()
    logging.info("Analysis complete!")

if __name__ == "__main__":
    main()
