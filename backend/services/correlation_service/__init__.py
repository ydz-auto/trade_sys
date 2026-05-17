"""
Correlation Service - 多数据源相关性分析定时任务

对接现有 TaskScheduler，定时执行相关性分析。
分析结果存入本地文件 + 可选推送 Kafka。

用法:
    python -m services.correlation_service
"""

import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger

logger = get_logger("correlation_service")

from services.data_service.pipeline.scheduler import (
    TaskScheduler,
    TaskPriority,
    get_scheduler,
)


# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────

DEFAULT_SYMBOLS = os.environ.get("CORRELATION_SYMBOLS", "BTC,ETH").split(",")
DEFAULT_TIMEFRAMES = os.environ.get("CORRELATION_TIMEFRAMES", "1h,4h").split(",")
DEFAULT_INTERVAL = int(os.environ.get("CORRELATION_INTERVAL", "3600"))  # 默认1小时
OUTPUT_DIR = os.environ.get("CORRELATION_OUTPUT_DIR", "./data/correlation_results")

# Kafka 推送开关
KAFKA_ENABLED = os.environ.get("CORRELATION_KAFKA_ENABLED", "false").lower() == "true"
KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC = os.environ.get("CORRELATION_KAFKA_TOPIC", "tradeagent.correlation_results")


class CorrelationWorker:
    """
    相关性分析 Worker

    功能：
    1. 定时执行多数据源相关性分析
    2. 结果存储（JSON + 可视化）
    3. 可选 Kafka 推送
    4. 强信号告警
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        timeframes: Optional[List[str]] = None,
        interval: int = DEFAULT_INTERVAL,
        output_dir: str = OUTPUT_DIR,
        kafka_enabled: bool = KAFKA_ENABLED,
    ):
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.timeframes = timeframes or DEFAULT_TIMEFRAMES
        self.interval = interval
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.kafka_enabled = kafka_enabled

        self._broker = None
        self._scheduler: Optional[TaskScheduler] = None
        self._running = False
        self._results_cache: Dict[str, Dict] = {}  # symbol:timeframe -> latest result

        logger.info(
            f"CorrelationWorker initialized: symbols={self.symbols}, "
            f"timeframes={self.timeframes}, interval={self.interval}s"
        )

    async def initialize(self):
        """初始化 Worker"""
        from research.correlation import CorrelationAnalyzer, CorrelationConfig

        self._analyzer_cls = CorrelationAnalyzer
        self._config_cls = CorrelationConfig

        # 初始化 Kafka（如果启用）
        if self.kafka_enabled:
            try:
                from infrastructure.messaging import get_broker
                self._broker = get_broker(KAFKA_BOOTSTRAP)
                logger.info("Kafka broker connected for correlation results")
            except Exception as e:
                logger.warning(f"Failed to connect Kafka, disabling: {e}")
                self.kafka_enabled = False

        # 注册到系统调度器
        self._scheduler = get_scheduler()
        self._register_tasks()

        logger.info("CorrelationWorker initialized successfully")

    def _register_tasks(self):
        """注册定时任务到系统调度器"""
        for symbol in self.symbols:
            for tf in self.timeframes:
                task_id = f"correlation_{symbol}_{tf}"
                task_name = f"Correlation Analysis [{symbol} {tf}]"

                self._scheduler.register_task(
                    task_id=task_id,
                    name=task_name,
                    callback=self._make_callback(symbol, tf),
                    interval=self.interval,
                    priority=TaskPriority.NORMAL,
                    timeout=300.0,  # 5分钟超时
                    metadata={"symbol": symbol, "timeframe": tf},
                )

                logger.info(f"Registered task: {task_name} (interval={self.interval}s)")

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
        """
        执行单次分析

        Args:
            symbol: 交易对
            timeframe: 时间周期
            news_data: 可选新闻数据

        Returns:
            分析结果字典
        """
        start_time = datetime.now()
        logger.info(f"Starting analysis: {symbol} {timeframe}")

        try:
            from research.correlation import analyze_correlation

            # 执行分析
            result = await analyze_correlation(
                symbol=symbol,
                timeframe=timeframe,
                output_dir=str(self.output_dir / f"{symbol}_{timeframe}"),
                generate_visualization=True,
            )

            # 保存结果
            result_path = result.save()
            result_dict = result.to_dict()

            # 缓存最新结果
            cache_key = f"{symbol}:{timeframe}"
            self._results_cache[cache_key] = result_dict

            # Kafka 推送
            if self.kafka_enabled and self._broker:
                await self._publish_to_kafka(result_dict, symbol, timeframe)

            # 强信号告警
            await self._check_alerts(result, symbol, timeframe)

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"Analysis completed: {symbol} {timeframe} "
                f"in {duration:.1f}s | "
                f"+{len(result.positive_signals)} -{len(result.negative_signals)} ~{len(result.neutral_signals)}"
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
        """推送结果到 Kafka"""
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
                topic=KAFKA_TOPIC,
                key=f"{symbol}_{timeframe}",
            )
            logger.debug(f"Published correlation result to Kafka: {symbol} {timeframe}")

        except Exception as e:
            logger.warning(f"Failed to publish to Kafka: {e}")

    async def _check_alerts(self, result, symbol: str, timeframe: str):
        """检查强信号并告警"""
        strong_signals = [
            (name, assessment)
            for name, assessment in result.signal_assessments.items()
            if assessment.confidence > 0.8 and assessment.direction.value != "neutral"
        ]

        if not strong_signals:
            return

        alert_msg = (
            f"🔔 Correlation Alert [{symbol} {timeframe}]: "
            f"{len(strong_signals)} strong signals detected\n"
        )
        for name, assessment in strong_signals[:5]:
            alert_msg += (
                f"  • {name}: {assessment.direction.value} "
                f"(confidence={assessment.confidence:.3f}, strength={assessment.strength:.3f})\n"
            )

        logger.info(alert_msg.strip())

    def get_latest_result(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """获取最新分析结果"""
        return self._results_cache.get(f"{symbol}:{timeframe}")

    def get_all_latest_results(self) -> Dict[str, Dict]:
        """获取所有最新结果"""
        return dict(self._results_cache)

    async def run_once(self):
        """手动触发一次全量分析"""
        for symbol in self.symbols:
            for tf in self.timeframes:
                await self.run_analysis(symbol, tf)

    async def start(self):
        """启动 Worker（使用系统调度器）"""
        self._running = True
        await self.initialize()
        await self._scheduler.start()
        logger.info("CorrelationWorker started")

    async def stop(self):
        """停止 Worker"""
        self._running = False
        if self._scheduler:
            await self._scheduler.stop()
        logger.info("CorrelationWorker stopped")


# ──────────────────────────────────────────────
# 全局实例
# ──────────────────────────────────────────────

_worker: Optional[CorrelationWorker] = None


async def get_correlation_service() -> CorrelationWorker:
    """获取 Worker 单例"""
    global _worker
    if _worker is None:
        _worker = CorrelationWorker()
        await _worker.initialize()
    return _worker


# ──────────────────────────────────────────────
# 独立运行入口
# ──────────────────────────────────────────────

async def main():
    """独立运行入口"""
    print("=" * 60)
    print("Correlation Worker - 多数据源相关性分析")
    print("=" * 60)
    print(f"Symbols: {DEFAULT_SYMBOLS}")
    print(f"Timeframes: {DEFAULT_TIMEFRAMES}")
    print(f"Interval: {DEFAULT_INTERVAL}s")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Kafka: {'enabled' if KAFKA_ENABLED else 'disabled'}")
    print("=" * 60)

    worker = CorrelationWorker()

    # 先执行一次
    print("\n[correlation_service] Running initial analysis...")
    await worker.run_once()

    # 启动定时调度
    print(f"\n[correlation_service] Starting scheduler (interval={DEFAULT_INTERVAL}s)...")
    await worker.start()

    try:
        while worker._running:
            await asyncio.sleep(10)
            # 打印状态
            stats = worker._scheduler.get_all_stats()
            for task_id, stat in stats.items():
                if task_id.startswith("correlation_"):
                    print(
                        f"[correlation_service] {stat['name']}: "
                        f"runs={stat['total_runs']} "
                        f"success_rate={stat['success_rate']:.0%} "
                        f"avg={stat['avg_duration_ms']:.0f}ms"
                    )
    except KeyboardInterrupt:
        print("\n[correlation_service] Received shutdown signal")
    finally:
        await worker.stop()
        print("[correlation_service] Stopped")


if __name__ == "__main__":
    asyncio.run(main())
