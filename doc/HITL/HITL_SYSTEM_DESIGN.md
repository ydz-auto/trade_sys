# TradeAgent HITL (Human-in-the-Loop) 审批系统设计文档

**版本**: 1.0  
**日期**: 2026-05-11  
**状态**: 设计中

---

## 一、概述

### 1.1 什么是 HITL

HITL (Human-in-the-Loop) 是一种将人工决策融入自动化流程的架构模式。在交易系统中，这意味着：

- **信号生成** → **人工审批** → **执行** → **监控**

### 1.2 为什么需要 HITL

| 场景 | 无 HITL | 有 HITL |
|------|---------|---------|
| 市场异常 | 可能自动亏损 | 可人工暂停 |
| 模型错误 | 可能执行错误交易 | 可拦截 |
| 突发事件 | 可能追高杀低 | 可人工确认 |
| 风控合规 | 完全依赖模型 | 人工双重确认 |
| 系统故障 | 可能无限亏损 | 可人工介入 |

### 1.3 设计目标

```
┌─────────────────────────────────────────────────────────────────┐
│                    TradeAgent HITL 模式                          │
├─────────────────────────────────────────────────────────────────┤
│  模式1: AUTO (自动执行)                                        │
│    Signal → Decision → Execution (无需人工)                     │
├─────────────────────────────────────────────────────────────────┤
│  模式2: MANUAL (人工审批)                                      │
│    Signal → Approval Queue → Telegram/WeChat                    │
│         ↓                                                       │
│    人工确认 → 信号时效性检查 → 执行                             │
│         ↓                                                       │
│    超时 → 重新计算 → 二次确认                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、核心概念

### 2.1 交易模式

```python
class TradingMode(str, Enum):
    AUTO = "auto"           # 全自动模式，直接执行
    MANUAL = "manual"       # 人工审批模式
    HYBRID = "hybrid"       # 混合模式：智能判断是否需要确认
```

### 2.2 审批状态

```python
class ApprovalStatus(str, Enum):
    PENDING = "pending"           # 等待确认
    APPROVED = "approved"         # 已批准
    REJECTED = "rejected"         # 已拒绝
    TIMEOUT = "timeout"           # 超时
    CANCELLED = "cancelled"       # 已取消
    RECALCULATING = "recalculating" # 重新计算中
    RESUBMITTED = "resubmitted"   # 重新提交
    EXPIRED = "expired"           # 已过期（重试次数用完）
    SIGNAL_STALE = "signal_stale" # 信号已过期
```

### 2.3 信号时效性

```
Signal 发出
    │
    ▼
signal_created_at: datetime    # 信号生成时间
signal_expires_at: datetime    # 信号过期时间 (默认 60s)
approval_delayed_threshold: int  # 审批延迟阈值 (默认 60s)
    │
    ▼
用户审批时检查：
1. 信号是否已过期？
2. 审批延迟是否超过阈值？
3. 价格是否变化过大？
    │
    ▼
任何一项触发 → 重新计算 → 二次确认
```

---

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         TradeAgent                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    Data Service                                   │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │   Exchange   │ │    News     │ │    ETF      │              │
│  │  Collector  │ │  Collector  │ │  Collector  │              │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│         │                │                │                      │
│         └────────────────┼────────────────┘                      │
│                          ▼                                       │
│                   Raw Data (Kafka)                               │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Fusion Service                                 │
│  ┌─────────────────────────────────────────────────┐            │
│  │              Fusion Engine                       │            │
│  │  Multi-source Signal Generation                 │            │
│  └─────────────────────┬───────────────────────────┘            │
│                        ▼                                         │
│                   Signal (Kafka)                                 │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Decision Gate                                   │
│  ┌─────────────────────────────────────────────────┐            │
│  │           Mode: AUTO / MANUAL / HYBRID         │            │
│  └─────────────────────┬───────────────────────────┘            │
│                        │                                         │
│         ┌──────────────┼──────────────┐                          │
│         ▼              ▼              ▼                          │
│    ┌────────┐    ┌──────────┐   ┌─────────┐                    │
│    │  AUTO  │    │  HYBRID  │   │ MANUAL  │                    │
│    │  直接  │    │ 智能判断 │   │ 审批   │                    │
│    │  执行  │    │         │   │        │                    │
│    └────────┘    └────┬────┘   └────┬────┘                    │
│                       │              │                           │
└───────────────────────┼──────────────┼───────────────────────────┘
                        │              │
                        ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Approval Service                               │
│  ┌─────────────────────────────────────────────────┐            │
│  │              Approval Queue                       │            │
│  │  - 创建审批请求                                   │            │
│  │  - 状态管理                                       │            │
│  │  - 超时检测                                       │            │
│  │  - 信号时效性检查                                 │            │
│  └─────────────────────┬───────────────────────────┘            │
│                        │                                         │
│         ┌──────────────┼──────────────┐                          │
│         ▼              ▼              ▼                          │
│    ┌────────┐    ┌──────────┐   ┌─────────┐                    │
│    │Signal  │    │ Timeout  │   │ Price   │                    │
│    │Expired │    │  Retry   │   │ Change  │                    │
│    └────┬───┘    └────┬─────┘   └────┬────┘                    │
│         │              │              │                           │
│         └──────────────┼──────────────┘                          │
│                        │                                         │
│                        ▼                                         │
│              Recalculate + Resubmit                              │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                 Notification Service                              │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │  Telegram   │ │   WeChat    │ │    SMS      │              │
│  │     Bot     │ │     Bot     │ │             │              │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│         │                │                │                      │
│         ▼                ▼                ▼                      │
│    User Confirm    User Confirm      (Fallback)                  │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Execution Service                                │
│  ┌─────────────────────────────────────────────────┐            │
│  │              Order Executor                      │            │
│  │  - Place Order                                  │            │
│  │  - Monitor Position                            │            │
│  │  - Risk Management                             │            │
│  └─────────────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 数据流时序图

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                   完整审批流程（含时效性检查）                   │
                    └─────────────────────────────────────────────────────────────────┘

Signal 生成                    用户收到通知                    用户点击"确认"
    │                              │                              │
    │                              │                              │
    ▼                              ▼                              ▼
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│ signal_created_at │      │ 等待用户响应...     │      │ approved_at = now │
│     = now()       │      │                   │      │                   │
└─────────┬─────────┘      │ (可能等待很久)     │      └─────────┬─────────┘
          │                 └─────────┬─────────┘                │
          │                           │                          │
          │                           │                          │
          ▼                           ▼                          ▼
┌───────────────────┐      ┌───────────────────┐      ┌───────────────────┐
│ signal_expires_at │      │                   │      │ 检查1: 信号过期?  │
│   = now() + 60s   │      │                   │      │ now > expires_at │
└─────────┬─────────┘      │                   │      └─────────┬─────────┘
          │                 │                   │                │
          │                 │                   │         ┌─────┴─────┐
          │                 │                   │        Yes          No
          │                 │                   │         │            │
          │                 │                   │         ▼            │
          │                 │                   │   ┌───────────┐       │
          │                 │                   │   │ 拒绝执行  │       │
          │                 │                   │   │ 需重计算  │       │
          │                 │                   │   └───────────┘       │
          │                 │                   │                      │
          │                 │                   │                      │
          │                 │                   │                      ▼
          │                 │                   │            ┌───────────────────┐
          │                 │                   │            │ 检查2: 审批延迟过长?│
          │                 │                   │            │ delay = approved   │
          │                 │                   │            │     - created     │
          │                 │                   │            └─────────┬─────────┘
          │                 │                   │                      │
          │                 │                   │               ┌─────┴─────┐
          │                 │                   │              Yes          No
          │                 │                   │               │            │
          │                 │                   │               ▼            │
          │                 │                   │      ┌───────────────┐      │
          │                 │                   │      │ 检查价格变化 │      │
          │                 │                   │      │ > threshold?  │      │
          │                 │                   │      └───────┬───────┘      │
          │                 │                   │              │              │
          │                 │                   │       ┌─────┴─────┐       │
          │                 │                   │      Yes          No       │
          │                 │                   │       │            │       │
          │                 │                   │       ▼            │       │
          │                 │                   │  ┌───────────┐   │       │
          │                 │                   │  │ 重新计算  │   │       │
          │                 │                   │  │ 二次确认  │   │       │
          │                 │                   │  └─────┬─────┘   │       │
          │                 │                   │        │         │       │
          │                 │                   │        └─────────┼───────┘
          │                 │                   │                  │
          │                 │                   │                  │
          │                 │                   │                  ▼
          │                 │                   │           ┌───────────┐
          │                 │                   │           │ 执行交易  │
          │                 │                   │           └───────────┘
```

---

## 四、配置设计

### 4.1 配置层级

```
┌─────────────────────────────────────────────────────────────────┐
│                    配置层级                                       │
└─────────────────────────────────────────────────────────────────┘

Level 1: 系统级配置 (System Config)
  │
  └── 所有交易对通用配置
      - 默认超时时间
      - 默认重试次数
      - 通知渠道配置

Level 2: 交易对级配置 (Symbol Config)
  │
  └── 针对特定交易对的配置
      - BTC/USDT: 高风险，高延迟阈值
      - ETH/USDT: 中风险
      - 山寨币: 高风险

Level 3: 用户级配置 (User Config)
  │
  └── 用户个性化配置
      - 通知渠道偏好
      - 审批延迟阈值
      - 自动批准阈值
```

### 4.2 配置项定义

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `approval.mode` | TradingMode | hybrid | 审批模式 |
| `approval.timeout_seconds` | int | 300 | 审批超时时间 |
| `approval.max_retries` | int | 2 | 最大重试次数 |
| `approval.recalculate_on_timeout` | bool | true | 超时后重新计算 |
| `approval.signal_expires_seconds` | int | 60 | 信号有效期 |
| `approval.delayed_threshold_seconds` | int | 60 | 审批延迟阈值 |
| `approval.price_change_threshold` | float | 0.01 | 价格变化阈值 (1%) |
| `approval.auto_threshold_usd` | float | 100 | 小额自动批准阈值 |
| `approval.notify_telegram` | bool | true | Telegram 通知 |
| `approval.notify_wechat` | bool | false | WeChat 通知 |
| `approval.notify_sms` | bool | false | SMS 通知 |

### 4.3 智能判断规则 (HYBRID 模式)

```python
def _needs_approval(self, signal: dict) -> bool:
    """
    判断是否需要人工确认
    
    规则：
    1. 小额自动批准 (estimated_value < auto_threshold_usd)
    2. 高风险必须确认 (risk_level in [HIGH, EXTREME])
    3. 低置信度必须确认 (confidence < 0.7)
    4. 新上市交易对必须确认
    5. 人工模式全部需要确认
    """
    pass
```

---

## 五、通知服务设计

### 5.1 Telegram Bot

```python
class TelegramApprovalBot:
    async def send_approval(self, request: ApprovalRequest):
        """
        发送审批消息
        
        包含：
        - 操作详情 (BUY/SELL symbol)
        - 价格/数量/价值
        - 信号理由
        - 风险等级
        - 信心度
        - 信号年龄警告
        """
        pass
    
    async def handle_callback(self, update: Update):
        """
        处理用户回调
        
        支持：
        - approve:{id} - 确认
        - reject:{id} - 拒绝
        - force_approve:{id} - 强制批准 (忽略延迟)
        - delay:{id} - 延长 10 分钟
        """
        pass
```

### 5.2 消息模板

#### 审批请求消息

```
📊 交易确认请求

操作: BUY BTC/USDT
价格: $67,234.56
数量: 0.01 BTC
价值: $672.35

信号理由:
- ETF 资金流入 +$120M
- BTC 情绪指数上升 15%
- 技术指标 MACD 金叉

风险等级: MEDIUM
信心度: 85%

⚠️ 信号已生成 45 秒前

⏱️ 请在 5 分钟内确认
```

#### 延迟警告消息

```
🚨 警告：审批延迟过长

⚠️ 信号已生成 120 秒前
📈 当前价格已变化 +2.35%

当前价格: $68,815.23
审批时价格: $67,234.56

请重新确认是否执行？
```

---

## 六、数据库设计

### 6.1 表结构

```sql
-- 审批请求表
CREATE TABLE approval_requests (
    id VARCHAR(50) PRIMARY KEY,
    type VARCHAR(20) NOT NULL,           -- trade, adjust_position, close_position
    action VARCHAR(10) NOT NULL,          -- BUY, SELL, CLOSE
    
    -- 交易信息
    symbol VARCHAR(20) NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    quantity DECIMAL(20, 8) NOT NULL,
    estimated_value DECIMAL(20, 8),
    
    -- 信号信息
    signal_id VARCHAR(50),
    signal_created_at TIMESTAMP,
    signal_expires_at TIMESTAMP,
    original_signal_id VARCHAR(50),       -- 如果是重新计算的，记录原信号ID
    
    -- 审批信息
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    approved_at TIMESTAMP,
    rejected_at TIMESTAMP,
    
    -- 重试信息
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 2,
    recalculated_from VARCHAR(50),
    
    -- 原因
    reason TEXT,
    risk_level VARCHAR(20),
    confidence DECIMAL(5, 2),
    rejection_reason TEXT,
    
    -- 元数据
    created_by VARCHAR(50),
    approved_by VARCHAR(50),
    notified_channels JSON,
    
    INDEX idx_status (status),
    INDEX idx_symbol (symbol),
    INDEX idx_created_at (created_at),
    INDEX idx_signal_id (signal_id)
);

-- 审批历史表
CREATE TABLE approval_history (
    id SERIAL PRIMARY KEY,
    approval_id VARCHAR(50) NOT NULL,
    event_type VARCHAR(20) NOT NULL,       -- created, notified, approved, rejected, timeout, recalculated
    event_data JSON,
    created_at TIMESTAMP NOT NULL,
    
    INDEX idx_approval_id (approval_id),
    INDEX idx_created_at (created_at)
);

-- 用户配置表
CREATE TABLE user_approval_config (
    user_id VARCHAR(50) PRIMARY KEY,
    mode VARCHAR(20) NOT NULL DEFAULT 'hybrid',
    timeout_seconds INT DEFAULT 300,
    max_retries INT DEFAULT 2,
    auto_threshold_usd DECIMAL(20, 8) DEFAULT 100,
    delayed_threshold_seconds INT DEFAULT 60,
    notify_telegram BOOLEAN DEFAULT TRUE,
    notify_wechat BOOLEAN DEFAULT FALSE,
    telegram_chat_id VARCHAR(50),
    wechat_webhook_url VARCHAR(255),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- 交易对审批配置表
CREATE TABLE symbol_approval_config (
    symbol VARCHAR(20) PRIMARY KEY,
    mode VARCHAR(20) NOT NULL,
    timeout_seconds INT,
    max_retries INT,
    auto_threshold_usd DECIMAL(20, 8),
    delayed_threshold_seconds INT,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## 七、API 设计

### 7.1 REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/approval/request` | POST | 创建审批请求 |
| `/api/v1/approval/{id}` | GET | 获取审批详情 |
| `/api/v1/approval/{id}/approve` | POST | 批准交易 |
| `/api/v1/approval/{id}/reject` | POST | 拒绝交易 |
| `/api/v1/approval/{id}/delay` | POST | 延长超时时间 |
| `/api/v1/approval/list` | GET | 获取待审批列表 |
| `/api/v1/approval/history` | GET | 获取审批历史 |
| `/api/v1/mode` | GET | 获取当前交易模式 |
| `/api/v1/mode` | POST | 设置交易模式 |
| `/api/v1/approval/config` | GET | 获取审批配置 |
| `/api/v1/approval/config` | PUT | 更新审批配置 |

### 7.2 SSE API

| 端点 | 说明 |
|------|------|
| `/sse/approvals` | 审批状态实时推送 |
| `/sse/market` | 市场数据实时推送 |

### 7.3 API 响应示例

#### 审批请求响应

```json
{
  "success": true,
  "data": {
    "id": "apr_1715400000000",
    "type": "trade",
    "action": "BUY",
    "symbol": "BTC/USDT",
    "price": 67234.56,
    "quantity": 0.01,
    "estimated_value": 672.35,
    "status": "pending",
    "created_at": "2026-05-11T10:00:00Z",
    "expires_at": "2026-05-11T10:05:00Z",
    "signal_expires_at": "2026-05-11T10:01:00Z",
    "approval_delayed_threshold": 60,
    "retry_count": 0,
    "max_retries": 2
  }
}
```

#### 批准响应（含时效性检查）

```json
{
  "success": true,
  "data": {
    "needs_recalculation": true,
    "message": "审批延迟 120s，价格已变化 +2.35%，需要重新计算",
    "price_change": 0.0235,
    "original_request": {
      "id": "apr_1715400000000",
      "status": "signal_stale"
    },
    "new_request": {
      "id": "apr_1715400060000",
      "price": 68815.23,
      "quantity": 0.00976,
      "status": "pending"
    }
  }
}
```

---

## 八、错误处理

### 8.1 错误类型

| 错误类型 | 代码 | 说明 | 处理方式 |
|----------|------|------|---------|
| APPROVAL_NOT_FOUND | 1001 | 审批请求不存在 | 返回错误 |
| APPROVAL_ALREADY_PROCESSED | 1002 | 审批已处理 | 返回当前状态 |
| APPROVAL_TIMEOUT | 1003 | 审批超时 | 自动拒绝 |
| SIGNAL_EXPIRED | 1004 | 信号已过期 | 重新计算 |
| RECALCULATION_FAILED | 1005 | 重新计算失败 | 标记过期 |
| NOTIFICATION_FAILED | 1006 | 通知发送失败 | 重试/降级 |
| INVALID_ACTION | 1007 | 无效操作 | 返回错误 |

### 8.2 重试策略

```
通知发送失败:
  ↓
重试 3 次，间隔 5s, 10s, 30s
  ↓
失败 → 尝试其他通知渠道
  ↓
全部失败 → 记录日志 + 告警
```

---

## 九、监控与告警

### 9.1 监控指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| `approval.pending.count` | 待审批数量 | > 10 |
| `approval.pending.avg_age` | 平均等待时间 | > 300s |
| `approval.timeout.rate` | 超时率 | > 10% |
| `approval.recalculation.count` | 重新计算次数 | > 5/min |
| `approval.recalculation.success_rate` | 重新计算成功率 | < 80% |
| `notification.failed.count` | 通知失败次数 | > 3/min |

### 9.2 告警规则

```python
# 告警规则
alerts = [
    {
        "name": "approval_queue_large",
        "condition": "approval.pending.count > 10",
        "severity": "warning",
        "message": "待审批队列过长，请检查"
    },
    {
        "name": "approval_timeout_high",
        "condition": "approval.timeout.rate > 0.1",
        "severity": "critical",
        "message": "审批超时率过高，可能用户未收到通知"
    },
    {
        "name": "recalculation_failed",
        "condition": "approval.recalculation.success_rate < 0.8",
        "severity": "critical",
        "message": "重新计算成功率过低，请检查数据源"
    }
]
```

---

## 十、安全设计

### 10.1 权限控制

```
用户角色:
  ├── Admin: 所有审批权限
  ├── Trader: 普通交易审批权限
  └── Viewer: 仅查看权限
```

### 10.2 操作审计

```python
# 所有审批操作都记录审计日志
audit_log = {
    "event": "approval.approve",
    "approval_id": "apr_xxx",
    "user_id": "user_xxx",
    "timestamp": "2026-05-11T10:00:00Z",
    "ip": "192.168.1.1",
    "user_agent": "Telegram Bot",
    "success": True
}
```

---

## 十一、性能优化

### 11.1 缓存策略

```
审批请求缓存:
  - Redis: approval:{id} → JSON
  - TTL: 1 小时

用户配置缓存:
  - Redis: user_config:{user_id} → JSON
  - TTL: 5 分钟
```

### 11.2 并发处理

```
多个审批同时超时:
  │
  ▼
使用锁机制防止重复处理
  │
  ▼
Redis Distributed Lock
  key: "approval_lock:{id}"
  ttl: 30s
```

---

## 十二、部署架构

### 12.1 组件部署

```
┌─────────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │   data-     │   │   fusion-   │   │   approval- │           │
│  │   service   │   │   service   │   │   service   │           │
│  │  (3 pods)  │   │  (3 pods)   │   │  (3 pods)   │           │
│  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘           │
│         │                 │                 │                   │
│         └─────────────────┼─────────────────┘                   │
│                           │                                     │
│                           ▼                                     │
│                   ┌─────────────┐                               │
│                   │    Kafka    │                               │
│                   └──────┬──────┘                               │
│                          │                                      │
│                           ▼                                     │
│  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐           │
│  │  telegram- │   │   wechat-   │   │   api-      │           │
│  │    bot      │   │    bot      │   │   server    │           │
│  │  (2 pods)  │   │  (2 pods)   │   │  (3 pods)   │           │
│  └─────────────┘   └─────────────┘   └─────────────┘           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 12.2 依赖关系

```
Kafka ← data_service ← fusion_service ← approval_service
                                                      │
                              ┌───────────────────────┼───────────────────────┐
                              │                       │                       │
                              ▼                       ▼                       ▼
                        telegram_bot            wechat_bot              api_server
                              │                       │                       │
                              └───────────────────────┼───────────────────────┘
                                                      │
                                                      ▼
                                               Telegram/WeChat
                                                      │
                                                      ▼
                                                  Users
```

---

## 十三、测试策略

### 13.1 单元测试

```python
# 测试审批状态机
def test_approval_status_transitions():
    request = ApprovalRequest(...)
    
    # PENDING → APPROVED
    request.status = ApprovalStatus.PENDING
    assert request.can_transition_to(ApprovalStatus.APPROVED)
    
    # PENDING → TIMEOUT
    request.status = ApprovalStatus.PENDING
    assert request.can_transition_to(ApprovalStatus.TIMEOUT)
    
    # APPROVED → (任何状态) 应该失败
    request.status = ApprovalStatus.APPROVED
    assert not request.can_transition_to(ApprovalStatus.PENDING)
```

### 13.2 集成测试

```python
# 测试完整审批流程
async def test_full_approval_flow():
    # 1. 创建审批请求
    request = await approval_service.request_approval(signal)
    assert request.status == ApprovalStatus.PENDING
    
    # 2. 批准
    result = await approval_service.approve(request.id)
    assert result["success"] == True
    
    # 3. 验证状态
    request = await approval_service.get(request.id)
    assert request.status == ApprovalStatus.APPROVED
```

### 13.3 压力测试

```
场景: 100 个审批同时超时
预期: 
  - 系统正常处理
  - 无重复处理
  - 所有请求正确标记
  - 监控指标正确更新
```

---

## 十四、路线图

### Phase 1: MVP (1-2 周)
- [ ] 审批服务核心
- [ ] Telegram Bot 集成
- [ ] 基础 API
- [ ] 简单配置管理

### Phase 2: 增强 (2-3 周)
- [ ] 信号时效性检查
- [ ] 重新计算流程
- [ ] WeChat Bot 集成
- [ ] 前端审批监控

### Phase 3: 完善 (2 周)
- [ ] 监控告警
- [ ] 审计日志
- [ ] 权限控制
- [ ] 性能优化

### Phase 4: 高级功能 (持续)
- [ ] 多级审批
- [ ] 审批模板
- [ ] 移动端 App
- [ ] AI 辅助审批建议

---

## 十五、文档列表

| 文档 | 说明 |
|------|------|
| HITL_SYSTEM_DESIGN.md | 本文档 - 系统设计 |
| APPROVAL_SERVICE_API.md | API 文档 |
| APPROVAL_CONFIG_GUIDE.md | 配置指南 |
| TELEGRAM_BOT_GUIDE.md | Telegram Bot 使用指南 |
| DEPLOYMENT_GUIDE.md | 部署指南 |
| TROUBLESHOOTING.md | 故障排查 |

---

**文档版本**: 1.0  
**下次更新**: 2026-05-25
