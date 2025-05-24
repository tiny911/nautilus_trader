from nautilus_trader.strategy import Strategy
from nautilus_trader.model.events import BarEvent
import numpy as np

class MultiMACDStrategy(Strategy):
    def __init__(self, config, context):
        super().__init__(config, context)
        self.symbols = config.symbols
        self.frequencies = config.frequencies
        self.bar_cache = {symbol: {freq: [] for freq in self.frequencies} for symbol in self.symbols}
        self.macd_vals = {symbol: {freq: [] for freq in self.frequencies} for symbol in self.symbols}
        self.positions = {symbol: 0 for symbol in self.symbols}
        self.signals = {symbol: 'HOLD' for symbol in self.symbols}
        # 可扩展：持久化、打分、排名等

    def on_start(self, event):
        self.log.info("MultiMACDStrategy started.")

    def on_bar(self, event: BarEvent):
        symbol = str(event.bar.instrument_id.symbol)
        freq = self._get_freq_from_bar_type(event.bar.bar_type)
        self.bar_cache[symbol][freq].append(event.bar)
        # 只在主周期聚合点做信号
        if freq == self.frequencies[-1]:
            self._process_signals(event.bar.ts_event)

    def _process_signals(self, ts):
        # 示例：多周期MACD打分、排名、信号
        for symbol in self.symbols:
            score = 0
            for freq in self.frequencies:
                closes = [float(b.close) for b in self.bar_cache[symbol][freq]]
                if len(closes) >= 26:
                    macd, signal, hist = self._calc_macd(closes)
                    self.macd_vals[symbol][freq].append((macd, signal, hist))
                    score += hist
            # 简单示例：分数大于0买入，否则空仓
            if score > 0:
                self.signals[symbol] = 'BUY'
                if self.positions[symbol] == 0:
                    self.buy(symbol, 1)  # 下单接口
                    self.positions[symbol] = 1
            else:
                self.signals[symbol] = 'HOLD'
                if self.positions[symbol] == 1:
                    self.close(symbol)
                    self.positions[symbol] = 0
        # 可扩展：排名、持久化等

    def _calc_macd(self, prices, fast=12, slow=26, signal=9):
        ema_fast = self._ema(prices, fast)
        ema_slow = self._ema(prices, slow)
        macd = np.array(ema_fast) - np.array(ema_slow)
        signal_line = self._ema(macd.tolist(), signal)
        hist = macd[-len(signal_line):] - np.array(signal_line)
        return macd[-1], signal_line[-1], hist[-1]

    def _ema(self, prices, period):
        ema = []
        k = 2 / (period + 1)
        for i, price in enumerate(prices):
            price = float(price)
            if i == 0:
                ema.append(price)
            else:
                ema.append(price * k + ema[-1] * (1 - k))
        return ema

    def _get_freq_from_bar_type(self, bar_type):
        # 假设step为分钟数
        return f"{bar_type.spec.step}min"
