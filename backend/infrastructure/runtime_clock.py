"""
Runtime Clock - 统一时间源

核心问题：
Replay 和 Live 使用不同的时间源，导致特征计算结果不同。

解决方案：
1. 单一时间源
2. Replay 模式：按时间推进
3. Live 模式：从交易所时间转换
4. 所有组件共享同一个时间源
"""

from typing import Optional, Dict, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import time

from infrastructure.logging import get_logger

logger = get_logger("infrastructure.runtime_clock")


class ClockMode(Enum):
    """时钟模式"""
    REPLAY = "replay"    # 回测模式
    LIVE = "live"        # 实盘模式
    PAPER = "paper"      # 模拟盘模式


@dataclass
class TimeSnapshot:
    """时间快照"""
    tick: int
    timestamp_ms: int
    exchange_time: int
    available_at: int
    is_closed: bool
    closed_kline_timestamp: Optional[int] = None
    metadata: Dict = field(default_factory=dict)


class RuntimeClock:
    """
    统一时间源

    所有组件必须从这里获取时间，不能使用 datetime.now() 或 time.time()
    """

    def __init__(self, mode: ClockMode = ClockMode.REPLAY):
        self.mode = mode
        self._current_tick = 0
        self._current_timestamp_ms: int = 0
        self._exchange_time: int = 0
        self._network_latency_ms: int = 100
        self._processing_delay_ms: int = 50
        self._time_snapshots: List[TimeSnapshot] = []
        self._tick_callbacks: List[Callable[[TimeSnapshot], None]] = []
        self._last_closed_kline_timestamp: Optional[int] = None
        self._kline_interval_ms: int = 60000

    def reset(self):
        """重置时钟状态"""
        self._current_tick = 0
        self._current_timestamp_ms = 0
        self._exchange_time = 0
        self._time_snapshots = []
        self._last_closed_kline_timestamp = None

    def set_mode(self, mode: ClockMode):
        """设置时钟模式"""
        self.mode = mode
        logger.info(f"Runtime clock mode set to: {mode}")

    def set_kline_interval(self, interval_ms: int):
        """设置 K 线周期"""
        self._kline_interval_ms = interval_ms
        logger.info(f"Kline interval set to: {interval_ms}ms")

    def set_latency(self, network_latency_ms: int = 100, processing_delay_ms: int = 50):
        """设置延迟"""
        self._network_latency_ms = network_latency_ms
        self._processing_delay_ms = processing_delay_ms

    # === Replay Mode ===

    def advance_to(self, timestamp_ms: int, exchange_time: Optional[int] = None):
        """
        回测模式：推进到指定时间

        Args:
            timestamp_ms: 本地时间（模拟）
            exchange_time: 交易所时间（如果不提供，则等于 timestamp_ms）
        """
        if self.mode != ClockMode.REPLAY:
            raise RuntimeError("advance_to() only available in REPLAY mode")

        self._current_tick += 1
        self._current_timestamp_ms = timestamp_ms
        self._exchange_time = exchange_time if exchange_time is not None else timestamp_ms

        available_at = self._compute_available_at()

        is_closed = False
        if self._last_closed_kline_timestamp is None:
            self._last_closed_kline_timestamp = self._floor_to_kline(available_at)
        else:
            new_closed = self._floor_to_kline(available_at)
            if new_closed > self._last_closed_kline_timestamp:
                self._last_closed_kline_timestamp = new_closed
                is_closed = True

        snapshot = TimeSnapshot(
            tick=self._current_tick,
            timestamp_ms=self._current_timestamp_ms,
            exchange_time=self._exchange_time,
            available_at=available_at,
            is_closed=is_closed,
            closed_kline_timestamp=self._last_closed_kline_timestamp if is_closed else None
        )

        self._time_snapshots.append(snapshot)
        self._notify_tick(snapshot)

    def fast_forward(self, steps: int = 1, step_ms: int = 60000):
        """快速向前推进（Replay 模式）"""
        if self.mode != ClockMode.REPLAY:
            raise RuntimeError("fast_forward() only available in REPLAY mode")
        for _ in range(steps):
            self.advance_to(self._current_timestamp_ms + step_ms)

    # === Live Mode ===

    def update_from_exchange(self, exchange_time: int):
        """
        Live 模式：从交易所更新时间

        Args:
            exchange_time: 交易所时间戳
        """
        if self.mode not in (ClockMode.LIVE, ClockMode.PAPER):
            raise RuntimeError("update_from_exchange() only available in LIVE/PAPER mode")

        self._current_tick += 1
        self._current_timestamp_ms = int(time.time() * 1000)
        self._exchange_time = exchange_time

        available_at = self._compute_available_at()

        is_closed = False
        if self._last_closed_kline_timestamp is None:
            self._last_closed_kline_timestamp = self._floor_to_kline(available_at)
        else:
            new_closed = self._floor_to_kline(available_at)
            if new_closed > self._last_closed_kline_timestamp:
                self._last_closed_kline_timestamp = new_closed
                is_closed = True

        snapshot = TimeSnapshot(
            tick=self._current_tick,
            timestamp_ms=self._current_timestamp_ms,
            exchange_time=self._exchange_time,
            available_at=available_at,
            is_closed=is_closed,
            closed_kline_timestamp=self._last_closed_kline_timestamp if is_closed else None
        )

        self._time_snapshots.append(snapshot)
        self._notify_tick(snapshot)

    # === Time Access ===

    def now_ms(self) -> int:
        """获取当前可用时间（所有特征计算使用这个）"""
        return self._current_timestamp_ms if self._current_timestamp_ms > 0 else int(time.time() * 1000)

    def exchange_now_ms(self) -> int:
        """获取当前交易所时间"""
        return self._exchange_time if self._exchange_time > 0 else self.now_ms()

    def available_at_ms(self) -> int:
        """获取事件可用时间（考虑延迟）"""
        if self._current_timestamp_ms > 0:
            return self._compute_available_at()
        return int(time.time() * 1000) + self._processing_delay_ms

    def last_closed_kline_timestamp(self) -> Optional[int]:
        """获取最后一根已完成 K 线的开盘时间戳"""
        return self._last_closed_kline_timestamp

    def is_kline_closed(self) -> bool:
        """当前 tick 是否刚完成一根 K 线"""
        if not self._time_snapshots:
            return False
        return self._time_snapshots[-1].is_closed

    def current_snapshot(self) -> Optional[TimeSnapshot]:
        """获取当前时间快照"""
        return self._time_snapshots[-1] if self._time_snapshots else None

    def tick(self) -> int:
        """获取当前 tick 计数"""
        return self._current_tick

    # === Time Helpers ===

    def _compute_available_at(self) -> int:
        """计算事件可用时间"""
        if self.mode == ClockMode.REPLAY:
            return self._exchange_time + self._network_latency_ms + self._processing_delay_ms
        else:
            return self._current_timestamp_ms + self._processing_delay_ms

    def _floor_to_kline(self, timestamp_ms: int) -> int:
        """对齐到 K 线开始时间"""
        return (timestamp_ms // self._kline_interval_ms) * self._kline_interval_ms

    def is_time_available(self, feature_timestamp: int) -> bool:
        """检查特定时间戳的数据是否已可用"""
        return feature_timestamp <= self.available_at_ms()

    def get_safe_lookback_start(self, lookback_periods: int) -> int:
        """获取安全的回溯起始时间（不包含未来）"""
        current_available = self.available_at_ms()
        return current_available - (lookback_periods * self._kline_interval_ms)

    # === Callbacks ===

    def on_tick(self, callback: Callable[[TimeSnapshot], None]):
        """注册 tick 回调"""
        self._tick_callbacks.append(callback)

    def _notify_tick(self, snapshot: TimeSnapshot):
        """通知 tick 回调"""
        for callback in self._tick_callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                logger.error(f"Tick callback failed: {e}")

    # === Stats ===

    def get_statistics(self) -> Dict:
        """获取时钟统计信息"""
        return {
            "mode": self.mode.value,
            "current_tick": self._current_tick,
            "current_timestamp_ms": self._current_timestamp_ms,
            "exchange_time": self._exchange_time,
            "kline_interval_ms": self._kline_interval_ms,
            "last_closed_kline": self._last_closed_kline_timestamp,
            "total_ticks": len(self._time_snapshots)
        }


# Global clock instance
_clock_instance: Optional[RuntimeClock] = None


def get_clock() -> RuntimeClock:
    """获取全局时钟实例"""
    global _clock_instance
    if _clock_instance is None:
        _clock_instance = RuntimeClock()
    return _clock_instance


def set_clock_mode(mode: ClockMode):
    """设置全局时钟模式"""
    get_clock().set_mode(mode)


def now_ms() -> int:
    """便捷函数：获取当前可用时间"""
    return get_clock().now_ms()


def exchange_now_ms() -> int:
    """便捷函数：获取当前交易所时间"""
    return get_clock().exchange_now_ms()
