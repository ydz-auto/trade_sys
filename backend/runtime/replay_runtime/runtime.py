"""
Replay Runtime - 时间因果一致的回放运行时（完整 Kernel）

核心改进：
1. Session 管理 - start_session/stop_session/step/pause/resume
2. Event Stream 驱动 - 真正的 replay loop
3. 注入机制 - Strategy/Feature/Execution Runtime
4. 状态查询 - get_session_state
5. 数据源加载 - load_dataset
6. 集成 BacktestExecutionEngine - 支持真实交易成本模型

架构定位：
- 全系统唯一的 Replay Driver
- 所有 replay 场景的入口：backtest/optimization/walk-forward/paper/trading/debug

重点防护：
- Replay 必须 100% 确定性
- 不能偷看未来数据
- Replay/Live 特征完全一致
- 事件严格按时间推进
- 交易成本模型：手续费、滑点、保证金、爆仓、资金费
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import asyncio
from datetime import datetime

from infrastructure.logging import get_logger
from infrastructure.utilities.runtime_clock import (
    RuntimeClock,
    ClockMode,
    get_clock,
    set_clock_mode,
    now_ms
)
from infrastructure.utilities.time_authority import (
    TimeAuthority,
    get_time_authority,
    ensure_time_ms,
    normalize_time_ms,
    check_monotonic
)
from domain.feature.availability import (
    SystematicAvailabilityGuard,
    get_systematic_guard
)
from domain.feature.label_isolation import (
    StrictLabelStore,
    get_label_store,
    set_label_store_mode
)
from infrastructure.storage.immutable_snapshot import (
    ImmutableFeatureSnapshot,
    get_immutable_snapshot_store,
    create_immutable_snapshot
)
from domain.feature.infrastructure.warmup_determinism import (
    WarmupDeterminismManager,
    get_warmup_manager
)
from domain.event.kernel_event.event_ordering import (
    EventOrderingDeterminism,
    get_event_ordering,
    create_deterministic_event
)
from runtime.verification_runtime.replay_live_verifier import (
    ReplayLiveConsistencyVerifier,
    create_consistency_verifier
)

# 引入回测执行引擎
from runtime.replay_runtime.models import (
    BacktestExecutionEngine,
    create_backtest_engine,
    OrderSide,
    OrderType
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
    
    # 账户信息（来自 BacktestExecutionEngine）
    capital: float = 0.0
    equity: float = 0.0
    wallet_balance: float = 0.0
    used_margin: float = 0.0
    available_balance: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    total_fees: float = 0.0
    total_funding: float = 0.0
    
    # 交易记录和曲线
    equity_curve: List[Dict[str, Any]] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    positions: List[Dict[str, Any]] = field(default_factory=list)
    
    # 错误和指标
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
    - 时间类型统一使用 int64 ms
    """
    
    def __init__(self, config: ReplayConfig = None):
        self.config = config or ReplayConfig()
        
        # 1. 初始化基础设施（时间权威优先）
        self._time_authority = get_time_authority()
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
        
        # 5. 回测执行引擎（核心）
        self._backtest_engine = None
        
        # 6. Event 源和队列
        self._event_source = None
        self._event_iterator = None
        self._warmup_data = None  # 预热数据副本（不消耗主迭代器）
        self._event_queue = asyncio.Queue()
        
        # 7. 控制标志
        self._running = False
        self._paused = False
        self._step_mode = False
        self._step_event = asyncio.Event()
        
        # 8. 回调函数
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
        
        # 1. 更新配置（强制时间归一化）
        if symbol:
            self.config.symbol = symbol
        
        # 强制转换时间参数为 int64 ms
        if start_time_ms:
            self.config.start_time_ms = ensure_time_ms(
                start_time_ms,
                source="api",
                field_name="start_time_ms"
            )
        if end_time_ms:
            self.config.end_time_ms = ensure_time_ms(
                end_time_ms,
                source="api",
                field_name="end_time_ms"
            )
        
        # 验证时间范围
        if self.config.start_time_ms >= self.config.end_time_ms:
            raise ValueError(
                f"start_time_ms ({self.config.start_time_ms}) >= end_time_ms ({self.config.end_time_ms})"
            )
        
        # 2. 重置状态
        self._session_state = SessionState(
            status=SessionStatus.INITIALIZING,
            capital=initial_capital,
            equity_curve=[initial_capital]
        )
        
        # 3. 初始化基础设施
        await self._initialize_session()
        
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
        # 重置时钟（先切回 REPLAY 模式，防止被其他 Runtime 改成 LIVE）
        set_clock_mode(ClockMode.REPLAY)
        self._clock.reset()
        self._clock.advance_to(self.config.start_time_ms)
        
        # 重置时间权威的单调检查状态（关键！防止多窗口之间时间冲突）
        self._time_authority.reset_monotonic()
        self._time_authority.start_session(self.config.start_time_ms)
        
        # 重置 snapshot store（防止多窗口之间 snapshot 冲突）
        self._snapshot_store.reset()
        
        # 重置其他基础设施
        self._event_ordering.reset_sequence()
        self._warmup_manager.reset_all()
        
        # 初始化回测执行引擎（核心）
        self._backtest_engine = create_backtest_engine(
            symbol=self.config.symbol,
            initial_capital=self._session_state.capital,
            default_leverage=5,
            maker_fee=0.0002,
            taker_fee=0.0005,
            base_slippage_bps=2.0,
            enable_slippage=True,
            enable_liquidation=True,
            enable_funding=True
        )
        logger.info(f"BacktestExecutionEngine initialized with capital: {self._session_state.capital}")
        
        # 通知注入的 Runtime 初始化
        if self._feature_runtime:
            await self._feature_runtime.initialize(self.config.symbol, mode="replay")
        
        if self._signal_runtime:
            await self._signal_runtime.initialize()
        
        if self._execution_runtime:
            await self._execution_runtime.initialize()
    
    async def _perform_warmup(self):
        """执行预热（防止冷启动偏差）
        
        注意：预热使用数据的 COPY，不消耗主循环迭代器。
        合成数据测试建议 warmup_periods=0。
        """
        logger.info(f"Performing warmup for {self.config.warmup_periods} periods...")
        
        if self.config.warmup_periods <= 0:
            logger.info("Warmup skipped (warmup_periods <= 0)")
            return
        
        if self._warmup_data is None or len(self._warmup_data) == 0:
            logger.info("Warmup skipped (no warmup data available)")
            return
        
        set_clock_mode(ClockMode.REPLAY)
        
        warmup_data = list(self._warmup_data[:self.config.warmup_periods])
        logger.info(f"Warmup data prepared: {len(warmup_data)} events (copy)")
        
        for event in warmup_data:
            self._clock.advance_to(event.timestamp_ms)
            
            if self._feature_runtime:
                event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
                feature_event = {
                    "event_type": event_type_str,
                    "timestamp_ms": event.timestamp_ms,
                    "data": event.data,
                }
                await self._feature_runtime.update(feature_event)
        
        logger.info(f"Warmup completed: {len(warmup_data)} events processed (using copy)")
    
    async def load_dataset(self, data_path: str):
        """加载事件数据源（强制时间归一化）"""
        logger.info(f"Loading dataset from: {data_path}")
        
        try:
            import pandas as pd
            from pathlib import Path
            
            df = pd.read_parquet(data_path)
            
            # 时间字段检测和归一化
            timestamp_col = None
            if 'timestamp' in df.columns:
                timestamp_col = 'timestamp'
            elif 'open_time' in df.columns:
                timestamp_col = 'open_time'
            elif 'time' in df.columns:
                timestamp_col = 'time'
            elif 'event_time' in df.columns:
                timestamp_col = 'event_time'
            
            if timestamp_col is None:
                raise ValueError("No timestamp column found in dataset")
            
            # 统一转换为 int64 ms
            df['timestamp_ms'] = df[timestamp_col].apply(
                lambda x: normalize_time_ms(x, source="parquet", field_name="timestamp")
            )
            
            df = df.sort_values('timestamp_ms').reset_index(drop=True)
            
            # 过滤时间范围
            df = df[
                (df['timestamp_ms'] >= self.config.start_time_ms) & 
                (df['timestamp_ms'] <= self.config.end_time_ms)
            ]
            
            # 创建事件迭代器（强制单调检查）
            warmup_events = []
            
            async def event_generator():
                for _, row in df.iterrows():
                    ts_ms = int(row['timestamp_ms'])
                    
                    # 单调递增检查
                    check_monotonic(ts_ms)
                    
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
                    warmup_events.append(event)
                    yield event
            
            self._event_iterator = event_generator()
            self._warmup_data = warmup_events  # 保存预热数据副本
            self._session_state.total_events = len(df)
            
            logger.info(f"Dataset loaded: {len(df)} events, "
                        f"time range: {self.config.start_time_ms} - {self.config.end_time_ms}")
            
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
        try:
            # 0. 强制验证时间类型（Runtime 内部必须是 int）
            if not isinstance(event.timestamp_ms, int):
                raise TypeError(
                    f"Event timestamp must be int, got {type(event.timestamp_ms).__name__}: {event.timestamp_ms}"
                )
            
            # 1. 时间因果检查
            if event.timestamp_ms < self._clock.available_at_ms():
                logger.warning(f"Event time {event.timestamp_ms} is in the past! Skipping.")
                return
            
            # 2. 单调递增检查
            check_monotonic(event.timestamp_ms)
            
            # 3. 推进时钟
            self._clock.advance_to(event.timestamp_ms)
            
            # 4. 事件确定性排序
            event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
            ordered_event = create_deterministic_event(
                event_type=event_type_str,
                timestamp=event.timestamp_ms,
                data=event.data,
                symbol=self.config.symbol,
            )
            
            # 5. 特征计算 — 直接用原始 ReplayEvent 传给 FeatureRuntime（它有 timestamp_ms）
            if self._feature_runtime:
                feature_event = {
                    "event_type": event_type_str,
                    "timestamp_ms": event.timestamp_ms,
                    "data": event.data,
                }
                await self._feature_runtime.update(feature_event)
            
            # 6. 信号生成
            signal = None
            if self._signal_runtime and self._strategy:
                features = await self._feature_runtime.get_features(event.timestamp_ms)
                signal = await self._signal_runtime.generate_signal(
                    self._strategy,
                    features,
                    event.timestamp_ms
                )
            
            # 7. 执行（使用 BacktestExecutionEngine）
            if signal and self._backtest_engine:
                try:
                    signal_type = signal.get('signal_type', 'buy')
                    size = signal.get('size', 0.001)
                    
                    # 从多个可能的字段获取价格
                    price = event.data.get('price', 0.0) or \
                            event.data.get('close', 0.0) or \
                            signal.get('price', 0.0)
                    
                    if price <= 0:
                        logger.warning(f"No price available for signal execution")
                    else:
                        side = OrderSide.BUY if signal_type == 'buy' else OrderSide.SELL
                        
                        trade_result = await self._backtest_engine.execute_order(
                            side=side,
                            size=size,
                            price=price,
                            order_type=OrderType.MARKET,
                            is_maker=False,
                            timestamp_ms=event.timestamp_ms,
                            current_funding_rate=event.data.get('funding_rate', 0.0),
                            avg_daily_volume=event.data.get('volume', 1000000.0),
                            current_spread_bps=2.0,
                            volatility=0.002,
                            orderbook_depth=100.0
                        )
                        
                        if trade_result.success:
                            # 记录交易
                            trade_dict = {
                                'order_id': trade_result.order_id,
                                'timestamp_ms': event.timestamp_ms,
                                'side': trade_result.side.value,
                                'requested_price': trade_result.requested_price,
                                'execution_price': trade_result.execution_price,
                                'size': trade_result.size,
                                'fee': trade_result.fee,
                                'fee_rate': trade_result.fee_rate,
                                'slippage_bps': trade_result.slippage_bps,
                                'pnl': trade_result.pnl,
                                'realized_pnl': trade_result.realized_pnl,
                                'liquidation_occurred': trade_result.liquidation_occurred,
                                'position_before': trade_result.position_before,
                                'position_after': trade_result.position_after
                            }
                            self._session_state.trades.append(trade_dict)
                            
                            # 如果发生爆仓，记录错误
                            if trade_result.liquidation_occurred:
                                error_msg = f"Liquidation occurred at {event.timestamp_ms}: {trade_result.liquidation_details}"
                                logger.error(error_msg)
                                self._session_state.errors.append(error_msg)
                        else:
                            # 执行失败，记录错误
                            error_msg = f"Order execution failed: {trade_result.error}"
                            logger.error(error_msg)
                            self._session_state.errors.append(error_msg)
                            
                except Exception as e:
                    error_msg = f"Error executing signal: {str(e)}"
                    logger.error(error_msg)
                    import traceback
                    logger.error(traceback.format_exc())
                    self._session_state.errors.append(error_msg)
            
            # 8. 更新状态（从 BacktestExecutionEngine 获取）
            self._session_state.current_time_ms = event.timestamp_ms
            self._session_state.processed_events += 1
            
            if self._backtest_engine:
                account_state = self._backtest_engine.get_account_state()
                self._session_state.capital = account_state.get('current_balance', 0.0)
                self._session_state.equity = account_state.get('equity', 0.0)
                self._session_state.wallet_balance = account_state.get('current_balance', 0.0)
                self._session_state.used_margin = account_state.get('used_margin', 0.0)
                self._session_state.available_balance = account_state.get('available_balance', 0.0)
                self._session_state.unrealized_pnl = account_state.get('unrealized_pnl', 0.0)
                self._session_state.realized_pnl = account_state.get('total_realized_pnl', 0.0)
                self._session_state.total_fees = account_state.get('total_fees', 0.0)
                self._session_state.total_funding = account_state.get('total_funding', 0.0)
                
                # 更新仓位记录
                position = self._backtest_engine.get_position()
                if position:
                    self._session_state.positions.append({
                        'timestamp_ms': event.timestamp_ms,
                        'quantity': position.quantity,
                        'average_price': position.average_price,
                        'current_price': position.current_price,
                        'leverage': position.leverage,
                        'margin': position.margin,
                        'liquidation_price': position.liquidation_price,
                        'unrealized_pnl': position.unrealized_pnl
                    })
            
            # 记录权益曲线
            self._session_state.equity_curve.append({
                'timestamp_ms': event.timestamp_ms,
                'equity': self._session_state.equity,
                'capital': self._session_state.capital,
                'unrealized_pnl': self._session_state.unrealized_pnl,
                'realized_pnl': self._session_state.realized_pnl,
                'fees': self._session_state.total_fees
            })
            
            # 8. 生成不可变快照
            snapshot = self.create_snapshot(
                features={
                    'capital': self._session_state.capital,
                    'event_count': self._session_state.processed_events,
                    'timestamp_ms': event.timestamp_ms
                }
            )
            
            # 9. 一致性验证
            self._consistency_verifier.record_replay(event.timestamp_ms, snapshot)
            
            # 10. 触发回调
            if self._on_event_callback:
                await self._on_event_callback(event, self._session_state)
            
            # 11. 检查点
            if self._session_state.processed_events % self.config.checkpoint_interval == 0:
                logger.info(f"Checkpoint: {self._session_state.processed_events} events processed")
        except Exception as e:
            error_msg = f"Error processing event {event.event_id} at {event.timestamp_ms}: {str(e)}"
            logger.error(error_msg)
            import traceback
            logger.error(traceback.format_exc())
            self._session_state.errors.append(error_msg)
    
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
        return create_immutable_snapshot(
            self.config.symbol,
            features,
            self._clock.available_at_ms(),
            source="replay",
        )

    async def snapshot(self) -> Dict[str, Any]:
        ts = now_ms()
        return {
            "name": "replay_runtime",
            "state": self._session_state.status.value,
            "timestamp": ts,
            "business_state": {
                "status": self._session_state.status.value,
                "current_time_ms": self._session_state.current_time_ms,
                "total_events": self._session_state.total_events,
                "processed_events": self._session_state.processed_events,
                "capital": self._session_state.capital,
                "equity_curve": list(self._session_state.equity_curve),
                "trades": list(self._session_state.trades),
                "errors": list(self._session_state.errors),
                "metrics": dict(self._session_state.metrics),
            },
        }

    async def recover(self, checkpoint: Any = None) -> None:
        if not isinstance(checkpoint, dict):
            return
        business_state = checkpoint.get("business_state")
        if business_state:
            self._session_state.status = SessionStatus(business_state.get("status", SessionStatus.IDLE.value))
            self._session_state.current_time_ms = business_state.get("current_time_ms", 0)
            self._session_state.total_events = business_state.get("total_events", 0)
            self._session_state.processed_events = business_state.get("processed_events", 0)
            self._session_state.capital = business_state.get("capital", 0.0)
            self._session_state.equity_curve = list(business_state.get("equity_curve", []))
            self._session_state.trades = list(business_state.get("trades", []))
            self._session_state.errors = list(business_state.get("errors", []))
            self._session_state.metrics = dict(business_state.get("metrics", {}))

    async def run_backtest(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        start_time_ms: int,
        end_time_ms: int,
        initial_capital: float = 10000.0,
        data_path: Optional[str] = None,
        event_iterator=None,
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
            data_path: 数据源路径（如果 event_iterator 为 None）
            event_iterator: 可选的异步事件迭代器（优先级高于 data_path）
        
        Returns:
            SessionState: 回测结果
        """
        from engines.compute.strategy.registry import get_strategy
        self._strategy = get_strategy(strategy_id, params)
        
        await self.start_session(
            symbol=symbol,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
            initial_capital=initial_capital,
        )
        
        if event_iterator is not None:
            self._event_iterator = event_iterator
            self._session_state.total_events = 0
        elif data_path:
            await self.load_dataset(data_path)
        else:
            raise ValueError("Either data_path or event_iterator must be provided")
        
        await self.run_event_stream()
        
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
    logger.info("=" * 60)
    logger.info("Replay Runtime - Standby Mode")
    logger.info("=" * 60)

    runtime = get_replay_runtime()

    from runtime.feature_runtime import get_feature_runtime, FeatureConfig, FeatureMode
    from runtime.signal_runtime import get_signal_runtime
    from runtime.execution_runtime import get_execution_runtime

    feature_config = FeatureConfig(symbol="BTCUSDT", mode=FeatureMode.REPLAY)
    runtime.attach_feature_runtime(get_feature_runtime(feature_config))
    runtime.attach_signal_runtime(get_signal_runtime())
    runtime.attach_execution_runtime(get_execution_runtime())

    logger.info("Replay Runtime ready. Waiting for backtest requests...")
    logger.info("Use the API or CLI to submit a backtest job with valid time range.")

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Replay Runtime shutting down...")


if __name__ == "__main__":
    asyncio.run(main())