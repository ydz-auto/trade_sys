"""
API Gateway 配置 - 基础设施配置
"""

from infrastructure.config.enums import HTTPMethod


API_GATEWAY_CONFIGS = {
    "api_gateway.host": "0.0.0.0",
    "api_gateway.port": 8000,
    "api_gateway.debug": False,
    "api_gateway.service_timeout": 30.0,
    "api_gateway.max_retries": 3,
    "api_gateway.rate_limit_enabled": True,
    "api_gateway.auth_enabled": True,
    "api_gateway.log_requests": True,
    "api_gateway.cors_enabled": True,
    "api_gateway.allowed_origins": "*",
}


API_ROUTES = {
    "GET /api/v1/market/price/{symbol}": "market_service.get_price",
    "GET /api/v1/market/ohlcv/{symbol}": "market_service.get_ohlcv",
    "GET /api/v1/market/etf/{symbol}": "market_service.get_etf_flow",
    "POST /api/v1/factor/calculate": "factor_service.calculate",
    "GET /api/v1/factor/scores/{symbol}": "factor_service.get_scores",
    "POST /api/v1/risk/calculate": "risk_service.calculate",
    "GET /api/v1/risk/index": "risk_service.get_risk_index",
    "POST /api/v1/signal/generate": "signal_service.generate",
    "GET /api/v1/signal/current": "signal_service.get_current_signal",
    "GET /api/v1/position": "position_service.get_positions",
    "GET /api/v1/position/{symbol}": "position_service.get_position",
    "POST /api/v1/position/calculate": "position_service.calculate",
    "POST /api/v1/execution/order": "execution_service.submit_order",
    "GET /api/v1/execution/order/{order_id}": "execution_service.get_order",
    "POST /api/v1/execution/cancel/{order_id}": "execution_service.cancel_order",
    "GET /api/v1/state": "state_service.get_all_state",
    "GET /api/v1/state/{state_type}": "state_service.get_state",
    "GET /api/v1/state/history/{state_type}": "state_service.get_history",
    "GET /api/v1/config": "config_service.get_all",
    "GET /api/v1/config/{category}": "config_service.get_category",
    "PUT /api/v1/config/{category}": "config_service.update_category",
    "POST /api/v1/config/{category}/{key}": "config_service.update_key",
    "POST /api/v1/control/pause": "control_service.pause",
    "POST /api/v1/control/resume": "control_service.resume",
    "POST /api/v1/control/close_all": "control_service.close_all",
    "POST /api/v1/control/set_mode": "control_service.set_mode",
    "GET /api/v1/system/health": "system_service.health",
    "GET /api/v1/system/status": "system_service.get_status",
}


RATE_LIMITS = {
    "default": {"requests": 100, "window": 60},
    "execution": {"requests": 10, "window": 60},
    "config_update": {"requests": 5, "window": 300},
    "control": {"requests": 3, "window": 60},
}


PERMISSIONS = {
    "admin": ["*"],
    "trader": [
        "GET /api/v1/*",
        "POST /api/v1/signal/*",
        "POST /api/v1/execution/*",
        "POST /api/v1/control/*",
    ],
    "viewer": [
        "GET /api/v1/*",
    ],
}


ERROR_CODES = {
    1000: "系统错误",
    1001: "服务不可用",
    1002: "服务超时",
    2000: "认证错误",
    2001: "API Key无效",
    2002: "Token过期",
    2003: "权限不足",
    3000: "请求错误",
    3001: "参数错误",
    3002: "参数缺失",
    3003: "请求格式错误",
    4000: "业务错误",
    4001: "风控拦截",
    4002: "仓位超限",
    4003: "余额不足",
    4004: "订单失败",
    5000: "限流错误",
    5001: "请求过于频繁",
    5002: "熔断触发",
}
