# -----------------------------------------------------------------------------
#  Copyright (C) 2025 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -----------------------------------------------------------------------------


import numpy as np
import pandas as pd
from sqlalchemy import create_engine  # type: ignore

from nautilus_trader.config import StrategyConfig
from nautilus_trader.indicators.macd import MovingAverageConvergenceDivergence
from nautilus_trader.indicators.rsi import RelativeStrengthIndex
from nautilus_trader.model import Bar
from nautilus_trader.model import BarType
from nautilus_trader.model import InstrumentId
from nautilus_trader.model import PriceType
from nautilus_trader.model import Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.trading.strategy import Strategy


class ScoreStrategyConfig(StrategyConfig, frozen=True):
    instrument_universe: list[InstrumentId]
    score_weights: dict[str, float] = {"technical": 0.4, "fundamental": 0.3, "liquidity": 0.3}
    # MACD多周期配置
    macd_params: tuple[tuple[int, int, int], ...] = (
        (8, 17, 9),  # 短期-捕捉日内趋势
        (12, 26, 9),  # 中期-基准趋势
        (24, 52, 18),  # 长期-主趋势
    )
    macd_base_weights: tuple[float, ...] = (0.5, 0.3, 0.2)
    volatility_window: int = 30  # 波动率计算周期
    rebalance_interval: str = "5m"
    max_positions: int = 20
    max_leverage: float = 3.0
    risk_per_trade: float = 0.02


class ScoreBoard:
    def __init__(self, weights: dict[str, float]):
        self.weights = weights
        self.scores = {}

    def update_score(self, instrument_id: InstrumentId, technical: float, fundamental: float, liquidity: float) -> None:
        composite = technical * self.weights["technical"] + fundamental * self.weights["fundamental"] + liquidity * self.weights["liquidity"]
        self.scores[instrument_id] = {
            "technical": technical,
            "fundamental": fundamental,
            "liquidity": liquidity,
            "composite": composite,
            "timestamp": self.clock.timestamp_ns(),
        }


class FundamentalDataLoader:
    def __init__(self, db_url: str = "postgresql://user:pass@localhost:5432/finance"):
        self.engine = create_engine(db_url)

    def get_fundamentals(self, instrument_id: InstrumentId) -> dict:
        # 获取个股基本面数据
        stock_query = f"""
        SELECT
            f.pe_ratio, 
            f.pb_ratio, 
            f.roe, 
            f.market_cap,
            f.dividend_yield,
            f.revenue_growth,
            f.profit_margin,
            f.debt_to_equity,
            i.industry
        FROM fundamentals f
        JOIN instruments i ON f.symbol = i.symbol
        WHERE f.symbol = '{instrument_id.symbol}'
        """

        # 获取行业数据
        industry_query = """
        SELECT 
            industry,
            AVG(pe_ratio) as ind_pe,
            AVG(pb_ratio) as ind_pb,
            AVG(roe) as ind_roe,
            AVG(debt_to_equity) as ind_debt
        FROM fundamentals f
        JOIN instruments i ON f.symbol = i.symbol
        GROUP BY industry
        """
        try:
            # 获取个股和行业数据
            stock_df = pd.read_sql(stock_query, self.engine)
            industry_df = pd.read_sql(industry_query, self.engine)

            if not stock_df.empty and not industry_df.empty:
                industry = stock_df.industry[0]
                ind_data = industry_df[industry_df.industry == industry].iloc[0]
                return {
                    "pe_ratio": float(stock_df.pe_ratio[0]),
                    "pb_ratio": float(stock_df.pb_ratio[0]),
                    "roe": float(stock_df.roe[0]),
                    "market_cap": float(stock_df.market_cap[0]),
                    "dividend_yield": float(stock_df.dividend_yield[0]),
                    "revenue_growth": float(stock_df.revenue_growth[0]),
                    "profit_margin": float(stock_df.profit_margin[0]),
                    "debt_to_equity": float(stock_df.debt_to_equity[0]),
                    "industry": industry,
                    "ind_pe": float(ind_data.ind_pe),
                    "ind_pb": float(ind_data.ind_pb),
                    "ind_roe": float(ind_data.ind_roe),
                    "ind_debt": float(ind_data.ind_debt),
                }
            return {}
        except Exception as e:
            self.log.error(f"Failed to load fundamentals: {e}")
            return {}


class ScoreStrategy(Strategy):
    def __init__(self, config: ScoreStrategyConfig):
        super().__init__(config)

        # 初始化组件
        self.score_board = ScoreBoard(config.score_weights)
        self.data_loader = FundamentalDataLoader()
        self.current_positions = {}

        # 配置参数
        self.instrument_universe = config.instrument_universe
        self.max_positions = config.max_positions
        self.rebalance_interval_ns = pd.Timedelta(config.rebalance_interval).value
        self.last_rebalance_time = 0

    def on_start(self):
        # 订阅全市场行情
        for instrument_id in self.instrument_universe:
            bar_type = BarType(f"{instrument_id}-1MIN-LAST-EXTERNAL")
            self.subscribe_bars(bar_type)

    def on_bar(self, bar: Bar):
        # 更新技术指标
        technical_score = self.calc_technical_score(bar)

        # 获取基本面数据
        fundamental_score = self.calc_fundamental_score(bar.instrument_id)

        # 计算流动性指标
        liquidity_score = self.calc_liquidity_score(bar)

        # 更新评分板
        self.score_board.update_score(bar.instrument_id, technical_score, fundamental_score, liquidity_score)

        # 执行再平衡
        if self._should_rebalance(bar.ts_event):
            self._rebalance_portfolio()

    def _should_rebalance(self, timestamp: int) -> bool:
        elapsed = timestamp - self.last_rebalance_time
        return elapsed >= self.rebalance_interval_ns

    def _rebalance_portfolio(self):
        # 获取当前排名
        ranked = sorted(self.score_board.scores.items(), key=lambda x: x[1]["composite"], reverse=True)[: self.max_positions]

        # 计算目标仓位
        target_positions = {item[0]: self._calc_position_size(item[1]) for item in ranked}

        # 调整持仓
        self._adjust_positions(target_positions)

        self.last_rebalance_time = self.clock.timestamp_ns()

    def _calc_position_size(self, score: dict) -> Quantity:
        equity = self.cache.account_balance().total.as_f64_c()
        risk_amount = equity * self.config.risk_per_trade
        return Quantity.from_f64(risk_amount / score["composite"])

    def _adjust_positions(self, target_positions: dict[InstrumentId, Quantity]):
        current_positions = self.cache.positions_open()

        # 平仓不在目标列表中的持仓
        for position in current_positions:
            if position.instrument_id not in target_positions:
                self.close_position(position)

        # 调整现有持仓
        for instrument_id, target_qty in target_positions.items():
            current_qty = self._get_current_position_qty(instrument_id)
            delta = target_qty - current_qty

            if delta > 0:
                self._enter_position(instrument_id, delta)
            elif delta < 0:
                self._reduce_position(instrument_id, abs(delta))

    def _get_current_position_qty(self, instrument_id: InstrumentId) -> Quantity:
        position = self.cache.position(instrument_id)
        return position.quantity if position else Quantity.zero()

    def _enter_position(self, instrument_id: InstrumentId, quantity: Quantity):
        order = self.order_factory.market(instrument_id=instrument_id, order_side=OrderSide.BUY, quantity=quantity)
        self.submit_order(order)

    def _reduce_position(self, instrument_id: InstrumentId, quantity: Quantity):
        order = self.order_factory.market(instrument_id=instrument_id, order_side=OrderSide.SELL, quantity=quantity)
        self.submit_order(order)

    def calc_fundamental_score(self, instrument_id: InstrumentId) -> float:
        """基于多维度基本面指标计算评分，包含行业相对估值和分位数标准化"""
        fundamentals = self.data_loader.get_fundamentals(instrument_id)
        if not fundamentals:
            return 0.0

        # 行业相对估值得分
        pe_rel = fundamentals["pe_ratio"] / fundamentals["ind_pe"] if fundamentals["ind_pe"] > 0 else 1
        pb_rel = fundamentals["pb_ratio"] / fundamentals["ind_pb"] if fundamentals["ind_pb"] > 0 else 1
        valuation_score = 1 / (0.5 * pe_rel + 0.5 * pb_rel)

        # 盈利能力得分 (行业分位数)
        roe_score = min(1, fundamentals["roe"] / fundamentals["ind_roe"]) if fundamentals["ind_roe"] > 0 else 0.5

        # 成长性得分
        growth_score = np.tanh(fundamentals["revenue_growth"] / 10)  # 标准化到0-1

        # 财务健康得分
        debt_score = 1 - np.tanh(fundamentals["debt_to_equity"] / fundamentals["ind_debt"]) if fundamentals["ind_debt"] > 0 else 0.5

        # 分红得分
        dividend_score = np.tanh(fundamentals["dividend_yield"] * 2)  # 标准化到0-1

        # 综合评分 (可调整权重)
        return valuation_score * 0.4 + roe_score * 0.3 + growth_score * 0.15 + debt_score * 0.1 + dividend_score * 0.05

    def calc_technical_score(self, bar: Bar) -> float:
        """基于多周期MACD、RSI和波动率计算技术评分"""
        # 获取历史数据计算指标
        hist_data = self.cache.bars(bar.bar_type)[-self.config.volatility_window :]

        # 计算多周期MACD趋势
        macd_indicators = [self._create_multi_macd(hist_data, *params) for params in self.config.macd_params]
        trend_states = [macd.macd[-1] > macd.signal[-1] for macd in macd_indicators]

        # 计算波动率调整因子
        returns = np.diff([b.close.as_f64_c() for b in hist_data])
        volatility = np.std(returns) * 100
        volatility_adj = 1 - np.tanh(volatility / 8)  # 波动率>8%时显著衰减

        # 动态调整权重
        adjusted_weights = list(self.config.macd_base_weights)
        adjusted_weights[2] *= volatility_adj  # 调整长期趋势权重
        total_weight = sum(adjusted_weights)
        normalized_weights = [w / total_weight for w in adjusted_weights]

        # 计算趋势得分
        trend_score = sum(state * weight for state, weight in zip(trend_states, normalized_weights))

        # 计算RSI动量得分
        rsi = self._create_rsi(hist_data)
        momentum_score = (rsi[-1] - 50) / 50  # 标准化到-1到1

        # 计算波动率得分
        volatility_score = 1 - np.tanh(volatility / 5)  # 波动率越低得分越高

        # 综合技术评分
        return (
            trend_score * 0.6  # 提升趋势评分权重
            + momentum_score * 0.25
            + volatility_score * 0.15
        )

    def _create_multi_macd(self, bars: list[Bar], fast: int, slow: int, signal: int):
        macd = MovingAverageConvergenceDivergence(fast_period=fast, slow_period=slow, signal_period=signal, price_type=PriceType.MID)
        for bar in bars:
            macd.update_raw(bar)
        return macd

    def _create_rsi(self, bars: list[Bar]):
        rsi = RelativeStrengthIndex(period=14)
        for bar in bars:
            rsi.update_raw(bar.close.as_f64_c())
        return rsi

    def calc_liquidity_score(self, bar: Bar) -> float:
        """基于成交量和价差计算流动性评分"""
        # 计算平均成交量
        volume_avg = np.mean([b.volume.as_f64_c() for b in self.cache.bars(bar.bar_type)[-5:]])
        volume_score = np.log1p(volume_avg) / 10  # 对数标准化

        # 计算平均价差
        spread_avg = np.mean([(b.high.as_f64_c() - b.low.as_f64_c()) for b in self.cache.bars(bar.bar_type)[-5:]])
        spread_score = 1 - np.tanh(spread_avg / bar.close.as_f64_c())  # 价差越小得分越高

        # 波动率调整
        returns = np.diff([b.close.as_f64_c() for b in self.cache.bars(bar.bar_type)[-5:]])
        volatility = np.std(returns) * 100
        volatility_adj = 1 - np.tanh(volatility / 10)

        return (volume_score * 0.6 + spread_score * 0.4) * volatility_adj
