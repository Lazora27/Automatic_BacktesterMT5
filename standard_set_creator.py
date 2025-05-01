import os
from pathlib import Path
import logging
import re
import codecs

class StandardSetCreator:
    def __init__(self):
        # MT5 Pfade
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5")
        self.experts_path = self.mt5_base / "Experts"
        self.target_path = self.mt5_base / "Profiles" / "Tester"
        
        # Logger setup
        self.logger = self._setup_logger()

    def _setup_logger(self):
        logger = logging.getLogger('StandardSetCreator')
        logger.setLevel(logging.INFO)
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        return logger

    def read_file_with_encoding(self, file_path: Path) -> str:
        """Liest eine Datei mit verschiedenen Kodierungen."""
        encodings = ['utf-8', 'utf-16', 'utf-16le', 'utf-16be', 'ascii', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with codecs.open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                self.logger.error(f"❌ Fehler beim Lesen von {file_path} mit {encoding}: {e}")
                continue
        
        raise UnicodeDecodeError(f"Konnte {file_path} mit keiner Kodierung lesen")

    def extract_inputs_from_mq5(self, mq5_path: Path) -> list:
        """Extrahiert Input-Parameter aus einer .mq5 Datei."""
        inputs = []
        try:
            # Versuche verschiedene Kodierungen
            content = self.read_file_with_encoding(mq5_path)
                
            # Finde alle input Deklarationen
            input_pattern = r'input\s+\w+\s+(\w+)\s*=\s*([^;]+)'
            matches = re.finditer(input_pattern, content)
            
            for match in matches:
                param, value = match.groups()
                value = value.strip()
                inputs.append(f"{param}={value}")
                
            return inputs
            
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Lesen von {mq5_path}: {e}")
            return []

    def create_standard_set(self, mq5_path: Path):
        """Erstellt eine Standard-Set-Datei basierend auf den Input-Parametern."""
        try:
            ea_name = mq5_path.stem
            
            # Extrahiere Input-Parameter
            inputs = self.extract_inputs_from_mq5(mq5_path)
            if not inputs:
                self.logger.warning(f"⚠️ Keine Inputs gefunden in: {ea_name}")
                return False
                
            # Erstelle .set Datei
            set_file = self.target_path / f"{ea_name}_01_standard.set"
            
            # Schreibe .set Datei mit UTF-16 LE BOM
            with codecs.open(set_file, 'w', encoding='utf-16') as f:
                for input_line in inputs:
                    f.write(input_line + '\n')
            
            self.logger.info(f"✅ Standard-Set erstellt für: {ea_name}")
            return True
                
        except Exception as e:
            self.logger.error(f"❌ Fehler beim Erstellen der Set-Datei für {ea_name}: {e}")
            return False

    def process_all_eas(self):
        """Verarbeitet alle EAs in allen Batch-Ordnern."""
        total_eas = 0
        successful_sets = 0
        
        # Durchsuche alle Batch-Ordner
        for batch_dir in self.experts_path.glob("Batch_*"):
            if batch_dir.is_dir():
                self.logger.info(f"\n🔍 Verarbeite Batch: {batch_dir.name}")
                
                # Verarbeite alle .mq5 Dateien im Batch
                for ea_file in batch_dir.glob("**/*.mq5"):
                    total_eas += 1
                    if self.create_standard_set(ea_file):
                        successful_sets += 1

        # Statistik ausgeben
        self.logger.info(f"\n📊 Statistik:")
        self.logger.info(f"   Gefundene EAs: {total_eas}")
        self.logger.info(f"   Erfolgreich erstellte Sets: {successful_sets}")
        self.logger.info(f"   Fehlgeschlagene Sets: {total_eas - successful_sets}")

def main():
    creator = StandardSetCreator()
    creator.process_all_eas()

if __name__ == "__main__":
    main()
