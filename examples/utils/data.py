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

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine

from nautilus_trader.model.currencies import USD
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.model.instruments import Equity
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider


class FundamentalDataLoader:
    """Provides access to fundamental data from a PostgreSQL database"""

    def __init__(self, db_url: str = "postgresql://user:pass@localhost:5432/finance"):
        self.engine = create_engine(db_url)

    def get_fundamentals(self, instrument_id: InstrumentId) -> dict:
        """Retrieve fundamental data for a given instrument"""
        query = f"""
        SELECT
            pe_ratio,
            pb_ratio,
            roe,
            market_cap,
            dividend_yield
        FROM fundamentals
        WHERE symbol = '{instrument_id.symbol}'
        """
        try:
            df = pd.read_sql(query, self.engine)
            if not df.empty:
                return {
                    "pe_ratio": float(df.pe_ratio[0]),
                    "pb_ratio": float(df.pb_ratio[0]),
                    "roe": float(df.roe[0]),
                    "market_cap": float(df.market_cap[0]),
                    "dividend_yield": float(df.dividend_yield[0]),
                }
            return {}
        except Exception as e:
            print(f"Error loading fundamental data: {e}")
            return {}


def prepare_demo_data_sh000300_futures_1min():
    # Define exchange name
    VENUE_NAME = "SZSE"

    # Instrument definition for 000300.SH
    SH000300_INSTRUMENT = TestInstrumentProvider.equity(
        symbol="000300.SH",
        venue=VENUE_NAME,
    )

    # CSV file containing 1-minute bars instrument data above
    csv_file_path = "/home/tiny/github/CZSC投研数据/A股主要指数/000300.SH.parquet"

    # Load raw data from CSV file and restructure them into required format for BarDataWrangler
    df = pd.read_parquet(csv_file_path, engine="pyarrow")
    print(df.columns)
    print(df.head(3))
    df = df.rename(columns={"dt": "timestamp"})
    df = df.rename(columns={"vol": "volume"})
    df = df.reindex(columns=["timestamp", "open", "high", "low", "close", "volume"])
    print(df.columns)
    df = df.set_index("timestamp")

    # Define bar type
    SH000300_1MIN_BARTYPE = BarType.from_str(f"{SH000300_INSTRUMENT.id}-1-MINUTE-LAST-EXTERNAL")

    # Convert DataFrame rows into Bar objects
    wrangler = BarDataWrangler(SH000300_1MIN_BARTYPE, SH000300_INSTRUMENT)
    bars_list: list[Bar] = wrangler.process(df)

    # Collect and return all prepared data
    return {
        "venue_name": VENUE_NAME,
        "instrument": SH000300_INSTRUMENT,
        "bar_type_1min": SH000300_1MIN_BARTYPE,
        "bars_list": bars_list,
    }


def prepareNautilusTraderData_1min():
    # Define exchange name
    VENUE_NAME = "SZSE"

    # Instrument definition for 000300.SH
    SH000300_INSTRUMENT = TestInstrumentProvider.equity(
        symbol="000300.SH",
        venue=VENUE_NAME,
    )

    # parquet file containing 1-minute bars instrument data above
    csv_file_path = "/home/tiny/github/CZSC投研数据/A股主要指数/000300.SH.parquet"

    # Load raw data from CSV file and restructure them into required format for BarDataWrangler
    df = pd.read_parquet(csv_file_path, engine="pyarrow")
    df = df.rename(columns={"dt": "timestamp"})
    df = df.rename(columns={"vol": "volume"})
    df = df.reindex(columns=["timestamp", "open", "high", "low", "close", "volume"])
    print(df.columns)
    df = df.set_index("timestamp")

    # Define bar type
    SH000300_1MIN_BARTYPE = BarType.from_str(f"{SH000300_INSTRUMENT.id}-1-MINUTE-LAST-EXTERNAL")

    # Convert DataFrame rows into Bar objects
    wrangler = BarDataWrangler(SH000300_1MIN_BARTYPE, SH000300_INSTRUMENT)
    bars_list: list[Bar] = wrangler.process(df)

    # Collect and return all prepared data
    return {
        "venue_name": VENUE_NAME,
        "instrument": SH000300_INSTRUMENT,
        "bar_type_1min": SH000300_1MIN_BARTYPE,
        "bars_list": bars_list,
    }


def process_data(df):
    df = df.rename(columns={"dt": "timestamp"})
    df = df.rename(columns={"vol": "volume"})
    df = df.reindex(columns=["timestamp", "open", "high", "low", "close", "volume"])
    print(df.columns)
    df = df.set_index("timestamp")

    # Define exchange name
    VENUE_NAME = "SZSE"

    # Instrument definition
    symbol="000300.SH" # df.Symbol
    venue=VENUE_NAME

    Equity_INSTRUMENT = Equity(
            instrument_id=InstrumentId(symbol=Symbol(symbol), venue=Venue(venue)),
            raw_symbol=Symbol(symbol),
            currency=USD,
            price_precision=2,
            price_increment=Price.from_str("0.01"),
            lot_size=Quantity.from_int(100),
            isin="US0378331005",
            ts_event=0,
            ts_init=0,
        )

    # Define bar type
    BARTYPE = BarType.from_str(f"{Equity_INSTRUMENT.id}-1-MINUTE-LAST-EXTERNAL")

    # Convert DataFrame rows into Bar objects
    wrangler = BarDataWrangler(BARTYPE, Equity_INSTRUMENT)
    bars_list: list[Bar] = wrangler.process(df)

    # Create a Data Catalog (folder will be created if it doesn't exist)
    data_catalog = ParquetDataCatalog("./data_catalog")

    # Write data to the catalog
    data_catalog.write_data([Equity_INSTRUMENT])  # Store instrument definition(s)
    data_catalog.write_data(bars_list)  # Store bar data

def process_czsc_data(directory_path):

    directory = Path(directory_path)
    parquet_files = directory.glob("*.parquet")
    
    results = []
    for file in parquet_files:
        try:
            # Load raw data from parquet file and restructure them into required format for BarDataWrangler
            df = pd.read_parquet(file, engine="pyarrow")
            df = df.rename(columns={"dt": "timestamp"})
            df = df.rename(columns={"vol": "volume"})
            df = df.reindex(columns=["timestamp", "open", "high", "low", "close", "volume"])
            print(df.columns)
            df = df.set_index("timestamp")

            file_result = process_data(df)
            file_result['文件名'] = file.name
            results.append(file_result)
            print(f"处理完成: {file.name}")
        except Exception as e:
            print(f"处理失败 {file.name}: {str(e)}")
    
    if results:
        result_df = pd.DataFrame(results)
        print("\n处理结果汇总:")
        print(result_df)
        return result_df
    else:
        print("没有成功处理任何文件")
        return None

# 使用示例
process_czsc_data("/path/to/your/csv/files")
