"""
Runtime Kernel - 交易内核

设计原则:
- 单一入口: runtime.handle(raw_event) - 没有其他路径
- 强制路径: Authority → Guard → State Transition → Emit
- 不可绕过: 所有事件必须经过完整管道
- 确定性: 同样的输入，100% 同样的输出
"""

from typing import Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from enum import Enum
import json
import hashlib
from datetime import datetime
from pathlib import Path

from runtime.authority import (
    AuthoritySystem,
    ClockAuthority,
    ClockMode,
)
from runtime.guards import (
    GuardSystem,
    GuardViolation,
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

logger = get_logger("runtime.kernel")


class KernelMode(Enum):
    """内核模式"""
    LIVE = "live"          # 实时运行
    RECORD = "record"      # 实时运行 + 记录
    REPLAY = "replay"      # 回放模式
    VALIDATE = "validate"  # 验证模式


@dataclass
class RawEvent:
    """
    原始事件 - 进入内核的唯一入口格式
    
    只包含基本数据，所有时间语义由内核计算
    """
    event_type: str
    symbol: str
    exchange: str
    event_time_ms: int
    payload: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "event_time_ms": self.event_time_ms,
            "payload": self.payload,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RawEvent':
        return cls(
            event_type=data["event_type"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            event_time_ms=data["event_time_ms"],
            payload=data["payload"],
        )


@dataclass
class StateTrajectory:
    """
    状态轨迹 - 用于验证 Replay ≡ Live
    
    每一步都记录 state hash，确保行为完全一致
    """
    steps: list[Tuple[int, str, str]] = None  # (seq_num, event_id, state_hash)
    start_time_ms: int = 0
    end_time_ms: int = 0
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []
    
    def add_step(
        self,
        sequence_number: int,
        event_id: str,
        state_data: Dict[str, Any],
    ) -> None:
        """添加一步"""
        state_hash = self._compute_hash(state_data)
        self.steps.append((sequence_number, event_id, state_hash))
    
    @staticmethod
    def _compute_hash(state_data: Dict[str, Any]) -> str:
        """计算 state hash"""
        content = json.dumps(state_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:32]
    
    def compare(
        self,
        other: 'StateTrajectory',
        name_a: str = "a",
        name_b: str = "b",
    ) -> Tuple[bool, list[Dict[str, Any]]]:
        """
        比较两条轨迹
        
        Returns:
            (是否一致, 差异列表)
        """
        differences = []
        
        # 1. 检查步数
        if len(self.steps) != len(other.steps):
            differences.append({
                "step": -1,
                "category": "step_count_mismatch",
                f"{name_a}_count": len(self.steps),
                f"{name_b}_count": len(other.steps),
            })
        
        # 2. 逐步比较
        min_steps = min(len(self.steps), len(other.steps))
        
        for i in range(min_steps):
            seq_a, event_a, hash_a = self.steps[i]
            seq_b, event_b, hash_b = other.steps[i]
            
            # 检查序列号
            if seq_a != seq_b:
                differences.append({
                    "step": i,
                    "category": "seq_mismatch",
                    "message": f"Sequence mismatch: {seq_a} vs {seq_b}",
                })
                continue
            
            # 检查事件 ID
            if event_a != event_b:
                differences.append({
                    "step": i,
                    "category": "event_mismatch",
                    "message": f"Event mismatch: {event_a} vs {event_b}",
                    "seq": seq_a,
                })
                continue
            
            # 检查 state hash
            if hash_a != hash_b:
                differences.append({
                    "step": i,
                    "category": "state_hash_mismatch",
                    "message": f"State hash mismatch at step {i}, seq {seq_a}",
                    "seq": seq_a,
                    "event_id": event_a,
                    f"{name_a}_hash": hash_a,
                    f"{name_b}_hash": hash_b,
                })
        
        is_consistent = len(differences) == 0
        return is_consistent, differences
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": [
                {
                    "seq": s[0],
                    "event_id": s[1],
                    "hash": s[2],
                }
                for s in self.steps
            ],
            "start_time_ms": self.start_time_ms,
            "end_time_ms": self.end_time_ms,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StateTrajectory':
        return cls(
            steps=[(s["seq"], s["event_id"], s["hash"]) for s in data["steps"]],
            start_time_ms=data["start_time_ms"],
            end_time_ms=data["end_time_ms"],
        )
    
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> 'StateTrajectory':
        with open(path, 'r', encoding='utf-8') as f:
            return cls.from_dict(json.load(f))


class RuntimeKernel:
    """
    交易内核 - 单一入口
    
    唯一入口: handle(raw_event)
    强制路径: Authority → Guard → State Transition → Emit
    """
    
    def __init__(
        self,
        name: str = "kernel",
        storage_dir: Optional[Path] = None,
        state_provider: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        self.name = name
        self.storage_dir = storage_dir or Path("./kernel_data")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # 状态提供者
        self._state_provider = state_provider
        
        # 核心系统
        self._authority = AuthoritySystem()
        self._guard_system = GuardSystem(
            clock_authority=self._authority.clock,
        )
        
        # 记录系统
        self._event_log = EventLog(
            name=f"{name}_events",
            storage_path=self.storage_dir / "events.json",
        )
        self._state_capture = StateCapture(
            name=f"{name}_states",
            storage_path=self.storage_dir / "states.json",
        )
        self._state_trajectory = StateTrajectory()
        
        # 状态
        self._mode = KernelMode.LIVE
        self._is_running = False
        self._step_count = 0
        
        # 业务回调
        self._business_callback: Optional[Callable[[ImmutableEvent], Dict[str, Any]]] = None
        
        logger.info(f"RuntimeKernel initialized in {self._mode.value} mode")
    
    @property
    def mode(self) -> KernelMode:
        return self._mode
    
    @property
    def state_trajectory(self) -> StateTrajectory:
        return self._state_trajectory
    
    def set_state_provider(
        self,
        provider: Callable[[], Dict[str, Any]],
    ) -> None:
        """设置状态提供者"""
        self._state_provider = provider
    
    def set_business_callback(
        self,
        callback: Callable[[ImmutableEvent], Dict[str, Any]],
    ) -> None:
        """
        设置业务逻辑回调
        
        这是内核和业务逻辑的唯一接口
        """
        self._business_callback = callback
    
    # ===============================
    # 模式控制
    # ===============================
    
    def start_record(self) -> None:
        """
        开始记录模式
        
        Live 运行同时记录所有事件和状态
        """
        self._mode = KernelMode.RECORD
        self._is_running = True
        
        # 切换时钟到 LIVE 模式
        self._authority.switch_to_live_mode()
        
        # 开始记录
        self._event_log.start_recording(
            start_time_ms=self._authority.clock.now_ms(),
        )
        
        # 重置轨迹
        self._state_trajectory = StateTrajectory()
        self._state_trajectory.start_time_ms = self._authority.clock.now_ms()
        
        logger.info("RuntimeKernel started RECORD mode")
    
    def stop_record(self) -> None:
        """停止记录"""
        self._is_running = False
        self._state_trajectory.end_time_ms = self._authority.clock.now_ms()
        
        self._event_log.stop_recording()
        
        # 保存
        self._event_log.save()
        self._state_capture.save()
        self._state_trajectory.save(self.storage_dir / "trajectory.json")
        
        logger.info(
            f"RuntimeKernel stopped RECORD mode, "
            f"steps={len(self._state_trajectory.steps)}"
        )
    
    def start_replay(
        self,
        event_log_path: Optional[Path] = None,
    ) -> None:
        """
        开始回放模式
        
        Args:
            event_log_path: 可选的 log 路径
        """
        self._mode = KernelMode.REPLAY
        self._is_running = True
        
        # 加载 log（如果指定）
        if event_log_path:
            self._event_log = EventLog.load(event_log_path)
        
        # 切换时钟到 REPLAY 模式
        start_time = self._event_log._start_time_ms
        self._authority.switch_to_replay_mode(start_time)
        
        # 重置
        self._state_trajectory = StateTrajectory()
        self._state_trajectory.start_time_ms = start_time
        self._guard_system.reset()
        
        logger.info(
            f"RuntimeKernel started REPLAY mode, "
            f"events={self._event_log.count}"
        )
    
    # ===============================
    # 唯一入口
    # ===============================
    
    def handle(
        self,
        raw_event: RawEvent,
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        唯一入口 - 处理原始事件
        
        强制路径:
        1. Authority Layer - 计算所有时间语义
        2. Guard Chain - 验证所有约束
        3. State Capture Before - 记录处理前状态
        4. Business Logic - 执行业务逻辑
        5. State Capture After - 记录处理后状态
        6. State Trajectory - 添加到轨迹
        
        没有其他路径可以绕过此流程
        
        Args:
            raw_event: 原始事件
        
        Returns:
            (是否成功, 业务结果)
        """
        self._step_count += 1
        
        try:
            # ============================================
            # 1. Authority Layer - 强制计算所有时间语义
            # ============================================
            event, seq_num = self._authority.process_raw_event(
                event_type=raw_event.event_type,
                symbol=raw_event.symbol,
                exchange=raw_event.exchange,
                event_time_ms=raw_event.event_time_ms,
                payload=raw_event.payload,
                source=EventSource.LIVE if self._mode == KernelMode.LIVE else EventSource.REPLAY,
            )
            
            # ============================================
            # 2. Guard Chain - 强制验证
            # ============================================
            self._guard_system.process_before(event)
            
            # ============================================
            # 3. State Capture Before - 处理前状态
            # ============================================
            state_before = self._get_current_state()
            if self._mode in [KernelMode.RECORD, KernelMode.REPLAY]:
                self._state_capture.capture(
                    capture_point="EVENT_BEFORE",
                    clock_time_ms=self._authority.clock.now_ms(),
                    sequence_number=seq_num,
                    state_data=state_before,
                    event_id=event.event_id,
                )
            
            # ============================================
            # 4. Record Event (仅 RECORD 模式)
            # ============================================
            if self._mode == KernelMode.RECORD:
                self._event_log.record_event(event, seq_num)
            
            # ============================================
            # 5. Business Logic - 业务逻辑
            # ============================================
            business_result = {}
            if self._business_callback:
                business_result = self._business_callback(event)
            
            # ============================================
            # 6. State Capture After - 处理后状态
            # ============================================
            state_after = self._get_current_state()
            if self._mode in [KernelMode.RECORD, KernelMode.REPLAY]:
                self._state_capture.capture(
                    capture_point="EVENT_AFTER",
                    clock_time_ms=self._authority.clock.now_ms(),
                    sequence_number=seq_num,
                    state_data=state_after,
                    event_id=event.event_id,
                )
                
                # ============================================
                # 7. State Trajectory - 添加轨迹点
                # ============================================
                self._state_trajectory.add_step(
                    sequence_number=seq_num,
                    event_id=event.event_id,
                    state_data=state_after,
                )
            
            # ============================================
            # 8. Guard After - 处理后验证
            # ============================================
            self._guard_system.process_after(event, business_result)
            
            return True, business_result
        
        except GuardViolation as e:
            logger.error(f"Guard violation: {e}")
            return False, None
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False, None
    
    # ===============================
    # 完整回放
    # ===============================
    
    def run_full_replay(
        self,
        event_log_path: Optional[Path] = None,
    ) -> Tuple[bool, StateTrajectory]:
        """
        运行完整回放
        
        Returns:
            (是否成功, 生成的轨迹)
        """
        if not self._state_provider:
            raise RuntimeError("State provider not set")
        
        # 开始回放
        self.start_replay(event_log_path)
        
        # 重置轨迹
        self._state_trajectory = StateTrajectory()
        self._state_trajectory.start_time_ms = self._authority.clock.now_ms()
        
        # 逐事件回放
        success_count = 0
        fail_count = 0
        
        for logged_event in self._event_log.get_event_iterator():
            # 时钟前进
            self._authority.advance_clock(logged_event.processing_time_ms)
            
            # 构建 RawEvent 并重放
            raw_event = RawEvent(
                event_type=logged_event.event_type,
                symbol=logged_event.symbol,
                exchange=logged_event.exchange,
                event_time_ms=logged_event.event_time_ms,
                payload=logged_event.payload,
            )
            
            # 处理
            ok, _ = self.handle(raw_event)
            if ok:
                success_count += 1
            else:
                fail_count += 1
        
        self._state_trajectory.end_time_ms = self._authority.clock.now_ms()
        
        # 保存轨迹
        if self.storage_dir:
            self._state_trajectory.save(self.storage_dir / "replay_trajectory.json")
        
        is_success = fail_count == 0
        logger.info(
            f"Full replay complete: success={success_count}, "
            f"fail={fail_count}, trajectory_steps={len(self._state_trajectory.steps)}"
        )
        
        return is_success, self._state_trajectory
    
    # ===============================
    # 内部工具
    # ===============================
    
    def _get_current_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        if self._state_provider:
            return self._state_provider()
        return {"step": self._step_count, "kernel_time": self._authority.clock.now_ms()}
    
    def reset(self) -> None:
        """重置"""
        self._is_running = False
        self._mode = KernelMode.LIVE
        self._step_count = 0
        self._event_log.reset()
        self._state_capture.reset()
        self._state_trajectory = StateTrajectory()
        self._authority.clock.switch_to_live_mode()
        self._guard_system.reset()
    
    def __repr__(self) -> str:
        return (
            f"RuntimeKernel(mode={self._mode.value}, "
            f"steps={self._step_count}, "
            f"trajectory={len(self._state_trajectory.steps)})"
        )
