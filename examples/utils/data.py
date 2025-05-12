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

import pandas as pd
from sqlalchemy import create_engine

from nautilus_trader import TEST_DATA_DIR
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId
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


def prepare_demo_data_eurusd_futures_1min_test():
    # Define exchange name
    VENUE_NAME = "XCME"

    # CSV file containing 1-minute bars instrument data above
    csv_file_path = rf"{TEST_DATA_DIR}/xcme/6EH4.{VENUE_NAME}_1min_bars_20240101_20240131.csv.gz"

    # Load raw data from CSV file and restructure them into required format for BarDataWrangler
    df = pd.read_csv(csv_file_path, header=0, index_col=False)
    df = df.reindex(columns=["timestamp_utc", "open", "high", "low", "close", "volume"])
    print(df.columns)
    print(df.head(3))


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

    # CSV file containing 1-minute bars instrument data above
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
