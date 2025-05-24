# example_06_macd_multi_engine

本示例演示如何将多标的多周期MACD+动态打分排名策略迁移到nautilus-trader的BacktestEngine回测框架下。

## 目录结构
- run_example.py：回测主脚本，集成引擎、数据、策略
- multi_macd_strategy.py：多标的多周期MACD策略（继承Strategy）
- data_prepare.py：数据准备与多周期聚合
- README.md：说明文档

## 主要迁移要点
- 策略类继承自nautilus_trader.strategy.Strategy，实现on_bar等接口
- 多标的多周期Bar缓存与MACD信号在策略内部维护
- 用engine.add_instrument/add_data/add_strategy注册所有数据和策略
- 信号、持仓、排名等可在策略内部持久化
