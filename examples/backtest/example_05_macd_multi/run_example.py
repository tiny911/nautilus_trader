"""
run_example.py
多标的多周期MACD回测主脚本
"""
import mysql.connector
from data_prepare import prepare_hs300_multi_period_data, prepare_hs300_index_multi_period_data
from macd_multi_strategy import MACDMultiStrategy, MACDMultiStrategyConfig
from datetime import datetime
# from nautilus_trader.backtest.engine import BacktestEngine
# from nautilus_trader.model.instruments.base import Instrument
# ... 其他必要import

def init_mysql_conn(
    host="localhost", user="your_user", password="your_password", database="quant_backtest", port=3306
):
    conn = mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database,
        autocommit=True
    )
    return conn

def main():
    frequencies = ["1min", "5min"]
    # 沪深300多周期Bar数据通过1min聚合
    hs300_bars_dict = prepare_hs300_index_multi_period_data(frequencies)
    instruments, bars_dict = prepare_hs300_multi_period_data(frequencies)
    config = MACDMultiStrategyConfig(instruments, frequencies, top_n=10, hs300_symbol="HS300", hs300_bars_dict=hs300_bars_dict)
    strategy = MACDMultiStrategy(config)

    MYSQL_HOST = "localhost"  # 不带端口
    MYSQL_USER = "root"
    MYSQL_PASSWORD = "123456"
    MYSQL_DB = "quant_backtest"
    MYSQL_PORT = 3306
    conn = init_mysql_conn(
        host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database=MYSQL_DB, port=MYSQL_PORT
    )
    c = conn.cursor()

    # 假设所有symbol的bar数量一致
    num_bars = min(len(bars_dict[symbol][frequencies[0]]) for symbol in bars_dict)
    for t in range(num_bars):
        for symbol in bars_dict:
            for freq in frequencies:
                bars = bars_dict[symbol][freq]
                if t < len(bars):
                    strategy.update_bar(symbol, freq, bars[t], t)
        top_symbols = strategy.score_and_rank(t)
        for rank, symbol in enumerate(top_symbols, 1):
            score = strategy.scores[symbol]
            bar = bars_dict[symbol][frequencies[0]][t]
            ts = datetime.fromtimestamp(bar.ts_event / 1e9)  # 转为MySQL DATETIME
            position = strategy.positions[symbol]
            trade_signal = strategy.signals[symbol]
            c.execute(
                "INSERT INTO ranking (step, symbol, rank, score, ts, position, trade_signal) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (t, symbol, rank, score, ts, position, trade_signal)
            )
        if t % 100 == 0:
            conn.commit()
    conn.commit()
    c.close()
    conn.close()
    print("Backtest results saved to MySQL database.")

if __name__ == "__main__":
    main() 