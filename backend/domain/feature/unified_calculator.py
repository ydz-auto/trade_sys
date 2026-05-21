"""
Unified Feature Calculator - 统一特征计算器

核心原则：
1. 在线/离线使用完全相同的特征计算逻辑
2. 所有特征计算都通过这个入口
3. 防止数据泄漏

用法：
    # 在线
    calculator = UnifiedFeatureCalculator()
    features = calculator.compute(candle)
    
    # 离线
    calculator = UnifiedFeatureCalculator()
    df = calculator.compute_batch(parquet_path)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from collections import deque
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("unified_feature_calculator")


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


class UnifiedFeatureCalculator:
    """
    统一特征计算器
    
    确保在线/离线使用完全相同的特征计算逻辑。
    
    这是消除 feature 在线/离线双实现的核心组件。
    """
    
    def __init__(self, max_lookback: int = 500):
        self.max_lookback = max_lookback
        self.schemas = DEFAULT_SCHEMAS
        
        self._price_buffer: Dict[str, deque] = {}
        self._volume_buffer: Dict[str, deque] = {}
        self._high_buffer: Dict[str, deque] = {}
        self._low_buffer: Dict[str, deque] = {}
    
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
    ) -> pd.DataFrame:
        """
        批量计算特征
        
        用于离线特征生成，确保与在线计算逻辑一致。
        """
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
    ) -> pd.DataFrame:
        """
        从 Parquet 计算特征
        
        用于离线特征生成。
        """
        df = pd.read_parquet(parquet_path)
        
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        elif 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        
        result_df = self.compute_batch(df, symbol)
        
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
        result = {}
        
        for period in [7, 14, 21]:
            if len(prices) < period + 1:
                result[f"rsi_{period}"] = 50.0
                continue
            
            deltas = np.diff(prices[-(period + 1):])
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)
            
            avg_gain = np.mean(gains)
            avg_loss = np.mean(losses)
            
            if avg_loss == 0:
                rsi = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi = 100.0 - (100.0 / (1 + rs))
            
            result[f"rsi_{period}"] = rsi
        
        return result
    
    def _compute_sma(self, symbol: str) -> Dict[str, float]:
        """计算 SMA"""
        prices = list(self._price_buffer.get(symbol, []))
        result = {}
        
        for window in [10, 20, 50, 100]:
            if len(prices) >= window:
                result[f"sma_{window}"] = np.mean(prices[-window:])
            else:
                result[f"sma_{window}"] = prices[-1] if prices else 0.0
        
        return result
    
    def _compute_ema(self, symbol: str) -> Dict[str, float]:
        """计算 EMA"""
        prices = list(self._price_buffer.get(symbol, []))
        result = {}
        
        for window in [10, 20, 50]:
            if len(prices) >= window:
                ema = pd.Series(prices).ewm(span=window, adjust=False).mean().iloc[-1]
                result[f"ema_{window}"] = ema
            else:
                result[f"ema_{window}"] = prices[-1] if prices else 0.0
        
        return result
    
    def _compute_macd(self, symbol: str) -> Dict[str, float]:
        """计算 MACD"""
        prices = list(self._price_buffer.get(symbol, []))
        
        if len(prices) < 35:
            return {"macd": 0.0, "macd_signal": 0.0, "macd_hist": 0.0}
        
        series = pd.Series(prices)
        ema_fast = series.ewm(span=12, adjust=False).mean()
        ema_slow = series.ewm(span=26, adjust=False).mean()
        
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - macd_signal
        
        return {
            "macd": float(macd.iloc[-1]),
            "macd_signal": float(macd_signal.iloc[-1]),
            "macd_hist": float(macd_hist.iloc[-1]),
        }
    
    def _compute_bollinger(self, symbol: str) -> Dict[str, float]:
        """计算布林带"""
        prices = list(self._price_buffer.get(symbol, []))
        
        if len(prices) < 20:
            return {"bb_upper": 0.0, "bb_middle": 0.0, "bb_lower": 0.0, "bb_width": 0.0}
        
        recent = prices[-20:]
        sma = np.mean(recent)
        std = np.std(recent)
        
        return {
            "bb_upper": sma + 2 * std,
            "bb_middle": sma,
            "bb_lower": sma - 2 * std,
            "bb_width": 4 * std / sma if sma > 0 else 0.0,
        }
    
    def _compute_volume_ratio(self, symbol: str) -> Dict[str, float]:
        """计算成交量比率"""
        volumes = list(self._volume_buffer.get(symbol, []))
        
        if len(volumes) < 20:
            return {"volume_ratio": 1.0, "volume_ma": 0.0}
        
        current_vol = volumes[-1]
        avg_vol = np.mean(volumes[-20:])
        
        return {
            "volume_ratio": current_vol / avg_vol if avg_vol > 0 else 1.0,
            "volume_ma": avg_vol,
        }
    
    def _compute_atr(self, symbol: str) -> Dict[str, float]:
        """计算 ATR"""
        highs = list(self._high_buffer.get(symbol, []))
        lows = list(self._low_buffer.get(symbol, []))
        prices = list(self._price_buffer.get(symbol, []))
        
        if len(prices) < 15:
            return {"atr_14": 0.0}
        
        tr_list = []
        for i in range(1, min(15, len(prices))):
            tr = max(
                highs[-i] - lows[-i],
                abs(highs[-i] - prices[-i-1]),
                abs(lows[-i] - prices[-i-1]),
            )
            tr_list.append(tr)
        
        atr = np.mean(tr_list) if tr_list else 0.0
        
        return {"atr_14": atr}
    
    def _compute_momentum(self, symbol: str) -> Dict[str, float]:
        """计算动量"""
        prices = list(self._price_buffer.get(symbol, []))
        
        if len(prices) < 11:
            return {"momentum_10": 0.0}
        
        momentum_10 = (prices[-1] - prices[-11]) / prices[-11] if prices[-11] > 0 else 0.0
        
        return {"momentum_10": momentum_10}
    
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
