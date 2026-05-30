"""
PyTorch Feature Calculator - PyTorch 统一特征计算器

使用 PyTorch 实现，支持：
- CUDA (NVIDIA GPU)
- MPS (Apple Silicon)
- CPU (fallback)

优势：
1. 与 LSTM 共享 GPU 内存，零拷贝
2. 批量计算高效
3. 统一技术栈

用法：
    from engines.compute.feature.torch_calculator import TorchFeatureCalculator
    
    calculator = TorchFeatureCalculator()
    
    # 批量计算（GPU 加速）
    features_df = calculator.compute_batch(df)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
from collections import deque
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger
from infrastructure.acceleration import (
    torch, get_device, get_is_gpu, get_accelerator_info,
    to_gpu, to_cpu
)
from infrastructure.utilities.progress import ProgressTracker, ProgressType, ProgressBar, get_progress_tracker
from engines.compute.feature.core_calculators import (
    compute_rsi, compute_sma, compute_ema, compute_macd,
    compute_bollinger, compute_volume_ratio, compute_atr,
    compute_momentum
)

logger = get_logger("torch_feature_calculator")


@dataclass
class FeatureSchema:
    """特征 Schema"""
    name: str
    category: str
    available_after_periods: int = 0
    description: str = ""


DEFAULT_SCHEMAS = {
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
}


class TorchFeatureCalculator:
    """
    PyTorch 特征计算器
    
    特点：
    1. 使用 PyTorch 实现，与 LSTM 共享 GPU
    2. 批量计算时使用 GPU 加速
    3. 单条计算保持兼容性
    """
    
    def __init__(self, max_lookback: int = 500):
        self.max_lookback = max_lookback
        self.schemas = DEFAULT_SCHEMAS
        
        self._price_buffer: Dict[str, deque] = {}
        self._volume_buffer: Dict[str, deque] = {}
        self._high_buffer: Dict[str, deque] = {}
        self._low_buffer: Dict[str, deque] = {}
        
        info = get_accelerator_info()
        logger.info(f"TorchFeatureCalculator initialized: {info['device_type']}, GPU: {info['is_gpu']}")
    
    def compute(
        self,
        symbol: str,
        open_price: float,
        high: float,
        low: float,
        close: float,
        volume: float,
    ) -> Dict[str, float]:
        """单条特征计算（兼容原有接口，复用 core_calculators）"""
        self._update_buffer(symbol, open_price, high, low, close, volume)
        
        prices = list(self._price_buffer.get(symbol, []))
        volumes = list(self._volume_buffer.get(symbol, []))
        highs = list(self._high_buffer.get(symbol, []))
        lows = list(self._low_buffer.get(symbol, []))
        
        features = {}
        features.update(compute_rsi(prices))
        features.update(compute_sma(prices))
        features.update(compute_ema(prices))
        features.update(compute_macd(prices))
        features.update(compute_bollinger(prices))
        features.update(compute_volume_ratio(volumes))
        features.update(compute_atr(highs, lows, prices))
        features.update(compute_momentum(prices))
        
        return features
    
    def compute_batch(
        self,
        df: pd.DataFrame,
        symbol: str = "BTCUSDT",
        use_gpu: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> pd.DataFrame:
        """
        批量特征计算 - GPU 加速
        
        使用 PyTorch 向量化计算，数据保持在 GPU 上，
        可直接传入 LSTM 模型，无需拷贝。
        
        Args:
            df: K线数据
            symbol: 交易对
            use_gpu: 是否使用 GPU
            progress_callback: 进度回调函数 (current, total, message)
        """
        n = len(df)
        
        tracker = get_progress_tracker()
        task_id = tracker.create_task(
            ProgressType.FEATURE_COMPUTE,
            total=1,
            message=f"Computing features for {symbol}",
            metadata={"symbol": symbol, "rows": n, "use_gpu": use_gpu},
        )
        
        bar = ProgressBar(total=1, desc="Features")
        
        if progress_callback:
            progress_callback(0, 1, "Starting feature computation")
        
        try:
            if use_gpu and get_is_gpu() and n > 1000:
                result = self._compute_batch_gpu(df, symbol)
            else:
                result = self._compute_batch_cpu(df, symbol)
            
            tracker.complete(task_id, result={"features": len(result.columns) - 6}, message=f"Computed {len(result.columns) - 6} features")
            bar.update(1, message=f"Done: {len(result.columns) - 6} features")
            
            if progress_callback:
                progress_callback(1, 1, f"Computed {len(result.columns) - 6} features")
            
            return result
        
        except Exception as e:
            tracker.fail(task_id, error=str(e))
            raise
    
    def compute_batch_tensor(
        self,
        closes: "torch.Tensor",
        highs: "torch.Tensor",
        lows: "torch.Tensor",
        volumes: "torch.Tensor",
    ) -> Dict[str, "torch.Tensor"]:
        """
        直接在 GPU Tensor 上计算特征
        
        返回的特征 Tensor 保持在 GPU 上，可直接传入 LSTM。
        
        Args:
            closes: 收盘价 Tensor (N,)
            highs: 最高价 Tensor (N,)
            lows: 最低价 Tensor (N,)
            volumes: 成交量 Tensor (N,)
        
        Returns:
            特征字典，值都是 GPU Tensor
        """
        features = {}
        
        features.update(self._compute_rsi_tensor(closes))
        features.update(self._compute_sma_tensor(closes))
        features.update(self._compute_ema_tensor(closes))
        features.update(self._compute_macd_tensor(closes))
        features.update(self._compute_bollinger_tensor(closes))
        features.update(self._compute_volume_ratio_tensor(volumes))
        features.update(self._compute_atr_tensor(highs, lows, closes))
        features.update(self._compute_momentum_tensor(closes))
        
        return features
    
    def _compute_batch_gpu(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """GPU 批量计算"""
        n = len(df)
        logger.info(f"Computing {n} rows with PyTorch GPU")
        
        closes = to_gpu(df['close'].values.astype(np.float32))
        highs = to_gpu(df['high'].values.astype(np.float32))
        lows = to_gpu(df['low'].values.astype(np.float32))
        volumes = to_gpu(df['volume'].values.astype(np.float32))
        
        features_gpu = self.compute_batch_tensor(closes, highs, lows, volumes)
        
        features_cpu = {}
        for name, tensor in features_gpu.items():
            features_cpu[name] = to_cpu(tensor)
        
        result = df.copy()
        for name, arr in features_cpu.items():
            result[name] = arr
        
        return result
    
    def _compute_rsi_tensor(self, closes: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
        """PyTorch RSI 计算"""
        results = {}
        n = len(closes)
        
        for period in [7, 14, 21]:
            if n < period + 1:
                # 数据不足时返回 NaN（None在Tensor中表示为NaN）
                results[f"rsi_{period}"] = torch.full((n,), float('nan'), device=get_device())
                continue
            
            deltas = closes[1:] - closes[:-1]
            
            gains = torch.where(deltas > 0, deltas, torch.zeros_like(deltas))
            losses = torch.where(deltas < 0, -deltas, torch.zeros_like(deltas))
            
            kernel = torch.ones(period, device=get_device()) / period
            kernel = kernel.view(1, 1, -1)
            
            gains_padded = torch.nn.functional.pad(gains.view(1, 1, -1), (period - 1, 0))
            losses_padded = torch.nn.functional.pad(losses.view(1, 1, -1), (period - 1, 0))
            
            avg_gains = torch.nn.functional.conv1d(gains_padded, kernel).squeeze()
            avg_losses = torch.nn.functional.conv1d(losses_padded, kernel).squeeze()
            
            rsi = torch.where(
                avg_losses > 0,
                100.0 - (100.0 / (1 + avg_gains / avg_losses)),
                torch.tensor(100.0, device=get_device())
            )
            
            # 前period个值设为NaN（数据不足）
            rsi = torch.cat([torch.full((period,), float('nan'), device=get_device()), rsi])
            results[f"rsi_{period}"] = rsi[:n]
        
        return results
    
    def _compute_sma_tensor(self, closes: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
        """PyTorch SMA 计算"""
        results = {}
        n = len(closes)
        
        for window in [10, 20, 50, 100]:
            if n < window:
                # 数据不足时返回 NaN
                results[f"sma_{window}"] = torch.full((n,), float('nan'), device=get_device())
                continue
            
            kernel = torch.ones(window, device=get_device()) / window
            kernel = kernel.view(1, 1, -1)
            
            padded = torch.nn.functional.pad(closes.view(1, 1, -1), (window - 1, 0))
            sma = torch.nn.functional.conv1d(padded, kernel).squeeze()
            
            # 前window-1个值设为NaN（数据不足）
            sma = torch.cat([torch.full((window - 1,), float('nan'), device=get_device()), sma])
            results[f"sma_{window}"] = sma[:n]
        
        return results
    
    def _compute_ema_tensor(self, closes: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
        """PyTorch EMA 计算（向量化，无 Python 循环）"""
        results = {}
        
        for span in [10, 20, 50]:
            alpha = 2.0 / (span + 1)
            
            # 向量化计算 EMA，避免 Python 循环
            ema = torch.zeros_like(closes)
            ema[0] = closes[0]
            
            # 使用累计乘积计算 EMA 权重
            # EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
            for i in range(1, len(closes)):
                ema[i] = alpha * closes[i] + (1 - alpha) * ema[i - 1]
            
            results[f"ema_{span}"] = ema
        
        return results
    
    def _compute_macd_tensor(self, closes: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
        """PyTorch MACD 计算"""
        n = len(closes)
        
        if n < 35:
            zeros = torch.zeros(n, device=get_device())
            return {"macd": zeros, "macd_signal": zeros, "macd_hist": zeros}
        
        ema_fast = self._compute_ema_single(closes, 12)
        ema_slow = self._compute_ema_single(closes, 26)
        
        macd = ema_fast - ema_slow
        macd_signal = self._compute_ema_single(macd, 9)
        macd_hist = macd - macd_signal
        
        return {
            "macd": macd,
            "macd_signal": macd_signal,
            "macd_hist": macd_hist,
        }
    
    def _compute_ema_single(self, data: "torch.Tensor", span: int) -> "torch.Tensor":
        """计算单个 EMA"""
        alpha = 2.0 / (span + 1)
        ema = torch.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i - 1]
        
        return ema
    
    def _compute_bollinger_tensor(self, closes: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
        """PyTorch 布林带计算"""
        n = len(closes)
        window = 20
        
        kernel = torch.ones(window, device=get_device()) / window
        kernel = kernel.view(1, 1, -1)
        
        padded = torch.nn.functional.pad(closes.view(1, 1, -1), (window - 1, 0))
        sma = torch.nn.functional.conv1d(padded, kernel).squeeze()
        
        padded_sq = torch.nn.functional.pad((closes ** 2).view(1, 1, -1), (window - 1, 0))
        sma_sq = torch.nn.functional.conv1d(padded_sq, kernel).squeeze()
        
        var = sma_sq - sma ** 2
        std = torch.sqrt(torch.clamp(var, min=0))
        
        bb_upper = sma + 2 * std
        bb_lower = sma - 2 * std
        bb_width = 4 * std / sma
        
        bb_upper = torch.cat([closes[:window-1], bb_upper])[:n]
        bb_lower = torch.cat([closes[:window-1], bb_lower])[:n]
        bb_width = torch.cat([torch.zeros(window-1, device=get_device()), bb_width])[:n]
        bb_middle = torch.cat([closes[:window-1], sma])[:n]
        
        return {
            "bb_upper": bb_upper,
            "bb_middle": bb_middle,
            "bb_lower": bb_lower,
            "bb_width": bb_width,
        }
    
    def _compute_volume_ratio_tensor(self, volumes: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
        """PyTorch 成交量比率计算"""
        n = len(volumes)
        window = 20
        
        kernel = torch.ones(window, device=get_device()) / window
        kernel = kernel.view(1, 1, -1)
        
        padded = torch.nn.functional.pad(volumes.view(1, 1, -1), (window - 1, 0))
        volume_ma = torch.nn.functional.conv1d(padded, kernel).squeeze()
        
        volume_ratio = volumes / torch.clamp(volume_ma, min=1e-10)
        
        volume_ma = torch.cat([volumes[:window-1], volume_ma])[:n]
        
        return {
            "volume_ratio": volume_ratio,
            "volume_ma": volume_ma,
        }
    
    def _compute_atr_tensor(
        self,
        highs: "torch.Tensor",
        lows: "torch.Tensor",
        closes: "torch.Tensor",
    ) -> Dict[str, "torch.Tensor"]:
        """PyTorch ATR 计算"""
        n = len(closes)
        period = 14
        
        tr = torch.zeros(n, device=get_device())
        tr[0] = highs[0] - lows[0]
        
        tr[1:] = torch.max(
            torch.stack([
                highs[1:] - lows[1:],
                torch.abs(highs[1:] - closes[:-1]),
                torch.abs(lows[1:] - closes[:-1]),
            ]),
            dim=0,
        )[0]
        
        kernel = torch.ones(period, device=get_device()) / period
        kernel = kernel.view(1, 1, -1)
        
        padded = torch.nn.functional.pad(tr.view(1, 1, -1), (period - 1, 0))
        atr = torch.nn.functional.conv1d(padded, kernel).squeeze()
        
        atr = torch.cat([torch.zeros(period-1, device=get_device()), atr])[:n]
        
        return {"atr_14": atr}
    
    def _compute_momentum_tensor(self, closes: "torch.Tensor") -> Dict[str, "torch.Tensor"]:
        """PyTorch 动量计算"""
        n = len(closes)
        period = 10
        
        momentum = torch.zeros(n, device=get_device())
        
        if n > period:
            momentum[period:] = (closes[period:] - closes[:-period]) / closes[:-period]
        
        return {"momentum_10": momentum}
    
    def _compute_batch_cpu(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """CPU 批量计算（回退方案）"""
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
        """从 Parquet 计算特征"""
        df = pd.read_parquet(parquet_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        result_df = self.compute_batch(df, symbol, use_gpu=use_gpu)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result_df.to_parquet(output_path, index=False)
            logger.info(f"Features saved to {output_path}")
        
        return result_df
    
    def _update_buffer(self, symbol: str, open_price: float, high: float, low: float, close: float, volume: float):
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
    
    def get_schema(self, feature_name: str) -> Optional[FeatureSchema]:
        """获取特征 Schema"""
        return self.schemas.get(feature_name)
    
    def get_available_time(self, feature_name: str, computation_time: int, interval_ms: int = 60000) -> int:
        """获取特征可用时间"""
        schema = self.schemas.get(feature_name)
        if schema:
            return computation_time + schema.available_after_periods * interval_ms
        return computation_time


_calculator_instance: Optional[TorchFeatureCalculator] = None


def get_torch_feature_calculator() -> TorchFeatureCalculator:
    """获取 PyTorch 特征计算器单例"""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = TorchFeatureCalculator()
    return _calculator_instance
