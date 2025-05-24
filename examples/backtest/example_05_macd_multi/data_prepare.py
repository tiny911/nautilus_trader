"""
data_prepare.py
批量准备沪深300成份股多周期Bar数据
"""
from typing import Dict, List
from nautilus_trader.model.instruments.equity import Equity
from nautilus_trader.model.identifiers import InstrumentId, Venue, Symbol
from nautilus_trader.model import Bar
from nautilus_trader.model.objects import Price, Quantity
from nautilus_trader.model.enums import BarAggregation, PriceType, AggregationSource
from nautilus_trader.model.data import BarSpecification, BarType
from nautilus_trader.model.currencies import CNY
from datetime import datetime, timedelta
import random

def get_hs300_components() -> List[str]:
    """返回沪深300成份股代码列表（示例用部分代码）。"""
    return [
        "600000.SH", "600519.SH", "000001.SZ", "000651.SZ", # ... 可补充完整
    ]

def load_instrument(symbol: str) -> Equity:
    if symbol == "HS300":
        venue = Venue("CSI300")
    else:
        venue = Venue("SSE")
    return Equity(
        instrument_id=InstrumentId(Symbol(symbol), venue),
        raw_symbol=Symbol(symbol),
        currency=CNY,
        price_precision=2,
        price_increment=Price(0.01, 2),
        lot_size=Quantity(100, 0),
        ts_event=0,
        ts_init=0,
    )

def get_instrument_id(symbol: str) -> InstrumentId:
    if symbol == "HS300":
        venue = Venue("CSI300")
    else:
        venue = Venue("SSE")
    return InstrumentId(Symbol(symbol), venue)

def load_bars_for_instrument(symbol: str, freq: str) -> List[Bar]:
    # 只生成1min数据，其他周期通过聚合生成
    if freq != "1min":
        raise ValueError("只允许直接加载1min数据，其他周期请用聚合函数生成")
    bars = []
    dt = datetime(2024, 1, 1, 9, 30)
    instrument_id = get_instrument_id(symbol)
    bar_spec = BarSpecification(1, BarAggregation.MINUTE, PriceType.LAST)
    bar_type = BarType(instrument_id, bar_spec, AggregationSource.EXTERNAL)
    price = 100 + random.random() * 10
    for i in range(200):
        open_ = price + random.uniform(-1, 1)
        close = open_ + random.uniform(-1, 1)
        high = max(open_, close) + random.uniform(0, 1)
        low = min(open_, close) - random.uniform(0, 1)
        volume = random.randint(1000, 10000)
        ts = int(dt.timestamp() * 1e9)
        bars.append(Bar(
            bar_type=bar_type,
            open=Price(open_, 2),
            high=Price(high, 2),
            low=Price(low, 2),
            close=Price(close, 2),
            volume=Quantity(volume, 0),
            ts_event=ts,
            ts_init=ts,
        ))
        dt += timedelta(minutes=1)
        price = close
    return bars

def aggregate_bars(bars_1min: List[Bar], target_minutes: int, bar_type_str: str, instrument_id: InstrumentId) -> List[Bar]:
    if not bars_1min:
        return []
    result = []
    group = []
    step = target_minutes
    bar_spec = BarSpecification(step, BarAggregation.MINUTE, PriceType.LAST)
    bar_type = BarType(instrument_id, bar_spec, AggregationSource.EXTERNAL)
    for bar in bars_1min:
        group.append(bar)
        if len(group) == target_minutes:
            open_ = group[0].open
            close = group[-1].close
            high = max(b.high for b in group)
            low = min(b.low for b in group)
            volume = sum(b.volume for b in group)
            timestamp = group[0].ts_event
            result.append(
                Bar(
                    bar_type=bar_type,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=Quantity(volume, 0),
                    ts_event=timestamp,
                    ts_init=timestamp,
                )
            )
            group = []
    return result

def prepare_hs300_multi_period_data(frequencies: List[str]):
    symbols = get_hs300_components()
    instruments = []
    bars_dict = {}
    freq_map = {"1min": 1, "5min": 5, "15min": 15}  # 可扩展
    for symbol in symbols:
        instrument = load_instrument(symbol)
        instruments.append(instrument)
        bars_1min = load_bars_for_instrument(symbol, "1min")
        instrument_id = get_instrument_id(symbol)
        bars_dict[symbol] = {}
        for freq in frequencies:
            if freq == "1min":
                bars_dict[symbol][freq] = bars_1min
            else:
                bars_dict[symbol][freq] = aggregate_bars(bars_1min, freq_map[freq], freq, instrument_id)
    return instruments, bars_dict

def prepare_hs300_index_multi_period_data(frequencies: List[str]):
    bars_1min = load_bars_for_instrument("HS300", "1min")
    instrument_id = get_instrument_id("HS300")
    bars_dict = {}
    freq_map = {"1min": 1, "5min": 5, "15min": 15}
    for freq in frequencies:
        if freq == "1min":
            bars_dict[freq] = bars_1min
        else:
            bars_dict[freq] = aggregate_bars(bars_1min, freq_map[freq], freq, instrument_id)
    return bars_dict 