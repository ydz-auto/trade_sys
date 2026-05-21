"""
Signal Domain - 信号领域（核心）

这是整个系统的信号统一层。

因为：
- Feature 已经统一在 Feature Matrix
- 但 Signal 还散落各处
- 没有统一的信号生命周期管理
- 没有统一的信号融合机制

这是现在最大的缺口。
"""

from domain.signal.models import (
    Signal,
    SignalDirection,
    SignalConfidence,
    SignalStrength,
    SignalState,
    SignalType,
)
from domain.signal.fusion import (
    VotingFusion,
    BlendingFusion,
    ConsensusFusion,
    EnsembleFusion,
)
from domain.signal.lifecycle import (
    SignalGenerator,
    SignalDecay,
    SignalInvalidation,
    SignalCooldown,
)
from domain.signal.registry import SignalRegistry

__all__ = [
    # Models
    "Signal",
    "SignalDirection",
    "SignalConfidence",
    "SignalStrength",
    "SignalState",
    "SignalType",
    
    # Fusion
    "VotingFusion",
    "BlendingFusion",
    "ConsensusFusion",
    "EnsembleFusion",
    
    # Lifecycle
    "SignalGenerator",
    "SignalDecay",
    "SignalInvalidation",
    "SignalCooldown",
    
    # Registry
    "SignalRegistry",
]
