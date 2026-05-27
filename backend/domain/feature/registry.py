"""
Feature Registry - 唯一特征注册表 (Domain 层)

核心原则：
- 这是所有特征定义的唯一真相源
- 任何地方引用特征名时必须从这里获取
- 特征名只能从 FEATURE_REGISTRY.keys() 中选择

添加新特征流程：
1. 在 FEATURE_REGISTRY 中添加 FeatureDef
2. 如果有旧别名，更新 FEATURE_ALIASES（在 aliases.py）
3. 更新 CONTEXT_FEATURE_MAP（在 compute/context/feature_map.py）
"""

from typing import Dict, Optional
from .schema import FeatureDef, FeatureCategory, FeatureValueType


# ========== 唯一真相源：特征注册表 ==========
FEATURE_REGISTRY: Dict[str, FeatureDef] = {}


# ========== 原始 K 线特征 ==========
_raw_kline_features = [
    FeatureDef(
        name="open",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线开盘价",
    ),
    FeatureDef(
        name="high",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线最高价",
    ),
    FeatureDef(
        name="low",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线最低价",
    ),
    FeatureDef(
        name="close",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线收盘价",
    ),
    FeatureDef(
        name="volume",
        category=FeatureCategory.RAW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="K线成交量",
    ),
]


# ========== 技术指标特征 ==========
_technical_features = [
    # RSI 系列
    FeatureDef(
        name="rsi_14",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="14周期 RSI 相对强弱指标",
    ),
    FeatureDef(
        name="rsi_7",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="7周期 RSI 相对强弱指标",
    ),
    FeatureDef(
        name="rsi_21",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="21周期 RSI 相对强弱指标",
    ),
    
    # EMA 系列
    FeatureDef(
        name="ema_10",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="10周期指数移动平均线",
    ),
    FeatureDef(
        name="ema_20",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="20周期指数移动平均线",
    ),
    FeatureDef(
        name="ema_50",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="50周期指数移动平均线",
    ),
    
    # SMA 系列
    FeatureDef(
        name="sma_10",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="10周期简单移动平均线",
    ),
    FeatureDef(
        name="sma_20",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="20周期简单移动平均线",
    ),
    FeatureDef(
        name="sma_50",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="50周期简单移动平均线",
    ),
    FeatureDef(
        name="sma_100",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="100周期简单移动平均线",
    ),
    
    # MACD 系列
    FeatureDef(
        name="macd",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="MACD 主指标线 (DIF)",
    ),
    FeatureDef(
        name="macd_signal",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="MACD 信号线 (DEA)",
    ),
    FeatureDef(
        name="macd_hist",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="MACD 柱状图 (Histogram)",
    ),
    
    # 布林带系列
    FeatureDef(
        name="bb_upper",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带上轨",
    ),
    FeatureDef(
        name="bb_middle",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带中轨",
    ),
    FeatureDef(
        name="bb_lower",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带下轨",
    ),
    FeatureDef(
        name="bb_width",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带宽度 (绝对)",
    ),
    FeatureDef(
        name="bb_width_pct",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="布林带宽度 (百分比)",
    ),
    
    # ATR 系列
    FeatureDef(
        name="atr_14",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="14周期平均真实波幅",
    ),
    FeatureDef(
        name="atr",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="平均真实波幅 (ATR_14 别名)",
    ),
    FeatureDef(
        name="atr_pct",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="ATR 百分比 (相对于价格)",
    ),
    
    # 成交量衍生
    FeatureDef(
        name="volume_ma",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="成交量移动平均",
    ),
    FeatureDef(
        name="volume_zscore",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="成交量 Z-Score",
    ),
    FeatureDef(
        name="volume_ratio",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="成交量比率 (当前/MA)",
    ),
    
    # 其他技术指标
    FeatureDef(
        name="momentum_10",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="10周期动量指标",
    ),
    FeatureDef(
        name="slope",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格趋势斜率",
    ),
    FeatureDef(
        name="realized_vol",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="已实现波动率",
    ),
    FeatureDef(
        name="realized_vol_zscore",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="已实现波动率 Z-Score",
    ),
]


# ========== 衍生品特征 ==========
_derivatives_features = [
    # 持仓量
    FeatureDef(
        name="oi",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量 (Open Interest)",
    ),
    FeatureDef(
        name="oi_delta",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量变化量",
    ),
    FeatureDef(
        name="oi_zscore",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量 Z-Score",
    ),
    FeatureDef(
        name="oi_history",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.LIST,
        default_timeframes=[],
        required_sources=["open_interest"],
        description="持仓量历史序列",
    ),
    
    # 资金费率
    FeatureDef(
        name="funding_rate",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率",
    ),
    FeatureDef(
        name="funding_zscore",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率 Z-Score",
    ),
    FeatureDef(
        name="funding_history",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.LIST,
        default_timeframes=[],
        required_sources=["funding"],
        description="资金费率历史序列",
    ),
    
    # 其他衍生品
    FeatureDef(
        name="funding_mark_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="标记价格",
    ),
    FeatureDef(
        name="funding_index_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="指数价格",
    ),
    FeatureDef(
        name="mark_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="标记价格 (别名)",
    ),
    FeatureDef(
        name="index_price",
        category=FeatureCategory.DERIVATIVES,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["funding"],
        description="指数价格 (别名)",
    ),
]


# ========== 强平特征 ==========
_liquidation_features = [
    FeatureDef(
        name="liquidation_long",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="多头强平量",
    ),
    FeatureDef(
        name="liquidation_short",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="空头强平量",
    ),
    FeatureDef(
        name="liquidation_total",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="总强平量",
    ),
    FeatureDef(
        name="liquidation_long_zscore",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="多头强平量 Z-Score",
    ),
    FeatureDef(
        name="liquidation_short_zscore",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="空头强平量 Z-Score",
    ),
    FeatureDef(
        name="liquidation_reversal_signal",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平反转信号",
    ),
    FeatureDef(
        name="liquidation_side",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平方向",
    ),
    FeatureDef(
        name="liquidation_price",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平价格",
    ),
    FeatureDef(
        name="liquidation_quantity",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平数量",
    ),
    FeatureDef(
        name="liquidation_value_usd",
        category=FeatureCategory.LIQUIDATION,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["liquidation"],
        description="强平价值 (USD)",
    ),
]


# ========== 订单簿特征 ==========
_orderbook_features = [
    FeatureDef(
        name="spread",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买卖价差 (绝对)",
    ),
    FeatureDef(
        name="spread_bps",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买卖价差 (基点)",
    ),
    FeatureDef(
        name="depth_ratio",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买卖深度比率",
    ),
    FeatureDef(
        name="top5_bid_depth",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top5 买方深度",
    ),
    FeatureDef(
        name="top5_ask_depth",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top5 卖方深度",
    ),
    FeatureDef(
        name="microprice",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="微观价格 (深度加权中间价)",
    ),
    FeatureDef(
        name="imbalance_5",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top5 订单不平衡度",
    ),
    FeatureDef(
        name="imbalance_20",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="Top20 订单不平衡度",
    ),
    FeatureDef(
        name="is_vacuum",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="是否流动性真空",
    ),
    FeatureDef(
        name="vacuum_score",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="流动性真空评分",
    ),
    FeatureDef(
        name="cancel_rate",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="撤单率",
    ),
    FeatureDef(
        name="liquidity_vacuum",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="流动性真空 (is_vacuum 别名)",
    ),
    FeatureDef(
        name="bid_price_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买一价",
    ),
    FeatureDef(
        name="bid_volume_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="买一量",
    ),
    FeatureDef(
        name="ask_price_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="卖一价",
    ),
    FeatureDef(
        name="ask_volume_0",
        category=FeatureCategory.ORDERBOOK,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["orderbook"],
        description="卖一量",
    ),
]


# ========== 资金流特征 ==========
_flow_features = [
    FeatureDef(
        name="cvd",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="成交量 delta (Cumulative Volume Delta)",
    ),
    FeatureDef(
        name="cvd_slope",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="CVD 斜率",
    ),
    FeatureDef(
        name="cumulative_delta",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="累计 delta",
    ),
    FeatureDef(
        name="aggressive_buy_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动买入成交量",
    ),
    FeatureDef(
        name="aggressive_sell_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动卖出成交量",
    ),
    FeatureDef(
        name="aggressive_buy",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动买入 (aggressive_buy_volume 别名)",
    ),
    FeatureDef(
        name="aggressive_sell",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动卖出 (aggressive_sell_volume 别名)",
    ),
    FeatureDef(
        name="aggressive_ratio",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="主动买卖比率",
    ),
    FeatureDef(
        name="whale_buy_count",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户买入次数",
    ),
    FeatureDef(
        name="whale_sell_count",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.INT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户卖出次数",
    ),
    FeatureDef(
        name="whale_buy_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户买入成交量",
    ),
    FeatureDef(
        name="whale_sell_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="大户卖出成交量",
    ),
    FeatureDef(
        name="trade_delta",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="交易 delta (CVD 别名)",
    ),
    FeatureDef(
        name="trade_price",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="最新成交价",
    ),
    FeatureDef(
        name="trade_volume",
        category=FeatureCategory.FLOW,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["trade"],
        description="最新成交量",
    ),
]


# ========== 价格衍生特征 ==========
_price_derived_features = [
    FeatureDef(
        name="return_1h",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="1小时收益率",
    ),
    FeatureDef(
        name="return_24h",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="24小时收益率",
    ),
    FeatureDef(
        name="change",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格变化量",
    ),
    FeatureDef(
        name="change_percent",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格变化百分比",
    ),
    FeatureDef(
        name="closes",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.LIST,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="收盘价历史序列",
    ),
    FeatureDef(
        name="highs",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.LIST,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="最高价历史序列",
    ),
    FeatureDef(
        name="lows",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.LIST,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="最低价历史序列",
    ),
    FeatureDef(
        name="support",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="支撑位",
    ),
    FeatureDef(
        name="resistance",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="阻力位",
    ),
    FeatureDef(
        name="structure",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.STRING,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="价格结构",
    ),
    FeatureDef(
        name="strength",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="趋势强度",
    ),
    FeatureDef(
        name="momentum_score",
        category=FeatureCategory.TECHNICAL,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=["1m", "5m", "15m", "1h", "4h"],
        required_sources=["kline"],
        description="动量评分",
    ),
]


# ========== 跨市场特征 ==========
_cross_market_features = [
    FeatureDef(
        name="binance_return",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="币安收益率",
    ),
    FeatureDef(
        name="okx_return",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="OKX 收益率",
    ),
    FeatureDef(
        name="bybit_return",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="Bybit 收益率",
    ),
    FeatureDef(
        name="basis",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="基差",
    ),
    FeatureDef(
        name="premium",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="溢价",
    ),
    FeatureDef(
        name="lead_exchange",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="领先交易所",
    ),
    FeatureDef(
        name="lag_exchange",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.STRING,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="落后交易所",
    ),
    FeatureDef(
        name="lead_lag_score",
        category=FeatureCategory.CROSS_MARKET,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["cross_market"],
        description="领先落后评分",
    ),
]


# ========== 风险特征 ==========
_risk_features = [
    FeatureDef(
        name="high_volatility",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="高波动率标记",
    ),
    FeatureDef(
        name="low_liquidity",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="低流动性标记",
    ),
    FeatureDef(
        name="news_event",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="新闻事件标记",
    ),
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
    FeatureDef(
        name="regime_change",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description=" regime 切换标记",
    ),
    FeatureDef(
        name="extreme_move",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.BOOL,
        default_timeframes=[],
        required_sources=["composite"],
        description="极端行情标记",
    ),
    FeatureDef(
        name="risk_multiplier",
        category=FeatureCategory.COMPOSITE,
        value_type=FeatureValueType.FLOAT,
        default_timeframes=[],
        required_sources=["composite"],
        description="风险乘数",
    ),
]


# ========== 填充注册表 ==========
for features in [
    _raw_kline_features,
    _technical_features,
    _derivatives_features,
    _liquidation_features,
    _orderbook_features,
    _flow_features,
    _price_derived_features,
    _cross_market_features,
    _risk_features,
]:
    for feature in features:
        FEATURE_REGISTRY[feature.name] = feature


# ========== 公共 API ==========
def get_feature_def(name: str) -> Optional[FeatureDef]:
    """
    获取特征定义
    
    Args:
        name: 特征名称（会通过 aliases 归一化）
    
    Returns:
        FeatureDef 或 None
    """
    from .aliases import normalize_feature_name
    normalized_name = normalize_feature_name(name)
    return FEATURE_REGISTRY.get(normalized_name)


def is_feature_registered(name: str) -> bool:
    """
    检查特征是否已注册
    
    Args:
        name: 特征名称
    
    Returns:
        是否在注册表中
    """
    from .aliases import normalize_feature_name
    normalized_name = normalize_feature_name(name)
    return normalized_name in FEATURE_REGISTRY


def list_features_by_category(category: FeatureCategory) -> list[FeatureDef]:
    """
    按分类列出所有特征
    
    Args:
        category: 特征分类
    
    Returns:
        该分类的 FeatureDef 列表
    """
    return [
        feature for feature in FEATURE_REGISTRY.values()
        if feature.category == category
    ]


def list_all_feature_names() -> list[str]:
    """
    列出所有已注册的特征名称
    
    Returns:
        特征名称列表
    """
    return list(FEATURE_REGISTRY.keys())


# ========== 导入时校验（安全检查） ==========
_duplicate_names = set()
_seen_names = set()
for name in FEATURE_REGISTRY:
    if name in _seen_names:
        _duplicate_names.add(name)
    _seen_names.add(name)

if _duplicate_names:
    raise ValueError(f"FEATURE_REGISTRY 包含重复名称: {sorted(_duplicate_names)}")
