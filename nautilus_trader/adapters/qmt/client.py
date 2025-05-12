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
The `client` module provides QMT data client integration with Nautilus Trader.
"""

from datetime import datetime
from typing import Optional

import pandas as pd

from nautilus_trader.adapters.qmt.config import QMTDataClientConfig
from nautilus_trader.adapters.qmt.data import QMTDataParser
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import Logger
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.data.client import DataClient
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Venue


class QMTDataClient(DataClient):
    """
    Provides a data client for the QMT trading platform.
    """
    
    def __init__(
        self,
        config: QMTDataClientConfig,
        logger: Optional[Logger] = None,
    ):
        """
        Initialize a new instance of the QMTDataClient class.

        Parameters
        ----------
        config : QMTDataClientConfig
            The configuration for the client.
        logger : Logger, optional
            The logger for the client, by default None.
        """
        super().__init__(
            client_id=config.client_id,
            venue=None,  # Will be set per instrument
            logger=logger,
            clock=LiveClock(),
        )

        self.qmt_path = config.qmt_path
        self._subscribed_instruments: dict[InstrumentId, bool] = {}
        self._subscribed_bars: dict[BarType, bool] = {}
        self._subscribed_quotes: dict[InstrumentId, bool] = {}
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

            # Register callbacks
            self.xtdata.register_callback(self._on_bar_update, "k_data")
            self.xtdata.register_callback(self._on_quote_update, "quote_data")

            self._log.info("Connected to QMT data service")
        except ImportError:
            raise ImportError("xtquant package not found. Please install QMT first.")

    def _on_bar_update(self, data):
        """
        Handle bar updates from QMT.

        Parameters
        ----------
        data : dict
            The bar data from QMT.
        """
        symbol = data.get("symbol")
        if not symbol:
            return

        # Find matching instrument ID
        instrument_id = None
        for id in self._subscribed_instruments:
            if id.symbol == symbol:
                instrument_id = id
                break

        if instrument_id is None:
            return

        # Convert to Nautilus Bar
        qmt_bar = {
            "open": data.get("open", 0.0),
            "high": data.get("high", 0.0),
            "low": data.get("low", 0.0),
            "close": data.get("close", 0.0),
            "volume": data.get("volume", 0),
            "timestamp": data.get("time", 0),
        }

        bar = QMTDataParser.parse_bar(qmt_bar, instrument_id)

        # Find matching bar type
        for bar_type in self._subscribed_bars:
            if bar_type.instrument_id == instrument_id:
                self._handle_bar(bar_type, bar)

    def _on_quote_update(self, data):
        """
        Handle quote updates from QMT.

        Parameters
        ----------
        data : dict
            The quote data from QMT.
        """
        symbol = data.get("symbol")
        if not symbol:
            return

        # Find matching instrument ID
        instrument_id = None
        for id in self._subscribed_quotes:
            if id.symbol == symbol:
                instrument_id = id
                break

        if instrument_id is None:
            return

        # Convert to Nautilus QuoteTick
        qmt_tick = {
            "bid": data.get("bid", 0.0),
            "ask": data.get("ask", 0.0),
            "bid_size": data.get("bid_volume", 0),
            "ask_size": data.get("ask_volume", 0),
            "timestamp": data.get("time", 0),
        }

        tick = QMTDataParser.parse_tick(qmt_tick, instrument_id)

        # Send to data engine
        self._handle_quote_tick(tick)

    def _request_bars(
        self,
        bar_type: BarType,
        start: datetime,
        end: datetime,
    ) -> list[Bar]:
        """
        Request historical bars from QMT.

        Parameters
        ----------
        bar_type : BarType
            The bar type to request.
        start : datetime
            The start time for the request.
        end : datetime
            The end time for the request.

        Returns
        -------
        List[Bar]
            A list of bars.
        """
        # Convert to QMT format
        symbol = bar_type.instrument_id.symbol
        start_str = start.strftime("%Y%m%d")
        end_str = end.strftime("%Y%m%d")

        # Map bar type to QMT ktype
        ktype_map = {
            "1-MINUTE": "1m",
            "5-MINUTE": "5m",
            "15-MINUTE": "15m",
            "30-MINUTE": "30m",
            "1-HOUR": "60m",
            "1-DAY": "1d",
        }

        ktype = ktype_map.get(f"{bar_type.spec.step}-{bar_type.spec.aggregation}", "1m")

        # Request data from QMT
        df = self.xtdata.get_k_data(
            symbol,
            start_str,
            end_str,
            ktype=ktype,
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
            bar = QMTDataParser.parse_bar(qmt_bar, bar_type.instrument_id)
            bars.append(bar)

        return bars

    # -- DataClient abstract method implementations -- #

    def connect(self):
        """Connect to the data service."""
        if not hasattr(self, "xtdata"):
            self._initialize_qmt()

    def disconnect(self):
        """Disconnect from the data service."""
        # QMT doesn't have explicit disconnect method
        return

    def reset(self):
        """Reset the client."""
        self._subscribed_instruments = {}
        self._subscribed_bars = {}
        self._subscribed_quotes = {}

    def subscribe_instrument(self, instrument_id: InstrumentId):
        """
        Subscribe to market data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to subscribe to.
        """
        PyCondition.not_none(instrument_id, "instrument_id")

        if instrument_id in self._subscribed_instruments:
            self._log.warning(f"Already subscribed to {instrument_id}")
            return

        self._subscribed_instruments[instrument_id] = True
        self._log.info(f"Subscribed to instrument {instrument_id}")

    def subscribe_order_book_deltas(self, instrument_id: InstrumentId, depth: int = 10):
        """
        Subscribe to order book delta data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to subscribe to.
        depth : int, optional
            The depth of the order book, by default 10.
        """
        self._log.warning("Order book deltas not supported by QMT")

    def subscribe_order_book_snapshots(self, instrument_id: InstrumentId, depth: int = 10):
        """
        Subscribe to order book snapshot data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to subscribe to.
        depth : int, optional
            The depth of the order book, by default 10.
        """
        self._log.warning("Order book snapshots not supported by QMT")

    def subscribe_quote_ticks(self, instrument_id: InstrumentId):
        """
        Subscribe to quote tick data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to subscribe to.
        """
        PyCondition.not_none(instrument_id, "instrument_id")

        if instrument_id in self._subscribed_quotes:
            self._log.warning(f"Already subscribed to quote ticks for {instrument_id}")
            return

        # Subscribe to QMT quotes
        self.xtdata.subscribe_quote(instrument_id.symbol)

        self._subscribed_quotes[instrument_id] = True
        self._log.info(f"Subscribed to quote ticks for {instrument_id}")

    def subscribe_trade_ticks(self, instrument_id: InstrumentId):
        """
        Subscribe to trade tick data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to subscribe to.
        """
        self._log.warning("Trade ticks not supported by QMT")

    def subscribe_bars(self, bar_type: BarType):
        """
        Subscribe to bar data for the given bar type.

        Parameters
        ----------
        bar_type : BarType
            The bar type to subscribe to.
        """
        PyCondition.not_none(bar_type, "bar_type")

        if bar_type in self._subscribed_bars:
            self._log.warning(f"Already subscribed to {bar_type}")
            return

        # Map bar type to QMT ktype
        ktype_map = {
            "1-MINUTE": "1m",
            "5-MINUTE": "5m",
            "15-MINUTE": "15m",
            "30-MINUTE": "30m",
            "1-HOUR": "60m",
            "1-DAY": "1d",
        }

        ktype = ktype_map.get(f"{bar_type.spec.step}-{bar_type.spec.aggregation}", "1m")

        # Subscribe to QMT bars
        self.xtdata.subscribe_kdata(bar_type.instrument_id.symbol, ktype)

        self._subscribed_bars[bar_type] = True
        self._log.info(f"Subscribed to {bar_type}")

    def unsubscribe_instrument(self, instrument_id: InstrumentId):
        """
        Unsubscribe from market data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to unsubscribe from.
        """
        PyCondition.not_none(instrument_id, "instrument_id")

        if instrument_id in self._subscribed_instruments:
            del self._subscribed_instruments[instrument_id]
            self._log.info(f"Unsubscribed from instrument {instrument_id}")

    def unsubscribe_order_book_deltas(self, instrument_id: InstrumentId):
        """
        Unsubscribe from order book delta data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to unsubscribe from.
        """
        pass  # Not supported

    def unsubscribe_order_book_snapshots(self, instrument_id: InstrumentId):
        """
        Unsubscribe from order book snapshot data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to unsubscribe from.
        """
        pass  # Not supported

    def unsubscribe_quote_ticks(self, instrument_id: InstrumentId):
        """
        Unsubscribe from quote tick data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to unsubscribe from.
        """
        PyCondition.not_none(instrument_id, "instrument_id")

        if instrument_id in self._subscribed_quotes:
            # Unsubscribe from QMT quotes
            self.xtdata.unsubscribe_quote(instrument_id.symbol)

            del self._subscribed_quotes[instrument_id]
            self._log.info(f"Unsubscribed from quote ticks for {instrument_id}")

    def unsubscribe_trade_ticks(self, instrument_id: InstrumentId):
        """
        Unsubscribe from trade tick data for the given instrument.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to unsubscribe from.
        """
        pass  # Not supported

    def unsubscribe_bars(self, bar_type: BarType):
        """
        Unsubscribe from bar data for the given bar type.

        Parameters
        ----------
        bar_type : BarType
            The bar type to unsubscribe from.
        """
        PyCondition.not_none(bar_type, "bar_type")

        if bar_type in self._subscribed_bars:
            # Map bar type to QMT ktype
            ktype_map = {
                "1-MINUTE": "1m",
                "5-MINUTE": "5m",
                "15-MINUTE": "15m",
                "30-MINUTE": "30m",
                "1-HOUR": "60m",
                "1-DAY": "1d",
            }

            ktype = ktype_map.get(f"{bar_type.spec.step}-{bar_type.spec.aggregation}", "1m")

            # Unsubscribe from QMT bars
            self.xtdata.unsubscribe_kdata(bar_type.instrument_id.symbol, ktype)

            del self._subscribed_bars[bar_type]
            self._log.info(f"Unsubscribed from {bar_type}")

    def request_instrument(self, instrument_id: InstrumentId, correlation_id=None):
        """
        Request instrument data.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to request.
        correlation_id : UUID, optional
            The correlation ID for the request, by default None.
        """
        self._log.warning("Instrument request not supported by QMT")

    def request_instruments(self, venue: Venue = None, correlation_id=None):
        """
        Request all instruments for the given venue.

        Parameters
        ----------
        venue : Venue, optional
            The venue to request instruments for, by default None.
        correlation_id : UUID, optional
            The correlation ID for the request, by default None.
        """
        self._log.warning("Instruments request not supported by QMT")

    def request_quote_ticks(
        self,
        instrument_id: InstrumentId,
        start: datetime,
        end: datetime,
        limit: int = None,
        correlation_id=None,
    ):
        """
        Request historical quote ticks.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to request data for.
        start : datetime
            The start time for the request.
        end : datetime
            The end time for the request.
        limit : int, optional
            The maximum number of ticks to return, by default None.
        correlation_id : UUID, optional
            The correlation ID for the request, by default None.
        """
        self._log.warning("Historical quote ticks not supported by QMT")

    def request_trade_ticks(
        self,
        instrument_id: InstrumentId,
        start: datetime,
        end: datetime,
        limit: int = None,
        correlation_id=None,
    ):
        """
        Request historical trade ticks.

        Parameters
        ----------
        instrument_id : InstrumentId
            The instrument ID to request data for.
        start : datetime
            The start time for the request.
        end : datetime
            The end time for the request.
        limit : int, optional
            The maximum number of ticks to return, by default None.
        correlation_id : UUID, optional
            The correlation ID for the request, by default None.
        """
        self._log.warning("Historical trade ticks not supported by QMT")

    def request_bars(
        self,
        bar_type: BarType,
        start: datetime,
        end: datetime,
        limit: int = None,
        correlation_id=None,
    ):
        """
        Request historical bars.

        Parameters
        ----------
        bar_type : BarType
            The bar type to request.
        start : datetime
            The start time for the request.
        end : datetime
            The end time for the request.
        limit : int, optional
            The maximum number of bars to return, by default None.
        correlation_id : UUID, optional
            The correlation ID for the request, by default None.
        """
        PyCondition.not_none(bar_type, "bar_type")
        PyCondition.not_none(start, "start")
        PyCondition.not_none(end, "end")

        self._log.info(f"Requesting {bar_type} bars from {start} to {end}")

        # Request bars from QMT
        bars = self._request_bars(bar_type, start, end)

        if limit is not None and len(bars) > limit:
            bars = bars[-limit:]

        # Send bars to data engine
        for bar in bars:
            self._handle_bar(bar_type, bar)
