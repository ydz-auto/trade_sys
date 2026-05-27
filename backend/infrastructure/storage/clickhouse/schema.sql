-- ClickHouse Schema - 市场数据表

-- K线数据表
CREATE TABLE IF NOT EXISTS klines
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    exchange String DEFAULT 'binance',
    timeframe String,
    
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume Float64,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, ts)
TTL ts + INTERVAL 90 DAY;

-- 持仓量数据表
CREATE TABLE IF NOT EXISTS open_interest
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    exchange String DEFAULT 'binance',
    open_interest Float64,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, exchange, ts)
TTL ts + INTERVAL 90 DAY;

-- 资金费率数据表
CREATE TABLE IF NOT EXISTS funding_rates
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    exchange String DEFAULT 'binance',
    funding_rate Float64,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, exchange, ts)
TTL ts + INTERVAL 90 DAY;

-- 强平数据表
CREATE TABLE IF NOT EXISTS liquidations
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    exchange String DEFAULT 'binance',
    side String,
    size Float64,
    price Float64,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, ts)
TTL ts + INTERVAL 90 DAY;

-- 成交数据表
CREATE TABLE IF NOT EXISTS trades
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    exchange String DEFAULT 'binance',
    side String,
    price Float64,
    size Float64,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, ts)
TTL ts + INTERVAL 30 DAY;

-- 订单簿快照表
CREATE TABLE IF NOT EXISTS orderbook_snapshots
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    exchange String DEFAULT 'binance',
    bids String,
    asks String,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, ts)
TTL ts + INTERVAL 7 DAY;

-- 特征数据表（计算后的）
CREATE TABLE IF NOT EXISTS features
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    timeframe String,
    
    feature_name String,
    feature_value Float64,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, feature_name, ts)
TTL ts + INTERVAL 90 DAY;

-- 信号数据表
CREATE TABLE IF NOT EXISTS signals
(
    ts DateTime64(3, 'UTC'),
    symbol String,
    strategy String,
    signal_type String,
    confidence Float64,
    reason String,
    
    created_at DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, strategy, ts)
TTL ts + INTERVAL 365 DAY;

-- 聚合 K线视图（从1m生成其他周期）
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_klines_1h
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, ts)
AS
SELECT
    toStartOfHour(ts) as ts,
    symbol,
    '1h' as timeframe,
    any(open) as open,
    max(high) as high,
    min(low) as low,
    any(close) as close,
    sum(volume) as volume
FROM klines
WHERE timeframe = '1m'
GROUP BY ts, symbol;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_klines_4h
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, ts)
AS
SELECT
    toStartOfInterval(ts, INTERVAL 4 hour) as ts,
    symbol,
    '4h' as timeframe,
    any(open) as open,
    max(high) as high,
    min(low) as low,
    any(close) as close,
    sum(volume) as volume
FROM klines
WHERE timeframe = '1m'
GROUP BY ts, symbol;

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_klines_1d
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(ts)
ORDER BY (symbol, timeframe, ts)
AS
SELECT
    toStartOfDay(ts) as ts,
    symbol,
    '1d' as timeframe,
    any(open) as open,
    max(high) as high,
    min(low) as low,
    any(close) as close,
    sum(volume) as volume
FROM klines
WHERE timeframe = '1m'
GROUP BY ts, symbol;
