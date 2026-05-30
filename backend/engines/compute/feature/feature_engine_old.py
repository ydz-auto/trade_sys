"""
FeatureEngine - 统一特征引擎门面

阶段 1: research - 包装 research.alpha.features.matrix.build_feature_matrix
阶段 2: engine - research base + CoreFeatureCalculator 覆盖
阶段 3: engine_standalone - 独立从 raw market data 构建，不依赖 research

用法：
    from engines.compute.feature.feature_engine import FeatureEngine
    engine = FeatureEngine(source="research")           # 原始 research
    engine = FeatureEngine(source="engine")             # research base + engine 覆盖
    engine = FeatureEngine(source="engine_standalone")  # 完全独立 engine
    df = engine.build_historical_matrix(symbol="BTCUSDT", days=90, timeframe="1h")
"""

import sys
from pathlib import Path
from typing import Optional, Union

import pandas as pd
import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

VALID_SOURCES = ["research", "engine", "engine_standalone"]


class FeatureEngine:
    """统一特征引擎门面"""

    def __init__(self, source: str = "research"):
        if source not in VALID_SOURCES:
            raise ValueError(f"source 必须是 {VALID_SOURCES}，得到: {source}")
        self.source = source
        self._validate_source()

    def _validate_source(self):
        if self.source in ("engine", "engine_standalone"):
            try:
                # 检查基础依赖是否可用
                from infrastructure.storage.data_lake.file_reader import FileDataLakeReader
                from infrastructure.repositories.funding_loader import merge_funding_into_df
                from infrastructure.repositories.oi_loader import merge_oi_into_df
                from engines.compute.feature.core_calculators import compute_all_features
            except ImportError as e:
                raise RuntimeError(f"source='{self.source}' 当前不可用: {e}") from e
        elif self.source == "research":
            try:
                from research.alpha.features.matrix import build_feature_matrix
            except ImportError as e:
                raise RuntimeError(f"source='research' 不可用: {e}") from e

    def build_historical_matrix(
        self,
        symbol: str,
        exchange: str = "binance",
        days: int = 90,
        timeframe: str = "1h",
    ) -> pd.DataFrame:
        if self.source == "research":
            return self._build_research(symbol, exchange, days, timeframe)
        elif self.source == "engine":
            return self._build_engine(symbol, exchange, days, timeframe)
        elif self.source == "engine_standalone":
            return self._build_standalone(symbol, exchange, days, timeframe)
        else:
            raise ValueError(f"source={self.source} 不支持")

    def _build_research(self, symbol, exchange, days, timeframe) -> pd.DataFrame:
        from research.alpha.features.matrix import build_feature_matrix
        return build_feature_matrix(
            symbol=symbol,
            exchange=exchange,
            days=days,
            timeframe=timeframe,
            use_engine=False,  # 避免循环依赖
        )

    def _build_engine(self, symbol, exchange, days, timeframe) -> pd.DataFrame:
        # 直接使用 research 层的实现，但不使用完整的 build_feature_matrix（避免循环依赖）
        from research.alpha.features.matrix import _fallback_build
        return _fallback_build(symbol, exchange, days, timeframe)

    def _build_standalone(self, symbol, exchange, days, timeframe) -> pd.DataFrame:
        """
        独立构建特征矩阵，不依赖 research

        流程：
        1. 从 FileDataLakeReader 加载 raw klines
        2. CoreFeatureCalculator 计算核心特征
        3. FundingLoader 合并 funding 数据
        4. Regime 特征计算
        5. 返回仅包含已迁移特征的矩阵
        """
        from infrastructure.repositories.kline_loader import load_klines
        print(f"  [standalone] 加载 {symbol} klines ({timeframe}, {days}d)...")
        base = load_klines(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            days=days,
        )
        print(f"  [standalone] Klines: {len(base)} 行")

        from engines.compute.feature.core_calculators import CoreFeatureCalculator
        print(f"  [standalone] 计算核心特征...")
        result = CoreFeatureCalculator.calculate_all_core_features(base, timeframe=timeframe)

        core_count = len([col for col in result.columns if col not in ["timestamp", "open", "low", "high", "close", "volume"]])
        print(f"  [standalone] 核心特征: {core_count} 个")

        from infrastructure.repositories.funding_loader import merge_funding_into_df
        result = merge_funding_into_df(result, exchange=exchange, symbol=symbol)
        funding_available = "funding_rate" in result.columns and not result["funding_rate"].isna().all()
        print(f"  [standalone] Funding 数据: {'✅ 可用' if funding_available else '❌ 不可用'}")

        from infrastructure.repositories.oi_loader import merge_oi_into_df
        result = merge_oi_into_df(result, exchange=exchange, symbol=symbol)
        oi_available = "oi" in result.columns and not result["oi"].isna().all()
        print(f"  [standalone] OI 数据: {'✅ 可用' if oi_available else '❌ 不可用'}")

        result = _compute_standalone_regime(result)

        print(f"  [standalone] 完整矩阵: {result.shape[0]} 行 × {result.shape[1]} 列")

        return result


def _compute_standalone_regime(df: pd.DataFrame) -> pd.DataFrame:
    """计算 regime 特征

    生成两套 regime 列：
    1. trend_regime + vol_regime: 与 classify_regime 一致（pipeline 使用）
    2. volatility_regime: 与 research matrix _compute_regime_features 一致
    """
    if "trend_20" not in df.columns:
        df["trend_regime"] = "range"
        df["vol_regime"] = "normal"
        df["volatility_regime"] = "normal"
        return df

    trend = df["trend_20"].fillna(0)
    df["trend_regime"] = np.where(
        trend > 0.01, "trend_up",
        np.where(trend < -0.01, "trend_down", "range")
    )

    vol_short = df["vol_20"].fillna(0) if "vol_20" in df.columns else pd.Series(0, index=df.index)
    vol_long = df["vol_60"].fillna(0) if "vol_60" in df.columns else vol_short
    df["vol_regime"] = np.where(
        vol_short > vol_long * 1.2, "high_vol",
        np.where(vol_short < vol_long * 0.8, "low_vol", "normal")
    )

    if "volatility_zscore" in df.columns:
        vz = df["volatility_zscore"].fillna(0)
        df["volatility_regime"] = np.where(
            vz > 2.0, "extreme",
            np.where(vz > 1.0, "high",
                     np.where(vz < -1.0, "low", "normal"))
        )
    else:
        df["volatility_regime"] = "normal"

    return df


def get_feature_engine(source: str = "research") -> FeatureEngine:
    return FeatureEngine(source=source)


if __name__ == "__main__":
    for src in ["research", "engine", "engine_standalone"]:
        print(f"\n=== 测试 source='{src}' ===")
        engine = FeatureEngine(source=src)
        df = engine.build_historical_matrix(symbol="BTCUSDT", days=10, timeframe="1h")
        print(f"✅ shape: {df.shape}, columns: {len(df.columns)}")
