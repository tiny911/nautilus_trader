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

"""
An example of backtesting the MACD strategy with QMT data.
"""

import os
from datetime import datetime
from datetime import timedelta
from decimal import Decimal

from examples.backtest.example_04_macd.strategy import MACDStrategy
from examples.backtest.example_04_macd.strategy import MACDStrategyConfig
from nautilus_trader.adapters.qmt.data import QMTDataLoader
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.currencies import CNY
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import StrategyId
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from nautilus_trader.test_kit.providers import TestInstrumentProvider


log = Logger(__name__)


def load_qmt_data(
    instrument_id: InstrumentId,
    start_date: datetime,
    end_date: datetime,
    qmt_path: str = None,
) -> list:
    """
    Load historical data from QMT for backtesting.

    Parameters
    ----------
    instrument_id : InstrumentId
        The instrument identifier.
    start_date : datetime
        The start date for data.
    end_date : datetime
        The end date for data.
    qmt_path : str, optional
        The path to QMT installation, by default None.

    Returns
    -------
    list
        A list of bars.
    """
    # Initialize QMT data loader
    loader = QMTDataLoader(qmt_path=qmt_path)

    # Load bars
    bars = loader.load_bars(
        instrument_id=instrument_id,
        start_time=start_date,
        end_time=end_date,
    )

    log.info(f"Loaded {len(bars)} bars for {instrument_id}")
    return bars


if __name__ == "__main__":
    # ----------------------------------------------------------------------------------
    # Step 1: Configure and Create the Backtest Engine
    # ----------------------------------------------------------------------------------

    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTEST_TRADER-001"),
        logging=LoggingConfig(
            log_level="INFO",
        ),
    )
    engine = BacktestEngine(config=engine_config)

    # ----------------------------------------------------------------------------------
    # 2. Prepare market data
    # ----------------------------------------------------------------------------------

    # Define the trading venue
    venue_name = "SZSE"

    # Define instruments
    SH000300 = TestInstrumentProvider.equity(
        symbol="000300.SH",
        venue=venue_name,
        currency=CNY,
        price_precision=2,
        size_precision=0,
        multiplier=1,
    )

    # Define bar type
    bar_type_1min = BarType.from_str(f"{SH000300.id}-1-MINUTE-LAST-EXTERNAL")

    # Define date range for backtest
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days

    # Load data from QMT
    qmt_path = os.environ.get("QMT_PATH")
    bars = load_qmt_data(
        instrument_id=SH000300.id,
        start_date=start_date,
        end_date=end_date,
        qmt_path=qmt_path,
    )

    # ----------------------------------------------------------------------------------
    # 3. Configure trading environment
    # ----------------------------------------------------------------------------------

    # Set up the trading venue with a margin account
    engine.add_venue(
        venue=Venue(venue_name),
        oms_type=OmsType.NETTING,  # Netting: positions are netted against each other
        account_type=AccountType.MARGIN,  # Margin account: allows trading with leverage
        starting_balances=[Money(1_000_000, CNY)],  # Initial account balance
        base_currency=CNY,  # Account base currency
        default_leverage=Decimal(1),  # No leverage is used (1:1)
    )

    # Add instrument and market data to the engine
    engine.add_instrument(SH000300)
    engine.add_data(bars)

    # ----------------------------------------------------------------------------------
    # 4. Configure and use Data Catalog
    # ----------------------------------------------------------------------------------

    # Create a Data Catalog (folder will be created if it doesn't exist)
    data_catalog = ParquetDataCatalog("./data_catalog")

    # Write data to the catalog
    data_catalog.write_data([SH000300])  # Store instrument definition
    data_catalog.write_data(bars)  # Store bars data

    # ----------------------------------------------------------------------------------
    # 5. Configure and run strategy
    # ----------------------------------------------------------------------------------

    # Create strategy configuration
    strategy_config = MACDStrategyConfig(
        instrument_id=SH000300.id,
        bar_type_1min=bar_type_1min,
        fast_period=12,
        slow_period=26,
        base_trade_size=100,
        enter_threshold=0.00010,
        follow_step=0.00005,
        max_follow_steps=5,
        follow_risk_multiplier=0.5,
        volatility_window=20,
        max_leverage=3.0,
        risk_per_trade=0.02,
    )

    # Create and add strategy
    strategy = MACDStrategy(config=strategy_config)
    engine.add_strategy(strategy)

    # Execute the backtest
    engine.run()

    # ----------------------------------------------------------------------------------
    # 6. Analyze results
    # ----------------------------------------------------------------------------------

    # Get performance statistics
    performance = engine.trader.generate_account_report(SH000300.id.venue)
    log.info(f"Performance Report:\n{performance}", color=LogColor.BLUE)

    # Get trade statistics
    trade_statistics = engine.trader.generate_trade_statistics()
    log.info(f"Trade Statistics:\n{trade_statistics}", color=LogColor.BLUE)

    # Clean up resources
    engine.dispose()
