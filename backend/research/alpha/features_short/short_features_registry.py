"""
Short Features Registry - 做空 Alpha Feature 注册表

定义并管理所有做空 Alpha Features 的元信息。
"""

from typing import Dict, List
from dataclasses import dataclass


@dataclass
class ShortFeatureMeta:
    name: str
    family: str
    description: str
    data_source: str
    logic: str


SHORT_FEATURES_BY_FAMILY: Dict[str, List[ShortFeatureMeta]] = {
    "SHORT_OVEREXTENSION": [
        ShortFeatureMeta(
            name="distance_from_ma20",
            family="SHORT_OVEREXTENSION",
            description="价格偏离 MA20 百分比",
            data_source="kline",
            logic="问的是：涨得是不是偏离均线太远",
        ),
        ShortFeatureMeta(
            name="distance_from_ma60",
            family="SHORT_OVEREXTENSION",
            description="价格偏离 MA60 百分比",
            data_source="kline",
            logic="问的是：中长期超买信号",
        ),
        ShortFeatureMeta(
            name="distance_from_vwap",
            family="SHORT_OVEREXTENSION",
            description="价格偏离 VWAP 百分比",
            data_source="kline",
            logic="问的是：是否在日内均价之上太远",
        ),
        ShortFeatureMeta(
            name="zscore_price",
            family="SHORT_OVEREXTENSION",
            description="价格 Z-Score（相对100周期均值）",
            data_source="kline",
            logic="问的是：是否统计上偏离历史均值太多",
        ),
        ShortFeatureMeta(
            name="ma20_slope_zscore",
            family="SHORT_OVEREXTENSION",
            description="MA20 斜率 Z-Score",
            data_source="kline",
            logic="问的是：均线是否陡峭地上升",
        ),
        ShortFeatureMeta(
            name="price_deviation_band",
            family="SHORT_OVEREXTENSION",
            description="价格偏离布林带上轨程度",
            data_source="kline",
            logic="问的是：是否突破布林带上轨",
        ),
    ],
    "SHORT_PARABOLIC": [
        ShortFeatureMeta(
            name="ret_3_acceleration",
            family="SHORT_PARABOLIC",
            description="ret_3 加速指标",
            data_source="kline",
            logic="问的是：短期收益是否在加速",
        ),
        ShortFeatureMeta(
            name="ret_5_acceleration",
            family="SHORT_PARABOLIC",
            description="ret_5 加速指标",
            data_source="kline",
            logic="问的是：中期收益是否在加速",
        ),
        ShortFeatureMeta(
            name="ret_10_acceleration",
            family="SHORT_PARABOLIC",
            description="ret_10 加速指标",
            data_source="kline",
            logic="问的是：较长期收益是否在加速",
        ),
        ShortFeatureMeta(
            name="slope_acceleration",
            family="SHORT_PARABOLIC",
            description="斜率变化率（趋势加速）",
            data_source="kline",
            logic="问的是：趋势是否在加速",
        ),
        ShortFeatureMeta(
            name="curvature",
            family="SHORT_PARABOLIC",
            description="价格曲率（二阶导数）",
            data_source="kline",
            logic="问的是：是否进入抛物线阶段",
        ),
        ShortFeatureMeta(
            name="velocity_increase",
            family="SHORT_PARABOLIC",
            description="速度增量",
            data_source="kline",
            logic="问的是：当前速度是否高于近期均值",
        ),
        ShortFeatureMeta(
            name="momentum_divergence",
            family="SHORT_PARABOLIC",
            description="动量背离",
            data_source="kline",
            logic="问的是：价格创新高但RSI下降",
        ),
    ],
    "SHORT_EXHAUSTION": [
        ShortFeatureMeta(
            name="distance_from_high",
            family="SHORT_EXHAUSTION",
            description="距离高点的百分比",
            data_source="kline",
            logic="问的是：从高点下跌了多少（正值=下跌）",
        ),
        ShortFeatureMeta(
            name="parabolic_ret_10",
            family="SHORT_EXHAUSTION",
            description="10周期抛物线累计收益",
            data_source="kline",
            logic="问的是：是否已经连续暴涨",
        ),
        ShortFeatureMeta(
            name="parabolic_ret_zscore",
            family="SHORT_EXHAUSTION",
            description="抛物线收益 Z-Score",
            data_source="kline",
            logic="问的是：涨幅是否历史极端",
        ),
        ShortFeatureMeta(
            name="volatility_spike",
            family="SHORT_EXHAUSTION",
            description="波动率尖峰",
            data_source="kline",
            logic="问的是：波动率是否异常放大",
        ),
        ShortFeatureMeta(
            name="upper_shadow_ratio",
            family="SHORT_EXHAUSTION",
            description="上影线占比",
            data_source="kline",
            logic="问的是：是否冲高回落（上影线长）",
        ),
        ShortFeatureMeta(
            name="consecutive_green",
            family="SHORT_EXHAUSTION",
            description="连续阳线数量",
            data_source="kline",
            logic="问的是：是否连续上涨很久",
        ),
        ShortFeatureMeta(
            name="close_position_in_range",
            family="SHORT_EXHAUSTION",
            description="收盘价在 K 线范围内位置",
            data_source="kline",
            logic="问的是：收盘是否在低点（冲高回落）",
        ),
        ShortFeatureMeta(
            name="volume_climax",
            family="SHORT_EXHAUSTION",
            description="成交量高潮指标",
            data_source="kline",
            logic="问的是：是否放量且波幅大",
        ),
        ShortFeatureMeta(
            name="taker_buy_climax",
            family="SHORT_EXHAUSTION",
            description="Taker 买入高潮",
            data_source="trade",
            logic="问的是：是否主动买入衰竭",
        ),
        ShortFeatureMeta(
            name="new_high_60",
            family="SHORT_EXHAUSTION",
            description="60周期新高标记",
            data_source="kline",
            logic="问的是：是否创60周期新高",
        ),
        ShortFeatureMeta(
            name="high_volume_decline",
            family="SHORT_EXHAUSTION",
            description="放量下跌标记",
            data_source="kline",
            logic="问的是：是否放量下跌（多头平仓）",
        ),
        ShortFeatureMeta(
            name="funding_extreme_positive",
            family="SHORT_EXHAUSTION",
            description="资金费率极端正向标记",
            data_source="funding",
            logic="问的是：资金费率是否极端高",
        ),
        ShortFeatureMeta(
            name="ret_5_percentile",
            family="SHORT_EXHAUSTION",
            description="ret_5 的百分位排名",
            data_source="kline",
            logic="问的是：近期涨幅是否历史极端",
        ),
        ShortFeatureMeta(
            name="volume_spike_up",
            family="SHORT_EXHAUSTION",
            description="放量上涨标记",
            data_source="kline",
            logic="问的是：是否放量上涨",
        ),
        ShortFeatureMeta(
            name="momentum_overheat",
            family="SHORT_EXHAUSTION",
            description="动量过热（RSI>80）",
            data_source="kline",
            logic="问的是：RSI是否超买",
        ),
        ShortFeatureMeta(
            name="breakout_volume_decay",
            family="SHORT_EXHAUSTION",
            description="突破后量能衰减",
            data_source="kline",
            logic="问的是：突破后量能是否下降",
        ),
    ],
    "SHORT_BREAKFAIL": [
        ShortFeatureMeta(
            name="new_high_20",
            family="SHORT_BREAKFAIL",
            description="20周期新高标记",
            data_source="kline",
            logic="问的是：是否创短期新高",
        ),
        ShortFeatureMeta(
            name="new_high_60",
            family="SHORT_BREAKFAIL",
            description="60周期新高标记",
            data_source="kline",
            logic="问的是：是否创中期新高",
        ),
        ShortFeatureMeta(
            name="new_high_120",
            family="SHORT_BREAKFAIL",
            description="120周期新高标记",
            data_source="kline",
            logic="问的是：是否创长期新高",
        ),
        ShortFeatureMeta(
            name="breakout_strength",
            family="SHORT_BREAKFAIL",
            description="突破强度",
            data_source="kline",
            logic="问的是：突破幅度是否大",
        ),
        ShortFeatureMeta(
            name="breakout_failure",
            family="SHORT_BREAKFAIL",
            description="突破失败信号",
            data_source="kline",
            logic="问的是：创新高后是否回落",
        ),
        ShortFeatureMeta(
            name="breakout_retraction",
            family="SHORT_BREAKFAIL",
            description="突破回撤比率",
            data_source="kline",
            logic="问的是：回落幅度占突破幅度的比例",
        ),
        ShortFeatureMeta(
            name="double_top_probability",
            family="SHORT_BREAKFAIL",
            description="双顶形态概率",
            data_source="kline",
            logic="问的是：是否形成双顶",
        ),
        ShortFeatureMeta(
            name="failed_rebound_strength",
            family="SHORT_BREAKFAIL",
            description="反弹失败强度",
            data_source="kline",
            logic="问的是：反弹是否很快失败",
        ),
    ],
    "SHORT_CROWDED": [
        ShortFeatureMeta(
            name="funding_zscore_long",
            family="SHORT_CROWDED",
            description="资金费率 Z-Score",
            data_source="funding",
            logic="问的是：资金费率是否极端（多头付费率）",
        ),
        ShortFeatureMeta(
            name="oi_zscore_long",
            family="SHORT_CROWDED",
            description="持仓量 Z-Score",
            data_source="open_interest",
            logic="问的是：持仓量是否极端（多头拥挤）",
        ),
        ShortFeatureMeta(
            name="basis_zscore",
            family="SHORT_CROWDED",
            description="基差 Z-Score",
            data_source="cross_market",
            logic="问的是：基差是否极端",
        ),
        ShortFeatureMeta(
            name="long_short_ratio",
            family="SHORT_CROWDED",
            description="多空持仓比率",
            data_source="open_interest",
            logic="问的是：多头是否远超空头",
        ),
        ShortFeatureMeta(
            name="leverage_ratio_long",
            family="SHORT_CROWDED",
            description="多头杠杆率",
            data_source="open_interest",
            logic="问的是：多头杠杆是否过高",
        ),
        ShortFeatureMeta(
            name="funding_oi_combined",
            family="SHORT_CROWDED",
            description="Funding×OI 综合拥挤度",
            data_source="funding, open_interest",
            logic="问的是：双重极端（高费率+高OI）",
        ),
        ShortFeatureMeta(
            name="crowded_long_score",
            family="SHORT_CROWDED",
            description="多头拥挤综合评分",
            data_source="composite",
            logic="问的是：多维度综合拥挤程度",
        ),
        ShortFeatureMeta(
            name="liquidation_risk_long",
            family="SHORT_CROWDED",
            description="多头爆仓风险指标",
            data_source="liquidation",
            logic="问的是：多头爆仓风险是否高",
        ),
        ShortFeatureMeta(
            name="short_squeeze_prob",
            family="SHORT_CROWDED",
            description="逼空概率",
            data_source="open_interest, funding",
            logic="问的是：是否可能出现逼空",
        ),
        ShortFeatureMeta(
            name="margin_usage_long",
            family="SHORT_CROWDED",
            description="多头保证金使用率",
            data_source="open_interest",
            logic="问的是：多头保证金是否接近极限",
        ),
    ],
}


ALL_SHORT_FEATURES: List[str] = []
for family_features in SHORT_FEATURES_BY_FAMILY.values():
    for feature in family_features:
        ALL_SHORT_FEATURES.append(feature.name)


def get_short_features_by_family(family: str) -> List[str]:
    return [f.name for f in SHORT_FEATURES_BY_FAMILY.get(family, [])]


def print_short_feature_summary():
    print("\n" + "=" * 70)
    print("Short Alpha Feature Factory - Feature Summary")
    print("=" * 70)
    print(f"\nTotal Short Features: {len(ALL_SHORT_FEATURES)}")
    print()

    for family, features in SHORT_FEATURES_BY_FAMILY.items():
        print(f"\n{family} ({len(features)} features):")
        for f in features:
            print(f"  [{f.data_source:12}] {f.name:30} - {f.description}")

    print("\n" + "=" * 70)
    print("Alpha Logic Questions:")
    print("=" * 70)
    print("""
    OVEREXTENSION: 涨得是不是太离谱？
    PARABOLIC:     是不是进入抛物线阶段？
    EXHAUSTION:    买盘是否衰竭？
    BREAKFAIL:     创新高后是否失败？
    CROWDED:       多头是不是太拥挤？
    """)
