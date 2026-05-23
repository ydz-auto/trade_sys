"""
Replay Engine - 确定性回放引擎

核心职责:
- Record 模式: 记录 Live 运行的完整状态
- Replay 模式: 完全按照记录的时间序列回放
- 验证: 对比 Replay 和 Live 是否 100% 一致
"""

from enum import Enum
from typing import Optional, Dict, Any, Callable
from pathlib import Path

from runtime.authority import (
    AuthoritySystem,
    ClockAuthority,
    ClockMode,
)
from runtime.guards import (
    GuardSystem,
)
from runtime.replay_engine.event_log import (
    EventLog,
    LoggedEvent,
)
from runtime.replay_engine.state_capture import (
    StateCapture,
    StateSnapshot,
)
from domain.event.protocol import (
    ImmutableEvent,
    ImmutableEventBuilder,
    EventSource,
)
from domain.logging import get_logger

logger = get_logger("runtime.replay.engine")


class ReplayMode(Enum):
    """回放模式"""
    LIVE = "live"          # 实时运行，同时记录
    RECORD = "record"      # 仅记录模式
    REPLAY = "replay"      # 回放模式
    VALIDATE = "validate"  # 验证模式（回放 + 验证）


class ReplayEngine:
    """
    确定性回放引擎
    
    核心目标:
    1. Record: 完整记录 Live 运行
    2. Replay: 100% 确定性回放
    3. Validate: 验证 Replay ≡ Live
    """
    
    def __init__(
        self,
        name: str = "replay_engine",
        authority_system: Optional[AuthoritySystem] = None,
        guard_system: Optional[GuardSystem] = None,
        storage_dir: Optional[Path] = None,
    ):
        self.name = name
        self.storage_dir = storage_dir or Path("./replay_data")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 依赖的系统
        self._authority_system = authority_system or AuthoritySystem()
        self._guard_system = guard_system or GuardSystem(
            clock_authority=self._authority_system.clock,
        )
        
        # 核心组件
        self._event_log = EventLog(
            name=f"{name}_events",
            storage_path=self.storage_dir / "events.json",
        )
        self._state_capture = StateCapture(
            name=f"{name}_states",
            storage_path=self.storage_dir / "states.json",
        )
        
        # 状态
        self._mode = ReplayMode.LIVE
        self._is_running = False
        
        # 状态提供函数
        self._state_provider: Optional[Callable[[], Dict[str, Any]]] = None
        
        logger.info(f"ReplayEngine initialized in {self._mode.value} mode")
    
    @property
    def mode(self) -> ReplayMode:
        return self._mode
    
    @property
    def event_log(self) -> EventLog:
        return self._event_log
    
    @property
    def state_capture(self) -> StateCapture:
        return self._state_capture
    
    def set_state_provider(
        self,
        provider: Callable[[], Dict[str, Any]],
    ) -> None:
        """
        设置状态提供函数
        
        Args:
            provider: 返回当前完整状态的函数
        """
        self._state_provider = provider
    
    def start_record(self) -> None:
        """
        开始记录模式
        
        Live 运行同时保存所有事件和状态
        """
        self._mode = ReplayMode.RECORD
        self._is_running = True
        
        # 确保是 LIVE 时钟模式
        self._authority_system.clock.switch_to_live_mode()
        
        # 开始记录事件
        self._event_log.start_recording(
            start_time_ms=self._authority_system.clock.now_ms(),
        )
        
        # 重置状态捕获
        self._state_capture.reset()
        
        logger.info(f"ReplayEngine started RECORD mode")
    
    def stop_record(self) -> None:
        """
        停止记录并保存
        """
        self._is_running = False
        
        # 停止记录
        self._event_log.stop_recording()
        
        # 保存
        self._event_log.save()
        self._state_capture.save()
        
        logger.info(f"ReplayEngine stopped RECORD mode")
    
    def process_event(
        self,
        event_type: str,
        symbol: str,
        exchange: str,
        event_time_ms: int,
        payload: Dict[str, Any],
        source: EventSource = EventSource.LIVE,
    ) -> tuple[ImmutableEvent, int]:
        """
        处理事件（统一入口）
        
        根据模式:
        - RECORD: 处理 + 记录
        - LIVE: 仅处理
        - REPLAY: 从日志读取并处理
        """
        # 1. 通过 Authority 生成完整事件
        event, sequence_number = self._authority_system.process_raw_event(
            event_type=event_type,
            symbol=symbol,
            exchange=exchange,
            event_time_ms=event_time_ms,
            payload=payload,
            source=source,
        )
        
        # 2. 通过 Guard 验证
        if self._guard_system:
            self._guard_system.process_before(event)
        
        # 3. 在 RECORD 模式下记录
        if self._mode in [ReplayMode.RECORD, ReplayMode.LIVE]:
            self._event_log.record_event(
                event=event,
                sequence_number=sequence_number,
            )
            
            # 捕获处理前的状态
            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_BEFORE",
                    clock_time_ms=self._authority_system.clock.now_ms(),
                    sequence_number=sequence_number,
                    state_data=self._state_provider(),
                    event_id=event.event_id,
                )
        
        # 4. 这里应该调用实际的业务处理
        # （为了演示，我们先跳过，实际应该有回调机制）
        
        # 5. 在 RECORD 模式下记录处理后的状态
        if self._mode in [ReplayMode.RECORD, ReplayMode.LIVE]:
            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_AFTER",
                    clock_time_ms=self._authority_system.clock.now_ms(),
                    sequence_number=sequence_number,
                    state_data=self._state_provider(),
                    event_id=event.event_id,
                )
        
        # 6. Guard 处理后
        if self._guard_system:
            self._guard_system.process_after(event, result={})
        
        return event, sequence_number
    
    def start_replay(
        self,
        event_log_path: Optional[Path] = None,
    ) -> None:
        """
        开始回放模式
        
        Args:
            event_log_path: 加载的日志路径
        """
        self._mode = ReplayMode.REPLAY
        self._is_running = True
        
        # 加载日志（如果指定）
        if event_log_path:
            self._event_log = EventLog.load(event_log_path)
        
        # 切换到 REPLAY 时钟模式
        start_time = self._event_log._start_time_ms
        self._authority_system.switch_to_replay_mode(start_time)
        
        # 重置状态捕获（用于记录回放时的状态）
        self._state_capture.reset()
        
        # 重置 Guard
        if self._guard_system:
            self._guard_system.reset()
        
        logger.info(
            f"ReplayEngine started REPLAY mode, "
            f"events={self._event_log.count}, "
            f"start_time={start_time}"
        )
    
    def run_full_replay(
        self,
        validate: bool = True,
    ) -> tuple[int, int]:
        """
        运行完整回放
        
        Args:
            validate: 是否在回放时验证
        
        Returns:
            (处理事件数, 违规数)
        """
        if self._mode != ReplayMode.REPLAY:
            self.start_replay()
        
        processed_count = 0
        violation_count = 0
        
        # 逐个回放事件
        for logged_event in self._event_log.get_event_iterator():
            processed_count += 1
            
            # 1. 时钟前进到事件的 processing_time
            self._authority_system.advance_clock(logged_event.processing_time_ms)
            
            # 2. 重建事件
            builder = ImmutableEventBuilder()
            replay_event = (
                builder
                .event_id(logged_event.event_id)
                .event_type(logged_event.event_type)
                .symbol(logged_event.symbol)
                .exchange(logged_event.exchange)
                .event_time_ms(logged_event.event_time_ms)
                .available_time_ms(logged_event.available_time_ms)
                .processing_time_ms(logged_event.processing_time_ms)
                .payload(logged_event.payload)
                .source(EventSource.REPLAY)
                .build()
            )
            
            # 3. 捕获处理前状态
            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_BEFORE",
                    clock_time_ms=logged_event.processing_time_ms,
                    sequence_number=logged_event.sequence_number,
                    state_data=self._state_provider(),
                    event_id=logged_event.event_id,
                )
            
            # 4. 通过 Guard 验证
            if self._guard_system:
                try:
                    self._guard_system.process_before(replay_event)
                except Exception as e:
                    violation_count += 1
                    logger.error(
                        f"Guard violation during replay: {logged_event.event_id}, "
                        f"error={e}"
                    )
            
            # 5. 业务处理（应该和 Live 用同样的代码）
            
            # 6. 捕获处理后状态
            if self._state_provider:
                self._state_capture.capture(
                    capture_point="EVENT_AFTER",
                    clock_time_ms=logged_event.processing_time_ms,
                    sequence_number=logged_event.sequence_number,
                    state_data=self._state_provider(),
                    event_id=logged_event.event_id,
                )
        
        logger.info(
            f"Replay completed: "
            f"processed={processed_count}, "
            f"violations={violation_count}"
        )
        
        return processed_count, violation_count
    
    def save_session(
        self,
        name: Optional[str] = None,
    ) -> Path:
        """
        保存完整回话
        
        Args:
            name: 会话名称
        
        Returns:
            保存的目录路径
        """
        session_name = name or self.name
        session_dir = self.storage_dir / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存事件和状态
        self._event_log.save(session_dir / "events.json")
        self._state_capture.save(session_dir / "states.json")
        
        logger.info(f"Saved session to {session_dir}")
        return session_dir
    
    @classmethod
    def load_session(
        cls,
        session_dir: Path,
        authority_system: Optional[AuthoritySystem] = None,
        guard_system: Optional[GuardSystem] = None,
    ) -> 'ReplayEngine':
        """
        加载会话
        
        Args:
            session_dir: 会话目录
            authority_system: 可复用的 authority 系统
            guard_system: 可复用的 guard 系统
        
        Returns:
            加载的 ReplayEngine
        """
        engine = cls(
            name=session_dir.name,
            authority_system=authority_system,
            guard_system=guard_system,
            storage_dir=session_dir.parent,
        )
        
        engine._event_log = EventLog.load(session_dir / "events.json")
        engine._state_capture = StateCapture.load(session_dir / "states.json")
        
        logger.info(f"Loaded session from {session_dir}")
        return engine
    
    def reset(self) -> None:
        """重置"""
        self._is_running = False
        self._mode = ReplayMode.LIVE
        self._event_log.reset()
        self._state_capture.reset()
        self._authority_system.clock.switch_to_live_mode()
        
        if self._guard_system:
            self._guard_system.reset()
    
    def __repr__(self) -> str:
        return (
            f"ReplayEngine(mode={self._mode.value}, "
            f"events={self._event_log.count}, "
            f"states={self._state_capture.count})"
        )
