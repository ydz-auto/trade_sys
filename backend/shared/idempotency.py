"""
Idempotency Manager - 幂等性管理器
确保操作不会被重复执行
"""

from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import hashlib
import json

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseManager

logger = get_logger("shared.idempotency")


class ExecutionStatus(str, Enum):
    """执行状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ExecutionRecord:
    """执行记录"""
    execution_id: str
    operation_type: str
    operation_key: str
    
    status: ExecutionStatus = ExecutionStatus.PENDING
    
    request_hash: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    created_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))
    started_at: Optional[int] = None
    completed_at: Optional[int] = None
    
    retry_count: int = 0
    max_retries: int = 3
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "operation_type": self.operation_type,
            "operation_key": self.operation_key,
            "status": self.status.value,
            "request_hash": self.request_hash,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionRecord":
        return cls(
            execution_id=data["execution_id"],
            operation_type=data["operation_type"],
            operation_key=data["operation_key"],
            status=ExecutionStatus(data.get("status", "pending")),
            request_hash=data.get("request_hash", ""),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data.get("created_at", 0),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {}),
        )


class IdempotencyManager:
    """幂等性管理器
    
    确保操作不会被重复执行，支持：
    - 基于唯一键的执行追踪
    - 执行状态持久化
    - 自动去重
    - 执行超时处理
    """
    
    TABLE_NAME = "execution_records"
    
    def __init__(self, ttl_seconds: int = 86400 * 7):
        self.ttl_seconds = ttl_seconds
        self.clickhouse: Optional[ClickHouseManager] = None
        
        self._records: Dict[str, ExecutionRecord] = {}
        self._lock = asyncio.Lock()
        self._initialized = False
    
    async def initialize(self):
        """初始化"""
        if self._initialized:
            return
        
        self.clickhouse = ClickHouseManager()
        await self._ensure_table()
        self._initialized = True
        logger.info("IdempotencyManager initialized")
    
    async def _ensure_table(self):
        """确保表存在"""
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
            execution_id String,
            operation_type String,
            operation_key String,
            status String,
            request_hash String,
            result String,
            error String,
            created_at Int64,
            started_at Int64,
            completed_at Int64,
            retry_count Int32,
            max_retries Int32,
            metadata String
        ) ENGINE = MergeTree()
        ORDER BY (operation_type, operation_key, created_at)
        """
        try:
            await self.clickhouse.execute(create_sql)
        except Exception as e:
            logger.warning(f"Table creation warning: {e}")
    
    def _generate_hash(self, data: Dict[str, Any]) -> str:
        """生成请求哈希"""
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]
    
    def _generate_execution_id(self, operation_type: str, operation_key: str) -> str:
        """生成执行ID"""
        timestamp = int(datetime.now().timestamp() * 1000)
        return f"{operation_type}_{operation_key}_{timestamp}"
    
    async def check_and_lock(
        self,
        operation_type: str,
        operation_key: str,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Optional[ExecutionRecord]]:
        """检查并锁定操作
        
        Returns:
            tuple: (是否可以执行, 已存在的记录)
        """
        async with self._lock:
            existing = await self._get_record(operation_type, operation_key)
            
            if existing:
                if existing.status == ExecutionStatus.COMPLETED:
                    return False, existing
                
                if existing.status == ExecutionStatus.PROCESSING:
                    if existing.started_at:
                        elapsed = (int(datetime.now().timestamp() * 1000) - existing.started_at) / 1000
                        if elapsed < 300:
                            return False, existing
                    
                    existing.status = ExecutionStatus.FAILED
                    existing.error = "Timeout"
                    await self._update_record(existing)
            
            request_hash = self._generate_hash(request_data) if request_data else ""
            
            record = ExecutionRecord(
                execution_id=self._generate_execution_id(operation_type, operation_key),
                operation_type=operation_type,
                operation_key=operation_key,
                status=ExecutionStatus.PROCESSING,
                request_hash=request_hash,
                started_at=int(datetime.now().timestamp() * 1000),
            )
            
            await self._save_record(record)
            self._records[record.execution_id] = record
            
            return True, existing
    
    async def complete(
        self,
        operation_type: str,
        operation_key: str,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """标记操作完成"""
        async with self._lock:
            record = await self._get_record(operation_type, operation_key)
            
            if not record:
                logger.warning(f"No record found for {operation_type}:{operation_key}")
                return False
            
            record.status = ExecutionStatus.COMPLETED
            record.result = result
            record.completed_at = int(datetime.now().timestamp() * 1000)
            
            await self._update_record(record)
            return True
    
    async def fail(
        self,
        operation_type: str,
        operation_key: str,
        error: str,
        can_retry: bool = True,
    ) -> bool:
        """标记操作失败"""
        async with self._lock:
            record = await self._get_record(operation_type, operation_key)
            
            if not record:
                return False
            
            if can_retry and record.retry_count < record.max_retries:
                record.retry_count += 1
                record.status = ExecutionStatus.PENDING
                record.error = error
            else:
                record.status = ExecutionStatus.FAILED
                record.error = error
                record.completed_at = int(datetime.now().timestamp() * 1000)
            
            await self._update_record(record)
            return True
    
    async def skip(
        self,
        operation_type: str,
        operation_key: str,
        reason: str,
    ) -> bool:
        """标记操作跳过"""
        async with self._lock:
            record = await self._get_record(operation_type, operation_key)
            
            if not record:
                return False
            
            record.status = ExecutionStatus.SKIPPED
            record.error = reason
            record.completed_at = int(datetime.now().timestamp() * 1000)
            
            await self._update_record(record)
            return True
    
    async def _get_record(
        self,
        operation_type: str,
        operation_key: str,
    ) -> Optional[ExecutionRecord]:
        """获取执行记录"""
        cache_key = f"{operation_type}:{operation_key}"
        if cache_key in self._records:
            return self._records[cache_key]
        
        try:
            rows = await self.clickhouse.fetch(
                f"""
                SELECT execution_id, operation_type, operation_key,
                       status, request_hash, result, error,
                       created_at, started_at, completed_at,
                       retry_count, max_retries, metadata
                FROM {self.TABLE_NAME}
                WHERE operation_type = '{operation_type}'
                AND operation_key = '{operation_key}'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            
            if rows:
                row = rows[0]
                record = ExecutionRecord(
                    execution_id=row.get("execution_id", ""),
                    operation_type=row.get("operation_type", ""),
                    operation_key=row.get("operation_key", ""),
                    status=ExecutionStatus(row.get("status", "pending")),
                    request_hash=row.get("request_hash", ""),
                    result=json.loads(row.get("result", "{}")) if row.get("result") else None,
                    error=row.get("error"),
                    created_at=row.get("created_at", 0),
                    started_at=row.get("started_at"),
                    completed_at=row.get("completed_at"),
                    retry_count=row.get("retry_count", 0),
                    max_retries=row.get("max_retries", 3),
                    metadata=json.loads(row.get("metadata", "{}")) if row.get("metadata") else {},
                )
                self._records[cache_key] = record
                return record
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get record: {e}")
            return None
    
    async def _save_record(self, record: ExecutionRecord):
        """保存执行记录"""
        try:
            await self.clickhouse.insert(
                self.TABLE_NAME,
                [{
                    "execution_id": record.execution_id,
                    "operation_type": record.operation_type,
                    "operation_key": record.operation_key,
                    "status": record.status.value,
                    "request_hash": record.request_hash,
                    "result": json.dumps(record.result) if record.result else "",
                    "error": record.error or "",
                    "created_at": record.created_at,
                    "started_at": record.started_at or 0,
                    "completed_at": record.completed_at or 0,
                    "retry_count": record.retry_count,
                    "max_retries": record.max_retries,
                    "metadata": json.dumps(record.metadata) if record.metadata else "",
                }]
            )
            
            cache_key = f"{record.operation_type}:{record.operation_key}"
            self._records[cache_key] = record
            
        except Exception as e:
            logger.error(f"Failed to save record: {e}")
    
    async def _update_record(self, record: ExecutionRecord):
        """更新执行记录"""
        await self._save_record(record)
    
    async def get_status(
        self,
        operation_type: str,
        operation_key: str,
    ) -> Optional[ExecutionStatus]:
        """获取执行状态"""
        record = await self._get_record(operation_type, operation_key)
        return record.status if record else None
    
    async def clear_expired(self):
        """清理过期记录"""
        cutoff = int(datetime.now().timestamp() * 1000) - self.ttl_seconds * 1000
        
        try:
            await self.clickhouse.execute(
                f"""
                ALTER TABLE {self.TABLE_NAME} DELETE
                WHERE created_at < {cutoff}
                """
            )
            
            self._records = {
                k: v for k, v in self._records.items()
                if v.created_at >= cutoff
            }
            
            logger.info(f"Cleared expired records before {cutoff}")
            
        except Exception as e:
            logger.error(f"Failed to clear expired records: {e}")


_idempotency_manager: Optional[IdempotencyManager] = None


async def get_idempotency_manager() -> IdempotencyManager:
    """获取幂等性管理器实例"""
    global _idempotency_manager
    if _idempotency_manager is None:
        _idempotency_manager = IdempotencyManager()
        await _idempotency_manager.initialize()
    return _idempotency_manager
