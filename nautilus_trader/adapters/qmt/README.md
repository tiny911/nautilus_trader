# QMT Adapter for Nautilus Trader

This adapter provides integration between [Nautilus Trader](https://github.com/nautechsystems/nautilus_trader) and the QMT (Quantitative Trading Platform) commonly used in Chinese markets.

## Features

- Data integration with QMT for historical and real-time market data
- Execution integration for order management and trading
- Support for MACD and other trading strategies
- Backtesting capabilities using QMT historical data
- Live trading support

## Installation

1. Install QMT platform first
2. Install Nautilus Trader
3. The QMT adapter is included in Nautilus Trader

## Configuration

To use the QMT adapter, you need to set the following environment variables:

```bash
export QMT_PATH="/path/to/qmt/installation"
export QMT_ACCOUNT_ID="your_account_id"
```

## Usage Examples

### Backtesting with QMT Data

```python
from nautilus_trader.adapters.qmt.data import QMTDataLoader
from nautilus_trader.model.identifiers import InstrumentId

# Initialize QMT data loader
loader = QMTDataLoader(qmt_path="/path/to/qmt")

# Load historical bars
bars = loader.load_bars(
    instrument_id=InstrumentId.from_str("000300.SH.SZSE"),
    start_time=datetime(2023, 1, 1),
    end_time=datetime(2023, 12, 31),
)

# Use bars for backtesting
# See examples/backtest/qmt_macd_backtest.py for a complete example
```

### Live Trading with QMT

```python
from nautilus_trader.adapters.qmt.client import QMTDataClient
from nautilus_trader.adapters.qmt.config import QMTDataClientConfig
from nautilus_trader.adapters.qmt.execution import QMTExecutionClient

# Configure QMT data client
qmt_data_config = QMTDataClientConfig(
    client_id="QMT-DATA-001",
    qmt_path="/path/to/qmt",
)

# Configure QMT execution client
qmt_exec_client = QMTExecutionClient(
    client_id="QMT-EXEC-001",
    account_id="your_account_id",
    qmt_path="/path/to/qmt",
)

# See examples/live/qmt_macd_strategy.py for a complete example
```

## Components

### Data Client

The `QMTDataClient` provides real-time market data from QMT:

- Bar data (various timeframes)
- Quote ticks
- Historical data requests

### Execution Client

The `QMTExecutionClient` handles order execution:

- Market and limit orders
- Order cancellation
- Order status updates
- Trade execution reports

### Data Loader

The `QMTDataLoader` provides historical data loading capabilities:

- Load historical bars for backtesting
- Convert QMT data format to Nautilus Trader format

## MACD Strategy Implementation

The QMT adapter includes examples of implementing the MACD (Moving Average Convergence Divergence) strategy:

1. **Backtesting**: See `examples/backtest/qmt_macd_backtest.py`
2. **Live Trading**: See `examples/live/qmt_macd_strategy.py`

The MACD strategy implementation includes:
- Dynamic position sizing based on volatility
- Risk management features
- Customizable parameters

## Troubleshooting

If you encounter issues with the QMT adapter:

1. Ensure QMT is properly installed and the path is correctly set
2. Verify your account credentials
3. Check the logs for detailed error messages
4. Make sure the symbols you're using are available in QMT

## License

This adapter is part of Nautilus Trader and is licensed under the GNU Lesser General Public License Version 3.0.
