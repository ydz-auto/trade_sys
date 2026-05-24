"""
Topic System - 分层 Topic 体系

架构设计：
原始层 (raw.*)        → data_service 产生
    ↓
聚合层 (kline.*)     → aggregation_service 产生
    ↓
事件层 (events.*)    → event_service 产生
    ↓
信号层 (signals.*)  → fusion_service 产生
    ↓
因子层 (factors.*)   → factor_service 产生
    ↓
订单层 (orders.*)    → strategy_service 产生

Topic 命名规范：
{namespace}.{layer}.{source}.{type}.{symbol}.{timeframe}

示例：
- raw.kline.binance.1m.BTC
- raw.trade.binance.BTC
- raw.news.odaily
- raw.twitter.crypto
- kline.binance.5m.BTC
- kline.binance.1h.BTC
- events.market.BTC
- events.etf.BTC
- events.macro.BTC
- signals.market.BTC
- factors.sentiment.BTC
- orders.limit.BTC
"""

from typing import Final


class Topics:
    """Topic 命名空间"""

    NAMESPACE: Final[str] = "tradeagent"

    RAW_DATA: Final[str] = f"{NAMESPACE}.raw_data"
    FEATURES: Final[str] = f"{NAMESPACE}.features"
    FACTORS: Final[str] = f"{NAMESPACE}.factors"
    REGIMES: Final[str] = f"{NAMESPACE}.regimes"
    RISK_ALERTS: Final[str] = f"{NAMESPACE}.risk_alerts"
    TRADING_SIGNALS: Final[str] = f"{NAMESPACE}.trading_signals"
    ORDER_EVENTS: Final[str] = f"{NAMESPACE}.order_events"
    EXECUTION_RESULTS: Final[str] = f"{NAMESPACE}.execution_results"
    FEEDBACK_DATA: Final[str] = f"{NAMESPACE}.feedback_data"
    SIGNALS: Final[str] = f"{NAMESPACE}.signals"
    DECISIONS: Final[str] = f"{NAMESPACE}.decisions.all"
    ORDERS: Final[str] = f"{NAMESPACE}.orders"
    EVENTS: Final[str] = f"{NAMESPACE}.events"
    ALERTS: Final[str] = f"{NAMESPACE}.alerts"
    LOGS: Final[str] = f"{NAMESPACE}.logs"
    CORRELATION_RESULTS: Final[str] = f"{NAMESPACE}.correlation_results"

    @classmethod
    def _layer(cls, layer: str, source: str = "", type: str = "", symbol: str = "", timeframe: str = "") -> str:
        """生成分层 Topic"""
        parts = [cls.NAMESPACE, layer]
        if source:
            parts.append(source)
        if type:
            parts.append(type)
        if symbol:
            parts.append(symbol)
        if timeframe:
            parts.append(timeframe)
        return ".".join(parts)

    @classmethod
    def raw_kline(cls, exchange: str, symbol: str, timeframe: str) -> str:
        """原始 K线数据"""
        return cls._layer("raw", "kline", exchange, symbol, timeframe)

    @classmethod
    def raw_trade(cls, exchange: str, symbol: str) -> str:
        """原始成交数据"""
        return cls._layer("raw", "trade", exchange, symbol)

    @classmethod
    def raw_orderbook(cls, exchange: str, symbol: str) -> str:
        """原始订单簿数据"""
        return cls._layer("raw", "orderbook", exchange, symbol)

    @classmethod
    def raw_news(cls, source: str = "") -> str:
        """原始新闻数据"""
        return cls._layer("raw", "news", source)

    @classmethod
    def raw_twitter(cls, platform: str = "") -> str:
        """原始 Twitter 数据"""
        return cls._layer("raw", "twitter", platform)

    @classmethod
    def raw_telegram(cls, channel: str = "") -> str:
        """原始 Telegram 数据"""
        return cls._layer("raw", "telegram", channel)

    @classmethod
    def raw_macro(cls, source: str = "") -> str:
        """原始宏观数据"""
        return cls._layer("raw", "macro", source)

    @classmethod
    def raw_etf(cls, symbol: str = "") -> str:
        """原始 ETF 数据"""
        return cls._layer("raw", "etf", symbol)

    @classmethod
    def raw_onchain(cls, source: str = "") -> str:
        """原始链上数据"""
        return cls._layer("raw", "onchain", source)

    @classmethod
    def raw_odaily(cls) -> str:
        """原始 Odaily 数据"""
        return cls._layer("raw", "news", "odaily")

    @classmethod
    def kline(cls, exchange: str, timeframe: str, symbol: str) -> str:
        """聚合 K线数据"""
        return cls._layer("kline", exchange, timeframe, symbol)

    @classmethod
    def kline_1s(cls, exchange: str, symbol: str) -> str:
        """1秒K线（聚合服务生成）"""
        return cls._layer("kline", exchange, "1s", symbol)

    @classmethod
    def kline_1m(cls, exchange: str, symbol: str) -> str:
        """1分钟K线"""
        return cls._layer("kline", exchange, "1m", symbol)

    @classmethod
    def kline_5m(cls, exchange: str, symbol: str) -> str:
        """5分钟K线"""
        return cls._layer("kline", exchange, "5m", symbol)

    @classmethod
    def kline_15m(cls, exchange: str, symbol: str) -> str:
        """15分钟K线"""
        return cls._layer("kline", exchange, "15m", symbol)

    @classmethod
    def kline_1h(cls, exchange: str, symbol: str) -> str:
        """1小时K线"""
        return cls._layer("kline", exchange, "1h", symbol)

    @classmethod
    def kline_4h(cls, exchange: str, symbol: str) -> str:
        """4小时K线"""
        return cls._layer("kline", exchange, "4h", symbol)

    @classmethod
    def kline_1d(cls, exchange: str, symbol: str) -> str:
        """日K线"""
        return cls._layer("kline", exchange, "1d", symbol)

    @classmethod
    def orderbook_feature(cls, exchange: str, symbol: str) -> str:
        """订单簿特征（聚合服务生成）"""
        return cls._layer("orderbook", "feature", exchange, symbol)

    @classmethod
    def events_market(cls, symbol: str = "") -> str:
        """市场事件"""
        return cls._layer("events", "market", symbol=symbol)

    @classmethod
    def events_etf(cls, symbol: str = "") -> str:
        """ETF 事件"""
        return cls._layer("events", "etf", symbol=symbol)

    @classmethod
    def events_macro(cls, symbol: str = "") -> str:
        """宏观事件"""
        return cls._layer("events", "macro", symbol=symbol)

    @classmethod
    def events_social(cls, symbol: str = "") -> str:
        """社交事件"""
        return cls._layer("events", "social", symbol=symbol)

    @classmethod
    def events_onchain(cls, symbol: str = "") -> str:
        """链上事件"""
        return cls._layer("events", "onchain", symbol=symbol)

    @classmethod
    def signals_market(cls, symbol: str = "") -> str:
        """市场信号"""
        return cls._layer("signals", "market", symbol=symbol)

    @classmethod
    def signals_sentiment(cls, symbol: str = "") -> str:
        """情绪信号"""
        return cls._layer("signals", "sentiment", symbol=symbol)

    @classmethod
    def factors_trend(cls, symbol: str = "") -> str:
        """趋势因子"""
        return cls._layer("factors", "trend", symbol=symbol)

    @classmethod
    def factors_sentiment(cls, symbol: str = "") -> str:
        """情绪因子"""
        return cls._layer("factors", "sentiment", symbol=symbol)

    @classmethod
    def orders_limit(cls, symbol: str = "") -> str:
        """限价订单"""
        return cls._layer("orders", "limit", symbol=symbol)

    @classmethod
    def orders_market(cls, symbol: str = "") -> str:
        """市价订单"""
        return cls._layer("orders", "market", symbol=symbol)

    @classmethod
    def alerts(cls, level: str = "") -> str:
        """告警"""
        return cls._layer("alerts", level)
    
    # 新增：决策和执行层 Topic
    @classmethod
    def decisions(cls) -> str:
        """策略决策"""
        return cls._layer("decisions", "all")
    
    @classmethod
    def decisions_risk_checked(cls) -> str:
        """风控检查后的决策"""
        return cls._layer("decisions", "risk_checked")
    
    @classmethod
    def decisions_approved(cls) -> str:
        """已批准的决策"""
        return cls._layer("decisions", "approved")


class TopicGroups:
    """Topic 分组"""

    DATA_INPUT = "data_input"
    AGGREGATION = "aggregation"
    UNDERSTANDING = "understanding"
    SIGNAL = "signal"
    FACTOR = "factor"
    EXECUTION = "execution"
    OUTPUT = "output"

    @classmethod
    def get_topics(cls, group: str) -> list:
        """获取分组内的 Topic"""
        groups = {
            cls.DATA_INPUT: [
                Topics.raw_kline("+", "+", "+"),
                Topics.raw_trade("+", "+"),
                Topics.raw_news(),
                Topics.raw_twitter(),
                Topics.raw_telegram(),
                Topics.raw_macro(),
                Topics.raw_etf(),
                Topics.raw_onchain(),
            ],
            cls.AGGREGATION: [
                Topics.kline_1s("+", "+"),
                Topics.kline_1m("+", "+"),
                Topics.kline_5m("+", "+"),
                Topics.kline_15m("+", "+"),
                Topics.kline_1h("+", "+"),
                Topics.kline_4h("+", "+"),
                Topics.kline_1d("+", "+"),
                Topics.orderbook_feature("+", "+"),
            ],
            cls.UNDERSTANDING: [
                Topics.events_market(),
                Topics.events_etf(),
                Topics.events_macro(),
                Topics.events_social(),
                Topics.events_onchain(),
            ],
            cls.SIGNAL: [
                Topics.signals_market(),
                Topics.signals_sentiment(),
            ],
            cls.EXECUTION: [
                Topics.orders_limit(),
                Topics.orders_market(),
            ],
            cls.OUTPUT: [
                Topics.alerts(),
            ],
        }
        return groups.get(group, [])


class DataSource(str):
    """数据源标识"""
    BINANCE = "binance"
    OKX = "okx"
    COINBASE = "coinbase"

    ODAILY = "odaily"
    JINSE = "jinse"
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"

    TWITTER = "twitter"
    TELEGRAM = "telegram"
    REDDIT = "reddit"

    CLAWHUB = "clawhub"
    POLYMARKET = "polymarket"

    GLASSNODE = "glassnode"
    COINGECKO = "coingecko"


class DataLayer(str):
    """数据层级"""
    RAW = "raw"
    AGGREGATED = "aggregated"
    EVENT = "event"
    SIGNAL = "signal"
    FACTOR = "factor"


class TimeframeTopic:
    """时间周期 Topic"""

    MAPPING = {
        "1s": "1s",
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }

    @classmethod
    def all(cls) -> list:
        return list(cls.MAPPING.values())
