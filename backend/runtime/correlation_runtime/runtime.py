"""
Correlation Runtime - 多数据源相关性分析运行时实现

职责边界（Runtime 层）：
- 时间因果一致性保证
- 相关性分析结果（state）
- GPU 加速计算
- 定时调度

禁止在 Runtime 层维护：
- results_cache（下沉到 runtime_bus）
- pd.read_parquet 直接访问（下沉到 runtime_bus）

状态管理：
- 相关性结果写入 runtime_bus state
- 不在 Runtime 内部维护 cache
"""
import asyncio
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig
from infrastructure.logging import get_logger
from infrastructure.runtime_clock import get_clock, ClockMode, now_ms
from infrastructure.feature_availability import get_systematic_guard
from infrastructure.label_isolation import get_label_store
from infrastructure.storage.immutable_snapshot import get_immutable_snapshot_store


class CorrelationConfig(RuntimeConfig):
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

    def __init__(self, config: CorrelationConfig = None):
        config = config or CorrelationConfig.from_env()
        super().__init__(config)
        self.config: CorrelationConfig = config

        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._snapshot_store = None

        self.scheduler = None
        self._gpu_available = False
        self._gpu_correlation_engine = None

        self._state: Dict[str, Any] = {}
        self._feature_data: Dict[str, Any] = {}

    async def initialize(self) -> None:
        self.logger.info("Initializing Correlation Runtime...")

        self._snapshot_store = get_immutable_snapshot_store("correlation")

        try:
            from services.data_service.pipeline.scheduler import get_scheduler
            self.scheduler = get_scheduler()
        except ImportError:
            self.logger.warning("Scheduler not available")
            self.scheduler = None

        if self.config.enable_gpu:
            await self._init_gpu()

        self._register_tasks()

        self.logger.info("Correlation Runtime initialized")

    async def _init_gpu(self):
        try:
            from infrastructure.acceleration import is_gpu_available, get_accelerator_info
            info = get_accelerator_info()
            self._gpu_available = info['is_gpu']
            if self._gpu_available:
                self._gpu_correlation_engine = self._create_gpu_correlation_engine()
                self.logger.info(f"GPU enabled: {info['device_type']}")
        except ImportError:
            self._gpu_available = False
        except Exception as e:
            self._gpu_available = False
            self.logger.warning(f"GPU init failed: {e}")

    def _create_gpu_correlation_engine(self):
        from infrastructure.acceleration import torch, device

        class GPUCorrelationEngine:
            def __init__(self):
                self.torch = torch
                self.device = device

            def compute_correlation_matrix(self, data):
                if not isinstance(data, self.torch.Tensor):
                    data = self.torch.tensor(data, dtype=self.torch.float32, device=self.device)
                data_centered = data - data.mean(dim=0, keepdim=True)
                cov = self.torch.mm(data_centered.T, data_centered) / (data.shape[0] - 1)
                std = self.torch.sqrt(self.torch.diag(cov))
                corr = cov / (self.torch.outer(std, std) + 1e-8)
                return corr.cpu().numpy()

        return GPUCorrelationEngine()

    async def shutdown(self) -> None:
        self.logger.info("Shutting down Correlation Runtime...")
        if self.scheduler:
            await self.scheduler.stop()

    def _register_tasks(self):
        if not self.scheduler:
            return
        try:
            from services.data_service.pipeline.scheduler import TaskPriority
            for symbol in self.config.symbols:
                for tf in self.config.timeframes:
                    task_id = f"correlation_{symbol}_{tf}"
                    self.scheduler.register_task(
                        task_id=task_id,
                        name=f"Correlation [{symbol} {tf}]",
                        callback=self._make_callback(symbol, tf),
                        interval=self.config.interval,
                        priority=TaskPriority.NORMAL,
                        timeout=300.0,
                        metadata={"symbol": symbol, "timeframe": tf},
                    )
        except Exception as e:
            self.logger.warning(f"Task registration failed: {e}")

    def _make_callback(self, symbol: str, timeframe: str):
        async def callback():
            return await self.run_analysis(symbol, timeframe)
        return callback

    async def run_analysis(
        self,
        symbol: str,
        timeframe: str,
        news_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        current_time = self._clock.now()

        if self._availability_guard:
            self._availability_guard.check_data_availability(
                symbol=symbol,
                query_time=current_time,
                data_type="correlation"
            )

        if self._label_store:
            self._label_store.ensure_isolation("correlation_analysis")

        if self._gpu_available and self._gpu_correlation_engine:
            result = await self._run_analysis_gpu(symbol, timeframe, news_data)
        else:
            result = await self._run_analysis_cpu(symbol, timeframe)

        if self._snapshot_store:
            result["snapshot_timestamp"] = current_time.isoformat()
            result["clock_mode"] = self._clock.mode.value
            self._snapshot_store.save(result, timestamp=current_time)

        self._publish_to_runtime_bus(symbol, timeframe, result)

        self.context.increment_stat("analyses_completed")
        return result

    def _publish_to_runtime_bus(self, symbol: str, timeframe: str, result: Dict) -> None:
        self._state.update({
            f"{symbol}:{timeframe}": result,
            "last_update": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
        })
        from runtime.bus.runtime_bus import get_runtime_bus
        try:
            bus = get_runtime_bus()
            bus.publish_state_update("correlation", {
                f"{symbol}:{timeframe}": result,
                "last_update": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
            })
        except Exception as e:
            self.logger.debug(f"Could not publish to runtime_bus: {e}")

    async def _run_analysis_gpu(
        self,
        symbol: str,
        timeframe: str,
        news_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        from runtime.replay_runtime.shared_replay.market_event_emitter import MarketEventEmitter, EmitterConfig, EmitMode

        feature_data = self._feature_data.get(symbol)

        if not feature_data:
            emitter = MarketEventEmitter(EmitterConfig(
                emit_mode=EmitMode.BATCH,
                include_trades=False,
            ))
            async for event in emitter.emit_from_feature_parquet(
                parquet_path=Path(self.config.output_dir).parent.parent / "data_lake" / "features" / "binance" / f"{symbol}USDT" / "features.parquet",
                symbol=symbol,
                exchange="binance",
                start_time=None,
                end_time=None,
            ):
                if event.event_type == "features":
                    feature_data = event.data
                    break

        if not feature_data or "feature_matrix" not in feature_data:
            return await self._run_analysis_cpu(symbol, timeframe)

        feature_matrix = feature_data["feature_matrix"]
        corr_matrix = self._gpu_correlation_engine.compute_correlation_matrix(feature_matrix)

        feature_names = feature_data.get("feature_names", [f"f{i}" for i in range(corr_matrix.shape[0])])

        strong_correlations = []
        for i in range(len(feature_names)):
            for j in range(i + 1, len(feature_names)):
                if abs(corr_matrix[i, j]) > 0.7:
                    strong_correlations.append({
                        "feature_1": feature_names[i],
                        "feature_2": feature_names[j],
                        "correlation": float(corr_matrix[i, j]),
                    })

        self.context.increment_stat("gpu_correlations_computed")

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "correlation_matrix": corr_matrix.tolist(),
            "feature_names": feature_names,
            "strong_correlations": strong_correlations,
            "gpu_accelerated": True,
            "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
        }

    async def _run_analysis_cpu(
        self,
        symbol: str,
        timeframe: str,
    ) -> Dict[str, Any]:
        feature_data = self._feature_data.get(symbol)

        if not feature_data:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "error": "Feature data not available via runtime_bus",
                "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
            }

        feature_matrix = feature_data.get("feature_matrix", [])
        feature_names = feature_data.get("feature_names", [])

        if len(feature_matrix) < 2:
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "correlation_matrix": [],
                "feature_names": feature_names,
                "strong_correlations": [],
                "gpu_accelerated": False,
                "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
            }

        import numpy as np
        corr_matrix = np.corrcoef(feature_matrix.T)

        strong_correlations = []
        for i in range(len(feature_names)):
            for j in range(i + 1, len(feature_names)):
                if abs(corr_matrix[i, j]) > 0.7:
                    strong_correlations.append({
                        "feature_1": feature_names[i],
                        "feature_2": feature_names[j],
                        "correlation": float(corr_matrix[i, j]),
                    })

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "correlation_matrix": corr_matrix.tolist(),
            "feature_names": feature_names,
            "strong_correlations": strong_correlations,
            "gpu_accelerated": False,
            "timestamp": datetime.fromtimestamp(now_ms() / 1000).isoformat(),
        }

    async def run(self) -> None:
        self.logger.info("Starting Correlation Runtime...")
        if self.scheduler:
            await self.scheduler.start()
            while not self.context.is_shutdown_requested():
                await asyncio.sleep(10)

    def get_state(self) -> Dict[str, Any]:
        return self._state

    def get_latest_result(self, symbol: str, timeframe: str) -> Optional[Dict]:
        try:
            return self._state.get(f"{symbol}:{timeframe}")
        except Exception:
            return None

    async def health_check(self) -> Dict[str, Any]:
        health = await super().health_check()
        health.update({
            "scheduler_running": self.scheduler is not None,
            "gpu_acceleration": {
                "available": self._gpu_available,
                "engine_ready": self._gpu_correlation_engine is not None,
            },
        })
        return health


_correlation_runtime: Optional[CorrelationRuntime] = None


def get_correlation_runtime() -> CorrelationRuntime:
    global _correlation_runtime
    if _correlation_runtime is None:
        _correlation_runtime = CorrelationRuntime()
    return _correlation_runtime


async def main():
    print("=" * 60)
    print("Correlation Runtime - Multi-source Correlation Analysis")
    print("=" * 60)
    runtime = get_correlation_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
