from nautilus_trader.core.message import Event
import pandas as pd

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
    def initialized(self):
        return self._initialized
from nautilus_trader.model.data import Bar, BarType, BarSpecification
from nautilus_trader.model.enums import OrderSide, PriceType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from dataclasses import field
from nautilus_trader.trading.strategy import Strategy, StrategyConfig


class MultiTimeframeMACDConfig(StrategyConfig):
    instrument_id: str
    timeframes: list[str] = field(default_factory=lambda: ["1m", "5m", "15m", "30m", "60m"])
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    timeframe_weights: dict[str, float] = field(default_factory=lambda: {
        "1m": 0.05,
        "5m": 0.15,
        "15m": 0.20,
        "30m": 0.25,
        "60m": 0.35
    })
    threshold_long: float = 0.7
    threshold_short: float = -0.7


class MultiTimeframeMACDStrategy(Strategy):
    def __init__(self, config: MultiTimeframeMACDConfig) -> None:
        super().__init__(config)
        
        self.instrument_id = config.instrument_id
        self.macd_indicators = {}
        self.current_signals = {}
        
        # Initialize MACD indicators for each timeframe
        for timeframe in config.timeframes:
            self.macd_indicators[timeframe] = MACD(
                fast=config.fast_period,
                slow=config.slow_period,
                signal=config.signal_period
            )
            self.current_signals[timeframe] = 0.0

    def on_start(self) -> None:
        # Subscribe to bars for all timeframes
        timeframe_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "60m": 60
        }
        for timeframe_str in self.config.timeframes:
            minutes = timeframe_map[timeframe_str]
            bar_type = BarType(
                instrument_id=self.instrument_id,
                spec=BarSpecification(minutes, PriceType.LAST, 0)
            )
            self.subscribe_bars(bar_type)

    def on_bar(self, bar: Bar) -> None:
        timeframe = bar.bar_type.spec.timeframe
        macd = self.macd_indicators[timeframe]
        
        # Update MACD with new bar data
        macd.update(bar.close.as_double())
        
        if macd.initialized:
            # Calculate normalized signal strength [-1, 1]
            signal_strength = macd.hist / (macd.signal * 2) if macd.signal != 0 else 0
            self.current_signals[timeframe] = signal_strength
            
            # Calculate weighted composite signal
            composite_signal = sum(
                self.current_signals[tf] * self.config.timeframe_weights[tf]
                for tf in self.config.timeframes
            )
            
            # Execute trades based on composite signal
            if composite_signal > self.config.threshold_long:
                self.buy_signal(composite_signal)
            elif composite_signal < self.config.threshold_short:
                self.sell_signal(composite_signal)

    def buy_signal(self, signal_strength: float) -> None:
        if not self.portfolio.is_flat(self.instrument_id):
            return
            
        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=OrderSide.BUY,
            quantity=Quantity.from_int(100),  # Adjust quantity as needed
        )
        self.submit_order(order)

    def sell_signal(self, signal_strength: float) -> None:
        if self.portfolio.is_flat(self.instrument_id):
            return
            
        order = self.order_factory.market(
            instrument_id=self.instrument_id,
            order_side=OrderSide.SELL,
            quantity=Quantity.from_int(100),  # Adjust quantity as needed
        )
        self.submit_order(order)
