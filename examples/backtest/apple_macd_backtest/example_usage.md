# Example Usage of Apple MACD Backtest

This document provides examples of how to use the Apple MACD backtest system.

## Running with Demo Data

To run the backtest with synthetic demo data:

```bash
cd examples/backtest/apple_macd_backtest
python run_backtest.py --use-demo-data
```

## Running with Real Data

To run the backtest with real data:

```bash
cd examples/backtest/apple_macd_backtest
python run_backtest.py --apple-data path/to/apple_data.csv --nasdaq-data path/to/nasdaq_data.csv
```

## Customizing Strategy Parameters

You can customize the MACD parameters:

```bash
cd examples/backtest/apple_macd_backtest
python run_backtest.py --use-demo-data --fast-period 12 --slow-period 26 --signal-period 9 --trade-size 100
```

## Data Format Requirements

The data files should be in CSV or Parquet format with the following columns:
- timestamp: The timestamp of the bar
- open: The opening price
- high: The highest price
- low: The lowest price
- close: The closing price
- volume: The trading volume

Example CSV format:
```
timestamp,open,high,low,close,volume
2023-01-01 09:30:00,150.25,151.30,149.80,150.75,10000
2023-01-01 09:31:00,150.75,151.50,150.60,151.20,8500
...
```

## Troubleshooting

If you encounter circular import errors when running the backtest, it may be due to issues with the Nautilus Trader library. Try the following:

1. Make sure you're using a compatible version of Nautilus Trader
2. Check for any updates to the library
3. Try running one of the official examples first to ensure your environment is set up correctly

## Code Structure

The backtest system consists of three main components:

1. **Data Preparation (`data_preparation.py`)**: Functions to prepare data for backtesting
   - `prepare_apple_stock_data()`: Prepares Apple stock data
   - `prepare_nasdaq100_index_data()`: Prepares NASDAQ 100 index data
   - `prepare_demo_data()`: Generates synthetic data for testing

2. **Strategy Implementation (`multi_macd_strategy.py`)**: Implementation of the multi-period MACD strategy
   - `MultiMACDStrategyConfig`: Configuration class for the strategy
   - `MultiMACDStrategy`: The strategy class that implements the trading logic

3. **Backtest Runner (`run_backtest.py`)**: Main script to run the backtest
   - Parses command-line arguments
   - Sets up the backtest engine
   - Configures the strategy
   - Runs the backtest
   - Displays the results
