"""
State Management - 状态管理
负责聚合窗口状态和 checkpoint 管理
"""

from typing import Dict, Optional, Tuple
import json
import time

from infrastructure.logging import get_logger
from infrastructure.cache import RedisClient
from services.aggregation_service.models.candle_model import CandleWindow, Timeframe

logger = get_logger("aggregation_service.state")


class WindowStateManager:
    """内存窗口状态管理器"""

    def __init__(self):
        self.windows: Dict[Tuple[str, str, str], CandleWindow] = {}

    def get_window(
        self,
        exchange: str,
        symbol: str,
        timeframe: str
    ) -> CandleWindow:
        """获取或创建窗口"""
        key = (exchange, symbol, timeframe)
        if key not in self.windows:
            self.windows[key] = CandleWindow(
                exchange=exchange,
                symbol=symbol,
                timeframe=Timeframe(timeframe),
                bucket=0,
            )
        return self.windows[key]

    def close_window(
        self,
        exchange: str,
        symbol: str,
        timeframe: str
    ) -> Optional[CandleWindow]:
        """关闭窗口"""
        key = (exchange, symbol, timeframe)
        window = self.windows.get(key)
        if window and window.bucket > 0:
            return window
        return None

    def reset_window(
        self,
        exchange: str,
        symbol: str,
        timeframe: str
    ):
        """重置窗口"""
        key = (exchange, symbol, timeframe)
        window = self.windows.get(key)
        if window:
            window.reset()

    def get_all_windows(self) -> Dict[Tuple[str, str, str], CandleWindow]:
        """获取所有窗口"""
        return self.windows.copy()

    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "windows": {
                f"{k[0]}:{k[1]}:{k[2]}": {
                    "bucket": v.bucket,
                    "open": v.open,
                    "high": v.high,
                    "low": v.low,
                    "close": v.close,
                    "volume": v.volume,
                    "trade_count": v.trade_count,
                }
                for k, v in self.windows.items()
                if v.bucket > 0
            },
            "timestamp": int(time.time())
        }


class RedisCheckpointManager:
    """Redis Checkpoint 管理器

    用于 crash recovery 和 restart recovery
    """

    KEY_PREFIX = "agg:checkpoint"

    def __init__(self):
        self.redis: Optional[RedisClient] = None

    async def initialize(self):
        """初始化"""
        try:
            self.redis = RedisClient()
        except Exception as e:
            logger.warning(f"Redis not available: {e}")

    def _make_key(self, exchange: str, symbol: str, timeframe: str) -> str:
        """生成 key"""
        return f"{self.KEY_PREFIX}:{exchange}:{symbol}:{timeframe}"

    async def save_checkpoint(
        self,
        exchange: str,
        symbol: str,
        timeframe: str,
        bucket: int,
        window_state: Dict
    ):
        """保存 checkpoint"""
        if not self.redis:
            return

        key = self._make_key(exchange, symbol, timeframe)
        try:
            await self.redis.set(
                key,
                json.dumps({
                    "bucket": bucket,
                    "state": window_state,
                    "timestamp": int(time.time())
                }),
                ex=86400
            )
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    async def load_checkpoint(
        self,
        exchange: str,
        symbol: str,
        timeframe: str
    ) -> Optional[Dict]:
        """加载 checkpoint"""
        if not self.redis:
            return None

        key = self._make_key(exchange, symbol, timeframe)
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
        return None

    async def delete_checkpoint(
        self,
        exchange: str,
        symbol: str,
        timeframe: str
    ):
        """删除 checkpoint"""
        if not self.redis:
            return

        key = self._make_key(exchange, symbol, timeframe)
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")

    async def get_all_checkpoints(self) -> Dict[str, Dict]:
        """获取所有 checkpoint"""
        if not self.redis:
            return {}

        try:
            keys = await self.redis.keys(f"{self.KEY_PREFIX}:*")
            result = {}
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    result[key] = json.loads(data)
            return result
        except Exception as e:
            logger.error(f"Failed to get checkpoints: {e}")
            return {}


_state_manager: Optional[WindowStateManager] = None
_checkpoint_manager: Optional[RedisCheckpointManager] = None


def get_window_state_manager() -> WindowStateManager:
    """获取窗口状态管理器"""
    global _state_manager
    if _state_manager is None:
        _state_manager = WindowStateManager()
    return _state_manager


async def get_checkpoint_manager() -> RedisCheckpointManager:
    """获取 checkpoint 管理器"""
    global _checkpoint_manager
    if _checkpoint_manager is None:
        _checkpoint_manager = RedisCheckpointManager()
        await _checkpoint_manager.initialize()
    return _checkpoint_manager
