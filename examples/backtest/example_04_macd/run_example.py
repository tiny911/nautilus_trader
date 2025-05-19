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

from strategy import DualMACDConfig
from strategy import DualMACDStrategy
from strategy import MACDStrategy
from strategy import MACDStrategyConfig

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.common.component import Logger
from nautilus_trader.common.config import LoggingConfig
from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import BacktestEngineConfig

# from nautilus_trader.config import LoggingConfig
from nautilus_trader.core.nautilus_pyo3 import BarType
from nautilus_trader.core.nautilus_pyo3 import Money
from nautilus_trader.model import TraderId
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog


log = Logger(__name__)

def backtest():
    # 初始化回测引擎
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(
            log_level="INFO",  # Set to DEBUG to see detailed timer and bar processing logs
        )))

    # 创建交易场所
    nasdaq = Venue("SZSE")
    # engine.add_venue(
    #     BacktestVenueConfig(
    #         name=nasdaq.value,
    #         oms_type="HEDGING",
    #         account_type=AccountType.CASH,
    #         base_currency="USD",
    #         starting_balances=["USD 1_000_000"]
    #     )
    # )

    engine.add_venue(
        venue=Venue(nasdaq),
        oms_type="HEDGING",  # Netting: positions are netted against each other
        account_type=AccountType.MARGIN,  # Margin account: allows trading with leverage
        starting_balances=[Money(1_000_000, USD)],  # Initial account balance of $1,000,000 USD
        base_currency=USD,  # Account base currency is USD
        default_leverage=Decimal(1),  # No leverage is used (1:1)
    )

    # # 加载苹果股票数据
    # aapl = Equity.from_dict({
    #     "id": "AAPL.NASDAQ",
    #     "symbol": "AAPL",
    #     "currency": "USD",
    #     "price_precision": 2,
    #     "maker_fee": 0.001,
    #     "taker_fee": 0.002
    # })
   

    # engine.add_data(aapl_bars)

    # # 加载纳斯达克指数数据
    # ndx = Equity.from_dict({
    #     "id": "NDX.NASDAQ",
    #     "symbol": "NDX",
    #     "currency": "USD",
    #     "price_precision": 2,
    #     "maker_fee": 0.0005,
    #     "taker_fee": 0.001
    # })

    # ndx_bars = load_data("NDX_daily.csv", ndx)
    # engine.add_data(ndx_bars)

        # ----------------------------------------------------------------------------------
    # 2. Load all data from catalog
    # ----------------------------------------------------------------------------------
    data_catalog = ParquetDataCatalog("./data_catalog")

    # Get all instruments and bars
    all_instruments = data_catalog.instruments()
    equity = all_instruments[1]
    log.info(f"equity id:\n{equity.id}", color=LogColor.YELLOW)

    hs300_index_instrument_id = InstrumentId.from_str("000300.SH.SZSE")
    queryHS300Results = list(filter(lambda el: el.id == hs300_index_instrument_id, all_instruments))
    log.info(f"filter result:{queryHS300Results}", color=LogColor.GREEN)

    # # - Get all available bars
    # all_bars = data_catalog.bars()
    # log.info(f"All bars count: {len(all_bars)}", color=LogColor.YELLOW)

    # Define bar type
    barType = BarType.from_str(f"{equity.id}-1-MINUTE-LAST-EXTERNAL")
    hs300BarType = BarType.from_str(f"{hs300_index_instrument_id}-1-MINUTE-LAST-EXTERNAL")

    # - Get specific bars with date range filter
    filtered_bars = data_catalog.bars(
        bar_types=[str(barType), str(hs300BarType)],
        # start="2024-01-10",  # Filter start date
        # end="2024-01-15",  # Filter end date
    )
    log.info(f"Bars between Jan 10-15: {len(filtered_bars)}", color=LogColor.YELLOW)

    # 配置策略
    strategy_config = DualMACDConfig(
        instrument_aapl=equity.id,
        instrument_ndx=hs300_index_instrument_id,
        macd_fast=12,
        macd_slow=26,
        macd_signal=9,
        ndx_fast=50,
        ndx_slow=200,
        trade_size=100
    )

    # 添加策略
    engine.add_strategy(DualMACDStrategy(config=strategy_config))

    # 运行回测
    engine.run()

    # 生成报告
    report = engine.get_report()
    print("="*50)
    print("回测结果统计:")
    print(f"总收益率: {report.total_return_pct:.2f}%")
    print(f"年化收益率: {report.annualized_return_pct:.2f}%")
    print(f"最大回撤: {report.max_drawdown_pct:.2f}%")
    print(f"夏普比率: {report.sharpe_ratio:.2f}")
    print(f"胜率: {report.win_rate_pct:.2f}%")
    print("详细报告已保存到 backtest_report.html")
    engine.save_report("backtest_report.html")
# endregion



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
    equity = all_instruments[1]
    log.info(f"equity id:\n{equity.id}", color=LogColor.YELLOW)

    hs300_index_instrument_id = InstrumentId.from_str("000300.SH.SZSE")
    queryHS300Results = list(filter(lambda el: el.id == hs300_index_instrument_id, all_instruments))
    log.info(f"filter result:{queryHS300Results}", color=LogColor.GREEN)

    # # - Get all available bars
    # all_bars = data_catalog.bars()
    # log.info(f"All bars count: {len(all_bars)}", color=LogColor.YELLOW)

    # Define bar type
    barType = BarType.from_str(f"{equity.id}-1-MINUTE-LAST-EXTERNAL")
    hs300BarType = BarType.from_str(f"{hs300_index_instrument_id}-1-MINUTE-LAST-EXTERNAL")

    # - Get specific bars with date range filter
    filtered_bars = data_catalog.bars(
        bar_types=[str(barType), str(hs300BarType)],
        # start="2024-01-10",  # Filter start date
        # end="2024-01-15",  # Filter end date
    )
    log.info(f"Bars between Jan 10-15: {len(filtered_bars)}", color=LogColor.YELLOW)

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

    # Add instrument and market data to the engine
    engine.add_instrument(equity)
    engine.add_instrument(queryHS300Results[0])
    engine.add_data(filtered_bars)

    # ----------------------------------------------------------------------------------
    # 5. Configure and run strategy
    # ----------------------------------------------------------------------------------

    config = MACDStrategyConfig(
        instrument_id=equity.id,
        bar_type_1min=barType,  # 根据策略定义修正参数名称
        bar_type_hs300=hs300BarType,
        fast_period=12,
        slow_period=26,
        # signal_period=9
    )

    engine.add_strategy(MACDStrategy(config=config))
    log.info(f"Added strategy for {equity.id} {barType}", color=LogColor.GREEN)

    # Execute the backtest
    engine.run()

    # Clean up resources
    engine.dispose()