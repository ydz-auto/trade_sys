# LLM 资源池 - 多级降级系统

## 概述

实现了一个高可用的 LLM 资源池，支持多级降级策略，确保即使多个 API 服务不可用时，系统仍然能正常工作。

## 降级链

```
智谱 AI (GLM-4-Flash) 
    ↓ (失败/熔断)
硅基流动 (DeepSeek V2.5)
    ↓ (失败/熔断)
DeepSeek API
    ↓ (失败/熔断)
百度千帆
    ↓ (失败/熔断)
阿里百炼
    ↓ (失败/熔断)
Ollama 本地模型
    ↓ (失败/熔断)
关键词匹配 (终极降级)
```

## 功能特性

### 1. 熔断器 (Circuit Breaker)
- 每个 LLM 池独立熔断器
- 配置失败阈值和重置超时时间
- 半开状态测试重试

### 2. 重试机制
- 指数退避重试
- 可配置最大重试次数

### 3. 负载均衡
- 优先级策略（优先使用高级池）
- 自动切换到下一个可用池

### 4. 状态监控
- `get_pool_stats()` 获取所有池的状态
- 实时监控熔断状态和失败计数

## 配置文件

`config/llm_pools.yaml`

```yaml
llm_pools:
  zhipu:
    enabled: true
    priority: 1
    type: openai_compatible
    base_url: https://open.bigmodel.cn/api/paas/v4
    api_key_env: ZHIPU_API_KEY
    models:
      - glm-4-flash
    circuit_breaker:
      failure_threshold: 5
      timeout_seconds: 60
    fallback_to: siliconflow
  
  # ... 更多池配置
```

## 使用方式

### 直接使用 LLM 池

```python
from infrastructure.llm import get_llm_pool

llm_pool = get_llm_pool()

# 发送聊天请求
response = await llm_pool.chat(
    messages=[{"role": "user", "content": "分析这篇新闻"}],
    temperature=0.3,
    max_tokens=400
)

print(f"Success: {response.success}")
print(f"Pool used: {response.pool_used}")
print(f"Result: {response.text}")

# 获取池状态
stats = llm_pool.get_pool_stats()
print(stats)
```

### 新闻情绪分析（高级方法）

```python
result = await llm_pool.analyze_news_sentiment(
    title="BTC ETF 流入创新高",
    content="..."
)

print(result)
# {
#   "sentiment": "bullish",
#   "sentiment_score": 0.85,
#   "is_black_swan": false,
#   "black_swan_level": "none",
#   "affected_symbols": ["BTC"],
#   "summary": "..."
# }
```

### 环境变量配置

设置 API 密钥（可选，没配置的话会自动降级到关键词匹配）：

```bash
export ZHIPU_API_KEY=your_zhipu_key
export SILICONFLOW_API_KEY=your_siliconflow_key
export DEEPSEEK_API_KEY=your_deepseek_key
```

### 完全零配置模式

即使不配置任何 API 密钥，系统仍然能工作！会自动使用关键词匹配进行情绪分析。

## 架构

```
infrastructure/llm/
├── __init__.py
└── llm_pool.py
    ├── CircuitBreaker        # 熔断器
    ├── KeywordAnalyzer       # 关键词分析（终极降级）
    ├── OpenAICompatibleClient# OpenAI 兼容 API 客户端
    ├── OllamaClient          # Ollama 本地模型客户端
    ├── LLMPoolManager        # 主管理器
    └── get_llm_pool()        # 全局单例
```

## 与新闻采集器集成

新的 `news_collector.py` 已自动集成：

```python
# 自动使用 LLM 池 + 降级
collector = NewsCollector(use_llm=True)
news = await collector.collect()

# 查看每条新闻使用了哪个池
for item in news:
    print(f"Title: {item.title}")
    print(f"Sentiment: {item.sentiment}")
    print(f"Pool: {item.llm_pool_used}")
    print(f"Keyword fallback: {item._fallback_to_keyword}")
```

## 监控

每个 LLM 池都有独立的状态：

```python
stats = llm_pool.get_pool_stats()
# {
#   "zhipu": {
#     "pool_id": "zhipu",
#     "state": "CLOSED",   # CLOSED/OPEN/HALF_OPEN
#     "failure_count": 0,
#     "last_failure_time": null
#   },
#   "siliconflow": { ... },
#   ...
# }
```

## 性能建议

1. 优先使用免费 API（智谱、硅基流动）
2. 本地 Ollama 作为备用，适合离线场景
3. 关键词匹配作为终极保障，100% 可用
4. 熔断器阈值建议 3-5，超时 60s

## 文件说明

| 文件 | 说明 |
|------|------|
| `infrastructure/llm/llm_pool.py` | LLM 池核心实现 |
| `config/llm_pools.yaml` | 配置文件 |
| `services/data_service/collectors/news_collector.py` | 集成的新闻采集器 |
