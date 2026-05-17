"""
Replay Engine - 事件回放引擎

支持全链路回放、策略验证、AI Explainability

架构：
    ClickHouse (历史事件)
         ↓
    ┌─────────────────────────────────────────────────────────┐
    │                  Replay Engine                          │
    │                                                          │
    │  - Event Replay: 按时间顺序回放事件                     │
    │  - Strategy Simulation: 模拟策略执行                    │
    │  - PnL Attribution: 盈亏归因                            │
    │  - Divergence Detection: 偏移检测                       │
    │  - Explainability: 决策解释                            │
    └─────────────────────────────────────────────────────────┘
         ↓
    Projection Service (生成回放状态)
         ↓
    Frontend (展示回放结果)
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Callable, Iterator
from dataclasses import dataclass, field
from enum import Enum

from infrastructure.logging import get_logger

logger = get_logger("replay_engine")


class ReplayMode(str, Enum):
    """回放模式"""
    LIVE = "live"
    HISTORICAL = "historical"
    SANDBOX = "sandbox"
    BACKTEST = "backtest"


class ReplayStatus(str, Enum):
    """回放状态"""
    IDLE = "idle"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class ReplayConfig:
    """回放配置"""
    mode: ReplayMode = ReplayMode.HISTORICAL
    
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    speed: float = 1.0
    
    symbols: List[str] = field(default_factory=lambda: ["BTCUSDT"])
    
    include_events: List[str] = field(default_factory=lambda: [
        "raw_data", "event", "signal", "decision", "risk_checked", "order", "fill"
    ])
    
    skip_validation: bool = False
    enable_explainability: bool = True
    
    output_to_projection: bool = False


@dataclass
class ReplayState:
    """回放状态"""
    replay_id: str
    
    status: ReplayStatus
    
    config: ReplayConfig
    
    current_time: datetime
    total_events: int
    processed_events: int
    
    progress: float = 0.0
    
    current_event: Optional[Dict[str, Any]] = None
    
    simulated_positions: Dict[str, Any] = field(default_factory=dict)
    simulated_pnl: float = 0.0
    
    divergences: List[Dict[str, Any]] = field(default_factory=list)
    
    explanations: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "replay_id": self.replay_id,
            "status": self.status.value,
            "current_time": self.current_time.isoformat(),
            "progress": self.progress,
            "processed_events": self.processed_events,
            "total_events": self.total_events,
            "simulated_pnl": self.simulated_pnl,
            "divergences_count": len(self.divergences),
            "explanations_count": len(self.explanations),
        }


@dataclass
class ReplayEvent:
    """回放事件"""
    event_index: int
    event: Dict[str, Any]
    
    timestamp: datetime
    
    replay_time: datetime
    
    is_divergence: bool = False
    divergence_reason: str = ""
    
    explanation: str = ""


class EventReplayIterator:
    """
    事件回放迭代器
    
    按时间顺序迭代事件
    """
    
    def __init__(self, events: List[Dict[str, Any]], config: ReplayConfig):
        self.events = sorted(events, key=lambda e: e.get("timestamp", ""))
        self.config = config
        self.index = 0
        self.replay_start = datetime.utcnow()
    
    def __iter__(self) -> Iterator[ReplayEvent]:
        return self
    
    def __next__(self) -> ReplayEvent:
        if self.index >= len(self.events):
            raise StopIteration
        
        event = self.events[self.index]
        
        replay_time = self._calculate_replay_time(self.index)
        
        self.index += 1
        
        return ReplayEvent(
            event_index=self.index,
            event=event,
            timestamp=self._parse_timestamp(event.get("timestamp")),
            replay_time=replay_time,
        )
    
    def _calculate_replay_time(self, index: int) -> datetime:
        """计算回放时间"""
        if index == 0:
            return self.config.start_time or datetime.utcnow()
        
        prev_time = self._parse_timestamp(
            self.events[max(0, index-1)].get("timestamp")
        )
        curr_time = self._parse_timestamp(event.get("timestamp"))
        
        if self.config.speed > 0:
            real_diff = (curr_time - prev_time).total_seconds() / self.config.speed
            return self.replay_start + timedelta(seconds=real_diff)
        
        return curr_time
    
    def _parse_timestamp(self, ts) -> datetime:
        """解析时间戳"""
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.utcnow()


class ReplayEngine:
    """
    Replay Engine
    
    职责：
    1. 从 ClickHouse/Redis 加载历史事件
    2. 按时间顺序回放事件
    3. 模拟策略执行
    4. 检测与实时执行的偏移
    5. 生成决策解释
    """
    
    def __init__(self):
        self._current_replay: Optional[ReplayState] = None
        self._event_cache: Dict[str, List[Dict[str, Any]]] = {}
        
        self._stats = {
            "replays_started": 0,
            "replays_completed": 0,
            "events_replayed": 0,
            "divergences_detected": 0,
        }
    
    async def load_events(
        self,
        config: ReplayConfig,
        event_loader: Optional[Callable] = None,
    ) -> ReplayState:
        """
        加载事件
        
        Args:
            config: 回放配置
            event_loader: 事件加载器函数
            
        Returns:
            ReplayState: 回放状态
        """
        replay_id = f"replay_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        state = ReplayState(
            replay_id=replay_id,
            status=ReplayStatus.LOADING,
            config=config,
            current_time=config.start_time or datetime.utcnow(),
            total_events=0,
            processed_events=0,
        )
        
        self._current_replay = state
        
        events = []
        
        if event_loader:
            events = await event_loader(config)
        else:
            events = await self._load_from_cache(config)
        
        if config.include_events:
            events = [
                e for e in events
                if e.get("event_type") in config.include_events
            ]
        
        state.total_events = len(events)
        state.status = ReplayStatus.IDLE
        
        logger.info(f"Loaded {len(events)} events for replay {replay_id}")
        
        return state
    
    async def _load_from_cache(self, config: ReplayConfig) -> List[Dict[str, Any]]:
        """从缓存加载事件"""
        from infrastructure.cache.redis_client import get_redis_client
        from services.projection_service.state_keys import ProjectionKeys
        
        try:
            redis = await get_redis_client()
            if not redis:
                return []
            
            events = []
            for symbol in config.symbols:
                key = ProjectionKeys.timeline_by_symbol(symbol)
                symbol_events = await redis.lrange(key, 0, 1000)
                
                for e in symbol_events:
                    try:
                        event = json.loads(e) if isinstance(e, str) else e
                        events.append(event)
                    except json.JSONDecodeError:
                        continue
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to load events from cache: {e}")
            return []
    
    async def start_replay(
        self,
        on_event: Optional[Callable[[ReplayEvent], None]] = None,
        on_state_update: Optional[Callable[[ReplayState], None]] = None,
    ) -> ReplayState:
        """
        开始回放
        
        Args:
            on_event: 事件回调
            on_state_update: 状态更新回调
            
        Returns:
            ReplayState: 最终状态
        """
        if not self._current_replay:
            raise RuntimeError("No replay loaded")
        
        state = self._current_replay
        state.status = ReplayStatus.PLAYING
        
        self._stats["replays_started"] += 1
        
        events = await self._get_cached_events(state.config)
        
        iterator = EventReplayIterator(events, state.config)
        
        for replay_event in iterator:
            if state.status != ReplayStatus.PLAYING:
                break
            
            state.current_time = replay_event.replay_time
            state.current_event = replay_event.event
            state.processed_events += 1
            state.progress = state.processed_events / state.total_events if state.total_events > 0 else 0
            
            if state.config.enable_explainability:
                explanation = self._generate_explanation(replay_event)
                if explanation:
                    state.explanations.append(explanation)
                    replay_event.explanation = explanation
            
            if on_event:
                await on_event(replay_event)
            
            if on_state_update and state.processed_events % 100 == 0:
                await on_state_update(state)
        
        state.status = ReplayStatus.COMPLETED
        state.progress = 1.0
        
        self._stats["replays_completed"] += 1
        self._stats["events_replayed"] += state.processed_events
        
        logger.info(
            f"Replay completed: {state.replay_id} - "
            f"{state.processed_events} events, "
            f"{len(state.divergences)} divergences, "
            f"{len(state.explanations)} explanations"
        )
        
        return state
    
    async def _get_cached_events(self, config: ReplayConfig) -> List[Dict[str, Any]]:
        """获取缓存的事件"""
        return self._event_cache.get(config.symbols[0], [])
    
    def pause_replay(self) -> ReplayState:
        """暂停回放"""
        if self._current_replay:
            self._current_replay.status = ReplayStatus.PAUSED
        return self._current_replay
    
    def resume_replay(self) -> ReplayState:
        """恢复回放"""
        if self._current_replay:
            self._current_replay.status = ReplayStatus.PLAYING
        return self._current_replay
    
    def stop_replay(self) -> None:
        """停止回放"""
        if self._current_replay:
            self._current_replay.status = ReplayStatus.COMPLETED
    
    def simulate_strategy(
        self,
        events: List[Dict[str, Any]],
        strategy_fn: Callable[[Dict[str, Any]], Optional[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """
        模拟策略执行
        
        Args:
            events: 事件列表
            strategy_fn: 策略函数
            
        Returns:
            Dict: 模拟结果
        """
        positions = {}
        pnl_history = []
        
        for event in events:
            signal = strategy_fn(event)
            
            if not signal:
                continue
            
            action = signal.get("action")
            symbol = signal.get("symbol", "BTC")
            
            if action in ("LONG", "BUY"):
                positions[symbol] = {
                    "size": signal.get("quantity", 0.01),
                    "entry_price": event.get("close") or event.get("price", 0),
                    "entry_time": event.get("timestamp"),
                }
            
            elif action in ("SHORT", "SELL"):
                positions[symbol] = {
                    "size": -signal.get("quantity", 0.01),
                    "entry_price": event.get("close") or event.get("price", 0),
                    "entry_time": event.get("timestamp"),
                }
            
            elif action in ("CLOSE", "EXIT"):
                if symbol in positions:
                    entry = positions.pop(symbol)
                    current = event.get("close") or event.get("price", 0)
                    pnl = (current - entry["entry_price"]) * entry["size"]
                    pnl_history.append({
                        "symbol": symbol,
                        "entry_price": entry["entry_price"],
                        "exit_price": current,
                        "pnl": pnl,
                        "timestamp": event.get("timestamp"),
                    })
        
        total_pnl = sum(p.get("pnl", 0) for p in pnl_history)
        
        return {
            "positions": positions,
            "closed_trades": pnl_history,
            "total_pnl": total_pnl,
            "trade_count": len(pnl_history),
        }
    
    def detect_divergence(
        self,
        replay_event: ReplayEvent,
        real_event: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        检测偏移
        
        Args:
            replay_event: 回放事件
            real_event: 实时事件
            
        Returns:
            Optional[Dict]: 偏移信息
        """
        if not real_event:
            return None
        
        divergences = []
        
        if replay_event.event.get("action") != real_event.get("action"):
            divergences.append({
                "type": "action_mismatch",
                "replay": replay_event.event.get("action"),
                "real": real_event.get("action"),
            })
        
        replay_ts = replay_event.timestamp
        real_ts = self._parse_timestamp(real_event.get("timestamp"))
        
        time_diff = abs((replay_ts - real_ts).total_seconds())
        if time_diff > 60:
            divergences.append({
                "type": "timing_mismatch",
                "replay_time": replay_ts.isoformat(),
                "real_time": real_ts.isoformat(),
                "diff_seconds": time_diff,
            })
        
        if divergences:
            divergence = {
                "event_index": replay_event.event_index,
                "timestamp": replay_event.timestamp.isoformat(),
                "event_type": replay_event.event.get("event_type"),
                "divergences": divergences,
            }
            
            self._stats["divergences_detected"] += 1
            
            if self._current_replay:
                self._current_replay.divergences.append(divergence)
            
            return divergence
        
        return None
    
    def _generate_explanation(self, event: ReplayEvent) -> str:
        """生成事件解释"""
        event_type = event.event.get("event_type", "")
        event_data = event.event
        
        if event_type == "signal":
            signal_name = event_data.get("signal_name", "")
            direction = event_data.get("direction", "")
            confidence = event_data.get("confidence", 0)
            
            return (
                f"Signal '{signal_name}' generated with {direction} direction "
                f"at {confidence:.0%} confidence"
            )
        
        elif event_type == "decision":
            action = event_data.get("action", "")
            reason = event_data.get("reason", "")
            confidence = event_data.get("confidence", 0)
            
            return (
                f"Decision made: {action} with {confidence:.0%} confidence. "
                f"Reason: {reason[:100]}"
            )
        
        elif event_type == "risk_checked":
            approved = event_data.get("approved", False)
            risk_level = event_data.get("risk_level", "unknown")
            
            if approved:
                return f"Risk check passed at {risk_level} level"
            else:
                reason = event_data.get("rejection_reason", "Unknown")
                return f"Risk check failed: {reason}"
        
        elif event_type == "fill":
            side = event_data.get("side", "")
            quantity = event_data.get("quantity", 0)
            price = event_data.get("price", 0)
            
            return (
                f"Order filled: {side} {quantity} @ ${price}. "
                f"Total: ${quantity * price:.2f}"
            )
        
        return ""
    
    def _parse_timestamp(self, ts) -> datetime:
        """解析时间戳"""
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return datetime.utcnow()
        return datetime.utcnow()
    
    def get_current_state(self) -> Optional[ReplayState]:
        """获取当前回放状态"""
        return self._current_replay
    
    def cache_events(self, symbol: str, events: List[Dict[str, Any]]) -> None:
        """缓存事件"""
        self._event_cache[symbol] = events
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            **self._stats,
            "current_replay": self._current_replay.replay_id if self._current_replay else None,
        }


_replay_engine: Optional[ReplayEngine] = None


def get_replay_engine() -> ReplayEngine:
    """获取 ReplayEngine 单例"""
    global _replay_engine
    if _replay_engine is None:
        _replay_engine = ReplayEngine()
    return _replay_engine
