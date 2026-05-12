"""
Repair Service - 数据修复服务
主入口
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from infrastructure.logging import get_logger
logger = get_logger("repair_service.main")

from shared.config import get_datasource_config_manager
from shared.state import get_system_state_manager

from .schedulers.repair_scheduler import get_repair_scheduler, RepairScheduler
from .detectors.gap_detector import get_gap_detector, GapDetector
from .models.repair_models import Timeframe

SERVICE_NAME = "repair_service"


class RepairService:
    """修复服务"""

    def __init__(self):
        self.scheduler: Optional[RepairScheduler] = None
        self.detector: Optional[GapDetector] = None

        self._running = False
        self._stats = {
            "gaps_detected": 0,
            "gaps_repaired": 0,
            "tasks_completed": 0,
            "tasks_failed": 0
        }

    async def initialize(self) -> None:
        """初始化"""
        logger.info("Initializing Repair Service...")

        self.scheduler = await get_repair_scheduler()
        self.detector = await get_gap_detector()

        self._running = True
        logger.info("Repair Service initialized successfully")

    async def shutdown(self) -> None:
        """关闭"""
        logger.info("Shutting down Repair Service...")

        if self.scheduler:
            await self.scheduler.shutdown()

        self._running = False
        logger.info(f"Repair Service stopped. Stats: {self._stats}")

    async def scan_symbol(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        days: int = 30
    ) -> Dict:
        """扫描单个交易对"""
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        gaps = await self.detector.detect_gaps(
            exchange, symbol, Timeframe(timeframe), start_time, end_time
        )

        self._stats["gaps_detected"] += len(gaps)

        for gap in gaps:
            await self.scheduler.add_gap(gap)

        return {
            "exchange": exchange,
            "symbol": symbol,
            "timeframe": timeframe,
            "gaps_found": len(gaps),
            "gaps": [g.to_dict() for g in gaps]
        }

    async def scan_all_symbols(
        self,
        exchange: str,
        symbols: list,
        timeframes: list,
        days: int = 7
    ) -> Dict:
        """扫描所有交易对"""
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        results = {}
        total_gaps = 0

        for symbol in symbols:
            for tf in timeframes:
                gaps = await self.detector.detect_gaps(
                    exchange, symbol, Timeframe(tf), start_time, end_time
                )
                if gaps:
                    total_gaps += len(gaps)
                    results[f"{symbol}:{tf}"] = gaps

                    for gap in gaps:
                        await self.scheduler.add_gap(gap)

        self._stats["gaps_detected"] += total_gaps

        return {
            "total_gaps": total_gaps,
            "results": {k: [g.to_dict() for g in v] for k, v in results.items()}
        }

    async def run_repair(self):
        """运行修复"""
        if self.scheduler:
            await self.scheduler.run()

    @property
    def stats(self) -> Dict[str, Any]:
        scheduler_stats = self.scheduler.stats if self.scheduler else {}
        return {
            "running": self._running,
            **self._stats,
            "scheduler": scheduler_stats
        }


_service: Optional[RepairService] = None


async def get_repair_service() -> RepairService:
    """获取修复服务"""
    global _service
    if _service is None:
        _service = RepairService()
        await _service.initialize()
    return _service


async def main():
    service = await get_repair_service()

    try:
        state_manager = get_system_state_manager()
        await state_manager.update({"status": "RUNNING"})
        logger.info("Repair Service is running. Press Ctrl+C to stop.")

        symbols = ["BTCUSDT", "ETHUSDT"]
        timeframes = ["1m", "5m", "15m"]

        await service.scan_all_symbols("binance", symbols, timeframes)

        asyncio.create_task(service.run_repair())

        while service._running:
            await asyncio.sleep(60)
            logger.info(f"Stats: {service.stats}")

    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await service.shutdown()
        await state_manager.update({"status": "STOPPED"})


if __name__ == "__main__":
    asyncio.run(main())
