"""
ClickHouse Adapter - ClickHouse 存储适配器

只负责 SQL 执行，不包含任何业务逻辑。
"""

import asyncio
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

from ..interfaces import AsyncStorageAdapter


class ClickHouseAdapter(AsyncStorageAdapter):
    """
    ClickHouse 存储适配器
    
    职责：
    - SQL 执行
    - 连接管理
    - 错误处理
    
    不包含：
    - 业务逻辑
    - 表名映射
    - 数据转换
    """
    
    def __init__(
        self,
        host: str = "localhost",
        port: int = 9000,
        database: str = "default",
        user: str = "default",
        password: str = "",
        pool_size: int = 10,
    ):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self._client = None
        self._executor = ThreadPoolExecutor(max_workers=pool_size)
    
    def _get_client(self):
        """获取或创建 ClickHouse 客户端"""
        if self._client is None:
            try:
                from clickhouse_driver import Client
                self._client = Client(
                    host=self.host,
                    port=self.port,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    connect_timeout=10,
                    send_receive_timeout=60,
                )
            except ImportError:
                raise ImportError(
                    "clickhouse_driver is not installed. "
                    "Install it with: pip install clickhouse-driver"
                )
        return self._client
    
    async def fetch(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        执行 SELECT 查询并返回结果
        
        Args:
            query: SQL 查询语句
            params: 查询参数
        
        Returns:
            List[Dict[str, Any]]: 查询结果
        """
        client = self._get_client()
        params = params or {}
        
        def _execute():
            try:
                rows, columns = client.execute(
                    query,
                    params,
                    with_column_types=True,
                )
                if not rows:
                    return []
                
                names = [c[0] for c in columns]
                return [dict(zip(names, row)) for row in rows]
            except Exception as e:
                raise RuntimeError(f"ClickHouse fetch failed: {e}")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _execute)
    
    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        执行 DDL/DML 语句
        
        Args:
            query: SQL 语句
            params: 参数
        
        Returns:
            Any: 执行结果
        """
        client = self._get_client()
        params = params or {}
        
        def _execute():
            try:
                result = client.execute(query, params)
                return result
            except Exception as e:
                raise RuntimeError(f"ClickHouse execute failed: {e}")
        
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._executor, _execute)
    
    async def insert(
        self,
        table: str,
        rows: List[Dict[str, Any]]
    ) -> None:
        """
        批量插入数据
        
        Args:
            table: 表名
            rows: 要插入的行数据
        """
        if not rows:
            return
        
        client = self._get_client()
        columns = list(rows[0].keys())
        values = [[row.get(c) for c in columns] for row in rows]
        
        def _insert():
            try:
                sql = f"INSERT INTO {table} ({', '.join(columns)}) VALUES"
                client.execute(sql, values)
            except Exception as e:
                raise RuntimeError(f"ClickHouse insert failed: {e}")
        
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(self._executor, _insert)
    
    async def health_check(self) -> bool:
        """健康检查"""
        try:
            await self.fetch("SELECT 1")
            return True
        except Exception:
            return False
    
    def close(self):
        """关闭连接"""
        if self._client:
            self._client.disconnect()
            self._client = None
        self._executor.shutdown(wait=False)


class MockStorageAdapter(AsyncStorageAdapter):
    """
    Mock 存储适配器（用于测试）
    """
    
    def __init__(self):
        self._data: Dict[str, List[Dict[str, Any]]] = {}
    
    async def fetch(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """返回空结果"""
        return []
    
    async def execute(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """空操作"""
        return None
    
    async def insert(
        self,
        table: str,
        rows: List[Dict[str, Any]]
    ) -> None:
        """存储数据"""
        if table not in self._data:
            self._data[table] = []
        self._data[table].extend(rows)
    
    def set_data(self, table: str, rows: List[Dict[str, Any]]):
        """设置测试数据"""
        self._data[table] = rows


__all__ = [
    "ClickHouseAdapter",
    "MockStorageAdapter",
]
