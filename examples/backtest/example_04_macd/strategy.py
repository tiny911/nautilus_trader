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

import datetime as dt

from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import StrategyConfig

from nautilus_trader.indicators.macd import MovingAverageConvergenceDivergence

from nautilus_trader.trading.strategy import Strategy

from nautilus_trader.core.datetime import unix_nanos_to_dt
from nautilus_trader.model import BarType, Quantity
from nautilus_trader.model import Bar
from nautilus_trader.model import Position
from nautilus_trader.model import InstrumentId
from nautilus_trader.model.enums import PriceType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import PositionSide


class MACDStrategyConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type_1min: BarType
    fast_period: int = 12
    slow_period: int = 26
    trading_side = 10_000
    enter_threshold: float = 0.00010


# Create a subclass of Strategy class
class MACDStrategy(Strategy):
    def __init__(self, config: MACDStrategyConfig):
        super().__init__()
        self.bar_type_1min = config.bar_type_1min

        self.macd = MovingAverageConvergenceDivergence(
            fast_period=config.fast_period,
            slow_period=config.slow_period,
            price_type=PriceType.MID
        )
        self.instrument_id = config.instrument_id
        self.trade_size = Quantity.from_int(config.trading_side)

        self.position: Position | None = None
        self.enter_threshold = config.enter_threshold

        self.count_processed_bars = 0

        self.start_time = None
        self.end_time = None

    def on_start(self):
        self.start_time = dt.datetime.now()

        self.subscribe_bars(self.bar_type_1min)

        self.log.info(f"My MACD strategy started at {self.start_time}")

    def on_bar(self, bar: Bar):

        self.count_processed_bars += 1

        self.macd.handle_bar(bar)
        if not self.macd.initialized:
            return

        self.check_for_entry()
        self.check_for_exit()

    def check_for_entry(self):
        if self.macd.value >= self.enter_threshold:
            # If already in Long position do nothing
            if self.position and self.position.side == PositionSide.LONG:
                return
            # Else make order
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.trade_size
            )
            self.submit_order(order)

        elif self.macd.value < -self.enter_threshold:
            # If already in Short poisition do nothing
            if self.position and self.position.side == PositionSide.SHORT:
                return
            # Else make order
            order = self.order_factory.market(
                instrument_id=self.instrument_id,
                order_side=OrderSide.SELL,
                quantity=self.trade_size
            )
            self.submit_order(order)

    def check_for_exit(self):
        # If we are in a Short position, exit when MACD value is positive
        if self.macd.value >= 0:
            if self.position and self.position.side == PositionSide.SHORT:
                self.close_position(self.position)

        # If we are in a Long position, exit when MACD value is negative
        else:
            if self.position and self.position.side == PositionSide.LONG:
                self.close_position(self.position)

    def on_end(self):

        self.end_time = dt.datetime.now()
        self.close_all_positions(instrument_id=self.config.instrument_id)
        self.unsubscribe_bars()

        self.log.info(f"My MACD strategy finnished at {self.end_time}")
        self.log.info(f"Total count of 1 day bars: {self.count_processed_bars} ")


class DemoStrategy(Strategy):

    def __init__(self, bar_type_1min: BarType):
        super().__init__()

        # Extract the trading instrument's ID from the 1-minute bar configuration
        self.instrument_id = bar_type_1min.instrument_id

        # Save the 1-minute bar configuration and create a counter to track how many bars we receive
        self.bar_type_1min = bar_type_1min
        self.count_1min_bars = 0  # This will increment each time we receive a 1-minute bar

        # Track when the strategy starts and ends
        self.start_time = None
        self.end_time = None

    def on_start(self):
        # Save the exact time when strategy begins
        self.start_time = dt.datetime.now()
        self.log.info(f"Strategy started at: {self.start_time}")

        # Start receiving 1-minute bar updates
        self.subscribe_bars(self.bar_type_1min)

    def on_bar(self, bar: Bar):
        # You can implement any action here (like submit order), but for simplicity, we are just counting bars
        self.count_1min_bars += 1
        self.log.info(
            f"Bar #{self.count_1min_bars} | Time: {unix_nanos_to_dt(bar.ts_event):%Y-%m-%d %H:%M:%S} | Bar: {bar}",
            color=LogColor.BLUE,
        )

    def on_stop(self):
        # Save the exact time when strategy ends
        self.end_time = dt.datetime.now()
        self.log.info(f"Strategy finished at: {self.end_time}")

        # Show summary of how many bars we processed
        self.log.info(f"Total count of 1-MINUTE bars: {self.count_1min_bars}")
