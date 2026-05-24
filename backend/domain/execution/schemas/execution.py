"""
Execution Service PostgreSQL Schemas

执行服务专用表结构（PostgreSQL 语法）
"""

EXECUTION_ORDER_SCHEMAS = {
    "execution_orders": """
        CREATE TABLE IF NOT EXISTS execution_orders (
            id BIGSERIAL PRIMARY KEY,
            order_id VARCHAR(64) UNIQUE NOT NULL,
            client_order_id VARCHAR(64),
            exchange_order_id VARCHAR(64),
            
            symbol VARCHAR(32) NOT NULL,
            exchange VARCHAR(20) NOT NULL,
            market_type VARCHAR(20) NOT NULL DEFAULT 'spot',
            
            side VARCHAR(10) NOT NULL,
            order_type VARCHAR(20) NOT NULL,
            quantity NUMERIC(20, 8) NOT NULL,
            price NUMERIC(20, 8),
            stop_price NUMERIC(20, 8),
            
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            filled_quantity NUMERIC(20, 8) DEFAULT 0,
            avg_fill_price NUMERIC(20, 8),
            
            leverage INT DEFAULT 1,
            reduce_only BOOLEAN DEFAULT FALSE,
            time_in_force VARCHAR(10) DEFAULT 'GTC',
            
            error_message TEXT,
            metadata JSONB DEFAULT '{}',
            
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            INDEX idx_symbol_exchange (symbol, exchange),
            INDEX idx_status (status),
            INDEX idx_created_at (created_at)
        )
    """,
}

EXECUTION_POSITION_SCHEMAS = {
    "execution_positions": """
        CREATE TABLE IF NOT EXISTS execution_positions (
            id BIGSERIAL PRIMARY KEY,
            
            symbol VARCHAR(32) NOT NULL,
            exchange VARCHAR(20) NOT NULL,
            market_type VARCHAR(20) NOT NULL DEFAULT 'spot',
            
            quantity NUMERIC(20, 8) NOT NULL DEFAULT 0,
            avg_entry_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
            current_price NUMERIC(20, 8) DEFAULT 0,
            unrealized_pnl NUMERIC(20, 8) DEFAULT 0,
            realized_pnl NUMERIC(20, 8) DEFAULT 0,
            
            leverage INT DEFAULT 1,
            margin NUMERIC(20, 8) DEFAULT 0,
            liquidation_price NUMERIC(20, 8),
            position_id VARCHAR(64),
            
            metadata JSONB DEFAULT '{}',
            
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE (symbol, exchange, market_type),
            INDEX idx_symbol_exchange (symbol, exchange),
            INDEX idx_updated_at (updated_at)
        )
    """,
}

EXECUTION_FILL_SCHEMAS = {
    "execution_fills": """
        CREATE TABLE IF NOT EXISTS execution_fills (
            id BIGSERIAL PRIMARY KEY,
            fill_id VARCHAR(64) UNIQUE NOT NULL,
            order_id VARCHAR(64) NOT NULL,
            
            symbol VARCHAR(32) NOT NULL,
            exchange VARCHAR(20) NOT NULL,
            market_type VARCHAR(20) NOT NULL,
            
            side VARCHAR(10) NOT NULL,
            quantity NUMERIC(20, 8) NOT NULL,
            price NUMERIC(20, 8) NOT NULL,
            
            fee NUMERIC(20, 8) DEFAULT 0,
            fee_currency VARCHAR(10),
            
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            INDEX idx_order_id (order_id),
            INDEX idx_symbol_exchange (symbol, exchange),
            INDEX idx_created_at (created_at)
        )
    """,
}

EXECUTION_EVENT_SCHEMAS = {
    "execution_events": """
        CREATE TABLE IF NOT EXISTS execution_events (
            id BIGSERIAL PRIMARY KEY,
            event_id VARCHAR(64) UNIQUE NOT NULL,
            event_type VARCHAR(50) NOT NULL,
            
            order_id VARCHAR(64),
            symbol VARCHAR(32),
            exchange VARCHAR(20),
            
            payload JSONB NOT NULL,
            
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
            
            INDEX idx_event_type (event_type),
            INDEX idx_order_id (order_id),
            INDEX idx_created_at (created_at)
        )
    """,
}

EXECUTION_POSTGRESQL_SCHEMAS = {
    **EXECUTION_ORDER_SCHEMAS,
    **EXECUTION_POSITION_SCHEMAS,
    **EXECUTION_FILL_SCHEMAS,
    **EXECUTION_EVENT_SCHEMAS,
}

__all__ = ["EXECUTION_POSTGRESQL_SCHEMAS"]
