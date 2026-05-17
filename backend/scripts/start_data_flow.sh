#!/bin/bash
# 启动数据流处理器

cd "$(dirname "$0")/.."

echo "=== 启动数据流处理器 ==="
echo "这个脚本会从Kafka读取真实数据并写入Redis"
echo ""

# 检查Kafka是否有数据
echo "检查Kafka状态..."
MESSAGE_COUNT=$(docker exec kafka kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic tradeagent.events --time -1 2>/dev/null | awk -F: '{print $3}')

if [ -z "$MESSAGE_COUNT" ] || [ "$MESSAGE_COUNT" -eq 0 ]; then
    echo "❌ Kafka中没有消息"
    echo "请先启动Ingestion Runtime采集数据"
    exit 1
fi

echo "✅ Kafka中有 $MESSAGE_COUNT 条消息"
echo ""

# 运行处理器
echo "启动数据流处理器..."
python3 scripts/data_flow_processor.py
