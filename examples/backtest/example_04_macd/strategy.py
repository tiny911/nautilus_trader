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

import numpy as np

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


class MACDStrategyConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type_1min: BarType
    bar_type_sp500: BarType  # 新增标普500指数配置
    fast_period: int = 12
    slow_period: int = 26
    base_trade_size: int = 10_000
    enter_threshold: float = 0.00010
    follow_step: float = 0.00005
    max_follow_steps: int = 5
    follow_risk_multiplier: float = 0.5
    volatility_window: int = 20
    max_leverage: float = 3.0
    risk_per_trade: float = 0.02


# Create a subclass of Strategy class
class MACDStrategy(Strategy):
    def __init__(self, config: MACDStrategyConfig):
        super().__init__()
        self.bar_type_1min = config.bar_type_1min
        self.bar_type_sp500 = config.bar_type_sp500

        self.macd = MovingAverageConvergenceDivergence(
            fast_period=config.fast_period,
            slow_period=config.slow_period,
            #signal_period=9,  # 添加标准信号线周期
            price_type=PriceType.MID
        )
        self.instrument_id = config.instrument_id
        self.base_trade_size = Quantity.from_int(config.base_trade_size)
        self.volatility_window = config.volatility_window
        self.max_leverage = config.max_leverage
        self.risk_per_trade = config.risk_per_trade
        self.returns = []

        self.position: Position | None = None
        self.enter_threshold = config.enter_threshold

        self.count_processed_bars = 0

        self.start_time = None
        self.end_time = None

    def on_start(self):
        self.start_time = dt.datetime.now()

        # 订阅交易品种和标普500指数数据
        self.subscribe_bars(self.bar_type_1min)
        self.subscribe_bars(self.bar_type_sp500)

        self.log.info(f"My MACD strategy started at {self.start_time}")

    def on_bar(self, bar: Bar):
        # 处理标普500指数数据
        if bar.bar_type == self.bar_type_sp500:
            self.ema50.update(bar.close.as_f64_c())
            self.ema200.update(bar.close.as_f64_c())
            
            # 更新市场趋势判断
            if self.ema50.value > self.ema200.value:
                self.market_trend = "上涨"
            elif self.ema50.value < self.ema200.value:
                self.market_trend = "下跌"
            else:
                self.market_trend = "中性"
            return

        # 原交易品种数据处理
        self.count_processed_bars += 1
        self.macd.handle_bar(bar)
        if not self.macd.initialized:
            return

        # 只在趋势有利时交易
        if (self.market_trend == "上涨" and self.macd.value > 0) or \
           (self.market_trend == "下跌" and self.macd.value < 0):
            self.check_for_entry()
            self.check_for_exit()

    def calculate_volatility(self) -> float:
        if len(self.returns) >= 2:
            return np.std(self.returns[-self.volatility_window :])
        return 0.0

    def calculate_position_size(self) -> Quantity:
        equity = self.cache.account_balance().total.as_f64_c()
        volatility = self.calculate_volatility()
        risk_amount = equity * self.risk_per_trade

        # 计算跟随步数
        current_value = abs(self.macd.value)
        steps = min(int((current_value - self.enter_threshold) / self.config.follow_step), self.config.max_follow_steps)
        steps = max(steps, 0)  # 确保不小于0

        # 动态调整风险系数
        adjusted_risk = 1 + self.config.follow_risk_multiplier * steps
        size = (risk_amount * adjusted_risk) / (volatility + 1e-6)

        # 应用杠杆限制
        max_size = equity * self.max_leverage / self.cache.last_quote().as_f64_c()
        return Quantity.from_f64(min(size, max_size))

    def check_for_entry(self):
        # 根据市场趋势调整入场阈值
        adjusted_threshold = self.enter_threshold
        if self.market_trend == "上涨" and self.macd.value > 0:
            adjusted_threshold *= 0.8  # 牛市降低入场门槛
        elif self.market_trend == "下跌" and self.macd.value < 0:
            adjusted_threshold *= 0.8  # 熊市降低入场门槛
        elif self.market_trend == "中性":
            adjusted_threshold *= 1.2  # 震荡市提高入场门槛

        current_value = self.macd.value
        if abs(current_value) < adjusted_threshold:
            return

        # 计算目标步数（根据市场趋势调整）
        steps = min(int((abs(current_value) - self.enter_threshold) / self.config.follow_step), self.config.max_follow_steps)
        steps = max(steps, 0)

        # 计算基础仓位
        base_size = self.base_trade_size.as_double()
        target_qty = base_size * (1 + self.config.follow_risk_multiplier * steps)

        # 获取当前持仓
        current_qty = 0.0
        if self.position:
            current_qty = abs(self.position.quantity.as_double())

        # 需要调整的仓位量
        delta_qty = target_qty - current_qty
        if delta_qty <= 0:
            return

        position_size = Quantity.from_f64(delta_qty)

        # 根据信号方向下单
        if current_value >= self.enter_threshold:
            if not self.position or self.position.side != PositionSide.LONG:
                order = self.order_factory.market(instrument_id=self.instrument_id, order_side=OrderSide.BUY, quantity=position_size)
                self.submit_order(order)

        elif current_value < -self.enter_threshold:
            if not self.position or self.position.side != PositionSide.SHORT:
                order = self.order_factory.market(instrument_id=self.instrument_id, order_side=OrderSide.SELL, quantity=position_size)
                self.submit_order(order)

    def check_for_exit(self):
        # Exit short positions when MACD crosses above signal line
        if self.macd.value > self.macd.signal:
            if self.position and self.position.side == PositionSide.SHORT:
                self.close_position(self.position)

        # Exit long positions when MACD crosses below signal line
        elif self.macd.value < self.macd.signal:
            if self.position and self.position.side == PositionSide.LONG:
                self.close_position(self.position)

    def on_end(self):
        self.end_time = dt.datetime.now()
        self.close_all_positions(instrument_id=self.config.instrument_id)
        self.unsubscribe_bars()

        self.log.info(f"My MACD strategy finished at {self.end_time}")
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
