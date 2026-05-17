"""
Replay Engine - 回放引擎

功能：
1. 事件回放 - 从历史数据回放事件
2. 确定性回放 - 保证回放结果可重现
3. 时间旅行 - 跳转到任意时间点
4. 策略回溯 - 回溯策略状态

设计原则：
- 所有随机操作使用确定性种子
- 事件顺序严格按时间戳排序
- 支持断点续传
- 支持状态快照
"""

import asyncio
import json
import hashlib
import random
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid

from infrastructure.logging import get_logger
from infrastructure.database import ClickHouseManager
from infrastructure.data_lake import DataLakeManager, DataLayer

logger = get_logger("infrastructure.replay.engine")


class ReplayMode(str, Enum):
    """回放模式"""
    REALTIME = "realtime"
    FAST = "fast"
    STEP = "step"
    DETERMINISTIC = "deterministic"


class ReplayState(str, Enum):
    """回放状态"""
    CREATED = "created"
    LOADING = "loading"
    READY = "ready"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ReplayConfig:
    """回放配置"""
    mode: ReplayMode = ReplayMode.DETERMINISTIC
    speed: float = 1.0
    
    seed: Optional[int] = None
    deterministic: bool = True
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    batch_size: int = 1000
    checkpoint_interval: int = 10000
    
    enable_state_snapshot: bool = True
    snapshot_interval: int = 5000
    
    event_types: List[str] = field(default_factory=list)
    symbols: List[str] = field(default_factory=list)
    exchanges: List[str] = field(default_factory=list)


@dataclass
class ReplayContext:
    """回放上下文"""
    replay_id: str
    session_id: str
    
    current_time: datetime
    current_sequence: int
    
    total_events: int
    processed_events: int
    
    state: ReplayState
    
    checkpoint_time: Optional[datetime] = None
    snapshot: Optional[Dict[str, Any]] = None
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "session_id": self.session_id,
            "current_time": self.current_time.isoformat(),
            "current_sequence": self.current_sequence,
            "total_events": self.total_events,
            "processed_events": self.processed_events,
            "state": self.state.value,
            "checkpoint_time": self.checkpoint_time.isoformat() if self.checkpoint_time else None,
            "snapshot": self.snapshot,
            "metadata": self.metadata,
        }


@dataclass
class TimeTravelPoint:
    """时间旅行点"""
    timestamp: datetime
    sequence: int
    event_count: int
    state_hash: str
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "sequence": self.sequence,
            "event_count": self.event_count,
            "state_hash": self.state_hash,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class StrategyState:
    """策略状态"""
    strategy_id: str
    timestamp: datetime
    
    positions: Dict[str, Any]
    signals: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    
    state_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp.isoformat(),
            "positions": self.positions,
            "signals": self.signals,
            "metrics": self.metrics,
            "state_hash": self.state_hash,
        }


class DeterministicRNG:
    """确定性随机数生成器"""
    
    def __init__(self, seed: int):
        self.seed = seed
        self._rng = random.Random(seed)
        self._call_count = 0
    
    def random(self) -> float:
        self._call_count += 1
        return self._rng.random()
    
    def randint(self, a: int, b: int) -> int:
        self._call_count += 1
        return self._rng.randint(a, b)
    
    def choice(self, seq: List[Any]) -> Any:
        self._call_count += 1
        return self._rng.choice(seq)
    
    def gauss(self, mu: float, sigma: float) -> float:
        self._call_count += 1
        return self._rng.gauss(mu, sigma)
    
    def reset(self) -> None:
        self._rng = random.Random(self.seed)
        self._call_count = 0
    
    def get_state(self) -> Dict[str, Any]:
        return {
            "seed": self.seed,
            "call_count": self._call_count,
        }


class ReplayEngine:
    """回放引擎
    
    提供完整的事件回放能力
    """
    
    def __init__(self, config: Optional[ReplayConfig] = None):
        self.config = config or ReplayConfig()
        
        self.data_lake: Optional[DataLakeManager] = None
        self.clickhouse: Optional[ClickHouseManager] = None
        
        self._context: Optional[ReplayContext] = None
        self._rng: Optional[DeterministicRNG] = None
        
        self._event_buffer: List[Dict[str, Any]] = []
        self._time_travel_points: List[TimeTravelPoint] = []
        self._strategy_states: Dict[str, StrategyState] = {}
        
        self._handlers: Dict[str, List[Callable]] = {}
        self._state_snapshots: List[Dict[str, Any]] = []
        
        self._running = False
        self._paused = False
    
    async def initialize(self) -> None:
        """初始化"""
        self.data_lake = await DataLakeManager().initialize()
        self.clickhouse = ClickHouseManager()
        
        if self.config.deterministic:
            seed = self.config.seed or int(datetime.now().timestamp() * 1000) % (2**32)
            self._rng = DeterministicRNG(seed)
        
        logger.info(f"ReplayEngine initialized (mode={self.config.mode.value}, deterministic={self.config.deterministic})")
    
    async def create_session(
        self,
        start_time: datetime,
        end_time: datetime,
        replay_id: Optional[str] = None,
    ) -> ReplayContext:
        """创建回放会话"""
        replay_id = replay_id or f"replay_{uuid.uuid4().hex[:12]}"
        session_id = f"session_{uuid.uuid4().hex[:8]}"
        
        total_events = await self._count_events(start_time, end_time)
        
        self._context = ReplayContext(
            replay_id=replay_id,
            session_id=session_id,
            current_time=start_time,
            current_sequence=0,
            total_events=total_events,
            processed_events=0,
            state=ReplayState.CREATED,
        )
        
        logger.info(f"Created replay session: {session_id} (events={total_events})")
        return self._context
    
    async def _count_events(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """统计事件数量"""
        try:
            conditions = ["timestamp >= %(start_time)s", "timestamp < %(end_time)s"]
            params = {"start_time": start_time, "end_time": end_time}
            
            if self.config.symbols:
                conditions.append("symbol IN %(symbols)s")
                params["symbols"] = tuple(self.config.symbols)
            
            if self.config.exchanges:
                conditions.append("exchange IN %(exchanges)s")
                params["exchanges"] = tuple(self.config.exchanges)
            
            if self.config.event_types:
                conditions.append("event_type IN %(event_types)s")
                params["event_types"] = tuple(self.config.event_types)
            
            count_sql = f"""
                SELECT count() FROM replay_events
                WHERE {' AND '.join(conditions)}
            """
            
            result = await self.clickhouse.fetch(count_sql, params)
            return result[0].get("count()", 0) if result else 0
            
        except Exception as e:
            logger.error(f"Failed to count events: {e}")
            return 0
    
    async def load_events(self) -> int:
        """加载事件"""
        if not self._context:
            raise RuntimeError("No replay session created")
        
        self._context.state = ReplayState.LOADING
        
        try:
            conditions = [
                "timestamp >= %(start_time)s",
                "timestamp < %(end_time)s",
            ]
            params = {
                "start_time": self.config.start_time or self._context.current_time,
                "end_time": self.config.end_time or datetime.utcnow(),
            }
            
            if self.config.symbols:
                conditions.append("symbol IN %(symbols)s")
                params["symbols"] = tuple(self.config.symbols)
            
            if self.config.exchanges:
                conditions.append("exchange IN %(exchanges)s")
                params["exchanges"] = tuple(self.config.exchanges)
            
            if self.config.event_types:
                conditions.append("event_type IN %(event_types)s")
                params["event_types"] = tuple(self.config.event_types)
            
            query_sql = f"""
                SELECT * FROM replay_events
                WHERE {' AND '.join(conditions)}
                ORDER BY timestamp, sequence
            """
            
            self._event_buffer = await self.clickhouse.fetch(query_sql, params)
            
            self._context.state = ReplayState.READY
            self._context.total_events = len(self._event_buffer)
            
            logger.info(f"Loaded {len(self._event_buffer)} events for replay")
            return len(self._event_buffer)
            
        except Exception as e:
            self._context.state = ReplayState.FAILED
            logger.error(f"Failed to load events: {e}")
            raise
    
    async def play(self) -> None:
        """开始回放"""
        if not self._context:
            raise RuntimeError("No replay session created")
        
        if self._context.state not in [ReplayState.READY, ReplayState.PAUSED]:
            raise RuntimeError(f"Invalid state: {self._context.state}")
        
        self._context.state = ReplayState.PLAYING
        self._running = True
        self._paused = False
        
        logger.info(f"Starting replay: {self._context.session_id}")
        
        try:
            for i, event in enumerate(self._event_buffer):
                if not self._running:
                    break
                
                while self._paused:
                    await asyncio.sleep(0.1)
                
                await self._process_event(event, i)
                
                self._context.processed_events = i + 1
                self._context.current_time = datetime.fromisoformat(event["timestamp"])
                self._context.current_sequence = event.get("sequence", i)
                
                if self.config.mode == ReplayMode.REALTIME:
                    await asyncio.sleep(0.001 / self.config.speed)
                elif self.config.mode == ReplayMode.STEP:
                    await asyncio.sleep(0.1)
                
                if i > 0 and i % self.config.checkpoint_interval == 0:
                    await self._save_checkpoint()
                
                if self.config.enable_state_snapshot and i > 0 and i % self.config.snapshot_interval == 0:
                    await self._save_state_snapshot()
            
            if self._running:
                self._context.state = ReplayState.COMPLETED
                logger.info(f"Replay completed: {self._context.processed_events} events")
            
        except Exception as e:
            self._context.state = ReplayState.FAILED
            logger.error(f"Replay failed: {e}")
            raise
    
    async def _process_event(
        self,
        event: Dict[str, Any],
        index: int,
    ) -> None:
        """处理事件"""
        event_type = event.get("event_type", "unknown")
        
        handlers = self._handlers.get(event_type, [])
        handlers.extend(self._handlers.get("*", []))
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event, self._context)
                else:
                    handler(event, self._context)
            except Exception as e:
                logger.error(f"Handler error for {event_type}: {e}")
    
    def register_handler(
        self,
        event_type: str,
        handler: Callable[[Dict[str, Any], ReplayContext], Any],
    ) -> None:
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def pause(self) -> None:
        """暂停回放"""
        self._paused = True
        if self._context:
            self._context.state = ReplayState.PAUSED
        logger.info("Replay paused")
    
    async def resume(self) -> None:
        """恢复回放"""
        self._paused = False
        if self._context:
            self._context.state = ReplayState.PLAYING
        logger.info("Replay resumed")
    
    async def stop(self) -> None:
        """停止回放"""
        self._running = False
        self._paused = False
        logger.info("Replay stopped")
    
    async def run(self) -> None:
        """运行回放 - play() 的别名"""
        await self.play()
    
    async def time_travel(
        self,
        target_time: datetime,
    ) -> bool:
        """时间旅行 - 跳转到指定时间"""
        if not self._context:
            return False
        
        target_index = None
        for i, event in enumerate(self._event_buffer):
            event_time = datetime.fromisoformat(event["timestamp"])
            if event_time >= target_time:
                target_index = i
                break
        
        if target_index is None:
            logger.warning(f"Target time {target_time} not found in event buffer")
            return False
        
        self._context.current_time = target_time
        self._context.processed_events = target_index
        self._context.current_sequence = self._event_buffer[target_index].get("sequence", target_index)
        
        logger.info(f"Time traveled to {target_time} (event {target_index})")
        return True
    
    async def jump_to_event(
        self,
        event_id: str,
    ) -> bool:
        """跳转到指定事件"""
        if not self._context:
            return False
        
        for i, event in enumerate(self._event_buffer):
            if event.get("event_id") == event_id:
                self._context.processed_events = i
                self._context.current_time = datetime.fromisoformat(event["timestamp"])
                self._context.current_sequence = event.get("sequence", i)
                logger.info(f"Jumped to event {event_id} (index {i})")
                return True
        
        return False
    
    def create_time_travel_point(self) -> TimeTravelPoint:
        """创建时间旅行点"""
        if not self._context:
            raise RuntimeError("No replay session")
        
        state_hash = self._compute_state_hash()
        
        point = TimeTravelPoint(
            timestamp=self._context.current_time,
            sequence=self._context.current_sequence,
            event_count=self._context.processed_events,
            state_hash=state_hash,
        )
        
        self._time_travel_points.append(point)
        logger.debug(f"Created time travel point at {point.timestamp}")
        return point
    
    async def go_to_time_travel_point(
        self,
        point: TimeTravelPoint,
    ) -> bool:
        """跳转到时间旅行点"""
        return await self.time_travel(point.timestamp)
    
    def _compute_state_hash(self) -> str:
        """计算状态哈希"""
        if not self._context:
            return ""
        
        state_data = {
            "processed_events": self._context.processed_events,
            "current_sequence": self._context.current_sequence,
            "rng_state": self._rng.get_state() if self._rng else None,
        }
        
        state_str = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()[:16]
    
    async def save_strategy_state(
        self,
        strategy_id: str,
        positions: Dict[str, Any],
        signals: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> StrategyState:
        """保存策略状态"""
        if not self._context:
            raise RuntimeError("No replay session")
        
        state_data = {
            "positions": positions,
            "signals": signals,
            "metrics": metrics,
        }
        state_str = json.dumps(state_data, sort_keys=True)
        state_hash = hashlib.sha256(state_str.encode()).hexdigest()[:16]
        
        state = StrategyState(
            strategy_id=strategy_id,
            timestamp=self._context.current_time,
            positions=positions,
            signals=signals,
            metrics=metrics,
            state_hash=state_hash,
        )
        
        self._strategy_states[strategy_id] = state
        logger.debug(f"Saved strategy state: {strategy_id} @ {state.timestamp}")
        return state
    
    async def rewind_strategy(
        self,
        strategy_id: str,
        to_time: datetime,
    ) -> Optional[StrategyState]:
        """回溯策略状态"""
        if strategy_id not in self._strategy_states:
            return None
        
        current_state = self._strategy_states[strategy_id]
        
        if to_time > current_state.timestamp:
            logger.warning("Cannot rewind to future time")
            return None
        
        await self.time_travel(to_time)
        
        logger.info(f"Rewound strategy {strategy_id} to {to_time}")
        return current_state
    
    async def _save_checkpoint(self) -> None:
        """保存检查点"""
        if not self._context:
            return
        
        checkpoint = {
            "replay_id": self._context.replay_id,
            "session_id": self._context.session_id,
            "timestamp": self._context.current_time.isoformat(),
            "sequence": self._context.current_sequence,
            "processed_events": self._context.processed_events,
            "state_hash": self._compute_state_hash(),
            "rng_state": self._rng.get_state() if self._rng else None,
        }
        
        self._context.checkpoint_time = self._context.current_time
        
        try:
            await self.clickhouse.insert("replay_checkpoints", [checkpoint])
            logger.debug(f"Saved checkpoint at {checkpoint['timestamp']}")
        except Exception as e:
            logger.warning(f"Failed to save checkpoint: {e}")
    
    async def _save_state_snapshot(self) -> None:
        """保存状态快照"""
        if not self._context:
            return
        
        snapshot = {
            "timestamp": self._context.current_time.isoformat(),
            "processed_events": self._context.processed_events,
            "strategy_states": {k: v.to_dict() for k, v in self._strategy_states.items()},
            "time_travel_points": [p.to_dict() for p in self._time_travel_points[-10:]],
        }
        
        self._state_snapshots.append(snapshot)
        self._context.snapshot = snapshot
        
        logger.debug(f"Saved state snapshot at {snapshot['timestamp']}")
    
    async def load_checkpoint(
        self,
        checkpoint_id: str,
    ) -> bool:
        """加载检查点"""
        try:
            result = await self.clickhouse.fetch(
                "SELECT * FROM replay_checkpoints WHERE checkpoint_id = %(id)s ORDER BY created_at DESC LIMIT 1",
                {"id": checkpoint_id}
            )
            
            if not result:
                return False
            
            checkpoint = result[0]
            
            self._context.current_time = datetime.fromisoformat(checkpoint["timestamp"])
            self._context.current_sequence = checkpoint["sequence"]
            self._context.processed_events = checkpoint["processed_events"]
            
            if self._rng and checkpoint.get("rng_state"):
                self._rng.seed = checkpoint["rng_state"]["seed"]
                self._rng.reset()
                for _ in range(checkpoint["rng_state"]["call_count"]):
                    self._rng.random()
            
            logger.info(f"Loaded checkpoint: {checkpoint_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return False
    
    def get_rng(self) -> Optional[DeterministicRNG]:
        """获取确定性随机数生成器"""
        return self._rng
    
    def get_context(self) -> Optional[ReplayContext]:
        """获取回放上下文"""
        return self._context
    
    def get_progress(self) -> float:
        """获取回放进度"""
        if not self._context or self._context.total_events == 0:
            return 0.0
        return self._context.processed_events / self._context.total_events
    
    def get_time_travel_points(self) -> List[TimeTravelPoint]:
        """获取所有时间旅行点"""
        return self._time_travel_points.copy()
    
    def get_strategy_states(self) -> Dict[str, StrategyState]:
        """获取所有策略状态"""
        return self._strategy_states.copy()
    
    async def verify_determinism(
        self,
        other_replay_id: str,
    ) -> bool:
        """验证确定性 - 比较两次回放结果"""
        if not self._context:
            return False
        
        try:
            result = await self.clickhouse.fetch(
                """
                SELECT state_hash FROM replay_checkpoints
                WHERE replay_id = %(id)s
                ORDER BY created_at
                """,
                {"id": other_replay_id}
            )
            
            if not result:
                return False
            
            other_hashes = [r["state_hash"] for r in result]
            current_hashes = [p.state_hash for p in self._time_travel_points]
            
            if len(other_hashes) != len(current_hashes):
                return False
            
            return all(a == b for a, b in zip(other_hashes, current_hashes))
            
        except Exception as e:
            logger.error(f"Failed to verify determinism: {e}")
            return False
    
    async def close(self) -> None:
        """关闭引擎"""
        self._running = False
        
        if self._state_snapshots:
            pass
        
        if self.data_lake:
            await self.data_lake.close()
        
        logger.info("ReplayEngine closed")


_replay_engine: Optional[ReplayEngine] = None


async def get_replay_engine(
    config: Optional[ReplayConfig] = None,
) -> ReplayEngine:
    """获取回放引擎实例"""
    global _replay_engine
    if _replay_engine is None:
        _replay_engine = ReplayEngine(config)
        await _replay_engine.initialize()
    return _replay_engine
