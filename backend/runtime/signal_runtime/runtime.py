"""
Signal Runtime - 信号生成运行时

职责（仅运行时编排）：
- Kafka 消费
- 生命周期管理
- 重试机制
- 健康检查
- 指标收集
- 因子计算与发布

业务逻辑：调用 services/fusion_service/ 和 services/strategy_service/

GPU 加速：
- 特征计算：TorchFeatureCalculator
- LSTM 策略：LSTMStrategy
- 自动检测 GPU 可用性，无 GPU 时降级到 CPU
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.base import BaseRuntime, RuntimeConfig
from runtime.shared import (
    RuntimeLifecycle,
    RuntimeMetrics,
    RuntimeConsumer,
    ConsumerConfig,
    RuntimePublisher,
    PublisherConfig,
    RuntimeHealthCheck,
)
from infrastructure.messaging import Topics
from infrastructure.messaging.kafka_config import ConsumerGroup


class SignalConfig(RuntimeConfig):
    """Signal Runtime 配置"""
    name: str = "signal_runtime"
    fusion_window_seconds: int = 300
    fusion_min_events: int = 1
    fusion_min_confidence: float = 0.3
    factor_calc_interval: int = 60
    enable_factor_publish: bool = True
    enable_strategy_discovery: bool = False
    strategy_discovery_interval: int = 3600
    max_auto_strategies: int = 5
    min_win_rate: float = 0.6
    min_sample_size: int = 50
    min_avg_return: float = 0.005
    
    enable_gpu: bool = True
    lstm_enabled: bool = False
    lstm_sequence_length: int = 60
    
    symbols: List[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.symbols is None:
            self.symbols = ["BTC", "ETH", "SOL"]


class SignalRuntime(BaseRuntime):
    """
    Signal Runtime - 信号生成运行时
    
    只负责运行时编排，业务逻辑在：
    - services/fusion_service/ - 信号融合
    - services/strategy_service/ - 策略决策
    - services/factor_service/ - 因子计算
    
    GPU 加速（可选）：
    - TorchFeatureCalculator - GPU 特征计算
    - LSTMStrategy - LSTM 深度学习策略
    """
    
    def __init__(self, config: SignalConfig = None):
        config = config or SignalConfig.from_env()
        super().__init__(config)
        self.config: SignalConfig = config
        
        self.lifecycle: Optional[RuntimeLifecycle] = None
        self.metrics: Optional[RuntimeMetrics] = None
        self.health_check: Optional[RuntimeHealthCheck] = None
        
        self.consumer: Optional[RuntimeConsumer] = None
        self.publisher: Optional[RuntimePublisher] = None
        self.factor_publisher: Optional[RuntimePublisher] = None
        
        self.fusion_engine = None
        self.strategy_orchestrator = None
        self.factor_calculator = None
        self._factor_task: Optional[asyncio.Task] = None
        self._price_cache: Dict[str, Dict[str, float]] = {}
        
        self.strategy_discovery_engine = None
        self._strategy_discovery_task: Optional[asyncio.Task] = None
        self._auto_discovered_strategies: List = []
        
        self.gpu_feature_calculator = None
        self.lstm_strategy = None
        self._gpu_available = False
        self._kline_buffer: Dict[str, List[Dict]] = {}
    
    async def initialize(self) -> None:
        """初始化运行时组件"""
        self.logger.info("Initializing Signal Runtime...")
        
        self.lifecycle = RuntimeLifecycle("signal")
        self.metrics = RuntimeMetrics("signal")
        self.health_check = RuntimeHealthCheck("signal")
        
        self.consumer = RuntimeConsumer(ConsumerConfig(
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            topics=[Topics.EVENTS],
            group_id=ConsumerGroup.SIGNAL_RUNTIME,
        ))
        
        self.publisher = RuntimePublisher(PublisherConfig(
            bootstrap_servers=self.config.kafka_bootstrap_servers,
            topic=Topics.DECISIONS,
        ))
        
        if self.config.enable_factor_publish:
            self.factor_publisher = RuntimePublisher(PublisherConfig(
                bootstrap_servers=self.config.kafka_bootstrap_servers,
                topic=Topics.FACTORS,
            ))
        
        await self.consumer.start()
        await self.publisher.start()
        if self.factor_publisher:
            await self.factor_publisher.start()
        
        try:
            from services.fusion_service import FusionEngine
            self.fusion_engine = FusionEngine(
                window_seconds=self.config.fusion_window_seconds,
                min_events=self.config.fusion_min_events,
                min_confidence=self.config.fusion_min_confidence,
            )
            self.logger.info("Fusion engine initialized")
        except Exception as e:
            self.logger.warning(f"Fusion engine init failed: {e}")
        
        try:
            from services.strategy_service.strategies import create_default_strategies
            
            symbols_with_usdt = [f"{s}USDT" for s in self.config.symbols]
            self.strategy_orchestrator = create_default_strategies(symbols=symbols_with_usdt)
            self.logger.info(f"Strategy orchestrator initialized for {symbols_with_usdt}")
        except Exception as e:
            self.logger.warning(f"Strategy orchestrator init failed: {e}")
        
        try:
            from services.factor_service import get_factor_calculator
            self.factor_calculator = get_factor_calculator()
            await self.factor_calculator.initialize()
            self.logger.info("Factor calculator initialized")
        except Exception as e:
            self.logger.warning(f"Factor calculator init failed: {e}")
        
        if self.config.enable_gpu:
            await self._init_gpu_components()
        
        if self.config.enable_strategy_discovery:
            try:
                from services.strategy_service.strategy_discovery import StrategyDiscoveryEngine
                
                symbols_with_usdt = [f"{s}USDT" for s in self.config.symbols]
                self.strategy_discovery_engine = StrategyDiscoveryEngine(
                    min_win_rate=self.config.min_win_rate,
                    min_sample_size=self.config.min_sample_size,
                    min_avg_return=self.config.min_avg_return,
                    symbols=symbols_with_usdt,
                )
                self.logger.info(f"Strategy discovery engine initialized for {symbols_with_usdt}")
            except Exception as e:
                self.logger.warning(f"Strategy discovery engine init failed: {e}")
        
        self.health_check.register_check("fusion_engine", self._check_fusion_engine)
        self.health_check.register_check("strategy_orchestrator", self._check_strategy)
        self.health_check.register_check("consumer", self.consumer.is_healthy)
        self.health_check.register_check("publisher", self.publisher.is_healthy)
        self.health_check.register_check("factor_calculator", self._check_factor_calculator)
        self.health_check.register_check("gpu_acceleration", self._check_gpu)
        
        self.logger.info("Signal Runtime initialized successfully")
    
    async def _init_gpu_components(self):
        """初始化 GPU 加速组件"""
        try:
            from shared.acceleration import is_gpu_available, get_accelerator_info
            from domain.feature.torch_calculator import TorchFeatureCalculator
            
            info = get_accelerator_info()
            self._gpu_available = info['is_gpu']
            
            self.logger.info(f"GPU acceleration: {info['device_type']}, is_gpu={self._gpu_available}")
            
            self.gpu_feature_calculator = TorchFeatureCalculator()
            self.logger.info("GPU feature calculator initialized")
            
            if self.config.lstm_enabled:
                await self._init_lstm_strategy()
            
        except ImportError as e:
            self.logger.warning(f"GPU acceleration not available: {e}")
            self._gpu_available = False
        except Exception as e:
            self.logger.warning(f"GPU initialization failed: {e}")
            self._gpu_available = False
    
    async def _init_lstm_strategy(self):
        """初始化 LSTM 策略"""
        try:
            from domain.strategy.lstm_strategy import LSTMStrategyBuilder
            
            self.lstm_strategy = LSTMStrategyBuilder.create_fast(input_size=21)
            self.logger.info("LSTM strategy initialized")
            
            model_path = Path(__file__).parent.parent.parent / "models" / "lstm" / "lstm_model.pt"
            if model_path.exists():
                self.lstm_strategy.load(str(model_path))
                self.logger.info(f"LSTM model loaded from {model_path}")
            
        except Exception as e:
            self.logger.warning(f"LSTM strategy init failed: {e}")
            self.lstm_strategy = None
    
    async def _check_fusion_engine(self) -> bool:
        return self.fusion_engine is not None
    
    async def _check_strategy(self) -> bool:
        return self.strategy_orchestrator is not None
    
    async def _check_factor_calculator(self) -> bool:
        return self.factor_calculator is not None
    
    async def _check_gpu(self) -> bool:
        return self._gpu_available
    
    async def shutdown(self) -> None:
        """关闭运行时组件"""
        self.logger.info("Shutting down Signal Runtime...")
        
        if self._factor_task:
            self._factor_task.cancel()
            try:
                await self._factor_task
            except asyncio.CancelledError:
                pass
        
        if self._strategy_discovery_task:
            self._strategy_discovery_task.cancel()
            try:
                await self._strategy_discovery_task
            except asyncio.CancelledError:
                pass
        
        if self.consumer:
            await self.consumer.stop()
        if self.publisher:
            await self.publisher.stop()
        if self.factor_publisher:
            await self.factor_publisher.stop()
        
        self.logger.info(f"Signal Runtime stopped. Stats: {self.metrics.to_dict()}")
    
    async def run(self) -> None:
        """主运行循环"""
        self.logger.info("Starting Signal Runtime main loop...")
        
        await self.lifecycle.transition_to_running()
        
        if self.config.enable_factor_publish and self.factor_calculator:
            self._factor_task = asyncio.create_task(self._factor_calculation_loop())
            self.logger.info("Factor calculation task started")
        
        if self.config.enable_strategy_discovery and self.strategy_discovery_engine:
            self._strategy_discovery_task = asyncio.create_task(self._strategy_discovery_loop())
            self.logger.info("Strategy discovery task started")
        
        while not self.context.is_shutdown_requested():
            try:
                message = await self.consumer.consume(timeout=1.0)
                if message:
                    await self._process_event(message)
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                self.metrics.increment("errors")
                await self.lifecycle.handle_error(e)
    
    async def _factor_calculation_loop(self) -> None:
        """因子计算循环（多币种）- GPU 加速"""
        symbols = self.config.symbols
        
        while not self.context.is_shutdown_requested():
            try:
                for symbol in symbols:
                    if self._gpu_available and self.gpu_feature_calculator:
                        factors = await self._compute_factors_gpu(symbol)
                    else:
                        factors = await self.factor_calculator.calculate_all_factors(symbol)
                    
                    if factors and self.factor_publisher:
                        factor_event = {
                            "event_type": "factors",
                            "symbol": symbol,
                            "timestamp": datetime.utcnow().isoformat(),
                            "gpu_accelerated": self._gpu_available,
                            "factors": [
                                {
                                    "type": f.type,
                                    "name": f.name,
                                    "nameEn": f.name_en,
                                    "weight": f.weight,
                                    "value": f.value,
                                    "confidence": f.confidence,
                                    "color": f.color,
                                }
                                for f in factors
                            ],
                        }
                        
                        await self.factor_publisher.publish(factor_event)
                        self.metrics.increment("factors_published")
                        self.logger.debug(f"Published factors for {symbol} (GPU={self._gpu_available})")
                
                await asyncio.sleep(self.config.factor_calc_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in factor calculation loop: {e}")
                await asyncio.sleep(10)
    
    async def _compute_factors_gpu(self, symbol: str) -> Optional[List]:
        """使用 GPU 计算因子"""
        try:
            if symbol not in self._kline_buffer or len(self._kline_buffer[symbol]) < 100:
                return await self.factor_calculator.calculate_all_factors(symbol)
            
            import pandas as pd
            from shared.acceleration import to_gpu
            
            klines = self._kline_buffer[symbol][-500:]
            df = pd.DataFrame(klines)
            
            features_df = self.gpu_feature_calculator.compute_batch(df, symbol=f"{symbol}USDT", use_gpu=True)
            
            factors = self._convert_features_to_factors(features_df, symbol)
            
            self.metrics.increment("gpu_factor_computations")
            
            return factors
            
        except Exception as e:
            self.logger.error(f"GPU factor computation failed: {e}")
            return await self.factor_calculator.calculate_all_factors(symbol)
    
    def _convert_features_to_factors(self, features_df, symbol: str) -> List:
        """将特征 DataFrame 转换为因子列表"""
        from services.factor_service import Factor
        
        factors = []
        last_row = features_df.iloc[-1]
        
        feature_factor_map = {
            "rsi_14": ("technical", "RSI", "RSI", 0.15),
            "macd": ("technical", "MACD", "MACD", 0.12),
            "bb_width": ("technical", "BB Width", "Bollinger Width", 0.08),
            "volume_ratio": ("volume", "Volume Ratio", "Volume Ratio", 0.10),
            "atr_14": ("volatility", "ATR", "Average True Range", 0.08),
            "momentum_10": ("momentum", "Momentum", "Momentum", 0.10),
        }
        
        for feature_name, (factor_type, name, name_en, weight) in feature_factor_map.items():
            if feature_name in last_row:
                value = last_row[feature_name]
                
                if feature_name == "rsi_14":
                    confidence = 1 - abs(value - 50) / 50
                    color = "green" if value < 30 else "red" if value > 70 else "gray"
                elif feature_name == "macd":
                    confidence = min(abs(value) / 100, 1.0)
                    color = "green" if value > 0 else "red"
                else:
                    confidence = min(abs(value) if value else 0.5, 1.0)
                    color = "gray"
                
                factors.append(Factor(
                    type=factor_type,
                    name=name,
                    name_en=name_en,
                    weight=weight,
                    value=float(value) if value else 0.0,
                    confidence=float(confidence),
                    color=color,
                ))
        
        return factors
    
    async def _strategy_discovery_loop(self) -> None:
        """策略发现循环（多币种）"""
        while not self.context.is_shutdown_requested():
            try:
                if self.strategy_discovery_engine and self.strategy_orchestrator:
                    self.logger.info("Starting multi-symbol strategy discovery cycle...")
                    
                    all_results = self.strategy_discovery_engine.auto_discover_all_symbols(
                        orchestrator=self.strategy_orchestrator,
                        max_strategies_per_symbol=self.config.max_auto_strategies,
                    )
                    
                    total_strategies = sum(len(strats) for strats in all_results.values())
                    if total_strategies > 0:
                        self._auto_discovered_strategies.extend([
                            (sym, s) for sym, strats in all_results.items()
                            for s in strats
                        ])
                        self.metrics.increment("strategies_auto_discovered", total_strategies)
                        self.logger.info(f"Auto-discovered {total_strategies} strategies across {len(all_results)} symbols")
                    
                    self.strategy_discovery_engine.print_discovery_report()
                
                await asyncio.sleep(self.config.strategy_discovery_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in strategy discovery loop: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                await asyncio.sleep(self.config.strategy_discovery_interval)
    
    async def _process_event(self, message: Dict[str, Any]) -> None:
        """处理事件（运行时编排）"""
        trace_id = message.get("trace_id", "unknown")
        
        self.metrics.increment("events_received")
        
        event_type = message.get("event_type", "")
        
        if event_type == "kline_update":
            symbol = message.get("symbol", "BTC")
            kline = message.get("kline", {})
            if symbol not in self._kline_buffer:
                self._kline_buffer[symbol] = []
            self._kline_buffer[symbol].append(kline)
            if len(self._kline_buffer[symbol]) > 1000:
                self._kline_buffer[symbol] = self._kline_buffer[symbol][-500:]
        
        elif event_type == "price_update" and self.factor_calculator:
            symbol = message.get("symbol", "BTC")
            price = message.get("price", 0)
            volume = message.get("volume_24h", 0)
            self.factor_calculator.update_price(symbol, price, volume)
        
        with self.metrics.timing("event_processing"):
            signals = await self._fuse_events(message)
            
            if signals:
                decisions = await self._run_strategies(signals)
                
                for decision in decisions:
                    await self.publisher.publish(decision)
                    self.metrics.increment("decisions_made")
    
    async def _fuse_events(self, message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """融合事件（调用 services/fusion_service/）"""
        if not self.fusion_engine:
            return []
        
        try:
            from services.fusion_service import FusionEvent
            
            fusion_event = FusionEvent(
                id=message.get("event_id", ""),
                timestamp=datetime.now(),
                source=message.get("source", "unknown"),
                event_type=message.get("event_type", ""),
                category=message.get("category", ""),
                asset=message.get("asset"),
                direction=message.get("direction", "neutral"),
                strength=message.get("strength", 0.5),
            )
            
            self.fusion_engine.add_event(fusion_event)
            
            signals = self.fusion_engine.process(price_change=0.02)
            
            if signals:
                self.metrics.increment("signals_generated", len(signals))
                return self._resolve_conflicts(signals)
            
            return []
            
        except Exception as e:
            self.logger.error(f"Fusion error: {e}")
            return []
    
    def _resolve_conflicts(self, signals: List[Any]) -> List[Dict[str, Any]]:
        """冲突解决（业务逻辑）"""
        if not signals:
            return []
        
        asset_map = defaultdict(lambda: {"bullish": 0.0, "bearish": 0.0, "events": 0})
        
        for s in signals:
            asset = s.assets[0] if s.assets else "CRYPTO"
            direction = s.direction
            
            if direction == "bullish":
                asset_map[asset]["bullish"] += s.confidence
            elif direction == "bearish":
                asset_map[asset]["bearish"] += s.confidence
            
            asset_map[asset]["events"] += 1
        
        final_signals = []
        
        for asset, v in asset_map.items():
            net = v["bullish"] - v["bearish"]
            
            if abs(net) < 0.05:
                continue
            
            direction = "bullish" if net > 0 else "bearish"
            confidence = abs(net)
            
            final_signals.append({
                "asset": asset,
                "signal": f"{asset}_{direction.upper()}",
                "direction": direction,
                "confidence": confidence,
                "event_count": v["events"],
            })
        
        return final_signals
    
    async def _run_strategies(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """运行策略（币种感知）- 支持 GPU 加速"""
        if not signals:
            return []
        
        decisions = []
        
        for signal in signals:
            try:
                asset = signal.get("asset", "BTC")
                symbol = f"{asset}USDT"
                
                if self._gpu_available and self.lstm_strategy and symbol in self._kline_buffer:
                    decision = await self._run_lstm_strategy(symbol, signal)
                    if decision:
                        decisions.append(decision)
                        continue
                
                if self.strategy_orchestrator:
                    strategy_signals = self.strategy_orchestrator.process(symbol)
                    
                    if strategy_signals:
                        decision = self._convert_to_decision(strategy_signals, signal)
                        decisions.append(decision)
                    
            except Exception as e:
                self.logger.error(f"Strategy error: {e}")
        
        return decisions
    
    async def _run_lstm_strategy(self, symbol: str, signal: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """运行 LSTM 策略（GPU 加速）"""
        if not self.lstm_strategy or symbol not in self._kline_buffer:
            return None
        
        try:
            import pandas as pd
            from shared.acceleration import to_gpu
            
            klines = self._kline_buffer[symbol][-self.config.lstm_sequence_length:]
            if len(klines) < self.config.lstm_sequence_length:
                return None
            
            df = pd.DataFrame(klines)
            features = self.gpu_feature_calculator.compute_batch(df, symbol=symbol, use_gpu=True)
            
            feature_cols = [c for c in features.columns if c not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            feature_matrix = to_gpu(features[feature_cols].values.astype('float32'))
            
            lstm_signal = await self.lstm_strategy.predict(feature_matrix)
            
            if lstm_signal != 0:
                action = "BUY" if lstm_signal == 1 else "SELL"
                confidence = 0.7
                
                self.metrics.increment("lstm_signals")
                
                return {
                    "trace_id": signal.get("trace_id", ""),
                    "action": action,
                    "symbol": symbol,
                    "quantity": min(confidence * 0.08, 0.1),
                    "confidence": confidence,
                    "reason": f"LSTM 策略信号，GPU 加速",
                    "strategy": "lstm",
                    "gpu_accelerated": True,
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"LSTM strategy error: {e}")
            return None
    
    def _convert_to_decision(self, strategy_signals: List[Any], signal: Dict[str, Any]) -> Dict[str, Any]:
        """转换策略信号为决策"""
        if not strategy_signals:
            return {
                "action": "HOLD",
                "symbol": f"{signal.get('asset', 'BTC')}USDT",
                "quantity": 0.0,
                "confidence": 0.0,
                "reason": "无策略信号",
            }
        
        direction_votes = defaultdict(float)
        total_confidence = 0.0
        
        for sig in strategy_signals:
            weight = sig.confidence
            direction_votes[sig.action] += weight
            total_confidence += weight
        
        if not direction_votes:
            action = "HOLD"
            confidence = 0.0
        else:
            sorted_directions = sorted(
                direction_votes.items(),
                key=lambda x: x[1],
                reverse=True,
            )
            action = sorted_directions[0][0]
            confidence = sorted_directions[0][1] / max(total_confidence, 0.001)
        
        return {
            "trace_id": signal.get("trace_id", ""),
            "action": action,
            "symbol": f"{signal.get('asset', 'BTC')}USDT",
            "quantity": min(confidence * 0.08, 0.1),
            "confidence": confidence,
            "reason": f"信号{signal.get('signal', '')}，置信度 {confidence:.3f}",
            "gpu_accelerated": self._gpu_available,
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        health = await super().health_check()
        health.update({
            "lifecycle": self.lifecycle.to_dict() if self.lifecycle else {},
            "metrics": self.metrics.to_dict() if self.metrics else {},
            "health_check": await self.health_check.to_dict() if self.health_check else {},
            "gpu_acceleration": {
                "available": self._gpu_available,
                "feature_calculator": self.gpu_feature_calculator is not None,
                "lstm_strategy": self.lstm_strategy is not None,
            },
        })
        return health


_signal_runtime: Optional[SignalRuntime] = None


def get_signal_runtime() -> SignalRuntime:
    """获取 Signal Runtime 单例"""
    global _signal_runtime
    if _signal_runtime is None:
        _signal_runtime = SignalRuntime()
    return _signal_runtime


async def main():
    """主入口"""
    print("=" * 60)
    print("Signal Runtime - Event Fusion + Strategy (GPU Accelerated)")
    print("=" * 60)
    
    runtime = get_signal_runtime()
    await runtime.start()


if __name__ == "__main__":
    asyncio.run(main())
