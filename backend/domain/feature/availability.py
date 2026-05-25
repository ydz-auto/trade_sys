"""
Systematic Feature Availability - 系统化特征可用性

核心问题：
Feature Availability Guard 虽然有，但不是所有地方都在使用，而且
各个地方定义的规则不一致。

解决方案：
1. 集中式特征可用性规则库
2. 装饰器 + 上下文确保所有特征计算都经过检查
3. 运行时检测违规并报错
"""

from typing import Dict, List, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
import warnings

from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import get_clock

logger = get_logger("infrastructure.feature_availability")


class AvailabilityStatus(Enum):
    """可用性状态"""
    AVAILABLE = "available"           # ✅ 可用
    NOT_YET_AVAILABLE = "not_ready"   # ⚠️ 时间未到
    PARTIAL_ONLY = "partial_only"     # ⚠️ 只能用不完整 K 线
    FORBIDDEN = "forbidden"           # ❌ 明确禁止
    UNKNOWN = "unknown"               # ❓ 未注册


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

    def compute_available_at(self, feature_timestamp: int, clock) -> int:
        """计算特征可用时间"""
        if self.requires_closed_kline:
            base = clock._floor_to_kline(feature_timestamp)
            if not hasattr(clock, '_kline_interval_ms'):
                return feature_timestamp + (self.delay_periods * 60000)
            interval = clock._kline_interval_ms
            if self.delay_periods == 0:
                return base + interval
            return base + interval + (self.delay_periods * interval)
        elif self.delay_periods > 0:
            if not hasattr(clock, '_kline_interval_ms'):
                return feature_timestamp + (self.delay_periods * 60000)
            return feature_timestamp + (self.delay_periods * clock._kline_interval_ms)
        else:
            return feature_timestamp


class SystematicAvailabilityGuard:
    """
    系统化特征可用性守卫

    所有特征必须在这里注册，运行时会强制检查
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
            "spread", "imbalance_5", "imbalance_20",
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
            "btc_eth_correlation", "btc_eth_beta",
            "market_regime", "cross_currency_spread"
        ]
        for name in cross_features:
            self.register(
                FeatureRule(
                    name=name,
                    requires_closed_kline=True,
                    delay_periods=1,
                    category="cross_symbol",
                    is_derived=True,
                    description=f"跨品种 {name} 特征"
                )
            )

        # K线技术指标特征（TorchFeatureCalculator 产出）
        kline_technical_features = [
            "rsi_7", "rsi_14", "rsi_21",
            "sma_10", "sma_20", "sma_50", "sma_100",
            "ema_10", "ema_20", "ema_50",
            "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_middle", "bb_lower", "bb_width",
            "volume_ratio", "volume_ma",
            "atr_14", "momentum_10",
            "close", "open", "high", "low", "volume",
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
            "open_interest",
            "liquidation_side", "liquidation_price", "liquidation_quantity", "liquidation_value_usd",
            "mark_price", "index_price",
            "trade_price", "trade_volume",
            "bid_price_0", "bid_volume_0", "ask_price_0", "ask_volume_0",
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

    def register(self, rule: FeatureRule):
        """注册特征规则"""
        self._rules[rule.name] = rule
        logger.debug(f"Registered feature rule: {rule.name}")

    def is_registered(self, name: str) -> bool:
        """检查特征是否已注册"""
        return name in self._rules

    def check(
        self,
        feature_name: str,
        feature_timestamp: int,
        query_time: Optional[int] = None,
        clock=None
    ) -> AvailabilityStatus:
        """
        检查特征是否可用

        Args:
            feature_name: 特征名称
            feature_timestamp: 特征计算的时间
            query_time: 查询时间（默认使用当前时钟）
            clock: 时钟实例（默认使用全局）

        Returns:
            AvailabilityStatus
        """
        if clock is None:
            clock = get_clock()

        if query_time is None:
            query_time = clock.available_at_ms()

        rule = self._rules.get(feature_name)
        if rule is None:
            self._log_violation(
                feature_name, "not_registered",
                f"Feature {feature_name} not registered in availability guard"
            )
            return AvailabilityStatus.UNKNOWN

        available_at = rule.compute_available_at(feature_timestamp, clock)

        if query_time >= available_at:
            return AvailabilityStatus.AVAILABLE
        elif rule.requires_closed_kline:
            return AvailabilityStatus.NOT_YET_AVAILABLE
        else:
            return AvailabilityStatus.PARTIAL_ONLY

    def safe_get(
        self,
        feature_name: str,
        compute_fn: Callable[[], Any],
        feature_timestamp: int,
        default: Any = None,
        clock=None
    ) -> Any:
        """
        安全获取特征（带可用性检查）

        Args:
            feature_name: 特征名称
            compute_fn: 计算函数（仅在可用时调用）
            feature_timestamp: 特征计算时间
            default: 默认值
            clock: 时钟实例

        Returns:
            特征值（如果可用）
        """
        status = self.check(feature_name, feature_timestamp, clock=clock)

        if status == AvailabilityStatus.AVAILABLE:
            return compute_fn()
        elif status == AvailabilityStatus.PARTIAL_ONLY:
            return default
        else:
            self._log_violation(
                feature_name, status.value,
                f"Feature {feature_name} not available yet"
            )
            return default

    def assert_available(
        self,
        feature_name: str,
        feature_timestamp: int,
        query_time: Optional[int] = None,
        clock=None
    ):
        """
        断言特征可用（严格模式下抛出异常）

        Raises:
            ValueError: 如果特征不可用
        """
        status = self.check(feature_name, feature_timestamp, query_time, clock)

        if status != AvailabilityStatus.AVAILABLE:
            msg = f"Feature {feature_name} not available: {status.value}"
            if self._strict_mode:
                raise ValueError(msg)
            else:
                warnings.warn(msg, UserWarning)

    def _log_violation(self, feature_name: str, violation_type: str, message: str):
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

    def set_strict_mode(self, enabled: bool):
        """设置严格模式"""
        self._strict_mode = enabled

    def get_rule(self, name: str) -> Optional[FeatureRule]:
        """获取规则"""
        return self._rules.get(name)

    def check_data_availability(
        self,
        symbol: str,
        query_time: Optional[Any] = None,
        data_type: str = "default"
    ) -> bool:
        """检查数据可用性（便捷接口）"""
        return True


# Decorator
def enforce_availability(feature_name: Optional[str] = None):
    """
    强制特征可用性检查装饰器

    Args:
        feature_name: 特征名称（默认从函数名推断）

    Usage:
        @enforce_availability("volatility_1h")
        def compute_volatility_1h(data):
            ...
    """
    guard = get_systematic_guard()

    def decorator(func: Callable):
        fn_name = feature_name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            # 尝试从 kwargs 或 args 获取时间戳
            timestamp = kwargs.get('timestamp') or kwargs.get('feature_timestamp')
            if timestamp is None and len(args) > 1:
                timestamp = args[1] if isinstance(args[1], int) else None

            if timestamp is not None:
                guard.assert_available(fn_name, timestamp)

            return func(*args, **kwargs)

        return wrapper
    return decorator


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
