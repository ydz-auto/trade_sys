"""
Unified Feature Calculator - 统一特征计算器（内部使用）

⚠️ WARNING: 禁止外部直接调用！⚠️
所有特征计算必须通过 FeatureRuntime！

核心原则：
1. 在线/离线使用完全相同的特征计算逻辑
2. 所有特征计算都通过 FeatureRuntime 入口
3. 防止数据泄漏

GPU 加速（走 Runtime 主链）：
- compute() 单条计算：CPU（在线实时场景，延迟敏感）
- compute_batch() 批量计算：委托 TorchFeatureCalculator（GPU 向量化）
- compute_from_parquet() 离线计算：委托 TorchFeatureCalculator（GPU 向量化）
- 数据量 > 1000 且 GPU 可用时自动启用 GPU，否则 CPU fallback

用法（通过 FeatureRuntime）：
    feature_runtime = get_feature_runtime()
    await feature_runtime.emit_event("kline", kline_data)
    features = feature_runtime.get_features_at(timestamp_ms)

⚠️ 禁止直接使用！⚠️
直接使用会导致：
- 时间因果不一致
- 在线/离线实现不同步
- 特征可用性检查缺失
- Future Leakage 风险
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from collections import deque
import pandas as pd
import numpy as np

import logging

# Import feature extractors
from domain.feature.trade.trade_feature import TradeFeatureExtractor, Trade
from domain.feature.liquidation.liquidation_feature import LiquidationFeatureExtractor, Liquidation
from domain.feature.oi.oi_funding_correlation import OIFundingCorrelator
from engines.compute.feature.core_calculators import (
    compute_rsi,
    compute_sma,
    compute_ema,
    compute_macd,
    compute_bollinger,
    compute_volume_ratio,
    compute_atr,
    compute_momentum,
    compute_all_features
)

logger = logging.getLogger(__name__)


@dataclass
class FeatureSchema:
    """特征 Schema"""
    name: str
    category: str
    available_after_periods: int = 0
    description: str = ""


DEFAULT_SCHEMAS = {
    # Technical indicators
    "rsi_14": FeatureSchema("rsi_14", "technical", 14, "RSI 14周期"),
    "rsi_7": FeatureSchema("rsi_7", "technical", 7, "RSI 7周期"),
    "rsi_21": FeatureSchema("rsi_21", "technical", 21, "RSI 21周期"),
    "sma_20": FeatureSchema("sma_20", "technical", 20, "SMA 20周期"),
    "sma_50": FeatureSchema("sma_50", "technical", 50, "SMA 50周期"),
    "ema_20": FeatureSchema("ema_20", "technical", 20, "EMA 20周期"),
    "ema_50": FeatureSchema("ema_50", "technical", 50, "EMA 50周期"),
    "macd": FeatureSchema("macd", "technical", 26, "MACD"),
    "macd_signal": FeatureSchema("macd_signal", "technical", 35, "MACD Signal"),
    "bb_upper": FeatureSchema("bb_upper", "technical", 20, "Bollinger Upper"),
    "bb_lower": FeatureSchema("bb_lower", "technical", 20, "Bollinger Lower"),
    "volume_ratio": FeatureSchema("volume_ratio", "volume", 20, "Volume Ratio"),
    "atr_14": FeatureSchema("atr_14", "volatility", 14, "ATR 14"),
    # Trade features
    "trade_delta": FeatureSchema("trade_delta", "trade", 1, "主动买卖差"),
    "cumulative_delta": FeatureSchema("cumulative_delta", "trade", 1, "累积主动流"),
    "aggressive_buy_volume": FeatureSchema("aggressive_buy_volume", "trade", 1, "主动买入量"),
    "aggressive_sell_volume": FeatureSchema("aggressive_sell_volume", "trade", 1, "主动卖出量"),
    "total_volume": FeatureSchema("total_volume", "trade", 1, "总成交量"),
    "total_value": FeatureSchema("total_value", "trade", 1, "总成交金额"),
    "num_trades": FeatureSchema("num_trades", "trade", 1, "成交笔数"),
    "trade_velocity": FeatureSchema("trade_velocity", "trade", 1, "成交速度"),
    "avg_trade_size": FeatureSchema("avg_trade_size", "trade", 1, "平均成交大小"),
    "max_trade_size": FeatureSchema("max_trade_size", "trade", 1, "最大成交大小"),
    "large_trade_ratio": FeatureSchema("large_trade_ratio", "trade", 1, "大单占比"),
    "large_trade_volume": FeatureSchema("large_trade_volume", "trade", 1, "大单成交量"),
    "sweep_buy_score": FeatureSchema("sweep_buy_score", "trade", 1, "扫单买入评分"),
    "sweep_sell_score": FeatureSchema("sweep_sell_score", "trade", 1, "扫单卖出评分"),
    "liquidity_vacuum": FeatureSchema("liquidity_vacuum", "trade", 1, "流动性真空"),
    "trade_imbalance": FeatureSchema("trade_imbalance", "trade", 1, "买卖失衡"),
    "buy_sell_ratio": FeatureSchema("buy_sell_ratio", "trade", 1, "买卖比率"),
    # Liquidation features
    "liquidation_long": FeatureSchema("liquidation_long", "liquidation", 1, "多头爆仓量"),
    "liquidation_short": FeatureSchema("liquidation_short", "liquidation", 1, "空头爆仓量"),
    "liquidation_total": FeatureSchema("liquidation_total", "liquidation", 1, "总爆仓量"),
    "liquidation_spike": FeatureSchema("liquidation_spike", "liquidation", 10, "爆仓尖峰"),
    "liquidation_pressure": FeatureSchema("liquidation_pressure", "liquidation", 1, "爆仓压力"),
    "long_liq_ratio": FeatureSchema("long_liq_ratio", "liquidation", 1, "多头爆仓比率"),
    "liquidation_cluster": FeatureSchema("liquidation_cluster", "liquidation", 5, "爆仓聚集"),
    "liquidation_acceleration": FeatureSchema("liquidation_acceleration", "liquidation", 3, "爆仓加速"),
    "liquidation_chain_probability": FeatureSchema("liquidation_chain_probability", "liquidation", 10, "连锁爆仓概率"),
    "long_short_liq_ratio": FeatureSchema("long_short_liq_ratio", "liquidation", 1, "多空爆仓比率"),
    "liquidation_reversal_signal": FeatureSchema("liquidation_reversal_signal", "liquidation", 10, "清算反转信号"),
    # OI/Funding features
    "oi": FeatureSchema("oi", "oi", 1, "持仓量"),
    "oi_delta": FeatureSchema("oi_delta", "oi", 2, "持仓量变化"),
    "oi_zscore": FeatureSchema("oi_zscore", "oi", 24, "持仓量Z分数"),
    "funding_rate": FeatureSchema("funding_rate", "funding", 1, "资金费率"),
    "funding_zscore": FeatureSchema("funding_zscore", "funding", 24, "资金费率Z分数"),
    "funding_delta": FeatureSchema("funding_delta", "funding", 2, "资金费率变化"),
    "oi_funding_divergence": FeatureSchema("oi_funding_divergence", "oi_funding", 24, "OI-资金背离"),
    "oi_squeeze_probability": FeatureSchema("oi_squeeze_probability", "oi_funding", 24, "杠杆挤压概率"),
    "oi_liq_pressure": FeatureSchema("oi_liq_pressure", "oi_funding", 24, "潜在踩踏压力"),
    "funding_extreme_reversal": FeatureSchema("funding_extreme_reversal", "oi_funding", 24, "资金极端反转"),
    "leverage_crowdedness": FeatureSchema("leverage_crowdedness", "oi_funding", 24, "杠杆拥挤度"),
}


class UnifiedFeatureCalculator:
    """
    统一特征计算器
    
    确保在线/离线使用完全相同的特征计算逻辑。
    
    GPU 加速策略（走 Runtime 主链）：
    - compute() 单条计算：CPU（在线实时场景，延迟敏感）
    - compute_batch() 批量计算：委托 TorchFeatureCalculator（GPU 向量化）
    - 数据量 > 1000 且 GPU 可用时自动启用 GPU，否则 CPU fallback
    """
    
    def __init__(self, max_lookback: int = 500, use_gpu: bool = True, accelerator_info: Optional[Dict] = None):
        self.max_lookback = max_lookback
        self.schemas = DEFAULT_SCHEMAS
        self.use_gpu = use_gpu
        self._accelerator_info = accelerator_info
        
        self._price_buffer: Dict[str, deque] = {}
        self._volume_buffer: Dict[str, deque] = {}
        self._high_buffer: Dict[str, deque] = {}
        self._low_buffer: Dict[str, deque] = {}
        
        # Feature extractors
        self._trade_extractor: Dict[str, TradeFeatureExtractor] = {}
        self._liquidation_extractor: Dict[str, LiquidationFeatureExtractor] = {}
        self._oi_funding_correlator: Dict[str, OIFundingCorrelator] = {}
        
        # Data buffers for trade/liquidation/OI
        self._trade_buffer: Dict[str, List[Trade]] = {}
        self._liquidation_buffer: Dict[str, List[Liquidation]] = {}
        self._oi_buffer: Dict[str, List[float]] = {}
        self._funding_buffer: Dict[str, List[float]] = {}
        self._oi_timestamp_buffer: Dict[str, List[int]] = {}
        
        self._torch_calculator = None
        self._gpu_available = False
        if self.use_gpu:
            self._init_gpu()
    
    def _init_gpu(self):
        try:
            from engines.compute.feature.torch_calculator import TorchFeatureCalculator
            
            if self._accelerator_info is not None:
                info = self._accelerator_info
            else:
                info = {"is_gpu": False, "device_type": "cpu"}
            
            self._gpu_available = info['is_gpu']
            
            if self._gpu_available:
                self._torch_calculator = TorchFeatureCalculator(
                    max_lookback=self.max_lookback
                )
                logger.info(
                    f"UnifiedFeatureCalculator GPU enabled: {info['device_type']}"
                )
            else:
                logger.info("UnifiedFeatureCalculator using CPU (GPU not available)")
        except ImportError as e:
            logger.warning(f"GPU acceleration not available: {e}")
            self._gpu_available = False
        except Exception as e:
            logger.warning(f"GPU initialization failed: {e}")
            self._gpu_available = False
    
    def compute(
        self,
        symbol: str,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> Dict[str, float]:
        """
        计算特征
        
        这是核心方法，在线/离线都调用这个方法。
        """
        self._update_buffer(symbol, open_price, high, low, close, volume)
        
        features = {}
        
        features.update(self._compute_rsi(symbol))
        features.update(self._compute_sma(symbol))
        features.update(self._compute_ema(symbol))
        features.update(self._compute_macd(symbol))
        features.update(self._compute_bollinger(symbol))
        features.update(self._compute_volume_ratio(symbol))
        features.update(self._compute_atr(symbol))
        features.update(self._compute_momentum(symbol))
        
        return features
    
    def compute_batch(
        self,
        df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        use_gpu: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> pd.DataFrame:
        """
        批量计算特征
        
        GPU 加速：委托给 TorchFeatureCalculator，走 shared/acceleration 主链。
        数据量 > 1000 且 GPU 可用时自动启用 GPU，否则 CPU fallback。
        """
        n = len(df)
        
        if use_gpu and self._gpu_available and self._torch_calculator and n > 1000:
            logger.info(
                f"compute_batch: delegating to TorchFeatureCalculator "
                f"(GPU, {n} rows)"
            )
            return self._torch_calculator.compute_batch(
                df, symbol, use_gpu=True, progress_callback=progress_callback
            )
        
        logger.info(f"compute_batch: CPU path ({n} rows)")
        self._reset_buffer(symbol)
        
        results = []
        
        for idx, row in df.iterrows():
            features = self.compute(
                symbol=symbol,
                open_price=float(row.get('open', 0)),
                high=float(row.get('high', 0)),
                low=float(row.get('low', 0)),
                close=float(row.get('close', 0)),
                volume=float(row.get('volume', 0)),
            )
            
            result = {
                'timestamp': row.get('timestamp', row.get('open_time', 0)),
                'open': float(row.get('open', 0)),
                'high': float(row.get('high', 0)),
                'low': float(row.get('low', 0)),
                'close': float(row.get('close', 0)),
                'volume': float(row.get('volume', 0)),
            }
            result.update(features)
            results.append(result)
        
        return pd.DataFrame(results)
    
    def compute_from_parquet(
        self,
        parquet_path: Path,
        symbol: str = "BTCUSDT",
        output_path: Optional[Path] = None,
        use_gpu: bool = True,
    ) -> pd.DataFrame:
        """
        从 Parquet 计算特征
        
        GPU 加速：委托给 TorchFeatureCalculator，走 shared/acceleration 主链。
        """
        df = pd.read_parquet(parquet_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        if use_gpu and self._gpu_available and self._torch_calculator:
            result_df = self._torch_calculator.compute_from_parquet(
                parquet_path, symbol, output_path, use_gpu=True
            )
        else:
            result_df = self.compute_batch(df, symbol, use_gpu=False)
            
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result_df.to_parquet(output_path, index=False)
                logger.info(f"Features saved to {output_path}")
        
        return result_df
    
    def _update_buffer(
        self,
        symbol: str,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ):
        """更新数据缓冲区"""
        if symbol not in self._price_buffer:
            self._price_buffer[symbol] = deque(maxlen=self.max_lookback)
            self._volume_buffer[symbol] = deque(maxlen=self.max_lookback)
            self._high_buffer[symbol] = deque(maxlen=self.max_lookback)
            self._low_buffer[symbol] = deque(maxlen=self.max_lookback)
        
        self._price_buffer[symbol].append(close)
        self._volume_buffer[symbol].append(volume)
        self._high_buffer[symbol].append(high)
        self._low_buffer[symbol].append(low)
    
    def _reset_buffer(self, symbol: str):
        """重置缓冲区"""
        self._price_buffer[symbol] = deque(maxlen=self.max_lookback)
        self._volume_buffer[symbol] = deque(maxlen=self.max_lookback)
        self._high_buffer[symbol] = deque(maxlen=self.max_lookback)
        self._low_buffer[symbol] = deque(maxlen=self.max_lookback)
    
    def _compute_rsi(self, symbol: str) -> Dict[str, float]:
        """计算 RSI"""
        prices = list(self._price_buffer.get(symbol, []))
        return compute_rsi(prices)
    
    def _compute_sma(self, symbol: str) -> Dict[str, float]:
        """计算 SMA"""
        prices = list(self._price_buffer.get(symbol, []))
        return compute_sma(prices)
    
    def _compute_ema(self, symbol: str) -> Dict[str, float]:
        """计算 EMA"""
        prices = list(self._price_buffer.get(symbol, []))
        return compute_ema(prices)
    
    def _compute_macd(self, symbol: str) -> Dict[str, float]:
        """计算 MACD"""
        prices = list(self._price_buffer.get(symbol, []))
        return compute_macd(prices)
    
    def _compute_bollinger(self, symbol: str) -> Dict[str, float]:
        """计算布林带"""
        prices = list(self._price_buffer.get(symbol, []))
        return compute_bollinger(prices)
    
    def _compute_volume_ratio(self, symbol: str) -> Dict[str, float]:
        """计算成交量比率"""
        volumes = list(self._volume_buffer.get(symbol, []))
        return compute_volume_ratio(volumes)
    
    def _compute_atr(self, symbol: str) -> Dict[str, float]:
        """计算 ATR"""
        highs = list(self._high_buffer.get(symbol, []))
        lows = list(self._low_buffer.get(symbol, []))
        closes = list(self._price_buffer.get(symbol, []))
        return compute_atr(highs, lows, closes)
    
    def _compute_momentum(self, symbol: str) -> Dict[str, float]:
        """计算动量"""
        prices = list(self._price_buffer.get(symbol, []))
        return compute_momentum(prices)
    
    def _get_trade_extractor(self, symbol: str) -> TradeFeatureExtractor:
        """获取或初始化 Trade 特征提取器"""
        if symbol not in self._trade_extractor:
            self._trade_extractor[symbol] = TradeFeatureExtractor()
            self._trade_buffer[symbol] = []
        return self._trade_extractor[symbol]
    
    def update_trades(self, symbol: str, trades: List[Dict], window_ms: int = 60000) -> Dict[str, float]:
        """更新 Trade 数据并计算特征"""
        extractor = self._get_trade_extractor(symbol)
        
        # Convert dict trades to Trade objects
        trade_objects = []
        for t in trades:
            trade_obj = Trade(
                timestamp=t.get("timestamp", 0),
                price=t.get("price", 0.0),
                quantity=t.get("quantity", t.get("qty", 0.0)),
                quote_quantity=t.get("quote_quantity", t.get("quote_qty", 0.0)),
                is_buyer_maker=t.get("is_buyer_maker", False),
                trade_id=str(t.get("trade_id", t.get("id", "")))
            )
            trade_objects.append(trade_obj)
        
        # Add to buffer
        self._trade_buffer[symbol].extend(trade_objects)
        
        # Extract features
        features_list = extractor.extract_features(trade_objects, symbol, window_ms)
        
        if features_list:
            latest_feature = features_list[-1]
            return latest_feature.to_dict()
        
        return {}
    
    def _get_liquidation_extractor(self, symbol: str) -> LiquidationFeatureExtractor:
        """获取或初始化 Liquidation 特征提取器"""
        if symbol not in self._liquidation_extractor:
            self._liquidation_extractor[symbol] = LiquidationFeatureExtractor()
            self._liquidation_buffer[symbol] = []
        return self._liquidation_extractor[symbol]
    
    def update_liquidations(self, symbol: str, liquidations: List[Dict], window_ms: int = 60000) -> Dict[str, float]:
        """更新 Liquidation 数据并计算特征"""
        extractor = self._get_liquidation_extractor(symbol)
        
        # Convert dict liquidations to Liquidation objects
        liq_objects = []
        for l in liquidations:
            liq_obj = Liquidation(
                timestamp=l.get("timestamp", 0),
                symbol=symbol,
                side=l.get("side", "long"),
                quantity=l.get("quantity", l.get("qty", 0.0)),
                price=l.get("price", 0.0),
                quote_quantity=l.get("quote_quantity", l.get("quote_qty", 0.0))
            )
            liq_objects.append(liq_obj)
        
        # Add to buffer
        self._liquidation_buffer[symbol].extend(liq_objects)
        
        # Extract features
        features_list = extractor.extract_features(liq_objects, window_ms)
        
        if features_list:
            latest_feature = features_list[-1]
            return latest_feature.to_dict()
        
        return {}
    
    def _get_oi_funding_correlator(self, symbol: str) -> OIFundingCorrelator:
        """获取或初始化 OI/Funding 关联分析器"""
        if symbol not in self._oi_funding_correlator:
            self._oi_funding_correlator[symbol] = OIFundingCorrelator()
            self._oi_buffer[symbol] = []
            self._funding_buffer[symbol] = []
            self._oi_timestamp_buffer[symbol] = []
        return self._oi_funding_correlator[symbol]
    
    def update_oi(self, symbol: str, oi: float, timestamp: int) -> Dict[str, float]:
        """更新 OI 数据"""
        correlator = self._get_oi_funding_correlator(symbol)
        self._oi_buffer[symbol].append(oi)
        self._oi_timestamp_buffer[symbol].append(timestamp)
        
        # Keep buffer size limited
        if len(self._oi_buffer[symbol]) > 1008:
            self._oi_buffer[symbol].pop(0)
            self._oi_timestamp_buffer[symbol].pop(0)
        
        # If we have funding data, compute correlation
        if self._funding_buffer.get(symbol):
            latest_funding = self._funding_buffer[symbol][-1] if self._funding_buffer[symbol] else 0.0
            corr = correlator.compute_correlation(oi, latest_funding, timestamp)
            return corr.to_dict()
        
        # Just return basic OI features
        features = {"oi": oi}
        if len(self._oi_buffer[symbol]) >= 2:
            features["oi_delta"] = self._oi_buffer[symbol][-1] - self._oi_buffer[symbol][-2]
        if len(self._oi_buffer[symbol]) >= 24:
            oi_window = np.array(self._oi_buffer[symbol][-24:])
            oi_mean = np.mean(oi_window)
            oi_std = np.std(oi_window) + 1e-8
            features["oi_zscore"] = (oi - oi_mean) / oi_std
        
        return features
    
    def update_funding(self, symbol: str, funding_rate: float, timestamp: int) -> Dict[str, float]:
        """更新 Funding 数据"""
        correlator = self._get_oi_funding_correlator(symbol)
        self._funding_buffer[symbol].append(funding_rate)
        
        # Keep buffer size limited
        if len(self._funding_buffer[symbol]) > 1008:
            self._funding_buffer[symbol].pop(0)
        
        # If we have OI data, compute correlation
        if self._oi_buffer.get(symbol):
            latest_oi = self._oi_buffer[symbol][-1] if self._oi_buffer[symbol] else 0.0
            corr = correlator.compute_correlation(latest_oi, funding_rate, timestamp)
            return corr.to_dict()
        
        # Just return basic funding features
        features = {"funding_rate": funding_rate}
        if len(self._funding_buffer[symbol]) >= 2:
            features["funding_delta"] = self._funding_buffer[symbol][-1] - self._funding_buffer[symbol][-2]
        if len(self._funding_buffer[symbol]) >= 24:
            funding_window = np.array(self._funding_buffer[symbol][-24:])
            funding_mean = np.mean(funding_window)
            funding_std = np.std(funding_window) + 1e-8
            features["funding_zscore"] = (funding_rate - funding_mean) / funding_std
        
        return features
    
    def get_schema(self, feature_name: str) -> Optional[FeatureSchema]:
        """获取特征 Schema"""
        return self.schemas.get(feature_name)
    
    def get_available_time(
        self,
        feature_name: str,
        computation_time: int,
        interval_ms: int = 60000,
    ) -> int:
        """获取特征可用时间"""
        schema = self.schemas.get(feature_name)
        if schema:
            return computation_time + schema.available_after_periods * interval_ms
        return computation_time


_calculator_instance: Optional[UnifiedFeatureCalculator] = None


def get_feature_calculator() -> UnifiedFeatureCalculator:
    """获取特征计算器单例"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = UnifiedFeatureCalculator()
    return _calculator_instance
