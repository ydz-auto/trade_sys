"""
Warmup Determinism - 预热确定性控制

核心问题：
Rolling 特征需要 warmup 期才能稳定，但 Replay 和 Live 的初始化状态可能不同：
- Replay: 从头开始，warmup 期特征为 NaN
- Live: 可能已有历史数据，warmup 期特征有值

这导致 Replay 和 Live 在初始阶段的特征不一致。

解决方案：
1. 定义统一的 warmup 策略
2. 支持预热状态保存和恢复
3. 确保 Replay 和 Live 使用相同的初始状态
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import pickle

from infrastructure.logging import get_logger

logger = get_logger("domain.feature.infrastructure.warmup_determinism")


@dataclass
class WarmupState:
    """预热状态"""
    feature_name: str
    window_size: int
    current_position: int
    
    buffer: List[Any]
    running_sum: float = 0.0
    running_sum_sq: float = 0.0
    count: int = 0
    
    is_warmed_up: bool = False
    warmup_progress: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "window_size": self.window_size,
            "current_position": self.current_position,
            "buffer": self.buffer,
            "running_sum": self.running_sum,
            "running_sum_sq": self.running_sum_sq,
            "count": self.count,
            "is_warmed_up": self.is_warmed_up,
            "warmup_progress": self.warmup_progress,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WarmupState':
        return cls(
            feature_name=data["feature_name"],
            window_size=data["window_size"],
            current_position=data["current_position"],
            buffer=data["buffer"],
            running_sum=data["running_sum"],
            running_sum_sq=data["running_sum_sq"],
            count=data["count"],
            is_warmed_up=data["is_warmed_up"],
            warmup_progress=data["warmup_progress"],
        )


@dataclass
class WarmupConfig:
    """预热配置"""
    window_size: int
    min_periods: int = 1
    warmup_strategy: str = "skip"  # skip, pad, partial
    
    def __post_init__(self):
        if self.min_periods < 1:
            self.min_periods = 1
        if self.min_periods > self.window_size:
            self.min_periods = self.window_size


class WarmupDeterminismManager:
    """
    预热确定性管理器
    
    核心功能：
    1. 管理 rolling 特征的预热状态
    2. 支持状态保存和恢复
    3. 确保 Replay 和 Live 初始状态一致
    """
    
    def __init__(self):
        self._feature_states: Dict[str, WarmupState] = {}
        self._feature_configs: Dict[str, WarmupConfig] = {}
        
        self._warmup_log: List[Dict[str, Any]] = []
        self._saved_states: Dict[str, bytes] = {}
    
    def register_feature(
        self,
        feature_name: str,
        window_size: int,
        min_periods: int = 1,
        warmup_strategy: str = "skip",
    ):
        """
        注册特征
        
        Args:
            feature_name: 特征名称
            window_size: 窗口大小
            min_periods: 最小周期数
            warmup_strategy: 预热策略
        """
        config = WarmupConfig(
            window_size=window_size,
            min_periods=min_periods,
            warmup_strategy=warmup_strategy,
        )
        self._feature_configs[feature_name] = config
        
        self._feature_states[feature_name] = WarmupState(
            feature_name=feature_name,
            window_size=window_size,
            current_position=0,
            buffer=[None] * window_size,
        )
        
        logger.debug(f"Registered feature for warmup: {feature_name}, window={window_size}")
    
    def update_feature(
        self,
        feature_name: str,
        value: float,
    ) -> Tuple[Optional[float], bool]:
        """
        更新特征值
        
        Args:
            feature_name: 特征名称
            value: 新值
        
        Returns:
            Tuple[Optional[float], bool]: (有效值, 是否已预热)
        """
        if feature_name not in self._feature_states:
            logger.warning(f"Feature not registered: {feature_name}")
            return None, False
        
        state = self._feature_states[feature_name]
        config = self._feature_configs[feature_name]
        
        old_value = state.buffer[state.current_position]
        
        if old_value is not None and not (isinstance(old_value, float) and (old_value != old_value)):
            state.running_sum -= old_value
            state.running_sum_sq -= old_value * old_value
            state.count -= 1
        
        state.buffer[state.current_position] = value
        state.running_sum += value
        state.running_sum_sq += value * value
        state.count += 1
        
        state.current_position = (state.current_position + 1) % state.window_size
        
        state.count = min(state.count, state.window_size)
        
        state.is_warmed_up = state.count >= config.min_periods
        state.warmup_progress = min(1.0, state.count / config.min_periods)
        
        if not state.is_warmed_up:
            return None, False
        
        return value, True
    
    def get_rolling_mean(self, feature_name: str) -> Optional[float]:
        """获取滚动均值"""
        if feature_name not in self._feature_states:
            return None
        
        state = self._feature_states[feature_name]
        
        if not state.is_warmed_up or state.count == 0:
            return None
        
        return state.running_sum / state.count
    
    def get_rolling_std(self, feature_name: str) -> Optional[float]:
        """获取滚动标准差"""
        if feature_name not in self._feature_states:
            return None
        
        state = self._feature_states[feature_name]
        
        if not state.is_warmed_up or state.count < 2:
            return None
        
        mean = state.running_sum / state.count
        variance = (state.running_sum_sq / state.count) - (mean * mean)
        
        if variance < 0:
            variance = 0
        
        import math
        return math.sqrt(variance)
    
    def get_rolling_zscore(
        self,
        feature_name: str,
        value: float,
    ) -> Optional[float]:
        """获取滚动 Z-Score"""
        mean = self.get_rolling_mean(feature_name)
        std = self.get_rolling_std(feature_name)
        
        if mean is None or std is None or std == 0:
            return None
        
        return (value - mean) / std
    
    def is_warmed_up(self, feature_name: str) -> bool:
        """检查特征是否已预热"""
        if feature_name not in self._feature_states:
            return False
        return self._feature_states[feature_name].is_warmed_up
    
    def get_warmup_progress(self, feature_name: str) -> float:
        """获取预热进度"""
        if feature_name not in self._feature_states:
            return 0.0
        return self._feature_states[feature_name].warmup_progress
    
    def save_state(self, state_id: str) -> Dict[str, Any]:
        """
        保存当前状态
        
        Args:
            state_id: 状态ID
        
        Returns:
            Dict[str, Any]: 状态摘要
        """
        states_data = {
            name: state.to_dict()
            for name, state in self._feature_states.items()
        }
        
        self._saved_states[state_id] = pickle.dumps(states_data)
        
        summary = {
            "state_id": state_id,
            "feature_count": len(states_data),
            "warmed_up_count": sum(1 for s in self._feature_states.values() if s.is_warmed_up),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        self._warmup_log.append({
            "action": "save",
            "state_id": state_id,
            "summary": summary,
        })
        
        logger.info(f"Saved warmup state: {state_id}")
        return summary
    
    def restore_state(self, state_id: str) -> bool:
        """
        恢复状态
        
        Args:
            state_id: 状态ID
        
        Returns:
            bool: 是否成功恢复
        """
        if state_id not in self._saved_states:
            logger.warning(f"State not found: {state_id}")
            return False
        
        try:
            states_data = pickle.loads(self._saved_states[state_id])
            
            for name, data in states_data.items():
                self._feature_states[name] = WarmupState.from_dict(data)
            
            self._warmup_log.append({
                "action": "restore",
                "state_id": state_id,
                "feature_count": len(states_data),
            })
            
            logger.info(f"Restored warmup state: {state_id}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to restore state {state_id}: {e}")
            return False
    
    def export_state(self) -> Dict[str, Any]:
        """导出状态（用于 Replay 初始化）"""
        return {
            name: state.to_dict()
            for name, state in self._feature_states.items()
        }
    
    def import_state(self, state_data: Dict[str, Any]):
        """导入状态（用于 Live 初始化）"""
        for name, data in state_data.items():
            self._feature_states[name] = WarmupState.from_dict(data)
        
        logger.info(f"Imported warmup state for {len(state_data)} features")
    
    def reset_feature(self, feature_name: str):
        """重置单个特征状态"""
        if feature_name not in self._feature_configs:
            return
        
        config = self._feature_configs[feature_name]
        self._feature_states[feature_name] = WarmupState(
            feature_name=feature_name,
            window_size=config.window_size,
            current_position=0,
            buffer=[None] * config.window_size,
        )
    
    def reset_all(self):
        """重置所有特征状态"""
        for feature_name in self._feature_states.keys():
            self.reset_feature(feature_name)
        
        logger.info("Reset all warmup states")
    
    def get_warmup_summary(self) -> Dict[str, Any]:
        """获取预热摘要"""
        total = len(self._feature_states)
        warmed_up = sum(1 for s in self._feature_states.values() if s.is_warmed_up)
        
        return {
            "total_features": total,
            "warmed_up_features": warmed_up,
            "pending_features": total - warmed_up,
            "warmup_rate": warmed_up / total if total > 0 else 0,
            "feature_progress": {
                name: state.warmup_progress
                for name, state in self._feature_states.items()
            },
        }


_manager_instances: Dict[str, WarmupDeterminismManager] = {}


def get_warmup_manager(instance_id: str = "default") -> WarmupDeterminismManager:
    """获取预热管理器实例"""
    if instance_id not in _manager_instances:
        _manager_instances[instance_id] = WarmupDeterminismManager()
    return _manager_instances[instance_id]
