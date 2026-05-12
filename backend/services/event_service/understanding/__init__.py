"""
Event Understanding Layer - 事件理解层
负责：LLM 语义处理、事件提取、情绪分析、Narrative 检测、Regime 标记

架构：
data_service (事实层)
    ↓
event_service (理解层)
    ├── skills/        # Skill 适配器（ODaily, Twitter, Macro, ETF）
    ├── llm/          # LLM 客户端
    ├── parser/       # 原始数据解析
    ├── extractor/    # 事件提取
    ├── classifier/   # 分类器
    ├── engine/       # 理解引擎
    └── hub/          # 理解中心
        ↓
fusion_service (共识层)
"""

from .parser import DataParser
from .extractor import EventExtractor
from .classifier import EventClassifier
from .engine import UnderstandingEngine
from .hub import UnderstandingHub

__all__ = [
    "DataParser",
    "EventExtractor",
    "EventClassifier",
    "UnderstandingEngine",
    "UnderstandingHub",
]
