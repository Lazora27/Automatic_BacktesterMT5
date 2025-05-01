import os
from pathlib import Path
import logging
from datetime import datetime
import shutil
from typing import List, Dict, Set

class BatHierarchyCreator:
    def __init__(self):
        self.mt5_base = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5")
        self.experts_path = self.mt5_base / "Experts"
        self.terminal_exe = Path(r"C:\Program Files\MetaTrader 5 IC Markets EU\terminal64.exe")
        self.global_batch_dir = self.experts_path / "global_Batch"
        self.logger = self._setup_logger()
        
        # Erstelle global_Batch Ordner
        self.global_batch_dir.mkdir(exist_ok=True)

    def _setup_logger(self):
        """Logger Setup mit File- und Console-Handler"""
        logger = logging.getLogger("BatHierarchyCreator")
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File Handler
        log_file = self.global_batch_dir / "bat_creation.log"
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger

    def create_ea_bat_content(self, ea_dir: Path) -> str:
        """Erstellt den Inhalt für eine einzelne EA .bat Datei"""
        return f'''@echo off
setlocal EnableDelayedExpansion

set "TERMINAL={self.terminal_exe}"
set "INIDIR=%~dp0ini"
set "LOGDIR=%~dp0logs"
set "COUNTER=0"
set "EA_NAME={ea_dir.name}"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo [%DATE% %TIME%] Starte Tests für %EA_NAME% > "%LOGDIR%\\log.txt"

for %%F in ("%INIDIR%\\*.ini") do (
    echo Starte Backtest: %%~nxF
    echo [%DATE% %TIME%] Teste: %%~nxF >> "%LOGDIR%\\log.txt"
    
    "%TERMINAL%" /config:"%%~fF"
    
    REM Fehlerprüfung: Logfile scannen
    findstr /C:"error" /C:"failed" /C:"invalid" "%LOCALAPPDATA%\\MetaQuotes\\Terminal\\*.log" >nul
    if !errorlevel! equ 0 (
        echo [%DATE% %TIME%] Fehler erkannt in %%~nxF >> "%LOGDIR%\\error_log.txt"
        set /a COUNTER+=1
        
        if !COUNTER! geq 3 (
            echo [%DATE% %TIME%] 3 Fehler hintereinander - EA %EA_NAME% wird abgebrochen >> "%LOGDIR%\\error_log.txt"
            echo [%DATE% %TIME%] Letzte fehlerhafte INI: %%~nxF >> "%LOGDIR%\\error_log.txt"
            goto :SKIP_EA
        )
    ) else (
        set "COUNTER=0"
        echo [%DATE% %TIME%] Erfolgreich: %%~nxF >> "%LOGDIR%\\log.txt"
    )
    
    timeout /t 5 /nobreak
)

:SKIP_EA
echo [%DATE% %TIME%] Tests abgeschlossen für %EA_NAME% >> "%LOGDIR%\\log.txt"
exit /b
'''

    def create_batch_bat_content(self, batch_dir: Path, ea_bats: List[Path]) -> str:
        """Erstellt den Inhalt für eine Batch .bat Datei"""
        content = f'''@echo off
setlocal EnableDelayedExpansion

set "BATCH_NAME={batch_dir.name}"
set "LOGDIR={batch_dir}\\logs"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo [%DATE% %TIME%] Starte Tests für %BATCH_NAME% > "%LOGDIR%\\batch_log.txt"

'''
        
        for ea_bat in ea_bats:
            content += f'''
echo Starte EA: {ea_bat.parent.name}
echo [%DATE% %TIME%] Teste EA: {ea_bat.parent.name} >> "%LOGDIR%\\batch_log.txt"
call "{ea_bat}"
'''
            
        content += '''
echo [%DATE% %TIME%] Alle Tests abgeschlossen >> "%LOGDIR%\\batch_log.txt"
exit /b
'''
        return content

    def create_penta_bat_content(self, group_name: str, batch_bats: List[Path]) -> str:
        """Erstellt den Inhalt für eine Penta-Batch .bat Datei"""
        content = f'''@echo off
setlocal EnableDelayedExpansion

set "GROUP_NAME={group_name}"
set "LOGDIR={self.global_batch_dir}\\logs"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo [%DATE% %TIME%] Starte Tests für %GROUP_NAME% > "%LOGDIR%\\{group_name}_log.txt"

'''
        
        for batch_bat in batch_bats:
            content += f'''
echo Starte Batch: {batch_bat.stem}
echo [%DATE% %TIME%] Teste Batch: {batch_bat.stem} >> "%LOGDIR%\\{group_name}_log.txt"
call "{batch_bat}"
'''
            
        content += '''
echo [%DATE% %TIME%] Alle Tests abgeschlossen >> "%LOGDIR%\\{group_name}_log.txt"
exit /b
'''
        return content

    def create_global_bat_content(self, bat_type: str, bat_files: List[Path]) -> str:
        """Erstellt den Inhalt für eine globale .bat Datei"""
        content = f'''@echo off
setlocal EnableDelayedExpansion

set "LOGDIR={self.global_batch_dir}\\logs"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

echo [%DATE% %TIME%] Starte {bat_type} Tests > "%LOGDIR%\\global_{bat_type.lower()}_log.txt"

'''
        
        for bat_file in bat_files:
            content += f'''
echo Starte: {bat_file.stem}
echo [%DATE% %TIME%] Teste: {bat_file.stem} >> "%LOGDIR%\\global_{bat_type.lower()}_log.txt"
call "{bat_file}"
'''
            
        content += f'''
echo [%DATE% %TIME%] Alle {bat_type} Tests abgeschlossen >> "%LOGDIR%\\global_{bat_type.lower()}_log.txt"
pause
'''
        return content

    def create_bat_hierarchy(self):
        """Erstellt die komplette Hierarchie von .bat Dateien"""
        created_bats = {
            'ea': [],
            'batch': [],
            'penta': []
        }
        
        # 1. Erstelle EA-Level .bat Dateien
        self.logger.info("Erstelle EA-Level .bat Dateien...")
        for batch_dir in sorted(self.experts_path.glob("Batch_*")):
            if not batch_dir.is_dir():
                continue
                
            for ea_dir in batch_dir.glob("*"):
                if not ea_dir.is_dir() or not (ea_dir / "ini").exists():
                    continue
                    
                ea_bat = ea_dir / f"{ea_dir.name}_start.bat"
                ea_bat.write_text(self.create_ea_bat_content(ea_dir), encoding='utf-8')
                created_bats['ea'].append(ea_bat)
                self.logger.info(f"✅ EA-Bat erstellt: {ea_bat.name}")
        
        # 2. Erstelle Batch-Level .bat Dateien
        self.logger.info("\nErstelle Batch-Level .bat Dateien...")
        for batch_dir in sorted(self.experts_path.glob("Batch_*")):
            if not batch_dir.is_dir():
                continue
                
            ea_bats = list(batch_dir.glob("*/*_start.bat"))
            if not ea_bats:
                continue
                
            batch_bat = batch_dir / f"Hristos_{batch_dir.name}_start.bat"
            batch_bat.write_text(self.create_batch_bat_content(batch_dir, ea_bats), encoding='utf-8')
            created_bats['batch'].append(batch_bat)
            self.logger.info(f"✅ Batch-Bat erstellt: {batch_bat.name}")
        
        # 3. Erstelle Penta-Batch .bat Dateien
        self.logger.info("\nErstelle Penta-Batch .bat Dateien...")
        batch_bats = sorted(created_bats['batch'])
        for i in range(0, len(batch_bats), 5):
            group = batch_bats[i:i+5]
            if not group:
                continue
                
            start_num = int(group[0].parent.name.split('_')[1])
            end_num = int(group[-1].parent.name.split('_')[1])
            group_name = f"Penta_Batch_{start_num:04d}-{end_num:04d}"
            
            penta_bat = self.global_batch_dir / f"Hristos_{group_name}_start.bat"
            penta_bat.write_text(self.create_penta_bat_content(group_name, group), encoding='utf-8')
            created_bats['penta'].append(penta_bat)
            self.logger.info(f"✅ Penta-Bat erstellt: {penta_bat.name}")
        
        # 4. Erstelle Global .bat Dateien
        self.logger.info("\nErstelle Global .bat Dateien...")
        
        # Single Global (alle Batch-Dateien)
        single_global = self.global_batch_dir / "Hristos_Single_global_start.bat"
        single_global.write_text(self.create_global_bat_content("Single", created_bats['batch']), encoding='utf-8')
        self.logger.info("✅ Single Global Bat erstellt")
        
        # Penta Global (alle Penta-Dateien)
        penta_global = self.global_batch_dir / "Hristos_Penta_global_start.bat"
        penta_global.write_text(self.create_global_bat_content("Penta", created_bats['penta']), encoding='utf-8')
        self.logger.info("✅ Penta Global Bat erstellt")
        
        # Complete Global (alle EA-Dateien)
        complete_global = self.global_batch_dir / "Hristos_Global_global_start.bat"
        complete_global.write_text(self.create_global_bat_content("Complete", created_bats['ea']), encoding='utf-8')
        self.logger.info("✅ Complete Global Bat erstellt")

def main():
    creator = BatHierarchyCreator()
    creator.create_bat_hierarchy()

if __name__ == "__main__":
    main()
