"""
OrderBook Aggregator - 订单簿聚合器
从订单簿快照提取特征
"""

from typing import Dict, Optional
from datetime import datetime

from infrastructure.logging import get_logger
from ..models.orderbook_model import OrderBookSnapshot, OrderBookFeature

logger = get_logger("aggregation_service.orderbook_aggregator")


class OrderBookAggregator:
    """订单簿聚合器

    从订单簿快照提取特征：
    - Spread
    - Mid Price
    - Imbalance
    - 买卖盘量
    """

    def __init__(self):
        self.last_snapshot: Dict[str, OrderBookSnapshot] = {}

    def process_snapshot(self, snapshot: OrderBookSnapshot) -> OrderBookFeature:
        """处理订单簿快照，返回特征"""
        key = f"{snapshot.exchange}:{snapshot.symbol}"
        self.last_snapshot[key] = snapshot

        feature = OrderBookFeature.from_snapshot(snapshot)
        return feature

    def get_last_feature(self, exchange: str, symbol: str) -> Optional[OrderBookFeature]:
        """获取最新的订单簿特征"""
        key = f"{exchange}:{symbol}"
        snapshot = self.last_snapshot.get(key)
        if snapshot:
            return OrderBookFeature.from_snapshot(snapshot)
        return None


_aggregator: Optional[OrderBookAggregator] = None


def get_orderbook_aggregator() -> OrderBookAggregator:
    """获取全局订单簿聚合器"""
    global _aggregator
    if _aggregator is None:
        _aggregator = OrderBookAggregator()
    return _aggregator
