"""
Correlation Service - 多数据源相关性分析定时任务

对接现有 TaskScheduler，定时执行相关性分析。
分析结果存入本地文件 + ClickHouse + 可选推送 Kafka。

.. deprecated::
    本模块已由 correlation_runtime 取代。
    CorrelationWorker 现在委托给 CorrelationRuntime 执行分析，
    自身仅保留 Kafka 推送和告警等服务层逻辑。

用法:
    python -m services.correlation_service
"""

import asyncio
import json
import sys
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger

logger = get_logger("correlation_service")

from infrastructure.config import get_config_manager

warnings.warn(
    "CorrelationWorker is superseded by CorrelationRuntime. "
    "Use runtime.correlation_runtime.runtime.get_correlation_runtime() instead.",
    DeprecationWarning,
    stacklevel=2,
)


def _get_config(key: str, default: Any = None) -> Any:
    config_manager = get_config_manager()
    return config_manager.get(key, default)


class CorrelationWorker:

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        interval: Optional[int] = None,
        output_dir: Optional[str] = None,
        kafka_enabled: Optional[bool] = None,
        storage_enabled: Optional[bool] = None,
        correlation_runtime=None,
    ):
        self.symbols = symbols or _get_config("correlation.symbols", ["BTC", "ETH"])
        self.timeframes = timeframes or _get_config("correlation.timeframes", ["1h", "4h"])
        self.interval = interval or _get_config("correlation.interval", 3600)
        self.output_dir = Path(output_dir or _get_config("correlation.output_dir", "./data/correlation_results"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.kafka_enabled = kafka_enabled if kafka_enabled is not None else _get_config("correlation.kafka.enabled", False)
        self.storage_enabled = storage_enabled if storage_enabled is not None else _get_config("correlation.storage.enabled", True)
        self.kafka_topic = _get_config("correlation.kafka.topic", "tradeagent.correlation_results")

        self._broker = None
        self._running = False
        self._runtime = correlation_runtime

        logger.info(
            f"CorrelationWorker initialized: symbols={self.symbols}, "
            f"timeframes={self.timeframes}, interval={self.interval}s, "
            f"kafka={self.kafka_enabled}, storage={self.storage_enabled}"
        )

    async def initialize(self):
        if self._runtime is None:
            from runtime.correlation_runtime.runtime import get_correlation_runtime
            self._runtime = get_correlation_runtime()
        if self._runtime.state.value == "uninitialized":
            await self._runtime.initialize()

        if self.kafka_enabled:
            try:
                from infrastructure.messaging import get_broker
                from infrastructure.config.defaults.infrastructure.middleware import KAFKA_BOOTSTRAP_SERVERS
                kafka_bootstrap = _get_config("kafka.bootstrap_servers", KAFKA_BOOTSTRAP_SERVERS)
                self._broker = get_broker(kafka_bootstrap)
                logger.info("Kafka broker connected for correlation results")
            except Exception as e:
                logger.warning(f"Failed to connect Kafka, disabling: {e}")
                self.kafka_enabled = False

        logger.info("CorrelationWorker initialized successfully (delegating to CorrelationRuntime)")

    async def run_analysis(
        self,
        symbol: str,
        timeframe: str,
        news_data: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        start_time = datetime.now()
        logger.info(f"Starting analysis: {symbol} {timeframe}")

        try:
            result_dict = await self._runtime.run_analysis(symbol, timeframe, news_data)

            if "error" in result_dict:
                return result_dict

            if self.kafka_enabled and self._broker:
                await self._publish_to_kafka(result_dict, symbol, timeframe)

            await self._check_alerts(result_dict, symbol, timeframe)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Analysis completed: {symbol} {timeframe} "
                f"in {duration:.1f}s"
            )

            return result_dict

        except Exception as e:
            logger.error(f"Analysis failed: {symbol} {timeframe} - {e}")
            return {"error": str(e), "symbol": symbol, "timeframe": timeframe}

    async def _publish_to_kafka(
        self,
        result_dict: Dict[str, Any],
        symbol: str,
        timeframe: str,
    ):
        try:
            message = {
                "type": "correlation_result",
                "symbol": symbol,
                "timeframe": timeframe,
                "timestamp": datetime.now().isoformat(),
                "data": result_dict,
            }

            await self._broker.publish(
                message=message,
                topic=self.kafka_topic,
                key=f"{symbol}_{timeframe}",
            )
            logger.debug(f"Published correlation result to Kafka: {symbol} {timeframe}")

        except Exception as e:
            logger.warning(f"Failed to publish to Kafka: {e}")

    async def _check_alerts(self, result_dict: Dict[str, Any], symbol: str, timeframe: str):
        signal_assessments = result_dict.get("signal_assessments", {})
        if not signal_assessments:
            return

        strong_signals = []
        for name, assessment in signal_assessments.items():
            if isinstance(assessment, dict):
                confidence = assessment.get("confidence", 0)
                direction = assessment.get("direction", "neutral")
            else:
                confidence = getattr(assessment, "confidence", 0)
                direction = getattr(getattr(assessment, "direction", None), "value", "neutral")

            if confidence > 0.8 and direction != "neutral":
                strong_signals.append((name, confidence, direction))

        if not strong_signals:
            return

        alert_msg = (
            f"🔔 Correlation Alert [{symbol} {timeframe}]: "
            f"{len(strong_signals)} strong signals detected\n"
        )
        for name, confidence, direction in strong_signals[:5]:
            alert_msg += f"  • {name}: {direction} (confidence={confidence:.3f})\n"

        logger.info(alert_msg.strip())

    def get_latest_result(self, symbol: str, timeframe: str) -> Optional[Dict]:
        if self._runtime:
            return self._runtime.get_latest_result(symbol, timeframe)
        return None

    def get_all_latest_results(self) -> Dict[str, Dict]:
        if self._runtime:
            return self._runtime.get_all_latest_results()
        return {}

    async def run_once(self):
        for symbol in self.symbols:
            for tf in self.timeframes:
                await self.run_analysis(symbol, tf)

    async def start(self):
        self._running = True
        await self.initialize()
        await self._runtime.start()
        logger.info("CorrelationWorker started (via CorrelationRuntime)")

    async def stop(self):
        self._running = False
        if self._runtime:
            await self._runtime.stop()
        logger.info("CorrelationWorker stopped")


_worker: Optional[CorrelationWorker] = None


async def get_correlation_service() -> CorrelationWorker:
    global _worker
    if _worker is None:
        _worker = CorrelationWorker()
        await _worker.initialize()
    return _worker


async def main():
    print("=" * 60)
    print("Correlation Worker - 多数据源相关性分析")
    print("(Delegating to CorrelationRuntime)")
    print("=" * 60)

    worker = CorrelationWorker()

    print(f"Symbols: {worker.symbols}")
    print(f"Timeframes: {worker.timeframes}")
    print(f"Interval: {worker.interval}s")
    print(f"Output: {worker.output_dir}")
    print(f"Kafka: {'enabled' if worker.kafka_enabled else 'disabled'}")
    print(f"Storage: {'enabled' if worker.storage_enabled else 'disabled'}")
    print("=" * 60)

    print("\n[correlation_service] Running initial analysis...")
    await worker.run_once()

    print(f"\n[correlation_service] Starting via CorrelationRuntime (interval={worker.interval}s)...")
    await worker.start()

    try:
        while worker._running:
            await asyncio.sleep(10)
            results = worker.get_all_latest_results()
            for cache_key, result in results.items():
                symbol, tf = cache_key.split(":")
                print(
                    f"[correlation_service] {symbol} {tf}: "
                    f"gpu={result.get('gpu_accelerated', False)}"
                )
    except KeyboardInterrupt:
        print("\n[correlation_service] Received shutdown signal")
    finally:
        await worker.stop()
        print("[correlation_service] Stopped")


if __name__ == "__main__":
    asyncio.run(main())
