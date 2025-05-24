"""
macd_multi_strategy.py
多标的多周期MACD策略实现，支持动态打分排名
"""
from typing import Dict, List
from nautilus_trader.model.instruments.base import Instrument
from nautilus_trader.model import Bar
import numpy as np

class MACDMultiStrategyConfig:
    def __init__(self, instruments, frequencies, top_n=10, hs300_symbol="HS300", hs300_bars_dict=None, freq_weights=None, hs300_freq_weights=None):
        self.instruments = instruments
        self.frequencies = frequencies
        self.top_n = top_n
        self.hs300_symbol = hs300_symbol
        self.hs300_bars_dict = hs300_bars_dict or {}
        # 周期权重，默认为等权
        self.freq_weights = freq_weights or {freq: 1.0 for freq in frequencies}
        self.hs300_freq_weights = hs300_freq_weights or {freq: 1.0 for freq in frequencies}

class MACDMultiStrategy:
    def __init__(self, config: MACDMultiStrategyConfig):
        self.config = config
        # 统一所有symbol为str
        symbol_list = [str(ins.symbol) for ins in config.instruments]
        self.bars = {symbol: {freq: [] for freq in config.frequencies} for symbol in symbol_list}
        self.macd_vals = {symbol: {freq: [] for freq in config.frequencies} for symbol in symbol_list}
        self.scores = {}
        self.positions = {symbol: 0 for symbol in symbol_list}
        self.signals = {symbol: 'HOLD' for symbol in symbol_list}
        # 沪深300多周期趋势缓存
        self.hs300_macd_hist = {freq: [] for freq in config.frequencies}
        if config.hs300_bars_dict:
            self._calc_hs300_trend()

    def _to_float(self, v):
        # 支持Price/Quantity/Decimal/float
        try:
            return float(v.value)
        except AttributeError:
            return float(v)

    def _calc_hs300_trend(self):
        # 计算沪深300指数的多周期MACD柱状值序列
        for freq in self.config.frequencies:
            bars = self.config.hs300_bars_dict.get(freq, [])
            close_prices = [self._to_float(b.close) for b in bars]
            if len(close_prices) >= 26:
                for i in range(26, len(close_prices)):
                    macd, signal, hist = self.calc_macd(close_prices[:i+1])
                    self.hs300_macd_hist[freq].append(hist)
            else:
                self.hs300_macd_hist[freq] = [0] * len(close_prices)

    def update_bar(self, symbol, freq, bar, t=None):
        symbol = str(symbol)
        self.bars[symbol][freq].append(bar)
        close_prices = [self._to_float(b.close) for b in self.bars[symbol][freq]]
        if len(close_prices) >= 26:
            macd, signal, hist = self.calc_macd(close_prices)
            self.macd_vals[symbol][freq].append((macd, signal, hist))
        else:
            self.macd_vals[symbol][freq].append((0, 0, 0))
        # 只在主周期最后一次调用时生成信号
        if freq == self.config.frequencies[-1]:
            self.generate_signal(symbol, t)

    def calc_macd(self, prices, fast=12, slow=26, signal=9):
        ema_fast = self.ema(prices, fast)
        ema_slow = self.ema(prices, slow)
        macd = np.array(ema_fast) - np.array(ema_slow)
        signal_line = self.ema(macd.tolist(), signal)
        hist = macd[-len(signal_line):] - np.array(signal_line)
        return macd[-1], signal_line[-1], hist[-1]

    def ema(self, prices, period):
        ema = []
        k = 2 / (period + 1)
        for i, price in enumerate(prices):
            price = float(price)
            if i == 0:
                ema.append(price)
            else:
                ema.append(price * k + ema[-1] * (1 - k))
        return ema

    def score_and_rank(self, t=None):
        # 结合多周期MACD和沪深300多周期趋势打分
        for symbol in self.bars:
            score = 0
            for freq in self.config.frequencies:
                weight = self.config.freq_weights.get(freq, 1.0)
                if self.macd_vals[symbol][freq]:
                    _, _, hist = self.macd_vals[symbol][freq][-1]
                    prev_hist = self.macd_vals[symbol][freq][-2][2] if len(self.macd_vals[symbol][freq]) > 1 else 0
                    score += weight * (hist + 0.5 * prev_hist)
            # 融合沪深300多周期趋势（加权）
            hs300_trend = 0
            if self.config.hs300_bars_dict and t is not None:
                for freq in self.config.frequencies:
                    trend_hist = self.hs300_macd_hist.get(freq, [])
                    hs300_weight = self.config.hs300_freq_weights.get(freq, 1.0)
                    if t < len(trend_hist):
                        hs300_trend += hs300_weight * trend_hist[t]
                score += 0.5 * hs300_trend
            self.scores[symbol] = score
        ranked = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        return [s for s, _ in ranked[:self.config.top_n]]

    def generate_signal(self, symbol, t=None):
        symbol = str(symbol)
        ranked = self.score_and_rank(t)
        score = self.scores[symbol]
        if symbol in ranked and score > 60:
            self.signals[symbol] = 'BUY'
            self.positions[symbol] = 1
        else:
            self.signals[symbol] = 'HOLD'
            self.positions[symbol] = 0 