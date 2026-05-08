#!/bin/bash
# Kafka Pipeline Startup Script
# Usage: bash run_pipeline.sh

set -e

echo "============================================"
echo "TradeAgent Kafka Pipeline"
echo "============================================"
echo ""

# Check if Kafka is running
echo "[1/4] Checking Kafka..."
if ! nc -z localhost 9092 2>/dev/null; then
    echo "❌ Kafka not running on localhost:9092"
    echo "   Please start Kafka first:"
    echo "   - Docker: docker-compose up -d kafka"
    echo "   - Local: kafka-server-start.sh config/server.properties"
    exit 1
fi
echo "✅ Kafka is running"

# Create topics
echo ""
echo "[2/4] Creating topics..."
docker exec kafka kafka-topics --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --replication-factor 1 \
    --partitions 3 \
    --topic tradeagent.raw_data 2>/dev/null || echo "   Topic tradeagent.raw_data exists"

docker exec kafka kafka-topics --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --replication-factor 1 \
    --partitions 3 \
    --topic tradeagent.events 2>/dev/null || echo "   Topic tradeagent.events exists"

docker exec kafka kafka-topics --create --if-not-exists \
    --bootstrap-server localhost:9092 \
    --replication-factor 1 \
    --partitions 3 \
    --topic tradeagent.signals 2>/dev/null || echo "   Topic tradeagent.signals exists"

echo "✅ Topics created"

# Get backend directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR"

echo ""
echo "[3/4] Starting services..."
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "[CLEANUP] Stopping services..."
    jobs -p | xargs kill 2>/dev/null || true
}

trap cleanup EXIT

# Start services in background
echo "   Starting fusion_service..."
python -m services.fusion_service.main_kafka &
sleep 1

echo "   Starting strategy_service..."
python -m services.strategy_service.main_kafka &
sleep 1

echo "   Starting event_service..."
python -m services.event_service.main_kafka &
sleep 1

echo "   Starting data_service (producer)..."
python -m services.data_service.main_kafka &
sleep 1

echo ""
echo "[4/4] Pipeline running..."
echo "   Press Ctrl+C to stop"
echo "============================================"

# Wait for any process to exit
wait
