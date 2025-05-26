#!/usr/bin/env python3
from decimal import Decimal
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.core.nautilus_pyo3 import BarType
from nautilus_trader.model.currencies import USD
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.objects import Money
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from strategy import MultiTimeframeMACDConfig, MultiTimeframeMACDStrategy

log = Logger(__name__)

def backtest():
    # Initialize backtest engine
    engine = BacktestEngine(BacktestEngineConfig(
        logging=LoggingConfig(log_level="ERROR"),
    ))
    
    # Add SZSE venue for the instrument
    engine.add_venue(
        venue=Venue("SZSE"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(1_000_000, USD)],
        base_currency=USD,
        default_leverage=Decimal(1),
    )

    # Load data from catalog
    data_catalog = ParquetDataCatalog("./data_catalog")
    instrument_id = InstrumentId.from_str("000300.SH.SZSE")  # 使用沪深300指数作为测试instrument
    instruments = data_catalog.instruments()
    instrument = next((i for i in instruments if i.id == instrument_id), None)
    if instrument is None:
        raise ValueError(f"Instrument {instrument_id} not found in catalog")
    
    # Define bar types for all timeframes as strings
    bar_type_strs = [
        f"{instrument_id}-1-MINUTE-LAST-EXTERNAL",
        f"{instrument_id}-5-MINUTE-LAST-EXTERNAL",
        f"{instrument_id}-15-MINUTE-LAST-EXTERNAL",
        f"{instrument_id}-30-MINUTE-LAST-EXTERNAL",
        f"{instrument_id}-60-MINUTE-LAST-EXTERNAL"
    ]

    # Load bars
    bars = data_catalog.bars(bar_types=bar_type_strs)

    # Add data to engine
    engine.add_instrument(instrument)
    engine.add_data(bars)

    # Configure strategy
    strategy_config = MultiTimeframeMACDConfig(
        instrument_id=instrument_id,
        timeframes=["1m", "5m", "15m", "30m", "60m"],
        fast_period=12,
        slow_period=26,
        signal_period=9
    )

    # Add strategy
    engine.add_strategy(MultiTimeframeMACDStrategy(config=strategy_config))

    # Run backtest
    engine.run()

    # Generate reports
    print(engine.trader.generate_account_report(Venue("SIM")))
    print(engine.trader.generate_order_fills_report())
    print(engine.trader.generate_positions_report())

if __name__ == "__main__":
    backtest()
