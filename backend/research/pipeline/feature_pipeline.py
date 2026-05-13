"""
Feature Pipeline - 特征流水线

功能：
1. raw → feature 自动转换
2. feature → factor 组合
3. 标签生成
4. 训练集构建

这是因子研究的核心基础设施。
"""

import asyncio
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import uuid
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("research.pipeline.feature")


class PipelineStage(str, Enum):
    """流水线阶段"""
    RAW = "raw"
    NORMALIZED = "normalized"
    FEATURE = "feature"
    FACTOR = "factor"
    LABEL = "label"
    TRAINSET = "trainset"


@dataclass
class PipelineConfig:
    """流水线配置"""
    name: str
    
    symbols: List[str]
    timeframes: List[str]
    
    start_date: datetime
    end_date: datetime
    
    lookback_periods: Dict[str, int] = field(default_factory=lambda: {
        "1m": 60,
        "5m": 48,
        "1h": 24,
        "4h": 30,
        "1d": 30,
    })
    
    train_ratio: float = 0.7
    val_ratio: float = 0.15
    test_ratio: float = 0.15
    
    target_horizon: int = 1
    
    feature_engines: List[str] = field(default_factory=list)


@dataclass
class FeatureSpec:
    """特征规格"""
    feature_id: str
    name: str
    description: str
    
    dependencies: List[str] = field(default_factory=list)
    
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "name": self.name,
            "description": self.description,
            "dependencies": self.dependencies,
            "parameters": self.parameters,
        }


@dataclass
class LabelSpec:
    """标签规格"""
    label_id: str
    name: str
    
    label_type: str
    
    horizon: int
    
    direction: str = "long_only"
    
    threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "label_id": self.label_id,
            "name": self.name,
            "label_type": self.label_type,
            "horizon": self.horizon,
            "direction": self.direction,
            "threshold": self.threshold,
        }


@dataclass
class Trainset:
    """训练集"""
    trainset_id: str
    
    features: List[str]
    labels: List[str]
    
    train_start: datetime
    train_end: datetime
    
    val_start: Optional[datetime] = None
    val_end: Optional[datetime] = None
    
    test_start: Optional[datetime] = None
    test_end: Optional[datetime] = None
    
    sample_count: int = 0
    feature_count: int = 0
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trainset_id": self.trainset_id,
            "features": self.features,
            "labels": self.labels,
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "val_start": self.val_start.isoformat() if self.val_start else None,
            "val_end": self.val_end.isoformat() if self.val_end else None,
            "test_start": self.test_start.isoformat() if self.test_start else None,
            "test_end": self.test_end.isoformat() if self.test_end else None,
            "sample_count": self.sample_count,
            "feature_count": self.feature_count,
            "metadata": self.metadata,
        }


@dataclass
class FeatureResult:
    """特征计算结果"""
    symbol: str
    timestamp: datetime
    
    features: Dict[str, float]
    raw_data: Dict[str, Any]
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "features": self.features,
            "metadata": self.metadata,
        }


class FeatureEngine:
    """特征计算引擎基类"""
    
    def __init__(self, name: str):
        self.name = name
        self._features: Dict[str, FeatureSpec] = {}
    
    def register_feature(self, spec: FeatureSpec) -> None:
        """注册特征"""
        self._features[spec.feature_id] = spec
        logger.debug(f"Feature registered: {spec.feature_id}")
    
    def get_features(self) -> Dict[str, FeatureSpec]:
        """获取所有特征"""
        return self._features.copy()
    
    async def compute(
        self,
        symbol: str,
        timestamp: datetime,
        data: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """计算特征"""
        raise NotImplementedError
    
    async def compute_batch(
        self,
        symbol: str,
        timestamps: List[datetime],
        data_series: List[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, float]]:
        """批量计算特征"""
        results = []
        for ts, d in zip(timestamps, data_series):
            result = await self.compute(symbol, ts, d, parameters)
            results.append(result)
        return results


class TechnicalFeatureEngine(FeatureEngine):
    """技术指标特征引擎"""
    
    def __init__(self):
        super().__init__("technical")
        
        self._register_builtin_features()
    
    def _register_builtin_features(self) -> None:
        """注册内置特征"""
        features = [
            FeatureSpec(
                feature_id="returns_1m",
                name="1分钟收益率",
                description="过去1分钟收益率",
                dependencies=[],
            ),
            FeatureSpec(
                feature_id="returns_5m",
                name="5分钟收益率",
                description="过去5分钟收益率",
                dependencies=[],
            ),
            FeatureSpec(
                feature_id="returns_1h",
                name="1小时收益率",
                description="过去1小时收益率",
                dependencies=[],
            ),
            FeatureSpec(
                feature_id="volatility_1h",
                name="1小时波动率",
                description="过去1小时波动率",
                dependencies=["returns_1h"],
            ),
            FeatureSpec(
                feature_id="rsi_14",
                name="RSI(14)",
                description="14周期RSI",
                dependencies=["returns_1m"],
            ),
            FeatureSpec(
                feature_id="macd",
                name="MACD",
                description="MACD指标",
                dependencies=["returns_1m"],
            ),
            FeatureSpec(
                feature_id="bb_position",
                name="布林带位置",
                description="布林带中的位置",
                dependencies=["returns_1m"],
            ),
            FeatureSpec(
                feature_id="volume_ratio",
                name="成交量比率",
                description="当前成交量与平均成交量的比率",
                dependencies=[],
            ),
        ]
        
        for spec in features:
            self.register_feature(spec)
    
    async def compute(
        self,
        symbol: str,
        timestamp: datetime,
        data: Dict[str, Any],
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, float]:
        """计算技术指标"""
        features = {}
        
        price = data.get("close", 0)
        prices = data.get("prices", [])
        volumes = data.get("volumes", [])
        
        if len(prices) >= 2:
            features["returns_1m"] = (prices[-1] - prices[-2]) / prices[-2] if prices[-2] > 0 else 0
        
        if len(prices) >= 6:
            features["returns_5m"] = (prices[-1] - prices[-6]) / prices[-6] if prices[-6] > 0 else 0
        
        if len(prices) >= 60:
            features["returns_1h"] = (prices[-1] - prices[-60]) / prices[-60] if prices[-60] > 0 else 0
        
        if len(prices) >= 60:
            returns = np.diff(prices[-60:]) / prices[-59:]
            features["volatility_1h"] = float(np.std(returns)) if len(returns) > 0 else 0
        
        if len(prices) >= 15:
            features["rsi_14"] = self._compute_rsi(prices[-15:], 14)
        
        if len(prices) >= 26:
            features["macd"], _, _ = self._compute_macd(prices[-35:])
        
        if len(prices) >= 20:
            features["bb_position"] = self._compute_bb_position(prices[-20:], price)
        
        if len(volumes) >= 20:
            avg_volume = np.mean(volumes[-20:])
            current_volume = volumes[-1] if volumes else 0
            features["volume_ratio"] = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        return features
    
    def _compute_rsi(self, prices: List[float], period: int) -> float:
        """计算RSI"""
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _compute_macd(self, prices: List[float]) -> Tuple[float, float, float]:
        """计算MACD"""
        if len(prices) < 26:
            return 0, 0, 0
        
        ema12 = self._ema(prices, 12)
        ema26 = self._ema(prices, 26)
        
        macd = ema12 - ema26
        signal = self._ema([macd] * 9, 9) if macd != 0 else 0
        histogram = macd - signal
        
        return macd, signal, histogram
    
    def _compute_bb_position(self, prices: List[float], current_price: float) -> float:
        """计算布林带位置"""
        if len(prices) < 20:
            return 0.5
        
        sma = np.mean(prices)
        std = np.std(prices)
        
        upper = sma + 2 * std
        lower = sma - 2 * std
        
        if upper == lower:
            return 0.5
        
        return (current_price - lower) / (upper - lower)
    
    def _ema(self, prices: List[float], period: int) -> float:
        """计算EMA"""
        if len(prices) < period:
            return prices[-1] if prices else 0
        
        multiplier = 2 / (period + 1)
        ema = np.mean(prices[:period])
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema


class FeaturePipeline:
    """特征流水线
    
    管理特征计算和训练集构建
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config
        
        self._engines: Dict[str, FeatureEngine] = {}
        self._features: Dict[str, FeatureSpec] = {}
        
        self._label_specs: Dict[str, LabelSpec] = {}
        
        self._data_cache: Dict[str, Dict[str, Any]] = {}
        
        self._register_default_engines()
    
    def _register_default_engines(self) -> None:
        """注册默认引擎"""
        technical_engine = TechnicalFeatureEngine()
        self._engines["technical"] = technical_engine
        
        for feature_id, spec in technical_engine.get_features().items():
            self._features[feature_id] = spec
    
    def register_engine(self, name: str, engine: FeatureEngine) -> None:
        """注册特征引擎"""
        self._engines[name] = engine
        
        for feature_id, spec in engine.get_features().items():
            self._features[feature_id] = spec
        
        logger.info(f"Feature engine registered: {name} ({len(engine.get_features())} features)")
    
    def register_feature(self, spec: FeatureSpec) -> None:
        """注册特征"""
        self._features[spec.feature_id] = spec
        logger.debug(f"Feature registered: {spec.feature_id}")
    
    def register_label(self, spec: LabelSpec) -> None:
        """注册标签"""
        self._label_specs[spec.label_id] = spec
        logger.debug(f"Label registered: {spec.label_id}")
    
    async def compute_features(
        self,
        symbol: str,
        timestamp: datetime,
        data: Dict[str, Any],
        feature_ids: Optional[List[str]] = None,
    ) -> FeatureResult:
        """计算特征"""
        if feature_ids is None:
            feature_ids = list(self._features.keys())
        
        results = {}
        
        for feature_id in feature_ids:
            spec = self._features.get(feature_id)
            if not spec:
                continue
            
            if not self._check_dependencies(feature_id):
                logger.warning(f"Dependencies not met for {feature_id}")
                continue
            
            engine_name = self._get_engine_for_feature(feature_id)
            if engine_name not in self._engines:
                continue
            
            engine = self._engines[engine_name]
            
            try:
                feature_value = await engine.compute(symbol, timestamp, data, spec.parameters)
                if feature_id in feature_value:
                    results[feature_id] = feature_value[feature_id]
            except Exception as e:
                logger.error(f"Feature computation failed for {feature_id}: {e}")
        
        return FeatureResult(
            symbol=symbol,
            timestamp=timestamp,
            features=results,
            raw_data=data,
        )
    
    def _check_dependencies(self, feature_id: str) -> bool:
        """检查依赖是否满足"""
        spec = self._features.get(feature_id)
        if not spec:
            return False
        
        for dep in spec.dependencies:
            if dep not in self._features:
                return False
        
        return True
    
    def _get_engine_for_feature(self, feature_id: str) -> Optional[str]:
        """获取特征对应的引擎"""
        for engine_name, engine in self._engines.items():
            if feature_id in engine.get_features():
                return engine_name
        return None
    
    def generate_labels(
        self,
        prices: List[float],
        spec: LabelSpec,
    ) -> List[int]:
        """生成标签"""
        labels = []
        
        for i in range(len(prices) - spec.horizon):
            future_return = (prices[i + spec.horizon] - prices[i]) / prices[i] if prices[i] > 0 else 0
            
            if spec.label_type == "regression":
                if spec.direction == "long_only":
                    label = future_return
                else:
                    label = future_return
            elif spec.label_type == "classification":
                if spec.threshold:
                    label = 1 if future_return > spec.threshold else 0
                else:
                    label = 1 if future_return > 0 else 0
            else:
                label = 0
            
            labels.append(label)
        
        return labels
    
    def build_trainset(
        self,
        features: Dict[str, List[float]],
        labels: List[int],
        timestamps: List[datetime],
    ) -> Trainset:
        """构建训练集"""
        if not self.config:
            raise ValueError("Pipeline config required for trainset building")
        
        split_idx_train = int(len(timestamps) * self.config.train_ratio)
        split_idx_val = int(len(timestamps) * (self.config.train_ratio + self.config.val_ratio))
        
        train_end = timestamps[split_idx_train - 1] if split_idx_train > 0 else timestamps[0]
        val_start = timestamps[split_idx_train] if split_idx_train < len(timestamps) else None
        val_end = timestamps[split_idx_val - 1] if split_idx_val < len(timestamps) else None
        test_start = timestamps[split_idx_val] if split_idx_val < len(timestamps) else None
        test_end = timestamps[-1] if timestamps else None
        
        return Trainset(
            trainset_id=f"trainset_{uuid.uuid4().hex[:12]}",
            features=list(features.keys()),
            labels=[spec.label_id for spec in self._label_specs.values()],
            train_start=timestamps[0],
            train_end=train_end,
            val_start=val_start,
            val_end=val_end,
            test_start=test_start,
            test_end=test_end,
            sample_count=len(timestamps),
            feature_count=len(features),
            metadata={
                "train_ratio": self.config.train_ratio,
                "val_ratio": self.config.val_ratio,
                "test_ratio": self.config.test_ratio,
            },
        )
    
    def get_features(self) -> Dict[str, FeatureSpec]:
        """获取所有特征"""
        return self._features.copy()
    
    def get_feature_stats(self) -> Dict[str, Any]:
        """获取特征统计"""
        return {
            "total_features": len(self._features),
            "by_engine": {
                name: len(engine.get_features())
                for name, engine in self._engines.items()
            },
            "engines": list(self._engines.keys()),
            "labels": len(self._label_specs),
        }
    
    def get_pipeline_stages(self) -> List[PipelineStage]:
        """获取流水线阶段"""
        return [
            PipelineStage.RAW,
            PipelineStage.NORMALIZED,
            PipelineStage.FEATURE,
            PipelineStage.FACTOR,
            PipelineStage.LABEL,
            PipelineStage.TRAINSET,
        ]


_pipeline: Optional[FeaturePipeline] = None


def get_feature_pipeline(config: Optional[PipelineConfig] = None) -> FeaturePipeline:
    """获取特征流水线实例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = FeaturePipeline(config)
    return _pipeline
