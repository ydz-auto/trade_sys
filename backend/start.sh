#!/usr/bin/env bash
# 生产环境启动脚本 - CPU 版本
# 使用方法: ./start.sh [选项]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         TradeAgent - Production Startup (CPU)                ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

start_cpu() {
    echo -e "${GREEN}启动 CPU 版本服务...${NC}"
    cd "$SCRIPT_DIR/deploy"
    docker compose up -d
    echo ""
    echo -e "${GREEN}服务已启动:${NC}"
    echo "  API: http://localhost:8001"
    echo "  Kafka UI: http://localhost:8080"
    echo "  Grafana: http://localhost:3000 (admin/admin)"
    echo "  Prometheus: http://localhost:9090"
}

stop_all() {
    echo -e "${YELLOW}停止所有服务...${NC}"
    cd "$SCRIPT_DIR/deploy"
    docker compose down
    echo -e "${GREEN}服务已停止${NC}"
}

show_status() {
    echo -e "${CYAN}服务状态:${NC}"
    cd "$SCRIPT_DIR/deploy"
    docker compose ps
}

case "${1:-start}" in
    start)
        start_cpu
        ;;
    stop)
        stop_all
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 {start|stop|status}"
        exit 1
        ;;
esac
