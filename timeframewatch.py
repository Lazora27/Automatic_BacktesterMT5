"""
Trading timeframes with their corresponding minute values and MetaTrader identifiers.
"""

class Timeframes:
    # Timeframe definitions with their minute values
    TIMEFRAMES = {
        "M5": 5,      # 5 minutes
        "M15": 15,    # 15 minutes
        "M30": 30,    # 30 minutes
        "H1": 60,     # 1 hour
        "H4": 240,    # 4 hours
        "D1": 1440    # 1 day
    }
    
    # MetaTrader period constants
    MT5_TIMEFRAMES = {
        "M5": "PERIOD_M5",
        "M15": "PERIOD_M15",
        "M30": "PERIOD_M30",
        "H1": "PERIOD_H1",
        "H4": "PERIOD_H4",
        "D1": "PERIOD_D1"
    }
    
    @classmethod
    def get_minutes(cls, timeframe):
        """Get the number of minutes for a timeframe."""
        return cls.TIMEFRAMES.get(timeframe)
    
    @classmethod
    def get_mt5_constant(cls, timeframe):
        """Get the MetaTrader 5 constant for a timeframe."""
        return cls.MT5_TIMEFRAMES.get(timeframe)
    
    @classmethod
    def get_all_timeframes(cls):
        """Return all available timeframes."""
        return list(cls.TIMEFRAMES.keys())
    
    @classmethod
    def get_all_minutes(cls):
        """Return all timeframe values in minutes."""
        return list(cls.TIMEFRAMES.values())
    
    @classmethod
    def is_valid_timeframe(cls, timeframe):
        """Check if a timeframe is valid."""
        return timeframe in cls.TIMEFRAMES


import os
from pathlib import Path
import logging
import json
from typing import Dict, Tuple, List

class TimeframeWatcher:
    """Verwaltet Symbol- und Timeframe-Zuordnungen für EAs."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.config_file = Path(__file__).parent / 'timeframe_config.json'
        self.ea_config: Dict[str, Dict[str, str]] = {}
        self.load_config()
        
    def load_config(self) -> None:
        """Lädt die Konfiguration aus der JSON-Datei."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    self.ea_config = json.load(f)
            except Exception as e:
                self.logger.error(f"Fehler beim Laden der Konfiguration: {str(e)}")
                self.ea_config = {}
        else:
            # Standard-Konfiguration
            self.ea_config = {
                "default": {
                    "symbol": "EURUSD",
                    "timeframe": "H1"
                }
            }
            self.save_config()
            
    def save_config(self) -> None:
        """Speichert die Konfiguration in der JSON-Datei."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.ea_config, f, indent=4)
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern der Konfiguration: {str(e)}")
            
    def get_ea_config(self, ea_name: str) -> Tuple[str, str]:
        """Holt Symbol und Timeframe für einen EA."""
        if ea_name in self.ea_config:
            config = self.ea_config[ea_name]
            return config.get('symbol', 'EURUSD'), config.get('timeframe', 'H1')
        return self.ea_config['default']['symbol'], self.ea_config['default']['timeframe']
        
    def set_ea_config(self, ea_name: str, symbol: str, timeframe: str) -> None:
        """Setzt Symbol und Timeframe für einen EA."""
        self.ea_config[ea_name] = {
            'symbol': symbol.upper(),
            'timeframe': timeframe.upper()
        }
        self.save_config()
        
    def get_all_configs(self) -> Dict[str, Dict[str, str]]:
        """Gibt alle EA-Konfigurationen zurück."""
        return self.ea_config
        
    def get_available_timeframes(self) -> List[str]:
        """Gibt alle verfügbaren Timeframes zurück."""
        return ['M5', 'M15', 'M30', 'H1', 'H4', 'D1']
        
    def get_available_symbols(self) -> List[str]:
        """Gibt alle verfügbaren Symbole zurück."""
        return [
            "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDUSD", "CADCHF", "CADJPY",
            "CHFJPY", "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURNZD",
            "EURUSD", "GBPAUD", "GBPCAD", "GBPCHF", "GBPJPY", "GBPNZD", "GBPUSD",
            "NZDCAD", "NZDCHF", "NZDJPY", "NZDUSD", "USDCAD", "USDCHF", "USDJPY",
            "XAGUSD", "XAUUSD", "US30", "US100", "US500", "DE30", "UK100", "FR40",
            "AUS200", "STOXX50", "NL25", "ES35", "IT40", "JP225"
        ]
        
    def validate_timeframe(self, timeframe: str) -> bool:
        """Überprüft ob ein Timeframe gültig ist."""
        return timeframe.upper() in self.get_available_timeframes()
        
    def validate_symbol(self, symbol: str) -> bool:
        """Überprüft ob ein Symbol gültig ist."""
        return symbol.upper() in self.get_available_symbols()

def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)
    
    try:
        # Erstelle TimeframeWatcher
        watcher = TimeframeWatcher()
        
        # Zeige verfügbare Symbole und Timeframes
        symbols = watcher.get_available_symbols()
        timeframes = watcher.get_available_timeframes()
        
        logger.info(f"\nVerfügbare Symbole ({len(symbols)}):")
        for symbol in symbols:
            logger.info(symbol)
            
        logger.info(f"\nVerfügbare Timeframes ({len(timeframes)}):")
        for tf in timeframes:
            logger.info(tf)
            
        logger.info(f"\nGesamtkombinationen: {len(symbols) * len(timeframes)}")
            
    except Exception as e:
        logger.error(f"Kritischer Fehler: {str(e)}")

if __name__ == "__main__":
    main()
