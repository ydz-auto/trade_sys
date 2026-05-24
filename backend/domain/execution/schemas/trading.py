"""
Trading Schemas
交易相关表结构
"""

ORDER_SCHEMAS = {
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            order_id VARCHAR(64) UNIQUE NOT NULL,
            user_id BIGINT NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            order_type VARCHAR(20) NOT NULL,
            price DECIMAL(20, 8),
            quantity DECIMAL(20, 8),
            filled_quantity DECIMAL(20, 8) DEFAULT 0,
            avg_fill_price DECIMAL(20, 8),
            status VARCHAR(20) NOT NULL,
            exchange VARCHAR(20),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
    """,
}

POSITION_SCHEMAS = {
    "positions": """
        CREATE TABLE IF NOT EXISTS positions (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            quantity DECIMAL(20, 8) NOT NULL,
            avg_entry_price DECIMAL(20, 8) NOT NULL,
            unrealized_pnl DECIMAL(20, 8) DEFAULT 0,
            realized_pnl DECIMAL(20, 8) DEFAULT 0,
            exchange VARCHAR(20),
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_user_symbol (user_id, symbol)
        )
    """,
}

TRADE_SCHEMAS = {
    "trades": """
        CREATE TABLE IF NOT EXISTS trades (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            trade_id VARCHAR(64) UNIQUE NOT NULL,
            order_id VARCHAR(64) NOT NULL,
            user_id BIGINT NOT NULL,
            symbol VARCHAR(20) NOT NULL,
            side VARCHAR(10) NOT NULL,
            price DECIMAL(20, 8) NOT NULL,
            quantity DECIMAL(20, 8) NOT NULL,
            fee DECIMAL(20, 8) DEFAULT 0,
            fee_currency VARCHAR(10),
            exchange VARCHAR(20),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

FUND_FLOW_SCHEMAS = {
    "fund_flows": """
        CREATE TABLE IF NOT EXISTS fund_flows (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id BIGINT NOT NULL,
            type VARCHAR(20) NOT NULL,
            amount DECIMAL(20, 8) NOT NULL,
            balance_after DECIMAL(20, 8) NOT NULL,
            currency VARCHAR(10) DEFAULT 'USDT',
            reference_id VARCHAR(64),
            description VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
}
