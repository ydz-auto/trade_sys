"""
Optimization Backtest Engine - 基于 Runtime 的回测引擎

核心原则：
1. 走现有的 shared/replay/ 架构
2. 调用 ReplayOrchestrator 进行回放
3. 走 SignalRuntime 和 ExecutionRuntime 的业务逻辑

架构：
    OptimizationService
        ↓
    shared/replay/orchestrator.py
        ↓
    shared/replay/market_event_emitter.py (发出真实事件)
        ↓
    services/strategy_service/ (信号生成)
        ↓
    services/execution_service/ (订单执行)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import asyncio
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("optimization_backtest_engine")


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 10000.0
    commission: float = 0.0005
    slippage: float = 0.0002
    latency_ms: float = 50.0
    position_size: float = 0.3
    stop_loss: float = 0.02
    take_profit: float = 0.04
    max_hold_hours: int = 48
    leverage: float = 1.0
    
    enable_slippage: bool = True
    enable_latency: bool = True
    enable_partial_fill: bool = True
    enable_feature_guard: bool = True
    
    # 数据重采样配置
    resample_freq: Optional[str] = None  # 例如 "10min", "1h", "1d" 等，None 表示不重采样


@dataclass
class BacktestTrade:
    """回测交易记录"""
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    direction: str
    pnl: float
    pnl_pct: float
    exit_reason: str
    slippage: float = 0.0
    latency_ms: float = 0.0


@dataclass
class BacktestResult:
    """回测结果"""
    symbol: str
    strategy_id: str
    params: Dict[str, Any]
    
    total_return: float = 0.0
    annualized_return: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_hold_hours: float = 0.0
    
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    
    leakage_stats: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "strategy_id": self.strategy_id,
            "params": self.params,
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "max_drawdown": self.max_drawdown,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "avg_hold_hours": self.avg_hold_hours,
            "leakage_stats": self.leakage_stats,
        }


class OptimizationBacktestEngine:
    """
    优化回测引擎
    
    使用现有的 shared/replay/ 架构进行回测。
    
    用法：
    ```python
    engine = OptimizationBacktestEngine(config)
    result = await engine.run(
        symbol="BTCUSDT",
        strategy_id="rsi_oversold",
        params={"period": 14, "oversold": 30},
        start_time=1704067200000,
        end_time=1735689600000,
    )
    ```
    """
    
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        
        self._capital = 0.0
        self._position: Optional[Dict[str, Any]] = None
        self._trades: List[BacktestTrade] = []
        self._equity_curve: List[float] = []
        self._current_price = 0.0
        self._current_time: Optional[datetime] = None
        self._current_timestamp: int = 0
        
        self._signal_handler: Optional[Callable] = None
        self._leakage_stats: Dict[str, int] = {"blocked": 0, "allowed": 0}
        
        self._feature_guard = None
        self._replay_orchestrator = None
    
    async def initialize(self):
        """初始化 - 使用现有的 shared/replay/ 组件"""
        if self.config.enable_feature_guard:
            try:
                from shared.replay.feature_availability_guard import get_feature_availability_guard
                self._feature_guard = get_feature_availability_guard()
                logger.info("Feature guard initialized")
            except Exception as e:
                logger.warning(f"Feature guard init failed: {e}")
        
        try:
            from shared.replay.orchestrator import get_replay_orchestrator
            self._replay_orchestrator = await get_replay_orchestrator()
            logger.info("Replay orchestrator initialized")
        except Exception as e:
            logger.warning(f"Replay orchestrator init failed: {e}")
    
    async def run(
        self,
        symbol: str,
        strategy_id: str,
        params: Dict[str, Any],
        start_time: int,
        end_time: int,
        data_path: Optional[Path] = None,
    ) -> BacktestResult:
        """
        运行回测
        
        使用 shared/replay/market_event_emitter.py 发出事件流。
        """
        self._reset()
        
        self._signal_handler = self._create_signal_handler(strategy_id, params)
        
        data_path = data_path or self._get_default_data_path(symbol)
        
        if not data_path.exists():
            logger.error(f"Data not found: {data_path}")
            return BacktestResult(symbol=symbol, strategy_id=strategy_id, params=params)
        
        try:
            from shared.replay.market_event_emitter import MarketEventEmitter, EmitterConfig, EmitMode
            
            emitter = MarketEventEmitter(EmitterConfig(
                emit_mode=EmitMode.INSTANT,
                include_trades=False,
                include_funding=True,
            ))
            
            async for event in emitter.emit_from_feature_parquet(
                parquet_path=data_path,
                symbol=symbol,
                exchange="binance",
                start_time=start_time,
                end_time=end_time,
            ):
                await self._process_event(event)
        
        except ImportError:
            logger.warning("MarketEventEmitter not available, using fallback")
            await self._run_fallback(data_path, symbol, start_time, end_time)
        
        if self._position:
            await self._close_position(
                price=self._current_price,
                time=self._current_time,
                reason="end",
            )
        
        result = self._calculate_result(symbol, strategy_id, params)
        result.leakage_stats = self._leakage_stats
        
        return result
    
    async def _run_fallback(
        self,
        data_path: Path,
        symbol: str,
        start_time: int,
        end_time: int,
    ):
        """备用回测方法 - 直接读取 Parquet"""
        df = pd.read_parquet(data_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        start_dt = pd.Timestamp(start_time, unit='ms') if isinstance(start_time, int) else pd.Timestamp(start_time)
        end_dt = pd.Timestamp(end_time, unit='ms') if isinstance(end_time, int) else pd.Timestamp(end_time)
        
        df = df[(df['timestamp'] >= start_dt) & (df['timestamp'] <= end_dt)]
        
        # 数据重采样
        if self.config.resample_freq and not df.empty:
            df = self._resample_data(df, self.config.resample_freq)
        
        for idx, row in df.iterrows():
            ts = int(row['timestamp'].timestamp() * 1000) if isinstance(row['timestamp'], pd.Timestamp) else int(row['timestamp'])
            
            self._current_price = float(row.get('close', 0))
            self._current_time = datetime.fromtimestamp(ts / 1000)
            self._current_timestamp = ts
            
            if self._position:
                await self._check_position_exit()
            
            if self._signal_handler:
                features = self._extract_features(row)
                
                if self._feature_guard:
                    features = self._feature_guard.filter_available_features(
                        features=features,
                        feature_timestamps={k: ts for k in features},
                        replay_clock=ts,
                    )
                    self._leakage_stats["blocked"] += len(self._extract_features(row)) - len(features)
                    self._leakage_stats["allowed"] += len(features)
                
                signal = self._signal_handler(features, self._current_price)
                
                if signal != 0 and self._position is None:
                    await self._open_position(signal)
            
            equity = self._calculate_equity()
            self._equity_curve.append(equity)
    
    def _resample_data(self, df: pd.DataFrame, freq: str) -> pd.DataFrame:
        """重采样数据到指定频率"""
        if len(df) < 2:
            return df
        
        df = df.set_index('timestamp')
        
        # OHLCV 字段的重采样规则
        agg_rules = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'quote_volume': 'sum',
            'trades': 'sum',
        }
        
        # 技术指标字段用最后一个值
        tech_indicators = [
            'rsi_7', 'rsi_14', 'rsi_21',
            'sma_10', 'sma_20', 'sma_50', 'sma_100',
            'ema_10', 'ema_20', 'ema_50', 'ema_100',
            'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_lower', 'bb_width',
            'volume_ratio', 'oi_delta', 'funding_zscore',
        ]
        
        for col in tech_indicators:
            if col in df.columns:
                agg_rules[col] = 'last'
        
        # 应用重采样
        resampled = df.resample(freq).agg(
            {col: agg_rules.get(col, 'last') for col in df.columns}
        )
        
        resampled = resampled.reset_index()
        resampled = resampled.dropna(subset=['close'])
        
        return resampled

    def _extract_features(self, row: pd.Series) -> Dict[str, float]:
        """提取特征"""
        feature_fields = [
            'rsi_14', 'rsi_7', 'rsi_21',
            'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_lower', 'bb_width',
            'sma_20', 'sma_50', 'ema_20', 'ema_50',
            'volume_ratio', 'oi_delta', 'funding_zscore',
        ]
        
        features = {}
        for field in feature_fields:
            if field in row and not pd.isna(row[field]):
                features[field] = float(row[field])
        
        return features
    
    async def _process_event(self, event):
        """处理事件"""
        if event.event_type == "candle_1m":
            data = event.data
            self._current_price = data.get('close', 0)
            self._current_time = datetime.fromtimestamp(event.timestamp / 1000)
            self._current_timestamp = event.timestamp
            
            if self._position:
                await self._check_position_exit()
            
            equity = self._calculate_equity()
            self._equity_curve.append(equity)
        
        elif event.event_type == "features":
            if self._signal_handler is None:
                return
            
            features = event.data.get('features', {})
            
            if self._feature_guard:
                features = self._feature_guard.filter_available_features(
                    features=features,
                    feature_timestamps={k: event.timestamp for k in features},
                    replay_clock=self._current_timestamp,
                )
            
            signal = self._signal_handler(features, self._current_price)
            
            if signal != 0 and self._position is None:
                await self._open_position(signal)
    
    async def _open_position(self, signal: int):
        """开仓"""
        if self._position is not None:
            return
        
        entry_price = self._apply_slippage(self._current_price, signal)
        position_size = self._capital * self.config.position_size
        
        self._position = {
            "entry_time": self._current_time,
            "entry_price": entry_price,
            "quantity": position_size / entry_price,
            "direction": "long" if signal > 0 else "short",
        }
        
        self._capital -= position_size
    
    async def _check_position_exit(self):
        """检查持仓退出"""
        if self._position is None:
            return
        
        entry_price = self._position["entry_price"]
        direction = self._position["direction"]
        
        if direction == "long":
            pnl_pct = (self._current_price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - self._current_price) / entry_price
        
        exit_reason = None
        
        if pnl_pct <= -self.config.stop_loss:
            exit_reason = "stop_loss"
        elif pnl_pct >= self.config.take_profit:
            exit_reason = "take_profit"
        else:
            hold_hours = (self._current_time - self._position["entry_time"]).total_seconds() / 3600
            if hold_hours >= self.config.max_hold_hours:
                exit_reason = "time"
        
        if exit_reason:
            await self._close_position(self._current_price, self._current_time, exit_reason)
    
    async def _close_position(self, price: float, time: datetime, reason: str):
        """平仓"""
        if self._position is None:
            return
        
        exit_price = self._apply_slippage(price, -1 if self._position["direction"] == "long" else 1)
        
        if self._position["direction"] == "long":
            pnl_pct = (exit_price - self._position["entry_price"]) / self._position["entry_price"]
        else:
            pnl_pct = (self._position["entry_price"] - exit_price) / self._position["entry_price"]
        
        pnl = self._position["quantity"] * self._position["entry_price"] * pnl_pct
        
        self._capital += self._position["quantity"] * self._position["entry_price"] + pnl
        
        trade = BacktestTrade(
            entry_time=self._position["entry_time"],
            exit_time=time,
            entry_price=self._position["entry_price"],
            exit_price=exit_price,
            quantity=self._position["quantity"],
            direction=self._position["direction"],
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason,
            slippage=abs(exit_price - price) / price if self.config.enable_slippage else 0.0,
            latency_ms=self.config.latency_ms if self.config.enable_latency else 0.0,
        )
        
        self._trades.append(trade)
        self._position = None
    
    def _apply_slippage(self, price: float, direction: int) -> float:
        """应用滑点"""
        if not self.config.enable_slippage:
            return price
        
        slippage = self.config.slippage * (1 + np.random.uniform(-0.5, 0.5))
        if direction > 0:
            return price * (1 + slippage)
        else:
            return price * (1 - slippage)
    
    def _calculate_equity(self) -> float:
        """计算当前权益"""
        equity = self._capital
        
        if self._position:
            if self._position["direction"] == "long":
                pnl_pct = (self._current_price - self._position["entry_price"]) / self._position["entry_price"]
            else:
                pnl_pct = (self._position["entry_price"] - self._current_price) / self._position["entry_price"]
            
            equity += self._position["quantity"] * self._position["entry_price"] * (1 + pnl_pct)
        
        return equity
    
    def _create_signal_handler(self, strategy_id: str, params: Dict[str, Any]) -> Callable:
        """创建信号处理器"""
        def rsi_oversold_handler(features: Dict, price: float) -> int:
            period = params.get("period", 14)
            oversold = params.get("oversold", 30)
            rsi = features.get(f"rsi_{period}", 50)
            return 1 if rsi < oversold else 0
        
        def rsi_overbought_handler(features: Dict, price: float) -> int:
            period = params.get("period", 14)
            overbought = params.get("overbought", 70)
            rsi = features.get(f"rsi_{period}", 50)
            return -1 if rsi > overbought else 0
        
        def macd_cross_handler(features: Dict, price: float) -> int:
            macd = features.get("macd", 0)
            signal = features.get("macd_signal", 0)
            if macd > signal:
                return 1
            elif macd < signal:
                return -1
            return 0
        
        def sma_cross_handler(features: Dict, price: float) -> int:
            fast = params.get("fast", 10)
            slow = params.get("slow", 50)
            sma_fast = features.get(f"sma_{fast}", 0)
            sma_slow = features.get(f"sma_{slow}", 0)
            if sma_fast > sma_slow:
                return 1
            elif sma_fast < sma_slow:
                return -1
            return 0
        
        def ema_cross_handler(features: Dict, price: float) -> int:
            fast = params.get("fast", 10)
            slow = params.get("slow", 50)
            ema_fast = features.get(f"ema_{fast}", 0)
            ema_slow = features.get(f"ema_{slow}", 0)
            if ema_fast > ema_slow:
                return 1
            elif ema_fast < ema_slow:
                return -1
            return 0
        
        def bb_handler(features: Dict, price: float) -> int:
            bb_upper = features.get("bb_upper", 0)
            bb_lower = features.get("bb_lower", 0)
            if price < bb_lower:
                return 1
            elif price > bb_upper:
                return -1
            return 0
        
        handlers = {
            "rsi_oversold": rsi_oversold_handler,
            "rsi_overbought": rsi_overbought_handler,
            "macd_cross": macd_cross_handler,
            "sma_cross": sma_cross_handler,
            "ema_cross": ema_cross_handler,
            "bollinger_bands": bb_handler,
        }
        
        return handlers.get(strategy_id, lambda f, p: 0)
    
    def _reset(self):
        """重置状态"""
        self._capital = self.config.initial_capital
        self._position = None
        self._trades = []
        self._equity_curve = [self.config.initial_capital]
        self._current_price = 0.0
        self._current_time = None
        self._current_timestamp = 0
        self._leakage_stats = {"blocked": 0, "allowed": 0}
    
    def _calculate_result(self, symbol: str, strategy_id: str, params: Dict[str, Any]) -> BacktestResult:
        """计算回测结果"""
        if not self._trades:
            return BacktestResult(symbol=symbol, strategy_id=strategy_id, params=params)
        
        total_return = (self._capital - self.config.initial_capital) / self.config.initial_capital
        
        wins = [t for t in self._trades if t.pnl_pct > 0]
        losses = [t for t in self._trades if t.pnl_pct <= 0]
        
        win_rate = len(wins) / len(self._trades) if self._trades else 0
        
        total_wins = sum(t.pnl_pct for t in wins)
        total_losses = abs(sum(t.pnl_pct for t in losses))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0
        
        returns = [t.pnl_pct for t in self._trades]
        sharpe = np.mean(returns) / (np.std(returns) + 1e-10) * np.sqrt(252) if returns else 0
        
        negative_returns = [r for r in returns if r < 0]
        sortino = np.mean(returns) / (np.std(negative_returns) + 1e-10) * np.sqrt(252) if negative_returns else sharpe
        
        peak = self.config.initial_capital
        max_dd = 0
        for eq in self._equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak
            if dd > max_dd:
                max_dd = dd
        
        calmar = (total_return * 252 / 365) / max_dd if max_dd > 0 else 0
        
        avg_win = np.mean([t.pnl_pct for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl_pct for t in losses]) if losses else 0
        avg_hold = np.mean([(t.exit_time - t.entry_time).total_seconds() / 3600 for t in self._trades])
        
        return BacktestResult(
            symbol=symbol,
            strategy_id=strategy_id,
            params=params,
            total_return=total_return,
            annualized_return=total_return * 252 / 365,
            win_rate=win_rate,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown=max_dd,
            total_trades=len(self._trades),
            winning_trades=len(wins),
            losing_trades=len(losses),
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_hold_hours=avg_hold,
            trades=self._trades,
            equity_curve=self._equity_curve,
        )
    
    def _get_default_data_path(self, symbol: str) -> Path:
        """获取默认数据路径"""
        return Path(__file__).parent.parent.parent / "data_lake" / "features" / "binance" / symbol / "features.parquet"
