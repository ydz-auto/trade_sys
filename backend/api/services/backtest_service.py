"""
Backtest Manager Service - 回测管理服务

职责边界（Service 层）：
- backtest 任务状态持久化（Redis，只存储元数据）
- start/stop/query 转发

禁止在 Service 层维护：
- 回测执行逻辑
- replay loop
- position/session state
- equity curve 计算

执行流程：
    API Router
      ↓
    RuntimeBus.publish_command(run_backtest)
      ↓
    BacktestManager.start(id)  ← 启动
      ↓
    ReplayRuntime (唯一 execution source)
      ↓
    BacktestManager.query(id)  ← 查询结果
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4

from application.queries.infrastructure_queries import get_redis_client_sync, init_redis
from domain.logging import get_logger

logger = get_logger("backtest_manager")

_BACKTEST_KEY_PREFIX = "backtest:"
_BACKTEST_LIST_KEY = "backtest:list"


class BacktestManager:

    def __init__(self):
        self._redis = None

    async def ensure_connection(self):
        if self._redis is None:
            self._redis = await init_redis()
        elif hasattr(self._redis, 'is_connected') and not self._redis.is_connected:
            self._redis = await init_redis()

    @property
    def redis(self):
        if self._redis is None:
            raise RuntimeError("Redis not connected")
        return self._redis

    async def start(self, backtest_id: str, config: Dict) -> Dict:
        """启动回测 - 写入 Redis，委托 ReplayRuntime 执行"""
        await self.redis.set_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}", {
            "id": backtest_id,
            "status": "running",
            "config": config,
            "metrics": None,
            "trades": [],
            "equity_curve": [],
            "drawdown_curve": [],
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "error_message": None,
        })
        logger.info(f"Backtest started: {backtest_id}")
        return await self.redis.get_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}")

    async def stop(self, backtest_id: str) -> Dict:
        """停止回测"""
        backtest = await self.redis.get_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}")
        if not backtest:
            return {"success": False, "error": "Not found"}

        backtest["status"] = "stopped"
        backtest["completed_at"] = datetime.now().isoformat()
        await self.redis.set_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}", backtest)
        logger.info(f"Backtest stopped: {backtest_id}")
        return {"success": True, "backtest_id": backtest_id}

    async def query(self, backtest_id: str) -> Optional[Dict]:
        """查询回测状态 - 从 Redis 读取"""
        return await self.redis.get_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}")

    async def list(self) -> List[Dict]:
        """列出所有回测"""
        keys = await self.redis.client.keys(f"{_BACKTEST_KEY_PREFIX}*")
        results = []
        for key in keys:
            if key.endswith(":list"):
                continue
            data = await self.redis.get_json(key)
            if data:
                results.append(data)
        return sorted(results, key=lambda x: x.get("created_at", ""), reverse=True)

    async def update_result(self, backtest_id: str, result: Dict) -> None:
        """更新回测结果（由 ReplayRuntime 回调）"""
        await self.redis.set_json(f"{_BACKTEST_KEY_PREFIX}{backtest_id}", result)


_backtest_manager: Optional[BacktestManager] = None


def get_backtest_manager() -> BacktestManager:
    global _backtest_manager
    if _backtest_manager is None:
        _backtest_manager = BacktestManager()
    return _backtest_manager
