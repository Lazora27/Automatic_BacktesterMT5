import os
from pathlib import Path
import logging
from datetime import datetime
import sys
from typing import List, Dict

class PentaBatchCreator:
    def __init__(self):
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5")
        self.experts_path = self.mt5_base / "Experts"
        self.terminal_exe = Path(r"C:\Program Files\MetaTrader 5 IC Markets EU\terminal64.exe")
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Logger Setup"""
        logger = logging.getLogger("PentaBatchCreator")
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File Handler
        log_file = Path("penta_batch_creator.log")
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger

    def get_batch_groups(self) -> Dict[str, List[Path]]:
        """Gruppiert Batch-Ordner in 5er Gruppen"""
        batch_dirs = sorted(
            [d for d in self.experts_path.glob("Batch_*") if d.is_dir()],
            key=lambda x: int(x.name.split('_')[1])
        )
        
        groups = {}
        for i in range(0, len(batch_dirs), 5):
            group_batch_dirs = batch_dirs[i:i+5]
            if group_batch_dirs:
                start_num = int(group_batch_dirs[0].name.split('_')[1])
                end_num = int(group_batch_dirs[-1].name.split('_')[1])
                group_name = f"Batch_{start_num:04d}-{end_num:04d}"
                groups[group_name] = group_batch_dirs
                
        return groups

    def create_bat_content(self, group_name: str, batch_dirs: List[Path]) -> str:
        """Erstellt den Inhalt für die Penta-Batch .bat Datei"""
        bat_content = f'''@echo off
setlocal EnableDelayedExpansion

set "TERMINAL={self.terminal_exe}"
set "GROUP_NAME={group_name}"
set "FAILED_COUNTER=0"
set "CURRENT_EA="

echo Starte Tests für %GROUP_NAME%...
echo Timestamp: %DATE% %TIME% > "{self.experts_path}\\{group_name}_test_log.txt"

'''
        # Sammle alle EAs aus den Batch-Ordnern
        for batch_dir in batch_dirs:
            bat_content += f'\necho Verarbeite Batch: {batch_dir.name}\n'
            
            # Durchsuche alle EA-Verzeichnisse im Batch
            for ea_dir in batch_dir.glob("*"):
                if not ea_dir.is_dir():
                    continue
                    
                ini_dir = ea_dir / "ini"
                if not ini_dir.exists() or not list(ini_dir.glob("*.ini")):
                    continue
                
                ea_name = ea_dir.name
                bat_content += f'''
echo.
echo Verarbeite EA: {ea_name}
echo [%DATE% %TIME%] Starting EA: {ea_name} >> "{self.experts_path}\\{group_name}_test_log.txt"
set "CURRENT_EA={ea_name}"
set "FAILED_COUNTER=0"

for %%F in ("{ini_dir}\\*.ini") do (
    set "CURRENT_INI=%%~nxF"
    echo Processing !CURRENT_INI! ...
    echo [%DATE% %TIME%] Testing {ea_name} - !CURRENT_INI! >> "{self.experts_path}\\{group_name}_test_log.txt"
    
    "%TERMINAL%" /config:"%%~fF"
    
    if errorlevel 1 (
        echo [%DATE% %TIME%] Error with {ea_name} - !CURRENT_INI! >> "{self.experts_path}\\{group_name}_test_log.txt"
        set /a FAILED_COUNTER+=1
        
        if !FAILED_COUNTER! GEQ 3 (
            echo Drei Fehler in Folge für EA !CURRENT_EA! - Überspringe restliche Tests...
            echo [%DATE% %TIME%] EA {ea_name} skipped after 3 failures >> "{self.experts_path}\\{group_name}_test_log.txt"
            goto :next_ea_{ea_name.replace(" ", "_")}
        )
    ) else (
        set "FAILED_COUNTER=0"
        echo [%DATE% %TIME%] Successfully completed {ea_name} - !CURRENT_INI! >> "{self.experts_path}\\{group_name}_test_log.txt"
    )
    
    rem Warte bis MT5 vollständig beendet ist
    timeout /t 5 /nobreak
)

:next_ea_{ea_name.replace(" ", "_")}
'''

        # Füge Ende hinzu
        bat_content += '''
:end
echo.
echo Tests abgeschlossen für %GROUP_NAME%.
echo [%DATE% %TIME%] All tests completed >> "{self.experts_path}\\{group_name}_test_log.txt"
pause
'''

        return bat_content

    def create_penta_bats(self):
        """Erstellt .bat Dateien für alle 5er-Gruppen von Batches"""
        groups = self.get_batch_groups()
        
        for group_name, batch_dirs in groups.items():
            self.logger.info(f"\nVerarbeite Gruppe: {group_name}")
            
            # Erstelle bat-Datei für die Gruppe
            bat_content = self.create_bat_content(group_name, batch_dirs)
            bat_file = self.experts_path / f"Hristos_{group_name}_start.bat"
            
            try:
                bat_file.write_text(bat_content, encoding='utf-8')
                self.logger.info(f"✅ Penta-Batch-Datei erstellt: {bat_file.name}")
                
                # Logge die enthaltenen Batches
                batch_numbers = [int(d.name.split('_')[1]) for d in batch_dirs]
                self.logger.info(f"   Enthält Batches: {', '.join(str(n) for n in batch_numbers)}")
                
            except Exception as e:
                self.logger.error(f"❌ Fehler beim Erstellen der Penta-Batch-Datei: {e}")

def main():
    creator = PentaBatchCreator()
    creator.create_penta_bats()

if __name__ == "__main__":
    main()
