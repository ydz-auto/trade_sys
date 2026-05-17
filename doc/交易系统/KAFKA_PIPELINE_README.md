# TradeAgent Kafka Pipeline - Quick Start

## 前提条件

1. **Kafka 运行中** (localhost:9092)
2. **Python 环境** (backend 目录)

## 启动方式

### 方式 1: 一键脚本（需要 Kafka 在 Docker）

```bash
cd backend
bash run_pipeline.sh
```

### 方式 2: 手动启动（推荐调试用）

打开 **4 个终端**，分别运行：

```bash
# Terminal 1: fusion_service
cd backend
python -m services.fusion_service.main_kafka

# Terminal 2: strategy_service
cd backend
python -m services.strategy_service.main_kafka

# Terminal 3: event_service
cd backend
python -m services.event_service.main_kafka

# Terminal 4: data_service (触发数据)
cd backend
python -m services.data_service.main_kafka
```

## 期望输出

当 data_service 发送数据后，你应该看到：

```
[event_service] Detected: etf_inflow -> BTC (bullish)
[fusion_service] Buffer size: 1
[fusion_service] Final: BTC_BULLISH confidence=0.512

🎯 FINAL TRADING DECISION
  Symbol:     BTC
  Signal:     BTC_BULLISH
  ✅ ACTION:   LONG
  📊 POSITION: 0.41
```

## 停止

所有服务会自动停止。如果需要手动停止：

```bash
pkill -f "services\..*_service\.main_kafka"
```
