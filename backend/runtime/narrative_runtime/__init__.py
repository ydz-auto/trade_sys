"""
Narrative Runtime - AI 叙事引擎运行时

职责：
1. 事件序列总结
2. 决策解释
3. 市场叙事生成

用法:
    python -m runtime.narrative_runtime
"""

from runtime.narrative_runtime.runtime import NarrativeRuntime, get_narrative_runtime

__all__ = ["NarrativeRuntime", "get_narrative_runtime"]
