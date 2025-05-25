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
from pathlib import Path

from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.persistence.wranglers import BarDataWrangler
from nautilus_trader.test_kit.providers import TestInstrumentProvider


def prepare_apple_stock_data(data_path, timeframes=None):
    """
    Prepare Apple stock data for backtesting.
    
    Parameters
    ----------
    data_path : str
        Path to the Apple stock data file (CSV or Parquet format)
    timeframes : list of str, optional
        List of timeframes to prepare (e.g., ["1-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"])
        If None, only 1-MINUTE data will be prepared
        
    Returns
    -------
    dict
        Dictionary containing prepared data
    """
    # Define exchange name (NASDAQ)
    VENUE_NAME = "NASDAQ"
    
    # If timeframes not specified, default to 1-MINUTE only
    if timeframes is None:
        timeframes = ["1-MINUTE"]
    
    # Instrument definition for Apple stock
    APPLE_INSTRUMENT = TestInstrumentProvider.equity(
        symbol="AAPL",
        venue=VENUE_NAME,
    )
    
    # Load raw data from file
    file_path = Path(data_path)
    if file_path.suffix == '.csv':
        df = pd.read_csv(file_path)
    elif file_path.suffix in ['.parquet', '.pq']:
        df = pd.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    # Ensure the dataframe has the required columns
    required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
    
    # Rename columns if needed (adjust based on your data format)
    column_mapping = {
        "date": "timestamp",
        "time": "timestamp",
        "Date": "timestamp",
        "Time": "timestamp",
        "DateTime": "timestamp",
        "Datetime": "timestamp",
        "datetime": "timestamp",
        "vol": "volume",
        "Volume": "volume",
    }
    
    df = df.rename(columns={col: column_mapping[col] for col in column_mapping if col in df.columns})
    
    # Ensure timestamp is in datetime format
    if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Reindex to ensure columns are in the right order
    df = df.reindex(columns=required_columns)
    
    # Set timestamp as index
    df = df.set_index("timestamp")
    
    # Prepare data for each timeframe
    prepared_data = {
        "venue_name": VENUE_NAME,
        "instrument": APPLE_INSTRUMENT,
        "bar_types": {},
        "bars_lists": {},
    }
    
    for timeframe in timeframes:
        # Define bar type for this timeframe
        bar_type = BarType.from_str(f"{APPLE_INSTRUMENT.id}-{timeframe}-LAST-EXTERNAL")
        
        # Convert DataFrame rows into Bar objects
        wrangler = BarDataWrangler(bar_type, APPLE_INSTRUMENT)
        bars_list = wrangler.process(df)
        
        # Store in the prepared data
        prepared_data["bar_types"][timeframe] = bar_type
        prepared_data["bars_lists"][timeframe] = bars_list
    
    return prepared_data


def prepare_nasdaq100_index_data(data_path, timeframes=None):
    """
    Prepare NASDAQ 100 index data for backtesting.
    
    Parameters
    ----------
    data_path : str
        Path to the NASDAQ 100 index data file (CSV or Parquet format)
    timeframes : list of str, optional
        List of timeframes to prepare (e.g., ["1-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"])
        If None, only 1-MINUTE data will be prepared
        
    Returns
    -------
    dict
        Dictionary containing prepared data
    """
    # Define exchange name
    VENUE_NAME = "NASDAQ"
    
    # If timeframes not specified, default to 1-MINUTE only
    if timeframes is None:
        timeframes = ["1-MINUTE"]
    
    # Instrument definition for NASDAQ 100 index
    NASDAQ100_INSTRUMENT = TestInstrumentProvider.equity(
        symbol="NDX",
        venue=VENUE_NAME,
    )
    
    # Load raw data from file
    file_path = Path(data_path)
    if file_path.suffix == '.csv':
        df = pd.read_csv(file_path)
    elif file_path.suffix in ['.parquet', '.pq']:
        df = pd.read_parquet(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")
    
    # Ensure the dataframe has the required columns
    required_columns = ["timestamp", "open", "high", "low", "close", "volume"]
    
    # Rename columns if needed (adjust based on your data format)
    column_mapping = {
        "date": "timestamp",
        "time": "timestamp",
        "Date": "timestamp",
        "Time": "timestamp",
        "DateTime": "timestamp",
        "Datetime": "timestamp",
        "datetime": "timestamp",
        "vol": "volume",
        "Volume": "volume",
    }
    
    df = df.rename(columns={col: column_mapping[col] for col in column_mapping if col in df.columns})
    
    # Ensure timestamp is in datetime format
    if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Reindex to ensure columns are in the right order
    df = df.reindex(columns=required_columns)
    
    # Set timestamp as index
    df = df.set_index("timestamp")
    
    # Prepare data for each timeframe
    prepared_data = {
        "venue_name": VENUE_NAME,
        "instrument": NASDAQ100_INSTRUMENT,
        "bar_types": {},
        "bars_lists": {},
    }
    
    for timeframe in timeframes:
        # Define bar type for this timeframe
        bar_type = BarType.from_str(f"{NASDAQ100_INSTRUMENT.id}-{timeframe}-LAST-EXTERNAL")
        
        # Convert DataFrame rows into Bar objects
        wrangler = BarDataWrangler(bar_type, NASDAQ100_INSTRUMENT)
        bars_list = wrangler.process(df)
        
        # Store in the prepared data
        prepared_data["bar_types"][timeframe] = bar_type
        prepared_data["bars_lists"][timeframe] = bars_list
    
    return prepared_data


def prepare_demo_data():
    """
    Prepare demo data for testing when real data is not available.
    This generates synthetic data for Apple stock and NASDAQ 100 index.
    
    Returns
    -------
    tuple
        Tuple containing prepared Apple stock data and NASDAQ 100 index data
    """
    import numpy as np
    from nautilus_trader.model.identifiers import Venue
    from nautilus_trader.model.data import Bar
    
    # Define venue
    venue_name = "NASDAQ"
    
    # Create instruments
    apple_instrument = TestInstrumentProvider.equity(symbol="AAPL", venue=venue_name)
    nasdaq100_instrument = TestInstrumentProvider.equity(symbol="NDX", venue=venue_name)
    
    # Define timeframes
    timeframes = ["1-MINUTE", "15-MINUTE", "1-HOUR", "1-DAY"]
    
    # Generate synthetic data
    apple_data = {
        "venue_name": venue_name,
        "instrument": apple_instrument,
        "bar_types": {},
        "bars_lists": {},
    }
    
    nasdaq100_data = {
        "venue_name": venue_name,
        "instrument": nasdaq100_instrument,
        "bar_types": {},
        "bars_lists": {},
    }
    
    # Generate data for each timeframe
    for timeframe in timeframes:
        # Apple data
        apple_bar_type = BarType.from_str(f"{apple_instrument.id}-{timeframe}-LAST-EXTERNAL")
        apple_data["bar_types"][timeframe] = apple_bar_type
        
        # NASDAQ 100 data
        nasdaq_bar_type = BarType.from_str(f"{nasdaq100_instrument.id}-{timeframe}-LAST-EXTERNAL")
        nasdaq100_data["bar_types"][timeframe] = nasdaq_bar_type
        
        # Generate synthetic data
        np.random.seed(42)  # For reproducibility
        
        # Create synthetic bars for Apple
        start_price_apple = 150.0
        apple_bars = []
        
        # Create synthetic bars for NASDAQ 100
        start_price_nasdaq = 15000.0
        nasdaq_bars = []
        
        # Generate 1000 bars
        for i in range(1000):
            # Timestamp for the bar
            timestamp = pd.Timestamp("2023-01-01") + pd.Timedelta(minutes=i)
            
            # Generate Apple bar data
            if i == 0:
                apple_open = start_price_apple
            else:
                apple_open = apple_bars[-1].close
                
            apple_close = apple_open * (1 + np.random.normal(0, 0.005))
            apple_high = max(apple_open, apple_close) * (1 + abs(np.random.normal(0, 0.002)))
            apple_low = min(apple_open, apple_close) * (1 - abs(np.random.normal(0, 0.002)))
            apple_volume = np.random.randint(1000, 10000)
            
            # Create Apple bar
            apple_bar = Bar(
                bar_type=apple_bar_type,
                open=apple_open,
                high=apple_high,
                low=apple_low,
                close=apple_close,
                volume=apple_volume,
                ts_event=timestamp.timestamp() * 1_000_000_000,  # Convert to nanoseconds
                ts_init=timestamp.timestamp() * 1_000_000_000,   # Convert to nanoseconds
            )
            apple_bars.append(apple_bar)
            
            # Generate NASDAQ 100 bar data
            if i == 0:
                nasdaq_open = start_price_nasdaq
            else:
                nasdaq_open = nasdaq_bars[-1].close
                
            nasdaq_close = nasdaq_open * (1 + np.random.normal(0, 0.004))
            nasdaq_high = max(nasdaq_open, nasdaq_close) * (1 + abs(np.random.normal(0, 0.002)))
            nasdaq_low = min(nasdaq_open, nasdaq_close) * (1 - abs(np.random.normal(0, 0.002)))
            nasdaq_volume = np.random.randint(5000, 50000)
            
            # Create NASDAQ 100 bar
            nasdaq_bar = Bar(
                bar_type=nasdaq_bar_type,
                open=nasdaq_open,
                high=nasdaq_high,
                low=nasdaq_low,
                close=nasdaq_close,
                volume=nasdaq_volume,
                ts_event=timestamp.timestamp() * 1_000_000_000,  # Convert to nanoseconds
                ts_init=timestamp.timestamp() * 1_000_000_000,   # Convert to nanoseconds
            )
            nasdaq_bars.append(nasdaq_bar)
        
        # Store the bars
        apple_data["bars_lists"][timeframe] = apple_bars
        nasdaq100_data["bars_lists"][timeframe] = nasdaq_bars
    
    return apple_data, nasdaq100_data
