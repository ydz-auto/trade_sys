#!/usr/bin/env python3
"""
系统全策略回测 - 所有策略统一回测

参数配置:
- 初始本金: $10,000
- 杠杆: 50x
- 止损: 本金 10% (价格波动 0.2%)
- 止盈: 动态 60%~1000% (追踪止盈)
- 数据范围: 近 5 个月 (2025-12 ~ 2026-04)
- 不复利: 固定保证金

包含策略:
1. 原有策略: RSI, MACD, Panic Reversal, Long Liquidation Bounce, Volume Climax Fade, Weak Bounce Short
2. 创新策略: Leveraged Short Squeeze, Micro Range Ripples, Cascade Flip, Funding Exhaustion Trap, Meme Mania Rotation, Session Gap Exploit, Dead Cat Echo, Liquidity Vacuum Breakout
"""

import sys
from pathlib import Path
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import json

import pandas as pd
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.data_lake import get_features_path, get_research_path


# ============================================================
# 数据结构
# ============================================================

class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    features: Dict = field(default_factory=dict)


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0  # $10,000 本金
    commission: float = 0.0005
    slippage: float = 0.0002
    position_size: float = 1.0  # 全仓
    leverage: float = 50.0  # 50x 杠杆
    stop_loss_capital_pct: float = 0.15  # 止损 15% 本金 (优化后)
    take_profit_min_capital_pct: float = 0.60  # 最小止盈 60% 本金
    take_profit_max_capital_pct: float = 10.0  # 最大止盈 1000% 本金
    trailing_stop_drawdown_pct: float = 0.15  # 追踪止盈回撤 15% (优化后)
    max_hold_hours: int = 48  # 最大持仓 48 小时


# ============================================================
# 策略定义
# ============================================================

STRATEGY_DEFINITIONS = {
    # 原有策略
    "rsi_14": {
        "name": "RSI Strategy",
        "direction": "both",
        "timeframe": "1h",
        "description": "RSI 超买超卖策略",
    },
    "macd_12_26_9": {
        "name": "MACD Strategy",
        "direction": "both",
        "timeframe": "1h",
        "description": "MACD 金叉死叉策略",
    },
    "panic_reversal": {
        "name": "Panic Reversal",
        "direction": "long",
        "timeframe": "1h",
        "description": "恐慌性下跌后反弹",
    },
    "long_liquidation_bounce": {
        "name": "Long Liquidation Bounce",
        "direction": "long",
        "timeframe": "1h",
        "description": "多头爆仓后反弹",
    },
    "volume_climax_fade": {
        "name": "Volume Climax Fade",
        "direction": "short",
        "timeframe": "1h",
        "description": "放量高潮衰竭做空",
    },
    "weak_bounce_short": {
        "name": "Weak Bounce Short",
        "direction": "short",
        "timeframe": "1h",
        "description": "弱反弹后做空",
    },
    # 创新策略
    "leveraged_short_squeeze": {
        "name": "Leveraged Short Squeeze",
        "direction": "short",
        "timeframe": "1-15m",
        "description": "多头爆仓+OI激增+Funding极高 → 做空回调",
    },
    "micro_range_ripples": {
        "name": "Micro Range Ripples",
        "direction": "long",
        "timeframe": "1-5m",
        "description": "低波动区间突破 → 做多",
    },
    "cascade_flip": {
        "name": "Cascade Flip",
        "direction": "long",
        "timeframe": "5-30m",
        "description": "连锁爆仓后价格反弹 → 做多",
    },
    "funding_exhaustion_trap": {
        "name": "Funding Exhaustion Trap",
        "direction": "short",
        "timeframe": "15m-1h",
        "description": "Funding极高+仓位快速变化 → 做空",
    },
    "meme_mania_rotation": {
        "name": "Meme Mania Rotation",
        "direction": "long",
        "timeframe": "15m-4h",
        "description": "板块轮动+放量 → 做多",
    },
    "session_gap_exploit": {
        "name": "Session Gap Exploit",
        "direction": "long",
        "timeframe": "5m-1h",
        "description": "时段切换引发的微型波动 → 做多",
    },
    "dead_cat_echo": {
        "name": "Dead Cat Echo",
        "direction": "short",
        "timeframe": "15m-2h",
        "description": "暴跌弱反弹后的次级反转 → 做空",
    },
    "liquidity_vacuum_breakout": {
        "name": "Liquidity Vacuum Breakout",
        "direction": "long",
        "timeframe": "5-30m",
        "description": "夜间低流动性突破 → 做多",
    },
}


# ============================================================
# 全策略回测引擎
# ============================================================

class AllStrategiesBacktester:
    """全策略回测引擎 - 支持动态止盈"""

    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.bars: List[Bar] = []
        self.trades: List[Dict] = []
        self.equity_curve: List[Dict] = []
        self.position: Optional[Dict] = None
        self.capital: float = 0.0

    def load_df(self, df: pd.DataFrame):
        """加载 DataFrame → Bar 列表"""
        self.bars = []
        for _, row in df.iterrows():
            bar = Bar(
                timestamp=row["timestamp"],
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                features=row.to_dict(),
            )
            self.bars.append(bar)

    def prepare_features(self):
        """准备回测所需特征 (5分钟粒度)"""
        n = len(self.bars)
        BARS_1H = 12
        BARS_24H = 288

        volumes = np.array([b.volume for b in self.bars])
        avg_volumes = np.full(n, volumes[0])
        for i in range(1, n):
            start = max(0, i - BARS_24H)
            avg_volumes[i] = np.mean(volumes[start:i + 1])

        highs = np.array([b.high for b in self.bars])
        rolling_highs = np.full(n, highs[0])
        for i in range(1, n):
            start = max(0, i - BARS_24H)
            rolling_highs[i] = np.max(highs[start:i])

        for i in range(n):
            bar = self.bars[i]
            f = bar.features

            # 收益率
            if i >= BARS_1H:
                f["return_1h"] = (bar.close - self.bars[i - BARS_1H].close) / self.bars[i - BARS_1H].close
            else:
                f["return_1h"] = 0.0

            if i >= 1:
                f["return_5m"] = (bar.close - self.bars[i - 1].close) / self.bars[i - 1].close
            else:
                f["return_5m"] = 0.0

            # Bar内波动率
            f["intrabar_volatility"] = (bar.high - bar.low) / bar.close if bar.close > 0 else 0

            # 成交量比率
            f["volume_ratio"] = bar.volume / avg_volumes[i] if avg_volumes[i] > 0 else 1.0

            # 时间特征
            f["hour"] = bar.timestamp.hour
            f["day_of_week"] = bar.timestamp.dayofweek
            f["is_weekend"] = bar.timestamp.dayofweek >= 5

            # 时段
            if 0 <= f["hour"] < 8:
                f["session"] = "asia"
            elif 8 <= f["hour"] < 16:
                f["session"] = "europe"
            else:
                f["session"] = "us"

            f["session_open"] = f["hour"] in [0, 8, 16]

            # Funding 特征
            funding = f.get("funding_rate", 0)
            if pd.isna(funding):
                funding = 0
            f["funding_rate"] = funding

            # Funding Z-Score
            fz = f.get("funding_zscore", 0)
            if pd.isna(fz):
                fz = 0
            f["funding_zscore"] = fz

            # Funding Delta
            fd = f.get("funding_delta", 0)
            if pd.isna(fd):
                fd = 0
            f["funding_delta"] = fd

            # 趋势衰竭
            te = f.get("trend_exhaustion", 0)
            if pd.isna(te):
                te = 0
            f["trend_exhaustion"] = te

            # 突破强度
            f["breakout_strength_24h"] = (bar.high - rolling_highs[i]) / rolling_highs[i] if rolling_highs[i] > 0 else 0

            # Spike 检测
            spike_up = f.get("spike_up", False)
            f["spike_up"] = bool(spike_up) if not pd.isna(spike_up) else False
            spike_down = f.get("spike_down", False)
            f["spike_down"] = bool(spike_down) if not pd.isna(spike_down) else False

            # Volume Spike
            f["volume_spike"] = f["volume_ratio"] > 2.5

            # Regime
            regime = f.get("regime", "ranging")
            if pd.isna(regime):
                regime = "ranging"
            f["regime"] = regime

            # Low liquidity
            f["low_liquidity"] = f["volume_ratio"] < 0.7

            # Spread widening
            f["spread_widening"] = f["intrabar_volatility"] / (f["volume_ratio"] + 0.01) > 0.03

            # RSI
            if "rsi_14" not in f or pd.isna(f.get("rsi_14")):
                if i >= 14:
                    prices = [b.close for b in self.bars[i-14:i+1]]
                    deltas = np.diff(prices)
                    gains = np.where(deltas > 0, deltas, 0)
                    losses = np.where(deltas < 0, -deltas, 0)
                    avg_gain = np.mean(gains[-14:]) if len(gains) >= 14 else 1e-10
                    avg_loss = np.mean(losses[-14:]) if len(losses) >= 14 else 1e-10
                    rs = avg_gain / avg_loss if avg_loss > 0 else 0
                    f["rsi_14"] = 100 - (100 / (1 + rs))
                else:
                    f["rsi_14"] = 50.0

            # MACD
            if "macd" not in f or pd.isna(f.get("macd")):
                if i >= 26:
                    prices = [b.close for b in self.bars[i-26:i+1]]
                    ema12 = np.mean(prices[-12:])
                    ema26 = np.mean(prices[-26:])
                    f["macd"] = ema12 - ema26
                    f["macd_signal"] = f["macd"] * 0.9  # 简化
                else:
                    f["macd"] = 0.0
                    f["macd_signal"] = 0.0

    # ----------------------------------------------------------
    # 策略检测
    # ----------------------------------------------------------

    def detect_rsi(self, bar: Bar, i: int) -> Optional[str]:
        """RSI 策略"""
        f = bar.features
        rsi = f.get("rsi_14", 50)
        if rsi < 30:
            return "rsi_14_long"
        elif rsi > 70:
            return "rsi_14_short"
        return None

    def detect_macd(self, bar: Bar, i: int) -> Optional[str]:
        """MACD 策略"""
        f = bar.features
        macd = f.get("macd", 0)
        macd_signal = f.get("macd_signal", 0)
        if macd > macd_signal and macd > 0:
            return "macd_12_26_9_long"
        elif macd < macd_signal and macd < 0:
            return "macd_12_26_9_short"
        return None

    def detect_panic_reversal(self, bar: Bar, i: int) -> Optional[str]:
        """恐慌反弹策略"""
        f = bar.features
        if f.get("return_1h", 0) < -0.015 and f.get("volume_ratio", 1) > 1.5:
            return "panic_reversal"
        return None

    def detect_long_liquidation_bounce(self, bar: Bar, i: int) -> Optional[str]:
        """多头爆仓反弹"""
        f = bar.features
        if f.get("return_1h", 0) < -0.02 and f.get("volume_ratio", 1) > 2.0:
            return "long_liquidation_bounce"
        return None

    def detect_volume_climax_fade(self, bar: Bar, i: int) -> Optional[str]:
        """放量高潮衰竭"""
        f = bar.features
        if f.get("volume_ratio", 1) > 2.0 and f.get("intrabar_volatility", 0) > 0.025:
            wick = (bar.high - bar.close) / (bar.high - bar.low + 0.001)
            if wick > 0.3:
                return "volume_climax_fade"
        return None

    def detect_weak_bounce_short(self, bar: Bar, i: int) -> Optional[str]:
        """弱反弹做空"""
        f = bar.features
        if i < 48:
            return None
        drop_4h = (self.bars[i-48].close - bar.close) / self.bars[i-48].close
        bounce_1h = (bar.close - self.bars[i-12].close) / self.bars[i-12].close if i >= 12 else 0
        if drop_4h > 0.03 and 0.005 < bounce_1h < 0.015:
            return "weak_bounce_short"
        return None

    def detect_leveraged_short_squeeze(self, bar: Bar, i: int) -> Optional[str]:
        """杠杆空头挤压策略"""
        f = bar.features
        if i < 288:
            return None

        score = 0
        fz = f.get("funding_zscore", 0)
        if not pd.isna(fz) and fz > 1.5:
            score += 3
        elif not pd.isna(fz) and fz > 1.0:
            score += 1

        funding = f.get("funding_rate", 0)
        if not pd.isna(funding) and funding > 0.0003:
            score += 2

        ret_1h = f.get("return_1h", 0)
        if ret_1h > 0.01:
            score += 2
        elif ret_1h > 0.005:
            score += 1

        vr = f.get("volume_ratio", 1)
        if vr > 2.5:
            score += 2
        elif vr > 1.5:
            score += 1

        if f.get("volume_spike", False):
            score += 1

        if f.get("spread_widening", False):
            score += 1

        wick = (bar.high - bar.close) / (bar.high - bar.low + 0.001)
        if wick > 0.6:
            score += 1

        return "leveraged_short_squeeze" if score >= 5 else None

    def detect_micro_range_ripples(self, bar: Bar, i: int) -> Optional[str]:
        """微区间波纹策略"""
        f = bar.features
        if i < 288:
            return None
        if f.get("bb_width", 0.02) < 0.015 and f.get("breakout_strength_24h", 0) > 0.003 and f.get("volume_ratio", 1) > 1.2:
            return "micro_range_ripples"
        return None

    def detect_cascade_flip(self, bar: Bar, i: int) -> Optional[str]:
        """连锁爆仓翻转"""
        f = bar.features
        if i < 288:
            return None
        if f.get("volume_ratio", 1) > 3.0 and f.get("return_1h", 0) < -0.02 and f.get("funding_rate", 0) > 0.0002:
            return "cascade_flip"
        return None

    def detect_funding_exhaustion_trap(self, bar: Bar, i: int) -> Optional[str]:
        """Funding 枯竭陷阱"""
        f = bar.features
        if i < 288:
            return None
        if f.get("funding_zscore", 0) > 2.5 and f.get("funding_delta", 0) < 0 and f.get("return_1h", 0) < 0.005:
            return "funding_exhaustion_trap"
        return None

    def detect_meme_mania_rotation(self, bar: Bar, i: int) -> Optional[str]:
        """Meme 狂热轮动"""
        f = bar.features
        if i < 288:
            return None
        if f.get("volume_spike", False) and (f.get("spike_up", False) or f.get("return_1h", 0) > 0.02) and f.get("intrabar_volatility", 0) > 0.02:
            return "meme_mania_rotation"
        return None

    def detect_session_gap_exploit(self, bar: Bar, i: int) -> Optional[str]:
        """时段切换缺口"""
        f = bar.features
        if i < 288:
            return None
        if f.get("session_open", False) and f.get("low_liquidity", False) and f.get("intrabar_volatility", 0) > 0.015:
            return "session_gap_exploit"
        return None

    def detect_dead_cat_echo(self, bar: Bar, i: int) -> Optional[str]:
        """死猫回声"""
        f = bar.features
        if i < 288:
            return None
        price_4h_ago = self.bars[i - 48].close
        drop_4h = (price_4h_ago - bar.close) / price_4h_ago
        price_1h_ago = self.bars[i - 12].close
        bounce_1h = (bar.close - price_1h_ago) / price_1h_ago
        if drop_4h > 0.03 and 0.005 < bounce_1h < 0.015 and f.get("trend_exhaustion", 0) > 0 and f.get("volume_ratio", 1) < 1.0:
            return "dead_cat_echo"
        return None

    def detect_liquidity_vacuum_breakout(self, bar: Bar, i: int) -> Optional[str]:
        """流动性真空突破"""
        f = bar.features
        if i < 288:
            return None
        if f.get("low_liquidity", False) and f.get("spread_widening", False) and f.get("breakout_strength_24h", 0) > 0.002 and f.get("volume_ratio", 1) > 1.0:
            return "liquidity_vacuum_breakout"
        return None

    # ----------------------------------------------------------
    # 开仓逻辑
    # ----------------------------------------------------------

    def _open_position(self, bar: Bar, strategy: str, direction: str):
        """开仓 - 支持动态止盈"""
        leverage = self.config.leverage

        # 计算止损价格 (本金 10%)
        sl_price_pct = self.config.stop_loss_capital_pct / leverage

        # 初始止盈价格 (本金 60%)
        tp_price_pct = self.config.take_profit_min_capital_pct / leverage

        # 固定保证金 = 初始本金的 position_size 比例
        margin = self.config.initial_capital * self.config.position_size
        value = margin * leverage
        qty = value / bar.close

        if direction == "long":
            cost = margin * (1 + self.config.commission + self.config.slippage)
            stop_loss_price = bar.close * (1 - sl_price_pct)
            take_profit_price = bar.close * (1 + tp_price_pct)
        else:  # short
            cost = margin * (1 + self.config.commission + self.config.slippage)
            stop_loss_price = bar.close * (1 + sl_price_pct)
            take_profit_price = bar.close * (1 - tp_price_pct)

        self.position = {
            "type": direction,
            "entry_price": bar.close,
            "qty": qty,
            "capital": cost,
            "margin": margin,
            "leverage": leverage,
            "entry_time": bar.timestamp,
            "strategy": strategy,
            "stop_loss_price": stop_loss_price,
            "take_profit_price": take_profit_price,
            # 动态止盈参数
            "highest_price": bar.close,  # 多头: 跟踪最高价
            "lowest_price": bar.close,   # 空头: 跟踪最低价
            "trailing_stop_price": stop_loss_price if direction == "long" else stop_loss_price,
        }
        self.capital -= cost

    # ----------------------------------------------------------
    # 平仓逻辑
    # ----------------------------------------------------------

    def _close(self, bar: Bar, reason: str):
        """平仓"""
        if not self.position:
            return

        leverage = self.position.get("leverage", 1.0)
        entry_price = self.position["entry_price"]
        qty = self.position["qty"]
        margin = self.position.get("margin", self.position["capital"])

        if self.position["type"] == "long":
            price_pnl_pct = (bar.close - entry_price) / entry_price
            pnl = margin * price_pnl_pct * leverage
        else:
            price_pnl_pct = (entry_price - bar.close) / entry_price
            pnl = margin * price_pnl_pct * leverage

        pnl -= margin * (self.config.commission + self.config.slippage)
        pnl_pct = pnl / margin if margin > 0 else 0

        self.trades.append({
            "type": self.position["type"],
            "strategy": self.position["strategy"],
            "entry": entry_price,
            "exit": bar.close,
            "pnl": pnl,
            "pnl_pct": pnl_pct,
            "margin": margin,
            "leverage": leverage,
            "close_reason": reason,
            "entry_time": self.position["entry_time"],
            "exit_time": bar.timestamp,
            "hold_hours": (bar.timestamp - self.position["entry_time"]).total_seconds() / 3600,
        })

        self.capital += margin + pnl
        self.position = None

    # ----------------------------------------------------------
    # 回测主循环
    # ----------------------------------------------------------

    def run_backtest(self) -> Dict:
        """运行全策略回测"""
        self.trades = []
        self.equity_curve = []
        self.position = None
        self.capital = self.config.initial_capital
        peak = self.capital

        # 所有检测器
        detectors = {
            # 原有策略
            "rsi_14_long": (self.detect_rsi, "long"),
            "rsi_14_short": (self.detect_rsi, "short"),
            "macd_12_26_9_long": (self.detect_macd, "long"),
            "macd_12_26_9_short": (self.detect_macd, "short"),
            "panic_reversal": (self.detect_panic_reversal, "long"),
            "long_liquidation_bounce": (self.detect_long_liquidation_bounce, "long"),
            "volume_climax_fade": (self.detect_volume_climax_fade, "short"),
            "weak_bounce_short": (self.detect_weak_bounce_short, "short"),
            # 创新策略
            "leveraged_short_squeeze": (self.detect_leveraged_short_squeeze, "short"),
            "micro_range_ripples": (self.detect_micro_range_ripples, "long"),
            "cascade_flip": (self.detect_cascade_flip, "long"),
            "funding_exhaustion_trap": (self.detect_funding_exhaustion_trap, "short"),
            "meme_mania_rotation": (self.detect_meme_mania_rotation, "long"),
            "session_gap_exploit": (self.detect_session_gap_exploit, "long"),
            "dead_cat_echo": (self.detect_dead_cat_echo, "short"),
            "liquidity_vacuum_breakout": (self.detect_liquidity_vacuum_breakout, "long"),
        }

        for i, bar in enumerate(self.bars):
            if i < 288:
                continue

            f = bar.features

            # 检测所有信号
            signals = []
            for strategy_key, (detector, default_direction) in detectors.items():
                result = detector(bar, i)
                if result:
                    # 解析方向
                    if "_long" in result:
                        direction = "long"
                        strategy = result.replace("_long", "")
                    elif "_short" in result:
                        direction = "short"
                        strategy = result.replace("_short", "")
                    else:
                        direction = default_direction
                        strategy = result
                    signals.append((strategy, direction))

            # 持仓管理
            if self.position:
                elapsed = (bar.timestamp - self.position["entry_time"]).total_seconds() / 3600
                max_hold = self.config.max_hold_hours

                # 更新最高/最低价 (用于追踪止盈)
                if self.position["type"] == "long":
                    if bar.high > self.position["highest_price"]:
                        self.position["highest_price"] = bar.high
                        # 更新追踪止盈线
                        drawdown_pct = self.config.trailing_stop_drawdown_pct / self.position["leverage"]
                        new_trailing_stop = self.position["highest_price"] * (1 - drawdown_pct)
                        # 确保不低于初始止损
                        if new_trailing_stop > self.position["stop_loss_price"]:
                            self.position["trailing_stop_price"] = new_trailing_stop
                else:  # short
                    if bar.low < self.position["lowest_price"]:
                        self.position["lowest_price"] = bar.low
                        drawdown_pct = self.config.trailing_stop_drawdown_pct / self.position["leverage"]
                        new_trailing_stop = self.position["lowest_price"] * (1 + drawdown_pct)
                        if new_trailing_stop < self.position["stop_loss_price"]:
                            self.position["trailing_stop_price"] = new_trailing_stop

                # 计算当前盈亏
                if self.position["type"] == "long":
                    current_pnl_pct = (bar.close - self.position["entry_price"]) / self.position["entry_price"]
                else:
                    current_pnl_pct = (self.position["entry_price"] - bar.close) / self.position["entry_price"]

                # 检查是否达到最大止盈 (1000% 本金)
                max_tp_price_pct = self.config.take_profit_max_capital_pct / self.position["leverage"]
                max_tp_price = self.position["entry_price"] * (1 + max_tp_price_pct) if self.position["type"] == "long" else self.position["entry_price"] * (1 - max_tp_price_pct)

                # 退出条件
                close_reason = None

                # 1. 时间退出
                if elapsed >= max_hold:
                    close_reason = "time_exit"
                # 2. 止损
                elif self.position["type"] == "long" and bar.low <= self.position["stop_loss_price"]:
                    close_reason = "stop_loss"
                elif self.position["type"] == "short" and bar.high >= self.position["stop_loss_price"]:
                    close_reason = "stop_loss"
                # 3. 追踪止盈
                elif self.position["type"] == "long" and bar.low <= self.position["trailing_stop_price"]:
                    close_reason = "trailing_stop"
                elif self.position["type"] == "short" and bar.high >= self.position["trailing_stop_price"]:
                    close_reason = "trailing_stop"
                # 4. 最大止盈
                elif self.position["type"] == "long" and bar.high >= max_tp_price:
                    close_reason = "max_take_profit"
                elif self.position["type"] == "short" and bar.low <= max_tp_price:
                    close_reason = "max_take_profit"
                # 5. 反向信号退出
                elif signals:
                    for sig_strategy, sig_direction in signals:
                        if self.position["type"] != sig_direction:
                            close_reason = "reverse_signal"
                            break

                if close_reason:
                    self._close(bar, close_reason)

            # 开仓 (如果没有持仓)
            if not self.position and signals:
                # 只取第一个信号
                strategy, direction = signals[0]
                self._open_position(bar, strategy, direction)

            # 权益记录
            equity = self.capital
            if self.position:
                leverage = self.position.get("leverage", 1.0)
                margin = self.position.get("margin", self.position["capital"])
                entry_price = self.position["entry_price"]
                if self.position["type"] == "long":
                    price_pnl_pct = (bar.close - entry_price) / entry_price
                else:
                    price_pnl_pct = (entry_price - bar.close) / entry_price
                pos_pnl = margin * price_pnl_pct * leverage
                equity += margin + pos_pnl

            self.equity_curve.append({
                "timestamp": bar.timestamp,
                "equity": equity,
                "position": self.position is not None,
            })

            if equity > peak:
                peak = equity

        # 强制平仓
        if self.position:
            self._close(self.bars[-1], "end_of_data")

        return self._compute_metrics()

    def _compute_metrics(self) -> Dict:
        """计算回测指标"""
        if not self.equity_curve:
            return {}

        total = self.equity_curve[-1]["equity"] - self.config.initial_capital
        total_pct = total / self.config.initial_capital

        peak = self.config.initial_capital
        max_dd = 0
        for e in self.equity_curve:
            if e["equity"] > peak:
                peak = e["equity"]
            dd = peak - e["equity"]
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = max_dd / peak if peak > 0 else 0

        longs = [t for t in self.trades if t["type"] == "long"]
        shorts = [t for t in self.trades if t["type"] == "short"]
        wins = [t for t in self.trades if t["pnl"] > 0]
        losses = [t for t in self.trades if t["pnl"] <= 0]

        win_rate = len(wins) / len(self.trades) if self.trades else 0
        total_wins = sum(t["pnl"] for t in wins)
        total_losses = abs(sum(t["pnl"] for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        # 按策略分组
        by_strategy = {}
        for t in self.trades:
            sk = t["strategy"]
            if sk not in by_strategy:
                by_strategy[sk] = {"count": 0, "wins": 0, "total_pnl": 0, "longs": 0, "shorts": 0}
            by_strategy[sk]["count"] += 1
            if t["pnl"] > 0:
                by_strategy[sk]["wins"] += 1
            by_strategy[sk]["total_pnl"] += t["pnl"]
            if t["type"] == "long":
                by_strategy[sk]["longs"] += 1
            else:
                by_strategy[sk]["shorts"] += 1

        # 按平仓原因分组
        by_close_reason = {}
        for t in self.trades:
            cr = t["close_reason"]
            if cr not in by_close_reason:
                by_close_reason[cr] = {"count": 0, "total_pnl": 0}
            by_close_reason[cr]["count"] += 1
            by_close_reason[cr]["total_pnl"] += t["pnl"]

        # 夏普比率
        if self.trades:
            returns = [t["pnl_pct"] for t in self.trades]
            if np.std(returns) > 0:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
            else:
                sharpe = 0
        else:
            sharpe = 0

        return {
            "return": total,
            "return_pct": total_pct,
            "max_dd_pct": max_dd_pct,
            "total_trades": len(self.trades),
            "long_trades": len(longs),
            "short_trades": len(shorts),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "sharpe": sharpe,
            "avg_hold_hours": np.mean([t["hold_hours"] for t in self.trades]) if self.trades else 0,
            "by_strategy": by_strategy,
            "by_close_reason": by_close_reason,
        }


# ============================================================
# 报告生成
# ============================================================

def print_backtest_report(metrics: Dict):
    """打印回测报告"""
    print("\n" + "=" * 100)
    print("📊 全策略回测报告")
    print("=" * 100)

    print(f"\n💰 总体表现:")
    print(f"   总收益: ${metrics['return']:,.2f} ({metrics['return_pct']:.2%})")
    print(f"   最大回撤: {metrics['max_dd_pct']:.2%}")
    print(f"   夏普比率: {metrics['sharpe']:.2f}")
    print(f"   胜率: {metrics['win_rate']:.2%}")
    print(f"   盈亏比: {metrics['profit_factor']:.2f}")
    print(f"   总交易: {metrics['total_trades']}")
    print(f"   平均持仓时间: {metrics['avg_hold_hours']:.1f}小时")
    print(f"   - 多头: {metrics['long_trades']}")
    print(f"   - 空头: {metrics['short_trades']}")

    if metrics.get("by_strategy"):
        print(f"\n📋 按策略分析:")
        print(f"   {'策略':<30} | {'交易数':>6} | {'胜率':>6} | {'总收益':>12} | {'多头':>5} | {'空头':>5}")
        print(f"   {'-' * 80}")
        for sk, data in sorted(metrics["by_strategy"].items(), key=lambda x: -x[1]["total_pnl"]):
            name = STRATEGY_DEFINITIONS.get(sk, {}).get("name", sk)
            wr = data["wins"] / data["count"] if data["count"] > 0 else 0
            print(f"   {name:<30} | {data['count']:>6} | {wr:>6.1%} | ${data['total_pnl']:>10,.2f} | {data['longs']:>5} | {data['shorts']:>5}")

    if metrics.get("by_close_reason"):
        print(f"\n📋 按平仓原因:")
        print(f"   {'原因':<20} | {'次数':>6} | {'总收益':>12}")
        print(f"   {'-' * 45}")
        for cr, data in sorted(metrics["by_close_reason"].items(), key=lambda x: -x[1]["total_pnl"]):
            print(f"   {cr:<20} | {data['count']:>6} | ${data['total_pnl']:>10,.2f}")


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 100)
    print("🚀 系统全策略回测 - 所有策略统一回测")
    print("=" * 100)

    data_path = get_features_path("binance", "BTCUSDT") / "features_with_structure.parquet"
    if not data_path.exists():
        print(f"❌ 数据文件不存在: {data_path}")
        return

    df = pd.read_parquet(data_path)
    print(f"\n📊 原始数据: {len(df)} 行, {len(df.columns)} 列")

    # 使用近5个月数据
    five_months_ago = df["timestamp"].max() - pd.Timedelta(days=150)
    df_recent = df[df["timestamp"] >= five_months_ago].copy().reset_index(drop=True)
    print(f"   近5个月数据: {len(df_recent)} 行 ({df_recent['timestamp'].min().date()} ~ {df_recent['timestamp'].max().date()})")

    # 重采样为5分钟
    df_5m = df_recent.set_index("timestamp").resample("5min").agg({
        "open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum",
        "funding_rate": "last", "funding_zscore": "last", "funding_delta": "last",
        "bb_upper": "last", "bb_lower": "last", "bb_middle": "last", "bb_position": "last",
        "rsi_14": "last", "macd": "last", "macd_signal": "last", "macd_hist": "last",
        "regime": "last", "regime_code": "last", "spike_up": "max", "spike_down": "max",
        "trend_exhaustion": "last", "state_squeeze": "max", "state_panic_dump": "max",
        "state_breakout": "max", "state_accumulation": "max",
        "breakout_high_24h": "max", "breakout_low_24h": "max", "breakout_strength_24h": "max",
    }).dropna(subset=["close"]).reset_index()
    print(f"   5分钟数据: {len(df_5m)} 行")

    # 初始化回测引擎 (优化后参数: 止损15%, 追踪回撤15%)
    config = BacktestConfig(
        initial_capital=10000,
        commission=0.0005,
        slippage=0.0002,
        position_size=1.0,
        leverage=50.0,
        stop_loss_capital_pct=0.15,  # 优化后: 15%
        take_profit_min_capital_pct=0.60,
        take_profit_max_capital_pct=10.0,
        trailing_stop_drawdown_pct=0.15,  # 优化后: 15%
        max_hold_hours=48,
    )

    print(f"\n📊 回测配置:")
    print(f"   本金: ${config.initial_capital:,.0f}")
    print(f"   杠杆: {config.leverage}x")
    print(f"   止损: 本金 {config.stop_loss_capital_pct*100:.0f}% (价格 {config.stop_loss_capital_pct/config.leverage*100:.2f}%)")
    print(f"   止盈: 动态 {config.take_profit_min_capital_pct*100:.0f}% ~ {config.take_profit_max_capital_pct*100:.0f}%")
    print(f"   追踪止盈回撤: {config.trailing_stop_drawdown_pct*100:.0f}%")
    print(f"   最大持仓: {config.max_hold_hours} 小时")

    tester = AllStrategiesBacktester(config)
    print(f"\n⏳ 加载数据...")
    tester.load_df(df_5m)

    print(f"⏳ 准备特征...")
    tester.prepare_features()

    print(f"\n⏳ 运行全策略回测...")
    metrics = tester.run_backtest()

    print_backtest_report(metrics)

    output_dir = get_research_path()
    output_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "timestamp": datetime.now().isoformat(),
        "config": {
            "initial_capital": config.initial_capital,
            "leverage": config.leverage,
            "stop_loss_capital_pct": config.stop_loss_capital_pct,
            "take_profit_min_capital_pct": config.take_profit_min_capital_pct,
            "take_profit_max_capital_pct": config.take_profit_max_capital_pct,
            "trailing_stop_drawdown_pct": config.trailing_stop_drawdown_pct,
        },
        "data_range": f"{df_5m['timestamp'].min().date()} ~ {df_5m['timestamp'].max().date()}",
        "metrics": {
            "return": float(metrics.get("return", 0)),
            "return_pct": float(metrics.get("return_pct", 0)),
            "max_dd_pct": float(metrics.get("max_dd_pct", 0)),
            "total_trades": int(metrics.get("total_trades", 0)),
            "win_rate": float(metrics.get("win_rate", 0)),
            "profit_factor": float(metrics.get("profit_factor", 0)),
            "sharpe": float(metrics.get("sharpe", 0)),
            "by_strategy": metrics.get("by_strategy", {}),
            "by_close_reason": metrics.get("by_close_reason", {}),
        },
    }

    output_path = output_dir / "all_strategies_backtest_2025_2026_optimized.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n💾 结果已保存: {output_path}")

    print(f"\n{'=' * 100}")
    print("✅ 回测完成！")
    print("=" * 100)

    return result


if __name__ == "__main__":
    main()
