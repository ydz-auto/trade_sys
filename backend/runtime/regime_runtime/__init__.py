"""
Regime Runtime - 市场状态运行时

因为市场环境是动态的，策略不应该永远启用，而应该 regime-aware。

Regime	行为
高波动	breakout有效
横盘	reversal有效
爆仓潮	liquidation策略有效
narrative爆发	momentum有效

这是交易智能的核心之一。
"""

import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import numpy as np

from runtime.base import BaseRuntime, RuntimeConfig
from runtime.shared import RuntimeLifecycle, RuntimeMetrics, RuntimeHealthCheck
from infrastructure.logging import get_logger
from infrastructure.runtime_clock import now_ms


logger = get_logger("regime_runtime")


def _utcnow() -> datetime:
    return datetime.utcfromtimestamp(now_ms() / 1000)


class MarketRegime(str, Enum):
    """市场状态"""
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    TRENDING = "trending"
    RANGING = "ranging"
    LIQUIDATION_CASCADE = "liquidation_cascade"
    NARRATIVE_BURST = "narrative_burst"
    LIQUIDITY_DRAIN = "liquidity_drain"
    UNKNOWN = "unknown"


@dataclass
class RegimeState:
    """状态数据"""
    regime: MarketRegime
    confidence: float
    since: datetime
    duration_seconds: float
    features: Dict[str, float]
    active_strategies: List[str]


@dataclass
class RegimeRuntimeConfig(RuntimeConfig):
    """Regime Runtime 配置"""
    name: str = "regime_runtime"
    
    volatility_window: int = 240  # 波动率窗口（数据点）
    trend_window: int = 48  # 趋势窗口
    range_threshold: float = 0.02  # 区间阈值（2%）
    volatility_threshold: float = 0.03  # 波动率阈值
    check_interval_seconds: float = 5.0  # 检查间隔


class RegimeRuntime(BaseRuntime):
    """Regime Runtime - 市场状态运行时"""
    
    def __init__(self, config: Optional[RegimeRuntimeConfig] = None):
        config = config or RegimeRuntimeConfig()
        super().__init__(config)
        self.config: RegimeRuntimeConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.current_regime: RegimeState = RegimeState(
            regime=MarketRegime.UNKNOWN,
            confidence=0.0,
            since=_utcnow(),
            duration_seconds=0.0,
            features={},
            active_strategies=[],
        )
        
        self.price_history: List[float] = []
        self.volatility_history: List[float] = []
        self.regime_history: List[Dict[str, Any]] = []
        
        # 策略注册表（regime -> 策略列表）
        self.strategy_registry: Dict[MarketRegime, List[str]] = {
            MarketRegime.HIGH_VOLATILITY: ["breakout", "momentum"],
            MarketRegime.LOW_VOLATILITY: ["mean_reversion", "range"],
            MarketRegime.TRENDING: ["trend_following", "momentum"],
            MarketRegime.RANGING: ["mean_reversion", "grid"],
            MarketRegime.LIQUIDATION_CASCADE: ["liquidation_arbitrage", "contrarian"],
            MarketRegime.NARRATIVE_BURST: ["momentum", "news_trader"],
            MarketRegime.LIQUIDITY_DRAIN: ["passive", "low_touch"],
            MarketRegime.UNKNOWN: ["conservative"],
        }
    
    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing Regime Runtime...")
        
        self.lifecycle = RuntimeLifecycle("regime")
        self.metrics = RuntimeMetrics("regime")
        self.health_check = RuntimeHealthCheck("regime")
        
        logger.info("Regime Runtime initialized successfully")
    
    async def update_market_data(
        self,
        prices: List[float],
        volatility: Optional[float] = None,
        liquidation_data: Optional[Dict[str, Any]] = None,
        narrative_data: Optional[Dict[str, Any]] = None,
        liquidity_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """更新市场数据"""
        self.price_history.extend(prices)
        if len(self.price_history) > 1000:
            self.price_history = self.price_history[-1000:]
        
        if volatility is not None:
            self.volatility_history.append(volatility)
            if len(self.volatility_history) > 500:
                self.volatility_history = self.volatility_history[-500:]
        
        self.metrics.increment("market_data_updates")
        
        await self._classify_regime(volatility, liquidation_data, narrative_data, liquidity_data)
    
    async def _classify_regime(
        self,
        current_volatility: Optional[float],
        liquidation_data: Optional[Dict[str, Any]],
        narrative_data: Optional[Dict[str, Any]],
        liquidity_data: Optional[Dict[str, Any]],
    ) -> None:
        """分类市场状态"""
        features = {}
        
        if len(self.price_history) >= self.config.trend_window:
            recent_prices = self.price_history[-self.config.trend_window:]
            returns = np.diff(recent_prices) / recent_prices[:-1]
            
            # 计算趋势强度
            trend_strength = abs(np.mean(returns)) / (np.std(returns) + 1e-10)
            features["trend_strength"] = float(trend_strength)
            
            # 计算区间性
            price_range = (np.max(recent_prices) - np.min(recent_prices)) / np.mean(recent_prices)
            features["price_range"] = float(price_range)
        
        if len(self.volatility_history) >= self.config.volatility_window:
            avg_volatility = np.mean(self.volatility_history[-self.config.volatility_window:])
            features["volatility"] = float(avg_volatility)
        elif current_volatility is not None:
            features["volatility"] = current_volatility
        
        # 检查爆仓潮
        if liquidation_data:
            liquidation_volume = liquidation_data.get("total_volume", 0)
            features["liquidation_volume"] = liquidation_volume
        else:
            features["liquidation_volume"] = 0.0
        
        # 检查叙事爆发
        if narrative_data:
            narrative_score = narrative_data.get("score", 0)
            features["narrative_score"] = narrative_score
        else:
            features["narrative_score"] = 0.0
        
        # 检查流动性枯竭
        if liquidity_data:
            liquidity_score = liquidity_data.get("score", 0)
            features["liquidity_score"] = liquidity_score
        else:
            features["liquidity_score"] = 0.0
        
        # 分类决策
        new_regime = MarketRegime.UNKNOWN
        confidence = 0.0
        
        # 优先检查特殊状态
        if features.get("liquidation_volume", 0) > 10_000_000:
            new_regime = MarketRegime.LIQUIDATION_CASCADE
            confidence = min(1.0, features["liquidation_volume"] / 100_000_000)
        
        elif features.get("narrative_score", 0) > 0.8:
            new_regime = MarketRegime.NARRATIVE_BURST
            confidence = features["narrative_score"]
        
        elif features.get("liquidity_score", 0) > 0.7:
            new_regime = MarketRegime.LIQUIDITY_DRAIN
            confidence = features["liquidity_score"]
        
        # 检查波动状态
        elif "volatility" in features:
            if features["volatility"] > self.config.volatility_threshold:
                new_regime = MarketRegime.HIGH_VOLATILITY
                confidence = min(1.0, features["volatility"] / (self.config.volatility_threshold * 2))
            else:
                new_regime = MarketRegime.LOW_VOLATILITY
                confidence = min(1.0, (self.config.volatility_threshold - features["volatility"]) / self.config.volatility_threshold)
        
        # 检查趋势/区间
        if "trend_strength" in features and "price_range" in features:
            if features["trend_strength"] > 2.0:
                new_regime = MarketRegime.TRENDING
                confidence = max(confidence, min(1.0, features["trend_strength"] / 4.0))
            elif features["price_range"] < self.config.range_threshold:
                new_regime = MarketRegime.RANGING
                confidence = max(confidence, min(1.0, (self.config.range_threshold - features["price_range"]) / self.config.range_threshold))
        
        # 更新状态
        if new_regime != self.current_regime.regime:
            logger.info(f"Regime change: {self.current_regime.regime.value} -> {new_regime.value} (confidence: {confidence:.2f})")
            self.metrics.increment("regime_changes")
            
            self.regime_history.append({
                "old_regime": self.current_regime.regime.value,
                "new_regime": new_regime.value,
                "timestamp": _utcnow().isoformat(),
                "confidence": confidence,
            })
            
            self.current_regime = RegimeState(
                regime=new_regime,
                confidence=confidence,
                since=_utcnow(),
                duration_seconds=0.0,
                features=features,
                active_strategies=self.strategy_registry.get(new_regime, []),
            )
        else:
            self.current_regime.confidence = max(self.current_regime.confidence, confidence)
            self.current_regime.features = features
            self.current_regime.duration_seconds = (_utcnow() - self.current_regime.since).total_seconds()
    
    def get_active_strategies(self) -> List[str]:
        """获取当前状态应该启用的策略"""
        return self.current_regime.active_strategies
    
    def should_enable_strategy(self, strategy_id: str) -> bool:
        """检查策略是否应该启用"""
        return strategy_id in self.current_regime.active_strategies
    
    async def run(self) -> None:
        """主循环"""
        logger.info("Starting Regime Runtime main loop...")
        
        await self.lifecycle.transition_to_running()
        
        while not self.context.is_shutdown_requested():
            try:
                self.current_regime.duration_seconds = (
                    _utcnow() - self.current_regime.since
                ).total_seconds()
                
                await asyncio.sleep(self.config.check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in regime runtime loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)
    
    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down Regime Runtime...")
        logger.info(f"Regime Runtime stopped. Stats: {self.metrics.to_dict()}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        base_health = await super().health_check()
        
        base_health.update({
            "current_regime": self.current_regime.regime.value,
            "confidence": self.current_regime.confidence,
            "duration_seconds": self.current_regime.duration_seconds,
            "active_strategies": self.current_regime.active_strategies,
            "price_history_length": len(self.price_history),
            "regime_changes_count": len(self.regime_history),
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
        })
        
        return base_health


_regime_runtime: Optional[RegimeRuntime] = None


def get_regime_runtime() -> RegimeRuntime:
    """获取 Regime Runtime 单例"""
    global _regime_runtime
    if _regime_runtime is None:
        _regime_runtime = RegimeRuntime()
    return _regime_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Regime Runtime - Market State Detection")
    print("=" * 60)
    
    runtime = get_regime_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
