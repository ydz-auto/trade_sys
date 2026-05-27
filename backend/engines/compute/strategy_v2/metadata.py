"""
Strategy Metadata - 策略元数据定义

每个策略必须声明完整的元数据，包括：
- 名称和标识
- 时间周期配置
- 所需上下文
- 标签分类
"""

from dataclasses import dataclass, field
from typing import List, Set


@dataclass(frozen=True)
class StrategyMeta:
    """
    策略元数据
    
    设计原则：
    1. required_context 声明策略需要的上下文路径
    2. primary_tf 是主信号生成周期
    3. confirm_tfs 是确认周期（用于提升置信度）
    4. execution_tf 是执行周期（决定入场时机）
    """
    
    # 基础信息
    name: str
    id: str = ""  # 可选，默认为 name 的小写替换空格
    
    # 时间周期配置
    primary_tf: str = "15m"
    confirm_tfs: List[str] = field(default_factory=lambda: ["5m", "1h"])
    execution_tf: str = "1m"
    
    # 上下文依赖
    required_context: List[str] = field(default_factory=list)
    
    # 标签分类
    tags: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        # 如果没有指定 id，自动生成
        if not self.id:
            object.__setattr__(self, 'id', self.name.lower().replace(" ", "_"))
    
    @property
    def all_timeframes(self) -> List[str]:
        """获取策略使用的所有时间周期"""
        tfs = [self.primary_tf, self.execution_tf]
        tfs.extend(self.confirm_tfs)
        return list(set(tfs))


# ============== 预定义策略类型标签 ==============

STRATEGY_TAGS = {
    # 策略类型
    "derivatives": "衍生品相关",
    "orderflow": "订单流策略",
    "technical": "技术指标策略",
    "trend": "趋势策略",
    "mean_reversion": "均值回归策略",
    "momentum": "动量策略",
    "volatility": "波动率策略",
    
    # 具体策略
    "oi_behavior": "持仓量行为",
    "funding": "资金费率",
    "liquidation": "强平",
    "short_squeeze": "逼空",
    "trade_pressure": "交易压力",
    "breakout": "突破",
    
    # 特性
    "regime_aware": "状态感知",
    "multi_timeframe": "多周期",
    "real_time": "实时",
}


__all__ = [
    "StrategyMeta",
    "STRATEGY_TAGS",
]
