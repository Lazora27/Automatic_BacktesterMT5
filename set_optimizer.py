import os
import re
import math
import yaml
import json
import logging
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime
import csv
import numpy as np
import sys
from pathlib import Path
import glob

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('set_optimizer.log')
    ]
)
logger = logging.getLogger(__name__)

class ParameterRole(Enum):
    """Define roles for EA parameters to enable intelligent optimization."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    VOLUME = "volume"
    RISK = "risk"
    PERIOD = "period"
    TECHNICAL = "technical"
    FEATURE_SWITCH = "feature_switch"
    BREAKEVEN = "breakeven"
    SYSTEM = "system"
    POSITIONING = "positioning"  # Added for position management parameters
    UNKNOWN = "unknown"

@dataclass
class ParameterMetadata:
    """Metadata for EA parameters including validation rules and defaults."""
    role: ParameterRole
    default_value: Any = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    aliases: Set[str] = field(default_factory=set)
    is_static: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'role': self.role.value,
            'default_value': self.default_value,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'aliases': list(self.aliases),
            'is_static': self.is_static
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ParameterMetadata':
        """Create from dictionary."""
        data = data.copy()
        data['role'] = ParameterRole(data['role'])
        data['aliases'] = set(data.get('aliases', []))
        return cls(**data)

class ParameterRule:
    """Rule for parameter validation and optimization."""
    def __init__(self, rule_config: Dict[str, Any]):
        self.name = rule_config['name']
        self.condition = rule_config['condition']
        self.apply_if = rule_config['apply_if']
        self.priority = rule_config['priority']
        self.error_on_fail = rule_config['error_on_fail']
        self.min_ratio = rule_config.get('min_ratio')
        self.max_ratio = rule_config.get('max_ratio')
        
    def evaluate(self, params: Dict[str, float]) -> bool:
        """Evaluate the rule condition."""
        try:
            if not all(p in params for p in self.apply_if):
                return True  # Skip if not all parameters present
                
            if 'ratio' in self.condition:
                if len(self.apply_if) != 2:
                    return True
                p1, p2 = self.apply_if
                ratio = params[p1] / params[p2] if params[p2] != 0 else float('inf')
                return self.min_ratio <= ratio <= self.max_ratio
                
            elif '>' in self.condition:
                p1, p2 = self.apply_if
                return params[p1] > params[p2]
                
            elif '<=' in self.condition:
                value = params[self.apply_if[0]]
                limit = float(self.condition.split('<=')[1].strip())
                return value <= limit
                
            elif '>=' in self.condition:
                value = params[self.apply_if[0]]
                limit = float(self.condition.split('>=')[1].strip())
                return value >= limit
                
            elif 'between' in self.condition.lower():
                value = params[self.apply_if[0]]
                min_val, max_val = map(float, self.condition.split('between')[1].split('and'))
                return min_val <= value <= max_val
                
        except (ValueError, ZeroDivisionError, KeyError) as e:
            logger.warning(f"Error evaluating rule {self.name}: {str(e)}")
            return not self.error_on_fail
            
        return True

class SetFileOptimizer:
    """Optimizer for MT5 .set files."""
    def __init__(self):
        """Initialize the optimizer with enhanced parameter validation."""
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Create console handler with formatter
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Create file handler for detailed logging
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        file_handler = logging.FileHandler(log_dir / f"set_optimizer_{datetime.now():%Y%m%d_%H%M}.log")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # MT5 specific limits
        self.mt5_limits = {
            'lot': {
                'min': 0.01,
                'max': 100.0,
                'step': 0.01
            },
            'stop_loss': {
                'min': 5,
                'max': 5000,
                'step': 1
            },
            'take_profit': {
                'min': 5,
                'max': 5000,
                'step': 1
            },
            'trailing_stop': {
                'min': 5,
                'max': 5000,
                'step': 1
            },
            'magic_number': {
                'min': 1,
                'max': 999999,
                'step': 1
            },
            'period': {
                'min': 1,
                'max': 10000,
                'step': 1
            }
        }
        
        # Parameter metadata with enhanced validation
        self.parameter_metadata = {}
        self.alias_mapping = {}
        
        # Initialize common parameters
        self._add_parameter("lots", ParameterRole.VOLUME, 0.1, 0.01, 100,
                          ["volume", "lot_size", "inp_lots", "fixed_lot"])
        self._add_parameter("stoploss", ParameterRole.STOP_LOSS, 100, 5, 1000,
                          ["sl", "stop_loss", "inp_stoploss"])
        self._add_parameter("takeprofit", ParameterRole.TAKE_PROFIT, 200, 5, 1000,
                          ["tp", "take_profit", "inp_takeprofit"])
        self._add_parameter("trailingstart", ParameterRole.TRAILING_STOP, 30, 5, 200,
                          ["trailing_start", "tsl_start"])
        self._add_parameter("trailingstop", ParameterRole.TRAILING_STOP, 50, 10, 300,
                          ["trailing_stop", "tsl_stop"])
        self._add_parameter("period", ParameterRole.PERIOD, 14, 1, 1000,
                          ["timeframe", "ma_period", "inp_period"])
        self._add_parameter("shift", ParameterRole.TECHNICAL, 0, 0, 100,
                          ["offset", "displacement"])
        self._add_parameter("magico", ParameterRole.SYSTEM, 0, 0, 999999,
                          ["magic", "magic_number"])
        
        # Parameter relationships for validation
        self.parameter_relationships = {
            ("takeprofit", "stoploss"): (1.5, 3.0),  # TP should be 1.5-3x SL
            ("trailingstop", "trailingstart"): (1.2, 2.0),  # Trailing stop should be larger than start
            ("maFast_Period", "maMedium_Period"): (0.2, 0.8),  # Fast MA should be smaller than Medium MA
            ("maMedium_Period", "maSlow_Period"): (0.2, 0.8),  # Medium MA should be smaller than Slow MA
            ("rsiLevelDn", "rsiLevelUp"): (0.3, 0.7),  # RSI Lower should be smaller than RSI Upper
            ("AdxLevelBuy", "AdxLevelMain"): (0.4, 0.9),  # ADX Buy should be smaller than ADX Main
            ("AdxLevelSell", "AdxLevelMain"): (0.4, 0.9),  # ADX Sell should be smaller than ADX Main
            ("userSLpips", "userTPpips"): (0.3, 0.7),  # SL should be smaller than TP
            ("userTslStep", "userTslDistance"): (0.05, 0.2),  # Trailing step should be smaller than distance
            ("userTslInitialStep", "userTslDistance"): (0.5, 2.0),  # Initial trailing step should be relative to distance
            ("userLots", "userBalancePer"): (0.1, 10.0),  # Lots should be proportional to risk
        }
        
        # Parameter groups for diversity detection
        self.param_groups = {
            "trailing": ["trailingstart", "trailingstop", "trailingstep"],
            "breakeven": ["breakevenstart", "breakevenoffset"],
            "risk": ["risk", "lots", "multiplier"],
            "moving_averages": ["maFast_Period", "maMedium_Period", "maSlow_Period"],
            "adx_system": ["AdxPeriod", "AdxLevelMain", "AdxLevelBuy", "AdxLevelSell"],
            "rsi_system": ["rsiPeriod", "rsiLevelUp", "rsiLevelDn"],
            "cci_system": ["uPeriodcci"],
            "atr_system": ["uATRperiod"],
        }
        
        # Parameter priority scoring (higher = more important)
        self.param_priorities = {
            "stoploss": 100,
            "takeprofit": 100,
            "risk": 90,
            "lots": 90,
            "trailingstop": 80,
            "trailingstart": 80,
            "trailingstep": 70,
            "breakevenstart": 60,
            "breakevenoffset": 50,
            "period": 40,
            "shift": 30,
            "deviation": 20,
            "maFast_Period": 30,
            "maMedium_Period": 30,
            "maSlow_Period": 30,
            "AdxPeriod": 30,
            "AdxLevelMain": 30,
            "AdxLevelBuy": 30,
            "AdxLevelSell": 30,
            "rsiPeriod": 30,
            "rsiLevelUp": 30,
            "rsiLevelDn": 30,
            "uPeriodcci": 30,
            "uATRperiod": 30,
        }
        
        # Parameter metadata patterns (fallback if not in config)
        self.param_patterns = {
            r".*risk.*": ParameterMetadata(ParameterRole.RISK, min_value=0, max_value=100),
            r".*lot.*": ParameterMetadata(ParameterRole.RISK, min_value=0.01, max_value=100),
            r".*stop.*": ParameterMetadata(ParameterRole.RISK, min_value=5, max_value=1000),
            r".*profit.*": ParameterMetadata(ParameterRole.RISK, min_value=5, max_value=1000),
            r".*trail.*": ParameterMetadata(ParameterRole.TRAILING_STOP, min_value=1, max_value=500),
            r".*period.*": ParameterMetadata(ParameterRole.TECHNICAL, min_value=1, max_value=10000),
            r".*enabled.*": ParameterMetadata(ParameterRole.FEATURE_SWITCH, is_static=True)
        }
        
        # Semantic parameter metadata
        self.parameter_metadata = {
            # Risk Management
            "stoploss": ParameterMetadata(ParameterRole.STOP_LOSS, min_value=5, max_value=1000, default_value=100),
            "takeprofit": ParameterMetadata(ParameterRole.TAKE_PROFIT, min_value=5, max_value=1000, default_value=200),
            "maximumrisk": ParameterMetadata(ParameterRole.RISK, min_value=0.01, max_value=100, default_value=2),
            "lots": ParameterMetadata(ParameterRole.VOLUME, min_value=0.01, max_value=100, default_value=0.1),
            
            # Trailing System
            "trailingstop": ParameterMetadata(ParameterRole.TRAILING_STOP, min_value=5, max_value=500, default_value=30),
            "trailingstart": ParameterMetadata(ParameterRole.TRAILING_STOP, min_value=5, max_value=500, default_value=15),
            "trailingstep": ParameterMetadata(ParameterRole.TRAILING_STOP, min_value=1, max_value=500, default_value=5),
            
            # Breakeven
            "breakevenstart": ParameterMetadata(ParameterRole.BREAKEVEN, min_value=5, max_value=500, default_value=20),
            "breakevenoffset": ParameterMetadata(ParameterRole.BREAKEVEN, min_value=1, max_value=500, default_value=2),
            
            # Technical Parameters
            "period": ParameterMetadata(ParameterRole.PERIOD, min_value=1, max_value=1000, default_value=14),
            "shift": ParameterMetadata(ParameterRole.TECHNICAL, min_value=0, max_value=100, default_value=0),
            
            # System Parameters (static)
            "magic": ParameterMetadata(ParameterRole.SYSTEM, is_static=True),
            "slippage": ParameterMetadata(ParameterRole.SYSTEM, is_static=True),
            "comment": ParameterMetadata(ParameterRole.SYSTEM, is_static=True),
        }
        
        # Feature switches (boolean parameters)
        self.feature_switches = {
            "use", "enable", "apply", "allow", "is", "has"
        }
        
        # Parameter relationships for ratio analysis
        self.ratio_relationships = {
            ("takeprofit", "stoploss"): (1.5, 3.0),  # Recommended TP:SL ratio range
            ("trailingstop", "trailingstart"): (1.2, 2.0),  # Trailing stop should be larger than start
        }
        
        # Parameter validation system
        self.alias_mapping: Dict[str, str] = {}
        self._initialize_parameter_metadata()
        
    def _initialize_parameter_metadata(self):
        """Initialize metadata for common EA parameters."""
        self.parameter_metadata = {}
        self.alias_mapping = {}
        
        # Initialize common parameters
        self._add_parameter("lots", ParameterRole.VOLUME, 0.1, 0.01, 100,
                          ["volume", "lot_size", "inp_lots", "fixed_lot"])
        self._add_parameter("stoploss", ParameterRole.STOP_LOSS, 100, 5, 1000,
                          ["sl", "stop_loss", "inp_stoploss"])
        self._add_parameter("takeprofit", ParameterRole.TAKE_PROFIT, 200, 5, 1000,
                          ["tp", "take_profit", "inp_takeprofit"])
        self._add_parameter("trailingstart", ParameterRole.TRAILING_STOP, 30, 5, 200,
                          ["trailing_start", "tsl_start"])
        self._add_parameter("trailingstop", ParameterRole.TRAILING_STOP, 50, 10, 300,
                          ["trailing_stop", "tsl_stop"])
        self._add_parameter("period", ParameterRole.PERIOD, 14, 1, 1000,
                          ["timeframe", "ma_period", "inp_period"])
        self._add_parameter("shift", ParameterRole.TECHNICAL, 0, 0, 100,
                          ["offset", "displacement"])
        self._add_parameter("magico", ParameterRole.SYSTEM, 0, 0, 999999,
                          ["magic", "magic_number"])
        
        # Parameter relationships
        self.parameter_relationships.update({
            # Moving Averages: Fast < Medium < Slow
            ("maFast_Period", "maMedium_Period"): (0.2, 0.8),
            ("maMedium_Period", "maSlow_Period"): (0.2, 0.8),
            
            # RSI Levels: Lower < Upper
            ("rsiLevelDn", "rsiLevelUp"): (0.3, 0.7),
            
            # ADX Levels: Buy/Sell < Main
            ("AdxLevelBuy", "AdxLevelMain"): (0.4, 0.9),
            ("AdxLevelSell", "AdxLevelMain"): (0.4, 0.9),
            
            # Risk Management
            ("userSLpips", "userTPpips"): (0.3, 0.7),  # SL should be smaller than TP
            ("userTslStep", "userTslDistance"): (0.05, 0.2),  # Step should be smaller than Distance
            ("userTslInitialStep", "userTslDistance"): (0.5, 2.0),  # Initial step relative to distance
            
            # Money Management
            ("userLots", "userBalancePer"): (0.1, 10.0)  # Lots should be proportional to risk
        })
        
        # Parameter groups for validation
        self.parameter_groups = {
            "moving_averages": {
                "params": ["maFast_Period", "maMedium_Period", "maSlow_Period"],
                "rules": [
                    ("maFast_Period", "maMedium_Period", 0.2, 0.8),
                    ("maMedium_Period", "maSlow_Period", 0.2, 0.8)
                ]
            },
            "adx_system": {
                "params": ["AdxPeriod", "AdxLevelMain", "AdxLevelBuy", "AdxLevelSell"],
                "rules": [
                    ("AdxLevelBuy", "AdxLevelMain", 0.4, 0.9),
                    ("AdxLevelSell", "AdxLevelMain", 0.4, 0.9)
                ]
            },
            "rsi_system": {
                "params": ["rsiPeriod", "rsiLevelUp", "rsiLevelDn"],
                "rules": [
                    ("rsiLevelDn", "rsiLevelUp", 0.3, 0.7)
                ]
            },
            "risk_management": {
                "params": ["userSLpips", "userTPpips", "userLots", "userBalancePer"],
                "rules": [
                    ("userSLpips", "userTPpips", 0.3, 0.7),
                    ("userLots", "userBalancePer", 0.1, 10.0)
                ]
            },
            "trailing_stop": {
                "params": ["userTslStep", "userTslDistance", "userTslInitialStep"],
                "rules": [
                    ("userTslStep", "userTslDistance", 0.05, 0.2),
                    ("userTslInitialStep", "userTslDistance", 0.5, 2.0)
                ]
            }
        }
        
    def _add_parameter(self, name: str, role: ParameterRole, default: Any,
                      min_val: Optional[float], max_val: Optional[float],
                      aliases: List[str]):
        """Add parameter metadata and update alias mapping."""
        self.parameter_metadata[name] = ParameterMetadata(role, default, min_val, max_val, set(aliases), is_static=False)
        for alias in aliases:
            self.alias_mapping[alias.lower()] = name
    
    def normalize_parameter_name(self, name: str) -> str:
        """Normalize parameter name using alias mapping."""
        return self.alias_mapping.get(name.lower(), name)
    
    def validate_parameter(self, name: str, value: Any) -> Tuple[bool, str, Any]:
        """Validate parameter value and return (is_valid, message, corrected_value)."""
        normalized_name = self.normalize_parameter_name(name)
        metadata = self.parameter_metadata.get(normalized_name)
        
        if not metadata:
            return True, "Parameter not in metadata", value
        
        try:
            value_float = float(value)
            if metadata.min_value is not None and value_float < metadata.min_value:
                return False, f"Value {value} below minimum {metadata.min_value}", metadata.min_value
            if metadata.max_value is not None and value_float > metadata.max_value:
                return False, f"Value {value} above maximum {metadata.max_value}", metadata.max_value
            return True, "Valid", value_float
        except ValueError:
            return False, f"Invalid numeric value: {value}", metadata.default_value
    
    def optimize_set_file(self, input_file: str, output_file: str) -> None:
        """Optimize a set file with strict lotsize and multiplikator rules."""
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        parameters = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith(';') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            name = name.strip()
            value = value.strip().strip('"')
            parameters[name] = value
        
        optimized = {}
        for name, value in parameters.items():
            lname = name.lower()
            lval = str(value).lower()
            # Lotsize rule: always static 0.1
            if any(x in lname for x in ["lot", "lotsize", "fixed_lot", "volume"]):
                optimized[name] = {"value": 0.1, "start": 0.1, "step": 0, "stop": 0.1, "static": True}
                continue
            # Multiplikator/martingale rule: always static 1 or disabled
            if any(x in lname for x in ["multi", "martin", "factor", "mul", "multiplier"]):
                if any(y in lval for y in ["disable", "deactive", "off"]):
                    optimized[name] = {"value": "disabled", "start": "disabled", "step": "", "stop": "disabled", "static": True}
                else:
                    try:
                        if "." in value:
                            optimized[name] = {"value": 1.0, "start": 1.0, "step": 0, "stop": 1.0, "static": True}
                        else:
                            optimized[name] = {"value": 1, "start": 1, "step": 0, "stop": 1, "static": True}
                    except Exception:
                        optimized[name] = {"value": 1, "start": 1, "step": 0, "stop": 1, "static": True}
                continue
            # Magic number: copy original line, never optimize
            if "magic" in lname:
                optimized[name] = {"value": value, "static": True, "raw": True}
                continue
            # Boolean values
            if lval in ['true', 'on', 'enable', '1']:
                optimized[name] = {"value": 1, "start": 1, "step": 0, "stop": 1}
                continue
            if lval in ['false', 'off', 'disable', '0']:
                optimized[name] = {"value": 0, "start": 0, "step": 0, "stop": 0}
                continue
            # Default: keep value and allow optimization
            try:
                numval = float(value) if '.' in value else int(value)
                start = numval * 0.7
                end = min(numval * 2.0, numval * 5.0)
                step_size = (end - start) / 10
                from math import log10, floor
                magnitude = 10 ** floor(log10(step_size)) if step_size > 0 else 1
                normalized = step_size / magnitude if magnitude else 1
                if normalized <= 1.5:
                    step_size = magnitude
                elif normalized <= 2.2:
                    step_size = 2 * magnitude
                elif normalized <= 3.5:
                    step_size = 2.5 * magnitude
                elif normalized <= 7:
                    step_size = 5 * magnitude
                else:
                    step_size = 10 * magnitude
                optimized[name] = {
                    "value": numval,
                    "start": start,
                    "step": step_size,
                    "stop": end
                }
            except Exception:
                optimized[name] = {"value": value, "start": value, "step": "", "stop": value}
        # Write output file
        with open(output_file, 'w', encoding='utf-8') as f:
            for line in lines:
                orig = line.strip()
                if not orig or orig.startswith(';') or '=' not in orig:
                    f.write(line)
                    continue
                name = orig.split('=', 1)[0].strip()
                if name in optimized:
                    opt = optimized[name]
                    # Magic number: copy original line exactly
                    if opt.get("raw"):
                        f.write(line)
                    # Lotsize/multiplier: always static
                    elif opt.get("static"):
                        f.write(f'{name}={opt["value"]}\n')
                    # Write in MetaTrader optimizer format
                    elif isinstance(opt["value"], str):
                        # For string/static values
                        f.write(f'{name}={opt["value"]}\n')
                    else:
                        # Optimized parameter: value||start||step||stop||Y
                        if opt["step"] and float(opt["step"]) > 0:
                            f.write(f'{name}={opt["value"]}||{opt["start"]}||{opt["step"]}||{opt["stop"]}||Y\n')
                        else:
                            # Static parameter
                            f.write(f'{name}={opt["value"]}\n')
                else:
                    f.write(line)

    def validate_parameter_relationships(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Validate relationships between parameters."""
        changes = []
        
        # Define parameter groups for validation
        parameter_groups = {
            "risk_management": {
                "params": ["stoploss", "takeprofit", "maximumrisk", "lots"],
                "rules": [
                    ("takeprofit", "stoploss", 1.5, 3.0),  # TP should be 1.5-3x SL
                    ("maximumrisk", "lots", 0.1, 5.0)  # Risk should be proportional to lot size
                ]
            },
            "trailing_system": {
                "params": ["trailingstop", "trailingstart", "trailingstep"],
                "rules": [
                    ("trailingstop", "trailingstart", 1.2, 2.0),  # Stop > Start
                    ("trailingstart", "trailingstep", 2.0, 10.0)  # Start > Step
                ]
            },
            "technical_indicators": {
                "params": ["period", "shift"],
                "rules": [
                    ("period", "shift", 2.0, 20.0)  # Period should be larger than shift
                ]
            }
        }
        
        # Validate each parameter group
        for group_name, group_config in parameter_groups.items():
            group_params = {p: parameters.get(p) for p in group_config["params"] if p in parameters}
            
            if not group_params:
                continue
                
            self.logger.debug(f"Validating {group_name} parameters: {group_params}")
            
            # Check parameter rules within group
            for param1, param2, min_ratio, max_ratio in group_config["rules"]:
                if param1 in group_params and param2 in group_params:
                    try:
                        value1 = float(group_params[param1])
                        value2 = float(group_params[param2])
                        
                        if value2 == 0:
                            self.logger.warning(f"Cannot validate ratio for {param1}/{param2}: denominator is zero")
                            continue
                            
                        ratio = value1 / value2
                        
                        if ratio < min_ratio:
                            new_value = value2 * min_ratio
                            changes.append({
                                "parameter": param1,
                                "original": value1,
                                "corrected": new_value,
                                "reason": f"Ratio with {param2} too low ({ratio:.2f} < {min_ratio})"
                            })
                            parameters[param1] = new_value
                            
                        elif ratio > max_ratio:
                            new_value = value2 * max_ratio
                            changes.append({
                                "parameter": param1,
                                "original": value1,
                                "corrected": new_value,
                                "reason": f"Ratio with {param2} too high ({ratio:.2f} > {max_ratio})"
                            })
                            parameters[param1] = new_value
                            
                    except (ValueError, ZeroDivisionError) as e:
                        self.logger.warning(f"Error validating {param1}-{param2} relationship: {str(e)}")
        
        return changes
        
    def optimize_parameter_group(self, group_params: Dict[str, Any], group_rules: List[Tuple]) -> Dict[str, Any]:
        """Optimize a group of related parameters together."""
        optimized = group_params.copy()
        
        # Sort parameters by role priority
        param_priorities = {
            ParameterRole.STOP_LOSS: 1,
            ParameterRole.TAKE_PROFIT: 2,
            ParameterRole.TRAILING_STOP: 3,
            ParameterRole.VOLUME: 4,
            ParameterRole.RISK: 5,
            ParameterRole.PERIOD: 6,
            ParameterRole.TECHNICAL: 7,
            ParameterRole.UNKNOWN: 8
        }
        
        sorted_params = sorted(
            group_params.items(),
            key=lambda x: param_priorities.get(
                self.parameter_metadata.get(x[0], ParameterMetadata(ParameterRole.UNKNOWN)).role,
                999
            )
        )
        
        # Optimize parameters in priority order
        for param_name, value in sorted_params:
            metadata = self.parameter_metadata.get(param_name)
            if not metadata:
                continue
                
            # Get dependent parameters that this parameter influences
            dependent_params = [
                (p1, p2, min_r, max_r)
                for p1, p2, min_r, max_r in group_rules
                if p1 == param_name or p2 == param_name
            ]
            
            # Calculate optimal value considering relationships
            optimal_value, modified = self.optimize_with_relationships(
                param_name,
                float(value),
                optimized,
                dependent_params,
                metadata
            )
            
            if modified:
                optimized[param_name] = optimal_value
                
        return optimized
        
    def optimize_with_relationships(self, param_name: str, current_value: float,
                                  related_params: Dict[str, Any], relationships: List[Tuple],
                                  metadata: ParameterMetadata) -> Tuple[float, bool]:
        """Optimize a parameter while considering its relationships with other parameters."""
        if not relationships:
            return current_value, False
            
        valid_values = []
        
        # Calculate valid range based on relationships
        for p1, p2, min_ratio, max_ratio in relationships:
            if p1 == param_name and p2 in related_params:
                # Parameter is the numerator
                other_value = float(related_params[p2])
                min_valid = other_value * min_ratio
                max_valid = other_value * max_ratio
                valid_values.append((min_valid, max_valid))
                
            elif p2 == param_name and p1 in related_params:
                # Parameter is the denominator
                other_value = float(related_params[p1])
                min_valid = other_value / max_ratio
                max_valid = other_value / min_ratio
                valid_values.append((min_valid, max_valid))
        
        # Find intersection of all valid ranges
        final_min = max(v[0] for v in valid_values) if valid_values else metadata.min_value or 0
        final_max = min(v[1] for v in valid_values) if valid_values else metadata.max_value or float('inf')
        
        # Clamp current value to valid range
        return max(min(current_value, final_max), final_min), current_value != max(min(current_value, final_max), final_min)

    def get_parameter_metadata(self, name: str) -> ParameterMetadata:
        """Get metadata for a parameter with enhanced role detection."""
        name_lower = name.lower()
        
        # Risk management parameters
        if any(keyword in name_lower for keyword in ['risk', 'lot', 'volume']):
            return ParameterMetadata(
                role=ParameterRole.RISK,
                min_value=0.01,
                max_value=100.0,
                default_value=0.1
            )
            
        # Position parameters
        if any(keyword in name_lower for keyword in ['stop', 'sl', 'tp', 'profit', 'price']):
            return ParameterMetadata(
                role=ParameterRole.POSITIONING,
                min_value=0.0,
                max_value=10000.0,
                default_value=100.0
            )
            
        # Trailing parameters
        if any(keyword in name_lower for keyword in ['trail']):
            return ParameterMetadata(
                role=ParameterRole.TRAILING_STOP,
                min_value=0.0,
                max_value=1000.0,
                default_value=0.0
            )
            
        # Breakeven parameters
        if 'breakeven' in name_lower or 'be_' in name_lower:
            return ParameterMetadata(
                role=ParameterRole.BREAKEVEN,
                min_value=0.0,
                max_value=1000.0,
                default_value=0.0
            )
            
        # Technical parameters
        if any(keyword in name_lower for keyword in ['ma', 'rsi', 'cci', 'period', 'shift']):
            return ParameterMetadata(
                role=ParameterRole.TECHNICAL,
                min_value=1.0,
                max_value=10000.0,
                default_value=14.0
            )
            
        # Feature switches
        if any(keyword in name_lower for keyword in ['use_', 'enable_', 'is_', 'allow_']):
            return ParameterMetadata(
                role=ParameterRole.FEATURE_SWITCH,
                min_value=0.0,
                max_value=1.0,
                default_value=0.0,
                is_static=True
            )
            
        # System parameters (catch-all)
        return ParameterMetadata(
            role=ParameterRole.SYSTEM,
            min_value=-10000.0,
            max_value=10000.0,
            default_value=0.0
        )

    def get_parameter_priority(self, name: str) -> int:
        """Get priority score for a parameter."""
        name_lower = name.lower()
        
        # Check exact matches
        if name_lower in self.param_priorities:
            return self.param_priorities[name_lower]
            
        # Check partial matches
        for param, priority in self.param_priorities.items():
            if param in name_lower:
                return priority
                
        return 0  # Default priority

    def safe_float(self, value: str, default: float = 0.0) -> float:
        """Safely convert value to float with enhanced validation."""
        try:
            # Handle special cases
            if value.lower() in ('true', 'false'):
                return float(value.lower() == 'true')
            
            # Handle optimized values
            if '||' in value:
                value = value.split('||')[0]
                
            # Convert to float
            result = float(value)
            
            # Validate result
            if math.isinf(result) or math.isnan(result):
                return default
                
            return result
            
        except (ValueError, TypeError, AttributeError):
            return default

    def validate_mt5_constraints(self, name: str, value: float) -> float:
        """Validate and adjust value according to MT5 constraints."""
        name_lower = name.lower()
        
        # Find matching constraint
        for limit_key, (min_val, max_val) in self.mt5_limits.items():
            if limit_key in name_lower:
                # Apply min/max constraints
                value = max(min_val, min(value, max_val))
                
                # Special risk handling
                if limit_key == "risk" and value > 50:
                    value = 30  # Conservative risk limit
                    
                # Ensure minimum lot size
                if limit_key == "lots" and value < 0.01:
                    value = 0.01
                    
                break
                
        return value  # No specific constraints found

    def get_min_step(self, name: str) -> float:
        """Get minimum step size from config."""
        name_lower = name.lower()
        
        # Find matching constraint
        for key, constraint in self.mt5_limits.items():
            if key in name_lower:
                return constraint['step_min']
                
        # Fallback defaults
        if any(x in name_lower for x in ['risk', 'lot']):
            return 0.01
        return 1.0

    def smooth_steps(self, start: float, end: float, preferred_steps: int = 25) -> float:
        """Calculate smoothed step size based on value range."""
        if start >= end:
            return max(0.01, start * 0.1)  # At least 1% of start value
            
        raw_step = (end - start) / preferred_steps
        
        # Ensure minimum step size based on value magnitude
        min_step = max(0.01, min(start, end) * 0.01)  # At least 1% of smaller value
        raw_step = max(raw_step, min_step)
        
        # Round to nearest power of 10
        magnitude = math.floor(math.log10(raw_step))
        normalized = raw_step / (10 ** magnitude)
        
        # Choose appropriate step size
        if normalized <= 1:
            smoothed = 1
        elif normalized <= 2:
            smoothed = 2
        elif normalized <= 5:
            smoothed = 5
        else:
            smoothed = 10
            
        return max(min_step, smoothed * (10 ** magnitude))

    def detect_parameter_type(self, name: str, value: str) -> str:
        """Detect parameter type with enhanced validation."""
        try:
            # Handle boolean values
            if value.lower() in ('true', 'false'):
                return 'bool'
                
            # Handle optimized values
            if '||' in value:
                value = value.split('||')[0]
                
            # Try float conversion
            float_val = float(value)
            
            # Check if it's actually an integer
            if float_val.is_integer():
                return 'int'
                
            return 'float'
            
        except (ValueError, TypeError, AttributeError):
            return 'string'

    def safe_value(self, value: float, param_name: str) -> float:
        """Apply safety limits to parameter values."""
        param_lower = param_name.lower()
        
        # Check MT5 limits
        for limit_key, (min_val, max_val) in self.mt5_limits.items():
            if limit_key in param_lower:
                # Apply min/max constraints
                value = max(min_val, min(value, max_val))
                
                # Special risk handling
                if limit_key == "risk" and value > 50:
                    value = 30  # Conservative risk limit
                    
                # Ensure minimum lot size
                if limit_key == "lots" and value < 0.01:
                    value = 0.01
                    
                break
                
        return value

    def check_parameter_diversity(self, params: Dict[str, str]) -> Set[str]:
        """Check for parameter duplications and dependencies."""
        skip_params = set()
        
        # Check group diversity
        for group_name, group_params in self.param_groups.items():
            group_values = [float(params.get(p, '0')) for p in group_params if p in params]
            
            # If all parameters in group are 0, skip the whole group
            if group_values and all(v == 0 for v in group_values):
                skip_params.update(group_params)
                logger.info(f"Skipping {group_name} group - all values are 0")
        
        # Check parameter dependencies
        for (param1, param2), check_func in self.param_dependencies.items():
            if param1 in params and param2 in params:
                try:
                    val1 = float(params[param1])
                    val2 = float(params[param2])
                    if not check_func(val1, val2):
                        logger.warning(f"Dependency violation: {param1}={val1}, {param2}={val2}")
                        # Skip the less important parameter
                        skip_params.add(param2)
                except ValueError:
                    continue
                    
        return skip_params

    def calculate_optimization_size(self, params: Dict[str, str], skip_params: Set[str]) -> Tuple[List[str], int]:
        """Calculate optimization size and return prioritized parameters."""
        # Get optimizable parameters
        opt_params = [(name, self.get_parameter_priority(name)) 
                     for name in params 
                     if name not in skip_params and 
                     not self.get_parameter_metadata(name).is_static]
        
        # Sort by priority (highest first)
        opt_params.sort(key=lambda x: x[1], reverse=True)
        
        # Start with highest priority parameters
        selected_params = []
        total_combinations = 1
        max_combinations = 1_000_000  # Reasonable limit
        
        for name, _ in opt_params:
            # Calculate steps for this parameter
            param_type = self.detect_parameter_type(name, params[name])
            if param_type == 'int':
                steps = min(10, max(2, int(float(params[name]) * 0.6)))  # At least 2 steps
            else:
                steps = min(20, max(3, int(float(params[name]) * 0.4)))  # At least 3 steps
                    
            # Check if adding this parameter would exceed limit
            new_combinations = total_combinations * steps
            if new_combinations <= max_combinations:
                total_combinations = new_combinations
                selected_params.append(name)
            else:
                break
                    
        return selected_params, int(total_combinations)  # Convert to int

    def evaluate_rules(self, params: Dict[str, str]) -> Dict[str, List[str]]:
        """Evaluate all rules for the parameters."""
        float_params = {
            name: self.safe_float(value) 
            for name, value in params.items()
        }
        
        violations = defaultdict(list)
        for rule in self.rules:
            if not rule.evaluate(float_params):
                for param in rule.apply_if:
                    violations[param].append(rule.name)
                    
        return dict(violations)

    def _create_optimization_analysis(self, version_path: str, source_name: str, 
                                   original_params: Dict[str, str], optimized_params: Dict[str, str], 
                                   skip_params: Set[str], combinations: int, 
                                   selected_params: List[str], is_too_large: bool) -> Dict[str, Any]:
        """Create detailed analysis with enhanced metadata."""
        analysis = {
            "timestamp": datetime.now().isoformat(),
            "file_path": version_path,
            "source_file": f"{source_name}.set",
            "parameter_groups": defaultdict(list),
            "ratios": {},
            "optimization_summary": {
                "total_parameters": len(original_params),
                "optimized": len(selected_params),
                "static": sum(1 for v in optimized_params.values() if '||Y' not in v),
                "skipped": len(skip_params),
                "combinations": combinations,
                "estimated_time": f"{combinations / 100000:.1f} minutes",
                "selected_parameters": selected_params,
                "steps_per_parameter": {},
                "is_too_large": is_too_large,
                "fallback_strategy": "top_6_params" if is_too_large else None
            }
        }
        
        # Calculate steps per parameter
        for name in selected_params:
            try:
                value = optimized_params[name]
                if '||' in value:
                    _, start, step, end, _ = value.split('||')
                    start, step, end = float(start), float(step), float(end)
                    steps = int((end - start) / step) + 1
                    analysis["optimization_summary"]["steps_per_parameter"][name] = steps
            except (ValueError, IndexError):
                continue
        
        # Group parameters by role
        for name, value in optimized_params.items():
            role = self.get_parameter_metadata(name).role
            analysis["parameter_groups"][role.value].append({
                "name": name,
                "original": original_params.get(name, "N/A"),
                "optimized": value,
                "type": self.detect_parameter_type(name, str(analysis['original_values'].get(name, ''))),
                "priority": self.get_parameter_priority(name)
            })
            
        # Calculate important ratios
        if "takeprofit" in optimized_params and "stoploss" in optimized_params:
            try:
                tp = float(optimized_params["takeprofit"].split("||")[0])
                sl = float(optimized_params["stoploss"].split("||")[0])
                analysis["ratios"]["risk_reward"] = round(tp / sl, 2) if sl > 0 else "N/A"
            except (ValueError, IndexError):
                analysis["ratios"]["risk_reward"] = "N/A"
            
        # Save analysis
        analysis_path = version_path.replace('.set', '_analysis.json')
        with open(analysis_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, cls=EnumEncoder)

    def export_audit_sheet(self, version_path: str, original_params: Dict[str, str], 
                          optimized_params: Dict[str, str], skip_params: Set[str]) -> None:
        """Export detailed audit sheet for optimization."""
        audit_path = version_path.replace('.set', '_audit.csv')
        
        with open(audit_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'parameter_name', 'original', 'optimized', 'start', 'step', 'end',
                'priority', 'type', 'role', 'confidence', 'diversity', 'skipped'
            ])
            
            for name in sorted(original_params.keys()):
                original = original_params[name]
                optimized = optimized_params[name]
                param_type = self.detect_parameter_type(name, original)
                metadata = self.get_parameter_metadata(name)
                
                # Extract optimization values if present
                if '||' in optimized:
                    parts = optimized.split('||')
                    value, start, step, end = parts[:4]
                    diversity = self.calculate_diversity_score(
                        float(start), float(end), float(step))
                else:
                    value, start, step, end = optimized, '', '', ''
                    diversity = 0.0
                    
                confidence = self.calculate_confidence_score(
                    name, self.safe_float(value.split('||')[0] if '||' in value else value), 
                    metadata)
                    
                writer.writerow([
                    name,
                    original,
                    value,
                    start,
                    step,
                    end,
                    self.get_parameter_priority(name),
                    param_type,
                    metadata.role.value,
                    confidence,
                    f"{diversity:.2f}",
                    name in skip_params
                ])

    def export_for_ml(self, version_path: str, analysis: Dict[str, Any]) -> None:
        """Export optimization data in ML-ready format."""
        ml_path = version_path.replace('.set', '_ml.json')
        
        # Extract features for ML
        ml_data = {
            'metadata': {
                'timestamp': analysis['timestamp'],
                'source_file': analysis['source_file'],
                'total_params': analysis['optimization_summary']['total_parameters'],
                'optimized_params': analysis['optimization_summary']['optimized'],
                'combinations': analysis['optimization_summary']['combinations']
            },
            'parameter_features': defaultdict(dict)
        }
        
        # Group parameters by role
        for role, params in analysis['parameter_groups'].items():
            for param in params:
                param_data = {
                    'role': role,
                    'priority': self.get_parameter_priority(param),
                    'type': self.detect_parameter_type(param, str(analysis['original_values'].get(param, ''))),
                    'is_optimized': '||Y' in str(analysis['optimized_values'].get(param, '')),
                    'confidence': self.calculate_confidence_score(
                        param, 
                        self.safe_float(str(analysis['original_values'].get(param, 0))),
                        self.get_parameter_metadata(param)
                    )
                }
                
                # Extract optimization ranges if present
                opt_value = str(analysis['optimized_values'].get(param, ''))
                if '||' in opt_value:
                    parts = opt_value.split('||')
                    param_data.update({
                        'value': float(parts[0]),
                        'range_start': float(parts[1]),
                        'range_end': float(parts[3]),
                        'diversity': self.calculate_diversity_score(
                            float(parts[1]), float(parts[3]), float(parts[2]))
                    })
                else:
                    param_data.update({
                        'value': self.safe_float(opt_value),
                        'diversity': 0.0
                    })
                    
                ml_data['parameter_features'][param] = param_data
        
        # Save ML-ready data
        with open(ml_path, 'w', encoding='utf-8') as f:
            json.dump(ml_data, f, indent=2)

    def create_recovery_point(self, version_path: str, analysis: Dict[str, Any], 
                            params: Dict[str, str], optimized: Dict[str, str]) -> None:
        """Create recovery point for optimization state."""
        recovery_path = version_path.replace('.set', '_recovery.json')
        
        recovery_data = {
            'timestamp': datetime.now().isoformat(),
            'version_path': version_path,
            'analysis': analysis,
            'params': params,
            'optimized_params': optimized,
            'optimization_state': {
                'processed_params': self.processed_params,
                'optimized_params': self.optimized_params,
                'skipped_params': self.skipped_params
            }
        }
        
        with open(recovery_path, 'w', encoding='utf-8') as f:
            json.dump(recovery_data, f, indent=2)
            
    def load_recovery_point(self, recovery_path: str) -> Optional[Dict[str, Any]]:
        """Load recovery point if it exists."""
        try:
            if not os.path.exists(recovery_path):
                return None
                
            with open(recovery_path, 'r', encoding='utf-8') as f:
                recovery_data = json.load(f)
                
            # Validate recovery data
            required_keys = {'timestamp', 'version_path', 'analysis', 'params', 'optimized_params'}
            if not all(k in recovery_data for k in required_keys):
                logger.warning(f"Invalid recovery data in {recovery_path}")
                return None
                
            # Check if recovery is too old (> 24h)
            recovery_time = datetime.fromisoformat(recovery_data['timestamp'])
            if (datetime.now() - recovery_time).total_seconds() > 86400:
                logger.warning(f"Recovery data too old in {recovery_path}")
                return None
                
            return recovery_data
            
        except Exception as e:
            logger.error(f"Error loading recovery data: {str(e)}")
            return None
            
    def resume_optimization(self, recovery_data: Dict[str, Any]) -> bool:
        """Resume optimization from recovery point."""
        try:
            # Restore optimization state
            state = recovery_data['optimization_state']
            self.processed_params = state['processed_params']
            self.optimized_params = state['optimized_params']
            self.skipped_params = state['skipped_params']
            
            # Continue optimization
            params = recovery_data['params']
            optimized = recovery_data['optimized_params']
            version_path = recovery_data['version_path']
            
            # Get remaining parameters
            remaining = set(params.keys()) - set(optimized.keys())
            if not remaining:
                logger.info("No remaining parameters to optimize")
                return True
                
            logger.info(f"Resuming optimization with {len(remaining)} remaining parameters")
            
            # Optimize remaining parameters
            for name in remaining:
                if name not in optimized:
                    optimized[name] = self.optimize_parameter(name, params[name], params)
                    
            # Save final results
            with open(version_path, 'w', encoding='utf-8') as f:
                # Add source comment
                f.write(f"; Optimized from: {os.path.splitext(os.path.basename(version_path))[0]}.set\n")
                f.write(f"; Generated on: {datetime.now().isoformat()}\n")
                f.write(f"; Parameters: {len(remaining)} optimized, {len(recovery_data['params']) - len(remaining)} static\n\n")
                
                for name, value in optimized.items():
                    f.write(f"{name}={value}\n")
                    
            # Update analysis
            analysis = recovery_data['analysis']
            analysis['timestamp'] = datetime.now().isoformat()
            analysis['optimization_summary']['resumed'] = True
            
            analysis_path = version_path.replace('.set', '_analysis.json')
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, cls=EnumEncoder)
                
            return True
            
        except Exception as e:
            logger.error(f"Error resuming optimization: {str(e)}")
            return False

    def track_parameter_evolution(self, param_name: str, history_path: str) -> Dict[str, Any]:
        """Track parameter value evolution across optimizations with enhanced metrics."""
        evolution = {
            'values': [],
            'ranges': [],
            'metrics': [],
            'market_regimes': [],
            'timestamps': []
        }
        
        try:
            # Load existing history
            if os.path.exists(history_path):
                with open(history_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = {'optimizations': []}
                
            # Extract parameter evolution
            for entry in history['optimizations']:
                if param_name in entry['parameters']:
                    value = entry['parameters'][param_name]
                    timestamp = entry['timestamp']
                    metrics = entry.get('metrics', {})
                    regime = entry.get('market_regime', 'unknown')
                    
                    # Parse parameter value
                    if '||' in value:
                        val, start, step, end = value.split('||')[:4]
                        evolution['values'].append(float(val))
                        evolution['ranges'].append({
                            'start': float(start),
                            'step': float(step),
                            'end': float(end)
                        })
                    else:
                        evolution['values'].append(float(value))
                        evolution['ranges'].append(None)
                        
                    # Add metrics and context
                    evolution['metrics'].append({
                        'profit': metrics.get('profit', 0),
                        'trades': metrics.get('trades', 0),
                        'win_rate': metrics.get('win_rate', 0),
                        'sharpe': metrics.get('sharpe', 0)
                    })
                    evolution['market_regimes'].append(regime)
                    evolution['timestamps'].append(timestamp)
            
            # Calculate evolution statistics
            if evolution['values']:
                evolution['statistics'] = {
                    'mean': np.mean(evolution['values']),
                    'std': np.std(evolution['values']),
                    'min': min(evolution['values']),
                    'max': max(evolution['values']),
                    'trend': np.polyfit(range(len(evolution['values'])), evolution['values'], 1)[0],
                    'regime_performance': defaultdict(list)
                }
                
                # Calculate regime-specific performance
                for regime, metrics in zip(evolution['market_regimes'], evolution['metrics']):
                    evolution['statistics']['regime_performance'][regime].append(metrics['profit'])
                    
                evolution['statistics']['best_regimes'] = {
                    regime: np.mean(profits)
                    for regime, profits in evolution['statistics']['regime_performance'].items()
                }
            
            return evolution
            
        except Exception as e:
            logger.error(f"Error tracking parameter evolution: {str(e)}")
            return evolution

    def update_parameter_history(self, version_path: str, params: Dict[str, str], 
                               metrics: Dict[str, float], regime: str) -> None:
        """Update parameter history with new optimization results."""
        history_path = os.path.join(os.path.dirname(version_path), 'parameter_history.json')
        
        try:
            # Load existing history
            if os.path.exists(history_path):
                with open(history_path, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            else:
                history = {'optimizations': []}
                
            # Add new optimization entry
            entry = {
                'timestamp': datetime.now().isoformat(),
                'parameters': params,
                'metrics': metrics,
                'market_regime': regime,
                'source_file': os.path.basename(version_path)
            }
            
            history['optimizations'].append(entry)
            
            # Keep only last 100 optimizations
            if len(history['optimizations']) > 100:
                history['optimizations'] = history['optimizations'][-100:]
                
            # Save updated history
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error updating parameter history: {str(e)}")

    def detect_market_regime(self, metrics: Dict[str, float]) -> str:
        """Detect market regime based on optimization metrics."""
        volatility = metrics.get('volatility', 0)
        trend = metrics.get('trend', 0)
        
        if volatility > 0.2:  # High volatility
            if abs(trend) > 0.1:
                return 'volatile_trending'
            return 'volatile_ranging'
        else:  # Low volatility
            if abs(trend) > 0.1:
                return 'stable_trending'
            return 'stable_ranging'

    def generate_ml_features(self, params: Dict[str, str], 
                           metrics: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Generate advanced features for ML training."""
        features = {
            'parameter_features': defaultdict(dict),
            'combined_features': {},
            'metadata': {
                'timestamp': datetime.now().isoformat(),
                'total_params': len(params),
                'optimized_count': sum(1 for v in params.values() if '||Y' in v)
            }
        }
        
        # Extract parameter-specific features
        for name, value in params.items():
            param_data = self._extract_parameter_features(name, value)
            features['parameter_features'][name] = param_data
            
        # Generate combined features
        features['combined_features'] = self._generate_combined_features(params)
        
        # Add performance metrics if available
        if metrics:
            features['performance'] = {
                'profit': metrics.get('profit', 0),
                'trades': metrics.get('trades', 0),
                'win_rate': metrics.get('win_rate', 0),
                'sharpe': metrics.get('sharpe', 0),
                'drawdown': metrics.get('drawdown', 0)
            }
            
        return features
        
    def _extract_parameter_features(self, name: str, value: str) -> Dict[str, Any]:
        """Extract features for a single parameter."""
        metadata = self.get_parameter_metadata(name)
        param_type = self.detect_parameter_type(name, value)
        
        # Base features
        features = {
            'role': metadata.role.value,
            'type': param_type,
            'is_optimized': '||Y' in value,
            'confidence': self.calculate_confidence_score(
                name, self.safe_float(value.split('||')[0] if '||' in value else value), 
                metadata)
        }
        
        # Add one-hot encoded role
        for role in ParameterRole:
            features[f'role_{role.value}'] = int(metadata.role == role)
            
        # Extract numeric features if optimized
        if '||' in value:
            val, start, step, end = map(float, value.split('||')[:4])
            features.update({
                'value': val,
                'range_start': float(start),
                'range_end': float(end),
                'range_width': float(end) - float(start),
                'step_size': float(step),
                'step_ratio': float(step) / (float(end) - float(start)) if float(end) > float(start) else 0,
                'value_position': (float(val) - float(start)) / (float(end) - float(start)) 
                                if float(end) > float(start) else 0,
                'relative_range': (float(end) - float(start)) / float(start) if float(start) > 0 else 0
            })
        else:
            val = self.safe_float(value)
            features.update({
                'value': val,
                'range_width': 0,
                'step_ratio': 0,
                'value_position': 0,
                'relative_range': 0
            })
            
        return features
        
    def _generate_combined_features(self, params: Dict[str, str]) -> Dict[str, float]:
        """Generate combined features from multiple parameters."""
        combined = {}
        
        # Extract numeric values
        values = {
            name: self.safe_float(value.split('||')[0] if '||' in value else value)
            for name, value in params.items()
        }
        
        # Calculate common ratios
        if 'takeprofit' in values and 'stoploss' in values and values['stoploss'] != 0:
            combined['tp_sl_ratio'] = values['takeprofit'] / values['stoploss']
            
        if 'risk' in values and 'lots' in values:
            combined['risk_exposure'] = values['risk'] * values['lots']
            
        if 'trailing_start' in values and 'trailing_step' in values and values['trailing_step'] != 0:
            combined['trailing_ratio'] = values['trailing_start'] / values['trailing_step']
            
        # Calculate optimization intensity
        optimized_count = sum(1 for v in params.values() if '||Y' in v)
        combined['optimization_ratio'] = optimized_count / len(params)
        
        # Calculate parameter type distributions
        type_counts = defaultdict(int)
        for name in params:
            param_type = self.detect_parameter_type(name, params[name])
            type_counts[param_type] += 1
        
        for param_type, count in type_counts.items():
            combined[f'{param_type}_ratio'] = count / len(params)
            
        return combined
        
    def export_ml_dataset(self, version_path: str, features: Dict[str, Any], 
                         format: str = 'json') -> None:
        """Export ML-ready dataset in specified format."""
        base_path = version_path.replace('.set', f'_ml.{format}')
        
        try:
            if format == 'json':
                with open(base_path, 'w', encoding='utf-8') as f:
                    json.dump(features, f, indent=2)
                    
            elif format == 'csv':
                # Flatten features for CSV
                flat_data = []
                
                # Add parameter features
                for param_name, param_features in features['parameter_features'].items():
                    row = {'parameter': param_name}
                    row.update({f'param_{k}': v for k, v in param_features.items()})
                    flat_data.append(row)
                    
                # Write to CSV
                if flat_data:
                    with open(base_path, 'w', newline='', encoding='utf-8') as f:
                        writer = csv.DictWriter(f, fieldnames=flat_data[0].keys())
                        writer.writeheader()
                        writer.writerows(flat_data)
                        
            elif format == 'npz':
                # Convert to numpy arrays for ML
                param_features = []
                param_names = []
                
                for param_name, features in features['parameter_features'].items():
                    numeric_features = [v for v in features.values() if isinstance(v, (int, float))]
                    if numeric_features:
                        param_features.append(numeric_features)
                        param_names.append(param_name)
                        
                if param_features:
                    np.savez(base_path,
                            features=np.array(param_features),
                            names=np.array(param_names),
                            combined=np.array(list(features['combined_features'].values())))
                            
        except Exception as e:
            logger.error(f"Error exporting ML dataset: {str(e)}")

    def batch_process_directory(self, input_dir: str, output_dir: str) -> None:
        """Process all .set files in a directory."""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        
        # Find all .set files
        set_files = list(input_path.glob('**/*.set'))
        self.logger.info(f"Found {len(set_files)} .set files to process")
        
        success_count = 0
        fail_count = 0
        skip_count = 0
        failed_files = []
        
        for set_file in set_files:
            try:
                # Read input file
                params = self.read_set_file(set_file)
                
                # Create output path
                base_name = set_file.stem
                if base_name.endswith('_standard'):
                    base_name = base_name[:-9]  # Remove '_standard'
                output_name = f"{base_name}_otp.set"
                output_file = output_path / output_name
                
                # Optimize and write parameters
                self.write_set_file(output_file, params)
                
                self.logger.info(f"Successfully optimized {set_file.name} -> {output_name}")
                success_count += 1
                
            except Exception as e:
                self.logger.error(f"Error processing {set_file}: {str(e)}")
                failed_files.append(set_file.name)
                fail_count += 1
                
        print("\nOptimization Complete!")
        print(f"Successfully processed: {success_count} files")
        print(f"Failed: {fail_count} files")
        print(f"Skipped: {skip_count} files")
        
        if failed_files:
            print("\nFailed files:")
            for file in failed_files:
                print(f"- {file}")

    def process_set_file(self, input_path: Path) -> Dict[str, Any]:
        """Process a single .set file and create an optimized version."""
        try:
            # Read input file
            with open(input_path, 'r') as f:
                content = f.read()
            
            # Optimize parameters
            optimized_content = self.optimize_parameters(content)
            
            # Create output path
            base_name = input_path.stem
            if base_name.endswith('_standard'):
                base_name = base_name[:-9]  # Remove '_standard'
            output_name = f"{base_name}_otp.set"
            output_path = input_path.parent / 'optimized' / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write optimized content
            with open(output_path, 'w') as f:
                f.write(optimized_content)
                
            self.logger.info(f"Successfully optimized {input_path.name} -> {output_name}")
            return {'success': True, 'message': 'Optimization successful'}
            
        except Exception as e:
            self.logger.error(f"Error processing {input_path}: {str(e)}")
            return {'success': False, 'message': str(e)}

    def estimate_combinations(self, selected_params: List[str], params: Dict[str, str]) -> int:
        """Estimate combinations for selected parameters."""
        total = 1
        for name in selected_params:
            try:
                value = self.safe_float(params[name], 1.0)
                param_type = self.detect_parameter_type(name, params[name])
                if param_type == 'int':
                    steps = min(10, max(2, int(value * 0.6)))  # At least 2 steps
                else:
                    steps = min(20, max(3, int(value * 0.4)))  # At least 3 steps
                    
                # Check if adding this parameter would exceed limit
                new_combinations = total * steps
                if new_combinations <= 1_000_000:
                    total = new_combinations
                else:
                    break
                    
            except (ValueError, TypeError):
                continue
        return total

    def optimize_parameter(self, name: str, value: Any, params: Dict[str, Any], metadata: Optional[ParameterMetadata] = None) -> Tuple[Any, bool]:
        """Optimize a single parameter while considering its relationships."""
        try:
            # Get or create metadata
            if metadata is None:
                metadata = self.get_parameter_metadata(name)
                
            # Convert value to float if possible
            try:
                current_value = float(value)
            except (ValueError, TypeError):
                return value, False
                
            # Apply MT5 constraints
            current_value = self.validate_mt5_constraints(name, current_value)
            
            # Get parameter role
            role = metadata.role
            
            # Calculate optimization ranges based on role
            if role == ParameterRole.STOP_LOSS:
                start = max(30, current_value * 0.6)  # Mindestens 20 Pips
                end = min(70, current_value * 1.4)   # Maximal 500 Pips
                step = 1 if current_value <= 50 else 5
            elif role == ParameterRole.TAKE_PROFIT:
                start = max(70, current_value * 0.8)  # Mindestens 20 Pips
                end = min(130, current_value * 1.6)  # Maximal 1000 Pips
                step = 3 if current_value <= 50 else 15
            elif role == ParameterRole.TRAILING_STOP:
                start = 0
                end = current_value * 2.0
                step = 1
            elif role == ParameterRole.VOLUME:
                start = max(0.1, current_value * 0.8)
                end = min(0.15, current_value * 1.2)
                step = 0.05
            elif role == ParameterRole.PERIOD:
                if current_value <= 10:  # Schnelle Perioden
                    start = 0
                    end = 20
                    step = 1
                elif current_value <= 30:  # Mittlere Perioden
                    start = 0
                    end = 60
                    step = 2
                else:  # Langsame Perioden
                    start = 0
                    end = current_value * 2.5
                    step = 5
            elif role == ParameterRole.TECHNICAL:
                if 'shift' in name.lower():
                    start = 0
                    end = 10
                    step = 1
                elif 'magic' in name.lower():
                    start = 10
                    end = 999999999
                    step = 1000000
                elif 'lots' in name.lower():
                    start = 0.01
                    end = current_value * 3.0
                    step = 0.01
                elif 'count' in name.lower():
                    start = 0
                    end = max(20, current_value * 2)
                    step = 1
                else:
                    start = current_value * 0.5
                    end = current_value * 2.0
                    if current_value <= 1:
                        step = 0.1
                    elif current_value <= 10:
                        step = 0.5
                    elif current_value <= 50:
                        step = 1
                    else:
                        step = 5
            else:
                # Default optimization
                start = current_value * 0.5
                end = current_value * 2.0
                step = (end - start) / 10
                
            # Round values appropriately
            start = round(start, 2)
            end = round(end, 2)
            step = round(step, 2)
            
            # Format MT5 optimization string
            opt_string = f"{start}||{step}||{end}||Y"
            
            return opt_string, True
            
        except Exception as e:
            self.logger.warning(f"Error optimizing parameter {name}: {str(e)}")
            return value, False

    def write_set_file(self, output_path: Path, params: Dict[str, Any]) -> None:
        """Write parameters to a .set file."""
        try:
            with open(output_path, 'w') as f:
                for name, value in params.items():
                    if name.startswith('_comment_'):
                        f.write(f"{value}\n")
                        continue
                        
                    if isinstance(value, dict):
                        param_type = value.get('type', 'string')
                        current_value = value['value']
                        
                        # Spezielle Parameter nicht optimieren
                        if ('method' in name.lower() or 
                            'applied_price' in name.lower() or
                            'mode' in name.lower() or
                            'risk' in name.lower() or
                            'magic' in name.lower() or  # Magic Number nicht optimieren
                            name.lower() in ['usetrailing', 'usemartingale', 'usetakeprofit', 'usestoploss', 
                                           'inptakehalfprofit', 'inpprintlog', 'intlotorrisk']):
                            f.write(f"{name}={current_value}\n")
                            continue
                            
                        # Lot-Size spezifisch behandeln
                        if 'lots' in name.lower() or 'volume' in name.lower():
                            if 'multiplier' in name.lower():
                                # Lot-Multiplikatoren auf 1 setzen oder deaktivieren
                                if param_type == 'bool':
                                    f.write(f"{name}=false\n")
                                else:
                                    f.write(f"{name}=1\n")
                            else:
                                # Normale Lot-Size auf 0.1 setzen
                                f.write(f"{name}=0.1\n")
                            continue
                            
                        # Optimierungsbereich berechnen
                        try:
                            if param_type == 'bool':
                                # Boolean-Werte nicht optimieren
                                f.write(f"{name}={current_value}\n")
                            elif param_type in ['float', 'int']:
                                current = float(current_value)
                                
                                # Spezielle Behandlung für verschiedene Parameter-Typen
                                if 'stoploss' in name.lower():
                                    # StopLoss: breiter Bereich für genetische Optimierung
                                    start = max(1, current * 0.5)
                                    end = current * 3.0
                                    step = 1 if current <= 50 else 5
                                elif 'takeprofit' in name.lower():
                                    # TakeProfit: sehr breiter Bereich
                                    start = max(1, current * 0.4)
                                    end = current * 5.0
                                    step = 3 if current <= 50 else 15
                                elif 'trailing' in name.lower():
                                    # Trailing: feiner Bereich
                                    start = 0
                                    end = current * 2.0
                                    step = 1
                                elif 'period' in name.lower():
                                    # Perioden: typische Bereiche
                                    if current <= 10:  # Schnelle Perioden
                                        start, end = 2, 10
                                        step = 0.5
                                    elif current <= 30:  # Mittlere Perioden
                                        start, end = 5, 30
                                        step = 2.5
                                    elif current <= 50:  # Langsame Perioden
                                        start, end = 10, 100
                                        step = 5
                                    else:
                                        start, end = 20, 200
                                        step = 10
                                elif 'shift' in name.lower():
                                    # Shift: maximal 250% in beide Richtungen
                                    start = max(0, current - (current * 2.5))
                                    end = current + (current * 2.5)
                                    step = 1
                                elif 'count' in name.lower():
                                    # Count/Anzahl: ganzzahlige Schritte
                                    start = 0
                                    end = max(20, current * 2)
                                    step = 1
                                else:
                                    # Standard-Optimierung
                                    start = current * 0.5
                                    end = current * 2.0
                                    if current <= 1:
                                        step = 0.1
                                    elif current <= 10:
                                        step = 0.5
                                    elif current <= 50:
                                        step = 1
                                    else:
                                        step = 5
                                
                                # Formatierung beibehalten
                                if param_type == 'float':
                                    # Bestimme Anzahl der Dezimalstellen aus Original
                                    decimals = len(str(current_value).split('.')[-1])
                                    format_str = f"{{:.{decimals}f}}"
                                    f.write(f"{name}={format_str.format(current)}||{format_str.format(start)}||{format_str.format(step)}||{format_str.format(end)}||Y\n")
                                else:
                                    # Integer-Werte
                                    f.write(f"{name}={int(current)}||{int(start)}||{int(step)}||{int(end)}||Y\n")
                            else:
                                # String-Werte unverändert übernehmen
                                f.write(f"{name}={current_value}\n")
                                
                        except (ValueError, TypeError) as e:
                            self.logger.warning(f"Fehler beim Optimieren von {name}: {str(e)}")
                            # Bei Fehlern: Originalwert beibehalten
                            f.write(f"{name}={current_value}\n")
                    else:
                        # Direkter Wert (sollte nicht vorkommen)
                        f.write(f"{name}={value}\n")
                        
        except Exception as e:
            self.logger.error(f"Fehler beim Schreiben von {output_path}: {str(e)}")
            raise
    
    def read_set_file(self, file_path: Path) -> Dict[str, Any]:
        """Read and parse a .set file."""
        params = {}
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(';'):
                        # Behalte Kommentare und leere Zeilen
                        params[f"_comment_{len(params)}"] = line
                        continue
                        
                    if '=' in line:
                        name, value = line.split('=', 1)
                        name = name.strip()
                        value = value.strip()
                        
                        # Bestimme den Datentyp
                        if value.lower() in ['true', 'false']:
                            params[name] = {'value': value.lower(), 'type': 'bool'}
                        elif '.' in value and value.replace('.', '').isdigit():
                            params[name] = {'value': value, 'type': 'float'}
                        elif value.isdigit():
                            params[name] = {'value': value, 'type': 'int'}
                        else:
                            params[name] = {'value': value, 'type': 'string'}
                            
        except Exception as e:
            self.logger.error(f"Error reading {file_path}: {str(e)}")
            
        return params

    def group_parameters(self, params: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
        """Group parameters by their roles and types with enhanced error handling."""
        grouped = defaultdict(dict)
        
        for name, value in params.items():
            try:
                # Get parameter metadata
                metadata = self.get_parameter_metadata(name)
                role_key = f"role_{metadata.role.value}"
                
                # Convert value to appropriate type with validation
                try:
                    if metadata.role == ParameterRole.FEATURE_SWITCH:
                        parsed_value = value.lower() in ('true', '1', 'yes', 'on')
                    else:
                        parsed_value = self.safe_float(value)
                except ValueError:
                    parsed_value = value  # Keep as string if conversion fails
                
                # Store parameter with its metadata
                grouped[role_key][name] = {
                    'value': parsed_value,
                    'metadata': metadata,
                    'original': value
                }
                
            except Exception as e:
                self.logger.warning(f"Error processing group {name}: {str(e)}")
                # Add to unknown group if processing fails
                grouped['role_unknown'][name] = {
                    'value': value,
                    'metadata': ParameterMetadata(ParameterRole.UNKNOWN),
                    'original': value
                }
        
        return dict(grouped)  # Convert defaultdict to regular dict

    def process_set_file(self, input_path: Path) -> Dict[str, Any]:
        """Process a single .set file and create an optimized version."""
        try:
            # Read input file
            with open(input_path, 'r') as f:
                content = f.read()
            
            # Optimize parameters
            optimized_content = self.optimize_parameters(content)
            
            # Create output path
            base_name = input_path.stem
            if base_name.endswith('_standard'):
                base_name = base_name[:-9]  # Remove '_standard'
            output_name = f"{base_name}_otp.set"
            output_path = input_path.parent / 'optimized' / output_name
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write optimized content
            with open(output_path, 'w') as f:
                f.write(optimized_content)
                
            self.logger.info(f"Successfully optimized {input_path.name} -> {output_name}")
            return {'success': True, 'message': 'Optimization successful'}
            
        except Exception as e:
            self.logger.error(f"Error processing {input_path}: {str(e)}")
            return {'success': False, 'message': str(e)}

    def estimate_combinations(self, selected_params: List[str], params: Dict[str, str]) -> int:
        """Estimate combinations for selected parameters."""
        total = 1
        for name in selected_params:
            try:
                value = self.safe_float(params[name], 1.0)
                param_type = self.detect_parameter_type(name, params[name])
                if param_type == 'int':
                    steps = min(10, max(2, int(value * 0.6)))  # At least 2 steps
                else:
                    steps = min(20, max(3, int(value * 0.4)))  # At least 3 steps
                    
                # Check if adding this parameter would exceed limit
                new_combinations = total * steps
                if new_combinations <= 1_000_000:
                    total = new_combinations
                else:
                    break
                    
            except (ValueError, TypeError):
                continue
        return total

    def optimize_parameter(self, name: str, value: Any, params: Dict[str, Any], metadata: Optional[ParameterMetadata] = None) -> Tuple[Any, bool]:
        """Optimize a single parameter while considering its relationships."""
        try:
            # Get or create metadata
            if metadata is None:
                metadata = self.get_parameter_metadata(name)
                
            # Convert value to float if possible
            try:
                current_value = float(value)
            except (ValueError, TypeError):
                return value, False
                
            # Apply MT5 constraints
            current_value = self.validate_mt5_constraints(name, current_value)
            
            # Get parameter role
            role = metadata.role
            
            # Calculate optimization ranges based on role
            if role == ParameterRole.STOP_LOSS:
                start = max(30, current_value * 0.6)  # Mindestens 20 Pips
                end = min(70, current_value * 1.4)   # Maximal 500 Pips
                step = 1 if current_value <= 50 else 5
            elif role == ParameterRole.TAKE_PROFIT:
                start = max(70, current_value * 0.8)  # Mindestens 20 Pips
                end = min(130, current_value * 1.6)  # Maximal 1000 Pips
                step = 3 if current_value <= 50 else 15
            elif role == ParameterRole.TRAILING_STOP:
                start = 0
                end = current_value * 2.0
                step = 1
            elif role == ParameterRole.VOLUME:
                start = max(0.1, current_value * 0.8)
                end = min(0.15, current_value * 1.2)
                step = 0.05
            elif role == ParameterRole.PERIOD:
                if current_value <= 10:  # Schnelle Perioden
                    start = 0
                    end = 20
                    step = 1
                elif current_value <= 30:  # Mittlere Perioden
                    start = 0
                    end = 60
                    step = 2
                else:  # Langsame Perioden
                    start = 0
                    end = current_value * 2.5
                    step = 5
            elif role == ParameterRole.TECHNICAL:
                if 'shift' in name.lower():
                    start = 0
                    end = 10
                    step = 1
                elif 'magic' in name.lower():
                    start = 10
                    end = 999999999
                    step = 1000000
                elif 'lots' in name.lower():
                    start = 0.01
                    end = current_value * 3.0
                    step = 0.01
                elif 'count' in name.lower():
                    start = 0
                    end = max(20, current_value * 2)
                    step = 1
                else:
                    start = current_value * 0.5
                    end = current_value * 2.0
                    if current_value <= 1:
                        step = 0.1
                    elif current_value <= 10:
                        step = 0.5
                    elif current_value <= 50:
                        step = 1
                    else:
                        step = 5
            else:
                # Default optimization
                start = current_value * 0.5
                end = current_value * 2.0
                step = (end - start) / 10
                
            # Round values appropriately
            start = round(start, 2)
            end = round(end, 2)
            step = round(step, 2)
            
            # Format MT5 optimization string
            opt_string = f"{start}||{step}||{end}||Y"
            
            return opt_string, True
            
        except Exception as e:
            self.logger.warning(f"Error optimizing parameter {name}: {str(e)}")
            return value, False

    def get_range_step(self, value: float, param_type: str = 'default') -> tuple:
        """
        Berechnet optimale Ranges und Steps basierend auf Parameterwert und Typ.
        
        Args:
            value: Der Basiswert des Parameters
            param_type: Art des Parameters (z.B. 'lots', 'period', 'percent', etc.)
            
        Returns:
            tuple: (start, end, step)
        """
        if value == 0:
            return 0, 1, 0.1
            
        # Grundlegende Berechnung der Ranges
        if param_type == 'period':
            start = max(1, int(value * 0.5))
            end = int(value * 2)
            step = max(1, int((end - start) / 20))  # Mindestens 1 für Perioden
        elif param_type == 'percent':
            start = max(0, value * 0.5)
            end = min(100, value * 2)
            step = max(0.1, (end - start) / 20)  # Mindestens 0.1% für Prozente
        elif param_type == 'price':
            start = max(0, value * 0.5)
            end = value * 2
            step = max(0.1, (end - start) / 20)  # Mindestens 0.1 für Preise
        elif param_type == 'pips':
            start = max(1, value * 0.5)
            end = value * 2
            step = max(1, (end - start) / 20)  # Mindestens 1 für Pips
        else:  # default
            if value < 1:
                start = max(0.001, value * 0.5)
                end = value * 2
                step = max(0.001, (end - start) / 20)  # Mindestens 0.001 für kleine Werte
            else:
                start = max(1, value * 0.5)
                end = value * 2
                step = max(1, (end - start) / 20)  # Mindestens 1 für größere Werte
        
        # Stelle sicher, dass step niemals 0 ist
        if step <= 0:
            if value < 1:
                step = max(0.001, abs(value) * 0.05)  # 5% des Wertes oder mindestens 0.001
            else:
                step = max(1, abs(value) * 0.05)  # 5% des Wertes oder mindestens 1
        
        # Runde die Werte entsprechend
        if param_type in ['period', 'pips']:
            start = int(start)
            end = int(end)
            step = int(max(1, step))  # Mindestens 1 für ganzzahlige Parameter
        else:
            # Bestimme Anzahl der Dezimalstellen basierend auf dem Wert
            if value < 0.01:
                decimals = 4
            elif value < 0.1:
                decimals = 3
            elif value < 1:
                decimals = 2
            else:
                decimals = 1
                
            start = round(start, decimals)
            end = round(end, decimals)
            step = round(max(10 ** -decimals, step), decimals)  # Mindestens kleinste darstellbare Einheit
            
        return start, end, step

    def write_analysis(self, output_path: Path, analysis: Dict[str, Any]) -> None:
        """Write optimization analysis to a JSON file."""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, cls=EnumEncoder)

    def optimize_set_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize parameters while respecting their relationships."""
        optimized = {}
        
        for name, value in params.items():
            try:
                # Get parameter metadata
                metadata = self.get_parameter_metadata(name)
                
                # Skip static parameters
                if metadata.is_static:
                    optimized[name] = value
                    continue
                    
                # Optimize parameter
                new_value, modified = self.optimize_parameter(name, value, params, metadata)
                optimized[name] = new_value
                
                if modified:
                    self.logger.info(f"[OPT] {name}: {value} → {new_value}")
                    
            except Exception as e:
                self.logger.warning(f"Error optimizing parameter {name}: {str(e)}")
                optimized[name] = value
                
        return optimized

    def process_parameter_group(self, group_params: Dict[str, Any]) -> Dict[str, Any]:
        """Process and optimize a group of parameters."""
        optimized = group_params.copy()
        
        for name, value in group_params.items():
            try:
                # Get metadata
                metadata = self.get_parameter_metadata(name)
                
                # Skip static parameters
                if metadata.is_static:
                    continue
                    
                # Optimize parameter
                new_value, modified = self.optimize_parameter(name, value, optimized, metadata)
                if modified:
                    optimized[name] = new_value
                    self.logger.info(f"[OPT] {name}: {value} → {new_value}")
                    
            except Exception as e:
                self.logger.warning(f"Error optimizing parameter {name}: {str(e)}")
                
        return optimized

    def analyze_optimization(self, file_path: Path, original_params: Dict[str, Any], optimized_params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate analysis of parameter optimization."""
        # Group parameters by role
        param_groups = self.group_parameters(original_params)
        
        # Count static parameters
        static_params = sum(1 for name, value in optimized_params.items()
                          if self.get_parameter_metadata(name).is_static)
        
        # Generate optimization summary
        return {
            'file_name': file_path.name,
            'original_parameters': original_params,
            'optimized_parameters': optimized_params,
            'parameter_groups': {
                group_name: list(params.keys())
                for group_name, params in param_groups.items()
            },
            'optimization_summary': {
                'total_parameters': len(original_params),
                'optimized_parameters': len(optimized_params),
                'static_parameters': static_params,
                'timestamp': datetime.now().strftime("%Y%m%d_%H%M")
            }
        }

    def optimize_parameters(self, content: str, keep_values: bool = False) -> str:
        """
        Optimiert die Parameter einer .set Datei.
        
        Args:
            content: Inhalt der .set Datei
            keep_values: Wenn True, werden die Werte aus der Eingabedatei beibehalten
        
        Returns:
            Optimierter Inhalt
        """
        lines = content.strip().split('\n')
        optimized_lines = []
        params = {}
        
        # Erst alle Parameter sammeln
        for line in lines:
            if '=' in line:
                name, value = line.split('=', 1)
                name = name.strip().lower()
                value = value.strip()
                try:
                    base_value = float(value.split('||')[0])
                    params[name] = base_value
                except ValueError:
                    continue

        # Dann optimieren mit Berücksichtigung der Beziehungen
        for line in lines:
            if '=' in line:
                name, value = line.split('=', 1)
                name = name.strip()
                name_lower = name.lower()
                value = value.strip()
                
                # Ignoriere Kommentare und leere Zeilen
                if name.startswith(';') or not name:
                    optimized_lines.append(line)
                    continue
                
                # Statische Werte bleiben unverändert
                if ('magic' in name_lower or 
                    name_lower == 'comment'):
                    optimized_lines.append(line)
                    continue

                try:
                    base_value = float(value.split('||')[0])
                    
                    # Bestimme den Parametertyp
                    param_type = 'default'
                    if 'period' in name_lower:
                        param_type = 'period'
                    elif 'percent' in name_lower or '%' in name_lower:
                        param_type = 'percent'
                    elif 'price' in name_lower or 'level' in name_lower:
                        param_type = 'price'
                    elif 'pip' in name_lower or 'point' in name_lower:
                        param_type = 'pips'
                    
                    # Berechne optimierte Werte
                    start, end, step = self.get_range_step(base_value, param_type)
                    
                    # Stelle sicher, dass step > 0 ist
                    if step <= 0:
                        if param_type in ['period', 'pips']:
                            step = 1
                        else:
                            step = max(0.001, abs(base_value) * 0.05)  # 5% des Wertes oder mindestens 0.001
                    
                    # Formatiere die Ausgabe
                    optimized_line = f"{name}={base_value}||{start}||{step}||{end}||Y"
                    optimized_lines.append(optimized_line)
                    
                except ValueError:
                    # Wenn keine Zahl, original Zeile beibehalten
                    optimized_lines.append(line)
                    continue
            else:
                optimized_lines.append(line)

        return '\n'.join(optimized_lines)

    def is_lot_size_parameter(self, param_name: str) -> bool:
        """
        Prüft ob der Parameter ein Lot-Size Parameter ist.
        Berücksichtigt verschiedene gängige Schreibweisen und Variationen.
        """
        param_lower = param_name.lower()
        
        # Lot-spezifische Schlüsselwörter
        lot_keywords = {
            'lot', 'lots', 'volume', 'size', 'volumen', 'trade_volume', 'tradevolume',
            'position_size', 'positionsize', 'tradesize', 'trade_size', 'fixed_lot',
            'fixedlot', 'inplots', 'inp_lots', 'lotsize', 'lot_size'
        }
        
        # Prüfe auf exakte Übereinstimmungen
        if param_lower in lot_keywords:
            return True
        
        # Prüfe auf Teilübereinstimmungen
        for keyword in lot_keywords:
            if keyword in param_lower:
                return True
                
        # Prüfe auf typische Muster
        lot_patterns = [
            r'.*lot.*',
            r'.*vol.*',
            r'.*size.*',
            r'.*amount.*',
            r'.*quantity.*'
        ]
        
        return any(re.match(pattern, param_lower) for pattern in lot_patterns)

    def is_magic_number_parameter(self, param_name: str) -> bool:
        """
        Prüft ob der Parameter eine Magic Number ist.
        Berücksichtigt verschiedene gängige Schreibweisen und Variationen.
        """
        param_lower = param_name.lower()
        
        # Magic-spezifische Schlüsselwörter
        magic_keywords = {
            'magic', 'magicnumber', 'magic_number', 'ea_magic', 'expert_magic',
            'magic_id', 'magicid', 'ea_id', 'expert_id', 'identifier', 'magico',
            'inp_magic', 'inpmagic', 'm_magic', 'magic_value'
        }
        
        # Prüfe auf exakte Übereinstimmungen
        if param_lower in magic_keywords:
            return True
        
        # Prüfe auf Teilübereinstimmungen
        for keyword in magic_keywords:
            if keyword in param_lower:
                return True
                
        # Prüfe auf typische Muster
        magic_patterns = [
            r'.*magic.*',
            r'.*magik.*',  # Häufiger Tippfehler
            r'.*mgc.*',    # Abkürzung
            r'.*_id$',     # Endet mit _id
            r'^id_.*'      # Beginnt mit id_
        ]
        
        return any(re.match(pattern, param_lower) for pattern in magic_patterns)

    def optimize_parameter(self, name: str, value: Any, params: Dict[str, Any], metadata: Optional[ParameterMetadata] = None) -> Tuple[float, float, float]:
        """
        Optimiert einen einzelnen Parameter unter Berücksichtigung seiner Beziehungen.
        Für Lots und Magic Number werden feste Werte verwendet.
        
        Args:
            name: Name des Parameters
            value: Aktueller Wert
            params: Alle Parameter
            metadata: Optional, zusätzliche Metadaten zum Parameter
            
        Returns:
            Tuple[float, float, float]: (Start, Stop, Step) für die Optimierung
        """
        try:
            # Konvertiere Wert zu Float
            value = float(value)
            
            # Prüfe ob es sich um Lots oder Magic Number handelt
            if self.is_lot_size_parameter(name):
                # Setze festen Wert für Lots
                fixed_value = 0.1 if value != 0.1 else value
                self.logger.info(f"Lot-Parameter erkannt: {name} - Setze festen Wert {fixed_value}")
                return fixed_value, fixed_value, 0  # Start = Wert, Stop = Wert, Step = 0
                
            if self.is_magic_number_parameter(name):
                # Behalte den originalen Magic Number Wert bei
                self.logger.info(f"Magic Number erkannt: {name} - Behalte Wert {value}")
                return value, value, 0  # Start = Wert, Stop = Wert, Step = 0
            
            # Für alle anderen Parameter: Normale Optimierung
            if metadata is None:
                metadata = self.get_parameter_metadata(name)
            
            # Hole Optimierungsbereich basierend auf Parametertyp
            param_type = self.detect_parameter_type(name, str(value))
            start, end, step = self.get_range_step(value, param_type)
            
            # Validiere und passe die Werte an
            start = self.safe_value(start, name)
            end = self.safe_value(end, name)
            step = max(step, self.get_min_step(name))
            
            return start, end, step
            
        except Exception as e:
            self.logger.error(f"Fehler bei der Optimierung von Parameter {name}: {e}")
            return value, value, 0  # Im Fehlerfall: Behalte original Wert bei

class EnumEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Enum values and ParameterMetadata."""
    def default(self, obj):
        if isinstance(obj, Enum):
            return obj.value
        if isinstance(obj, ParameterMetadata):
            return obj.to_dict()
        return super().default(obj)

def main():
    """Main function to demonstrate usage."""
    optimizer = SetFileOptimizer()
    
    # Get command line arguments
    input_dir = sys.argv[1] if len(sys.argv) > 1 else "C:\\Users\\nikol\\AppData\\Roaming\\MetaQuotes\\Terminal\\4B1CE69F577705455263BD980C39A82C\\MQL5\\Profiles\\Tester"
    output_dir = os.path.join(input_dir, "optimized")
    
    # Process all files
    results = optimizer.batch_process_directory(input_dir, output_dir)
    
    # Print summary
    print("\nOptimization Complete!")
    if results:
        print(f"Successfully processed: {len(results['processed'])} files")
        print(f"Failed: {len(results['failed'])} files")
        print(f"Skipped: {len(results['skipped'])} files")
        
        if results['failed']:
            print("\nFailed files:")
            for f in results['failed']:
                print(f"- {f}")

if __name__ == '__main__':
    main()
