"""
Correlation Runtime - 多数据源相关性分析运行时实现

定时执行多数据源相关性分析
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig, RuntimeState
from infrastructure.logging import get_logger


class CorrelationConfig(RuntimeConfig):
    """Correlation Runtime 配置"""
    name: str = "correlation_runtime"
    
    symbols: List[str] = None
    timeframes: List[str] = None
    interval: int = 3600
    output_dir: str = "./data/correlation_results"
    kafka_enabled: bool = False
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.symbols is None:
            self.symbols = os.environ.get("CORRELATION_SYMBOLS", "BTC,ETH").split(",")
        if self.timeframes is None:
            self.timeframes = os.environ.get("CORRELATION_TIMEFRAMES", "1h,4h").split(",")


class CorrelationRuntime(BaseRuntime):
    """
    Correlation Runtime
    
    功能：
    1. 定时执行多数据源相关性分析
    2. 结果存储和可视化
    3. 强信号告警
    """
    
    def __init__(self, config: CorrelationConfig = None):
        config = config or CorrelationConfig.from_env()
        super().__init__(config)
        self.config: CorrelationConfig = config
        
        self.scheduler = None
        self.results_cache: Dict[str, Dict] = {}
    
    async def initialize(self) -> None:
        """初始化"""
        self.logger.info("Initializing Correlation Runtime...")
        
        from services.data_service.pipeline.scheduler import get_scheduler, TaskPriority
        self.scheduler = get_scheduler()
        
        self._register_tasks()
        
        self.logger.info("Correlation Runtime initialized successfully")
    
    async def shutdown(self) -> None:
        """关闭"""
        self.logger.info("Shutting down Correlation Runtime...")
        
        if self.scheduler:
            await self.scheduler.stop()
        
        self.logger.info(f"Correlation Runtime stopped. Stats: {self.context.stats}")
    
    def _register_tasks(self):
        """注册定时任务"""
        from services.data_service.pipeline.scheduler import TaskPriority
        
        for symbol in self.config.symbols:
            for tf in self.config.timeframes:
                task_id = f"correlation_{symbol}_{tf}"
                task_name = f"Correlation Analysis [{symbol} {tf}]"
                
                self.scheduler.register_task(
                    task_id=task_id,
                    name=task_name,
                    callback=self._make_callback(symbol, tf),
                    interval=self.config.interval,
                    priority=TaskPriority.NORMAL,
                    timeout=300.0,
                    metadata={"symbol": symbol, "timeframe": tf},
                )
                
                self.logger.info(f"Registered task: {task_name} (interval={self.config.interval}s)")
    
    def _make_callback(self, symbol: str, timeframe: str):
        """创建分析回调函数"""
        async def callback():
            return await self.run_analysis(symbol, timeframe)
        return callback
    
    async def run_analysis(
        self,
        symbol: str,
        timeframe: str,
        news_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """执行单次分析"""
        start_time = datetime.now()
        self.logger.info(f"Starting analysis: {symbol} {timeframe}")
        
        try:
            from research.correlation import analyze_correlation
            
            result = await analyze_correlation(
                symbol=symbol,
                timeframe=timeframe,
                output_dir=str(Path(self.config.output_dir) / f"{symbol}_{timeframe}"),
                generate_visualization=True,
            )
            
            result_dict = result.to_dict()
            
            cache_key = f"{symbol}:{timeframe}"
            self.results_cache[cache_key] = result_dict
            
            self.context.increment_stat("analyses_completed")
            
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"Analysis completed: {symbol} {timeframe} in {duration:.1f}s"
            )
            
            return result_dict
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {symbol} {timeframe} - {e}")
            self.context.record_error(str(e))
            return {"error": str(e), "symbol": symbol, "timeframe": timeframe}
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Correlation Runtime...")
        
        await self.scheduler.start()
        
        while not self.context.is_shutdown_requested():
            await asyncio.sleep(10)
            
            stats = self.scheduler.get_all_stats()
            for task_id, stat in stats.items():
                if task_id.startswith("correlation_"):
                    self.logger.debug(
                        f"{stat['name']}: runs={stat['total_runs']} "
                        f"success_rate={stat['success_rate']:.0%}"
                    )
    
    def get_latest_result(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """获取最新分析结果"""
        return self.results_cache.get(f"{symbol}:{timeframe}")
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "scheduler_running": self.scheduler is not None,
            "cached_results": len(self.results_cache),
        })
        return health


_correlation_runtime: Optional[CorrelationRuntime] = None


def get_correlation_runtime() -> CorrelationRuntime:
    """获取 Correlation Runtime 单例"""
    global _correlation_runtime
    if _correlation_runtime is None:
        _correlation_runtime = CorrelationRuntime()
    return _correlation_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Correlation Runtime - Multi-source Correlation Analysis")
    print("=" * 60)
    
    runtime = get_correlation_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
