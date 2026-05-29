"""
Feature Registry - 唯一特征注册表 (Domain 层)

核心原则：
- 这是所有特征定义的唯一真相源
- 任何地方引用特征名时必须从这里获取
- 特征名只能从 FEATURE_REGISTRY.keys() 中选择
- 每个特征同时拥有 FeatureCategory（数据源视角）和 AlphaFamily（alpha 研究视角）

添加新特征流程：
1. 在 FEATURE_REGISTRY 中添加 FeatureDef（含 alpha_family）
2. 如果有旧别名，更新 FEATURE_ALIASES（在 aliases.py）
3. 更新 CONTEXT_FEATURE_MAP（在 compute/context/feature_map.py）

Feature Taxonomy (Alpha Family):
┌──────────────────┬─────────────────────────────────────────────┐
│ AlphaFamily      │ 描述                                        │
├──────────────────┼─────────────────────────────────────────────┤
│ PRICE_ACTION     │ 价格收益、回撤、结构                         │
│ VOLATILITY       │ 波动率相关                                   │
│ FUNDING          │ 资金费率情绪                                 │
│ VOLUME           │ 成交量参与度                                 │
│ OPEN_INTEREST    │ 持仓量 / 杠杆结构                            │
│ ORDER_FLOW       │ 主动买卖流 / taker flow                      │
│ LIQUIDITY        │ 盘口深度 / 价差 / 流动性                     │
│ CROSS_SECTIONAL  │ 跨币种截面 alpha                             │
│ REGIME           │ 市场状态 / regime                            │
│ EVENT_DRIVEN     │ 事件驱动（爆仓、funding spike 等）            │
│ SHORT_EXHAUSTION │ 做空衰竭 / 爆顶反转                          │
└──────────────────┴─────────────────────────────────────────────┘
"""

from typing import Dict, List, Optional
from .schema import FeatureDef, FeatureCategory, FeatureValueType, AlphaFamily


FEATURE_REGISTRY: Dict[str, FeatureDef] = {}


# =====================================================================
# PRICE_ACTION Family
# =====================================================================

_raw_kline_features = [
    FeatureDef(
        name="open",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线开盘价",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="high",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线最高价",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="low",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线最低价",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="close",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线收盘价",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="volume",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线成交量",
        alpha_family=AlphaFamily.VOLUME,
    ),
]

_price_action_features = [
    FeatureDef(
        name="rsi_14",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="14周期 RSI 相对强弱指标",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="rsi_7",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="7周期 RSI 相对强弱指标",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="rsi_21",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="21周期 RSI 相对强弱指标",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="ema_10",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="10周期指数移动平均线",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="ema_20",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="20周期指数移动平均线",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="ema_50",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="50周期指数移动平均线",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="sma_10",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="10周期简单移动平均线",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="sma_20",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="20周期简单移动平均线",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="sma_50",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="50周期简单移动平均线",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="sma_100",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="100周期简单移动平均线",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="macd",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="MACD 主指标线 (DIF)",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="macd_signal",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="MACD 信号线 (DEA)",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="macd_hist",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="MACD 柱状图 (Histogram)",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="momentum_10",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="10周期动量指标",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="slope",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格趋势斜率",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="return_1h",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="1小时收益率",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="return_24h",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="24小时收益率",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="change",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格变化量",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="change_percent",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格变化百分比",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="closes",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.LIST,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="收盘价历史序列",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="highs",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.LIST,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="最高价历史序列",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="lows",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.LIST,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="最低价历史序列",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="support",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="支撑位",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="resistance",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="阻力位",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="structure",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.STRING,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格结构",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="strength",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="趋势强度",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="momentum_score",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="动量评分",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
    FeatureDef(
        name="drawdown_from_high",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="从高点回撤幅度",
        alpha_family=AlphaFamily.PRICE_ACTION,
    ),
]


# =====================================================================
# VOLATILITY Family
# =====================================================================

_volatility_features = [
    FeatureDef(
        name="bb_upper",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带上轨",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="bb_middle",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带中轨",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="bb_lower",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带下轨",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="bb_width",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带宽度 (绝对)",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="bb_width_pct",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带宽度 (百分比)",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="atr_14",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="14周期平均真实波幅",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="atr",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="平均真实波幅 (ATR_14 别名)",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="atr_pct",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="ATR 百分比 (相对于价格)",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="realized_vol",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="已实现波动率",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="realized_vol_zscore",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="已实现波动率 Z-Score",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
    FeatureDef(
        name="volatility_zscore",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="波动率 Z-Score (realized_vol_zscore 别名)",
        alpha_family=AlphaFamily.VOLATILITY,
    ),
]


# =====================================================================
# VOLUME Family
# =====================================================================

_volume_features = [
    FeatureDef(
        name="volume_ma",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="成交量移动平均",
        alpha_family=AlphaFamily.VOLUME,
    ),
    FeatureDef(
        name="volume_zscore",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="成交量 Z-Score",
        alpha_family=AlphaFamily.VOLUME,
    ),
    FeatureDef(
        name="volume_ratio",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="成交量比率 (当前/MA)",
        alpha_family=AlphaFamily.VOLUME,
    ),
]


# =====================================================================
# FUNDING Family
# =====================================================================

_funding_features = [
    FeatureDef(
        name="funding_rate",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率",
        alpha_family=AlphaFamily.FUNDING,
    ),
    FeatureDef(
        name="funding_zscore",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率 Z-Score",
        alpha_family=AlphaFamily.FUNDING,
    ),
    FeatureDef(
        name="funding_history",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.LIST,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率历史序列",
        alpha_family=AlphaFamily.FUNDING,
    ),
    FeatureDef(
        name="funding_mark_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="标记价格",
        alpha_family=AlphaFamily.FUNDING,
    ),
    FeatureDef(
        name="funding_index_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="指数价格",
        alpha_family=AlphaFamily.FUNDING,
    ),
    FeatureDef(
        name="mark_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="标记价格 (别名)",
        alpha_family=AlphaFamily.FUNDING,
    ),
    FeatureDef(
        name="index_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="指数价格 (别名)",
        alpha_family=AlphaFamily.FUNDING,
    ),
    FeatureDef(
        name="funding_extreme_reversal",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding", "open_interest"],
        description="资金费率极端反转信号",
        alpha_family=AlphaFamily.FUNDING,
    ),
]


# =====================================================================
# OPEN_INTEREST Family
# =====================================================================

_open_interest_features = [
    FeatureDef(
        name="oi",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量 (Open Interest)",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="oi_delta",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量变化量",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="oi_zscore",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量 Z-Score",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="oi_history",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.LIST,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量历史序列",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="oi_change",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量变化率",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="oi_funding_divergence",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest", "funding"],
        description="OI增长与Funding极端的背离",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="oi_squeeze_probability",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest", "funding"],
        description="杠杆挤压概率 (高OI+极端Funding)",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="oi_liq_pressure",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest", "funding"],
        description="潜在踩踏压力 (OI×Funding)",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="leverage_crowdedness",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest", "funding"],
        description="杠杆拥挤度",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
    FeatureDef(
        name="price_oi_divergence",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest", "kline"],
        description="价格与OI背离 (squeeze signal)",
        alpha_family=AlphaFamily.OPEN_INTEREST,
    ),
]


# =====================================================================
# ORDER_FLOW Family
# =====================================================================

_order_flow_features = [
    FeatureDef(
        name="cvd",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="成交量 delta (Cumulative Volume Delta)",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="cvd_slope",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="CVD 斜率",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="cvd_delta",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="CVD 变化量",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="cvd_zscore",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="CVD Z-Score",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="cumulative_delta",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="累计 delta",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="aggressive_buy_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动买入成交量",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="aggressive_sell_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动卖出成交量",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="aggressive_buy",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动买入 (aggressive_buy_volume 别名)",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="aggressive_sell",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动卖出 (aggressive_sell_volume 别名)",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="aggressive_ratio",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动买卖比率",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="taker_buy_ratio",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="Taker 买入占比",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="buy_sell_ratio",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="买卖量比率",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="trade_imbalance",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="买卖失衡度",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="trade_delta",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="交易 delta (CVD 别名)",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="trade_velocity",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="成交速度 (笔/秒)",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="large_trade_ratio",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大单成交占比",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="large_trade_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大单成交量",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="whale_buy_count",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户买入次数",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="whale_sell_count",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户卖出次数",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="whale_buy_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户买入成交量",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="whale_sell_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户卖出成交量",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="sweep_buy_score",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="买入扫单评分",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="sweep_sell_score",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="卖出扫单评分",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="trade_pressure_score",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="交易压力综合评分",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="long_pressure_score",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="多头压力评分",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="short_pressure_score",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="空头压力评分",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="squeeze_pressure_score",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="挤压压力评分 (替代OI条件)",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="flush_pressure_score",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="冲刷压力评分 (长期squeeze释放)",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="trade_price",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="最新成交价",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
    FeatureDef(
        name="trade_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="最新成交量",
        alpha_family=AlphaFamily.ORDER_FLOW,
    ),
]


# =====================================================================
# LIQUIDITY Family (Orderbook + Microstructure)
# =====================================================================

_liquidity_features = [
    FeatureDef(
        name="spread",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买卖价差 (绝对)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="spread_bps",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买卖价差 (基点)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="spread_estimate",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="价差估计 (由Trade合成)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="spread_pct_estimate",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="价差百分比估计 (由Trade合成)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="depth_ratio",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买卖深度比率",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="top5_bid_depth",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top5 买方深度",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="top5_ask_depth",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top5 卖方深度",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="microprice",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="微观价格 (深度加权中间价)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="microprice_estimate",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="微价格估计 (由Trade合成)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="imbalance_5",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top5 订单不平衡度",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="imbalance_20",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top20 订单不平衡度",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="imbalance_1",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="1档不平衡度 (由Trade合成)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="imbalance_10",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="10档不平衡度 (由Trade合成)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="imbalance_slope",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="不平衡度变化斜率",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="depth_pressure",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="深度压力 (imbalance × volume)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="depth_change",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="深度比率变化率",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="is_vacuum",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="是否流动性真空",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="vacuum_score",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="流动性真空评分",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="liquidity_vacuum",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="流动性真空 (is_vacuum 别名)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="liquidity_shift",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="流动性转移 (delta/total_volume)",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="cancel_rate",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="撤单率",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="spoof_probability",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="假挂单概率",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="wall_detection",
        category=FeatureCategory.MICROSTRUCTURE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大单墙检测",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="bid_price_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买一价",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="bid_volume_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买一量",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="ask_price_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="卖一价",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
    FeatureDef(
        name="ask_volume_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="卖一量",
        alpha_family=AlphaFamily.LIQUIDITY,
    ),
]


# =====================================================================
# CROSS_SECTIONAL Family
# =====================================================================

_cross_sectional_features = [
    FeatureDef(
        name="binance_return",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="币安收益率",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="okx_return",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="OKX 收益率",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="bybit_return",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="Bybit 收益率",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="basis",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="基差",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="premium",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="溢价",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="lead_exchange",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="领先交易所",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="lag_exchange",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="落后交易所",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="lead_lag_score",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="领先落后评分",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="relative_strength",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1h", "4h", "1d"],
        required_sources=["cross_market"],
        description="相对强弱 (vs BTC)",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="btc_beta",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1h", "4h", "1d"],
        required_sources=["cross_market"],
        description="BTC Beta 系数",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="btc_beta_residual",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1h", "4h", "1d"],
        required_sources=["cross_market"],
        description="BTC Beta 残差 (beta-neutral alpha)",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="volume_rank_cross_section",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1h", "4h", "1d"],
        required_sources=["cross_market"],
        description="跨币种成交量排名",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
    FeatureDef(
        name="sector_rotation",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["4h", "1d"],
        required_sources=["cross_market"],
        description="板块轮动信号",
        alpha_family=AlphaFamily.CROSS_SECTIONAL,
    ),
]


# =====================================================================
# REGIME Family
# =====================================================================

_regime_features = [
    FeatureDef(
        name="high_volatility",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="高波动率标记",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="low_liquidity",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="低流动性标记",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="regime_change",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="regime 切换标记",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="extreme_move",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="极端行情标记",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="risk_multiplier",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["composite"],
        description="风险乘数",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="volatility_regime",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["composite"],
        description="波动率 regime (low/normal/high/extreme)",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="trend_regime",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["composite"],
        description="趋势 regime (trend/chop/neutral)",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="liquidity_regime",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["composite"],
        description="流动性 regime (illiquid/normal/abundant)",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="risk_on_off",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["composite"],
        description="风险偏好状态 (-1~1, risk-off ~ risk-on)",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="primary_regime",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["composite"],
        description="主 regime (trend/chop/panic/squeeze/illiquid/high_leverage/neutral)",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="regime_risk_level",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["composite"],
        description="regime 风险等级 (0~1)",
        alpha_family=AlphaFamily.REGIME,
    ),
    FeatureDef(
        name="position_sizing_multiplier",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["composite"],
        description="仓位大小乘数 (由regime决定)",
        alpha_family=AlphaFamily.REGIME,
    ),
]


# =====================================================================
# SHORT_OVEREXTENSION Family (价格偏离度 - 涨得太离谱)
# =====================================================================

_short_overextension_features = [
    FeatureDef(
        name="distance_from_ma20",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格偏离 MA20 百分比 (做多超买信号)",
        alpha_family=AlphaFamily.SHORT_OVEREXTENSION,
    ),
    FeatureDef(
        name="distance_from_ma60",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格偏离 MA60 百分比 (中长期超买)",
        alpha_family=AlphaFamily.SHORT_OVEREXTENSION,
    ),
    FeatureDef(
        name="distance_from_vwap",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格偏离 VWAP 百分比",
        alpha_family=AlphaFamily.SHORT_OVEREXTENSION,
    ),
    FeatureDef(
        name="zscore_price",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格 Z-Score (相对100周期均值)",
        alpha_family=AlphaFamily.SHORT_OVEREXTENSION,
    ),
    FeatureDef(
        name="ma20_slope_zscore",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="MA20 斜率 Z-Score",
        alpha_family=AlphaFamily.SHORT_OVEREXTENSION,
    ),
    FeatureDef(
        name="price_deviation_band",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格偏离布林带上轨程度",
        alpha_family=AlphaFamily.SHORT_OVEREXTENSION,
    ),
]


# =====================================================================
# SHORT_PARABOLIC Family (抛物线阶段 - 加速上涨)
# =====================================================================

_short_parabolic_features = [
    FeatureDef(
        name="ret_3_acceleration",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="ret_3 加速指标 (ret_3 - ret_3.shift)",
        alpha_family=AlphaFamily.SHORT_PARABOLIC,
    ),
    FeatureDef(
        name="ret_5_acceleration",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="ret_5 加速指标 (ret_5 - ret_5.shift)",
        alpha_family=AlphaFamily.SHORT_PARABOLIC,
    ),
    FeatureDef(
        name="ret_10_acceleration",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="ret_10 加速指标",
        alpha_family=AlphaFamily.SHORT_PARABOLIC,
    ),
    FeatureDef(
        name="slope_acceleration",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="斜率变化率 (趋势加速)",
        alpha_family=AlphaFamily.SHORT_PARABOLIC,
    ),
    FeatureDef(
        name="curvature",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格曲率 (二阶导数)",
        alpha_family=AlphaFamily.SHORT_PARABOLIC,
    ),
    FeatureDef(
        name="velocity_increase",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="速度增量 (ret_1 - ret_1.rolling(5).mean())",
        alpha_family=AlphaFamily.SHORT_PARABOLIC,
    ),
    FeatureDef(
        name="momentum_divergence",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="动量背离 (价格创新高但RSI下降)",
        alpha_family=AlphaFamily.SHORT_PARABOLIC,
    ),
]


# =====================================================================
# SHORT_EXHAUSTION Family (做空衰竭 - 买盘衰竭)
# =====================================================================

_short_exhaustion_features = [
    FeatureDef(
        name="distance_from_high",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="距离高点的百分比 (正值=从高点下跌)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="parabolic_ret_10",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="10周期抛物线累计收益",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="parabolic_ret_zscore",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="抛物线收益Z-score（相对于历史）",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="volatility_spike",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="波动率尖峰",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="upper_shadow_ratio",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="上影线占比 (上影/(高-低))",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="consecutive_green",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="连续阳线数量",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="close_position_in_range",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="收盘价在 K 线范围内位置 (0=低,1=高)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="volume_climax",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="成交量高潮指标 (放量且波幅大)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="taker_buy_climax",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="Taker 买入高潮 (高买入率+高波动)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="new_high_60",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="60周期新高标记 (0/1)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="high_volume_decline",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="放量下跌标记 (0/1)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="funding_extreme_positive",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.INT,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率极端正向标记 (0/1) (多头拥挤)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="ret_5_percentile",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="ret_5 的百分位排名 (0~1)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="volume_spike_up",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="放量上涨标记 (ret>0 & volume_zscore>1.5)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="momentum_overheat",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="动量过热 (RSI>80 的 0/1 标记)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="breakout_volume_decay",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="突破后量能衰减 (new_high & volume下降)",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
    FeatureDef(
        name="distance_from_ma",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格偏离MA20百分比",
        alpha_family=AlphaFamily.SHORT_EXHAUSTION,
    ),
]


# =====================================================================
# SHORT_BREAKFAIL Family (失败突破 - 创新高后回落)
# =====================================================================

_short_breakfail_features = [
    FeatureDef(
        name="new_high_20",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="20周期新高标记 (0/1)",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
    FeatureDef(
        name="new_high_60",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="60周期新高标记 (0/1)",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
    FeatureDef(
        name="new_high_120",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="120周期新高标记 (0/1)",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
    FeatureDef(
        name="breakout_strength",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="突破强度 (突破幅度/ATR)",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
    FeatureDef(
        name="breakout_failure",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="突破失败信号 (创新高后回落幅度)",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
    FeatureDef(
        name="breakout_retraction",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="突破回撤比率 (回落/突破幅度)",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
    FeatureDef(
        name="double_top_probability",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="双顶形态概率",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
    FeatureDef(
        name="failed_rebound_strength",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="反弹失败强度",
        alpha_family=AlphaFamily.SHORT_BREAKFAIL,
    ),
]


# =====================================================================
# SHORT_CROWDED Family (多头拥挤 - 杠杆/资金费率极端)
# =====================================================================

_short_crowded_features = [
    FeatureDef(
        name="funding_zscore_long",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率 Z-Score (多头极端信号)",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="oi_zscore_long",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量 Z-Score (多头拥挤信号)",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="basis_zscore",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="基差 Z-Score (正向基差极端)",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="long_short_ratio",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="多空持仓比率",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="leverage_ratio_long",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="多头杠杆率",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="funding_oi_combined",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding", "open_interest"],
        description="Funding×OI 综合拥挤度",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="crowded_long_score",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["composite"],
        description="多头拥挤综合评分",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="liquidation_risk_long",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="多头爆仓风险指标",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="short_squeeze_prob",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest", "funding"],
        description="逼空概率 (低OI+负Funding)",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
    FeatureDef(
        name="margin_usage_long",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="多头保证金使用率",
        alpha_family=AlphaFamily.SHORT_CROWDED,
    ),
]


# =====================================================================
# EVENT_DRIVEN Family
# =====================================================================

_event_driven_features = [
    FeatureDef(
        name="liquidation_long",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="多头强平量",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_short",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="空头强平量",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_total",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="总强平量",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_long_zscore",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="多头强平量 Z-Score",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_short_zscore",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="空头强平量 Z-Score",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_reversal_signal",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平反转信号",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_side",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平方向",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_price",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平价格",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_quantity",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平数量",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_value_usd",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平价值 (USD)",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_spike",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="爆仓尖峰 (Z-Score)",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_pressure",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="爆仓压力 (long-short差值)",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="long_liq_ratio",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="多头爆仓占比",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_cluster",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="爆仓聚集度",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_acceleration",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="爆仓加速率",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="liquidation_chain_probability",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="连锁爆仓概率",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="long_short_liq_ratio",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="多空爆仓比率",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="funding_explosion",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率爆炸事件 (|zscore|>3)",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="volume_vacuum_event",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.BOOL,
        default_timeframes=["1m", "5m", "15m"],
        required_sources=["kline"],
        description="成交量真空事件 (volume_zscore < -2)",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
    FeatureDef(
        name="news_event",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="新闻事件标记",
        alpha_family=AlphaFamily.EVENT_DRIVEN,
    ),
]


# =====================================================================
# RISK / EXECUTION (非 alpha, 保留在 COMPOSITE 但无 alpha_family)
# =====================================================================

_risk_execution_features = [
    FeatureDef(
        name="overtrading",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="过度交易标记",
    ),
    FeatureDef(
        name="drawdown_exceeded",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="回撤超限标记",
    ),
    FeatureDef(
        name="slippage_warning",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="滑点警告标记",
    ),
    FeatureDef(
        name="execution_paused",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="执行暂停标记",
    ),
]


# =====================================================================
# 填充注册表
# =====================================================================

_ALL_FEATURE_GROUPS = [
    _raw_kline_features,
    _price_action_features,
    _volatility_features,
    _volume_features,
    _funding_features,
    _open_interest_features,
    _order_flow_features,
    _liquidity_features,
    _cross_sectional_features,
    _regime_features,
    _short_overextension_features,
    _short_parabolic_features,
    _short_exhaustion_features,
    _short_breakfail_features,
    _short_crowded_features,
    _event_driven_features,
    _risk_execution_features,
]

for features in _ALL_FEATURE_GROUPS:
    for feature in features:
        FEATURE_REGISTRY[feature.name] = feature


# =====================================================================
# 公共 API
# =====================================================================

def get_feature_def(name: str) -> Optional[FeatureDef]:
    from .aliases import normalize_feature_name
    normalized_name = normalize_feature_name(name)
    return FEATURE_REGISTRY.get(normalized_name)


def is_feature_registered(name: str) -> bool:
    from .aliases import normalize_feature_name
    normalized_name = normalize_feature_name(name)
    return normalized_name in FEATURE_REGISTRY


def list_features_by_category(category: FeatureCategory) -> List[FeatureDef]:
    return [
        feature for feature in FEATURE_REGISTRY.values()
        if feature.category == category
    ]


def list_features_by_alpha_family(family: AlphaFamily) -> List[FeatureDef]:
    return [
        feature for feature in FEATURE_REGISTRY.values()
        if feature.alpha_family == family
    ]


def list_all_feature_names() -> List[str]:
    return list(FEATURE_REGISTRY.keys())


def get_alpha_family_coverage() -> Dict[AlphaFamily, Dict[str, int]]:
    """返回每个 AlphaFamily 的覆盖情况

    Returns:
        {family: {"count": N, "with_extractor": M}}
        with_extractor: 有对应提取代码的 feature 数量
    """
    coverage: Dict[AlphaFamily, Dict[str, int]] = {}
    for family in AlphaFamily:
        features = list_features_by_alpha_family(family)
        coverage[family] = {
            "count": len(features),
        }
    return coverage


def get_taxonomy_summary() -> str:
    """返回 Feature Taxonomy 摘要"""
    lines = []
    lines.append("=" * 70)
    lines.append("Feature Taxonomy Summary")
    lines.append("=" * 70)

    for family in AlphaFamily:
        features = list_features_by_alpha_family(family)
        names = [f.name for f in features]
        lines.append(f"\n{family.value.upper()} ({len(features)} features):")
        for name in names:
            lines.append(f"  - {name}")

    total = len(FEATURE_REGISTRY)
    with_family = sum(1 for f in FEATURE_REGISTRY.values() if f.alpha_family is not None)
    lines.append(f"\nTotal: {total} features, {with_family} with alpha_family")

    return "\n".join(lines)


# =====================================================================
# 导入时校验
# =====================================================================

_duplicate_names = set()
_seen_names = set()
for name in FEATURE_REGISTRY:
    if name in _seen_names:
        _duplicate_names.add(name)
    _seen_names.add(name)

if _duplicate_names:
    raise ValueError(f"FEATURE_REGISTRY 包含重复名称: {sorted(_duplicate_names)}")
