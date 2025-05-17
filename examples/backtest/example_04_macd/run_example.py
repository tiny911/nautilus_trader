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

from decimal import Decimal

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.core.nautilus_pyo3 import BarType
from nautilus_trader.model import Bar
from nautilus_trader.model import TraderId
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.instruments.base import Instrument
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from strategy import MACDStrategy
from strategy import MACDStrategyConfig


log = Logger(__name__)


if __name__ == "__main__":
    # ----------------------------------------------------------------------------------
    # Step 1: Configure and Create the Backtest Engine
    # ----------------------------------------------------------------------------------

    engine_config = BacktestEngineConfig(
        trader_id=TraderId("BACKTEST_TRADER-001"),
        logging=LoggingConfig(
            log_level="DEBUG",  # Set to DEBUG to see detailed timer and bar processing logs
        ),
    )
    engine = BacktestEngine(config=engine_config)

    # ----------------------------------------------------------------------------------
    # 2. Load all data from catalog
    # ----------------------------------------------------------------------------------
    data_catalog = ParquetDataCatalog("./data_catalog")
    
    # Get all instruments and bars
    all_instruments = data_catalog.instruments()
    all_bars = data_catalog.bars()
    log.info(f"Loaded {len(all_instruments)} instruments and {len(all_bars)} bars from catalog", 
             color=LogColor.YELLOW)

    # Group bars by instrument and bar type
    bars_grouped = {}
    for bar in all_bars:
        try:
            instrument_id = bar.bar_type.instrument_id
            bar_type_str = str(bar.bar_type)
            key = (instrument_id, bar_type_str)
        except AttributeError as e:
            log.error(f"Skipping invalid bar: {e}")
            continue
        if key not in bars_grouped:
            bars_grouped[key] = []
        bars_grouped[key].append(bar)

    # ----------------------------------------------------------------------------------
    # 3. Configure trading environment
    # ----------------------------------------------------------------------------------
    VENUE_NAME = "SZSE"
    # Set up the trading venue with a margin account
    engine.add_venue(
        venue=Venue(VENUE_NAME),
        oms_type=OmsType.NETTING,  # Netting: positions are netted against each other
        account_type=AccountType.MARGIN,  # Margin account: allows trading with leverage
        starting_balances=[Money(1_000_000, USD)],  # Initial account balance of $1,000,000 USD
        base_currency=USD,  # Account base currency is USD
        default_leverage=Decimal(1),  # No leverage is used (1:1)
    )



    # ----------------------------------------------------------------------------------
    # 5. Configure and run strategy
    # ----------------------------------------------------------------------------------
    
    # Create strategies for each instrument and bar type combination
    strategies = []
    for (instrument_id, bar_type_str), bars in bars_grouped.items():
        bar_type = BarType.from_str(bar_type_str)
        config = MACDStrategyConfig(
            instrument_id=instrument_id,
            bar_type_1min=bar_type,  # 根据策略定义修正参数名称
            bar_type_sp500="",
            fast_period=12,
            slow_period=26,
            # signal_period=9
        )
        strategies.append(MACDStrategy(config=config))
        engine.add_strategy(strategies[-1])
        log.info(f"Added strategy for {instrument_id} {bar_type}", color=LogColor.GREEN)

    # Execute the backtest
    engine.run()

    # Clean up resources
    engine.dispose()
