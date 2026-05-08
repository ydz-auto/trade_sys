"""
User & Auth Schemas
用户和认证相关表结构
"""

USER_SCHEMAS = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            status VARCHAR(20) DEFAULT 'active',
            risk_level VARCHAR(20) DEFAULT 'normal',
            max_position_pct DECIMAL(5,2) DEFAULT 10.00,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

USER_ROLE_SCHEMAS = {
    "roles": """
        CREATE TABLE IF NOT EXISTS roles (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
    "user_roles": """
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id BIGINT REFERENCES users(id),
            role_id BIGINT REFERENCES roles(id),
            PRIMARY KEY (user_id, role_id)
        )
    """,
}

API_KEY_SCHEMAS = {
    "api_keys": """
        CREATE TABLE IF NOT EXISTS api_keys (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            api_key VARCHAR(64) UNIQUE NOT NULL,
            api_secret VARCHAR(128) NOT NULL,
            permissions JSONB DEFAULT '{}',
            status VARCHAR(20) DEFAULT 'active',
            last_used TIMESTAMP,
            expires_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}