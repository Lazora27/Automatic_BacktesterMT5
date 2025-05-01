# Intelligent .set File Optimizer

This program automatically analyzes MetaTrader 5 .set files and creates optimized versions suitable for strategy testing.

## Features

- Automatically detects optimizable parameters
- Intelligently generates optimization ranges based on parameter values
- Preserves boolean and string parameters
- Creates MT5-compatible .opt.set files
- Provides detailed logging of processed parameters

## Usage

1. Place your .set files in the input directory
2. Run the script:
   ```
   python set_optimizer.py
   ```
3. Find optimized files in the "optimized" subdirectory

## Parameter Optimization Rules

- Numeric values: Automatically generates appropriate ranges
- Small values (<10): Uses step size of 1
- Larger values: Uses proportional ranges
- Boolean values: Preserved as-is
- String values: Preserved as-is

## Output Format

The program generates MT5-compatible .opt.set files with the format:
```
parameter=value||start||step||end||Y
```

Example:
```
takeprofit=500||250||25||750||Y
stoploss=300||150||15||450||Y
use_filter=true
```
