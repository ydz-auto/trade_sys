#!/usr/bin/env zsh

# 项目综合启动脚本
# 统一入口，调用各模块的启动脚本

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="${0:a:h}"

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║      TradeAgent 统一启动入口         ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

show_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -d, --dev          启动后端开发服务 (Python直接运行)"
    echo "  -m, --mixed        启动混合模式 (基础设施Docker + Runtime Python)"
    echo "  -b, --backend      启动后端 Docker 服务"
    echo "  -f, --frontend     启动前端开发服务器"
    echo "  -a, --all          启动所有服务 (后端Docker + 前端)"
    echo "  -r, --replay       启动回放引擎 (需要指定时间范围)"
    echo "  --gpu              启动 GPU 加速服务"
    echo "  --gpu-status       查看 GPU 状态"
    echo "  -s, --stop         停止所有服务"
    echo "  -t, --status       查看服务状态"
    echo "  -l, --logs         查看后端日志"
    echo "  -h, --help         显示帮助信息"
    echo ""
    echo "回放引擎参数 (通过环境变量或命令行):"
    echo "  REPLAY_START_TIME  回放开始时间 (ISO格式，如: 2026-01-01T00:00:00)"
    echo "  REPLAY_END_TIME    回放结束时间 (ISO格式，如: 2026-01-02T00:00:00)"
    echo "  REPLAY_MODE        回放模式 (realtime/fast/step/deterministic，默认: fast)"
    echo "  REPLAY_SYMBOLS     交易对列表 (逗号分隔，默认: BTCUSDT)"
    echo ""
    echo "示例:"
    echo "  $0 --dev                      # 启动后端开发服务"
    echo "  $0 --mixed                    # 启动混合模式 (推荐开发使用)"
    echo "  $0 --backend                  # 启动后端Docker"
    echo "  $0 --frontend                 # 启动前端"
    echo "  $0 --all                      # 启动所有服务"
    echo "  $0 --replay                   # 交互式启动回放引擎"
    echo "  REPLAY_START_TIME=2026-01-01T00:00:00 REPLAY_END_TIME=2026-01-02T00:00:00 $0 --replay"
    echo "  $0 --logs -f                  # 查看实时日志"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}错误: 缺少命令 '$1'${NC}"
        return 1
    fi
    return 0
}

start_dev() {
    echo -e "${BLUE}正在启动后端开发服务...${NC}"
    cd "$SCRIPT_DIR/backend"
    ./dev.sh menu
}

start_mixed() {
    echo -e "${BLUE}正在启动混合模式...${NC}"
    echo ""
    echo -e "${CYAN}混合模式说明:${NC}"
    echo "  - 基础设施 (Kafka, Redis, Zookeeper) 运行在 Docker 中"
    echo "  - Python Runtime 直接运行 (方便调试)"
    echo "  - API Server (FastAPI)"
    echo "  - 前端开发服务器 (Vite)"
    echo ""
    
    cd "$SCRIPT_DIR/backend"
    
    echo -e "${YELLOW}步骤 1/4: 启动基础设施...${NC}"
    ./dev.sh infra-up
    echo ""
    
    echo -e "${YELLOW}步骤 2/4: 启动所有 Runtime (Python直接运行)...${NC}"
    ./dev.sh start-all
    echo ""
    
    echo -e "${YELLOW}步骤 3/4: 启动 API Server...${NC}"
    nohup python api_server.py > "$SCRIPT_DIR/backend/logs/api_server.log" 2>&1 &
    sleep 3
    if pgrep -f "api_server.py" > /dev/null; then
        echo -e "${GREEN}✓ API Server 已启动${NC}"
    else
        echo -e "${RED}✗ API Server 启动失败${NC}"
    fi
    echo ""
    
    echo -e "${YELLOW}步骤 4/4: 启动前端开发服务器...${NC}"
    cd "$SCRIPT_DIR/frontend"
    if [ ! -d "node_modules" ]; then
        echo -e "${CYAN}正在安装前端依赖...${NC}"
        npm install
    fi
    nohup npm run dev > "$SCRIPT_DIR/backend/logs/frontend.log" 2>&1 &
    sleep 3
    echo -e "${GREEN}✓ 前端已启动${NC}"
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║      混合模式启动完成                 ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${CYAN}服务地址:${NC}"
    echo "  前端:       http://localhost:3000"
    echo "  Kafka:      localhost:9092"
    echo "  Redis:      localhost:6379"
    echo "  Kafka UI:   http://localhost:8080"
    echo "  API Server: http://localhost:8001"
    echo "  API Docs:   http://localhost:8001/docs"
    echo ""
    echo -e "${YELLOW}管理命令:${NC}"
    echo "  查看状态:    $0 --status"
    echo "  查看日志:    $0 --logs dev"
    echo "  停止服务:    $0 --stop"
}

start_backend_docker() {
    echo -e "${BLUE}正在启动后端Docker服务...${NC}"
    cd "$SCRIPT_DIR/backend/deploy"
    ./start.sh start
}

start_frontend() {
    echo -e "${BLUE}正在启动前端服务...${NC}"
    cd "$SCRIPT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        echo -e "${YELLOW}正在安装前端依赖...${NC}"
        npm install
    fi

    echo -e "${GREEN}正在启动前端开发服务器...${NC}"
    npm run dev
}

start_replay() {
    echo -e "${BLUE}正在启动回放引擎...${NC}"
    echo ""
    
    if [ -z "$REPLAY_START_TIME" ]; then
        echo -e "${YELLOW}请输入回放开始时间 (ISO格式，如: 2026-01-01T00:00:00):${NC}"
        read -r REPLAY_START_TIME
        export REPLAY_START_TIME
    fi
    
    if [ -z "$REPLAY_END_TIME" ]; then
        echo -e "${YELLOW}请输入回放结束时间 (ISO格式，如: 2026-01-02T00:00:00):${NC}"
        read -r REPLAY_END_TIME
        export REPLAY_END_TIME
    fi
    
    if [ -z "$REPLAY_START_TIME" ] || [ -z "$REPLAY_END_TIME" ]; then
        echo -e "${RED}错误: 必须指定 REPLAY_START_TIME 和 REPLAY_END_TIME${NC}"
        exit 1
    fi
    
    export REPLAY_MODE="${REPLAY_MODE:-fast}"
    export REPLAY_SYMBOLS="${REPLAY_SYMBOLS:-BTCUSDT}"
    
    echo ""
    echo -e "${CYAN}回放配置:${NC}"
    echo "  开始时间: $REPLAY_START_TIME"
    echo "  结束时间: $REPLAY_END_TIME"
    echo "  回放模式: $REPLAY_MODE"
    echo "  交易对:   $REPLAY_SYMBOLS"
    echo ""
    
    cd "$SCRIPT_DIR/backend"
    ./dev.sh start replay
}

start_gpu() {
    echo -e "${BLUE}正在启动 GPU 加速服务...${NC}"
    echo ""
    
    cd "$SCRIPT_DIR/backend"
    
    echo -e "${CYAN}GPU 加速服务:${NC}"
    echo "  - GPU Signal Runtime (LSTM 策略)"
    echo "  - GPU Optimization Service (参数优化)"
    echo ""
    
    ./dev.sh gpu-status
    echo ""
    
    echo -e "${YELLOW}启动 GPU Signal Runtime...${NC}"
    ./dev.sh gpu-start gpu-signal
    
    echo ""
    echo -e "${YELLOW}启动 GPU Optimization Service...${NC}"
    ./dev.sh gpu-start gpu-optimization
    
    echo ""
    echo -e "${GREEN}GPU 服务已启动${NC}"
    echo "  日志目录: $SCRIPT_DIR/backend/logs/"
}

show_gpu_status() {
    echo -e "${BLUE}GPU 加速状态:${NC}"
    echo ""
    
    cd "$SCRIPT_DIR/backend"
    ./dev.sh gpu-status
}

stop_all() {
    echo -e "${YELLOW}正在停止所有服务...${NC}"

    pkill -f "vite|node.*frontend" 2>/dev/null
    
    pkill -f "api_server.py" 2>/dev/null

    cd "$SCRIPT_DIR/backend"
    echo -e "${CYAN}停止 Python Runtime...${NC}"
    ./dev.sh stop-all

    echo -e "${CYAN}停止 Docker 基础设施...${NC}"
    ./dev.sh infra-down

    echo -e "${GREEN}所有服务已停止${NC}"
}

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

    echo -e "${YELLOW}API Server:${NC}"
    if pgrep -f "api_server.py" > /dev/null; then
        echo -e "${GREEN}✓ API Server 运行中${NC}"
        echo "  地址: http://localhost:8001"
        echo "  文档: http://localhost:8001/docs"
    else
        echo -e "${RED}✗ API Server 未运行${NC}"
    fi
    echo ""

    echo -e "${YELLOW}后端服务 (Python Runtime):${NC}"
    cd "$SCRIPT_DIR/backend"
    ./dev.sh status
    echo ""

    echo -e "${YELLOW}后端服务 (Docker):${NC}"
    cd "$SCRIPT_DIR/backend/deploy"
    ./start.sh status 2>/dev/null || echo "  未启动"
}

show_logs() {
    local mode="${1:-docker}"
    
    if [ "$mode" = "dev" ]; then
        cd "$SCRIPT_DIR/backend"
        shift
        ./dev.sh logs "$@"
    else
        cd "$SCRIPT_DIR/backend/deploy"
        shift
        ./start.sh logs "$@"
    fi
}

case "${1:-help}" in
    -d|--dev)
        start_dev
        ;;
    -m|--mixed)
        start_mixed
        ;;
    -b|--backend)
        start_backend_docker
        ;;
    -f|--frontend)
        start_frontend
        ;;
    -a|--all)
        start_backend_docker
        start_frontend
        ;;
    -r|--replay)
        start_replay
        ;;
    --gpu)
        start_gpu
        ;;
    --gpu-status)
        show_gpu_status
        ;;
    -s|--stop)
        stop_all
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
