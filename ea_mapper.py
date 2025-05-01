from pathlib import Path
import json
import logging
from typing import Dict, List

class EAMapper:
    def __init__(self):
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C")
        self.experts_path = self.mt5_base / "MQL5" / "Experts"
        self.set_files_path = self.mt5_base / "MQL5" / "Profiles" / "Tester" / "optimized"
        self.mapping_file = Path("ea_batch_mapping.json")
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        
    def normalize_ea_name(self, name: str) -> str:
        """Normalize EA name by removing common suffixes and standardizing format."""
        # Remove version numbers and common suffixes
        name = name.replace('-MT5', '')
        name = name.replace('_MT5', '')
        name = name.replace('_v1.00', '')
        name = name.replace('_v2', '')
        
        # Replace underscores with spaces
        name = name.replace('_', ' ')
        
        # Remove extra spaces
        name = ' '.join(name.split())
        
        return name

    def get_ea_names_from_set_files(self) -> List[str]:
        """Extract EA names from .set files."""
        ea_names = set()
        for set_file in self.set_files_path.glob("*.set"):
            if "_01_standard_opt" in set_file.stem:
                # Extract EA name (everything before _01_standard_opt)
                ea_name = set_file.stem.split("_01_standard_opt")[0]
                normalized_name = self.normalize_ea_name(ea_name)
                ea_names.add(normalized_name)
                logging.debug(f"Found EA: {normalized_name} (from {set_file.name})")
        return list(ea_names)
    
    def find_ea_locations(self) -> Dict[str, List[str]]:
        """Find which batches contain each EA."""
        ea_locations = {}
        ea_names = self.get_ea_names_from_set_files()
        
        logging.info(f"Found {len(ea_names)} unique EAs in .set files")
        
        # Search through all batch folders
        for batch_num in range(1, 61):
            batch_dir = self.experts_path / f"Batch_{str(batch_num).zfill(4)}"
            if not batch_dir.exists():
                continue
                
            # Check each EA
            for ea_name in ea_names:
                # Try both normalized and original name formats
                possible_names = [
                    ea_name,
                    ea_name.replace(' ', '_'),
                    ea_name.replace(' ', '-')
                ]
                
                for name in possible_names:
                    ea_dir = batch_dir / name
                    if ea_dir.exists():
                        if ea_name not in ea_locations:
                            ea_locations[ea_name] = []
                        if f"Batch_{str(batch_num).zfill(4)}" not in ea_locations[ea_name]:
                            ea_locations[ea_name].append(f"Batch_{str(batch_num).zfill(4)}")
                        break
        
        return ea_locations
    
    def create_mapping(self):
        """Create and save the EA to batch mapping."""
        ea_locations = self.find_ea_locations()
        
        # Save mapping to file
        with open(self.mapping_file, 'w') as f:
            json.dump(ea_locations, f, indent=2)
        
        # Print summary
        logging.info(f"Mapping saved to {self.mapping_file}")
        for ea_name, batches in ea_locations.items():
            logging.info(f"{ea_name}: Found in {len(batches)} batches - {', '.join(batches)}")

if __name__ == "__main__":
    mapper = EAMapper()
    mapper.create_mapping()
