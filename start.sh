#!/bin/bash

# 项目综合启动脚本

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║    TradeAgent 启动脚本               ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

# 帮助信息
show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -a, --all          启动所有服务 (后端 Docker + 前端)"
    echo "  -b, --backend      仅启动后端 Docker 服务"
    echo "  -f, --frontend     仅启动前端开发服务器"
    echo "  -s, --stop         停止所有服务"
    echo "  -r, --restart      重启所有服务"
    echo "  -t, --status       查看服务状态"
    echo "  -l, --logs         查看后端日志"
    echo "  -h, --help         显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 --all           # 启动所有服务"
    echo "  $0 --backend       # 仅启动后端"
    echo "  $0 --frontend      # 仅启动前端"
    echo "  $0 --logs -f       # 查看实时日志"
}

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}错误: 缺少命令 '$1'${NC}"
        return 1
    fi
    return 0
}

# 启动后端 Docker 服务
start_backend() {
    echo -e "${BLUE}正在启动后端服务...${NC}"
    cd "$SCRIPT_DIR/backend/deploy"
    ./start.sh start
}

# 启动前端
start_frontend() {
    echo -e "${BLUE}正在启动前端服务...${NC}"
    cd "$SCRIPT_DIR/frontend"

    # 检查 node_modules
    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}正在安装前端依赖...${NC}"
        npm install
    fi

    echo -e "${GREEN}正在启动前端开发服务器...${NC}"
    npm run dev
}

# 停止所有服务
stop_all() {
    echo -e "${YELLOW}正在停止所有服务...${NC}"

    # 停止前端
    pkill -f "vite|node.*frontend" 2>/dev/null

    # 停止后端
    cd "$SCRIPT_DIR/backend/deploy"
    ./start.sh stop

    echo -e "${GREEN}所有服务已停止${NC}"
}

# 重启所有服务
restart_all() {
    echo -e "${YELLOW}正在重启所有服务...${NC}"
    stop_all
    sleep 2
    start_backend
}

# 查看状态
show_status() {
    echo -e "${BLUE}查看服务状态:${NC}"
    echo ""

    echo -e "${YELLOW}前端服务:${NC}"
    if pgrep -f "vite" > /dev/null; then
        echo -e "${GREEN}✓ 前端服务运行中${NC}"
    else
        echo -e "${RED}✗ 前端服务未运行${NC}"
    fi
    echo ""

    echo -e "${YELLOW}后端服务 (Docker):${NC}"
    cd "$SCRIPT_DIR/backend/deploy"
    ./start.sh status
}

# 查看日志
show_logs() {
    cd "$SCRIPT_DIR/backend/deploy"
    shift
    ./start.sh logs "$@"
}

# 主逻辑
case "${1:-help}" in
    -a|--all)
        start_backend
        start_frontend
        ;;
    -b|--backend)
        start_backend
        ;;
    -f|--frontend)
        start_frontend
        ;;
    -s|--stop)
        stop_all
        ;;
    -r|--restart)
        restart_all
        ;;
    -t|--status)
        show_status
        ;;
    -l|--logs)
        shift
        show_logs "$@"
        ;;
    -h|--help)
        show_help
        ;;
    *)
        echo -e "${RED}错误: 未知选项 '$1'${NC}"
        show_help
        exit 1
        ;;
esac
