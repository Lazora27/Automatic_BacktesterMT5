import os
from pathlib import Path
import logging
from datetime import datetime

class BatCreator:
    def __init__(self):
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5")
        self.experts_path = self.mt5_base / "Experts"
        self.terminal_exe = Path(r"C:\Program Files\MetaTrader 5 IC Markets EU\terminal64.exe")
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Logger Setup"""
        logger = logging.getLogger("BatCreator")
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        return logger

    def create_bat_content(self, ea_name: str, ini_dir: Path) -> str:
        """Erstellt den Inhalt für die .bat Datei"""
        return f'''@echo off
setlocal EnableDelayedExpansion

set "TERMINAL={self.terminal_exe}"
set "INIDIR={ini_dir}"
set "FAILED_COUNTER=0"
set "CURRENT_EA={ea_name}"

echo Starte Tests für %CURRENT_EA%...
echo Timestamp: %DATE% %TIME% > "%INIDIR%\test_log.txt"

for %%F in ("%INIDIR%\*.ini") do (
    set "CURRENT_INI=%%~nxF"
    echo.
    echo Processing !CURRENT_INI! ...
    echo [%DATE% %TIME%] Testing !CURRENT_INI! >> "%INIDIR%\test_log.txt"
    
    "%TERMINAL%" /config:"%%~fF"
    
    if errorlevel 1 (
        echo [%DATE% %TIME%] Error with !CURRENT_INI! >> "%INIDIR%\test_log.txt"
        set /a FAILED_COUNTER+=1
        
        if !FAILED_COUNTER! GEQ 3 (
            echo Drei Tests in Folge fehlgeschlagen. Beende Batch...
            echo [%DATE% %TIME%] Aborted after 3 consecutive failures >> "%INIDIR%\test_log.txt"
            goto :end
        )
    ) else (
        set "FAILED_COUNTER=0"
        echo [%DATE% %TIME%] Successfully completed !CURRENT_INI! >> "%INIDIR%\test_log.txt"
    )
    
    rem Warte bis MT5 vollständig beendet ist
    timeout /t 5 /nobreak
)

:end
echo.
echo Tests abgeschlossen für %CURRENT_EA%.
echo [%DATE% %TIME%] All tests completed >> "%INIDIR%\test_log.txt"
pause
'''

    def create_bat_files(self):
        """Erstellt .bat Dateien für alle EAs in den Batch-Ordnern"""
        for batch_dir in self.experts_path.glob("Batch_*"):
            if not batch_dir.is_dir():
                continue
                
            self.logger.info(f"\nVerarbeite Batch: {batch_dir.name}")
            
            # Verarbeite alle EAs im Batch
            for ea_file in batch_dir.glob("**/*.ex5"):
                ea_name = ea_file.stem
                ini_dir = batch_dir / ea_name / "ini"
                
                # Prüfe ob ini-Dateien existieren
                if not ini_dir.exists() or not list(ini_dir.glob("*.ini")):
                    self.logger.warning(f"Keine ini-Dateien gefunden für: {ea_name}")
                    continue
                
                # Erstelle bat-Datei
                bat_file = batch_dir / f"Hristos_{ea_name}_start.bat"
                bat_content = self.create_bat_content(ea_name, ini_dir)
                
                try:
                    bat_file.write_text(bat_content, encoding='utf-8')
                    self.logger.info(f"✅ Bat-Datei erstellt: {bat_file.name}")
                except Exception as e:
                    self.logger.error(f"❌ Fehler beim Erstellen der Bat-Datei für {ea_name}: {e}")

def main():
    creator = BatCreator()
    creator.create_bat_files()

if __name__ == "__main__":
    main()