"""
Market symbols categorized by type.
Each category contains a list of available symbols for trading.
"""

class MarketSymbols:
    # Forex Major Pairs (7)
    FOREX_MAJORS = [
        "EURUSD", "GBPUSD", "USDCHF", "USDJPY", 
        "USDCAD", "AUDUSD", "NZDUSD"
    ]
    
    # Forex Minor Pairs (17)
    FOREX_MINORS = [
        "AUDNZD", "AUDCAD", "AUDCHF", "AUDJPY",
        "NZDCAD", "EURCAD", "CADJPY", "EURJPY",
        "EURGBP", "EURCHF", "EURAUD", "EURNZD",
        "GBPCHF", "GBPJPY", "GBPAUD", "GBPCAD"
    ]
    
    # Nordic Forex Pairs (4)
    FOREX_NORDIC = [
        "EURNOK", "NOKSEK", "USDSEK", "USDNOK"
    ]
    
    # Commodities (5)
    COMMODITIES = [
        "XBRUSD", "XNGUSD", "XTIUSD",  # Energy
        "XAUUSD", "XAGUSD"             # Precious Metals
    ]
    
    # Stock Indices (9)
    INDICES = [
        "STOXX50", "F40", "JP225",     # European and Asian
        "AUS200", "UK100",             # Australian and UK
        "US30", "DE40", "US500",       # US and German
        "USTEC", "CA60"                # Tech and Canadian
    ]
    
    @classmethod
    def get_all_symbols(cls):
        """Return all forex symbols (28 pairs)."""
        return cls.FOREX_MAJORS + cls.FOREX_MINORS + cls.FOREX_NORDIC
        
    @classmethod
    def get_all_instruments(cls):
        """Return all available trading instruments (42 total)."""
        return (cls.FOREX_MAJORS + 
                cls.FOREX_MINORS + 
                cls.FOREX_NORDIC +
                cls.COMMODITIES +
                cls.INDICES)
