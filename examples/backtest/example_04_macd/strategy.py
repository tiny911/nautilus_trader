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

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model import Bar
from nautilus_trader.model import BarType
from nautilus_trader.model import Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import Venue
from nautilus_trader.trading.strategy import Strategy


# region 自定义指标实现
class MACD:
    """完整MACD指标实现(含MACD线、信号线、柱状图)"""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast_ema = pd.Series(dtype=float)
        self.slow_ema = pd.Series(dtype=float)
        self.signal_ema = pd.Series(dtype=float)
        self.macd_line = pd.Series(dtype=float)
        self.histogram = pd.Series(dtype=float)

        self._fast_period = fast
        self._slow_period = slow
        self._signal_period = signal
        self._initialized = False

    def update(self, price: float):
        # 计算EMA
        if len(self.fast_ema) < self._fast_period:
            self.fast_ema = pd.concat([self.fast_ema, pd.Series([price])]).tail(self._fast_period)
        else:
            ema = price * (2 / (self._fast_period + 1)) + self.fast_ema.iloc[-1] * (
                1 - 2 / (self._fast_period + 1)
            )
            self.fast_ema = pd.concat([self.fast_ema, pd.Series([ema])]).iloc[1:]

        if len(self.slow_ema) < self._slow_period:
            self.slow_ema = pd.concat([self.slow_ema, pd.Series([price])]).tail(self._slow_period)
        else:
            ema = price * (2 / (self._slow_period + 1)) + self.slow_ema.iloc[-1] * (
                1 - 2 / (self._slow_period + 1)
            )
            self.slow_ema = pd.concat([self.slow_ema, pd.Series([ema])]).iloc[1:]

        # 计算MACD线
        if len(self.fast_ema) == self._fast_period and len(self.slow_ema) == self._slow_period:
            current_macd = self.fast_ema.iloc[-1] - self.slow_ema.iloc[-1]
            self.macd_line = pd.concat([self.macd_line, pd.Series([current_macd])])

            # 计算信号线
            if len(self.macd_line) >= self._signal_period:
                signal = self.macd_line.ewm(span=self._signal_period, adjust=False).mean().iloc[-1]
                self.signal_ema = pd.concat([self.signal_ema, pd.Series([signal])])

                # 计算柱状图
                self.histogram = pd.concat([self.histogram, pd.Series([current_macd - signal])])

                if not self._initialized and len(self.histogram) > 3:
                    self._initialized = True

    @property
    def is_initialized(self):
        return self._initialized


# endregion


# region 策略配置
class DualMACDConfig(StrategyConfig, frozen=True):
    instrument_stock: str
    instrument_index: str
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ndx_fast: int = 50
    ndx_slow: int = 200
    ndx_signal: int = 9
    enable_short: bool = False


class DualMACDStrategy(Strategy):
    def __init__(self, config: DualMACDConfig):
        super().__init__(config)

        # 股票指标
        self.macd = MACD(
            fast=config.macd_fast, slow=config.macd_slow, signal=config.macd_signal
        )

        # 指数指标
        self.index_macd = MACD(fast=config.ndx_fast, slow=config.ndx_slow, signal=config.ndx_signal)

        self.enable_short = config.enable_short
        self.stock = config.instrument_stock
        self.index = config.instrument_index
        self.account_id = None  # Will be set in on_start

    def on_start(self):
        # Get account ID from venue
        venue = Venue("SZSE")
        account = self.cache.account_for_venue(venue)
        if not account:
            self.log.error(f"No account found for venue {venue}")
            return
            
        # Ensure we store the AccountId, not the account object
        from nautilus_trader.model.identifiers import AccountId
        if isinstance(account, AccountId):
            self.account_id = account
        else:
            self.account_id = account.id
            self.log.debug(f"Extracted AccountId {self.account_id} from account object")

        self.subscribe_bars(BarType.from_str(f"{self.stock}-1-MINUTE-LAST-EXTERNAL"))
        self.subscribe_bars(BarType.from_str(f"{self.index}-1-MINUTE-LAST-EXTERNAL"))
        # self.subscribe_bars(self.bar_type_1min)
        # self.subscribe_bars(self.bar_type_hs300)

    def calculate_full_position_size(self) -> Quantity:
        """Calculate position size using full available capital."""
        if not self.account_id:
            self.log.warning("No account_id set, using fallback position size")
            return Quantity.from_int(1)  # Fallback if account not set
            
        try:
            account = self.cache.account(self.account_id)
            if not account:
                self.log.warning(f"Account not found for {self.account_id}, using fallback position size")
                return Quantity.from_int(1)  # Fallback if account not found
            
            # Get available balance (adjust based on your broker's margin requirements)
            available = account.balance_free()
        except Exception as e:
            self.log.error(f"Error calculating position size: {e}")
            return Quantity.from_int(1)  # Fallback on error
        
        # Get current price
        last_quote = self.cache.quote_tick(self.stock)
        if not last_quote:
            return Quantity.from_int(1)  # Fallback if no price
        
        # Calculate max position size (adjust for your risk parameters)
        position_size = available / last_quote.ask
        return Quantity.from_float(position_size)

    def on_bar(self, bar: Bar):
        # 更新对应品种的指标
        if bar.bar_type == BarType.from_str(f"{self.stock}-1-MINUTE-LAST-EXTERNAL"):
            self.macd.update(bar.close)
        elif bar.bar_type == BarType.from_str(f"{self.index}-1-MINUTE-LAST-EXTERNAL"):
            self.index_macd.update(bar.close)

        # 检查指标初始化状态
        if not (self.macd.is_initialized and self.index_macd.is_initialized):
            return

        # 获取当前持仓
        positions = self.cache.positions(instrument_id=self.stock)
        position = positions[0] if positions else None

        # 市场趋势判断
        market_bullish = (
            self.index_macd.macd_line.iloc[-1] > self.index_macd.signal_ema.iloc[-1]
            and self.index_macd.histogram.iloc[-1] > 0
        )

        # 交易信号
        stock_buy = (
            self.macd.macd_line.iloc[-1] > self.macd.signal_ema.iloc[-1]
            and self.macd.histogram.iloc[-1] > 0
        )
        stock_sell = (
            self.macd.macd_line.iloc[-1] < self.macd.signal_ema.iloc[-1]
            and self.macd.histogram.iloc[-1] < 0
        )

        # 执行交易逻辑
        if market_bullish:
            if stock_buy and not position:
                self.submit_order(
                    self.order_factory.market(
                        instrument_id=self.stock,
                        order_side=OrderSide.BUY,
                        quantity=self.calculate_full_position_size(),
                    )
                )
            elif stock_sell and position and position.is_long:
                self.close_position(position)
        else:
            if position:
                self.close_position(position)


# endregion
