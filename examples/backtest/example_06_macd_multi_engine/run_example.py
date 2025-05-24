from data_prepare import prepare_hs300_multi_period_data, prepare_hs300_index_multi_period_data
from multi_macd_strategy import MultiMACDStrategy
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import BacktestEngineConfig, LoggingConfig
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.strategy.config import StrategyConfig

# 1. 数据准备
frequencies = ["1min", "5min"]
instruments, bars_dict = prepare_hs300_multi_period_data(frequencies)

# 2. 配置回测引擎
engine_config = BacktestEngineConfig(
    trader_id=TraderId("BACKTEST_TRADER-001"),
    logging=LoggingConfig(log_level="INFO"),
)
engine = BacktestEngine(config=engine_config)

# 3. 注册Instrument
for instrument in instruments:
    engine.add_instrument(instrument)

# 4. 注册Bar数据
for symbol in bars_dict:
    for freq in frequencies:
        for bar in bars_dict[symbol][freq]:
            engine.add_data(bar)

# 5. 注册策略
strategy_config = StrategyConfig(
    symbols=[str(ins.symbol) for ins in instruments],
    frequencies=frequencies,
    # 可扩展：其他自定义参数
)
engine.add_strategy(MultiMACDStrategy, config=strategy_config)

# 6. 运行回测
engine.run()
engine.dispose()
