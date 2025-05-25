#!/usr/bin/env python3
# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2025 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

import argparse
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import pandas as pd

from nautilus_trader.core.nautilus_pyo3 import BarType
from nautilus_trader.model.identifiers import InstrumentId


sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import local modules
# from examples.backtest.apple_macd_backtest.data_preparation import prepare_apple_stock_data
# from examples.backtest.apple_macd_backtest.data_preparation import prepare_demo_data
# from examples.backtest.apple_macd_backtest.data_preparation import prepare_nasdaq100_index_data
from examples.backtest.apple_macd_backtest.multi_macd_strategy import MultiMACDStrategy
from examples.backtest.apple_macd_backtest.multi_macd_strategy import MultiMACDStrategyConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.engine import BacktestEngineConfig
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run Apple stock MACD backtest")
    
    # Data source options
    parser.add_argument(
        "--use-demo-data",
        action="store_true",
        help="Use synthetic demo data instead of real data files",
    )
    parser.add_argument(
        "--apple-data",
        type=str,
        help="Path to Apple stock data file (CSV or Parquet)",
    )
    parser.add_argument(
        "--nasdaq-data",
        type=str,
        help="Path to NASDAQ 100 index data file (CSV or Parquet)",
    )
    
    # Strategy parameters
    parser.add_argument(
        "--fast-period",
        type=int,
        default=12,
        help="Fast period for MACD calculation",
    )
    parser.add_argument(
        "--slow-period",
        type=int,
        default=26,
        help="Slow period for MACD calculation",
    )
    parser.add_argument(
        "--signal-period",
        type=int,
        default=9,
        help="Signal period for MACD calculation",
    )
    parser.add_argument(
        "--trade-size",
        type=int,
        default=100,
        help="Trade size in number of shares",
    )
    
    return parser.parse_args()


def main():
    """Run the backtest."""
    
    # Configure logging
    log = Logger("BACKTEST")
    log.info("Starting Apple MACD backtest...")
    
    # Configure backtest engine
    engine_config = BacktestEngineConfig(
        trader_id=TraderId("APPLE_MACD_TRADER-001"),
        logging=LoggingConfig(
            log_level="INFO",
        ),
    )
    engine = BacktestEngine(config=engine_config)
    
    # Prepare data
    data_catalog = ParquetDataCatalog("./data_catalog")

    # Get all instruments and bars
    all_instruments = data_catalog.instruments()
    equity = all_instruments[1]
    log.info(f"equity id:\n{equity.id}", color=LogColor.YELLOW)

    hs300_index_instrument_id = InstrumentId.from_str("000300.SH.SZSE")
    queryHS300Results = list(filter(lambda el: el.id == hs300_index_instrument_id, all_instruments))
    log.info(f"filter result:{queryHS300Results}", color=LogColor.GREEN)
    


    # log.info(f"Loading Apple data from {args.apple_data}")
    # apple_data = prepare_apple_stock_data(
    #     args.apple_data,
    #     timeframes=["1-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"],
    # )
    apple_data = equity
    
    # log.info(f"Loading NASDAQ 100 data from {args.nasdaq_data}")
    # nasdaq_data = prepare_nasdaq100_index_data(
    #     args.nasdaq_data,
    #     timeframes=["1-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"],
    # )
    nasdaq_data = queryHS300Results[0]
    
    # Set up the trading venue
    VENUE_NAME = "SZSE"
    engine.add_venue(
        venue=Venue(VENUE_NAME),
        oms_type=OmsType.NETTING,  # Netting: positions are netted against each other
        account_type=AccountType.MARGIN,  # Margin account: allows trading with leverage
        starting_balances=[Money(1_000_000, USD)],  # Initial account balance of $1,000,000 USD
        base_currency=USD,  # Account base currency is USD
        default_leverage=Decimal(1),  # No leverage is used (1:1)
    )
    
    # Add instruments
    # engine.add_instrument(apple_data["instrument"])
    # engine.add_instrument(nasdaq_data["instrument"])
    engine.add_instrument(equity)
    engine.add_instrument(queryHS300Results[0])
    
    
    # # Add data for all timeframes
    # for timeframe in apple_data["bars_lists"]:
    #     engine.add_data(apple_data["bars_lists"][timeframe])
    #     engine.add_data(nasdaq_data["bars_lists"][timeframe])
    

    # Define bar type
    barType = BarType.from_str(f"{equity.id}-1-MINUTE-LAST-EXTERNAL")
    hs300BarType = BarType.from_str(f"{hs300_index_instrument_id}-1-MINUTE-LAST-EXTERNAL")
    # - Get specific bars with date range filter
    filtered_bars = data_catalog.bars(
        bar_types=[str(barType), str(hs300BarType)],
        # start="2024-01-10",  # Filter start date
        # end="2024-01-15",  # Filter end date
    )
    engine.add_data(filtered_bars)
    
    macd_fast_period:int  = 12
    macd_slow_period=26
    macd_signal_period=9

    trade_size = 1

    # Configure and add the strategy
    strategy_config = MultiMACDStrategyConfig(
        apple_instrument_id=apple_data.id,
        nasdaq_instrument_id=nasdaq_data.id,
        apple_bar_types=apple_data["bar_types"],
        nasdaq_bar_types=nasdaq_data["bar_types"],
        fast_period=macd_fast_period,
        slow_period=macd_slow_period,
        signal_period=macd_signal_period,
        trade_size=Decimal(trade_size),
        apple_entry_threshold=0.1,
        nasdaq_bullish_threshold=0.5,
        nasdaq_bearish_threshold=-0.5,
    )
    
    strategy = MultiMACDStrategy(config=strategy_config)
    engine.add_strategy(strategy)
    
    # Optional: Save data to catalog for future use
    data_catalog = ParquetDataCatalog("./data_catalog")
    data_catalog.write_data([apple_data["instrument"], nasdaq_data["instrument"]])
    
    for timeframe in apple_data["bars_lists"]:
        data_catalog.write_data(apple_data["bars_lists"][timeframe])
        data_catalog.write_data(nasdaq_data["bars_lists"][timeframe])
    
    # Run the backtest
    log.info("Running backtest...")
    start_time = time.time()
    engine.run()
    end_time = time.time()
    log.info(f"Backtest completed in {end_time - start_time:.2f} seconds")
    
    # Display results
    with pd.option_context(
        "display.max_rows", 100,
        "display.max_columns", None,
        "display.width", 300,
    ):
        print("\n=== ACCOUNT INFORMATION ===")
        print(engine.trader.generate_account_report(Venue(VENUE_NAME)))
        
        print("\n=== ORDER FILLS ===")
        print(engine.trader.generate_order_fills_report())
        
        print("\n=== POSITIONS ===")
        print(engine.trader.generate_positions_report())
        
        print("\n=== PERFORMANCE ===")
        print(engine.trader.generate_returns_report())
    
    # Clean up resources
    engine.dispose()
    log.info("Backtest finished")


if __name__ == "__main__":
    main()
