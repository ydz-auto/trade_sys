CLICKHOUSE_SCHEMAS: dict = {
    "klines": """
        CREATE TABLE IF NOT EXISTS klines (
            symbol String,
            timeframe String,
            open_time Int64,
            close_time Int64,
            open Float64,
            high Float64,
            low Float64,
            close Float64,
            volume Float64,
            quote_volume Float64,
            trades Int32,
            date Date DEFAULT toDate(open_time / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, timeframe, open_time)
    """,
    "features": """
        CREATE TABLE IF NOT EXISTS features (
            symbol String,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, timestamp)
    """,
    "factors": """
        CREATE TABLE IF NOT EXISTS factors (
            symbol String,
            timestamp Int64,
            regime String,
            confidence Float64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, timestamp)
    """,
    "trades": """
        CREATE TABLE IF NOT EXISTS trades (
            symbol String,
            timestamp Int64,
            side String,
            price Float64,
            quantity Float64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, timestamp)
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            order_id String,
            symbol String,
            side String,
            order_type String,
            quantity Float64,
            price Nullable(Float64),
            status String,
            exchange String,
            created_at Int64,
            updated_at Int64,
            date Date DEFAULT toDate(created_at / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (order_id, created_at)
    """,
    "signals": """
        CREATE TABLE IF NOT EXISTS signals (
            signal_id String,
            symbol String,
            direction String,
            confidence Float64,
            source String,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (signal_id, timestamp)
    """,
    "events": """
        CREATE TABLE IF NOT EXISTS events (
            event_id String,
            event_type String,
            source String,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (event_id, timestamp)
    """,
    "positions": """
        CREATE TABLE IF NOT EXISTS positions (
            symbol String,
            exchange String,
            side String,
            quantity Float64,
            entry_price Float64,
            unrealized_pnl Float64,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (symbol, exchange, timestamp)
    """,
    "audit_logs": """
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id String,
            action String,
            user_id String,
            timestamp Int64,
            details String,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (log_id, timestamp)
    """,
    "execution_records": """
        CREATE TABLE IF NOT EXISTS execution_records (
            record_id String,
            order_id String,
            symbol String,
            side String,
            quantity Float64,
            price Float64,
            status String,
            exchange String,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (record_id, timestamp)
    """,
    "idempotency_records": """
        CREATE TABLE IF NOT EXISTS idempotency_records (
            key String,
            status String,
            created_at Int64,
            updated_at Int64
        ) ENGINE = MergeTree()
        ORDER BY (key, created_at)
    """,
    "correlation_results": """
        CREATE TABLE IF NOT EXISTS correlation_results (
            result_id String,
            symbol String,
            factor String,
            correlation Float64,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (result_id, timestamp)
    """,
    "data_lineage": """
        CREATE TABLE IF NOT EXISTS data_lineage (
            lineage_id String,
            source String,
            target String,
            transform String,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (lineage_id, timestamp)
    """,
    "event_journal": """
        CREATE TABLE IF NOT EXISTS event_journal (
            event_id String,
            aggregate_id String,
            event_type String,
            payload String,
            version Int64,
            timestamp Int64,
            date Date DEFAULT toDate(timestamp / 1000)
        ) ENGINE = MergeTree()
        PARTITION BY toYYYYMM(date)
        ORDER BY (aggregate_id, version)
    """,
}
