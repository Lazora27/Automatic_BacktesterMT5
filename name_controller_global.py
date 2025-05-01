import os
from pathlib import Path
import re
import shutil
import logging
from typing import Dict

class NameControllerGlobal:
    def __init__(self):
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5")
        self.experts_path = self.mt5_base / "Experts"
        self.tester_path = self.mt5_base / "Profiles" / "Tester"
        self.optimized_path = self.tester_path / "optimized"
        self.timeframes = {
            "M5": 5,
            "M15": 15,
            "M30": 30,
            "H1": 60,
            "H4": 240,
            "D1": 1440
        }
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('name_controller.log'),
                logging.StreamHandler()
            ]
        )
        
    def get_unique_folder_name(self, parent_path: Path, base_name: str) -> str:
        """Generate a unique folder name by adding a number suffix if needed."""
        if not (parent_path / base_name).exists():
            return base_name
            
        counter = 1
        while (parent_path / f"{base_name}-{counter}").exists():
            counter += 1
        return f"{base_name}-{counter}"

    def sanitize_ea_name(self, name: str) -> str:
        """Sanitize EA name by removing special characters and standardizing format."""
        # Keep version numbers but standardize format
        name = re.sub(r'\s*[vV](\d+(\.\d+)*)\s*', r'-v\1', name)
        
        # Remove special characters and replace with hyphen
        name = re.sub(r'[@!+/\[\]{}()\\#$%^&*=~`<>?|]', '-', name)
        
        # Replace spaces and underscores with hyphens
        name = re.sub(r'[\s_]+', '-', name)
        
        # Clean up multiple hyphens and trim
        name = re.sub(r'-+', '-', name).strip('-')
        
        # Handle MT4/MT5 references
        name = re.sub(r'-?MT[45]', '', name, flags=re.IGNORECASE)
        
        return name or "Unnamed-EA"

    def process_ea_folder(self, ea_folder: Path) -> None:
        """Process a single EA folder and its contents."""
        try:
            old_name = ea_folder.name
            base_new_name = self.sanitize_ea_name(old_name)
            
            # Get a unique name for the folder
            new_name = self.get_unique_folder_name(ea_folder.parent, base_new_name)
            
            if old_name != new_name:
                # Create new folder path
                new_folder = ea_folder.parent / new_name
                
                # Create temporary folder for moving files
                temp_folder = ea_folder.parent / f"temp_{new_name}"
                temp_folder.mkdir(exist_ok=True)
                
                # Move all files to temp folder first
                for item in ea_folder.rglob('*'):
                    if item.is_file():
                        # Create relative path to maintain directory structure
                        rel_path = item.relative_to(ea_folder)
                        new_path = temp_folder / rel_path
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        item.rename(new_path)
                
                # Now rename the empty EA folder
                ea_folder.rmdir()  # Remove old empty folder
                new_folder.mkdir()  # Create new folder
                
                # Move files back from temp to new folder
                for item in temp_folder.rglob('*'):
                    if item.is_file():
                        # Replace old name with new name in filename
                        rel_path = item.relative_to(temp_folder)
                        new_filename = str(rel_path).replace(old_name, new_name)
                        new_path = new_folder / new_filename
                        new_path.parent.mkdir(parents=True, exist_ok=True)
                        item.rename(new_path)
                
                # Remove temp folder
                temp_folder.rmdir()
                
                # Create empty .bat file
                bat_file = new_folder / f"{new_name}-auto.bat"
                if not bat_file.exists():
                    bat_file.touch()
                    logging.info(f"Created empty bat file: {bat_file.name}")
                
                logging.info(f"Renamed EA folder and contents: {old_name} -> {new_name}")
                
        except Exception as e:
            logging.error(f"Error processing {ea_folder.name}: {str(e)}")

    def process_all_batches(self) -> None:
        """Process all batch folders and rename EAs according to the unified logic."""
        name_changes: Dict[str, str] = {}
        
        # First pass: collect all name changes
        for batch_num in range(1, 61):
            batch_folder = self.experts_path / f"Batch_{batch_num:04d}"
            if not batch_folder.exists():
                continue
                
            for ea_folder in batch_folder.iterdir():
                if not ea_folder.is_dir():
                    continue
                    
                old_name = ea_folder.name
                new_name = self.sanitize_ea_name(old_name)
                if old_name != new_name:
                    name_changes[old_name] = new_name
                    logging.info(f"Will rename EA: {old_name} -> {new_name}")
        
        # Second pass: apply all changes
        for batch_num in range(1, 61):
            batch_folder = self.experts_path / f"Batch_{batch_num:04d}"
            if not batch_folder.exists():
                continue
                
            for ea_folder in batch_folder.iterdir():
                if not ea_folder.is_dir():
                    continue
                    
                old_name = ea_folder.name
                if old_name in name_changes:
                    new_name = name_changes[old_name]
                    self.process_ea_folder(ea_folder)

def main():
    controller = NameControllerGlobal()
    controller.process_all_batches()
    logging.info("Name standardization complete!")

if __name__ == "__main__":
    main()
