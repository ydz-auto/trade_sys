"""
Data Lake Schemas (ClickHouse)
数据湖分层存储表结构

所有 TTL 值从 layer.LAYER_CONFIGS 动态读取，本文件不硬编码任何 TTL。
修改 TTL 请编辑 layer.py 中的 LAYER_CONFIGS。
"""

from infrastructure.data_lake.layer import DataLayer, get_layer_config


def _ttl(layer: DataLayer) -> str:
    return f"INTERVAL {get_layer_config(layer).ttl_days} DAY"


DATA_LAKE_TABLE_SCHEMAS = {
    "lake_raw_trades": f"""
        CREATE TABLE IF NOT EXISTS lake_raw_trades (
            timestamp DateTime,
            exchange String,
            symbol String,
            trade_id String,
            price Decimal(20, 8),
            quantity Decimal(20, 8),
            quote_quantity Decimal(20, 8),
            side String,
            is_buyer_maker UInt8,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(ingest_time)
        PARTITION BY toYYYYMMDD(timestamp)
        ORDER BY (exchange, symbol, timestamp, trade_id)
        TTL timestamp + {_ttl(DataLayer.RAW)}
    """,

    "lake_raw_klines": f"""
        CREATE TABLE IF NOT EXISTS lake_raw_klines (
            open_time DateTime,
            close_time DateTime,
            exchange String,
            symbol String,
            timeframe String,
            open Decimal(20, 8),
            high Decimal(20, 8),
            low Decimal(20, 8),
            close Decimal(20, 8),
            volume Decimal(20, 8),
            quote_volume Decimal(20, 8),
            trades UInt32,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(open_time)
        ORDER BY (exchange, symbol, timeframe, open_time)
        TTL open_time + {_ttl(DataLayer.RAW)}
    """,

    "lake_raw_news": f"""
        CREATE TABLE IF NOT EXISTS lake_raw_news (
            timestamp DateTime,
            source String,
            title String,
            content String,
            url String,
            sentiment_score Float64 DEFAULT 0,
            entities String DEFAULT '',
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (source, timestamp)
        TTL timestamp + {_ttl(DataLayer.RAW)}
    """,

    "lake_raw_orderbook": f"""
        CREATE TABLE IF NOT EXISTS lake_raw_orderbook (
            timestamp DateTime,
            exchange String,
            symbol String,
            bids String,
            asks String,
            spread Decimal(20, 8) DEFAULT 0,
            mid_price Decimal(20, 8) DEFAULT 0,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(ingest_time)
        PARTITION BY toYYYYMMDD(timestamp)
        ORDER BY (exchange, symbol, timestamp)
        TTL timestamp + {_ttl(DataLayer.RAW)}
    """,

    "lake_normalized_trades": f"""
        CREATE TABLE IF NOT EXISTS lake_normalized_trades (
            timestamp DateTime,
            exchange String,
            symbol String,
            trade_id String,
            price Float64,
            quantity Float64,
            quote_quantity Float64,
            side String,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(ingest_time)
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (exchange, symbol, timestamp, trade_id)
        TTL timestamp + {_ttl(DataLayer.NORMALIZED)}
    """,

    "lake_normalized_klines": f"""
        CREATE TABLE IF NOT EXISTS lake_normalized_klines (
            open_time DateTime,
            close_time DateTime,
            exchange String,
            symbol String,
            timeframe String,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume Float64,
            quote_volume Float64,
            trades UInt32,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(ingest_time)
        PARTITION BY toYYYYMM(open_time)
        ORDER BY (exchange, symbol, timeframe, open_time)
        TTL open_time + {_ttl(DataLayer.NORMALIZED)}
    """,

    "lake_aggregated_klines": f"""
        CREATE TABLE IF NOT EXISTS lake_aggregated_klines (
            open_time DateTime,
            close_time DateTime,
            exchange String,
            symbol String,
            timeframe String,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume Float64,
            quote_volume Float64,
            trades UInt32,
            vwap Float64 DEFAULT 0,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = ReplacingMergeTree(ingest_time)
        PARTITION BY toYYYYMM(open_time)
        ORDER BY (exchange, symbol, timeframe, open_time)
        TTL open_time + {_ttl(DataLayer.AGGREGATED)}
    """,

    "lake_aggregated_vwap": f"""
        CREATE TABLE IF NOT EXISTS lake_aggregated_vwap (
            timestamp DateTime,
            exchange String,
            symbol String,
            timeframe String,
            vwap Float64,
            volume Float64,
            quote_volume Float64,
            trades UInt32,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (exchange, symbol, timeframe, timestamp)
        TTL timestamp + {_ttl(DataLayer.AGGREGATED)}
    """,

    "lake_aggregated_footprint": f"""
        CREATE TABLE IF NOT EXISTS lake_aggregated_footprint (
            timestamp DateTime,
            exchange String,
            symbol String,
            timeframe String,
            price_level Float64,
            bid_volume Float64 DEFAULT 0,
            ask_volume Float64 DEFAULT 0,
            total_volume Float64 DEFAULT 0,
            delta Float64 DEFAULT 0,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (exchange, symbol, timeframe, timestamp, price_level)
        TTL timestamp + {_ttl(DataLayer.AGGREGATED)}
    """,

    "lake_feature_technical": f"""
        CREATE TABLE IF NOT EXISTS lake_feature_technical (
            timestamp DateTime,
            exchange String,
            symbol String,
            timeframe String,
            returns_1m Float64 DEFAULT 0,
            returns_5m Float64 DEFAULT 0,
            returns_1h Float64 DEFAULT 0,
            volatility Float64 DEFAULT 0,
            atr Float64 DEFAULT 0,
            momentum Float64 DEFAULT 0,
            rsi Float64 DEFAULT 0,
            macd Float64 DEFAULT 0,
            macd_signal Float64 DEFAULT 0,
            macd_hist Float64 DEFAULT 0,
            ma_5 Float64 DEFAULT 0,
            ma_20 Float64 DEFAULT 0,
            ma_50 Float64 DEFAULT 0,
            ma_200 Float64 DEFAULT 0,
            ma_alignment Int8 DEFAULT 0,
            trend_strength Float64 DEFAULT 0,
            bb_upper Float64 DEFAULT 0,
            bb_lower Float64 DEFAULT 0,
            bb_width Float64 DEFAULT 0,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (exchange, symbol, timeframe, timestamp)
        TTL timestamp + {_ttl(DataLayer.FEATURE)}
    """,

    "lake_feature_factor": f"""
        CREATE TABLE IF NOT EXISTS lake_feature_factor (
            timestamp DateTime,
            exchange String,
            symbol String,
            factor_trend Float64 DEFAULT 0,
            factor_flow Float64 DEFAULT 0,
            factor_sentiment Float64 DEFAULT 0,
            factor_macro Float64 DEFAULT 0,
            factor_behavioral Float64 DEFAULT 0,
            factor_historical Float64 DEFAULT 0,
            composite_score Float64 DEFAULT 0,
            regime String DEFAULT '',
            confidence Float64 DEFAULT 0,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (exchange, symbol, timestamp)
        TTL timestamp + {_ttl(DataLayer.FEATURE)}
    """,

    "lake_signal_trading": f"""
        CREATE TABLE IF NOT EXISTS lake_signal_trading (
            timestamp DateTime,
            exchange String,
            symbol String,
            signal_type String,
            action String,
            price Float64 DEFAULT 0,
            confidence Float64 DEFAULT 0,
            factors String DEFAULT '',
            regime String DEFAULT '',
            strategy_id String DEFAULT '',
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (exchange, symbol, timestamp)
        TTL timestamp + {_ttl(DataLayer.SIGNAL)}
    """,

    "lake_signal_fusion": f"""
        CREATE TABLE IF NOT EXISTS lake_signal_fusion (
            timestamp DateTime,
            exchange String,
            symbol String,
            fusion_score Float64 DEFAULT 0,
            signal_count UInt32 DEFAULT 0,
            consensus_action String DEFAULT '',
            confidence Float64 DEFAULT 0,
            contributing_signals String DEFAULT '',
            regime String DEFAULT '',
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (exchange, symbol, timestamp)
        TTL timestamp + {_ttl(DataLayer.SIGNAL)}
    """,

    "lake_replay_events": f"""
        CREATE TABLE IF NOT EXISTS lake_replay_events (
            timestamp DateTime,
            event_type String,
            source String,
            symbol String DEFAULT '',
            event_id String,
            payload String DEFAULT '',
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (event_type, source, timestamp)
        TTL timestamp + {_ttl(DataLayer.REPLAY)}
    """,

    "lake_replay_snapshots": f"""
        CREATE TABLE IF NOT EXISTS lake_replay_snapshots (
            timestamp DateTime,
            snapshot_type String,
            symbol String DEFAULT '',
            state String DEFAULT '',
            version UInt32 DEFAULT 0,
            ingest_time DateTime DEFAULT now()
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(timestamp)
        ORDER BY (snapshot_type, symbol, timestamp)
        TTL timestamp + {_ttl(DataLayer.REPLAY)}
    """,
}

DATA_LAKE_MATERIALIZED_VIEWS = {
    "mv_raw_to_normalized_trades": """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_raw_to_normalized_trades
        TO lake_normalized_trades
        AS SELECT
            timestamp,
            exchange,
            symbol,
            trade_id,
            toFloat64(price) AS price,
            toFloat64(quantity) AS quantity,
            toFloat64(quote_quantity) AS quote_quantity,
            side,
            ingest_time
        FROM lake_raw_trades
    """,

    "mv_raw_to_normalized_klines": """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_raw_to_normalized_klines
        TO lake_normalized_klines
        AS SELECT
            open_time,
            close_time,
            exchange,
            symbol,
            timeframe,
            toFloat64(open) AS open,
            toFloat64(high) AS high,
            toFloat64(low) AS low,
            toFloat64(close) AS close,
            toFloat64(volume) AS volume,
            toFloat64(quote_volume) AS quote_volume,
            trades,
            ingest_time
        FROM lake_raw_klines
    """,

    "mv_normalized_to_aggregated": """
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_normalized_to_aggregated
        TO lake_aggregated_klines
        AS SELECT
            open_time,
            close_time,
            exchange,
            symbol,
            timeframe,
            open,
            high,
            low,
            close,
            volume,
            quote_volume,
            trades,
            toFloat64(0) AS vwap,
            ingest_time
        FROM lake_normalized_klines
    """,
}

DATA_LAKE_SCHEMAS = {
    **DATA_LAKE_TABLE_SCHEMAS,
    **DATA_LAKE_MATERIALIZED_VIEWS,
}
