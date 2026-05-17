# Odaily 数据流重构说明

## 重构前的问题

- **架构混乱**：Odaily 数据采集和理解功能混合在 EventService 的 skill 中
- **数据重复采集**：DataService 和 EventService 各自调用 ClawHub 采集数据
- **职责不清**：EventService 的 Skill 应该是理解层，而不是采集层

## 重构后的架构

```
┌─────────────────────────────────────────────────────────────┐
│                    DataService (数据采集层)                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  OdailySkillAdapter  (data_service/adapters/...)     │  │
│  │  - 调用 ClawHub Skill 采集 M1-M5 数据                 │  │
│  │  - 转换为 StandardEvent 格式                          │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                │
│                    raw.odaily topic                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
                  Kafka (tradeagent.raw.news.odaily)
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                  EventService (理解增强层)                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  OdailyConsumer  (event_service/consumers/...)       │  │
│  │  - 消费 raw.odaily topic                              │  │
│  │  - 进行语义增强理解（叙事、可操作性、黑天鹅检测）        │  │
│  └──────────────────────────────────────────────────────┘  │
│                           ↓                                │
│                  enriched.odaily topic  (待实现)            │
└─────────────────────────────────────────────────────────────┘
```

## 文件变更

### 1. 新增文件

| 文件路径 | 说明 |
|---------|------|
| `infrastructure/messaging/topics.py` | 添加 `Topics.raw_odaily()` 方法 |
| `services/event_service/consumers/odaily_consumer.py` | 新增 Odaily 消费者 |
| `scripts/test_odaily_flow.py` | 测试脚本 |

### 2. 修改文件

| 文件路径 | 变更说明 |
|---------|---------|
| `runtime/ingestion_runtime/runtime.py` | 添加 Odaily 采集和发布逻辑 |
| `services/event_service/understanding/__init__.py` | 清理不完整的导入 |

## 功能说明

### DataService (Ingestion Runtime)

在 `runtime/ingestion_runtime/runtime.py` 中新增：

1. **初始化**：`OdailySkillAdapter` 实例化
2. **采集**：调用 `fetch_raw_data()` 和 `normalize()` 获取和标准化数据
3. **发布**：`_publish_odaily_events()` 将数据发布到 Kafka

### EventService (OdailyConsumer)

新增 `OdailyConsumer` 提供以下增强理解功能：

1. **叙事提取**：`_extract_narratives()` 从文本中提取叙事（ETF、Regulation、Bitcoin 等）
2. **可操作性计算**：`_calculate_actionability()` 评估事件可操作程度
3. **黑天鹅检测**：`_detect_black_swan()` 检测异常风险

## 测试

运行测试脚本：

```bash
cd backend
python scripts/test_odaily_flow.py
```

测试包含：
1. OdailySkillAdapter 功能测试
2. Kafka topic 配置测试
3. OdailyConsumer 增强逻辑测试
4. 端到端集成模拟测试

## 后续改进建议

1. **实现 enhanced.odaily topic 发布**：将增强后的数据发布到新的 topic
2. **对接 UnderstandingHub**：使用完整的理解引擎进行 LLM 增强
3. **添加 WebSocket 推送**：将增强后的事件推送到前端
4. **添加指标监控**：监控 Odaily 数据采集和消费的运行指标

## 架构原则

- **单一职责**：采集层只负责采集，理解层只负责理解
- **解耦合**：通过 Kafka 实现服务间解耦
- **可扩展性**：新增数据源只需在采集层添加新的 Adapter
- **可观测性**：通过 Kafka topic 和日志进行监控
