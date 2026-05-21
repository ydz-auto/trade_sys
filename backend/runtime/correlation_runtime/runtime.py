"""
Correlation Runtime - 多数据源相关性分析运行时实现

定时执行多数据源相关性分析

GPU 加速：
- 相关性矩阵计算
- 大规模数据协方差计算
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
    
    enable_gpu: bool = True
    
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
    
    GPU 加速：
    - 相关性矩阵计算
    - 大规模数据协方差计算
    """
    
    def __init__(self, config: CorrelationConfig = None):
        config = config or CorrelationConfig.from_env()
        super().__init__(config)
        self.config: CorrelationConfig = config
        
        self.scheduler = None
        self.results_cache: Dict[str, Dict] = {}
        
        self._gpu_available = False
        self._gpu_correlation_engine = None
    
    async def initialize(self) -> None:
        """初始化"""
        self.logger.info("Initializing Correlation Runtime...")
        
        from services.data_service.pipeline.scheduler import get_scheduler, TaskPriority
        self.scheduler = get_scheduler()
        
        if self.config.enable_gpu:
            await self._init_gpu()
        
        self._register_tasks()
        
        self.logger.info("Correlation Runtime initialized successfully")
    
    async def _init_gpu(self):
        """初始化 GPU 加速"""
        try:
            from shared.acceleration import is_gpu_available, get_accelerator_info
            
            info = get_accelerator_info()
            self._gpu_available = info['is_gpu']
            
            self.logger.info(f"GPU acceleration: {info['device_type']}, is_gpu={self._gpu_available}")
            
            if self._gpu_available:
                self._gpu_correlation_engine = self._create_gpu_correlation_engine()
                self.logger.info("GPU correlation engine initialized")
            
        except ImportError as e:
            self.logger.warning(f"GPU acceleration not available: {e}")
            self._gpu_available = False
        except Exception as e:
            self.logger.warning(f"GPU initialization failed: {e}")
            self._gpu_available = False
    
    def _create_gpu_correlation_engine(self):
        """创建 GPU 相关性计算引擎"""
        from shared.acceleration import torch, device
        
        class GPUCorrelationEngine:
            def __init__(self):
                self.torch = torch
                self.device = device
            
            def compute_correlation_matrix(self, data):
                """
                计算相关性矩阵
                
                Args:
                    data: (N, M) 的数据矩阵，N 是时间点，M 是变量
                
                Returns:
                    (M, M) 的相关性矩阵
                """
                if not isinstance(data, self.torch.Tensor):
                    data = self.torch.tensor(data, dtype=self.torch.float32, device=self.device)
                
                data_centered = data - data.mean(dim=0, keepdim=True)
                
                cov = self.torch.mm(data_centered.T, data_centered) / (data.shape[0] - 1)
                
                std = self.torch.sqrt(self.torch.diag(cov))
                corr = cov / (self.torch.outer(std, std) + 1e-8)
                
                return corr.cpu().numpy()
            
            def compute_rolling_correlation(self, data, window=100):
                """
                计算滚动相关性
                
                Args:
                    data: (N, 2) 的数据矩阵
                    window: 滚动窗口大小
                
                Returns:
                    (N - window + 1,) 的相关性序列
                """
                if not isinstance(data, self.torch.Tensor):
                    data = self.torch.tensor(data, dtype=self.torch.float32, device=self.device)
                
                n = data.shape[0]
                correlations = []
                
                for i in range(window, n + 1):
                    window_data = data[i - window:i]
                    corr = self.torch.corrcoef(window_data.T)
                    correlations.append(corr[0, 1].item())
                
                return correlations
        
        return GPUCorrelationEngine()
    
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
        """执行单次分析 - 支持 GPU 加速"""
        start_time = datetime.now()
        self.logger.info(f"Starting analysis: {symbol} {timeframe} (GPU={self._gpu_available})")
        
        try:
            if self._gpu_available and self._gpu_correlation_engine:
                result = await self._run_analysis_gpu(symbol, timeframe, news_data)
            else:
                from research.correlation import analyze_correlation
                
                result = await analyze_correlation(
                    symbol=symbol,
                    timeframe=timeframe,
                    output_dir=str(Path(self.config.output_dir) / f"{symbol}_{timeframe}"),
                    generate_visualization=True,
                )
                result = result.to_dict()
            
            cache_key = f"{symbol}:{timeframe}"
            self.results_cache[cache_key] = result
            
            self.context.increment_stat("analyses_completed")
            
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.info(
                f"Analysis completed: {symbol} {timeframe} in {duration:.1f}s (GPU={self._gpu_available})"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Analysis failed: {symbol} {timeframe} - {e}")
            self.context.record_error(str(e))
            return {"error": str(e), "symbol": symbol, "timeframe": timeframe}
    
    async def _run_analysis_gpu(
        self,
        symbol: str,
        timeframe: str,
        news_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """使用 GPU 加速分析"""
        try:
            import pandas as pd
            import numpy as np
            from pathlib import Path
            
            data_dir = Path(self.config.output_dir).parent.parent / "data_lake" / "features" / "binance" / f"{symbol}USDT"
            
            if not data_dir.exists():
                self.logger.warning(f"Data directory not found: {data_dir}")
                return {"error": "Data not found", "symbol": symbol, "timeframe": timeframe}
            
            feature_files = list(data_dir.glob("*.parquet"))
            if not feature_files:
                return {"error": "No feature files", "symbol": symbol, "timeframe": timeframe}
            
            df = pd.read_parquet(feature_files[0])
            
            feature_cols = [c for c in df.columns if c not in ['timestamp', 'open_time', 'open', 'high', 'low', 'close', 'volume']]
            
            if len(feature_cols) < 2:
                return {"error": "Not enough features", "symbol": symbol, "timeframe": timeframe}
            
            feature_matrix = df[feature_cols].values
            
            corr_matrix = self._gpu_correlation_engine.compute_correlation_matrix(feature_matrix)
            
            output_dir = Path(self.config.output_dir) / f"{symbol}_{timeframe}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            corr_df = pd.DataFrame(corr_matrix, index=feature_cols, columns=feature_cols)
            corr_df.to_csv(output_dir / "correlation_matrix.csv")
            
            strong_correlations = []
            for i in range(len(feature_cols)):
                for j in range(i + 1, len(feature_cols)):
                    if abs(corr_matrix[i, j]) > 0.7:
                        strong_correlations.append({
                            "feature_1": feature_cols[i],
                            "feature_2": feature_cols[j],
                            "correlation": float(corr_matrix[i, j]),
                        })
            
            self.context.increment_stat("gpu_correlations_computed")
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "correlation_matrix": corr_matrix.tolist(),
                "feature_names": feature_cols,
                "strong_correlations": strong_correlations,
                "gpu_accelerated": True,
                "timestamp": datetime.now().isoformat(),
            }
            
        except Exception as e:
            self.logger.error(f"GPU analysis failed: {e}")
            raise
    
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
            "gpu_acceleration": {
                "available": self._gpu_available,
                "engine_ready": self._gpu_correlation_engine is not None,
            },
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
    print("(GPU Accelerated)")
    print("=" * 60)
    
    runtime = get_correlation_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
