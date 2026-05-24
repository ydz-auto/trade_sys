"""
Audit Schemas
审计日志表结构
"""

OPERATION_LOG_SCHEMAS = {
    "operation_logs": """
        CREATE TABLE IF NOT EXISTS operation_logs (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            action VARCHAR(100) NOT NULL,
            resource VARCHAR(100),
            details JSONB,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

LOGIN_LOG_SCHEMAS = {
    "login_logs": """
        CREATE TABLE IF NOT EXISTS login_logs (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            ip_address VARCHAR(45),
            user_agent TEXT,
            status VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

AUDIT_LOG_SCHEMAS = {
    "audit_logs": """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            user_id VARCHAR(50),
            api_key_id VARCHAR(50),
            action VARCHAR(50) NOT NULL,
            resource VARCHAR(100),
            request_path VARCHAR(255),
            request_method VARCHAR(10),
            request_params JSON,
            response_status INT,
            ip_address VARCHAR(45),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """,
}
