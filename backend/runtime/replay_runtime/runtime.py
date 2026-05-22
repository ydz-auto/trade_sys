"""
Replay Runtime - 时间因果一致的回放运行时（完整 Kernel）

核心改进：
1. Session 管理 - start_session/stop_session/step/pause/resume
2. Event Stream 驱动 - 真正的 replay loop
3. 注入机制 - Strategy/Feature/Execution Runtime
4. 状态查询 - get_session_state
5. 数据源加载 - load_dataset

架构定位：
- 全系统唯一的 Replay Driver
- 所有 replay 场景的入口：backtest/optimization/walk-forward/paper/trading/debug

重点防护：
- Replay 必须 100% 确定性
- 不能偷看未来数据
- Replay/Live 特征完全一致
- 事件严格按时间推进
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.runtime_clock import (
    RuntimeClock,
    ClockMode,
    get_clock,
    set_clock_mode,
    now_ms
)
from infrastructure.feature_availability import (
    SystematicAvailabilityGuard,
    get_systematic_guard
)
from infrastructure.label_isolation import (
    StrictLabelStore,
    get_label_store,
    set_label_store_mode
)
from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    get_immutable_snapshot_store,
    create_immutable_snapshot
)
from infrastructure.feature.warmup_determinism import (
    WarmupDeterminismManager,
    get_warmup_manager
)
from infrastructure.event.event_ordering import (
    EventOrderingDeterminism,
    get_event_ordering,
    create_deterministic_event
)
from infrastructure.verification.replay_live_verifier import (
    ReplayLiveConsistencyVerifier,
    create_consistency_verifier
)


logger = get_logger("replay_runtime")


class SessionStatus(Enum):
    """会话状态"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    WARMING_UP = "warming_up"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class EventType(Enum):
    """事件类型"""
    KLINE = "kline"
    TRADE = "trade"
    ORDER = "order"
    SIGNAL = "signal"
    DECISION = "decision"
    PORTFOLIO = "portfolio"
    CUSTOM = "custom"


@dataclass
class ReplayEvent:
    """回放事件"""
    event_id: str
    event_type: EventType
    timestamp_ms: int
    data: Dict[str, Any]
    source: str = "replay"


@dataclass
class ReplayConfig:
    """回放配置"""
    symbol: str = "BTCUSDT"
    start_time_ms: int = 0
    end_time_ms: int = 0
    speed: float = 1.0
    max_concurrent_tasks: int = 10
    checkpoint_interval: int = 10000
    warmup_periods: int = 100


@dataclass
class SessionState:
    """会话状态"""
    status: SessionStatus = SessionStatus.IDLE
    current_time_ms: int = 0
    total_events: int = 0
    processed_events: int = 0
    capital: float = 0.0
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)


class TimeCausalReplayRuntime:
    """
    时间因果一致的回放运行时（完整 Kernel）
    
    核心能力：
    - Session 管理
    - Event Stream 驱动
    - Runtime 注入
    - 状态查询
    
    重点防护：
    - Replay 必须 100% 确定性
    - 不能偷看未来数据
    - Replay/Live 特征完全一致
    - 事件严格按时间推进
    """
    
    def __init__(self, config: ReplayConfig = None):
        self.config = config or ReplayConfig()
        
        # 1. 初始化基础设施
        self._clock = get_clock()
        self._availability_guard = get_systematic_guard()
        self._label_store = get_label_store()
        self._snapshot_store = get_immutable_snapshot_store(config.symbol if config else "BTCUSDT")
        self._warmup_manager = get_warmup_manager()
        self._event_ordering = get_event_ordering()
        self._consistency_verifier = create_consistency_verifier(config.symbol if config else "BTCUSDT")
        
        # 2. 设置为 Replay 模式
        self._setup_replay_mode()
        
        # 3. Session 状态
        self._session_state = SessionState()
        
        # 4. 注入的 Runtime
        self._feature_runtime = None
        self._signal_runtime = None
        self._execution_runtime = None
        self._strategy = None
        
        # 5. Event 源和队列
        self._event_source = None
        self._event_iterator = None
        self._event_queue = asyncio.Queue()
        
        # 6. 控制标志
        self._running = False
        self._paused = False
        self._step_mode = False
        self._step_event = asyncio.Event()
        
        # 7. 回调函数
        self._on_event_callback = None
        self._on_step_callback = None
        self._on_session_start_callback = None
        self._on_session_stop_callback = None
        
        logger.info(f"Time-Causal Replay Runtime initialized for {self.config.symbol}")
    
    def _setup_replay_mode(self):
        """设置 Replay 模式"""
        set_clock_mode(ClockMode.REPLAY)
        set_label_store_mode("research")
    
    def attach_feature_runtime(self, feature_runtime):
        """注入 Feature Runtime"""
        self._feature_runtime = feature_runtime
        logger.info("Feature Runtime attached")
    
    def attach_signal_runtime(self, signal_runtime):
        """注入 Signal Runtime"""
        self._signal_runtime = signal_runtime
        logger.info("Signal Runtime attached")
    
    def attach_execution_runtime(self, execution_runtime):
        """注入 Execution Runtime"""
        self._execution_runtime = execution_runtime
        logger.info("Execution Runtime attached")
    
    def attach_strategy(self, strategy):
        """注入策略"""
        self._strategy = strategy
        logger.info(f"Strategy attached: {strategy.__class__.__name__}")
    
    def set_callbacks(
        self,
        on_event: Optional[Callable] = None,
        on_step: Optional[Callable] = None,
        on_session_start: Optional[Callable] = None,
        on_session_stop: Optional[Callable] = None
    ):
        """设置回调函数"""
        self._on_event_callback = on_event
        self._on_step_callback = on_step
        self._on_session_start_callback = on_session_start
        self._on_session_stop_callback = on_session_stop
    
    async def start_session(
        self,
        symbol: Optional[str] = None,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
        initial_capital: float = 10000.0,
        data_path: Optional[str] = None
    ):
        """
        创建并启动 replay session
        
        Args:
            symbol: 交易对
            start_time_ms: 开始时间（毫秒）
            end_time_ms: 结束时间（毫秒）
            initial_capital: 初始资金
            data_path: 数据源路径（可选）
        """
        logger.info(f"Starting replay session for {symbol or self.config.symbol}")
        
        # 1. 更新配置
        if symbol:
            self.config.symbol = symbol
        if start_time_ms:
            self.config.start_time_ms = start_time_ms
        if end_time_ms:
            self.config.end_time_ms = end_time_ms
        
        # 2. 重置状态
        self._session_state = SessionState(
            status=SessionStatus.INITIALIZING,
            capital=initial_capital,
            equity_curve=[initial_capital]
        )
        
        # 3. 初始化基础设施
        await self._initialize_session()
        
        # 4. 加载数据源
        if data_path:
            await self.load_dataset(data_path)
        
        # 5. 触发回调
        if self._on_session_start_callback:
            await self._on_session_start_callback(self._session_state)
        
        self._session_state.status = SessionStatus.WARMING_UP
        
        # 6. 执行预热
        await self._perform_warmup()
        
        self._session_state.status = SessionStatus.RUNNING
        logger.info("Replay session started")
    
    async def _initialize_session(self):
        """初始化会话"""
        # 重置时钟
        self._clock.reset()
        self._clock.advance_to(self.config.start_time_ms)
        
        # 重置其他基础设施
        self._event_ordering.reset()
        self._warmup_manager.reset()
        
        # 通知注入的 Runtime 初始化
        if self._feature_runtime:
            await self._feature_runtime.initialize(self.config.symbol, mode="replay")
        
        if self._signal_runtime:
            await self._signal_runtime.initialize()
        
        if self._execution_runtime:
            await self._execution_runtime.initialize(initial_capital=self._session_state.capital)
    
    async def _perform_warmup(self):
        """执行预热（防止冷启动偏差）"""
        logger.info(f"Performing warmup for {self.config.warmup_periods} periods...")
        
        if self._event_iterator is None:
            return
        
        warmup_count = 0
        async for event in self._event_iterator:
            if warmup_count >= self.config.warmup_periods:
                break
            
            # 推进时钟
            self._clock.advance_to(event.timestamp_ms)
            
            # 只更新特征，不生成信号
            if self._feature_runtime:
                await self._feature_runtime.update(event)
            
            warmup_count += 1
        
        logger.info(f"Warmup completed: {warmup_count} events processed")
    
    async def load_dataset(self, data_path: str):
        """加载事件数据源"""
        logger.info(f"Loading dataset from: {data_path}")
        
        try:
            import pandas as pd
            from pathlib import Path
            
            df = pd.read_parquet(data_path)
            
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            elif 'open_time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # 创建事件迭代器
            async def event_generator():
                for _, row in df.iterrows():
                    ts_ms = int(row['timestamp'].timestamp() * 1000)
                    if ts_ms < self.config.start_time_ms:
                        continue
                    if ts_ms > self.config.end_time_ms:
                        break
                    
                    event = ReplayEvent(
                        event_id=f"kline_{ts_ms}",
                        event_type=EventType.KLINE,
                        timestamp_ms=ts_ms,
                        data={
                            'open': float(row.get('open', 0)),
                            'high': float(row.get('high', 0)),
                            'low': float(row.get('low', 0)),
                            'close': float(row.get('close', 0)),
                            'volume': float(row.get('volume', 0)),
                            'symbol': self.config.symbol
                        }
                    )
                    yield event
            
            self._event_iterator = event_generator()
            self._session_state.total_events = len(df)
            
            logger.info(f"Dataset loaded: {len(df)} events")
            
        except Exception as e:
            logger.error(f"Failed to load dataset: {e}")
            raise
    
    async def run_event_stream(self):
        """
        运行事件流 - 核心 replay loop
        
        这是真正的 Kernel 入口！
        """
        if self._session_state.status != SessionStatus.RUNNING:
            raise RuntimeError("Session not running. Call start_session() first.")
        
        if self._event_iterator is None:
            raise RuntimeError("No event source loaded. Call load_dataset() first.")
        
        logger.info("Starting event stream...")
        
        async for event in self._event_iterator:
            # 检查停止信号
            if self._session_state.status in [SessionStatus.STOPPED, SessionStatus.ERROR]:
                break
            
            # 检查暂停信号
            while self._paused and not self._step_mode:
                await asyncio.sleep(0.01)
            
            # 单步模式：等待 step() 调用
            if self._step_mode:
                await self._step_event.wait()
                self._step_event.clear()
            
            # 处理事件
            await self._process_event(event)
            
            # 控制速度
            if self.config.speed != float('inf'):
                await asyncio.sleep(0.001 / self.config.speed)
        
        logger.info("Event stream completed")
    
    async def _process_event(self, event: ReplayEvent):
        """处理单个事件（时间因果安全）"""
        # 1. 时间因果检查
        if event.timestamp_ms < self._clock.available_at_ms():
            logger.warning(f"Event time {event.timestamp_ms} is in the past! Skipping.")
            return
        
        # 2. 推进时钟
        self._clock.advance_to(event.timestamp_ms)
        
        # 3. 事件确定性排序
        ordered_event = create_deterministic_event(
            event=event.data,
            timestamp_ms=event.timestamp_ms
        )
        
        # 4. 特征计算
        if self._feature_runtime:
            await self._feature_runtime.update(ordered_event)
        
        # 5. 信号生成
        signal = None
        if self._signal_runtime and self._strategy:
            features = await self._feature_runtime.get_features(event.timestamp_ms)
            signal = await self._signal_runtime.generate_signal(
                self._strategy,
                features,
                event.timestamp_ms
            )
        
        # 6. 执行
        if signal and self._execution_runtime:
            trade_result = await self._execution_runtime.execute_signal(signal)
            
            if trade_result:
                self._session_state.trades.append(trade_result)
                self._session_state.capital += trade_result.get('pnl', 0)
        
        # 7. 更新状态
        self._session_state.current_time_ms = event.timestamp_ms
        self._session_state.processed_events += 1
        self._session_state.equity_curve.append(self._session_state.capital)
        
        # 8. 生成不可变快照
        snapshot = self.create_snapshot({
            'capital': self._session_state.capital,
            'event_count': self._session_state.processed_events,
            'timestamp_ms': event.timestamp_ms
        })
        
        # 9. 一致性验证
        self._consistency_verifier.record_replay(event.timestamp_ms, snapshot)
        
        # 10. 触发回调
        if self._on_event_callback:
            await self._on_event_callback(event, self._session_state)
        
        # 11. 检查点
        if self._session_state.processed_events % self.config.checkpoint_interval == 0:
            logger.info(f"Checkpoint: {self._session_state.processed_events} events processed")
    
    async def step(self):
        """单步执行"""
        if self._step_mode and self._session_state.status == SessionStatus.RUNNING:
            self._step_event.set()
    
    async def pause(self):
        """暂停回放"""
        self._paused = True
        self._session_state.status = SessionStatus.PAUSED
        logger.info("Replay paused")
    
    async def resume(self):
        """恢复回放"""
        self._paused = False
        self._session_state.status = SessionStatus.RUNNING
        logger.info("Replay resumed")
    
    async def stop(self):
        """停止回放"""
        self._running = False
        self._paused = False
        self._session_state.status = SessionStatus.STOPPED
        
        # 清理资源
        self._event_iterator = None
        
        # 触发回调
        if self._on_session_stop_callback:
            await self._on_session_stop_callback(self._session_state)
        
        logger.info("Replay stopped")
    
    def enable_step_mode(self, enable: bool = True):
        """启用/禁用单步模式"""
        self._step_mode = enable
        if enable:
            self._step_event = asyncio.Event()
            logger.info("Step mode enabled")
    
    def get_session_state(self) -> SessionState:
        """获取会话状态"""
        return self._session_state
    
    def create_snapshot(
        self,
        features: Dict[str, Any],
        snapshot_id: Optional[str] = None
    ) -> ImmutableFeatureSnapshot:
        """创建不可变快照"""
        snapshot = create_immutable_snapshot(
            features=features,
            snapshot_id=snapshot_id,
            metadata={
                "symbol": self.config.symbol,
                "mode": "replay",
                "timestamp": self._clock.available_at_ms()
            }
        )
        self._snapshot_store.store(snapshot)
        return snapshot
    
    async def run_backtest(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        start_time_ms: int,
        end_time_ms: int,
        initial_capital: float = 10000.0,
        data_path: Optional[str] = None
    ) -> SessionState:
        """
        运行完整回测（便捷方法）
        
        Args:
            symbol: 交易对
            strategy_id: 策略 ID
            params: 策略参数
            start_time_ms: 开始时间
            end_time_ms: 结束时间
            initial_capital: 初始资金
            data_path: 数据源路径
        
        Returns:
            SessionState: 回测结果
        """
        # 1. 加载策略
        from runtime.strategy_registry import get_strategy
        self._strategy = get_strategy(strategy_id, params)
        
        # 2. 启动会话
        await self.start_session(
            symbol=symbol,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            initial_capital=initial_capital,
            data_path=data_path
        )
        
        # 3. 运行事件流
        await self.run_event_stream()
        
        # 4. 返回结果
        return self.get_session_state()


# 全局实例
_tc_replay_runtime: Optional[TimeCausalReplayRuntime] = None


def get_replay_runtime(config: Optional[ReplayConfig] = None) -> TimeCausalReplayRuntime:
    """获取回放运行时（工厂函数）"""
    global _tc_replay_runtime
    if _tc_replay_runtime is None:
        if config is None:
            config = ReplayConfig()
        _tc_replay_runtime = TimeCausalReplayRuntime(config)
    return _tc_replay_runtime


async def main():
    """示例：使用 ReplayRuntime 运行回测"""
    logger.info("=" * 60)
    logger.info("Replay Runtime - Complete Kernel")
    logger.info("=" * 60)
    
    # 1. 获取 Runtime
    runtime = get_replay_runtime()
    
    # 2. 注入依赖
    from runtime.feature_matrix_runtime import get_feature_matrix_runtime
    from runtime.signal_runtime import get_signal_runtime
    from runtime.execution_runtime import get_execution_runtime
    
    runtime.attach_feature_runtime(get_feature_matrix_runtime())
    runtime.attach_signal_runtime(get_signal_runtime())
    runtime.attach_execution_runtime(get_execution_runtime())
    
    # 3. 设置回调
    async def on_event(event, state):
        if state.processed_events % 1000 == 0:
            logger.info(f"Processed {state.processed_events} events, Capital: {state.capital:.2f}")
    
    runtime.set_callbacks(on_event=on_event)
    
    # 4. 运行回测
    result = await runtime.run_backtest(
        symbol="BTCUSDT",
        strategy_id="rsi_oversold",
        params={"period": 14, "oversold": 30},
        start_time_ms=0,
        end_time_ms=0,
        initial_capital=10000.0,
        data_path="/path/to/features.parquet"
    )
    
    logger.info(f"Backtest completed: Total return: {(result.capital - 10000)/10000*100:.2f}%")


if __name__ == "__main__":
    asyncio.run(main())