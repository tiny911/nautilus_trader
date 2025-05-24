# example_05_macd_multi

本示例演示如何基于多时间周期MACD策略，对沪深300成份股进行回测，并实现成份股动态打分排名。

## 目录结构
- data_prepare.py：批量准备沪深300成份股多周期数据
- macd_multi_strategy.py：多标的多周期MACD策略实现
- run_example.py：回测主脚本
- analyze.py（可选）：结果分析与可视化

## 主要功能
- 支持沪深300成份股的多周期（如1min、5min）Bar数据加载
- 多标的多周期MACD信号融合与动态打分排名
- 回测结果输出与分析
