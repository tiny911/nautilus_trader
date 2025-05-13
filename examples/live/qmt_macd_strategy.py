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
An example of running the MACD strategy with QMT integration.
"""

import asyncio
import os
import sys

from nautilus_trader.adapters.qmt.client import QMTDataClient
from nautilus_trader.adapters.qmt.config import QMTDataClientConfig
from nautilus_trader.adapters.qmt.config import QMTExecutionClientConfig
from nautilus_trader.adapters.qmt.execution import QMTExecutionClient
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.config import LiveDataEngineConfig
from nautilus_trader.config import LiveExecEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.examples.strategies.macd import MACDStrategy
from nautilus_trader.examples.strategies.macd import MACDStrategyConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import CNY
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import StrategyId
from nautilus_trader.model.objects import Money
from nautilus_trader.test_kit.providers import TestInstrumentProvider


# Configure the trading node
config = TradingNodeConfig(
    trader_id="TRADER-001",
    logging=LoggingConfig(
        log_level="INFO",
        log_thread_id=False,
        log_to_file=False,
        log_file_path="logs/",
    ),
    data_engine=LiveDataEngineConfig(
        instrument_provider=InstrumentProviderConfig(),
    ),
    exec_engine=LiveExecEngineConfig(),
    timeout_connection=60.0,  # Seconds
    timeout_reconciliation=60.0,  # Seconds
    timeout_portfolio=60.0,  # Seconds
    timeout_disconnection=10.0,  # Seconds
    timeout_post_stop=5.0,  # Seconds
)


# Setup trading instruments
SH000300 = TestInstrumentProvider.equity(
    symbol="000300.SH",
    venue="SZSE",
    currency=CNY,
    price_precision=2,
    size_precision=0,
    multiplier=1,
)

# Setup QMT data client
qmt_data_config = QMTDataClientConfig(
    client_id="QMT-DATA-001",
    qmt_path=os.environ.get("QMT_PATH"),  # Set QMT_PATH environment variable
)

# Setup QMT execution client
qmt_exec_config = QMTExecutionClientConfig(
    client_id="QMT-EXEC-001",
    account_id=os.environ.get("QMT_ACCOUNT_ID", "YOUR_ACCOUNT_ID"),  # Set QMT_ACCOUNT_ID environment variable
    qmt_path=os.environ.get("QMT_PATH"),  # Set QMT_PATH environment variable
)

# Setup MACD strategy
strategy_config = MACDStrategyConfig(
    strategy_id=StrategyId("MACD-000300.SH"),
    instrument_id=SH000300.id,
    bar_type_1min=BarType.from_str(f"{SH000300.id}-1-MINUTE-LAST-EXTERNAL"),
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


async def run():
    # Instantiate the node with a configuration
    node = TradingNode(config=config)

    # Setup and initialize node
    await node.initialize()

    # Configure your clients
    qmt_data_client = QMTDataClient(config=qmt_data_config)
    qmt_exec_client = QMTExecutionClient(
        client_id=qmt_exec_config.client_id,
        account_id=qmt_exec_config.account_id,
        qmt_path=qmt_exec_config.qmt_path,
    )

    # Register the clients with the node
    node.add_data_client(qmt_data_client)
    node.add_exec_client(qmt_exec_client)

    # Register the test instruments with the node
    node.add_instrument(SH000300)

    # Create and add your strategy
    strategy = MACDStrategy(config=strategy_config)
    node.add_strategy(strategy)

    # Register your account
    node.add_account(
        AccountId(qmt_exec_config.account_id),
        AccountType.CASH,
        base_currency=CNY,
        starting_balances=[Money(1_000_000, CNY)],
    )

    # Start the node (synchronous)
    node.start()

    # Wait for completion or Ctrl+C
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        # Stop the node
        node.stop()
        await node.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("Stopped!")
        sys.exit(0)
