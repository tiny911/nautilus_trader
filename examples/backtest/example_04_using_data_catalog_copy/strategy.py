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


from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.nautilus_pyo3 import Quantity
from nautilus_trader.indicators.macd import MovingAverageConvergenceDivergence
from nautilus_trader.model import Bar
from nautilus_trader.model import BarType
from nautilus_trader.model import InstrumentId
from nautilus_trader.model import Position
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import PriceType
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.trading.strategy import Strategy


# 配置策略参数
# class MACDStrategyConfig(StrategyConfig,frozen=True):
#     """
#     Configuration for the demo strategy.
#     """

#     instrument_id: str
#     bar_type_1min: BarType
#     fast_period: int = 12
#     slow_period: int = 26

class MACDStrategyConfig(StrategyConfig, frozen=True):

    instrument_id: InstrumentId
    bar_type_1min: BarType
    fast_period: int = 4
    slow_period: int = 8
    trading_side = 10_000
    enter_threshold: float = 0.00010


class MACDStrategy(Strategy):
    def __init__(self, config: MACDStrategyConfig):
        super().__init__(config)
        # 初始化参数
        self.bar_type_1min = config.bar_type_1min
        self.instrument_id = config.instrument_id
        self.fast_period = config.fast_period
        self.slow_period = config.slow_period
        
        #self.signal_period = config.signal_period

        # 初始化指标
        self.macd = MovingAverageConvergenceDivergence(
            fast_period=self.fast_period,
            slow_period=self.slow_period,
            price_type=PriceType.MID)
        # self.macd = MovingAverageConvergenceDivergence(12, 26, 9)
        # self.register_indicator_for_bars(bar_type, self.macd)

        # 记录持仓状态
        #self.position = None
        self.trade_size = Quantity.from_int(config.trading_side)
        
        self.position: Position | None = None
        self.enter_threshold = config.enter_threshold
        
        self.count_processed_bars = 0
        
        self.start_time = None
        self.end_time = None

    def on_start(self):
        # 订阅行情数据（例如1分钟K线）
        self.subscribe_bars(self.bar_type_1min)

    def on_bar(self, bar: Bar):
        # 更新MACD指标
        self.macd.update(bar.close.as_double())

        if not self.macd.initialized:
            return  # 等待指标预热

        # 获取当前DIF、DEA、MACD值
        dif = self.macd.dif
        dea = self.macd.dea
        histogram = self.macd.histogram

        # 策略逻辑：金叉/死叉
        if dif > dea and self.macd.dif[-2] <= self.macd.dea[-2]:
            # 金叉信号：买入
            if not self.position or self.position.is_short:
                self.execute_buy(bar)
        elif dif < dea and self.macd.dif[-2] >= self.macd.dea[-2]:
            # 死叉信号：卖出
            if not self.position or self.position.is_long:
                self.execute_sell(bar)

    def execute_buy(self, bar: Bar):
        # 计算订单数量（示例：固定1手）
        quantity = self.instrument.quantity_precision.to_decimal(1.0)
        # 创建市价单
        order = MarketOrder(
            trader_id=self.trader_id,
            strategy_id=self.id,
            instrument_id=self.instrument_id,
            order_side=OrderSide.BUY,
            quantity=quantity,
            ts_event=bar.ts_event,
        )
        # 提交订单
        self.submit_order(order)
        self.position = order  # 更新持仓状态

    def execute_sell(self, bar: Bar):
        quantity = self.instrument.quantity_precision.to_decimal(1.0)
        order = MarketOrder(
            trader_id=self.trader_id,
            strategy_id=self.id,
            instrument_id=self.instrument_id,
            order_side=OrderSide.SELL,
            quantity=quantity,
            ts_event=bar.ts_event,
        )
        self.submit_order(order)
        self.position = order
