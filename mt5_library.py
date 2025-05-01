import os
from pathlib import Path
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
import json

@dataclass
class MT5Item:
    """Repräsentiert ein MT5-Item mit allen relevanten Pfaden."""
    name: str  # Name des EAs ohne Suffixe
    ea_dir: Path  # Verzeichnis des EAs
    ini_dir: Path  # Verzeichnis der INI-Dateien
    opt_set_file: Path  # Optimiertes SET-File
    batch_dir: Optional[Path] = None  # Optional: Batch-Verzeichnis

class MT5Library:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.mt5_base = Path(os.getenv('APPDATA')) / 'MetaQuotes' / 'Terminal' / '4B1CE69F577705455263BD980C39A82C'
        self.experts_path = self.mt5_base / 'MQL5' / 'Experts'
        self.tester_path = self.mt5_base / 'MQL5' / 'Profiles' / 'Tester'
        self.optimized_path = self.tester_path / 'optimized'
        
        # Bibliothek der MT5-Items
        self.items: Dict[str, MT5Item] = {}
        
        # Cache für optimierte .set Files
        self._opt_set_files: Dict[str, Path] = {}
        
        # Initialisiere die Bibliothek
        self._scan_optimized_files()
        self._scan_ea_directories()
        
    def _scan_optimized_files(self):
        """Scannt alle optimierten .set Files."""
        self.logger.info("Scanne optimierte .set Files...")
        
        if not self.optimized_path.exists():
            self.logger.warning(f"Optimiertes Verzeichnis nicht gefunden: {self.optimized_path}")
            return
            
        for set_file in self.optimized_path.glob('*_01_opt.set'):
            ea_name = set_file.stem.split('_')[0]  # Entferne _01_opt
            self._opt_set_files[ea_name] = set_file
            
        self.logger.info(f"Gefunden: {len(self._opt_set_files)} optimierte .set Files")
        
    def _scan_ea_directories(self):
        """Scannt alle EA-Verzeichnisse in allen Batch-Ordnern."""
        self.logger.info("Scanne EA-Verzeichnisse...")
        
        for batch_dir in self.experts_path.glob('Batch_*'):
            if not batch_dir.is_dir():
                continue
                
            for ea_dir in batch_dir.iterdir():
                if not ea_dir.is_dir():
                    continue
                    
                ea_name = ea_dir.name
                ini_dir = ea_dir / 'ini'
                
                # Prüfe ob ein optimiertes .set File existiert
                if ea_name in self._opt_set_files:
                    self.items[ea_name] = MT5Item(
                        name=ea_name,
                        ea_dir=ea_dir,
                        ini_dir=ini_dir,
                        opt_set_file=self._opt_set_files[ea_name],
                        batch_dir=batch_dir
                    )
                    
        self.logger.info(f"Gefunden: {len(self.items)} EA-Verzeichnisse mit optimierten .set Files")
        
    def get_item(self, ea_name: str) -> Optional[MT5Item]:
        """Holt ein MT5-Item anhand des EA-Namens."""
        return self.items.get(ea_name)
        
    def get_all_items(self) -> List[MT5Item]:
        """Gibt alle MT5-Items zurück."""
        return list(self.items.values())
        
    def get_opt_set_content(self, ea_name: str) -> Optional[str]:
        """Liest den Inhalt einer optimierten .set Datei."""
        item = self.get_item(ea_name)
        if not item or not item.opt_set_file.exists():
            return None
            
        try:
            with open(item.opt_set_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            self.logger.error(f"Fehler beim Lesen von {item.opt_set_file}: {str(e)}")
            return None
            
    def save_to_json(self, output_file: Path):
        """Speichert die Bibliothek als JSON."""
        data = {
            name: {
                'name': item.name,
                'ea_dir': str(item.ea_dir),
                'ini_dir': str(item.ini_dir),
                'opt_set_file': str(item.opt_set_file),
                'batch_dir': str(item.batch_dir) if item.batch_dir else None
            }
            for name, item in self.items.items()
        }
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.logger.info(f"Bibliothek gespeichert in: {output_file}")
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Bibliothek: {str(e)}")
            
    @classmethod
    def load_from_json(cls, input_file: Path) -> 'MT5Library':
        """Lädt die Bibliothek aus einer JSON-Datei."""
        library = cls()
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for name, item_data in data.items():
                library.items[name] = MT5Item(
                    name=item_data['name'],
                    ea_dir=Path(item_data['ea_dir']),
                    ini_dir=Path(item_data['ini_dir']),
                    opt_set_file=Path(item_data['opt_set_file']),
                    batch_dir=Path(item_data['batch_dir']) if item_data['batch_dir'] else None
                )
                
            library.logger.info(f"Bibliothek geladen aus: {input_file}")
            return library
        except Exception as e:
            library.logger.error(f"Fehler beim Laden der Bibliothek: {str(e)}")
            return library

def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('mt5_library.log', mode='w'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Erstelle und scanne die Bibliothek
        library = MT5Library()
        
        # Speichere die Bibliothek
        output_file = Path(__file__).parent / 'mt5_library.json'
        library.save_to_json(output_file)
        
        # Zeige einige Statistiken
        items = library.get_all_items()
        logger.info(f"\nBibliotheksstatistik:")
        logger.info(f"Gefundene EAs: {len(items)}")
        
        # Zeige die ersten 3 Items als Beispiel
        if items:
            logger.info("\nBeispiel-Items:")
            for item in items[:3]:
                logger.info(f"\nEA: {item.name}")
                logger.info(f"EA-Dir: {item.ea_dir}")
                logger.info(f"INI-Dir: {item.ini_dir}")
                logger.info(f"OPT-Set: {item.opt_set_file}")
                logger.info(f"Batch: {item.batch_dir}")
                
    except Exception as e:
        logger.error(f"Kritischer Fehler: {str(e)}")

if __name__ == "__main__":
    main()
