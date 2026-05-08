"""
System Schemas
系统配置相关表结构
"""

SYSTEM_CONFIG_SCHEMAS = {
    "system_configs": """
        CREATE TABLE IF NOT EXISTS system_configs (
            id BIGSERIAL PRIMARY KEY,
            config_key VARCHAR(100) UNIQUE NOT NULL,
            config_value JSONB NOT NULL,
            description TEXT,
            updated_by BIGINT REFERENCES users(id),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

STRATEGY_CONFIG_SCHEMAS = {
    "strategy_configs": """
        CREATE TABLE IF NOT EXISTS strategy_configs (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            strategy_name VARCHAR(100) NOT NULL,
            version INTEGER DEFAULT 1,
            config JSONB NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}