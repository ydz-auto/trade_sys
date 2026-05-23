"""
Signal Runtime - 信号生成运行时

合并 event_service + fusion_service + strategy_service

职责：
1. 消费 RAW_DATA，提取事件
2. 融合多个事件，生成信号
3. 运行策略，生成决策

用法:
    python -m runtime.signal_runtime
"""

from runtime.signal_runtime.runtime import TimeCausalSignalRuntime, get_signal_runtime

SignalRuntime = TimeCausalSignalRuntime

__all__ = ["SignalRuntime", "TimeCausalSignalRuntime", "get_signal_runtime"]
