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
The `execution` module provides QMT order execution integration with Nautilus Trader.
"""

from datetime import datetime
from typing import Optional

import pytz

from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import Logger
from nautilus_trader.execution.client import ExecutionClient
from nautilus_trader.execution.reports import ExecutionReport
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.orders import Order


class QMTExecutionClient(ExecutionClient):
    """
    Provides execution client integration with QMT trading platform.
    """

    def __init__(
        self,
        client_id: str,
        account_id: str,
        qmt_path: Optional[str] = None,
        logger: Optional[Logger] = None,
    ):
        """
        Initialize a new instance of the QMTExecutionClient class.

        Parameters
        ----------
        client_id : str
            The client identifier.
        account_id : str
            The account identifier.
        qmt_path : str, optional
            The path to QMT installation, by default None.
        logger : Logger, optional
            The logger, by default None.
        """
        super().__init__(
            client_id=client_id,
            venue=None,  # Will be set per instrument
            logger=logger,
            clock=LiveClock(),
        )

        self.account_id = account_id
        self.qmt_path = qmt_path
        self._order_map: dict[ClientOrderId, VenueOrderId] = {}
        self._initialize_qmt()

    def _initialize_qmt(self):
        """
        Initialize QMT connection.
        """
        try:
            import xtquant
            self.xttrader = xtquant.xttrader
            if self.qmt_path:
                self.xttrader.set_qmt_path(self.qmt_path)

            # Connect to QMT
            self.session = self.xttrader.connect(self.account_id)

            # Register callbacks
            self.xttrader.register_callback(self._on_order_status, "order_status")
            self.xttrader.register_callback(self._on_order_deal, "order_deal")

            self._log.info(f"Connected to QMT with account {self.account_id}")
        except ImportError:
            raise ImportError("xtquant package not found. Please install QMT first.")

    def _on_order_status(self, order_info):
        """
        Handle order status updates from QMT.

        Parameters
        ----------
        order_info : dict
            The order information from QMT.
        """
        venue_order_id = VenueOrderId(order_info["order_id"])
        client_order_id = None

        # Find client order ID from map
        for client_id, venue_id in self._order_map.items():
            if venue_id == venue_order_id:
                client_order_id = client_id
                break

        if client_order_id is None:
            self._log.warning(f"Received order status for unknown order {venue_order_id}")
            return

        # Map QMT status to Nautilus status
        status_map = {
            0: OrderStatus.SUBMITTED,  # 已报
            1: OrderStatus.ACCEPTED,   # 部成
            2: OrderStatus.FILLED,     # 已成
            3: OrderStatus.REJECTED,   # 已撤
            4: OrderStatus.REJECTED,   # 废单
        }

        status = status_map.get(order_info["status"], OrderStatus.REJECTED)

        # Generate execution report
        report = ExecutionReport(
            client_order_id=client_order_id,
            venue_order_id=venue_order_id,
            account_id=self.account_id,
            status=status,
            ts_event=datetime.now(pytz.UTC).timestamp() * 1e9,
            ts_init=datetime.now(pytz.UTC).timestamp() * 1e9,
        )

        # Send report to execution engine
        self._handle_report(report)

    def _on_order_deal(self, deal_info):
        """
        Handle order execution reports from QMT.

        Parameters
        ----------
        deal_info : dict
            The deal information from QMT.
        """
        venue_order_id = VenueOrderId(deal_info["order_id"])
        client_order_id = None

        # Find client order ID from map
        for client_id, venue_id in self._order_map.items():
            if venue_id == venue_order_id:
                client_order_id = client_id
                break

        if client_order_id is None:
            self._log.warning(f"Received deal for unknown order {venue_order_id}")
            return

        # Generate execution report
        report = ExecutionReport(
            client_order_id=client_order_id,
            venue_order_id=venue_order_id,
            account_id=self.account_id,
            trade_id=TradeId(deal_info["deal_id"]),
            last_qty=Quantity(deal_info["deal_volume"]),
            last_px=Price(deal_info["deal_price"]),
            ts_event=datetime.now(pytz.UTC).timestamp() * 1e9,
            ts_init=datetime.now(pytz.UTC).timestamp() * 1e9,
        )

        # Send report to execution engine
        self._handle_report(report)

    def _submit_order(self, order: Order) -> VenueOrderId:
        """
        Submit an order to QMT.

        Parameters
        ----------
        order : Order
            The order to submit.

        Returns
        -------
        VenueOrderId
            The venue order ID.
        """
        # Map Nautilus order side to QMT side
        side_map = {
            OrderSide.BUY: 0,   # 买入
            OrderSide.SELL: 1,  # 卖出
        }

        # Map Nautilus order type to QMT type
        type_map = {
            OrderType.MARKET: 1,  # 市价单
            OrderType.LIMIT: 0,   # 限价单
        }

        # Prepare QMT order parameters
        qmt_order = {
            "symbol": order.instrument_id.symbol,
            "price": float(order.price) if order.price else 0.0,
            "volume": int(order.quantity),
            "side": side_map.get(order.side, 0),
            "order_type": type_map.get(order.order_type, 0),
            "account": self.account_id,
        }

        # Submit order to QMT
        order_id = self.xttrader.order(qmt_order)

        if not order_id:
            self._log.error(f"Failed to submit order {order.client_order_id}")
            return VenueOrderId("0")

        venue_order_id = VenueOrderId(order_id)

        # Store mapping
        self._order_map[order.client_order_id] = venue_order_id

        return venue_order_id

    def _cancel_order(self, venue_order_id: VenueOrderId) -> bool:
        """
        Cancel an order with QMT.

        Parameters
        ----------
        venue_order_id : VenueOrderId
            The venue order ID to cancel.

        Returns
        -------
        bool
            If the cancel request was successful.
        """
        result = self.xttrader.cancel_order(str(venue_order_id))
        return result

    # -- ExecutionClient abstract method implementations -- #

    def connect(self):
        """Connect to the execution venue."""
        if not self.session:
            self._initialize_qmt()

    def disconnect(self):
        """Disconnect from the execution venue."""
        if self.session:
            self.xttrader.disconnect()
            self.session = None

    def submit_order(self, order: Order, position_id=None):
        """
        Submit the given order to the execution venue.

        Parameters
        ----------
        order : Order
            The order to submit.
        position_id : PositionId, optional
            The position ID for the order, by default None.
        """
        self._log.info(f"Submitting order {order}")

        venue_order_id = self._submit_order(order)

        # Generate submitted report
        if venue_order_id != VenueOrderId("0"):
            report = ExecutionReport(
                client_order_id=order.client_order_id,
                venue_order_id=venue_order_id,
                account_id=self.account_id,
                status=OrderStatus.SUBMITTED,
                ts_event=datetime.now(pytz.UTC).timestamp() * 1e9,
                ts_init=datetime.now(pytz.UTC).timestamp() * 1e9,
            )

            # Send report to execution engine
            self._handle_report(report)

    def cancel_order(self, order: Order, position_id=None):
        """
        Cancel the given order at the execution venue.

        Parameters
        ----------
        order : Order
            The order to cancel.
        position_id : PositionId, optional
            The position ID for the order, by default None.
        """
        self._log.info(f"Cancelling order {order}")

        venue_order_id = self._order_map.get(order.client_order_id)

        if venue_order_id:
            success = self._cancel_order(venue_order_id)

            if not success:
                self._log.warning(f"Failed to cancel order {order.client_order_id}")

    def modify_order(self, order: Order, position_id=None):
        """
        Modify the given order at the execution venue.

        Parameters
        ----------
        order : Order
            The order to modify.
        position_id : PositionId, optional
            The position ID for the order, by default None.
        """
        self._log.info(f"Modifying order {order}")

        # QMT doesn't support direct order modification
        # Cancel the existing order and submit a new one
        venue_order_id = self._order_map.get(order.client_order_id)

        if venue_order_id:
            success = self._cancel_order(venue_order_id)

            if success:
                # Submit as a new order
                self.submit_order(order, position_id)
            else:
                self._log.warning(f"Failed to cancel order {order.client_order_id} for modification")
