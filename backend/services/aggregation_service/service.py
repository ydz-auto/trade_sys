"""
Aggregation Service - K线聚合服务

业务逻辑：K线、成交、订单簿聚合
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

from infrastructure.logging import get_logger
from shared.config import get_datasource_config_manager
from shared.state import get_system_state_manager

from .aggregators.candle.candle_aggregator import get_timeframe_aggregator
from .aggregators.trade.trade_aggregator import get_trade_aggregator
from .aggregators.orderbook.orderbook_aggregator import get_orderbook_aggregator
from .state.state_manager import get_window_state_manager
from .models.candle_model import Candle, Timeframe
from .models.trade_model import Trade
from .models.orderbook_model import OrderBookSnapshot

logger = get_logger("aggregation_service")


class AggregationService:
    """聚合服务 - 纯业务逻辑"""

    def __init__(self):
        self.timeframe_aggregator = get_timeframe_aggregator()
        self.trade_aggregator = get_trade_aggregator()
        self.orderbook_aggregator = get_orderbook_aggregator()
        self.state_manager = get_window_state_manager()

        self._stats = {
            "candles_processed": 0,
            "candles_aggregated": 0,
            "trades_processed": 0,
            "trades_aggregated": 0,
            "orderbooks_processed": 0,
            "errors": 0,
        }

    async def aggregate_candle(self, candle: Candle, timeframe: Timeframe) -> Optional[Candle]:
        """聚合K线"""
        try:
            result = await self.timeframe_aggregator.aggregate(candle, timeframe)
            self._stats["candles_processed"] += 1
            if result:
                self._stats["candles_aggregated"] += 1
            return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error aggregating candle: {e}")
            return None

    async def aggregate_trade(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """聚合成交"""
        try:
            result = await self.trade_aggregator.aggregate(trade)
            self._stats["trades_processed"] += 1
            if result:
                self._stats["trades_aggregated"] += 1
            return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error aggregating trade: {e}")
            return None

    async def aggregate_orderbook(self, orderbook: OrderBookSnapshot) -> Optional[Dict[str, Any]]:
        """聚合订单簿"""
        try:
            result = await self.orderbook_aggregator.aggregate(orderbook)
            self._stats["orderbooks_processed"] += 1
            return result
        except Exception as e:
            self._stats["errors"] += 1
            logger.error(f"Error aggregating orderbook: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "timestamp": datetime.utcnow().isoformat(),
        }


def get_aggregation_service() -> AggregationService:
    """获取聚合服务实例"""
    return AggregationService()
