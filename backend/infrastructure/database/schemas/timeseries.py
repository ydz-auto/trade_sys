"""
TimeSeries Schemas (ClickHouse)
时序数据表结构 (ClickHouse)
"""

KLINE_SCHEMAS = {
    "klines": """
        CREATE TABLE IF NOT EXISTS klines (
            symbol String,
            timeframe String,
            open_time DateTime,
            close_time DateTime,
            open Decimal(20, 8),
            high Decimal(20, 8),
            low Decimal(20, 8),
            close Decimal(20, 8),
            volume Decimal(20, 8),
            quote_volume Decimal(20, 8),
            trades UInt32
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(open_time)
        ORDER BY (symbol, timeframe, open_time)
    """,
}

FEATURE_SCHEMAS = {
    "features": """
        CREATE TABLE IF NOT EXISTS features (
            id UInt64,
            symbol String,
            timeframe String,
            timestamp DateTime,
            returns_1m Float64,
            returns_5m Float64,
            returns_1h Float64,
            volatility Float64,
            atr Float64,
            momentum Float64,
            rsi Float64,
            macd Float64,
            ma_5 Float64,
            ma_20 Float64,
            ma_alignment Int8,
            trend_strength Float64
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (symbol, timeframe, timestamp)
    """,
}

FACTOR_SCHEMAS = {
    "factors": """
        CREATE TABLE IF NOT EXISTS factors (
            id UInt64,
            symbol String,
            timestamp DateTime,
            factor_trend Float64,
            factor_flow Float64,
            factor_sentiment Float64,
            factor_macro Float64,
            factor_behavioral Float64,
            factor_historical Float64,
            composite_score Float64,
            regime String,
            confidence Float64
        ) ENGINE = MergeTree()
        ORDER BY (symbol, timestamp)
    """,
}

SIGNAL_SCHEMAS = {
    "signals": """
        CREATE TABLE IF NOT EXISTS signals (
            id UInt64,
            symbol String,
            timestamp DateTime,
            signal_type String,
            action String,
            price Float64,
            confidence Float64,
            factors String,
            regime String
        ) ENGINE = MergeTree()
        ORDER BY (symbol, timestamp)
    """,
}

REGIME_SCHEMAS = {
    "regimes": """
        CREATE TABLE IF NOT EXISTS regimes (
            id UInt64,
            symbol String,
            timestamp DateTime,
            regime String,
            confidence Float64,
            risk_level UInt8,
            drivers String,
            duration UInt32
        ) ENGINE = MergeTree()
        ORDER BY (symbol, timestamp)
    """,
}