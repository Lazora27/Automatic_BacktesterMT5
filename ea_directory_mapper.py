import os
import json
from pathlib import Path
from typing import Dict, List

class EADirectoryMapper:
    def __init__(self):
        self.mt5_ea_path = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts")
        self.ea_mapping: Dict[str, dict] = {}

    def scan_ea_directories(self) -> None:
        """Scan the MT5 Experts directory for EA folders and their ini directories."""
        if not self.mt5_ea_path.exists():
            raise FileNotFoundError(f"MT5 Experts directory not found at: {self.mt5_ea_path}")

        for item in self.mt5_ea_path.rglob("*"):
            if item.is_dir():
                ini_dir = item / "ini"
                if ini_dir.exists():
                    ea_name = item.name
                    self.ea_mapping[ea_name] = {
                        "path": str(item),
                        "ini_dir": str(ini_dir)
                    }

    def create_ini_directories(self) -> None:
        """Ensure ini directories exist for all EAs."""
        for ea_info in self.ea_mapping.values():
            ini_dir = Path(ea_info["ini_dir"])
            ini_dir.mkdir(exist_ok=True)

    def save_mapping(self, output_file: str = "ea_directory_mapping.json") -> None:
        """Save the EA directory mapping to a JSON file."""
        with open(output_file, 'w') as f:
            json.dump(self.ea_mapping, f, indent=4)

    def get_ini_path(self, ea_name: str, symbol: str, timeframe: str) -> str:
        """Get the full path for an INI file based on EA name, symbol, and timeframe."""
        if ea_name not in self.ea_mapping:
            raise KeyError(f"EA '{ea_name}' not found in mapping")
        
        ini_filename = f"{ea_name}_{symbol}_{timeframe}.ini"
        return str(Path(self.ea_mapping[ea_name]["ini_dir"]) / ini_filename)

def main():
    mapper = EADirectoryMapper()
    mapper.scan_ea_directories()
    mapper.create_ini_directories()
    mapper.save_mapping()
    
    print("EA Directory Mapping completed!")
    print(f"Found {len(mapper.ea_mapping)} EAs with ini directories")
    print("\nEA Mapping:")
    for ea_name, info in mapper.ea_mapping.items():
        print(f"\n{ea_name}:")
        print(f"  Path: {info['path']}")
        print(f"  INI Directory: {info['ini_dir']}")

if __name__ == "__main__":
    main()
