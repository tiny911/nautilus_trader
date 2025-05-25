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

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, Optional

from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.datetime import unix_nanos_to_dt
from nautilus_trader.indicators.macd import MovingAverageConvergenceDivergence
from nautilus_trader.model import Bar
from nautilus_trader.model import BarType
from nautilus_trader.model import InstrumentId
from nautilus_trader.model import Position
from nautilus_trader.model import Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import PositionSide
from nautilus_trader.model.enums import PriceType
from nautilus_trader.trading.strategy import Strategy


class MultiMACDStrategyConfig(StrategyConfig, frozen=True):
    """
    Configuration for the MultiMACDStrategy.
    """
    # Instruments
    apple_instrument_id: InstrumentId
    nasdaq_instrument_id: InstrumentId
    
    # Bar types for different timeframes
    apple_bar_types: Dict[str, BarType]
    nasdaq_bar_types: Dict[str, BarType]
    
    # MACD parameters
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    
    # Trading parameters
    trade_size: Decimal = Decimal("100")
    
    # Thresholds for MACD signals
    apple_entry_threshold: float = 0.1
    nasdaq_bullish_threshold: float = 0.5
    nasdaq_bearish_threshold: float = -0.5


class MultiMACDStrategy(Strategy):
    """
    A strategy that uses multi-period MACD indicators to trade Apple stock
    based on market conditions determined by NASDAQ 100 index.
    """
    
    def __init__(self, config: MultiMACDStrategyConfig):
        super().__init__(config=config)
        
        # Store configuration
        self.apple_instrument_id = config.apple_instrument_id
        self.nasdaq_instrument_id = config.nasdaq_instrument_id
        self.apple_bar_types = config.apple_bar_types
        self.nasdaq_bar_types = config.nasdaq_bar_types
        self.trade_size = Quantity.from_decimal(config.trade_size)
        
        # Thresholds
        self.apple_entry_threshold = config.apple_entry_threshold
        self.nasdaq_bullish_threshold = config.nasdaq_bullish_threshold
        self.nasdaq_bearish_threshold = config.nasdaq_bearish_threshold


        # Aggregated 5-min bar data
        self.bar_type_5min = BarType.from_str(f"{self.instrument_id}-5-MINUTE-LAST-INTERNAL")
        self.count_5min_bars = 0  # Counter for received 5-minute bars
        
        # Initialize MACD indicators for Apple stock
        self.apple_macds = {}
        for timeframe, bar_type in self.apple_bar_types.items():
            self.apple_macds[timeframe] = MovingAverageConvergenceDivergence(
                fast_period=config.fast_period,
                slow_period=config.slow_period,
                signal_period=config.signal_period,
                price_type=PriceType.MID,
            )
        
        # Initialize MACD indicators for NASDAQ 100 index
        self.nasdaq_macds = {}
        for timeframe, bar_type in self.nasdaq_bar_types.items():
            self.nasdaq_macds[timeframe] = MovingAverageConvergenceDivergence(
                fast_period=config.fast_period,
                slow_period=config.slow_period,
                signal_period=config.signal_period,
                price_type=PriceType.MID,
            )
        
        # Track current position
        self.position: Optional[Position] = None
        
        # Track market condition
        self.market_condition = "NEUTRAL"  # Can be "BULLISH", "BEARISH", or "NEUTRAL"
        
        # Counters for bars processed
        self.apple_bars_count = {timeframe: 0 for timeframe in self.apple_bar_types}
        self.nasdaq_bars_count = {timeframe: 0 for timeframe in self.nasdaq_bar_types}
        
        # Track when the strategy starts and ends
        self.start_time = None
        self.end_time = None
    
    def on_start(self):
        """Called when the strategy starts."""
        self.start_time = dt.datetime.now()
        self.log.info(f"Multi-period MACD strategy started at {self.start_time}")

        # Start receiving 1-minute bar updates
        self.subscribe_bars(self.bar_type_1min)

        # ==================================================================
        # POINT OF FOCUS: Setting up 5-minute bar aggregation
        #
        # To create 5-minute bars from 1-minute data, we need a special subscription format:
        # "{target_bar_type}@{source_bar_type}"
        #
        # The '@' symbol separates:
        # - Left side (target): what we want to create (5-minute bars)
        # - Right side (source): what data to use (1-minute external bars)
        #
        # Full format:
        # "{instrument_id}-{interval}-{unit}-{price_type}@{source_interval}-{source_unit}-{source}"
        #
        # Note: instrument_id and price_type are only needed in the left (target) part
        # ------------------------------------------------------------------

        # Start receiving 5-minute bar updates (created from 1-minute external data)
        bar_type_5min_subscribe = BarType.from_str(f"{self.bar_type_5min}@1-MINUTE-EXTERNAL")
        self.subscribe_bars(bar_type_5min_subscribe)
        
        # Subscribe to all bar types
        for bar_type in self.apple_bar_types.values():
            self.subscribe_bars(bar_type)
        
        for bar_type in self.nasdaq_bar_types.values():
            self.subscribe_bars(bar_type)
    
    def on_bar(self, bar: Bar):
        """
        Called when a new bar is received.
        
        Parameters
        ----------
        bar : Bar
            The bar received.
        """
        # Determine if this is an Apple bar or NASDAQ bar
        if bar.bar_type.instrument_id == self.apple_instrument_id:
            # Process Apple bar
            for timeframe, bar_type in self.apple_bar_types.items():
                if bar.bar_type == bar_type:
                    self.apple_bars_count[timeframe] += 1
                    self.apple_macds[timeframe].handle_bar(bar)
                    self.log.debug(
                        f"Apple {timeframe} Bar #{self.apple_bars_count[timeframe]} | "
                        f"Time: {unix_nanos_to_dt(bar.ts_event):%Y-%m-%d %H:%M:%S} | "
                        f"MACD: {self.apple_macds[timeframe].value:.4f} | "
                        f"Signal: {self.apple_macds[timeframe].signal:.4f} | "
                        f"Histogram: {self.apple_macds[timeframe].histogram:.4f}",
                        color=LogColor.BLUE,
                    )
        
        elif bar.bar_type.instrument_id == self.nasdaq_instrument_id:
            # Process NASDAQ bar
            for timeframe, bar_type in self.nasdaq_bar_types.items():
                if bar.bar_type == bar_type:
                    self.nasdaq_bars_count[timeframe] += 1
                    self.nasdaq_macds[timeframe].handle_bar(bar)
                    self.log.debug(
                        f"NASDAQ {timeframe} Bar #{self.nasdaq_bars_count[timeframe]} | "
                        f"Time: {unix_nanos_to_dt(bar.ts_event):%Y-%m-%d %H:%M:%S} | "
                        f"MACD: {self.nasdaq_macds[timeframe].value:.4f} | "
                        f"Signal: {self.nasdaq_macds[timeframe].signal:.4f} | "
                        f"Histogram: {self.nasdaq_macds[timeframe].histogram:.4f}",
                        color=LogColor.YELLOW,
                    )
        
        # Check if all indicators are initialized
        if not self.all_indicators_initialized():
            return
        
        # Update market condition based on NASDAQ MACD
        self.update_market_condition()
        
        # Check for trading signals
        self.check_for_entry_signals()
        self.check_for_exit_signals()
    
    def all_indicators_initialized(self) -> bool:
        """
        Check if all MACD indicators are initialized.
        
        Returns
        -------
        bool
            True if all indicators are initialized, False otherwise.
        """
        for macd in self.apple_macds.values():
            if not macd.initialized:
                return False
        
        for macd in self.nasdaq_macds.values():
            if not macd.initialized:
                return False
        
        return True
    
    def update_market_condition(self):
        """Update the market condition based on NASDAQ MACD indicators."""
        # Use daily and hourly MACD for market condition assessment
        daily_macd = self.nasdaq_macds.get("1-DAY")
        hourly_macd = self.nasdaq_macds.get("1-HOUR")
        
        if daily_macd is None or hourly_macd is None:
            return
        
        # Both daily and hourly MACD are positive and above threshold
        if (daily_macd.histogram > self.nasdaq_bullish_threshold and 
            hourly_macd.histogram > self.nasdaq_bullish_threshold):
            new_condition = "BULLISH"
        
        # Both daily and hourly MACD are negative and below threshold
        elif (daily_macd.histogram < self.nasdaq_bearish_threshold and 
              hourly_macd.histogram < self.nasdaq_bearish_threshold):
            new_condition = "BEARISH"
        
        # Mixed signals or near zero
        else:
            new_condition = "NEUTRAL"
        
        # Log if market condition changes
        if new_condition != self.market_condition:
            self.log.info(
                f"Market condition changed from {self.market_condition} to {new_condition}",
                color=LogColor.MAGENTA,
            )
            self.market_condition = new_condition
    
    def check_for_entry_signals(self):
        """Check for entry signals based on Apple MACD and market condition."""
        # Skip if we already have a position
        if self.position is not None:
            return
        
        # Get MACD values for different timeframes
        hourly_macd = self.apple_macds.get("1-HOUR")
        minute_macd = self.apple_macds.get("1-MINUTE")
        
        if hourly_macd is None or minute_macd is None:
            return
        
        # In bullish market, look for long entries
        if self.market_condition == "BULLISH":
            # Hourly MACD is positive and 1-minute MACD crosses above signal
            if (hourly_macd.histogram > 0 and 
                minute_macd.histogram > 0 and 
                minute_macd.value > self.apple_entry_threshold):
                self.enter_long()
        
        # In bearish market, look for short entries
        elif self.market_condition == "BEARISH":
            # Hourly MACD is negative and 1-minute MACD crosses below signal
            if (hourly_macd.histogram < 0 and 
                minute_macd.histogram < 0 and 
                minute_macd.value < -self.apple_entry_threshold):
                self.enter_short()
    
    def check_for_exit_signals(self):
        """Check for exit signals based on Apple MACD and market condition."""
        # Skip if we don't have a position
        if self.position is None:
            return
        
        minute_macd = self.apple_macds.get("1-MINUTE")
        
        if minute_macd is None:
            return
        
        # Exit long position
        if self.position.side == PositionSide.LONG:
            # Exit when 1-minute MACD crosses below signal or market turns bearish
            if minute_macd.histogram < 0 or self.market_condition == "BEARISH":
                self.close_position(self.position)
                self.log.info(
                    f"Exited LONG position at {minute_macd.value:.4f}",
                    color=LogColor.GREEN,
                )
        
        # Exit short position
        elif self.position.side == PositionSide.SHORT:
            # Exit when 1-minute MACD crosses above signal or market turns bullish
            if minute_macd.histogram > 0 or self.market_condition == "BULLISH":
                self.close_position(self.position)
                self.log.info(
                    f"Exited SHORT position at {minute_macd.value:.4f}",
                    color=LogColor.RED,
                )
    
    def enter_long(self):
        """Enter a long position."""
        order = self.order_factory.market(
            instrument_id=self.apple_instrument_id,
            order_side=OrderSide.BUY,
            quantity=self.trade_size,
        )
        self.submit_order(order)
        self.log.info(
            f"Entered LONG position with size {self.trade_size}",
            color=LogColor.GREEN,
        )
    
    def enter_short(self):
        """Enter a short position."""
        order = self.order_factory.market(
            instrument_id=self.apple_instrument_id,
            order_side=OrderSide.SELL,
            quantity=self.trade_size,
        )
        self.submit_order(order)
        self.log.info(
            f"Entered SHORT position with size {self.trade_size}",
            color=LogColor.RED,
        )
    
    def on_position_changed(self, position: Position):
        """
        Called when a position changes.
        
        Parameters
        ----------
        position : Position
            The position that changed.
        """
        self.position = position if not position.is_closed else None
    
    def on_stop(self):
        """Called when the strategy stops."""
        self.end_time = dt.datetime.now()
        
        # Close any open positions
        if self.position is not None and not self.position.is_closed:
            self.close_position(self.position)
        
        # Log summary
        self.log.info(f"Multi-period MACD strategy finished at {self.end_time}")
        if self.start_time is not None and self.end_time is not None:
            self.log.info(f"Strategy ran for {self.end_time - self.start_time}")
        
        # Log bar counts
        for timeframe, count in self.apple_bars_count.items():
            self.log.info(f"Processed {count} Apple {timeframe} bars")
        
        for timeframe, count in self.nasdaq_bars_count.items():
            self.log.info(f"Processed {count} NASDAQ {timeframe} bars")
