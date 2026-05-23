"""
Narrative Runtime - AI 叙事引擎运行时实现

事件序列总结和决策解释
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig, RuntimeState
from infrastructure.logging import get_logger
from infrastructure.messaging import get_broker, Topics
from infrastructure.runtime_clock import get_clock, ClockMode
from infrastructure.feature_availability import get_systematic_guard
from infrastructure.label_isolation import get_label_store
from infrastructure.storage.immutable_snapshot import get_immutable_snapshot_store


class NarrativeConfig(RuntimeConfig):
    """Narrative Runtime 配置"""
    name: str = "narrative_runtime"
    
    llm_provider: str = "openai"
    model: str = "gpt-4"
    max_tokens: int = 1000


class NarrativeRuntime(BaseRuntime):
    """
    Narrative Runtime
    
    职责：
    1. 事件序列总结
    2. 决策解释
    3. 市场叙事生成
    """
    
    def __init__(self, config: NarrativeConfig = None):
        config = config or NarrativeConfig.from_env()
        super().__init__(config)
        self.config: NarrativeConfig = config
        
        # 时间因果基础设施集成
        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._snapshot_store = None
        
        self.broker = None
        self.llm_client = None
        self.narrative_engine = None
    
    async def initialize(self) -> None:
        """初始化"""
        self.logger.info("Initializing Narrative Runtime with time-causal infrastructure...")
        
        # 初始化时间因果基础设施
        self._snapshot_store = get_immutable_snapshot_store("narrative")
        
        self.broker = get_broker(self.config.kafka_bootstrap_servers)
        
        try:
            from runtime.narrative_runtime.narrative_engine import NarrativeEngine
            self.narrative_engine = NarrativeEngine()
        except Exception as e:
            self.logger.warning(f"Narrative engine not available: {e}")
        
        self.logger.info("Narrative Runtime initialized successfully")
    
    async def shutdown(self) -> None:
        """关闭"""
        self.logger.info("Shutting down Narrative Runtime...")
        
        if self.broker:
            await self.broker.stop()
        
        self.logger.info(f"Narrative Runtime stopped. Stats: {self.context.stats}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Narrative Runtime...")
        
        topics = [Topics.EVENTS, Topics.SIGNALS, Topics.DECISIONS]
        
        try:
            for topic in topics:
                @self.broker.subscriber(topic)
                async def on_event(msg: dict):
                    await self.process_event(msg)
            
            await self.broker.run()
            
        except Exception as e:
            self.logger.error(f"Narrative Runtime error: {e}")
            raise
    
    async def process_event(self, msg: dict) -> None:
        """处理事件 - 支持时间因果一致性"""
        try:
            current_time = self._clock.now()
            self.context.increment_stat("events_received")
            
            # 标签隔离检查
            if self._label_store:
                self._label_store.ensure_isolation("narrative")
            
            if self.narrative_engine:
                narrative = await self.narrative_engine.process(msg)
                if narrative:
                    # 保存不可变快照
                    if self._snapshot_store:
                        snapshot_data = {
                            "narrative": narrative,
                            "event": msg,
                            "timestamp": current_time.isoformat(),
                            "clock_mode": self._clock.mode.value
                        }
                        self._snapshot_store.save(snapshot_data, timestamp=current_time)
                    
                    self.context.increment_stat("narratives_generated")
                    self.logger.info(f"Generated narrative: {narrative[:100]}...")
            
        except Exception as e:
            self.logger.error(f"Error processing event: {e}")
            self.context.record_error(str(e))
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "broker_connected": self.broker is not None,
            "narrative_engine_ready": self.narrative_engine is not None,
        })
        return health


_narrative_runtime: Optional[NarrativeRuntime] = None


def get_narrative_runtime() -> NarrativeRuntime:
    """获取 Narrative Runtime 单例"""
    global _narrative_runtime
    if _narrative_runtime is None:
        _narrative_runtime = NarrativeRuntime()
    return _narrative_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Narrative Runtime - AI Narrative Engine")
    print("=" * 60)
    
    runtime = get_narrative_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
