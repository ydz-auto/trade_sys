# API Gateway 设计文档

# 🧠 1. 模块定位

# 1.1 核心作用

系统的**统一入口**，负责：
- 请求路由
- 认证鉴权
- 限流熔断
- 请求日志
- 统一响应格式

# 1.2 在系统中的位置

```
Client (Telegram/OpenClaw/Frontend)
    ↓
API Gateway
    ↓
Services (Factor/Risk/Decision/Position/Execution)
```

# 🏗️ 2. 路由设计

# 2.1 路由结构

```
/api/v1/
├── market/          # 市场数据
├── factor/          # 因子服务
├── risk/            # 风险服务
├── signal/          # 信号服务
├── position/        # 仓位服务
├── execution/       # 执行服务
├── state/           # 状态服务
├── config/          # 配置服务
├── control/         # 控制指令
│   ├── pause
│   ├── resume
│   └── close_all
└── system/          # 系统接口
```

# 2.2 详细路由定义

```python
ROUTES = {
    # 市场数据
    "GET /api/v1/market/price/{symbol}": "market_service.get_price",
    "GET /api/v1/market/ohlcv/{symbol}": "market_service.get_ohlcv",
    "GET /api/v1/market/etf/{symbol}": "market_service.get_etf_flow",

    # 因子服务
    "POST /api/v1/factor/calculate": "factor_service.calculate",
    "GET /api/v1/factor/scores/{symbol}": "factor_service.get_scores",

    # 风险服务
    "POST /api/v1/risk/calculate": "risk_service.calculate",
    "GET /api/v1/risk/index": "risk_service.get_risk_index",

    # 信号服务
    "POST /api/v1/signal/generate": "signal_service.generate",
    "GET /api/v1/signal/current": "signal_service.get_current_signal",

    # 仓位服务
    "GET /api/v1/position": "position_service.get_positions",
    "GET /api/v1/position/{symbol}": "position_service.get_position",
    "POST /api/v1/position/calculate": "position_service.calculate",

    # 执行服务
    "POST /api/v1/execution/order": "execution_service.submit_order",
    "GET /api/v1/execution/order/{order_id}": "execution_service.get_order",
    "POST /api/v1/execution/cancel/{order_id}": "execution_service.cancel_order",

    # 状态服务
    "GET /api/v1/state": "state_service.get_all_state",
    "GET /api/v1/state/{state_type}": "state_service.get_state",
    "GET /api/v1/state/history/{state_type}": "state_service.get_history",

    # 配置服务
    "GET /api/v1/config": "config_service.get_all",
    "GET /api/v1/config/{category}": "config_service.get_category",
    "PUT /api/v1/config/{category}": "config_service.update_category",
    "POST /api/v1/config/{category}/{key}": "config_service.update_key",

    # 控制指令
    "POST /api/v1/control/pause": "control_service.pause",
    "POST /api/v1/control/resume": "control_service.resume",
    "POST /api/v1/control/close_all": "control_service.close_all",
    "POST /api/v1/control/set_mode": "control_service.set_mode",

    # 系统接口
    "GET /api/v1/system/health": "system_service.health",
    "GET /api/v1/system/status": "system_service.get_status"
}
```

# 🔐 3. 认证鉴权

# 3.1 API Key认证

```python
@app.before_request
def authenticate():
    if request.path.startswith("/api/v1/system/health"):
        return None

    api_key = request.headers.get("X-API-Key")
    if not api_key:
        return {"error": "Missing API key"}, 401

    user = auth_service.validate_api_key(api_key)
    if not user:
        return {"error": "Invalid API key"}, 401

    g.current_user = user
    return None
```

# 3.2 JWT Token认证

```python
def create_access_token(user_id: str, expires_delta: timedelta = timedelta(hours=24)) -> str:
    to_encode = {
        "sub": user_id,
        "exp": datetime.utcnow() + expires_delta
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm="HS256")

def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError("Token expired")
    except jwt.JWTError:
        raise AuthError("Invalid token")
```

# 3.3 权限控制

```python
PERMISSIONS = {
    "admin": ["*"],
    "trader": [
        "GET /api/v1/*",
        "POST /api/v1/signal/*",
        "POST /api/v1/execution/*",
        "POST /api/v1/control/*"
    ],
    "viewer": [
        "GET /api/v1/*"
    ]
}

def check_permission(user: dict, path: str, method: str) -> bool:
    user_role = user.get("role", "viewer")
    allowed = PERMISSIONS.get(user_role, [])

    if "*" in allowed:
        return True

    permission = f"{method} {path}"
    return permission in allowed
```

# 🚦 4. 限流熔断

# 4.1 限流规则

```python
RATE_LIMITS = {
    "default": {"requests": 100, "window": 60},
    "execution": {"requests": 10, "window": 60},
    "config_update": {"requests": 5, "window": 300},
    "control": {"requests": 3, "window": 60}
}

@app.before_request
def rate_limit():
    user = g.get("current_user")
    if not user:
        return None

    key = f"rate_limit:{user['id']}:{request.endpoint}"
    limit_config = RATE_LIMITS.get(request.endpoint, RATE_LIMITS["default"])

    current = redis.get(key)
    if current and int(current) >= limit_config["requests"]:
        return {"error": "Rate limit exceeded"}, 429

    redis.incr(key)
    if not current:
        redis.expire(key, limit_config["window"])

    return None
```

# 4.2 熔断机制

```python
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError()

        try:
            result = func(*args, **kwargs)
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
            return result
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
            raise
```

# 📝 5. 请求日志

# 5.1 日志格式

```python
LOG_FORMAT = {
    "request_id": "req_12345",
    "method": "POST",
    "path": "/api/v1/signal/generate",
    "user_id": "user_001",
    "ip": "192.168.1.1",
    "user_agent": "Mozilla/5.0...",
    "timestamp": 1710000000,
    "request_body": {...},
    "response_status": 200,
    "response_time_ms": 125,
    "error": null
}
```

# 5.2 日志中间件

```python
@app.before_request
def log_request():
    g.request_id = f"req_{uuid.uuid4().hex[:12]}"
    g.start_time = time.time()

@app.after_request
def log_response(response):
    log_data = {
        "request_id": g.request_id,
        "method": request.method,
        "path": request.path,
        "user_id": g.get("current_user", {}).get("id"),
        "ip": request.remote_addr,
        "response_status": response.status_code,
        "response_time_ms": int((time.time() - g.start_time) * 1000)
    }
    logger.info(log_data)
    return response
```

# 📤 6. 统一响应格式

# 6.1 响应结构

```python
class Response:
    @staticmethod
    def success(data=None, message="OK"):
        return {
            "success": True,
            "data": data,
            "message": message,
            "timestamp": int(time.time()),
            "request_id": g.get("request_id")
        }

    @staticmethod
    def error(code: int, message: str, details=None):
        return {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details
            },
            "timestamp": int(time.time()),
            "request_id": g.get("request_id")
        }
```

# 6.2 响应示例

```python
# 成功响应
{
    "success": True,
    "data": {
        "symbol": "BTC",
        "signal": "BUY",
        "confidence": 0.75
    },
    "message": "Signal generated successfully",
    "timestamp": 1710000000,
    "request_id": "req_12345"
}

# 错误响应
{
    "success": False,
    "error": {
        "code": 400,
        "message": "Invalid request",
        "details": "Missing required field: symbol"
    },
    "timestamp": 1710000000,
    "request_id": "req_12345"
}
```

# 🏗️ 7. 架构设计

```
API Gateway
├── RequestRouter
├── AuthMiddleware
│   ├── APIKeyAuth
│   └── JWTAuth
├── RateLimitMiddleware
├── CircuitBreakerMiddleware
├── RequestLogger
├── ResponseFormatter
├── ErrorHandler
└── SecurityHeaders
```

# 🔧 8. Flask实现

```python
from flask import Flask, request, g
from functools import wraps

app = Flask(__name__)

@app.before_request
def before_request():
    g.request_id = f"req_{uuid.uuid4().hex[:12]}"
    g.start_time = time.time()

@app.after_request
def after_request(response):
    logger.info({
        "request_id": g.request_id,
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "time_ms": int((time.time() - g.start_time) * 1000)
    })
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error({"error": str(e), "request_id": g.request_id})
    return Response.error(500, str(e))
```

# 🔗 9. 与Telegram/OpenClaw对接

# 9.1 Telegram Bot Webhook

```python
@app.route(f"/webhook/telegram/{TELEGRAM_BOT_TOKEN}", methods=["POST"])
def telegram_webhook():
    update = request.get_json()
    handler = TelegramHandler(bot, state_service, config_service)
    handler.process_update(update)
    return "OK"
```

# 9.2 OpenClaw Skill调用

```python
@app.route("/skill/tradeagent_control", methods=["POST"])
def skill_tradeagent_control():
    payload = request.get_json()
    action = payload.get("action")

    if action == "pause":
        control_service.pause()
    elif action == "resume":
        control_service.resume()
    elif action == "close_all":
        control_service.close_all()

    return Response.success()
```

# 🚨 10. 错误码定义

```python
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
    5002: "熔断触发"
}
```

# 🚀 11. 扩展方向

- 支持gRPC
- 支持WebSocket
- 支持消息队列
- 支持API版本管理
- 支持A/B测试路由
