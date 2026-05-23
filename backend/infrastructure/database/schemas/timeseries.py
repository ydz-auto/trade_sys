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

CORRELATION_SCHEMAS = {
    "correlation_results": """
        CREATE TABLE IF NOT EXISTS correlation_results (
            symbol String,
            timeframe String,
            timestamp DateTime,
            positive_count UInt32,
            negative_count UInt32,
            neutral_count UInt32,
            total_signals UInt32,
            signal_assessments String,
            univariate_results String,
            multivariate_results String,
            llm_results String,
            analysis_duration_ms Float64
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (symbol, timeframe, timestamp)
    """,
}

EVENT_JOURNAL_SCHEMA = {
    "event_journal": """
        CREATE TABLE IF NOT EXISTS event_journal (
            event_id String,
            trace_id String,
            parent_event_id Nullable(String),
            schema_version String,
            event_type String,
            category String,
            source String,
            symbol Nullable(String),
            event_time_ms Int64,
            ingest_time_ms Int64,
            process_time_ms Int64,
            clock_mode String,
            metadata String,
            payload String,
            created_at Int64
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(fromUnixTimestamp64Milli(event_time_ms))
        ORDER BY (event_type, symbol, event_time_ms, event_id)
    """,
}