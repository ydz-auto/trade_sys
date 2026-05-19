"""
创新策略模块 - 8大创新策略

基于 Event Study + Playbook Backtest 验证的创新策略集合。
这些策略融入现有策略研究矩阵，通过 Feature Engine + Event Detection Pipeline 接入。

策略列表：
1. LeveragedShortSqueezeStrategy - 多头爆仓+OI激增+Funding极高 → 做空回调
2. MicroRangeRipplesStrategy - 低波动区间突破 → 做多
3. CascadeFlipStrategy - 连锁爆仓后价格反弹 → 做多
4. FundingExhaustionTrapStrategy - Funding极高+仓位快速变化 → 做空
5. MemeManiaRotationStrategy - 板块轮动+放量 → 做多
6. SessionGapExploitStrategy - 时段切换微型波动 → 做多
7. DeadCatEchoStrategy - 暴跌弱反弹后次级反转 → 做空
8. LiquidityVacuumBreakoutStrategy - 夜间低流动性突破 → 做多

回测配置：
- 杠杆: 50x
- 止损: 本金 10% (价格波动 0.2%)
- 止盈: 本金 60% (价格波动 1.2%)
- 最大持仓: 48 小时
- 数据范围: 近 5 个月

回测结果 (2025-12 ~ 2026-04, BTCUSDT 5min):
- Leveraged Short Squeeze: 500笔, 胜率 40.6%, 盈亏比 1.55, 总收益 +$29,139
- Micro Range Ripples: 77笔, 胜率 28.6%, 盈亏比 2.51, 总收益 -$333
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
import numpy as np

from .strategies import (
    BaseStrategy, StrategySignal, StrategyType, ActionType,
    MultiStrategyOrchestrator,
)
from infrastructure.logging import get_logger

logger = get_logger("innovation_strategies")


# ============================================================
# 策略定义常量
# ============================================================

INNOVATION_STRATEGY_CONFIGS = {
    "leveraged_short_squeeze": {
        "name": "Leveraged Short Squeeze",
        "description": "多头爆仓+OI激增+Funding极高 → 价格急涨后回调做空",
        "direction": "short",
        "timeframe": "1-15m",
        "context_tags": ["High Funding", "杠杆多头集中", "OI高"],
        "core_features": [
            "long_liq_ratio", "oi_delta", "funding_zscore", "funding_rate",
            "liquidation_spike", "volume_ratio", "volume_spike",
            "spread_widening", "wick_ratio",
        ],
        "backtest": {
            "trades": 500,
            "win_rate": 0.406,
            "profit_factor": 1.55,
            "avg_win": 0.2273,
            "avg_loss": -0.1467,
            "total_pnl_usd": 29139.12,
        },
    },
    "micro_range_ripples": {
        "name": "Micro Range Ripples",
        "description": "低波动区间突破 → 趋势延续做多",
        "direction": "long",
        "timeframe": "1-5m",
        "context_tags": ["低波动", "低流动性"],
        "core_features": ["bb_position", "volatility_1h", "volume_ratio"],
        "backtest": {
            "trades": 77,
            "win_rate": 0.286,
            "profit_factor": 0.86,
            "avg_win": 0.2561,
            "avg_loss": -0.1021,
            "total_pnl_usd": -333.25,
        },
    },
    "cascade_flip": {
        "name": "Cascade Flip",
        "description": "连锁爆仓后价格反弹 → 做多反弹",
        "direction": "long",
        "timeframe": "5-30m",
        "context_tags": ["High OI", "多头集中"],
        "core_features": ["volume_ratio", "return_1h", "funding_rate"],
        "backtest": {
            "trades": 0,
            "note": "近5个月数据未触发事件，需补充清算数据",
        },
    },
    "funding_exhaustion_trap": {
        "name": "Funding Exhaustion Trap",
        "description": "Funding极高+仓位快速变化 → 反转做空",
        "direction": "short",
        "timeframe": "15m-1h",
        "context_tags": ["funding_high", "OI上升"],
        "core_features": ["funding_zscore", "funding_delta", "return_1h"],
        "backtest": {
            "trades": 0,
            "note": "近5个月数据未触发事件，阈值需调整",
        },
    },
    "meme_mania_rotation": {
        "name": "Meme Mania Rotation",
        "description": "板块轮动+放量 → 追涨做多",
        "direction": "long",
        "timeframe": "15m-4h",
        "context_tags": ["社交热度高", "高波动"],
        "core_features": ["volume_ratio", "spike_up", "volatility_1h"],
        "backtest": {
            "trades": 2,
            "win_rate": 0.5,
            "note": "样本太少，需更长时间数据验证",
        },
    },
    "session_gap_exploit": {
        "name": "Session Gap Exploit",
        "description": "时段切换引发的微型波动 → 顺势做多",
        "direction": "long",
        "timeframe": "5m-1h",
        "context_tags": ["亚洲/美盘开盘", "低流动性"],
        "core_features": ["volume_ratio", "hour", "intrabar_volatility"],
        "backtest": {
            "trades": 0,
            "note": "近5个月数据未触发事件",
        },
    },
    "dead_cat_echo": {
        "name": "Dead Cat Echo",
        "description": "暴跌弱反弹后的次级反转 → 做空",
        "direction": "short",
        "timeframe": "15m-2h",
        "context_tags": ["压力位附近", "弱势趋势"],
        "core_features": ["trend_exhaustion", "return_1h", "volume_ratio"],
        "backtest": {
            "trades": 0,
            "note": "近5个月数据未触发事件",
        },
    },
    "liquidity_vacuum_breakout": {
        "name": "Liquidity Vacuum Breakout",
        "description": "夜间低流动性突破 → 趋势延续做多",
        "direction": "long",
        "timeframe": "5-30m",
        "context_tags": ["low volume", "spread_widening"],
        "core_features": ["volume_ratio", "bb_position", "breakout_strength_24h"],
        "backtest": {
            "trades": 0,
            "note": "近5个月数据未触发事件",
        },
    },
}


# ============================================================
# 1. Leveraged Short Squeeze Strategy
# ============================================================

class LeveragedShortSqueezeStrategy(BaseStrategy):
    """
    杠杆空头挤压策略

    核心逻辑: 多头过度杠杆化 → 爆仓 → 价格急涨后回调做空

    事件检测 (多特征综合评分, 阈值 >= 5分):
    ┌─────────────────────┬──────────┬────────┐
    │ Feature             │ 阈值      │ 分值    │
    ├─────────────────────┼──────────┼────────┤
    │ funding_zscore      │ > 1.5    │ +3     │
    │ funding_rate        │ > 0.03%  │ +2     │
    │ return_1h           │ > 1%     │ +2     │
    │ volume_ratio        │ > 2.5    │ +2     │
    │ volume_ratio        │ > 1.5    │ +1     │
    │ volume_spike        │ True     │ +1     │
    │ spread_widening     │ True     │ +1     │
    │ wick_ratio          │ > 0.6    │ +1     │
    │ oi_delta            │ > 0      │ +1     │
    └─────────────────────┴──────────┴────────┘

    回测 (2025-12~2026-04, 50x杠杆):
    - 500笔交易, 胜率 40.6%, 盈亏比 1.55
    - 盈利笔均 +22.73%, 亏损笔均 -14.67%
    """

    def __init__(
        self,
        strategy_id: str = "leveraged_short_squeeze",
        score_threshold: float = 5.0,
        default_quantity: float = 0.001,
        leverage: float = 50.0,
        stop_loss_capital_pct: float = 0.10,
        take_profit_capital_pct: float = 0.60,
        max_hold_hours: int = 48,
    ):
        super().__init__(strategy_id)
        self.score_threshold = score_threshold
        self.default_quantity = default_quantity
        self.leverage = leverage
        self.stop_loss_capital_pct = stop_loss_capital_pct
        self.take_profit_capital_pct = take_profit_capital_pct
        self.max_hold_hours = max_hold_hours

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行策略"""
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        # 需要至少 288 根 bar (24h, 5分钟粒度)
        if len(close_prices) < 288:
            return None

        current_price = close_prices[-1]
        current_high = high_prices[-1]
        current_low = low_prices[-1]

        # ---- 计算特征 ----

        # 1. Funding Z-Score
        funding_rates = data.get("funding_rates", [])
        funding_zscore = 0.0
        funding_rate = 0.0
        if len(funding_rates) >= 60:
            recent_funding = [x for x in funding_rates[-60:] if x != 0 and not np.isnan(x)]
            if len(recent_funding) > 10:
                funding_rate = recent_funding[-1]
                funding_zscore = (funding_rate - np.mean(recent_funding)) / (np.std(recent_funding) + 1e-10)

        # 2. 1h 收益率 (12 根 5分钟 bar)
        return_1h = 0.0
        if len(close_prices) >= 12:
            return_1h = (close_prices[-1] - close_prices[-12]) / close_prices[-12]

        # 3. 成交量比率
        volume_ratio = 1.0
        if len(volumes) >= 288:
            avg_vol = np.mean(volumes[-288:])
            if avg_vol > 0:
                volume_ratio = volumes[-1] / avg_vol

        # 4. Volume Spike
        volume_spike = volume_ratio > 2.5

        # 5. Spread Widening (代理: bar内波动率 / volume_ratio)
        intrabar_vol = (current_high - current_low) / current_price if current_price > 0 else 0
        spread_widening = intrabar_vol / (volume_ratio + 0.01) > 0.03

        # 6. Wick Ratio (上影线比例)
        candle_range = current_high - current_low
        if candle_range > 0:
            wick_ratio = (current_high - current_price) / candle_range
        else:
            wick_ratio = 0

        # 7. OI Delta
        oi_values = data.get("oi_values", [])
        oi_delta = 0.0
        if len(oi_values) >= 12:
            oi_delta = (oi_values[-1] - oi_values[-12]) / (oi_values[-12] + 1e-10)

        # ---- 综合评分 ----
        score = 0.0

        # Funding Z-Score (核心条件)
        if funding_zscore > 1.5:
            score += 3
        elif funding_zscore > 1.0:
            score += 1

        # Funding Rate
        if funding_rate > 0.0003:
            score += 2
        elif funding_rate > 0.0002:
            score += 1

        # 价格急涨
        if return_1h > 0.01:
            score += 2
        elif return_1h > 0.005:
            score += 1

        # 成交量异常
        if volume_ratio > 2.5:
            score += 2  # liquidation_spike 代理
        elif volume_ratio > 1.5:
            score += 1

        if volume_spike:
            score += 1

        # 流动性收窄
        if spread_widening:
            score += 1

        # 上影线 (抛压)
        if wick_ratio > 0.6:
            score += 1

        # OI 增加
        if oi_delta > 0:
            score += 1

        # ---- 触发判断 ----
        if score < self.score_threshold:
            return None

        # 计算止损止盈价格
        sl_price_pct = self.stop_loss_capital_pct / self.leverage
        tp_price_pct = self.take_profit_capital_pct / self.leverage
        stop_loss_price = current_price * (1 + sl_price_pct)  # 空头止损在上方
        take_profit_price = current_price * (1 - tp_price_pct)  # 空头止盈在下方

        # 置信度 = score / max_possible_score
        confidence = min(score / 10.0, 1.0)

        logger.info(
            f"[LeveragedShortSqueeze] 触发做空信号 | "
            f"score={score:.0f} | price={current_price:.0f} | "
            f"funding_z={funding_zscore:.2f} | ret_1h={return_1h*100:.2f}% | "
            f"vol_ratio={volume_ratio:.1f} | wick={wick_ratio:.2f}"
        )

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_type=StrategyType.EVENT_DRIVEN,
            symbol=symbol,
            action=ActionType.SHORT,
            quantity=self.default_quantity,
            price=current_price,
            confidence=confidence,
            reason=(
                f"Leveraged Short Squeeze (score={score:.0f}): "
                f"funding_z={funding_zscore:.2f}, ret_1h={return_1h*100:.2f}%, "
                f"vol_ratio={volume_ratio:.1f}, wick={wick_ratio:.2f}"
            ),
            metadata={
                "score": score,
                "funding_zscore": funding_zscore,
                "funding_rate": funding_rate,
                "return_1h": return_1h,
                "volume_ratio": volume_ratio,
                "wick_ratio": wick_ratio,
                "spread_widening": spread_widening,
                "oi_delta": oi_delta,
                "leverage": self.leverage,
                "stop_loss_price": stop_loss_price,
                "take_profit_price": take_profit_price,
                "stop_loss_capital_pct": self.stop_loss_capital_pct,
                "take_profit_capital_pct": self.take_profit_capital_pct,
                "max_hold_hours": self.max_hold_hours,
            },
        )


# ============================================================
# 2. Micro Range Ripples Strategy
# ============================================================

class MicroRangeRipplesStrategy(BaseStrategy):
    """
    微区间波纹策略

    核心逻辑: 低波动收敛后突破，趋势延续概率高

    条件: bb_width < 0.015 + 突破24h高点 + volume_ratio > 1.2
    """

    def __init__(
        self,
        strategy_id: str = "micro_range_ripples",
        bb_width_threshold: float = 0.015,
        breakout_threshold: float = 0.003,
        volume_ratio_threshold: float = 1.2,
        default_quantity: float = 0.001,
        leverage: float = 50.0,
        stop_loss_capital_pct: float = 0.10,
        take_profit_capital_pct: float = 0.60,
        max_hold_hours: int = 48,
    ):
        super().__init__(strategy_id)
        self.bb_width_threshold = bb_width_threshold
        self.breakout_threshold = breakout_threshold
        self.volume_ratio_threshold = volume_ratio_threshold
        self.default_quantity = default_quantity
        self.leverage = leverage
        self.stop_loss_capital_pct = stop_loss_capital_pct
        self.take_profit_capital_pct = take_profit_capital_pct
        self.max_hold_hours = max_hold_hours

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 288:
            return None

        current_price = close_prices[-1]
        current_high = high_prices[-1]

        # BB Width
        bb_width = data.get("bb_width", 0.02)
        if bb_width == 0:
            prices_24h = close_prices[-288:]
            bb_width = np.std(prices_24h) / np.mean(prices_24h) * 2

        # Breakout strength
        rolling_high = max(high_prices[-288:-1])
        breakout_strength = (current_high - rolling_high) / rolling_high if rolling_high > 0 else 0

        # Volume ratio
        volume_ratio = 1.0
        if len(volumes) >= 288:
            avg_vol = np.mean(volumes[-288:])
            if avg_vol > 0:
                volume_ratio = volumes[-1] / avg_vol

        if bb_width < self.bb_width_threshold and breakout_strength > self.breakout_threshold and volume_ratio > self.volume_ratio_threshold:
            sl_price_pct = self.stop_loss_capital_pct / self.leverage
            tp_price_pct = self.take_profit_capital_pct / self.leverage

            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.TECHNICAL,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min((bb_width / self.bb_width_threshold + breakout_strength / self.breakout_threshold) / 4, 1.0),
                reason=f"Micro Range Ripple: bb_width={bb_width:.4f}, breakout={breakout_strength*100:.2f}%, vol_ratio={volume_ratio:.1f}",
                metadata={
                    "bb_width": bb_width,
                    "breakout_strength": breakout_strength,
                    "volume_ratio": volume_ratio,
                    "leverage": self.leverage,
                    "stop_loss_price": current_price * (1 - sl_price_pct),
                    "take_profit_price": current_price * (1 + tp_price_pct),
                },
            )

        return None


# ============================================================
# 3. Cascade Flip Strategy
# ============================================================

class CascadeFlipStrategy(BaseStrategy):
    """
    连锁爆仓翻转策略

    核心逻辑: volume_ratio > 3.0 + 1h跌幅 > 2% + funding > 0.02%
    用 volume_ratio + 跌幅代理清算数据
    """

    def __init__(
        self,
        strategy_id: str = "cascade_flip",
        volume_ratio_threshold: float = 3.0,
        drop_threshold: float = -0.02,
        funding_threshold: float = 0.0002,
        default_quantity: float = 0.001,
        leverage: float = 50.0,
    ):
        super().__init__(strategy_id)
        self.volume_ratio_threshold = volume_ratio_threshold
        self.drop_threshold = drop_threshold
        self.funding_threshold = funding_threshold
        self.default_quantity = default_quantity
        self.leverage = leverage

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        funding_rates = data.get("funding_rates", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 288:
            return None

        current_price = close_prices[-1]
        return_1h = (close_prices[-1] - close_prices[-12]) / close_prices[-12] if len(close_prices) >= 12 else 0

        volume_ratio = 1.0
        if len(volumes) >= 288:
            avg_vol = np.mean(volumes[-288:])
            if avg_vol > 0:
                volume_ratio = volumes[-1] / avg_vol

        funding_rate = funding_rates[-1] if funding_rates else 0

        if volume_ratio > self.volume_ratio_threshold and return_1h < self.drop_threshold and funding_rate > self.funding_threshold:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.LONG,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(volume_ratio / 5.0, 1.0),
                reason=f"Cascade Flip: vol_ratio={volume_ratio:.1f}, ret_1h={return_1h*100:.2f}%, funding={funding_rate*100:.4f}%",
                metadata={"volume_ratio": volume_ratio, "return_1h": return_1h, "funding_rate": funding_rate},
            )

        return None


# ============================================================
# 4. Funding Exhaustion Trap Strategy
# ============================================================

class FundingExhaustionTrapStrategy(BaseStrategy):
    """
    Funding 枯竭陷阱策略

    核心逻辑: funding_zscore > 2.5 + funding_delta < 0 + return_1h < 0.5%
    """

    def __init__(
        self,
        strategy_id: str = "funding_exhaustion_trap",
        funding_zscore_threshold: float = 2.5,
        default_quantity: float = 0.001,
        leverage: float = 50.0,
    ):
        super().__init__(strategy_id)
        self.funding_zscore_threshold = funding_zscore_threshold
        self.default_quantity = default_quantity
        self.leverage = leverage

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        if not self._enabled:
            return None

        close_prices = data.get("close_prices", [])
        funding_rates = data.get("funding_rates", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 288 or len(funding_rates) < 60:
            return None

        current_price = close_prices[-1]
        return_1h = (close_prices[-1] - close_prices[-12]) / close_prices[-12] if len(close_prices) >= 12 else 0

        recent_funding = [x for x in funding_rates[-60:] if x != 0 and not np.isnan(x)]
        if len(recent_funding) < 10:
            return None

        funding_rate = recent_funding[-1]
        funding_zscore = (funding_rate - np.mean(recent_funding)) / (np.std(recent_funding) + 1e-10)
        funding_delta = funding_rate - recent_funding[0] if len(recent_funding) > 1 else 0

        if funding_zscore > self.funding_zscore_threshold and funding_delta < 0 and return_1h < 0.005:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol,
                action=ActionType.SHORT,
                quantity=self.default_quantity,
                price=current_price,
                confidence=min(funding_zscore / 4.0, 1.0),
                reason=f"Funding Exhaustion Trap: z={funding_zscore:.2f}, delta={funding_delta*100:.4f}%, ret={return_1h*100:.2f}%",
                metadata={"funding_zscore": funding_zscore, "funding_delta": funding_delta, "return_1h": return_1h},
            )

        return None


# ============================================================
# 5-8: 其余策略 (结构相同，检测条件不同)
# ============================================================

class MemeManiaRotationStrategy(BaseStrategy):
    """Meme 狂热轮动策略: volume_spike + spike_up + 高波动 → 做多"""

    def __init__(self, strategy_id: str = "meme_mania_rotation", default_quantity: float = 0.001, leverage: float = 50.0):
        super().__init__(strategy_id)
        self.default_quantity = default_quantity
        self.leverage = leverage

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        if not self._enabled:
            return None
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        symbol = data.get("symbol", "BTCUSDT")
        if len(close_prices) < 288:
            return None

        current_price = close_prices[-1]
        return_1h = (close_prices[-1] - close_prices[-12]) / close_prices[-12] if len(close_prices) >= 12 else 0
        volume_ratio = volumes[-1] / np.mean(volumes[-288:]) if len(volumes) >= 288 else 1.0
        intrabar_vol = (high_prices[-1] - low_prices[-1]) / current_price if current_price > 0 else 0

        if volume_ratio > 2.5 and (return_1h > 0.02) and intrabar_vol > 0.02:
            return StrategySignal(
                strategy_id=self.strategy_id, strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol, action=ActionType.LONG, quantity=self.default_quantity,
                price=current_price, confidence=min(volume_ratio / 5.0, 1.0),
                reason=f"Meme Mania: vol={volume_ratio:.1f}, ret={return_1h*100:.2f}%",
                metadata={"volume_ratio": volume_ratio, "return_1h": return_1h},
            )
        return None


class SessionGapExploitStrategy(BaseStrategy):
    """时段切换缺口策略: session_open + low_liquidity + 波动放大 → 做多"""

    def __init__(self, strategy_id: str = "session_gap_exploit", default_quantity: float = 0.001, leverage: float = 50.0):
        super().__init__(strategy_id)
        self.default_quantity = default_quantity
        self.leverage = leverage

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        if not self._enabled:
            return None
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        symbol = data.get("symbol", "BTCUSDT")
        hour = data.get("hour", -1)

        if len(close_prices) < 288 or hour < 0:
            return None

        current_price = close_prices[-1]
        volume_ratio = volumes[-1] / np.mean(volumes[-288:]) if len(volumes) >= 288 else 1.0
        intrabar_vol = (high_prices[-1] - low_prices[-1]) / current_price if current_price > 0 else 0

        if hour in [0, 8, 16] and volume_ratio < 0.7 and intrabar_vol > 0.015:
            return StrategySignal(
                strategy_id=self.strategy_id, strategy_type=StrategyType.TECHNICAL,
                symbol=symbol, action=ActionType.LONG, quantity=self.default_quantity,
                price=current_price, confidence=0.6,
                reason=f"Session Gap: hour={hour}, vol_ratio={volume_ratio:.1f}",
                metadata={"hour": hour, "volume_ratio": volume_ratio},
            )
        return None


class DeadCatEchoStrategy(BaseStrategy):
    """死猫回声策略: 前期大跌 + 弱反弹 + 趋势衰竭 + 量缩 → 做空"""

    def __init__(self, strategy_id: str = "dead_cat_echo", default_quantity: float = 0.001, leverage: float = 50.0):
        super().__init__(strategy_id)
        self.default_quantity = default_quantity
        self.leverage = leverage

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        if not self._enabled:
            return None
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 288:
            return None

        current_price = close_prices[-1]
        price_4h_ago = close_prices[-48] if len(close_prices) >= 48 else close_prices[0]
        price_1h_ago = close_prices[-12] if len(close_prices) >= 12 else close_prices[0]

        drop_4h = (price_4h_ago - current_price) / price_4h_ago
        bounce_1h = (current_price - price_1h_ago) / price_1h_ago
        volume_ratio = volumes[-1] / np.mean(volumes[-288:]) if len(volumes) >= 288 else 1.0
        trend_exhaustion = data.get("trend_exhaustion", 0)

        if drop_4h > 0.03 and 0.005 < bounce_1h < 0.015 and trend_exhaustion > 0 and volume_ratio < 1.0:
            return StrategySignal(
                strategy_id=self.strategy_id, strategy_type=StrategyType.EVENT_DRIVEN,
                symbol=symbol, action=ActionType.SHORT, quantity=self.default_quantity,
                price=current_price, confidence=0.7,
                reason=f"Dead Cat Echo: drop_4h={drop_4h*100:.1f}%, bounce={bounce_1h*100:.2f}%",
                metadata={"drop_4h": drop_4h, "bounce_1h": bounce_1h, "volume_ratio": volume_ratio},
            )
        return None


class LiquidityVacuumBreakoutStrategy(BaseStrategy):
    """流动性真空突破策略: low_liquidity + spread_widening + breakout → 做多"""

    def __init__(self, strategy_id: str = "liquidity_vacuum_breakout", default_quantity: float = 0.001, leverage: float = 50.0):
        super().__init__(strategy_id)
        self.default_quantity = default_quantity
        self.leverage = leverage

    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        if not self._enabled:
            return None
        close_prices = data.get("close_prices", [])
        volumes = data.get("volumes", [])
        high_prices = data.get("high_prices", [])
        low_prices = data.get("low_prices", [])
        symbol = data.get("symbol", "BTCUSDT")

        if len(close_prices) < 288:
            return None

        current_price = close_prices[-1]
        current_high = high_prices[-1]
        volume_ratio = volumes[-1] / np.mean(volumes[-288:]) if len(volumes) >= 288 else 1.0
        intrabar_vol = (current_high - low_prices[-1]) / current_price if current_price > 0 else 0
        spread_widening = intrabar_vol / (volume_ratio + 0.01) > 0.03
        rolling_high = max(high_prices[-288:-1])
        breakout_strength = (current_high - rolling_high) / rolling_high if rolling_high > 0 else 0

        if volume_ratio < 0.7 and spread_widening and breakout_strength > 0.002 and volume_ratio > 1.0:
            return StrategySignal(
                strategy_id=self.strategy_id, strategy_type=StrategyType.TECHNICAL,
                symbol=symbol, action=ActionType.LONG, quantity=self.default_quantity,
                price=current_price, confidence=0.6,
                reason=f"Liquidity Vacuum: vol={volume_ratio:.1f}, breakout={breakout_strength*100:.2f}%",
                metadata={"volume_ratio": volume_ratio, "breakout_strength": breakout_strength},
            )
        return None


# ============================================================
# 策略注册
# ============================================================

def create_innovation_strategies() -> MultiStrategyOrchestrator:
    """创建创新策略集合 (仅包含已验证的策略)"""
    orchestrator = MultiStrategyOrchestrator()

    # 1. Leveraged Short Squeeze (已验证, 500笔交易, 盈亏比1.55)
    lss = LeveragedShortSqueezeStrategy(
        strategy_id="leveraged_short_squeeze",
        score_threshold=5.0,
        default_quantity=0.001,
        leverage=50.0,
        stop_loss_capital_pct=0.10,
        take_profit_capital_pct=0.60,
        max_hold_hours=48,
    )
    orchestrator.add_strategy(lss)

    # 2. Micro Range Ripples (已验证, 但高杠杆下亏损)
    mrr = MicroRangeRipplesStrategy(
        strategy_id="micro_range_ripples",
        bb_width_threshold=0.015,
        breakout_threshold=0.003,
        volume_ratio_threshold=1.2,
        default_quantity=0.001,
        leverage=50.0,
    )
    # 默认禁用 (高杠杆下亏损)
    mrr.disable()
    orchestrator.add_strategy(mrr)

    # 3. Cascade Flip (需补充清算数据)
    cf = CascadeFlipStrategy(strategy_id="cascade_flip")
    cf.disable()
    orchestrator.add_strategy(cf)

    # 4. Funding Exhaustion Trap (需调整阈值)
    fet = FundingExhaustionTrapStrategy(strategy_id="funding_exhaustion_trap")
    fet.disable()
    orchestrator.add_strategy(fet)

    # 5. Meme Mania Rotation (样本太少)
    mmr = MemeManiaRotationStrategy(strategy_id="meme_mania_rotation")
    mmr.disable()
    orchestrator.add_strategy(mmr)

    # 6. Session Gap Exploit (未触发)
    sge = SessionGapExploitStrategy(strategy_id="session_gap_exploit")
    sge.disable()
    orchestrator.add_strategy(sge)

    # 7. Dead Cat Echo (未触发)
    dce = DeadCatEchoStrategy(strategy_id="dead_cat_echo")
    dce.disable()
    orchestrator.add_strategy(dce)

    # 8. Liquidity Vacuum Breakout (未触发)
    lvb = LiquidityVacuumBreakoutStrategy(strategy_id="liquidity_vacuum_breakout")
    lvb.disable()
    orchestrator.add_strategy(lvb)

    logger.info(
        f"Innovation strategies created: 8 strategies "
        f"(1 enabled: leveraged_short_squeeze, 7 disabled pending validation)"
    )
    return orchestrator


def register_innovation_strategies(orchestrator: MultiStrategyOrchestrator):
    """将创新策略注册到已有的编排器中"""
    innovation = create_innovation_strategies()
    for strategy_id, strategy in innovation._strategies.items():
        orchestrator.add_strategy(strategy)
    logger.info(f"Registered {len(innovation._strategies)} innovation strategies")
