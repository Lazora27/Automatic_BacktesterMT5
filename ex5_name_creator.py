import os
from pathlib import Path
import re
import shutil
import logging

class Ex5NameCleaner:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mt5_experts = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5\Experts")
        self.name_mapping = {}  # Original name -> New name mapping

    def clean_name(self, name: str) -> str:
        """Bereinigt den Namen von Sonderzeichen und ersetzt Leerzeichen/Unterstriche durch Bindestriche."""
        # Entferne die .ex5 Erweiterung wenn vorhanden
        name = os.path.splitext(name)[0]
        
        # Ersetze Leerzeichen und Unterstriche durch Bindestriche
        name = name.replace(" ", "-").replace("_", "-")
        
        # Entferne alle Sonderzeichen außer Bindestriche
        name = re.sub(r'[^a-zA-Z0-9\-]', '', name)
        
        # Reduziere mehrfache Bindestriche auf einen
        name = re.sub(r'-+', '-', name)
        
        # Entferne führende und nachfolgende Bindestriche
        name = name.strip('-')
        
        return name + ".ex5"

    def process_experts_directory(self):
        """Verarbeitet alle .ex5 Dateien im MT5 Experts-Ordner."""
        if not self.mt5_experts.exists():
            self.logger.error(f"MT5 Experts directory not found: {self.mt5_experts}")
            return
            
        self.logger.info(f"Processing MT5 Experts directory: {self.mt5_experts}")
        
        # Erstelle temporären Ordner für die Originaldateien
        temp_dir = self.mt5_experts / "original_files"
        temp_dir.mkdir(exist_ok=True)
        
        # Verarbeite alle .ex5 Dateien
        for ea_path in self.mt5_experts.glob("*.ex5"):
            if ea_path.parent == temp_dir:  # Überspringe Dateien im temp_dir
                continue
                
            original_name = ea_path.name
            new_name = self.clean_name(original_name)
            
            if original_name != new_name:
                self.logger.info(f"Renaming {original_name} -> {new_name}")
                
                # Sichere Original in temp_dir
                shutil.copy2(ea_path, temp_dir / original_name)
                
                # Benenne die Datei um
                new_path = ea_path.parent / new_name
                try:
                    if new_path.exists():
                        self.logger.warning(f"Target file already exists: {new_path}")
                        continue
                    
                    ea_path.rename(new_path)
                    self.name_mapping[original_name] = new_name
                except Exception as e:
                    self.logger.error(f"Error renaming {original_name}: {str(e)}")
        
        # Speichere die Namenszuordnung
        self.save_name_mapping()

    def save_name_mapping(self):
        """Speichert die Namenszuordnung in einer JSON-Datei."""
        import json
        
        mapping_file = Path("ea_name_mapping.json")
        with open(mapping_file, 'w') as f:
            json.dump(self.name_mapping, f, indent=2)
        
        self.logger.info(f"Saved name mapping to {mapping_file}")

def main():
    # Konfiguriere Logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('ex5_name_creator.log'),
            logging.StreamHandler()
        ]
    )
    
    cleaner = Ex5NameCleaner()
    cleaner.process_experts_directory()

if __name__ == "__main__":
    main()