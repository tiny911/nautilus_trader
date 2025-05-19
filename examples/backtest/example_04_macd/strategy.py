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
import pandas as pd

from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.nautilus_pyo3 import BarAggregation
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


# 自定义EMA指标实现
class ExponentialMovingAverage:
    def __init__(self, period: int):
        self.period = period
        self.alpha = 2 / (period + 1)
        self.value = 0.0
        self._previous_value = None
        self.initialized = False

    def update(self, price: float):
        if self._previous_value is None:
            self.value = price
            self.initialized = True
        else:
            self.value = self.alpha * price + (1 - self.alpha) * self._previous_value
        self._previous_value = self.value


class MACDStrategyConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type_1min: BarType
    bar_type_hs300: BarType  # 新增沪深300指数配置
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
        self.bar_type_hs300 = config.bar_type_hs300

        self.market_trend = "unknown"
        # 初始化EMA指标
        self.ema50 = ExponentialMovingAverage(50)
        self.ema200 = ExponentialMovingAverage(200)

        self.macd = MovingAverageConvergenceDivergence(
            fast_period=config.fast_period,
            slow_period=config.slow_period,
            #signal_period=9,  # 添加标准信号线周期
            price_type=PriceType.MID
        )

        self.signal = ExponentialMovingAverage(9)
        
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

        # 订阅交易品种和沪深300指数数据
        self.subscribe_bars(self.bar_type_1min)
        self.subscribe_bars(self.bar_type_hs300)

        # 初始化环境分析数据
        # self.env_data = {
        #     'hs300_1m': self.data.catalog.get_series("HS300_1MIN"),
        #     'hs300_1h': self.data.catalog.get_series("HS300_60MIN")
        # }

        self.log.info(f"My MACD strategy started at {self.start_time}")

    def on_bar(self, bar: Bar):
        # 处理沪深300指数数据
        if bar.bar_type == self.bar_type_hs300:
            self.ema50.update(bar.close)
            self.ema200.update(bar.close)
            
            # 更新市场趋势判断
            if self.ema50.initialized and self.ema200.initialized:
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
            return float(np.std(self.returns[-self.volatility_window :]))
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

        # # 计算目标步数（根据市场趋势调整）
        # steps = min(int((abs(current_value) - self.enter_threshold) / self.config.follow_step), self.config.max_follow_steps)
        # steps = max(steps, 0)

        # # 计算基础仓位
        # base_size = self.base_trade_size.as_double()
        # target_qty = base_size * (1 + self.config.follow_risk_multiplier * steps)

        # # 获取当前持仓
        # current_qty = 0.0
        # if self.position:
        #     current_qty = abs(self.position.quantity.as_double())

        # # 需要调整的仓位量
        # delta_qty = target_qty - current_qty
        # if delta_qty <= 0:
        #     return

        # position_size = Quantity.from_f64(delta_qty)

        # # 根据信号方向下单
        # if current_value >= self.enter_threshold:
        #     if not self.position or self.position.side != PositionSide.LONG:
        #         order = self.order_factory.market(instrument_id=self.instrument_id, order_side=OrderSide.BUY, quantity=position_size)
        #         self.submit_order(order)

        # elif current_value < -self.enter_threshold:
        #     if not self.position or self.position.side != PositionSide.SHORT:
        #         order = self.order_factory.market(instrument_id=self.instrument_id, order_side=OrderSide.SELL, quantity=position_size)
        #         self.submit_order(order)

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
            self.fast_ema = self.fast_ema.append(pd.Series(price)).tail(self._fast_period)
        else:
            ema = price * (2/(self._fast_period+1)) + self.fast_ema.iloc[-1] * (1 - 2/(self._fast_period+1))
            self.fast_ema = self.fast_ema.append(pd.Series(ema)).iloc[1:]

        if len(self.slow_ema) < self._slow_period:
            self.slow_ema = self.slow_ema.append(pd.Series(price)).tail(self._slow_period)
        else:
            ema = price * (2/(self._slow_period+1)) + self.slow_ema.iloc[-1] * (1 - 2/(self._slow_period+1))
            self.slow_ema = self.slow_ema.append(pd.Series(ema)).iloc[1:]

        # 计算MACD线
        if len(self.fast_ema) == self._fast_period and len(self.slow_ema) == self._slow_period:
            current_macd = self.fast_ema.iloc[-1] - self.slow_ema.iloc[-1]
            self.macd_line = self.macd_line.append(pd.Series(current_macd))

            # 计算信号线
            if len(self.macd_line) >= self._signal_period:
                signal = self.macd_line.ewm(span=self._signal_period, adjust=False).mean().iloc[-1]
                self.signal_ema = self.signal_ema.append(pd.Series(signal))

                # 计算柱状图
                self.histogram = self.histogram.append(pd.Series(current_macd - signal))

                if not self._initialized and len(self.histogram) > 3:
                    self._initialized = True

    @property
    def is_initialized(self):
        return self._initialized
# endregion

# region 策略配置
class DualMACDConfig(StrategyConfig, frozen=True):
    instrument_aapl: str
    instrument_ndx: str
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    ndx_fast: int = 50
    ndx_slow: int = 200
    ndx_signal: int = 9
    trade_size: int = 100
    enable_short: bool = False

class DualMACDStrategy(Strategy):
    def __init__(self, config: DualMACDConfig):
        super().__init__(config)

        # 苹果股票指标
        self.aapl_macd = MACD(
            fast=config.macd_fast,
            slow=config.macd_slow,
            signal=config.macd_signal
        )

        # 纳斯达克指数指标
        self.ndx_macd = MACD(
            fast=config.ndx_fast,
            slow=config.ndx_slow,
            signal=config.ndx_signal
        )

        self.trade_size = config.trade_size
        self.enable_short = config.enable_short
        self.aapl = config.instrument_aapl
        self.ndx = config.instrument_ndx

    def on_start(self):
        self.subscribe_bars(self.aapl, BarAggregation.HOUR, 1)
        self.subscribe_bars(self.ndx, BarAggregation.DAY, 1)

    def on_bar(self, bar: Bar):
        # 更新对应品种的指标
        if bar.instrument_id == self.aapl:
            self.aapl_macd.update(bar.close.as_double())
        elif bar.instrument_id == self.ndx:
            self.ndx_macd.update(bar.close.as_double())

        # 检查指标初始化状态
        if not (self.aapl_macd.is_initialized and self.ndx_macd.is_initialized):
            return

        # 获取当前持仓
        position = self.cache.position(self.aapl)

        # 市场趋势判断（纳斯达克）
        market_bullish = (
            self.ndx_macd.macd_line.iloc[-1] > self.ndx_macd.signal_ema.iloc[-1] and
            self.ndx_macd.histogram.iloc[-1] > 0
        )

        # 苹果交易信号
        aapl_buy = (
            self.aapl_macd.macd_line.iloc[-1] > self.aapl_macd.signal_ema.iloc[-1] and
            self.aapl_macd.histogram.iloc[-1] > 0
        )
        aapl_sell = (
            self.aapl_macd.macd_line.iloc[-1] < self.aapl_macd.signal_ema.iloc[-1] and
            self.aapl_macd.histogram.iloc[-1] < 0
        )

        # 执行交易逻辑
        if market_bullish:
            if aapl_buy and not position:
                self.submit_order(
                    self.order_factory.market(
                        instrument_id=self.aapl,
                        order_side=OrderSide.BUY,
                        quantity=Quantity.from_int(self.trade_size)
                    )
                )
            elif aapl_sell and position and position.is_long:
                self.close_position(position)
        else:
            if position:
                self.close_position(position)
# endregion