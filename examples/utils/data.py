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

import concurrent
from pathlib import Path

import pandas as pd

# from sqlalchemy import create_engine
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


def process_file(file):
    df = pd.read_parquet(file, engine="pyarrow")
    symbol = df["symbol"].iloc[0] # df.Symbol
    df = df.rename(columns={"dt": "timestamp"})
    df = df.rename(columns={"vol": "volume"})
    df = df.reindex(columns=["timestamp", "open", "high", "low", "close", "volume"])
    print(df.columns)
    df = df.set_index("timestamp")

    # Define exchange name
    VENUE_NAME = "SZSE"

    # Instrument definition

    Equity_INSTRUMENT = Equity(
            instrument_id=InstrumentId(symbol=Symbol(symbol), venue=Venue(VENUE_NAME)),
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
    data_catalog = ParquetDataCatalog("./data_catalog_index")

    # Write data to the catalog
    data_catalog.write_data([Equity_INSTRUMENT])  # Store instrument definition(s)
    data_catalog.write_data(bars_list)  # Store bar data

    print(f"处理完成: {file.name}")
    return file.name

def process_czsc_data(directory_path):

    directory = Path(directory_path)
    parquet_files = directory.glob("*.parquet")

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(process_file, parquet_files))
    
    # total_length = sum(results)

    # # 使用线程池（适合I/O密集型）
    # with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    #     futures = [executor.submit(process_file, file) for file in parquet_files]
    #     results = [future.result() for future in concurrent.futures.as_completed(futures)]

    print("处理完成:", results)

    # results = []
    # for file in parquet_files:
    #     try:
    #         # Load raw data from parquet file and restructure them into required format for BarDataWrangler
    #         process_file(file)
    #         # file_result['文件名'] = file.name
    #         # results.append(file_result)
    #         print(f"处理完成: {file.name}")
    #     except Exception as e:
    #         print(f"处理失败 {file.name}: {e}")
    
    # if results:
    #     result_df = pd.DataFrame(results)
    #     print("\n处理结果汇总:")
    #     print(result_df)
    #     return result_df
    # else:
    #     print("没有成功处理任何文件")
    #     return None

# 使用示例
# process_czsc_data("/home/tiny/github/CZSC投研数据/A股主要指数")
#process_czsc_data("/home/tiny/github/CZSC投研数据/中证500成分股")

