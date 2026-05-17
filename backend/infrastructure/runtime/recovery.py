"""
Runtime Recovery - 运行时恢复组件

提供运行时状态恢复能力：
- 从快照恢复
- 从事件日志重建
- 状态一致性检查
- 自动故障恢复
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import json

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.runtime.recovery")


class RecoveryState(Enum):
    IDLE = "idle"
    PREPARING = "preparing"
    RECOVERING = "recovering"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class RecoveryCheckpoint:
    """恢复检查点"""
    checkpoint_id: str
    timestamp: int
    runtime_name: str
    state_data: Dict[str, Any]
    event_sequence: int
    checksum: str
    created_at: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "timestamp": self.timestamp,
            "runtime_name": self.runtime_name,
            "state_data": self.state_data,
            "event_sequence": self.event_sequence,
            "checksum": self.checksum,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryCheckpoint":
        return cls(
            checkpoint_id=data["checkpoint_id"],
            timestamp=data["timestamp"],
            runtime_name=data["runtime_name"],
            state_data=data.get("state_data", {}),
            event_sequence=data.get("event_sequence", 0),
            checksum=data.get("checksum", ""),
            created_at=data.get("created_at", 0),
        )


@dataclass
class RecoveryConfig:
    """恢复配置"""
    auto_recovery_enabled: bool = True
    checkpoint_interval_seconds: int = 60
    max_checkpoints: int = 10
    recovery_timeout_seconds: int = 300
    verify_after_recovery: bool = True
    rollback_on_failure: bool = True


class RuntimeRecovery:
    """
    运行时恢复管理器
    
    功能：
    1. 定期创建检查点
    2. 从检查点恢复状态
    3. 从事件日志重建状态
    4. 状态一致性验证
    5. 自动故障恢复
    """
    
    def __init__(self, config: RecoveryConfig = None):
        self.config = config or RecoveryConfig()
        
        self._state = RecoveryState.IDLE
        self._checkpoints: Dict[str, List[RecoveryCheckpoint]] = {}
        self._current_checkpoint: Optional[RecoveryCheckpoint] = None
        
        self._recovery_handlers: Dict[str, Callable] = {}
        self._verification_handlers: Dict[str, Callable] = {}
        
        self._redis = None
        self._event_store = None
        
        self._stats = {
            "checkpoints_created": 0,
            "recoveries_performed": 0,
            "recoveries_failed": 0,
            "last_recovery_time": None,
        }
    
    async def initialize(self) -> None:
        """初始化"""
        try:
            from infrastructure.cache.redis_client import init_redis
            self._redis = await init_redis()
            logger.info("RuntimeRecovery: Redis connected")
        except Exception as e:
            logger.warning(f"RuntimeRecovery: Redis connection failed: {e}")
        
        try:
            from shared.replay.event_store import get_event_store
            self._event_store = await get_event_store()
            logger.info("RuntimeRecovery: Event store connected")
        except Exception as e:
            logger.warning(f"RuntimeRecovery: Event store not available: {e}")
        
        await self._load_checkpoints()
        logger.info("RuntimeRecovery initialized")
    
    async def _load_checkpoints(self) -> None:
        """加载检查点"""
        if not self._redis:
            return
        
        try:
            keys = await self._redis.keys("recovery:checkpoint:*")
            for key in keys:
                data = await self._redis.get(key)
                if data:
                    checkpoint = RecoveryCheckpoint.from_dict(json.loads(data))
                    runtime_name = checkpoint.runtime_name
                    if runtime_name not in self._checkpoints:
                        self._checkpoints[runtime_name] = []
                    self._checkpoints[runtime_name].append(checkpoint)
            
            for runtime_name in self._checkpoints:
                self._checkpoints[runtime_name].sort(key=lambda x: x.timestamp, reverse=True)
            
            logger.info(f"Loaded checkpoints for {len(self._checkpoints)} runtimes")
            
        except Exception as e:
            logger.error(f"Failed to load checkpoints: {e}")
    
    def register_recovery_handler(
        self,
        runtime_name: str,
        handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """注册恢复处理器"""
        self._recovery_handlers[runtime_name] = handler
        logger.info(f"Registered recovery handler for {runtime_name}")
    
    def register_verification_handler(
        self,
        runtime_name: str,
        handler: Callable[[Dict[str, Any]], bool]
    ) -> None:
        """注册验证处理器"""
        self._verification_handlers[runtime_name] = handler
        logger.info(f"Registered verification handler for {runtime_name}")
    
    async def create_checkpoint(
        self,
        runtime_name: str,
        state_data: Dict[str, Any],
        event_sequence: int = 0,
    ) -> RecoveryCheckpoint:
        """创建检查点"""
        import hashlib
        import uuid
        
        timestamp = int(datetime.utcnow().timestamp() * 1000)
        checkpoint_id = f"cp_{runtime_name}_{timestamp}"
        
        checksum = hashlib.sha256(
            json.dumps(state_data, sort_keys=True).encode()
        ).hexdigest()[:16]
        
        checkpoint = RecoveryCheckpoint(
            checkpoint_id=checkpoint_id,
            timestamp=timestamp,
            runtime_name=runtime_name,
            state_data=state_data,
            event_sequence=event_sequence,
            checksum=checksum,
            created_at=timestamp,
        )
        
        if runtime_name not in self._checkpoints:
            self._checkpoints[runtime_name] = []
        
        self._checkpoints[runtime_name].insert(0, checkpoint)
        
        while len(self._checkpoints[runtime_name]) > self.config.max_checkpoints:
            old_checkpoint = self._checkpoints[runtime_name].pop()
            await self._delete_checkpoint(old_checkpoint)
        
        await self._save_checkpoint(checkpoint)
        
        self._stats["checkpoints_created"] += 1
        logger.info(f"Checkpoint created: {checkpoint_id}")
        
        return checkpoint
    
    async def _save_checkpoint(self, checkpoint: RecoveryCheckpoint) -> None:
        """保存检查点到 Redis"""
        if not self._redis:
            return
        
        try:
            key = f"recovery:checkpoint:{checkpoint.checkpoint_id}"
            await self._redis.set(
                key,
                json.dumps(checkpoint.to_dict()),
                ttl=self.config.checkpoint_interval_seconds * 10
            )
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
    
    async def _delete_checkpoint(self, checkpoint: RecoveryCheckpoint) -> None:
        """删除检查点"""
        if not self._redis:
            return
        
        try:
            key = f"recovery:checkpoint:{checkpoint.checkpoint_id}"
            await self._redis.delete(key)
        except Exception as e:
            logger.error(f"Failed to delete checkpoint: {e}")
    
    async def get_latest_checkpoint(
        self,
        runtime_name: str
    ) -> Optional[RecoveryCheckpoint]:
        """获取最新检查点"""
        checkpoints = self._checkpoints.get(runtime_name, [])
        return checkpoints[0] if checkpoints else None
    
    async def recover(
        self,
        runtime_name: str,
        target_checkpoint_id: str = None,
    ) -> bool:
        """
        恢复运行时状态
        
        Args:
            runtime_name: 运行时名称
            target_checkpoint_id: 目标检查点 ID（可选，默认最新）
        
        Returns:
            是否恢复成功
        """
        self._state = RecoveryState.PREPARING
        logger.info(f"Starting recovery for {runtime_name}")
        
        try:
            checkpoint = None
            if target_checkpoint_id:
                for cp in self._checkpoints.get(runtime_name, []):
                    if cp.checkpoint_id == target_checkpoint_id:
                        checkpoint = cp
                        break
            else:
                checkpoint = await self.get_latest_checkpoint(runtime_name)
            
            if not checkpoint:
                logger.error(f"No checkpoint found for {runtime_name}")
                self._state = RecoveryState.FAILED
                return False
            
            self._state = RecoveryState.RECOVERING
            self._current_checkpoint = checkpoint
            
            handler = self._recovery_handlers.get(runtime_name)
            if handler:
                if asyncio.iscoroutinefunction(handler):
                    await handler(checkpoint.state_data)
                else:
                    handler(checkpoint.state_data)
            else:
                logger.warning(f"No recovery handler for {runtime_name}")
            
            if self.config.verify_after_recovery:
                self._state = RecoveryState.VERIFYING
                verified = await self._verify_recovery(runtime_name, checkpoint)
                if not verified:
                    logger.error(f"Recovery verification failed for {runtime_name}")
                    if self.config.rollback_on_failure:
                        await self._rollback(runtime_name)
                    self._state = RecoveryState.FAILED
                    self._stats["recoveries_failed"] += 1
                    return False
            
            self._state = RecoveryState.COMPLETED
            self._stats["recoveries_performed"] += 1
            self._stats["last_recovery_time"] = datetime.utcnow().isoformat()
            
            logger.info(f"Recovery completed for {runtime_name}")
            return True
            
        except Exception as e:
            logger.error(f"Recovery failed for {runtime_name}: {e}")
            self._state = RecoveryState.FAILED
            self._stats["recoveries_failed"] += 1
            return False
    
    async def _verify_recovery(
        self,
        runtime_name: str,
        checkpoint: RecoveryCheckpoint
    ) -> bool:
        """验证恢复结果"""
        handler = self._verification_handlers.get(runtime_name)
        if not handler:
            logger.warning(f"No verification handler for {runtime_name}")
            return True
        
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(checkpoint.state_data)
            else:
                return handler(checkpoint.state_data)
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False
    
    async def _rollback(self, runtime_name: str) -> None:
        """回滚到之前的状态"""
        checkpoints = self._checkpoints.get(runtime_name, [])
        if len(checkpoints) < 2:
            logger.warning(f"No checkpoint to rollback for {runtime_name}")
            return
        
        previous_checkpoint = checkpoints[1]
        logger.info(f"Rolling back to {previous_checkpoint.checkpoint_id}")
        
        handler = self._recovery_handlers.get(runtime_name)
        if handler:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(previous_checkpoint.state_data)
                else:
                    handler(previous_checkpoint.state_data)
            except Exception as e:
                logger.error(f"Rollback failed: {e}")
    
    async def rebuild_from_events(
        self,
        runtime_name: str,
        from_sequence: int = 0,
    ) -> Optional[Dict[str, Any]]:
        """从事件日志重建状态"""
        if not self._event_store:
            logger.warning("Event store not available for rebuild")
            return None
        
        try:
            events = await self._event_store.query(
                runtime_name=runtime_name,
                from_sequence=from_sequence
            )
            
            state = {}
            for event in events:
                state = await self._apply_event(state, event)
            
            logger.info(f"Rebuilt state from {len(events)} events for {runtime_name}")
            return state
            
        except Exception as e:
            logger.error(f"Failed to rebuild from events: {e}")
            return None
    
    async def _apply_event(
        self,
        state: Dict[str, Any],
        event: Dict[str, Any]
    ) -> Dict[str, Any]:
        """应用事件到状态"""
        event_type = event.get("event_type")
        event_data = event.get("data", {})
        
        if event_type == "state_update":
            state.update(event_data)
        elif event_type == "state_reset":
            state = event_data
        else:
            pass
        
        return state
    
    @property
    def state(self) -> RecoveryState:
        return self._state
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "state": self._state.value,
            "checkpoints_count": sum(
                len(cps) for cps in self._checkpoints.values()
            ),
            "routines_with_checkpoints": list(self._checkpoints.keys()),
        }


_recovery_instance: Optional[RuntimeRecovery] = None


async def get_runtime_recovery() -> RuntimeRecovery:
    """获取 RuntimeRecovery 单例"""
    global _recovery_instance
    if _recovery_instance is None:
        _recovery_instance = RuntimeRecovery()
        await _recovery_instance.initialize()
    return _recovery_instance
