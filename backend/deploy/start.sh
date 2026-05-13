#!/bin/bash

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  后端服务 Docker 部署脚本${NC}"
echo -e "${GREEN}================================${NC}"

# 脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# 帮助信息
show_help() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  start     启动所有服务"
    echo "  stop      停止所有服务"
    echo "  restart   重启所有服务"
    echo "  status    查看服务状态"
    echo "  logs      查看服务日志"
    echo "  clean     清理所有容器和数据"
    echo "  help      显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start     # 启动服务"
    echo "  $0 logs -f   # 实时查看日志"
}

# 检查 Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}错误: 未安装 Docker${NC}"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        echo -e "${RED}错误: 未安装 Docker Compose${NC}"
        exit 1
    fi
}

# Docker Compose 命令
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# 启动服务
start_services() {
    echo -e "${BLUE}正在启动服务...${NC}"

    # 构建并启动所有服务
    $DOCKER_COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" up -d --build

    echo -e "${YELLOW}等待服务启动...${NC}"
    sleep 5

    # 检查服务状态
    $DOCKER_COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" ps

    echo ""
    echo -e "${GREEN}================================${NC}"
    echo -e "${GREEN}  服务启动成功！${NC}"
    echo -e "${GREEN}================================${NC}"
    echo ""
    echo "API 服务器: http://localhost:8001"
    echo "Kafka UI:   http://localhost:8080"
    echo "Redis:      localhost:6379"
    echo ""
    echo "查看日志: $0 logs"
    echo "停止服务: $0 stop"
}

# 停止服务
stop_services() {
    echo -e "${YELLOW}正在停止服务...${NC}"
    $DOCKER_COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" down
    echo -e "${GREEN}所有服务已停止${NC}"
}

# 查看状态
status_services() {
    $DOCKER_COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" ps
}

# 查看日志
logs_services() {
    $DOCKER_COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" logs "$@"
}

# 清理
clean_services() {
    echo -e "${RED}警告: 将删除所有容器和数据卷！${NC}"
    read -p "确定要继续吗? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        $DOCKER_COMPOSE -f "$SCRIPT_DIR/docker-compose.yml" down -v
        echo -e "${GREEN}所有容器和数据卷已清理${NC}"
    else
        echo "取消清理操作"
    fi
}

# 主逻辑
check_docker

case "${1:-start}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        stop_services
        sleep 2
        start_services
        ;;
    status)
        status_services
        ;;
    logs)
        shift
        logs_services "$@"
        ;;
    clean)
        clean_services
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}错误: 未知命令 '$1'${NC}"
        show_help
        exit 1
        ;;
esac
