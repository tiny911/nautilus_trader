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
from nautilus_trader.model import Position
from nautilus_trader.model import PriceType
from nautilus_trader.model import Quantity
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import PositionSide
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
    position_sizing_method: str = "equal"  # "equal", "score_weighted", "volatility_adjusted"
    use_stop_loss: bool = True
    stop_loss_atr_multiple: float = 2.0
    use_trailing_stop: bool = False
    trailing_stop_activation: float = 0.02  # 2% 盈利激活追踪止损
    trailing_stop_distance: float = 0.01  # 1% 追踪距离
    db_url: str = "postgresql://user:pass@localhost:5432/finance"


class ScoreBoard:
    def __init__(self, weights: dict[str, float]):
        self.weights = weights
        self.scores = {}
        self.history = {}  # 存储历史评分
        self.max_history = 20  # 保留最近20个评分

    def update_score(self, instrument_id: InstrumentId, technical: float, fundamental: float, liquidity: float, timestamp: int) -> None:
        composite = (
            technical * self.weights["technical"]
            + fundamental * self.weights["fundamental"]
            + liquidity * self.weights["liquidity"]
        )

        # 更新当前评分
        self.scores[instrument_id] = {
            "technical": technical,
            "fundamental": fundamental,
            "liquidity": liquidity,
            "composite": composite,
            "timestamp": timestamp,
        }

        # 更新历史评分
        if instrument_id not in self.history:
            self.history[instrument_id] = []

        self.history[instrument_id].append({
            "composite": composite,
            "timestamp": timestamp,
        })

        # 保持历史记录在限定范围内
        if len(self.history[instrument_id]) > self.max_history:
            self.history[instrument_id].pop(0)

    def get_score_momentum(self, instrument_id: InstrumentId) -> float:
        """计算评分动量 - 评分变化趋势"""
        if instrument_id not in self.history or len(self.history[instrument_id]) < 2:
            return 0.0

        history = self.history[instrument_id]
        recent_scores = [item["composite"] for item in history]

        # 计算评分变化率
        changes = np.diff(recent_scores)

        # 使用指数加权平均,更重视最近变化
        weights = np.exp(np.linspace(0, 1, len(changes)))
        weights = weights / np.sum(weights)

        return np.sum(changes * weights)


class FundamentalDataLoader:
    def __init__(self, db_url: str = "postgresql://user:pass@localhost:5432/finance", logger=None):
        self.engine = create_engine(db_url)
        self._log = logger
        self._cache = {}  # 缓存基本面数据
        self._cache_expiry = {}  # 缓存过期时间 (一天更新一次)
        self._cache_duration = 24 * 60 * 60 * 1e9  # 24小时,纳秒

    def get_fundamentals(self, instrument_id: InstrumentId, timestamp: int) -> dict:
        # 检查缓存是否有效
        if (
            instrument_id in self._cache
            and instrument_id in self._cache_expiry
            and timestamp < self._cache_expiry[instrument_id]
        ):
            return self._cache[instrument_id]

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

                result = {
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

                # 更新缓存
                self._cache[instrument_id] = result
                self._cache_expiry[instrument_id] = timestamp + self._cache_duration

                return result
            return {}
        except Exception as e:
            if self._log:
                self._log.error(f"Failed to load fundamentals: {e}")
            return {}


class ScoreStrategy(Strategy):
    def __init__(self, config: ScoreStrategyConfig):
        super().__init__(config)

        # 初始化组件
        self.score_board = ScoreBoard(config.score_weights)
        self.data_loader = FundamentalDataLoader(config.db_url, self.log)
        self.current_positions = {}
        self.stop_levels = {}  # 存储止损水平
        self.trailing_stops = {}  # 存储追踪止损信息

        # 配置参数
        self.instrument_universe = config.instrument_universe
        self.max_positions = config.max_positions
        self.rebalance_interval_ns = pd.Timedelta(config.rebalance_interval).value
        self.last_rebalance_time = 0
        self.position_sizing_method = config.position_sizing_method
        self.use_stop_loss = config.use_stop_loss
        self.stop_loss_atr_multiple = config.stop_loss_atr_multiple
        self.use_trailing_stop = config.use_trailing_stop
        self.trailing_stop_activation = config.trailing_stop_activation
        self.trailing_stop_distance = config.trailing_stop_distance

        # 技术指标缓存
        self._indicators = {}

        # 性能统计
        self.stats = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "avg_win_pct": 0.0,
            "avg_loss_pct": 0.0,
            "max_drawdown": 0.0,
        }

    def on_start(self):
        # 订阅全市场行情
        for instrument_id in self.instrument_universe:
            bar_type = BarType.from_str(f"{instrument_id}-1-MINUTE-LAST-EXTERNAL")
            self.subscribe_bars(bar_type)

            # 初始化技术指标
            self._init_indicators(instrument_id)

        self.log.info(f"ScoreStrategy started with {len(self.instrument_universe)} instruments")

    def _init_indicators(self, instrument_id: InstrumentId):
        """初始化技术指标"""
        self._indicators[instrument_id] = {
            "macd": [
                MovingAverageConvergenceDivergence(
                    fast_period=fast,
                    slow_period=slow,
                    signal_period=signal,
                    price_type=PriceType.MID
                )
                for fast, slow, signal in self.config.macd_params
            ],
            "rsi": RelativeStrengthIndex(period=14),
            "atr_values": [],  # 存储ATR值
        }

    def on_bar(self, bar: Bar):
        # 更新技术指标
        self._update_indicators(bar)

        # 检查止损
        self._check_stop_loss(bar)

        # 更新技术指标评分
        technical_score = self.calc_technical_score(bar)

        # 获取基本面数据
        fundamental_score = self.calc_fundamental_score(bar.instrument_id, bar.ts_event)

        # 计算流动性指标
        liquidity_score = self.calc_liquidity_score(bar)

        # 更新评分板
        self.score_board.update_score(
            bar.instrument_id,
            technical_score,
            fundamental_score,
            liquidity_score,
            bar.ts_event
        )

        # 执行再平衡
        if self._should_rebalance(bar.ts_event):
            self._rebalance_portfolio()

    def _update_indicators(self, bar: Bar):
        """更新技术指标"""
        if bar.instrument_id not in self._indicators:
            self._init_indicators(bar.instrument_id)

        # 更新MACD
        for macd in self._indicators[bar.instrument_id]["macd"]:
            macd.update_raw(bar)

        # 更新RSI
        self._indicators[bar.instrument_id]["rsi"].update_raw(bar.close.as_f64_c())

        # 更新ATR (简化计算)
        hist_data = self.cache.bars(bar.bar_type)[-20:]
        if len(hist_data) >= 2:
            high_low = bar.high.as_f64_c() - bar.low.as_f64_c()
            high_close = abs(bar.high.as_f64_c() - hist_data[-2].close.as_f64_c())
            low_close = abs(bar.low.as_f64_c() - hist_data[-2].close.as_f64_c())
            tr = max(high_low, high_close, low_close)

            atr_values = self._indicators[bar.instrument_id]["atr_values"]
            atr_values.append(tr)

            # 保持ATR值列表在合理长度
            if len(atr_values) > 14:
                atr_values.pop(0)

    def _check_stop_loss(self, bar: Bar):
        """检查止损条件"""
        if not self.use_stop_loss and not self.use_trailing_stop:
            return

        position = self.cache.position(bar.instrument_id)
        if not position:
            return

        current_price = bar.close.as_f64_c()

        # 处理固定止损
        if self._check_regular_stop_loss(position, current_price):
            return

        # 处理追踪止损
        self._check_trailing_stop(position, current_price)

    def _check_regular_stop_loss(self, position: Position, current_price: float) -> bool:
        """检查并执行常规止损"""
        if not self.use_stop_loss or position.instrument_id not in self.stop_levels:
            return False

        stop_level = self.stop_levels[position.instrument_id]
        should_trigger = (
            position.side == PositionSide.LONG and current_price <= stop_level
        ) or (
            position.side == PositionSide.SHORT and current_price >= stop_level
        )

        if should_trigger:
            self.log.info(f"Stop loss triggered for {position.instrument_id} at {current_price}")
            self.close_position(position)
            return True
        return False

    def _check_trailing_stop_activation(self, position: Position, current_price: float, trailing_data: dict):
        """检查并激活追踪止损"""
        entry_price = position.avg_px.as_f64_c()
        activation_pct = self.trailing_stop_activation

        if position.side == PositionSide.LONG:
            profit_pct = (current_price - entry_price) / entry_price
            if profit_pct >= activation_pct:
                trailing_data.update({
                    "activated": True,
                    "stop_level": current_price * (1 - self.trailing_stop_distance)
                })
                self.log.info(f"Trailing stop activated for {position.instrument_id} at {current_price}")
        else:  # SHORT
            profit_pct = (entry_price - current_price) / entry_price
            if profit_pct >= activation_pct:
                trailing_data.update({
                    "activated": True,
                    "stop_level": current_price * (1 + self.trailing_stop_distance)
                })
                self.log.info(f"Trailing stop activated for {position.instrument_id} at {current_price}")

    def _update_trailing_stop(self, position: Position, current_price: float, trailing_data: dict):
        """更新并检查追踪止损"""
        stop_level = trailing_data["stop_level"]

        if position.side == PositionSide.LONG:
            if current_price <= stop_level:
                self.log.info(f"Trailing stop triggered for {position.instrument_id} at {current_price}")
                self.close_position(position)
            else:
                new_stop = current_price * (1 - self.trailing_stop_distance)
                if new_stop > stop_level:
                    trailing_data["stop_level"] = new_stop
        else:  # SHORT
            if current_price >= stop_level:
                self.log.info(f"Trailing stop triggered for {position.instrument_id} at {current_price}")
                self.close_position(position)
            else:
                new_stop = current_price * (1 + self.trailing_stop_distance)
                if new_stop < stop_level:
                    trailing_data["stop_level"] = new_stop

    def _check_trailing_stop(self, position: Position, current_price: float):
        """处理追踪止损逻辑"""
        if not self.use_trailing_stop or position.instrument_id not in self.trailing_stops:
            return

        trailing_data = self.trailing_stops[position.instrument_id]

        if not trailing_data["activated"]:
            self._check_trailing_stop_activation(position, current_price, trailing_data)
        else:
            self._update_trailing_stop(position, current_price, trailing_data)

    def _should_rebalance(self, timestamp: int) -> bool:
        elapsed = timestamp - self.last_rebalance_time
        return elapsed >= self.rebalance_interval_ns

    def _rebalance_portfolio(self):
        # 获取当前排名
        ranked = sorted(
            self.score_board.scores.items(),
            key=lambda x: x[1]["composite"],
            reverse=True
        )[: self.max_positions]

        # 计算目标仓位
        target_positions = {}

        if self.position_sizing_method == "equal":
            # 等权重分配
            for item in ranked:
                target_positions[item[0]] = self._calc_equal_position_size()
        elif self.position_sizing_method == "score_weighted":
            # 基于评分加权
            total_score = sum(item[1]["composite"] for item in ranked)
            for item in ranked:
                weight = item[1]["composite"] / total_score if total_score > 0 else 0
                target_positions[item[0]] = self._calc_weighted_position_size(weight)
        elif self.position_sizing_method == "volatility_adjusted":
            # 波动率调整
            for item in ranked:
                volatility = self._calc_volatility(item[0])
                target_positions[item[0]] = self._calc_volatility_adjusted_size(item[1]["composite"], volatility)
        else:
            # 默认使用评分计算
            target_positions = {item[0]: self._calc_position_size(item[1]) for item in ranked}

        # 调整持仓
        self._adjust_positions(target_positions)

        self.last_rebalance_time = self.clock.timestamp_ns()
        self.log.info(f"Portfolio rebalanced with {len(target_positions)} positions")

    def _calc_equal_position_size(self) -> Quantity:
        """计算等权重仓位大小"""
        equity = self.cache.account_balance().total.as_f64_c()
        position_value = equity / self.max_positions
        return Quantity.from_f64(position_value)

    def _calc_weighted_position_size(self, weight: float) -> Quantity:
        """计算加权仓位大小"""
        equity = self.cache.account_balance().total.as_f64_c()
        position_value = equity * weight
        return Quantity.from_f64(position_value)

    def _calc_volatility(self, instrument_id: InstrumentId) -> float:
        """计算波动率"""
        if instrument_id not in self._indicators:
            return 0.1  # 默认波动率

        atr_values = self._indicators[instrument_id]["atr_values"]
        if not atr_values:
            return 0.1

        return np.mean(atr_values)

    def _calc_volatility_adjusted_size(self, score: float, volatility: float) -> Quantity:
        """计算波动率调整后的仓位大小"""
        equity = self.cache.account_balance().total.as_f64_c()
        risk_amount = equity * self.config.risk_per_trade

        # 波动率越高,仓位越小
        position_value = risk_amount / (volatility + 1e-6) * score
        return Quantity.from_f64(position_value)

    def _calc_position_size(self, score: dict) -> Quantity:
        """基于评分计算仓位大小"""
        equity = self.cache.account_balance().total.as_f64_c()
        risk_amount = equity * self.config.risk_per_trade

        # 评分越高,仓位越大
        position_value = risk_amount * score["composite"]
        return Quantity.from_f64(position_value)

    def _adjust_positions(self, target_positions: dict[InstrumentId, Quantity]):
        """调整持仓到目标仓位"""
        current_positions = self.cache.positions_open()
        self._close_non_target_positions(current_positions, target_positions)
        self._adjust_existing_positions(target_positions)
        self._enter_new_positions(target_positions)

    def _close_non_target_positions(self, current_positions: list[Position], target_positions: dict[InstrumentId, Quantity]):
        """平仓不在目标列表中的持仓"""
        for position in current_positions:
            if position.instrument_id not in target_positions:
                self.close_position(position)
                # 清除止损设置
                if position.instrument_id in self.stop_levels:
                    del self.stop_levels[position.instrument_id]
                if position.instrument_id in self.trailing_stops:
                    del self.trailing_stops[position.instrument_id]

    def _adjust_existing_positions(self, target_positions: dict[InstrumentId, Quantity]):
        """调整现有持仓到目标数量"""
        for instrument_id, target_qty in target_positions.items():
            current_position = self.cache.position(instrument_id)
            if not current_position:
                continue

            side = OrderSide.BUY
            if self.score_board.scores[instrument_id]["technical"] < 0:
                side = OrderSide.SELL

            current_side = PositionSide.LONG if side == OrderSide.BUY else PositionSide.SHORT
            if current_position.side != current_side:
                self.close_position(current_position)
                self._enter_position(instrument_id, target_qty, side)
            else:
                delta = target_qty - current_position.quantity
                if delta > Quantity.zero():
                    self._increase_position(instrument_id, delta, side)
                elif delta < Quantity.zero():
                    self._reduce_position(instrument_id, abs(delta), side.opposite())

    def _enter_new_positions(self, target_positions: dict[InstrumentId, Quantity]):
        """建立新的目标仓位"""
        for instrument_id, target_qty in target_positions.items():
            if not self.cache.position(instrument_id):
                side = OrderSide.BUY
                if self.score_board.scores[instrument_id]["technical"] < 0:
                    side = OrderSide.SELL
                self._enter_position(instrument_id, target_qty, side)

    def _enter_position(self, instrument_id: InstrumentId, quantity: Quantity, side: OrderSide):
        """建立新仓位"""
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=quantity
        )
        self.submit_order(order)

        # 设置止损
        if self.use_stop_loss:
            self._set_stop_loss(instrument_id, side)

        # 初始化追踪止损
        if self.use_trailing_stop:
            self.trailing_stops[instrument_id] = {
                "activated": False,
                "stop_level": 0.0,
            }

        # 更新统计
        self.stats["total_trades"] += 1

    def _increase_position(self, instrument_id: InstrumentId, quantity: Quantity, side: OrderSide):
        """增加现有仓位"""
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=quantity
        )
        self.submit_order(order)

        # 更新止损
        if self.use_stop_loss:
            self._set_stop_loss(instrument_id, side)

    def _reduce_position(self, instrument_id: InstrumentId, quantity: Quantity, side: OrderSide):
        """减少现有仓位"""
        order = self.order_factory.market(
            instrument_id=instrument_id,
            order_side=side,
            quantity=quantity
        )
        self.submit_order(order)

    def _set_stop_loss(self, instrument_id: InstrumentId, side: OrderSide):
        """设置止损水平"""
        if instrument_id not in self._indicators:
            return

        # 计算ATR
        atr_values = self._indicators[instrument_id]["atr_values"]
        if not atr_values:
            return

        atr = np.mean(atr_values)

        # 获取当前价格
        last_bar = self.cache.bar(BarType.from_str(f"{instrument_id}-1-MINUTE-LAST-EXTERNAL"))
        if not last_bar:
            return

        current_price = last_bar.close.as_f64_c()

        # 设置止损水平
        if side == OrderSide.BUY:
            stop_level = current_price - (atr * self.stop_loss_atr_multiple)
        else:
            stop_level = current_price + (atr * self.stop_loss_atr_multiple)

        self.stop_levels[instrument_id] = stop_level
        self.log.info(f"Stop loss set for {instrument_id} at {stop_level}")

    def on_position_changed(self, position: Position):
        """处理持仓变化事件"""
        super().on_position_changed(position)

        # 如果持仓关闭,更新统计
        if position.is_closed:
            pnl = position.realized_return
            if pnl > 0:
                self.stats["winning_trades"] += 1
                self.stats["avg_win_pct"] = (
                    (self.stats["avg_win_pct"] * (self.stats["winning_trades"] - 1) + pnl)
                    / self.stats["winning_trades"]
                )
            else:
                self.stats["losing_trades"] += 1
                self.stats["avg_loss_pct"] = (
                    (self.stats["avg_loss_pct"] * (self.stats["losing_trades"] - 1) + pnl)
                    / self.stats["losing_trades"]
                )

            # 清除止损设置
            if position.instrument_id in self.stop_levels:
                del self.stop_levels[position.instrument_id]
            if position.instrument_id in self.trailing_stops:
                del self.trailing_stops[position.instrument_id]

    def calc_fundamental_score(self, instrument_id: InstrumentId, timestamp: int) -> float:
        """基于多维度基本面指标计算评分,包含行业相对估值和分位数标准化"""
        fundamentals = self.data_loader.get_fundamentals(instrument_id, timestamp)
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

        # 市值因子 (中小市值溢价)
        size_score = 1 - np.tanh(fundamentals["market_cap"] / 1e10)  # 市值越小得分越高

        # 盈利质量得分
        quality_score = np.tanh(fundamentals["profit_margin"] * 2)  # 标准化到0-1

        # 综合评分 (可调整权重)
        return (
            valuation_score * 0.3
            + roe_score * 0.2
            + growth_score * 0.15
            + debt_score * 0.1
            + dividend_score * 0.05
            + size_score * 0.1
            + quality_score * 0.1
        )

    def calc_technical_score(self, bar: Bar) -> float:
        """基于多周期MACD、RSI和波动率计算技术评分"""
        instrument_id = bar.instrument_id

        if instrument_id not in self._indicators:
            return 0.0

        # 获取MACD指标
        macd_indicators = self._indicators[instrument_id]["macd"]

        # 检查指标是否初始化
        if not all(macd.initialized for macd in macd_indicators):
            return 0.0

        # 计算多周期MACD趋势
        trend_states = []
        trend_strengths = []

        for macd in macd_indicators:
            # 趋势方向
            trend_states.append(1 if macd.macd > macd.signal else -1)

            # 趋势强度 (MACD与信号线差值)
            strength = abs(macd.macd - macd.signal) / (abs(macd.macd) + 1e-6)
            trend_strengths.append(min(1.0, strength))

        # 计算波动率调整因子
        atr_values = self._indicators[instrument_id]["atr_values"]
        if atr_values:
            volatility = np.mean(atr_values) / bar.close.as_f64_c() * 100  # 转为百分比
            volatility_adj = 1 - np.tanh(volatility / 8)  # 波动率>8%时显著衰减
        else:
            volatility_adj = 0.5

        # 动态调整权重
        adjusted_weights = list(self.config.macd_base_weights)
        adjusted_weights[2] *= volatility_adj  # 调整长期趋势权重
        total_weight = sum(adjusted_weights)
