"""
Data Lake Schemas - 数据湖表结构

包含：
1. 分层表结构 (raw, normalized, aggregated, feature, signal, replay)
2. TTL 策略
3. 物化视图
4. 分区策略
"""

from .layer import DataLayer, DataCategory, get_layer_config


def generate_raw_schemas() -> dict:
    """生成原始层表结构"""
    return {
        "raw_market_data": """
            CREATE TABLE IF NOT EXISTS raw_market_data (
                event_id String,
                source String,
                exchange String,
                symbol String,
                data_type String,
                timestamp DateTime64(3),
                
                raw_data String,
                
                received_at DateTime64(3) DEFAULT now64(3),
                processed_at Nullable(DateTime64(3)),
                
                metadata Map(String, String)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (source, exchange, symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 30 DAY
        """,
        
        "raw_news_data": """
            CREATE TABLE IF NOT EXISTS raw_news_data (
                event_id String,
                source String,
                timestamp DateTime64(3),
                
                title String,
                content String,
                url String,
                
                symbols Array(String),
                categories Array(String),
                
                raw_json String,
                
                received_at DateTime64(3) DEFAULT now64(3),
                
                metadata Map(String, String)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (source, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 30 DAY
        """,
        
        "raw_social_data": """
            CREATE TABLE IF NOT EXISTS raw_social_data (
                event_id String,
                source String,
                platform String,
                author String,
                timestamp DateTime64(3),
                
                content String,
                sentiment_score Nullable(Float32),
                
                symbols Array(String),
                
                raw_json String,
                
                received_at DateTime64(3) DEFAULT now64(3),
                
                metadata Map(String, String)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (source, platform, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 14 DAY
        """,
        
        "raw_onchain_data": """
            CREATE TABLE IF NOT EXISTS raw_onchain_data (
                event_id String,
                source String,
                chain String,
                event_type String,
                timestamp DateTime64(3),
                
                address String,
                amount Nullable(Float64),
                
                raw_json String,
                
                received_at DateTime64(3) DEFAULT now64(3),
                
                metadata Map(String, String)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (source, chain, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 60 DAY
        """,
    }


def generate_normalized_schemas() -> dict:
    """生成标准化层表结构"""
    return {
        "normalized_market": """
            CREATE TABLE IF NOT EXISTS normalized_market (
                event_id String,
                source_layer String,
                raw_event_id String,
                
                exchange String,
                symbol String,
                market_type String,
                timestamp DateTime64(3),
                
                price Float64,
                quantity Float64,
                side String,
                
                normalized_at DateTime64(3) DEFAULT now64(3),
                
                metadata Map(String, String)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (exchange, symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 60 DAY
        """,
        
        "normalized_events": """
            CREATE TABLE IF NOT EXISTS normalized_events (
                event_id String,
                source_layer String,
                raw_event_id String,
                
                category String,
                event_type String,
                
                symbol String,
                direction String,
                strength Float32,
                confidence Float32,
                
                timestamp DateTime64(3),
                normalized_at DateTime64(3) DEFAULT now64(3),
                
                affected_symbols Array(String),
                
                metadata Map(String, String)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (category, symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 60 DAY
        """,
    }


def generate_aggregated_schemas() -> dict:
    """生成聚合层表结构"""
    return {
        "aggregated_klines": """
            CREATE TABLE IF NOT EXISTS aggregated_klines (
                exchange String,
                symbol String,
                timeframe String,
                open_time DateTime64(3),
                close_time DateTime64(3),
                
                open Float64,
                high Float64,
                low Float64,
                close Float64,
                volume Float64,
                quote_volume Float64,
                trades UInt32,
                
                vwap Float64,
                twap Float64,
                
                is_closed UInt8 DEFAULT 0,
                
                aggregated_at DateTime64(3) DEFAULT now64(3),
                
                source_count UInt32 DEFAULT 1
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(open_time)
            ORDER BY (exchange, symbol, timeframe, open_time)
            TTL toDateTime(open_time) + INTERVAL 180 DAY
        """,
        
        "aggregated_trades": """
            CREATE TABLE IF NOT EXISTS aggregated_trades (
                exchange String,
                symbol String,
                trade_id String,
                
                price Float64,
                quantity Float64,
                quote_quantity Float64,
                side String,
                
                timestamp DateTime64(3),
                
                aggregated_at DateTime64(3) DEFAULT now64(3)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (exchange, symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 90 DAY
        """,
        
        "aggregated_orderbook": """
            CREATE TABLE IF NOT EXISTS aggregated_orderbook (
                exchange String,
                symbol String,
                timestamp DateTime64(3),
                
                bid_prices Array(Float64),
                bid_quantities Array(Float64),
                ask_prices Array(Float64),
                ask_quantities Array(Float64),
                
                spread Float64,
                mid_price Float64,
                
                imbalance Float64,
                
                aggregated_at DateTime64(3) DEFAULT now64(3)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (exchange, symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 30 DAY
        """,
    }


def generate_feature_schemas() -> dict:
    """生成特征层表结构"""
    return {
        "feature_technical": """
            CREATE TABLE IF NOT EXISTS feature_technical (
                symbol String,
                timeframe String,
                timestamp DateTime64(3),
                
                returns_1m Float64,
                returns_5m Float64,
                returns_15m Float64,
                returns_1h Float64,
                
                volatility Float64,
                atr Float64,
                
                momentum Float64,
                rsi Float64,
                macd Float64,
                macd_signal Float64,
                macd_hist Float64,
                
                ma_5 Float64,
                ma_10 Float64,
                ma_20 Float64,
                ma_50 Float64,
                ma_200 Float64,
                
                bb_upper Float64,
                bb_middle Float64,
                bb_lower Float64,
                
                adx Float64,
                cci Float64,
                
                volume_ma Float64,
                volume_ratio Float64,
                
                computed_at DateTime64(3) DEFAULT now64(3)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (symbol, timeframe, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 90 DAY
        """,
        
        "feature_microstructure": """
            CREATE TABLE IF NOT EXISTS feature_microstructure (
                symbol String,
                timestamp DateTime64(3),
                
                spread Float64,
                spread_bps Float64,
                
                imbalance Float64,
                imbalance_ma Float64,
                
                trade_flow Float64,
                trade_flow_ma Float64,
                
                vwap Float64,
                twap Float64,
                
                kyle_lambda Float64,
                amihud_illiq Float64,
                
                computed_at DateTime64(3) DEFAULT now64(3)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 60 DAY
        """,
        
        "feature_sentiment": """
            CREATE TABLE IF NOT EXISTS feature_sentiment (
                symbol String,
                timestamp DateTime64(3),
                
                news_sentiment Float64,
                news_count UInt32,
                news_weighted_sentiment Float64,
                
                social_sentiment Float64,
                social_count UInt32,
                social_weighted_sentiment Float64,
                
                combined_sentiment Float64,
                sentiment_momentum Float64,
                
                fear_greed_index Nullable(Float64),
                
                computed_at DateTime64(3) DEFAULT now64(3)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 30 DAY
        """,
    }


def generate_signal_schemas() -> dict:
    """生成信号层表结构"""
    return {
        "signal_trading": """
            CREATE TABLE IF NOT EXISTS signal_trading (
                signal_id String,
                trace_id String,
                
                symbol String,
                exchange String,
                timestamp DateTime64(3),
                
                signal_type String,
                direction String,
                
                strength Float64,
                confidence Float64,
                
                entry_price Nullable(Float64),
                target_price Nullable(Float64),
                stop_price Nullable(Float64),
                
                strategy_id String,
                
                feature_ids Array(String),
                feature_weights Map(String, Float64),
                
                metadata Map(String, String),
                
                created_at DateTime64(3) DEFAULT now64(3)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 30 DAY
        """,
        
        "signal_fusion": """
            CREATE TABLE IF NOT EXISTS signal_fusion (
                fusion_id String,
                trace_id String,
                
                symbol String,
                timestamp DateTime64(3),
                
                fused_direction String,
                fused_strength Float64,
                fused_confidence Float64,
                
                source_signals Array(String),
                source_count UInt32,
                
                agreement_score Float64,
                conflict_score Float64,
                
                weights Map(String, Float64),
                
                created_at DateTime64(3) DEFAULT now64(3)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (symbol, timestamp)
            TTL toDateTime(timestamp) + INTERVAL 30 DAY
        """,
    }


def generate_replay_schemas() -> dict:
    """生成回放层表结构"""
    return {
        "replay_events": """
            CREATE TABLE IF NOT EXISTS replay_events (
                replay_id String,
                event_id String,
                event_type String,
                
                exchange String,
                symbol String,
                timestamp DateTime64(3),
                sequence Int64,
                
                data String,
                
                replayed_at DateTime64(3) DEFAULT now64(3),
                
                metadata Map(String, String)
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(timestamp)
            ORDER BY (replay_id, timestamp, sequence)
            TTL toDateTime(timestamp) + INTERVAL 365 DAY
        """,
        
        "replay_checkpoints": """
            CREATE TABLE IF NOT EXISTS replay_checkpoints (
                checkpoint_id String,
                replay_id String,
                
                exchange String,
                symbol String,
                timeframe String,
                
                last_timestamp Int64,
                last_sequence Int64,
                processed_count Int64,
                
                created_at Int64,
                metadata String
            ) ENGINE = MergeTree()
            ORDER BY (replay_id, checkpoint_id)
        """,
        
        "replay_sessions": """
            CREATE TABLE IF NOT EXISTS replay_sessions (
                session_id String,
                replay_id String,
                
                start_time Int64,
                end_time Int64,
                speed Float64,
                
                status String,
                
                started_at Int64,
                completed_at Nullable(Int64),
                
                events_processed Int64 DEFAULT 0,
                errors_count Int64 DEFAULT 0,
                
                metadata String
            ) ENGINE = MergeTree()
            ORDER BY (session_id, started_at)
        """,
    }


def generate_materialized_views() -> dict:
    """生成物化视图"""
    return {
        "mv_klines_1h_from_1m": """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_klines_1h_from_1m
            TO aggregated_klines
            AS SELECT
                exchange,
                symbol,
                '1h' as timeframe,
                toStartOfHour(open_time) as open_time,
                toStartOfHour(open_time) + INTERVAL 1 HOUR as close_time,
                
                argMin(open, open_time) as open,
                max(high) as high,
                min(low) as low,
                argMax(close, open_time) as close,
                sum(volume) as volume,
                sum(quote_volume) as quote_volume,
                sum(trades) as trades,
                
                sum(volume * argMin(open, open_time)) / sum(volume) as vwap,
                avg(close) as twap,
                
                1 as is_closed,
                now64(3) as aggregated_at,
                count() as source_count
            FROM aggregated_klines
            WHERE timeframe = '1m' AND is_closed = 1
            GROUP BY exchange, symbol, toStartOfHour(open_time)
        """,
        
        "mv_klines_4h_from_1h": """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_klines_4h_from_1h
            TO aggregated_klines
            AS SELECT
                exchange,
                symbol,
                '4h' as timeframe,
                toStartOfInterval(open_time, INTERVAL 4 HOUR) as open_time,
                toStartOfInterval(open_time, INTERVAL 4 HOUR) + INTERVAL 4 HOUR as close_time,
                
                argMin(open, open_time) as open,
                max(high) as high,
                min(low) as low,
                argMax(close, open_time) as close,
                sum(volume) as volume,
                sum(quote_volume) as quote_volume,
                sum(trades) as trades,
                
                sum(volume * argMin(open, open_time)) / sum(volume) as vwap,
                avg(close) as twap,
                
                1 as is_closed,
                now64(3) as aggregated_at,
                count() as source_count
            FROM aggregated_klines
            WHERE timeframe = '1h' AND is_closed = 1
            GROUP BY exchange, symbol, toStartOfInterval(open_time, INTERVAL 4 HOUR)
        """,
        
        "mv_klines_1d_from_1h": """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_klines_1d_from_1h
            TO aggregated_klines
            AS SELECT
                exchange,
                symbol,
                '1d' as timeframe,
                toStartOfDay(open_time) as open_time,
                toStartOfDay(open_time) + INTERVAL 1 DAY as close_time,
                
                argMin(open, open_time) as open,
                max(high) as high,
                min(low) as low,
                argMax(close, open_time) as close,
                sum(volume) as volume,
                sum(quote_volume) as quote_volume,
                sum(trades) as trades,
                
                sum(volume * argMin(open, open_time)) / sum(volume) as vwap,
                avg(close) as twap,
                
                1 as is_closed,
                now64(3) as aggregated_at,
                count() as source_count
            FROM aggregated_klines
            WHERE timeframe = '1h' AND is_closed = 1
            GROUP BY exchange, symbol, toStartOfDay(open_time)
        """,
        
        "mv_daily_volume_stats": """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_volume_stats
            ENGINE = SummingMergeTree()
            PARTITION BY toYYYYMM(date)
            ORDER BY (exchange, symbol, date)
            AS SELECT
                exchange,
                symbol,
                toDate(open_time) as date,
                sum(volume) as total_volume,
                sum(quote_volume) as total_quote_volume,
                sum(trades) as total_trades
            FROM aggregated_klines
            WHERE timeframe = '1d'
            GROUP BY exchange, symbol, toDate(open_time)
        """,
    }


def get_all_schemas() -> dict:
    """获取所有表结构"""
    return {
        **generate_raw_schemas(),
        **generate_normalized_schemas(),
        **generate_aggregated_schemas(),
        **generate_feature_schemas(),
        **generate_signal_schemas(),
        **generate_replay_schemas(),
    }


def get_all_materialized_views() -> dict:
    """获取所有物化视图"""
    return generate_materialized_views()


DATA_LAKE_SCHEMAS = get_all_schemas()
DATA_LAKE_VIEWS = get_all_materialized_views()
