import os
import shutil
from pathlib import Path
import logging
from datetime import datetime, timedelta
from marketwatch import MarketSymbols
from timeframewatch import Timeframes

class IniCreator:
    def __init__(self):
        self.logger = self._setup_logger()
        self.mt5_path = Path(r"C:\Users\nikol\AppData\Roaming\MetaQuotes\Terminal\4B1CE69F577705455263BD980C39A82C\MQL5")
        self.experts_path = self.mt5_path / "Experts"
        self.optimized_path = self.mt5_path / "Profiles/Tester/optimized"
        self.symbols = MarketSymbols.get_all_instruments()
        self.timeframes = Timeframes.get_all_timeframes()
        
    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File Handler
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / f"ini_creator_{datetime.now():%Y%m%d_%H%M}.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
        
    def find_matching_otp_file(self, ea_name: str) -> Path:
        """
        Findet die passende .otp Datei für eine EA basierend auf dem Namen.
        
        Args:
            ea_name: Name der EA (ohne .ex5)
            
        Returns:
            Path: Pfad zur passenden .otp Datei oder None wenn keine gefunden
        """
        try:
            # Suche nach .otp Dateien die den EA Namen enthalten
            expected_name = f"{ea_name}_01_otp.set"
            otp_file = self.optimized_path / expected_name
            
            if otp_file.exists():
                return otp_file
                
            self.logger.warning(f"No matching .otp file found for EA: {ea_name} (expected: {expected_name})")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding .otp file for {ea_name}: {str(e)}")
            return None
        
    def create_ini(self, ea_name: str, symbol: str, timeframe: str, batch_folder: str) -> None:
        """
        Erstellt eine .ini Datei für den MT5 Strategy Tester.
        
        Args:
            ea_name: Name der EA (ohne .ex5)
            symbol: Handelssymbol (z.B. 'EURUSD')
            timeframe: Zeitrahmen (z.B. 'H1')
            batch_folder: Name des Batch-Ordners (z.B. 'Batch_0001')
        """
        try:
            # Erstelle ini-Verzeichnis im Batch-Ordner
            batch_path = self.experts_path / batch_folder
            ini_dir = batch_path / ea_name / "ini"
            ini_dir.mkdir(parents=True, exist_ok=True)
            
            # Erstelle den ini-Dateinamen
            ini_name = f"{ea_name}_{symbol}_{timeframe}.ini"
            ini_path = ini_dir / ini_name
            
            # Erstelle den vollständigen EA-Pfad
            ea_full_path = str(self.experts_path / f"{ea_name}.ex5")
            
            # Finde die passende .otp Datei
            otp_file = self.find_matching_otp_file(ea_name)
            if otp_file:
                # Lese den Inhalt der .otp Datei
                with open(otp_file, 'r') as f:
                    otp_content = f.read()
                self.logger.info(f"Found matching .otp file: {otp_file}")
            else:
                otp_content = ""
                self.logger.warning(f"No .otp file found for {ea_name}, ini will be created without optimization settings")
            
            # Berechne Datumsbereich (1 Jahr)
            today = datetime.now()
            from_date = today.replace(year=today.year-1, month=1, day=1)
            to_date = today.replace(month=1, day=1)
            
            # Erstelle .ini Inhalt mit vollständigem EA-Pfad
            ini_content = f"""[Tester]
Expert={ea_name}.ex5
Symbol={symbol}
Period={timeframe}
Model=1
Optimization=1
DateEnable=1
FromDate={from_date:%Y.%m.%d}
ToDate={to_date:%Y.%m.%d}
ForwardMode=0
Deposit=10000
Currency=USD
ProfitInPips=0

[TesterInputs]
{otp_content}

[Optimization]
MaximizeProfit=1
RiskMin=0
RiskMax=100
StepSize=0.1
OnTester=0

[Reporting]
Server=true
TradeReport=true
ProfitChart=true
BalanceChart=true
EquityChart=true
SaveReport=true
ShutdownTerminal=false
"""

            # Schreibe .ini Datei
            with open(ini_path, 'w') as f:
                f.write(ini_content)
                
            self.logger.info(f"Created INI file: {ini_path}")
            
        except Exception as e:
            self.logger.error(f"Error creating .ini file for {ea_name}: {str(e)}")

    def process_batch(self, batch_number: int) -> None:
        """
        Verarbeitet alle EAs in einem bestimmten Batch-Ordner.
        
        Args:
            batch_number: Nummer des Batch-Ordners (1-60)
        """
        batch_folder = f"Batch_{batch_number:04d}"
        batch_path = self.experts_path / batch_folder
        
        if not batch_path.exists():
            self.logger.warning(f"Batch folder does not exist: {batch_path}")
            return
            
        # Verarbeite jeden EA-Ordner im Batch
        for ea_dir in batch_path.iterdir():
            if not ea_dir.is_dir() or ea_dir.name == "ini":
                continue
                
            ea_name = ea_dir.name
            
            # Finde die passende .otp Datei einmal pro EA
            otp_file = self.find_matching_otp_file(ea_name)
            if otp_file:
                with open(otp_file, 'r') as f:
                    otp_content = f.read()
                self.logger.info(f"Found matching .otp file: {otp_file}")
            else:
                otp_content = ""
                self.logger.warning(f"No .otp file found for {ea_name}, ini will be created without optimization settings")
            
            # Erstelle ini-Verzeichnis
            ini_dir = ea_dir / "ini"
            ini_dir.mkdir(parents=True, exist_ok=True)
            
            # Berechne Datumsbereich einmal pro EA
            today = datetime.now()
            from_date = today.replace(year=today.year-1, month=1, day=1)
            to_date = today.replace(month=1, day=1)
            
            # Erstelle alle .ini Dateien für diese EA
            for symbol in self.symbols:
                for timeframe in self.timeframes:
                    output_path = ini_dir / f"{ea_name}_{symbol}_{timeframe}.ini"
                    
                    # Erstelle .ini Inhalt
                    ini_content = f"""[Tester]
Expert={self.experts_path / f"{ea_name}.ex5"}
Symbol={symbol}
Period={timeframe}
Model=1
Optimization=1
DateEnable=1

[TesterDate]
FromDate={from_date:%Y.%m.%d}
ToDate={to_date:%Y.%m.%d}
DateEnable=true

[Optimization]
OptimizationMode=2
OptimizationRuns=100
ForwardMode=0
ForwardDate={from_date:%Y.%m.%d}
OptimizationPopulation=200
OptimizationMutationFactor=0.5
OptimizationCrossoverFactor=0.5

[TesterSettings]
Deposit=10000
Currency=USD
Leverage=100
Spread=0
ExecutionMode=0
Positions=2
Model=1
OptimizationCriterion=0
AgentThreads=0
Visual=false
PrintOptimization=false
WriteReport=true

[AdditionalSettings]
DisableGT215=true
UseLocalTime=true
SkipErrors=false

[Reporting]
ReportHTML=true
ReportXML=true
ReportDetails=true
ReportGraph=true

[Limits]
MaxSymbols=1

[OptimizationParameters]
{otp_content}
"""
                    try:
                        with open(output_path, 'w') as f:
                            f.write(ini_content)
                        self.logger.info(f"Created {output_path} for {ea_name} on {symbol} {timeframe}")
                    except Exception as e:
                        self.logger.error(f"Error writing ini file {output_path}: {str(e)}")
                        continue
                    
    def process_all_batches(self, start_batch: int = 1, end_batch: int = 60) -> None:
        """
        Verarbeitet alle Batches von start_batch bis end_batch.
        
        Args:
            start_batch: Erste Batch-Nummer (default: 1)
            end_batch: Letzte Batch-Nummer (default: 60)
        """
        for batch_num in range(start_batch, end_batch + 1):
            self.logger.info(f"Processing Batch_{batch_num:04d}")
            self.process_batch(batch_num)

def main():
    creator = IniCreator()
    creator.process_all_batches()
    
if __name__ == "__main__":
    main()
