"""
Distributed Runtime Governance - 分布式运行时治理

提供多节点运行时协调：
- 节点注册与发现
- 主节点选举
- 任务分配
- 状态同步
- 故障转移
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from enum import Enum
import json
import hashlib

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.runtime.distributed_governance")


class NodeState(Enum):
    UNKNOWN = "unknown"
    STARTING = "starting"
    ACTIVE = "active"
    PASSIVE = "passive"
    STOPPING = "stopping"
    STOPPED = "stopped"


class Role(Enum):
    LEADER = "leader"
    FOLLOWER = "follower"
    CANDIDATE = "candidate"


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    host: str
    port: int
    runtimes: List[str]
    state: NodeState
    role: Role
    last_heartbeat: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "runtimes": self.runtimes,
            "state": self.state.value,
            "role": self.role.value,
            "last_heartbeat": self.last_heartbeat,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodeInfo":
        return cls(
            node_id=data["node_id"],
            host=data["host"],
            port=data["port"],
            runtimes=data.get("runtimes", []),
            state=NodeState(data.get("state", "unknown")),
            role=Role(data.get("role", "follower")),
            last_heartbeat=data.get("last_heartbeat", 0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DistributedGovernanceConfig:
    """分布式治理配置"""
    heartbeat_interval_ms: int = 1000
    heartbeat_timeout_ms: int = 5000
    election_timeout_ms: int = 10000
    leader_lease_ms: int = 15000
    
    max_nodes: int = 10
    min_nodes_for_election: int = 1
    
    redis_key_prefix: str = "distributed_governance:"
    node_ttl_seconds: int = 30


class DistributedRuntimeGovernance:
    """
    分布式运行时治理
    
    功能：
    1. 节点注册与发现
    2. 主节点选举（基于 Redis）
    3. 任务分配
    4. 状态同步
    5. 故障转移
    """
    
    def __init__(self, config: DistributedGovernanceConfig = None):
        self.config = config or DistributedGovernanceConfig()
        
        self._node_id: Optional[str] = None
        self._node_info: Optional[NodeInfo] = None
        self._nodes: Dict[str, NodeInfo] = {}
        
        self._role = Role.FOLLOWER
        self._leader_id: Optional[str] = None
        self._term = 0
        
        self._redis = None
        self._running = False
        
        self._task_assignments: Dict[str, str] = {}
        self._state_cache: Dict[str, Any] = {}
        
        self._stats = {
            "heartbeats_sent": 0,
            "heartbeats_received": 0,
            "elections_started": 0,
            "elections_won": 0,
            "tasks_assigned": 0,
            "failovers": 0,
        }
    
    async def initialize(
        self,
        node_id: str = None,
        host: str = "localhost",
        port: int = 8001,
        runtimes: List[str] = None,
    ) -> None:
        """初始化"""
        try:
            from infrastructure.cache.redis_client import init_redis
            self._redis = await init_redis()
            logger.info("DistributedRuntimeGovernance: Redis connected")
        except Exception as e:
            logger.warning(f"DistributedRuntimeGovernance: Redis connection failed: {e}")
        
        self._node_id = node_id or self._generate_node_id(host, port)
        self._node_info = NodeInfo(
            node_id=self._node_id,
            host=host,
            port=port,
            runtimes=runtimes or [],
            state=NodeState.STARTING,
            role=Role.FOLLOWER,
            last_heartbeat=int(datetime.utcnow().timestamp() * 1000),
        )
        
        await self._register_node()
        await self._discover_nodes()
        
        logger.info(f"DistributedRuntimeGovernance initialized: {self._node_id}")
    
    def _generate_node_id(self, host: str, port: int) -> str:
        """生成节点 ID"""
        data = f"{host}:{port}:{datetime.utcnow().isoformat()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]
    
    async def _register_node(self) -> None:
        """注册节点"""
        if not self._redis:
            return
        
        try:
            key = f"{self.config.redis_key_prefix}nodes:{self._node_id}"
            await self._redis.set(
                key,
                json.dumps(self._node_info.to_dict()),
                ttl=self.config.node_ttl_seconds
            )
            logger.info(f"Node registered: {self._node_id}")
        except Exception as e:
            logger.error(f"Failed to register node: {e}")
    
    async def _discover_nodes(self) -> None:
        """发现节点"""
        if not self._redis:
            return
        
        try:
            pattern = f"{self.config.redis_key_prefix}nodes:*"
            keys = await self._redis.keys(pattern)
            
            self._nodes.clear()
            
            for key in keys:
                data = await self._redis.get(key)
                if data:
                    node_info = NodeInfo.from_dict(json.loads(data))
                    if node_info.node_id != self._node_id:
                        self._nodes[node_info.node_id] = node_info
            
            logger.info(f"Discovered {len(self._nodes)} nodes")
            
        except Exception as e:
            logger.error(f"Failed to discover nodes: {e}")
    
    async def start(self) -> None:
        """启动治理"""
        self._running = True
        
        self._node_info.state = NodeState.ACTIVE
        await self._register_node()
        
        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._election_loop())
        
        logger.info("DistributedRuntimeGovernance started")
    
    async def stop(self) -> None:
        """停止治理"""
        self._running = False
        
        self._node_info.state = NodeState.STOPPING
        await self._register_node()
        
        if self._role == Role.LEADER:
            await self._step_down()
        
        self._node_info.state = NodeState.STOPPED
        await self._register_node()
        
        logger.info("DistributedRuntimeGovernance stopped")
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running:
            try:
                await self._send_heartbeat()
                await self._check_nodes_health()
                await asyncio.sleep(self.config.heartbeat_interval_ms / 1000)
            except Exception as e:
                logger.error(f"Heartbeat loop error: {e}")
                await asyncio.sleep(1)
    
    async def _send_heartbeat(self) -> None:
        """发送心跳"""
        self._node_info.last_heartbeat = int(datetime.utcnow().timestamp() * 1000)
        self._node_info.role = self._role
        
        await self._register_node()
        self._stats["heartbeats_sent"] += 1
        
        if self._role == Role.LEADER:
            await self._publish_leader_heartbeat()
    
    async def _publish_leader_heartbeat(self) -> None:
        """发布领导者心跳"""
        if not self._redis:
            return
        
        try:
            key = f"{self.config.redis_key_prefix}leader"
            await self._redis.set(
                key,
                json.dumps({
                    "leader_id": self._node_id,
                    "term": self._term,
                    "timestamp": self._node_info.last_heartbeat,
                }),
                ttl=self.config.leader_lease_ms // 1000
            )
        except Exception as e:
            logger.error(f"Failed to publish leader heartbeat: {e}")
    
    async def _check_nodes_health(self) -> None:
        """检查节点健康"""
        now = int(datetime.utcnow().timestamp() * 1000)
        timeout = self.config.heartbeat_timeout_ms
        
        dead_nodes = []
        for node_id, node_info in self._nodes.items():
            if now - node_info.last_heartbeat > timeout:
                dead_nodes.append(node_id)
        
        for node_id in dead_nodes:
            logger.warning(f"Node {node_id} is dead")
            del self._nodes[node_id]
            
            if self._role == Role.LEADER:
                await self._handle_node_failure(node_id)
    
    async def _handle_node_failure(self, node_id: str) -> None:
        """处理节点故障"""
        self._stats["failovers"] += 1
        
        tasks_to_reassign = []
        for task_id, assigned_node in list(self._task_assignments.items()):
            if assigned_node == node_id:
                tasks_to_reassign.append(task_id)
        
        for task_id in tasks_to_reassign:
            new_node = await self._find_best_node_for_task(task_id)
            if new_node:
                self._task_assignments[task_id] = new_node
                logger.info(f"Task {task_id} reassigned to {new_node}")
        
        logger.info(f"Handled failure of node {node_id}")
    
    async def _election_loop(self) -> None:
        """选举循环"""
        while self._running:
            try:
                await self._check_leader()
                await asyncio.sleep(self.config.election_timeout_ms / 1000)
            except Exception as e:
                logger.error(f"Election loop error: {e}")
                await asyncio.sleep(1)
    
    async def _check_leader(self) -> None:
        """检查领导者"""
        if not self._redis:
            return
        
        try:
            key = f"{self.config.redis_key_prefix}leader"
            data = await self._redis.get(key)
            
            if data:
                leader_info = json.loads(data)
                leader_id = leader_info.get("leader_id")
                term = leader_info.get("term", 0)
                
                if leader_id and leader_id != self._node_id:
                    self._leader_id = leader_id
                    self._term = term
                    self._role = Role.FOLLOWER
                    return
            
            await self._start_election()
            
        except Exception as e:
            logger.error(f"Failed to check leader: {e}")
    
    async def _start_election(self) -> None:
        """开始选举"""
        self._stats["elections_started"] += 1
        self._role = Role.CANDIDATE
        self._term += 1
        
        logger.info(f"Starting election for term {self._term}")
        
        if not self._redis:
            self._role = Role.LEADER
            self._leader_id = self._node_id
            self._stats["elections_won"] += 1
            return
        
        try:
            key = f"{self.config.redis_key_prefix}leader"
            
            result = await self._redis.client.set(
                key,
                json.dumps({
                    "leader_id": self._node_id,
                    "term": self._term,
                    "timestamp": int(datetime.utcnow().timestamp() * 1000),
                }),
                nx=True,
                ex=self.config.leader_lease_ms // 1000
            )
            
            if result:
                self._role = Role.LEADER
                self._leader_id = self._node_id
                self._stats["elections_won"] += 1
                logger.info(f"Election won! I am now the leader for term {self._term}")
            else:
                self._role = Role.FOLLOWER
                logger.info("Election lost, remaining as follower")
                
        except Exception as e:
            logger.error(f"Election error: {e}")
            self._role = Role.FOLLOWER
    
    async def _step_down(self) -> None:
        """下台"""
        if self._role != Role.LEADER:
            return
        
        logger.info("Stepping down as leader")
        
        self._role = Role.FOLLOWER
        self._leader_id = None
        
        if self._redis:
            try:
                key = f"{self.config.redis_key_prefix}leader"
                await self._redis.delete(key)
            except Exception as e:
                logger.error(f"Failed to step down: {e}")
    
    async def _find_best_node_for_task(self, task_id: str) -> Optional[str]:
        """找到最适合执行任务的节点"""
        best_node = None
        min_load = float('inf')
        
        for node_id, node_info in self._nodes.items():
            if node_info.state != NodeState.ACTIVE:
                continue
            
            load = sum(
                1 for t, n in self._task_assignments.items()
                if n == node_id
            )
            
            if load < min_load:
                min_load = load
                best_node = node_id
        
        return best_node
    
    async def assign_task(self, task_id: str, runtime: str) -> Optional[str]:
        """分配任务"""
        if self._role != Role.LEADER:
            return None
        
        best_node = await self._find_best_node_for_task(task_id)
        if best_node:
            self._task_assignments[task_id] = best_node
            self._stats["tasks_assigned"] += 1
            logger.info(f"Task {task_id} assigned to {best_node}")
            return best_node
        
        return None
    
    async def sync_state(self, key: str, value: Any) -> None:
        """同步状态"""
        if not self._redis:
            return
        
        try:
            sync_key = f"{self.config.redis_key_prefix}state:{key}"
            await self._redis.set(sync_key, json.dumps(value))
            self._state_cache[key] = value
        except Exception as e:
            logger.error(f"Failed to sync state: {e}")
    
    async def get_state(self, key: str) -> Optional[Any]:
        """获取同步状态"""
        if key in self._state_cache:
            return self._state_cache[key]
        
        if not self._redis:
            return None
        
        try:
            sync_key = f"{self.config.redis_key_prefix}state:{key}"
            data = await self._redis.get(sync_key)
            if data:
                value = json.loads(data)
                self._state_cache[key] = value
                return value
        except Exception as e:
            logger.error(f"Failed to get state: {e}")
        
        return None
    
    @property
    def is_leader(self) -> bool:
        return self._role == Role.LEADER
    
    @property
    def leader_id(self) -> Optional[str]:
        return self._leader_id
    
    @property
    def node_id(self) -> str:
        return self._node_id
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "node_id": self._node_id,
            "role": self._role.value,
            "term": self._term,
            "leader_id": self._leader_id,
            "nodes_count": len(self._nodes),
            "tasks_assigned": len(self._task_assignments),
        }


_governance_instance: Optional[DistributedRuntimeGovernance] = None


async def get_distributed_governance() -> DistributedRuntimeGovernance:
    """获取 DistributedRuntimeGovernance 单例"""
    global _governance_instance
    if _governance_instance is None:
        _governance_instance = DistributedRuntimeGovernance()
    return _governance_instance
