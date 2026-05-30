"""
Data Collection Schemas (ClickHouse)
数据采集相关表结构
"""

PRICE_SCHEMAS = {
    "prices": """
        CREATE TABLE IF NOT EXISTS prices (
            id UInt64,
            symbol String,
            exchange String,
            price Decimal(20, 8),
            bid Decimal(20, 8),
            ask Decimal(20, 8),
            spread Decimal(20, 8),
            volume_24h Decimal(20, 2),
            high_24h Decimal(20, 8),
            low_24h Decimal(20, 8),
            change_24h Decimal(20, 8),
            timestamp DateTime
        ) ENGINE = MergeTree()
        ORDER BY (symbol, exchange, timestamp)
        TTL timestamp + INTERVAL 30 DAY
    """,

    "prices_aggregated": """
        CREATE TABLE IF NOT EXISTS prices_aggregated (
            symbol String,
            exchange String,
            timeframe String,
            open Decimal(20, 8),
            high Decimal(20, 8),
            low Decimal(20, 8),
            close Decimal(20, 8),
            volume Decimal(20, 2),
            timestamp DateTime
        ) ENGINE = SummingMergeTree()
        ORDER BY (symbol, exchange, timeframe, timestamp)
        TTL timestamp + INTERVAL 90 DAY
    """
}

NEWS_SCHEMAS = {
    "news": """
        CREATE TABLE IF NOT EXISTS news (
            id String,
            title String,
            content String,
            url String,
            source String,
            published DateTime,
            sentiment String,
            sentiment_score Float64,
            sentiment_confidence Float64,
            event_type String,
            black_swan_score Float64,
            urgency String,
            affected_symbols Array(String),
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (source, published)
        TTL published + INTERVAL 7 DAY
    """,

    "news_black_swan": """
        CREATE TABLE IF NOT EXISTS news_black_swan (
            id String,
            title String,
            content String,
            url String,
            source String,
            published DateTime,
            sentiment String,
            black_swan_score Float64,
            urgency String,
            affected_symbols Array(String),
            acknowledged Bool DEFAULT false,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (published, black_swan_score DESC)
        TTL published + INTERVAL 30 DAY
    """
}

ETF_SCHEMAS = {
    "etf_flows": """
        CREATE TABLE IF NOT EXISTS etf_flows (
            id UInt64,
            symbol String,
            net_flow Decimal(20, 2),
            inflow Decimal(20, 2),
            outflow Decimal(20, 2),
            aum Decimal(20, 2),
            source String,
            confidence Float64,
            timestamp DateTime
        ) ENGINE = MergeTree()
        ORDER BY (symbol, timestamp)
        TTL timestamp + INTERVAL 90 DAY
    """,

    "etf_flows_detail": """
        CREATE TABLE IF NOT EXISTS etf_flows_detail (
            symbol String,
            source String,
            net_flow Decimal(20, 2),
            inflow Decimal(20, 2),
            outflow Decimal(20, 2),
            aum Decimal(20, 2),
            confidence Float64,
            timestamp DateTime
        ) ENGINE = SummingMergeTree()
        ORDER BY (symbol, source, timestamp)
    """
}

MACRO_SCHEMAS = {
    "macro_data": """
        CREATE TABLE IF NOT EXISTS macro_data (
            id UInt64,
            asset String,
            price Decimal(20, 8),
            change_1d Float64,
            change_7d Float64,
            volume Decimal(20, 2),
            source String,
            timestamp DateTime
        ) ENGINE = MergeTree()
        ORDER BY (asset, timestamp)
        TTL timestamp + INTERVAL 30 DAY
    """
}

SOCIAL_SCHEMAS = {
    "social_posts": """
        CREATE TABLE IF NOT EXISTS social_posts (
            id String,
            platform String,
            author String,
            author_handle String,
            content String,
            url String,
            published DateTime,
            likes UInt32,
            retweets UInt32,
            replies UInt32,
            sentiment String,
            sentiment_score Float64,
            mentioned_symbols Array(String),
            is_important Bool DEFAULT false,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (platform, published)
        TTL published + INTERVAL 7 DAY
    """
}

TRADER_SCHEMAS = {
    "trader_opinions": """
        CREATE TABLE IF NOT EXISTS trader_opinions (
            id UInt64,
            trader_id String,
            trader_name String,
            platform String,
            content String,
            url String,
            published DateTime,
            sentiment String,
            sentiment_score Float64,
            mentioned_assets Array(String),
            time_horizon String,
            arguments Array(String),
            influence_score Float64,
            credibility Float64,
            created_at DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        ORDER BY (trader_id, published)
        TTL published + INTERVAL 30 DAY
    """,

    "trader_sentiment_agg": """
        CREATE TABLE IF NOT EXISTS trader_sentiment_agg (
            symbol String,
            sentiment String,
            count UInt32,
            avg_score Float64,
            timestamp DateTime
        ) ENGINE = SummingMergeTree()
        ORDER BY (symbol, sentiment, timestamp)
    """
}

CRYPTO_STOCK_SCHEMAS = {
    "crypto_stocks": """
        CREATE TABLE IF NOT EXISTS crypto_stocks (
            id UInt64,
            symbol String,
            name String,
            price Decimal(20, 8),
            change_1d Float64,
            change_7d Float64,
            volume Decimal(20, 2),
            market_cap Decimal(20, 2),
            source String,
            timestamp DateTime
        ) ENGINE = MergeTree()
        ORDER BY (symbol, timestamp)
        TTL timestamp + INTERVAL 30 DAY
    """
}

ALL_SCHEMAS = {
    **PRICE_SCHEMAS,
    **NEWS_SCHEMAS,
    **ETF_SCHEMAS,
    **MACRO_SCHEMAS,
    **SOCIAL_SCHEMAS,
    **TRADER_SCHEMAS,
    **CRYPTO_STOCK_SCHEMAS,
}
