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
The `data` module provides QMT data integration with Nautilus Trader.
"""

from datetime import datetime

import pandas as pd
import pytz

from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


class QMTDataParser:
    """
    Provides data parsing functionality for QMT market data.
    """

    @staticmethod
    def parse_bar(qmt_bar: dict, instrument_id: InstrumentId, precision: int = 4) -> Bar:
        """
        Convert QMT K-line data to Nautilus Bar object.

        Parameters
        ----------
        qmt_bar : dict
            The QMT bar data dictionary.
        instrument_id : InstrumentId
            The instrument identifier.
        precision : int, optional
            The price precision, by default 4.

        Returns
        -------
        Bar
            The converted Nautilus Bar.
        """
        bar_type = BarType.from_str(f"{instrument_id}-1-MINUTE-LAST-EXTERNAL")

        return Bar(
            bar_type=bar_type,
            open=Price(qmt_bar["open"], precision=precision),
            high=Price(qmt_bar["high"], precision=precision),
            low=Price(qmt_bar["low"], precision=precision),
            close=Price(qmt_bar["close"], precision=precision),
            volume=Quantity(qmt_bar["volume"], precision=0),
            ts_event=datetime.fromtimestamp(qmt_bar["timestamp"]/1000, tz=pytz.UTC).timestamp() * 1e9,
            ts_init=datetime.utcnow().timestamp() * 1e9,
        )

    @staticmethod
    def parse_tick(qmt_tick: dict, instrument_id: InstrumentId, precision: int = 4) -> QuoteTick:
        """
        Convert QMT tick data to Nautilus QuoteTick object.

        Parameters
        ----------
        qmt_tick : dict
            The QMT tick data dictionary.
        instrument_id : InstrumentId
            The instrument identifier.
        precision : int, optional
            The price precision, by default 4.

        Returns
        -------
        QuoteTick
            The converted Nautilus QuoteTick.
        """
        return QuoteTick(
            instrument_id=instrument_id,
            bid=Price(qmt_tick["bid"], precision=precision),
            ask=Price(qmt_tick["ask"], precision=precision),
            bid_size=Quantity(qmt_tick["bid_size"], precision=0),
            ask_size=Quantity(qmt_tick["ask_size"], precision=0),
            ts_event=datetime.fromtimestamp(qmt_tick["timestamp"]/1000, tz=pytz.UTC).timestamp() * 1e9,
            ts_init=datetime.utcnow().timestamp() * 1e9,
        )


class QMTDataLoader:
    """
    Provides data loading functionality for QMT market data.
    """

    def __init__(self, qmt_path: str = None):
        """
        Initialize a new instance of the QMTDataLoader class.

        Parameters
        ----------
        qmt_path : str, optional
            The path to QMT installation, by default None.
        """
        self.qmt_path = qmt_path
        self._initialize_qmt()

    def _initialize_qmt(self):
        """
        Initialize QMT connection.
        """
        try:
            import xtquant
            self.xtdata = xtquant.xtdata
            if self.qmt_path:
                self.xtdata.set_qmt_path(self.qmt_path)
        except ImportError:
            raise ImportError("xtquant package not found. Please install QMT first.")

    def load_bars(
        self,
        instrument_id: InstrumentId,
        start_time: datetime,
        end_time: datetime,
        bar_type: BarType = None,
    ) -> list[Bar]:
        """
        Load historical bar data from QMT.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument identifier.
        start_time : datetime
            The start time for the data request.
        end_time : datetime
            The end time for the data request.
        bar_type : BarType, optional
            The bar type, by default None.

        Returns
        -------
        list[Bar]
            A list of Nautilus Bar objects.
        """
        if bar_type is None:
            bar_type = BarType.from_str(f"{instrument_id}-1-MINUTE-LAST-EXTERNAL")

        # Convert to QMT format
        symbol = instrument_id.symbol
        start_str = start_time.strftime("%Y%m%d")
        end_str = end_time.strftime("%Y%m%d")

        # Request data from QMT
        df = self.xtdata.get_k_data(
            symbol,
            start_str,
            end_str,
            ktype="1m",
        )

        if df is None or df.empty:
            return []

        # Rename columns to match Nautilus format
        df = df.rename(columns={
            "time": "timestamp",
            "vol": "volume",
        })

        # Convert timestamp to milliseconds
        df["timestamp"] = pd.to_datetime(df["timestamp"]).astype(int) // 10**6

        # Convert to Bar objects
        bars = []
        for _, row in df.iterrows():
            qmt_bar = {
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "timestamp": row["timestamp"],
            }
            bar = QMTDataParser.parse_bar(qmt_bar, instrument_id)
            bars.append(bar)

        return bars

    def load_bars_df(
        self,
        instrument_id: InstrumentId,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """
        Load historical bar data from QMT as DataFrame.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument identifier.
        start_time : datetime
            The start time for the data request.
        end_time : datetime
            The end time for the data request.

        Returns
        -------
        pd.DataFrame
            A DataFrame containing the bar data.
        """
        # Convert to QMT format
        symbol = instrument_id.symbol
        start_str = start_time.strftime("%Y%m%d")
        end_str = end_time.strftime("%Y%m%d")

        # Request data from QMT
        df = self.xtdata.get_k_data(
            symbol,
            start_str,
            end_str,
            ktype="1m",
        )

        if df is None:
            return pd.DataFrame()

        # Rename columns to match Nautilus format
        df = df.rename(columns={
            "time": "timestamp",
            "vol": "volume",
        })

        return df
