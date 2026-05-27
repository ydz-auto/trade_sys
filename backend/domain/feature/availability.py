"""
Systematic Feature Availability - 特征可用性规则（Domain 层）

注意：
- 此文件仅定义规则和数据结构
- 不依赖 infrastructure 或 runtime 模块
- 实际验证逻辑移至计算层
"""

from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class AvailabilityStatus(Enum):
    """可用性状态"""
    AVAILABLE = "available"              # ✓ 可用
    NOT_YET_AVAILABLE = "not_ready"      # ⚠️ 时间未到
    PARTIAL_ONLY = "partial_only"        # ⚠️ 只能用不完整 K 线
    FORBIDDEN = "forbidden"              # ❌ 明确禁止
    UNKNOWN = "unknown"                  # ❓ 未注册


@dataclass
class FeatureRule:
    """特征可用性规则"""
    name: str
    requires_closed_kline: bool = False
    lookback_periods: int = 0
    delay_periods: int = 0
    timeframe_ms: Optional[int] = None
    category: str = "instant"
    is_derived: bool = False
    description: str = ""


class SystematicAvailabilityGuard:
    """
    系统化特征可用性规则容器
    
    注意：
    - 仅存储和管理规则
    - 实际验证需要外部传入 clock 和 timestamp
    """

    def __init__(self):
        self._rules: Dict[str, FeatureRule] = {}
        self._violations: List[Dict] = []
        self._strict_mode: bool = True
        self._log_access: bool = True
        self._register_default_rules()

    def _register_default_rules(self):
        """注册默认规则"""
        # 即时特征 - 无延迟
        instant_features = [
            "spread_bps", "imbalance_5", "imbalance_20",
            "trade_delta", "aggressive_buy_ratio", "sweep_score",
            "oi_delta", "funding_rate", "liquidation_cluster"
        ]
        for name in instant_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=False,
                    category="instant",
                    description=f"即时 {name} 特征"
                )
            )

        # 5m 聚合特征 - 延迟 1 根
        five_min_features = [
            "volatility_5m", "trend_5m", "momentum_5m",
            "rsi_5m", "vwap_5m", "volume_5m"
        ]
        for name in five_min_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=True,
                    delay_periods=1,
                    timeframe_ms=300000,
                    category="aggregated",
                    description=f"5m {name} 特征"
                )
            )

        # 15m 聚合特征
        fifteen_min_features = [
            "volatility_15m", "trend_15m", "momentum_15m",
            "rsi_15m", "vwap_15m"
        ]
        for name in fifteen_min_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=True,
                    delay_periods=1,
                    timeframe_ms=900000,
                    category="aggregated",
                    description=f"15m {name} 特征"
                )
            )

        # 1h 聚合特征
        one_hour_features = [
            "volatility_1h", "trend_1h", "momentum_1h",
            "rsi_1h", "vwap_1h", "volume_1h"
        ]
        for name in one_hour_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=True,
                    delay_periods=1,
                    timeframe_ms=3600000,
                    category="aggregated",
                    description=f"1h {name} 特征"
                )
            )

        # 衍生品特征
        derivatives_features = [
            "funding_zscore", "oi_zscore", "leverage_crowdedness",
            "funding_oi_spread", "basis_zscore"
        ]
        for name in derivatives_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=False,
                    delay_periods=1,
                    category="derivatives",
                    is_derived=True,
                    description=f"衍生品 {name} 特征"
                )
            )

        # 跨品种特征
        cross_features = [
            "binance_return", "okx_return", "bybit_return",
            "basis", "premium",
            "lead_exchange", "lag_exchange", "lead_lag_score"
        ]
        for name in cross_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=True,
                    delay_periods=1,
                    category="cross_market",
                    is_derived=True,
                    description=f"跨品种 {name} 特征"
                )
            )

        # K线技术指标特征
        kline_technical_features = [
            "rsi_7", "rsi_14", "rsi_21",
            "sma_10", "sma_20", "sma_50", "sma_100",
            "ema_10", "ema_20", "ema_50",
            "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_middle", "bb_lower", "bb_width", "bb_width_pct",
            "volume_ratio", "volume_ma",
            "atr_14", "atr", "atr_pct", "momentum_10",
            "open", "high", "low", "close", "volume",
            "return_1h", "return_24h", "change", "change_percent",
            "closes", "highs", "lows", "support", "resistance",
            "slope", "structure", "strength",
            "realized_vol", "realized_vol_zscore",
            "volume_zscore"
        ]
        for name in kline_technical_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=True,
                    delay_periods=0,
                    category="kline_technical",
                    is_derived=True,
                    description=f"K线技术指标 {name}"
                )
            )

        # 衍生品原始特征
        derivative_raw_features = [
            "funding_rate", "funding_mark_price", "funding_index_price",
            "oi", "open_interest",
            "liquidation_long", "liquidation_short", "liquidation_total",
            "liquidation_side", "liquidation_price", 
            "liquidation_quantity", "liquidation_value_usd",
            "mark_price", "index_price",
            "trade_price", "trade_volume",
            "bid_price_0", "bid_volume_0", "ask_price_0", "ask_volume_0",
            "top5_bid_depth", "top5_ask_depth", "microprice",
            "is_vacuum", "vacuum_score", "cancel_rate", "liquidity_vacuum"
        ]
        for name in derivative_raw_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=False,
                    delay_periods=0,
                    category="derivative_raw",
                    is_derived=False,
                    description=f"衍生品原始 {name}"
                )
            )

        # 资金流特征
        flow_features = [
            "cvd", "cvd_slope", "cumulative_delta",
            "aggressive_buy_volume", "aggressive_sell_volume",
            "aggressive_buy", "aggressive_sell", "aggressive_ratio",
            "whale_buy_count", "whale_sell_count",
            "whale_buy_volume", "whale_sell_volume"
        ]
        for name in flow_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=True,
                    delay_periods=0,
                    category="flow",
                    is_derived=True,
                    description=f"资金流 {name} 特征"
                )
            )

        # 风险特征
        risk_features = [
            "high_volatility", "low_liquidity", "news_event",
            "overtrading", "drawdown_exceeded", "slippage_warning",
            "execution_paused", "regime_change", "extreme_move",
            "risk_multiplier"
        ]
        for name in risk_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=False,
                    delay_periods=0,
                    category="risk",
                    is_derived=True,
                    description=f"风险 {name} 特征"
                )
            )

    def register(self, rule: FeatureRule):
        """注册特征规则"""
        self._rules[rule.name] = rule

    def is_registered(self, name: str) -> bool:
        """检查特征是否已注册"""
        return name in self._rules

    def get_rule(self, name: str) -> Optional[FeatureRule]:
        """获取规则"""
        return self._rules.get(name)

    def get_all_rules(self) -> Dict[str, FeatureRule]:
        """获取所有规则"""
        return self._rules.copy()

    def set_strict_mode(self, enabled: bool):
        """设置严格模式"""
        self._strict_mode = enabled

    def get_strict_mode(self) -> bool:
        """获取严格模式"""
        return self._strict_mode

    def record_violation(self, feature_name: str, violation_type: str, message: str):
        """记录违规"""
        self._violations.append({
            "feature_name": feature_name,
            "violation_type": violation_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        })

    def get_violation_report(self) -> Dict:
        """获取违规报告"""
        violation_counts: Dict[str, int] = {}
        for v in self._violations:
            name = v["feature_name"]
            violation_counts[name] = violation_counts.get(name, 0) + 1

        return {
            "total_violations": len(self._violations),
            "violation_counts": violation_counts,
            "recent_violations": self._violations[-20:],
            "registered_features": list(self._rules.keys())
        }


# Global guard instance
_guard_instance: Optional[SystematicAvailabilityGuard] = None


def get_systematic_guard() -> SystematicAvailabilityGuard:
    """获取系统化可用性守卫实例"""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = SystematicAvailabilityGuard()
    return _guard_instance


def register_feature_rule(rule: FeatureRule):
    """注册特征规则"""
    get_systematic_guard().register(rule)
