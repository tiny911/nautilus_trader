# Apple Stock Multi-Period MACD Backtest

This example demonstrates how to use Nautilus Trader to backtest a trading strategy for Apple stock using multi-period MACD indicators. The strategy also uses the NASDAQ 100 index to determine overall market conditions.

## Strategy Overview

The strategy uses multiple timeframes of MACD (Moving Average Convergence Divergence) indicators:

1. **Market Condition Analysis (NASDAQ 100 Index)**
   - Daily MACD: Used to determine long-term market trend
   - Hourly MACD: Used to confirm medium-term market trend
   - The combination of these indicators determines if the market is BULLISH, BEARISH, or NEUTRAL

2. **Trading Signals (Apple Stock)**
   - Hourly MACD: Used to confirm the trend direction for Apple stock
   - 1-Minute MACD: Used for precise entry and exit timing

3. **Trading Rules**
   - Enter LONG positions when:
     - Market condition is BULLISH
     - Apple hourly MACD histogram is positive
     - Apple 1-minute MACD value crosses above threshold
   - Enter SHORT positions when:
     - Market condition is BEARISH
     - Apple hourly MACD histogram is negative
     - Apple 1-minute MACD value crosses below negative threshold
   - Exit positions when:
     - For LONG positions: 1-minute MACD histogram turns negative or market turns BEARISH
     - For SHORT positions: 1-minute MACD histogram turns positive or market turns BULLISH

## Files

- `data_preparation.py`: Functions to prepare data for backtesting
- `multi_macd_strategy.py`: Implementation of the multi-period MACD strategy
- `run_backtest.py`: Main script to run the backtest

## Usage

### Using Demo Data

To run the backtest with synthetic demo data:

```bash
python run_backtest.py --use-demo-data
```

### Using Real Data

To run the backtest with real data:

```bash
python run_backtest.py --apple-data path/to/apple_data.csv --nasdaq-data path/to/nasdaq_data.csv
```

The data files should be in CSV or Parquet format with columns: timestamp, open, high, low, close, volume.

### Customizing Strategy Parameters

You can customize the MACD parameters:

```bash
python run_backtest.py --use-demo-data --fast-period 12 --slow-period 26 --signal-period 9 --trade-size 100
```

## Data Requirements

For real data, you need:

1. **Apple Stock Data**: Historical price data for Apple (AAPL)
2. **NASDAQ 100 Index Data**: Historical price data for the NASDAQ 100 index (NDX)

Both datasets should have the same time range and preferably the same time resolution.

## Results

The backtest will output:

- Account information
- Order fills
- Positions
- Performance metrics

## Notes

- The strategy uses a margin account with $1,000,000 initial balance
- No leverage is used (1:1)
- The strategy trades with market orders
