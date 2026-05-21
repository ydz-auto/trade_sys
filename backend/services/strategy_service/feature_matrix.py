"""
Feature Matrix - 统一的特征矩阵管理

合并原有的因子层和特征层，形成统一的 Feature Matrix：

Feature Matrix
├─ raw_features
│   ├─ price, volume, funding, OI, liquidation ...
├─ derived_features (原因子)
│   ├─ RSI, MACD, Bollinger, funding_zscore ...
├─ microstructure_features
│   ├─ spread, imbalance, trade_delta, sweep_score ...
├─ cross_market_features
│   ├─ basis, lead-lag, risk-on/off ...
├─ event/narrative_features
│   ├─ news_sentiment, twitter_velocity, bullish_score ...
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import pandas as pd
import numpy as np
from pathlib import Path

from infrastructure.logging import get_logger
from infrastructure.data_lake import get_features_path

logger = get_logger("feature_matrix")


class FeatureCategory(Enum):
    """特征分类枚举"""
    RAW = "raw"  # 原始特征
    DERIVED = "derived"  # 衍生特征（原因子层）
    MICROSTRUCTURE = "microstructure"  # 微观结构特征
    CROSS_MARKET = "cross_market"  # 跨市场特征
    EVENT = "event"  # 事件/叙事特征


@dataclass
class FeatureMetadata:
    """特征元数据"""
    name: str
    name_en: str
    category: FeatureCategory
    description: str
    data_type: str = "float"
    normalization_range: Optional[tuple] = None  # (min, max)
    zscore_window: int = 288  # 默认5分钟K线，288根=24小时
    is_factor: bool = False  # 是否为原因子（兼容保留）
    source: str = "internal"  # 数据来源
    default_weight: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)


class FeatureMatrix:
    """
    统一特征矩阵管理类

    功能：
    - 加载和管理特征数据
    - 特征标准化
    - 特征选择
    - 特征矩阵输出
    """

    # 特征元数据定义
    FEATURE_METADATA: Dict[str, FeatureMetadata] = {
        # ==================== RAW FEATURES ====================
        "open": FeatureMetadata(
            name="开盘价",
            name_en="Open Price",
            category=FeatureCategory.RAW,
            description="K线开盘价"
        ),
        "high": FeatureMetadata(
            name="最高价",
            name_en="High Price",
            category=FeatureCategory.RAW,
            description="K线最高价"
        ),
        "low": FeatureMetadata(
            name="最低价",
            name_en="Low Price",
            category=FeatureCategory.RAW,
            description="K线最低价"
        ),
        "close": FeatureMetadata(
            name="收盘价",
            name_en="Close Price",
            category=FeatureCategory.RAW,
            description="K线收盘价"
        ),
        "volume": FeatureMetadata(
            name="成交量",
            name_en="Volume",
            category=FeatureCategory.RAW,
            description="K线成交量"
        ),
        "funding_rate": FeatureMetadata(
            name="资金费率",
            name_en="Funding Rate",
            category=FeatureCategory.RAW,
            description="币安永续合约资金费率"
        ),
        "open_interest": FeatureMetadata(
            name="持仓量",
            name_en="Open Interest",
            category=FeatureCategory.RAW,
            description="合约持仓量"
        ),
        "long_liquidations": FeatureMetadata(
            name="多头爆仓",
            name_en="Long Liquidations",
            category=FeatureCategory.RAW,
            description="多头爆仓量"
        ),
        "short_liquidations": FeatureMetadata(
            name="空头爆仓",
            name_en="Short Liquidations",
            category=FeatureCategory.RAW,
            description="空头爆仓量"
        ),

        # ==================== DERIVED FEATURES (原因子层) ====================
        "rsi_14": FeatureMetadata(
            name="RSI 14",
            name_en="RSI 14",
            category=FeatureCategory.DERIVED,
            description="14周期相对强弱指标",
            normalization_range=(0, 100),
            is_factor=True
        ),
        "rsi_7": FeatureMetadata(
            name="RSI 7",
            name_en="RSI 7",
            category=FeatureCategory.DERIVED,
            description="7周期相对强弱指标",
            normalization_range=(0, 100),
            is_factor=True
        ),
        "macd_line": FeatureMetadata(
            name="MACD 快线",
            name_en="MACD Line",
            category=FeatureCategory.DERIVED,
            description="MACD 快线 (EMA12-EMA26)",
            is_factor=True
        ),
        "macd_signal": FeatureMetadata(
            name="MACD 信号线",
            name_en="MACD Signal",
            category=FeatureCategory.DERIVED,
            description="MACD 信号线 (EMA9)",
            is_factor=True
        ),
        "macd_histogram": FeatureMetadata(
            name="MACD 柱",
            name_en="MACD Histogram",
            category=FeatureCategory.DERIVED,
            description="MACD 柱",
            is_factor=True
        ),
        "bollinger_upper": FeatureMetadata(
            name="布林带上轨",
            name_en="Bollinger Upper",
            category=FeatureCategory.DERIVED,
            description="布林带上轨 (MA20 + 2σ",
            is_factor=True
        ),
        "bollinger_lower": FeatureMetadata(
            name="布林带下轨",
            name_en="Bollinger Lower",
            category=FeatureCategory.DERIVED,
            description="布林带下轨 (MA20 - 2σ)",
            is_factor=True
        ),
        "bollinger_middle": FeatureMetadata(
            name="布林带中轨",
            name_en="Bollinger Middle",
            category=FeatureCategory.DERIVED,
            description="布林带中轨 (MA20)",
            is_factor=True
        ),
        "atr_14": FeatureMetadata(
            name="ATR 14",
            name_en="ATR 14",
            category=FeatureCategory.DERIVED,
            description="14周期平均真实波幅",
            is_factor=True
        ),
        "volatility_24h": FeatureMetadata(
            name="24小时波动率",
            name_en="24h Volatility",
            category=FeatureCategory.DERIVED,
            description="过去24小时价格波动率",
            is_factor=True
        ),
        "trend_ma_short": FeatureMetadata(
            name="短期趋势",
            name_en="Short Term Trend",
            category=FeatureCategory.DERIVED,
            description="短期趋势因子",
            is_factor=True
        ),
        "trend_ma_long": FeatureMetadata(
            name="长期趋势",
            name_en="Long Term Trend",
            category=FeatureCategory.DERIVED,
            description="长期趋势因子",
            is_factor=True
        ),
        "funding_zscore": FeatureMetadata(
            name="资金费率Z分数",
            name_en="Funding Z-Score",
            category=FeatureCategory.DERIVED,
            description="资金费率Z分数标准化",
            is_factor=True
        ),
        "oi_change_24h": FeatureMetadata(
            name="持仓量24小时变化",
            name_en="OI Change 24h",
            category=FeatureCategory.DERIVED,
            description="持仓量24小时变化率",
            is_factor=True
        ),
        "volume_zscore": FeatureMetadata(
            name="成交量Z分数",
            name_en="Volume Z-Score",
            category=FeatureCategory.DERIVED,
            description="成交量Z分数标准化",
            is_factor=True
        ),

        # ==================== MICROSTRUCTURE FEATURES ====================
        "spread": FeatureMetadata(
            name="买卖价差",
            name_en="Spread",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优买卖价价差"
        ),
        "spread_pct": FeatureMetadata(
            name="买卖价差百分比",
            name_en="Spread %",
            category=FeatureCategory.MICROSTRUCTURE,
            description="买卖价差百分比"
        ),
        "mid_price": FeatureMetadata(
            name="中间价",
            name_en="Mid Price",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优买卖价中间价"
        ),
        "microprice": FeatureMetadata(
            name="微观价格",
            name_en="Microprice",
            category=FeatureCategory.MICROSTRUCTURE,
            description="订单簿加权微观价格"
        ),
        "imbalance_1": FeatureMetadata(
            name="1档订单簿失衡",
            name_en="Imbalance 1",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优1档买卖量失衡"
        ),
        "imbalance_5": FeatureMetadata(
            name="5档订单簿失衡",
            name_en="Imbalance 5",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优5档买卖量失衡"
        ),
        "imbalance_10": FeatureMetadata(
            name="10档订单簿失衡",
            name_en="Imbalance 10",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优10档买卖量失衡"
        ),
        "imbalance_slope": FeatureMetadata(
            name="订单簿失衡斜率",
            name_en="Imbalance Slope",
            category=FeatureCategory.MICROSTRUCTURE,
            description="订单簿深度斜率"
        ),
        "top5_bid_volume": FeatureMetadata(
            name="5档买单量",
            name_en="Top5 Bid Volume",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优5档买单总量"
        ),
        "top5_ask_volume": FeatureMetadata(
            name="5档卖单量",
            name_en="Top5 Ask Volume",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优5档卖单总量"
        ),
        "top10_bid_volume": FeatureMetadata(
            name="10档买单量",
            name_en="Top10 Bid Volume",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优10档买单总量"
        ),
        "top10_ask_volume": FeatureMetadata(
            name="10档卖单量",
            name_en="Top10 Ask Volume",
            category=FeatureCategory.MICROSTRUCTURE,
            description="最优10档卖单总量"
        ),
        "depth_ratio": FeatureMetadata(
            name="订单簿深度比",
            name_en="Depth Ratio",
            category=FeatureCategory.MICROSTRUCTURE,
            description="买卖深度比"
        ),
        "depth_change": FeatureMetadata(
            name="订单簿深度变化",
            name_en="Depth Change",
            category=FeatureCategory.MICROSTRUCTURE,
            description="订单簿深度变化"
        ),
        "trade_delta": FeatureMetadata(
            name="成交delta",
            name_en="Trade Delta",
            category=FeatureCategory.MICROSTRUCTURE,
            description="主动买卖成交差"
        ),
        "cumulative_delta": FeatureMetadata(
            name="累计成交delta",
            name_en="Cumulative Delta",
            category=FeatureCategory.MICROSTRUCTURE,
            description="累计主动买卖成交差"
        ),
        "aggressive_buy_volume": FeatureMetadata(
            name="主动买入量",
            name_en="Aggressive Buy Volume",
            category=FeatureCategory.MICROSTRUCTURE,
            description="主动吃卖单成交量"
        ),
        "aggressive_sell_volume": FeatureMetadata(
            name="主动卖出量",
            name_en="Aggressive Sell Volume",
            category=FeatureCategory.MICROSTRUCTURE,
            description="主动吃买单成交量"
        ),
        "large_trade_ratio": FeatureMetadata(
            name="大单比例",
            name_en="Large Trade Ratio",
            category=FeatureCategory.MICROSTRUCTURE,
            description="大单占比"
        ),
        "trade_velocity": FeatureMetadata(
            name="成交速度",
            name_en="Trade Velocity",
            category=FeatureCategory.MICROSTRUCTURE,
            description="单位时间成交量"
        ),
        "sweep_score": FeatureMetadata(
            name="扫单分数",
            name_en="Sweep Score",
            category=FeatureCategory.MICROSTRUCTURE,
            description="大单扫单强度"
        ),

        # ==================== CROSS MARKET FEATURES ====================
        "basis_binance_okx": FeatureMetadata(
            name="币安-OKX基差",
            name_en="Binance-OKX Basis",
            category=FeatureCategory.CROSS_MARKET,
            description="币安与OKX永续合约基差"
        ),
        "basis_futures_spot": FeatureMetadata(
            name="期现基差",
            name_en="Futures-Spot Basis",
            category=FeatureCategory.CROSS_MARKET,
            description="期现货基差"
        ),
        "btc_dominance": FeatureMetadata(
            name="BTC市占率",
            name_en="BTC Dominance",
            category=FeatureCategory.CROSS_MARKET,
            description="BTC市值占比"
        ),
        "vix_crypto": FeatureMetadata(
            name="加密货币VIX",
            name_en="Crypto VIX",
            category=FeatureCategory.CROSS_MARKET,
            description="加密货币波动率指数"
        ),
        "risk_on_off": FeatureMetadata(
            name="风险开关",
            name_en="Risk On/Off",
            category=FeatureCategory.CROSS_MARKET,
            description="市场风险情绪开关"
        ),
        "usd_weakness": FeatureMetadata(
            name="USD弱势",
            name_en="USD Weakness",
            category=FeatureCategory.CROSS_MARKET,
            description="USD汇率弱势程度"
        ),

        # ==================== EVENT/NARRATIVE FEATURES ====================
        "news_sentiment": FeatureMetadata(
            name="新闻情绪",
            name_en="News Sentiment",
            category=FeatureCategory.EVENT,
            description="新闻情绪得分"
        ),
        "twitter_velocity": FeatureMetadata(
            name="Twitter热度",
            name_en="Twitter Velocity",
            category=FeatureCategory.EVENT,
            description="Twitter提及速度"
        ),
        "news_velocity": FeatureMetadata(
            name="新闻速度",
            name_en="News Velocity",
            category=FeatureCategory.EVENT,
            description="新闻发布速度"
        ),
        "bullish_score": FeatureMetadata(
            name="看涨分数",
            name_en="Bullish Score",
            category=FeatureCategory.EVENT,
            description="叙事看涨得分"
        ),
        "bearish_score": FeatureMetadata(
            name="看跌分数",
            name_en="Bearish Score",
            category=FeatureCategory.EVENT,
            description="叙事看跌得分"
        ),
    }

    def __init__(self, data_path: Optional[str] = None):
        if data_path:
            self.data_path = Path(data_path)
        else:
            self.data_path = get_features_path()
        self.df: Optional[pd.DataFrame] = None
        self.symbol: str = ""

    @classmethod
    def load_for_symbol(cls, symbol: str, exchange: str = "binance") -> "FeatureMatrix":
        """
        加载指定币种的特征矩阵

        从预计算的特征文件加载数据
        """
        instance = cls()
        instance.symbol = symbol
        
        feature_path = instance.data_path / exchange / symbol / "features_with_structure.parquet"
        
        if not feature_path.exists():
            logger.warning(f"Feature file not found: {feature_path}")
            instance.df = pd.DataFrame()
            return instance
            
        instance.df = pd.read_parquet(feature_path)
        logger.info(f"Loaded Feature Matrix for {symbol}: {instance.df.shape[0]} rows, {instance.df.shape[1]} features")
        return instance

    def get_features_by_category(self, category: FeatureCategory) -> List[str]:
        """获取指定分类的特征列表"""
        return [
            name for name, meta in self.FEATURE_METADATA.items()
            if meta.category == category
            and name in self.df.columns
        ]

    def get_derived_features(self) -> List[str]:
        """获取衍生特征列表（原因子层）"""
        return self.get_features_by_category(FeatureCategory.DERIVED)

    def get_raw_features(self) -> List[str]:
        """获取原始特征列表"""
        return self.get_features_by_category(FeatureCategory.RAW)

    def get_microstructure_features(self) -> List[str]:
        """获取微观结构特征列表"""
        return self.get_features_by_category(FeatureCategory.MICROSTRUCTURE)

    def get_cross_market_features(self) -> List[str]:
        """获取跨市场特征列表"""
        return self.get_features_by_category(FeatureCategory.CROSS_MARKET)

    def get_event_features(self) -> List[str]:
        """获取事件特征列表"""
        return self.get_features_by_category(FeatureCategory.EVENT)

    def normalize_feature(self, feature_name: str, method: str = "zscore") -> pd.Series:
        """
        标准化特征

        方法:
            zscore: Z分数标准化
            minmax: 最小最大标准化
        """
        if feature_name not in self.df.columns:
            return pd.Series()
            
        if method == "zscore":
            return (self.df[feature_name] - self.df[feature_name].mean()) / self.df[feature_name].std()
        elif method == "minmax":
            min_val = self.df[feature_name].min()
            max_val = self.df[feature_name].max()
            return (self.df[feature_name] - min_val) / (max_val - min_val)
        else:
            return self.df[feature_name]

    def get_feature_matrix(self, feature_names: Optional[List[str]] = None) -> pd.DataFrame:
        """
        获取特征矩阵

        Args:
            feature_names: 指定特征列表，None 返回所有特征
        """
        if feature_names is None:
            feature_names = list(self.FEATURE_METADATA.keys())
            
        available_features = [f for f in feature_names if f in self.df.columns]
        return self.df[available_features].copy()

    def add_future_returns(self, horizon: int = 12) -> pd.DataFrame:
        """
        添加未来收益率列

        Args:
            horizon: 预测窗口（12=1小时，5分钟K线）
        """
        df = self.df.copy()
        df[f"future_ret_{horizon}"] = df["close"].pct_change(-horizon).shift(-horizon)
        return df

    @classmethod
    def get_metadata(cls, feature_name: str) -> Optional[FeatureMetadata]:
        """获取特征元数据"""
        return cls.FEATURE_METADATA.get(feature_name)

    def summary(self) -> Dict[str, Any]:
        """获取特征矩阵摘要"""
        if self.df is None or self.df.empty:
            return {"status": "empty"}
            
        return {
            "symbol": self.symbol,
            "rows": len(self.df),
            "features_total": len(self.df.columns),
            "features_raw": len(self.get_raw_features()),
            "features_derived": len(self.get_derived_features()),
            "features_microstructure": len(self.get_microstructure_features()),
            "features_cross_market": len(self.get_cross_market_features()),
            "features_event": len(self.get_event_features()),
            "date_range": {
                "start": self.df["datetime"].min() if "datetime" in self.df.columns else None,
                "end": self.df["datetime"].max() if "datetime" in self.df.columns else None
            }
        }
