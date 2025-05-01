import os
from pathlib import Path
import logging
from datetime import datetime
import sys

class BatchBatCreator:
    def __init__(self):
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5")
        self.experts_path = self.mt5_base / "Experts"
        self.terminal_exe = Path(r"C:\Program Files\MetaTrader 5 IC Markets EU\terminal64.exe")
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Logger Setup"""
        logger = logging.getLogger("BatchBatCreator")
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        return logger

    def create_bat_content(self, batch_dir: Path) -> str:
        """Erstellt den Inhalt für die Batch .bat Datei"""
        # Sammle alle ini Verzeichnisse aus dem Batch
        ini_dirs = []
        for ea_dir in batch_dir.glob("**/ini"):
            if ea_dir.is_dir() and list(ea_dir.glob("*.ini")):
                ini_dirs.append(ea_dir)

        if not ini_dirs:
            self.logger.warning(f"Keine ini-Dateien gefunden in: {batch_dir}")
            return None

        bat_content = f'''@echo off
setlocal EnableDelayedExpansion

set "TERMINAL={self.terminal_exe}"
set "FAILED_COUNTER=0"
set "BATCH_NAME={batch_dir.name}"

echo Starte Tests für %BATCH_NAME%...
echo Timestamp: %DATE% %TIME% > "{batch_dir}\\batch_test_log.txt"

'''

        # Füge Verarbeitung für jedes ini-Verzeichnis hinzu
        for ini_dir in ini_dirs:
            ea_name = ini_dir.parent.name
            bat_content += f'''
echo.
echo Verarbeite EA: {ea_name}
echo [%DATE% %TIME%] Starting EA: {ea_name} >> "{batch_dir}\\batch_test_log.txt"

for %%F in ("{ini_dir}\\*.ini") do (
    set "CURRENT_INI=%%~nxF"
    echo Processing !CURRENT_INI! ...
    echo [%DATE% %TIME%] Testing {ea_name} - !CURRENT_INI! >> "{batch_dir}\\batch_test_log.txt"
    
    "%TERMINAL%" /config:"%%~fF"
    
    if errorlevel 1 (
        echo [%DATE% %TIME%] Error with {ea_name} - !CURRENT_INI! >> "{batch_dir}\\batch_test_log.txt"
        set /a FAILED_COUNTER+=1
        
        if !FAILED_COUNTER! GEQ 3 (
            echo Drei Tests in Folge fehlgeschlagen. Beende Batch...
            echo [%DATE% %TIME%] Aborted after 3 consecutive failures >> "{batch_dir}\\batch_test_log.txt"
            goto :end
        )
    ) else (
        set "FAILED_COUNTER=0"
        echo [%DATE% %TIME%] Successfully completed {ea_name} - !CURRENT_INI! >> "{batch_dir}\\batch_test_log.txt"
    )
    
    rem Warte bis MT5 vollständig beendet ist
    timeout /t 5 /nobreak
)
'''

        # Füge Ende hinzu
        bat_content += '''
:end
echo.
echo Tests abgeschlossen für %BATCH_NAME%.
echo [%DATE% %TIME%] All tests completed >> "{batch_dir}\\batch_test_log.txt"
pause
'''

        return bat_content

    def create_batch_bat(self, batch_number: str):
        """Erstellt eine .bat Datei für einen spezifischen Batch"""
        # Formatiere Batch-Nummer
        batch_dir_name = f"Batch_{batch_number.zfill(4)}"
        batch_dir = self.experts_path / batch_dir_name
        
        if not batch_dir.exists():
            self.logger.error(f"Batch-Verzeichnis nicht gefunden: {batch_dir_name}")
            return
            
        self.logger.info(f"\nVerarbeite Batch: {batch_dir_name}")
        
        # Erstelle bat-Datei
        bat_content = self.create_bat_content(batch_dir)
        if bat_content:
            bat_file = batch_dir / f"Hristos_{batch_dir_name}_start.bat"
            try:
                bat_file.write_text(bat_content, encoding='utf-8')
                self.logger.info(f"✅ Batch-Bat-Datei erstellt: {bat_file.name}")
            except Exception as e:
                self.logger.error(f"❌ Fehler beim Erstellen der Batch-Bat-Datei: {e}")

def main():
    if len(sys.argv) != 2:
        print("Verwendung: python create_bat_batch_single.py <batch_number>")
        print("Beispiel: python create_bat_batch_single.py 7")
        sys.exit(1)
        
    batch_number = sys.argv[1]
    creator = BatchBatCreator()
    creator.create_batch_bat(batch_number)

if __name__ == "__main__":
    main()
