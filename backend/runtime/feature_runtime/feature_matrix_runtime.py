"""
Feature Matrix Runtime - 时间因果一致的特征矩阵存储运行时

架构定位：
    FeatureRuntime (计算层，事件驱动)
         ↓ compute + store
    FeatureMatrixRuntime (存储层，PIT + 可用性检查 + 快照)
         ↓ query
    SignalRuntime / ReplayRuntime / Strategy

边界：
    FeatureRuntime        = 特征计算 (emit_event → compute → store)
    FeatureMatrixRuntime  = 特征存储 (PIT store + availability guard + snapshot)
    两者是上下游关系，不是替代关系

接入基础设施：
1. Runtime Clock - 单一时间源
2. Systematic Availability Guard - 特征可用性
3. Immutable Snapshot - 不可变特征
4. Label Isolation - 物理隔离
5. Point-in-Time Store - 时间点存储
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio

from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import (
    RuntimeClock,
    ClockMode,
    get_clock,
    set_clock_mode,
    now_ms
)
from domain.feature.availability import (
    SystematicAvailabilityGuard,
    get_systematic_guard,
    enforce_availability
)
from domain.feature.label_isolation import (
    StrictLabelStore,
    get_label_store,
    safe_dataframe
)
from infrastructure.storage.point_in_time_store import (
    PointInTimeFeatureStore,
    get_point_in_time_store
)
from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    get_immutable_snapshot_store,
    create_immutable_snapshot
)
from domain.feature.infrastructure.partial_candle_handler import (
    PartialCandleHandler,
    get_partial_candle_handler
)


logger = get_logger("feature_matrix_runtime")


class TimeCausalFeatureMatrix:
    """
    时间因果一致的特征矩阵
    
    重点防护：
    - 只能看到当前时间之前的特征
    - K 线必须完成才能使用
    - Label 物理隔离
    - 特征不可变
    """
    
    def __init__(
        self,
        symbol: str,
        mode: str = "live"
    ):
        self.symbol = symbol
        self.mode = mode  # "live", "replay", "paper"
        
        # 1. 初始化基础设施（不是上帝对象！只是组合使用！）
        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._pit_store = get_point_in_time_store(symbol)
        self._snapshot_store = get_immutable_snapshot_store(symbol)
        self._partial_candle = get_partial_candle_handler()
        
        # 2. 根据模式设置
        self._setup_mode()
        
        self._running = False
        
        logger.info(f"Time-Causal Feature Matrix initialized for {symbol}, mode={mode}")
    
    def _setup_mode(self):
        """根据模式设置时钟和 Label"""
        if self.mode == "replay":
            set_clock_mode(ClockMode.REPLAY)
            # Research 模式可以访问 Label
            from domain.feature.label_isolation import set_label_store_mode
            set_label_store_mode("research")
        elif self.mode == "paper":
            set_clock_mode(ClockMode.PAPER)
            from domain.feature.label_isolation import set_label_store_mode
            set_label_store_mode("runtime")
        else:  # live
            set_clock_mode(ClockMode.LIVE)
            from domain.feature.label_isolation import set_label_store_mode
            set_label_store_mode("runtime")
    
    def advance_to(self, timestamp_ms: int):
        """如果是 Replay 模式，推进时钟"""
        if self.mode == "replay":
            self._clock.advance_to(timestamp_ms)
    
    def update_kline(
        self,
        symbol: str,
        kline_data: Dict[str, Any],
        timestamp_ms: Optional[int] = None
    ):
        """
        更新 K 线（时间因果安全）
        
        重点防护：Partial Candle 检查
        """
        if timestamp_ms is None:
            timestamp_ms = now_ms()
        
        # 1. 存储到 Point-in-Time 存储
        self._pit_store.store_batch({
            "open": float(kline_data.get("open", 0)),
            "high": float(kline_data.get("high", 0)),
            "low": float(kline_data.get("low", 0)),
            "close": float(kline_data.get("close", 0)),
            "volume": float(kline_data.get("volume", 0))
        }, timestamp_ms)
        
        # 2. 记录到 Lineage（可选）
        # self._lineage.register_source("kline", ...)
    
    def get_features_at(
        self,
        timestamp_ms: int,
        feature_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        获取指定时间的特征（时间因果安全）
        
        重点防护：
        - 只返回 <= timestamp_ms 的特征
        - 自动检查特征可用性
        """
        # 1. 获取当前时钟时间作为上限
        current_clock = self._clock.available_at_ms()
        
        # 2. 确保不会获取未来数据
        safe_timestamp = min(timestamp_ms, current_clock)
        
        # 3. 从 PIT 存储获取
        features = self._pit_store.get_features_at_time(safe_timestamp)
        
        if feature_names is not None:
            # 检查每个特征的可用性
            from domain.feature.availability import AvailabilityStatus
            safe_features = {}
            for name in feature_names:
                status = self._availability_guard.check(
                    feature_name=name,
                    feature_timestamp=safe_timestamp,
                    query_time=current_clock,
                    clock=self._clock
                )
                
                if status == AvailabilityStatus.AVAILABLE and name in features:
                    safe_features[name] = features[name]
                else:
                    logger.debug(f"Feature {name} unavailable: {status.value}")
            
            features = safe_features
        
        return features
    
    def create_snapshot(
        self,
        features: Dict[str, Any],
        snapshot_id: Optional[str] = None
    ) -> ImmutableFeatureSnapshot:
        """
        创建不可变的特征快照
        
        防止未来数据污染历史状态
        """
        snapshot = create_immutable_snapshot(
            features=features,
            snapshot_id=snapshot_id,
            metadata={
                "symbol": self.symbol,
                "mode": self.mode,
                "timestamp": self._clock.available_at_ms()
            }
        )
        
        self._snapshot_store.store(snapshot)
        return snapshot
    
    def check_candle_closed(
        self,
        candle_time: int,
        period_ms: int = 60000
    ) -> bool:
        """
        检查 K 线是否已完成（防止 Partial Candle 泄漏）
        
        重点防护：不能使用还没收完的 K 线
        """
        available_at = self._clock.available_at_ms()
        return self._partial_candle.is_candle_closed(
            candle_timestamp=candle_time,
            available_at=available_at,
            period_ms=period_ms
        )
    
    def safe_dataframe(self, df):
        """清理 DataFrame，确保 Label 隔离"""
        return safe_dataframe(df)
    
    async def start(self):
        """启动运行时"""
        if self._running:
            return
        self._running = True
        logger.info(f"Feature Matrix Runtime started for {self.symbol}")
    
    async def stop(self):
        """停止运行时"""
        if not self._running:
            return
        self._running = False
        logger.info(f"Feature Matrix Runtime stopped for {self.symbol}")
    
    def is_running(self) -> bool:
        return self._running


# 全局实例（单例）
_tc_feature_matrix: Dict[str, TimeCausalFeatureMatrix] = {}


def get_feature_matrix_runtime(
    symbol: str,
    mode: str = "live"
) -> TimeCausalFeatureMatrix:
    """获取特征矩阵运行时（工厂函数）"""
    if symbol not in _tc_feature_matrix:
        _tc_feature_matrix[symbol] = TimeCausalFeatureMatrix(
            symbol=symbol,
            mode=mode
        )
    return _tc_feature_matrix[symbol]
