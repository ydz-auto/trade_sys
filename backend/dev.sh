#!/usr/bin/env zsh
# 统一开发服务管理脚本 - Runtime 架构版本
# 使用方法: ./dev.sh [命令] [runtime名]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

declare -A RUNTIMES=(
    ["ingestion"]="runtime.ingestion_runtime"
    ["signal"]="runtime.signal_runtime"
    ["execution"]="runtime.execution_runtime"
    ["projection"]="runtime.projection_runtime"
    ["correlation"]="runtime.correlation_runtime"
    ["narrative"]="runtime.narrative_runtime"
    ["monitoring"]="runtime.monitoring_runtime"
    ["scheduler"]="runtime.scheduler_runtime"
    ["governor"]="runtime.governor_runtime"
)

declare -A RUNTIME_NAMES=(
    ["ingestion"]="数据采集运行时"
    ["signal"]="信号生成运行时"
    ["execution"]="订单执行运行时"
    ["projection"]="CQRS投影运行时"
    ["correlation"]="相关性分析运行时"
    ["narrative"]="AI叙事运行时"
    ["monitoring"]="监控运行时"
    ["scheduler"]="调度运行时"
    ["governor"]="Runtime Governor"
)

LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"

print_header() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║         TradeAgent - Runtime 开发服务管理器                   ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

show_help() {
    print_header
    echo "用法: $0 [命令] [选项]"
    echo ""
    echo -e "${YELLOW}Runtime 管理命令:${NC}"
    echo "  start <runtime>    启动指定 runtime"
    echo "  stop <runtime>     停止指定 runtime"
    echo "  status [runtime]   查看 runtime 状态"
    echo "  logs <runtime>     查看 runtime 日志"
    echo ""
    echo -e "${YELLOW}批量操作:${NC}"
    echo "  start-all          启动所有 runtime"
    echo "  stop-all           停止所有 runtime"
    echo ""
    echo -e "${YELLOW}基础设施:${NC}"
    echo "  infra-up           启动基础设施 (Kafka KRaft, Redis)"
    echo "  infra-down         停止基础设施"
    echo "  infra-status       查看基础设施状态"
    echo "  fix-kafka          重置 Kafka (删除所有数据)"
    echo ""
    echo -e "${YELLOW}其他:${NC}"
    echo "  api                启动 API 服务器"
    echo "  list               列出所有 runtime"
    echo "  menu               显示交互式菜单"
    echo "  help               显示此帮助信息"
    echo ""
    echo -e "${CYAN}可用 Runtime:${NC}"
    for key in ${(k)RUNTIMES[@]}; do
        printf "  %-12s %s\n" "$key" "${RUNTIME_NAMES[$key]}"
    done
    echo ""
    echo "示例:"
    echo "  $0 infra-up        # 先启动基础设施"
    echo "  $0 start ingestion # 启动数据采集 runtime"
    echo "  $0 start-all       # 启动所有 runtime"
}

list_runtimes() {
    echo -e "${CYAN}可用 Runtime 列表:${NC}"
    echo ""
    for key in ${(k)RUNTIMES[@]}; do
        local runtime_status="停止"
        if pgrep -f "python.*${RUNTIMES[$key]}" > /dev/null; then
            runtime_status="${GREEN}运行中${NC}"
        else
            runtime_status="${RED}停止${NC}"
        fi
        printf "  %-12s %-20s %s\n" "$key" "${RUNTIME_NAMES[$key]}" "$runtime_status"
    done
}

start_runtime() {
    local runtime=$1
    if [ -z "$runtime" ]; then
        echo -e "${RED}错误: 请指定 runtime 名${NC}"
        echo "使用 '$0 list' 查看可用 runtime"
        return 1
    fi

    if [ -z "${RUNTIMES[$runtime]}" ]; then
        echo -e "${RED}错误: 未知 runtime '$runtime'${NC}"
        echo "使用 '$0 list' 查看可用 runtime"
        return 1
    fi

    local runtime_path="${RUNTIMES[$runtime]}"
    local runtime_name="${RUNTIME_NAMES[$runtime]}"
    local log_file="$LOG_DIR/${runtime}.log"

    if pgrep -f "python.*$runtime_path" > /dev/null; then
        echo -e "${YELLOW}$runtime_name 已在运行${NC}"
        return 0
    fi

    echo -e "${GREEN}正在启动 $runtime_name...${NC}"
    export RUNTIME_NAME="$runtime"
    export LOG_DIR="$LOG_DIR"
    nohup python -m "$runtime_path" > "$log_file" 2>&1 &
    local pid=$!
    sleep 1

    if ps -p $pid > /dev/null; then
        echo -e "${GREEN}✓ $runtime_name 启动成功 (PID: $pid)${NC}"
        echo "  日志文件: $log_file"
    else
        echo -e "${RED}✗ $runtime_name 启动失败${NC}"
        echo "  查看日志: tail -f $log_file"
        return 1
    fi
}

stop_runtime() {
    local runtime=$1
    if [ -z "$runtime" ]; then
        echo -e "${RED}错误: 请指定 runtime 名${NC}"
        return 1
    fi

    if [ -z "${RUNTIMES[$runtime]}" ]; then
        echo -e "${RED}错误: 未知 runtime '$runtime'${NC}"
        return 1
    fi

    local runtime_path="${RUNTIMES[$runtime]}"
    local runtime_name="${RUNTIME_NAMES[$runtime]}"

    if ! pgrep -f "python.*$runtime_path" > /dev/null; then
        echo -e "${YELLOW}$runtime_name 未运行${NC}"
        return 0
    fi

    echo -e "${YELLOW}正在停止 $runtime_name...${NC}"
    pkill -f "python.*$runtime_path"
    sleep 1

    if pgrep -f "python.*$runtime_path" > /dev/null; then
        echo -e "${RED}✗ $runtime_name 停止失败${NC}"
        return 1
    else
        echo -e "${GREEN}✓ $runtime_name 已停止${NC}"
    fi
}

show_status() {
    local runtime=$1
    
    if [ -n "$runtime" ]; then
        if [ -z "${RUNTIMES[$runtime]}" ]; then
            echo -e "${RED}错误: 未知 runtime '$runtime'${NC}"
            return 1
        fi
        
        local runtime_path="${RUNTIMES[$runtime]}"
        local runtime_name="${RUNTIME_NAMES[$runtime]}"
        
        echo -e "${CYAN}$runtime_name 状态:${NC}"
        if pgrep -f "python.*$runtime_path" > /dev/null; then
            echo -e "  状态: ${GREEN}运行中${NC}"
            pgrep -f "python.*$runtime_path" | while read pid; do
                echo "  PID: $pid"
            done
        else
            echo -e "  状态: ${RED}停止${NC}"
        fi
        
        local log_file="$LOG_DIR/${runtime}.log"
        if [ -f "$log_file" ]; then
            echo "  日志: $log_file"
            echo "  最后10行:"
            tail -n 10 "$log_file" | sed 's/^/    /'
        fi
    else
        echo -e "${CYAN}所有 Runtime 状态:${NC}"
        echo ""
        for key in ${(k)RUNTIMES[@]}; do
            local status_icon="✗"
            local status_color="$RED"
            if pgrep -f "python.*${RUNTIMES[$key]}" > /dev/null; then
                status_icon="✓"
                status_color="$GREEN"
            fi
            echo -e "  ${status_color}$status_icon${NC} ${RUNTIME_NAMES[$key]}"
        done
    fi
}

show_logs() {
    local runtime=$1
    if [ -z "$runtime" ]; then
        echo -e "${RED}错误: 请指定 runtime 名${NC}"
        return 1
    fi

    if [ -z "${RUNTIMES[$runtime]}" ]; then
        echo -e "${RED}错误: 未知 runtime '$runtime'${NC}"
        return 1
    fi

    local log_file="$LOG_DIR/${runtime}.log"
    if [ ! -f "$log_file" ]; then
        echo -e "${YELLOW}日志文件不存在: $log_file${NC}"
        return 1
    fi

    echo -e "${CYAN}查看 ${RUNTIME_NAMES[$runtime]} 日志 (Ctrl+C 退出):${NC}"
    tail -f "$log_file"
}

start_all() {
    echo -e "${GREEN}正在启动所有 Runtime...${NC}"
    echo ""
    
    for runtime in ${(k)RUNTIMES[@]}; do
        start_runtime "$runtime"
        echo ""
    done
    
    echo -e "${GREEN}所有 Runtime 已启动${NC}"
}

stop_all() {
    echo -e "${YELLOW}正在停止所有 Runtime...${NC}"
    
    for runtime in ${(k)RUNTIMES[@]}; do
        pkill -9 -f "python.*${RUNTIMES[$runtime]}" 2>/dev/null
    done
    
    sleep 1
    echo -e "${GREEN}所有 Runtime 已停止${NC}"
}

infra_up() {
    echo -e "${GREEN}正在启动基础设施 (KRaft 模式)...${NC}"
    cd "$SCRIPT_DIR/deploy"
    
    echo -e "${CYAN}步骤 1/2: 启动所有基础设施...${NC}"
    docker compose up -d kafka redis
    
    echo -e "${CYAN}步骤 2/2: 等待服务就绪...${NC}"
    local max_wait=30
    local waited=0
    local kafka_healthy=0
    local redis_running=0
    
    while [ $waited -lt $max_wait ]; do
        if [ $kafka_healthy -eq 0 ]; then
            local kafka_health=$(docker inspect --format='{{.State.Health.Status}}' kafka 2>/dev/null || echo "unknown")
            if [ "$kafka_health" = "healthy" ]; then
                kafka_healthy=1
                echo -e "${GREEN}✓ Kafka (KRaft) 已就绪${NC}"
            fi
        fi
        
        if [ $redis_running -eq 0 ]; then
            local redis_status=$(docker inspect --format='{{.State.Status}}' redis 2>/dev/null || echo "unknown")
            if [ "$redis_status" = "running" ]; then
                redis_running=1
                echo -e "${GREEN}✓ Redis 已就绪${NC}"
            fi
        fi
        
        if [ $kafka_healthy -eq 1 ] && [ $redis_running -eq 1 ]; then
            break
        fi
        
        echo -e "${YELLOW}等待服务就绪... ($waited/$max_wait)${NC}"
        sleep 2
        waited=$((waited + 2))
    done
    
    echo -e "${CYAN}启动 Kafka UI...${NC}"
    docker compose up -d kafka-ui
    
    echo ""
    echo -e "${GREEN}基础设施已启动 (KRaft 模式):${NC}"
    echo "  Kafka: localhost:9092"
    echo "  Redis: localhost:6379"
    echo "  Kafka UI: http://localhost:8080"
}

fix_kafka_dev() {
    echo -e "${RED}===========================================${NC}"
    echo -e "${RED}⚠ 这将删除所有 Kafka 数据！${NC}"
    echo -e "${RED}===========================================${NC}"
    echo ""
    read -p "确定要继续吗? (type 'YES' to confirm): " confirm
    if [ "$confirm" != "YES" ]; then
        echo "已取消"
        return 1
    fi
    
    cd "$SCRIPT_DIR/deploy"
    echo -e "${YELLOW}正在停止并删除数据卷...${NC}"
    docker compose down -v
    sleep 2
    echo -e "${YELLOW}正在重新启动 KRaft 集群...${NC}"
    docker compose up -d kafka redis kafka-ui
    echo -e "${GREEN}已重置 Kafka (KRaft 模式)${NC}"
}

infra_down() {
    echo -e "${YELLOW}正在停止基础设施...${NC}"
    cd "$SCRIPT_DIR/deploy"
    docker compose down
    echo -e "${GREEN}基础设施已停止${NC}"
}

infra_status() {
    echo -e "${CYAN}基础设施状态 (KRaft 模式):${NC}"
    cd "$SCRIPT_DIR/deploy"
    docker compose ps kafka redis 2>/dev/null || echo "  未启动"
}

start_api() {
    echo -e "${GREEN}正在启动 API 服务器...${NC}"
    echo -e "${BLUE}访问地址: http://localhost:8001${NC}"
    echo -e "${YELLOW}按 Ctrl+C 停止${NC}"
    echo ""
    python api_server.py
}

show_menu() {
    while true; do
        print_header
        echo "请选择操作:"
        echo ""
        echo "  1) 启动基础设施 (Kafka KRaft, Redis)"
        echo "  2) 停止基础设施"
        echo "  3) 重置 Kafka (删除所有数据)"
        echo "  4) 启动所有 Runtime"
        echo "  5) 停止所有 Runtime"
        echo "  6) 查看 Runtime 状态"
        echo "  7) 启动 API 服务器"
        echo "  8) 查看 Runtime 日志"
        echo "  0) 退出"
        echo ""
        
        read -rp "请输入选项: " choice
        
        case "$choice" in
            1)
                infra_up
                ;;
            2)
                infra_down
                ;;
            3)
                fix_kafka_dev
                ;;
            4)
                start_all
                ;;
            5)
                stop_all
                ;;
            6)
                show_status
                ;;
            7)
                start_api
                ;;
            8)
                list_runtimes
                read -rp "输入 runtime 名: " runtime_name
                show_logs "$runtime_name"
                ;;
            0)
                echo -e "${GREEN}再见！${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}无效选项: $choice${NC}"
                ;;
        esac
        
        echo ""
        read -rp "按 Enter 继续..."
        echo ""
    done
}

if ! command -v python &> /dev/null; then
    if command -v python3 &> /dev/null; then
        alias python=python3
    else
        echo -e "${RED}错误: 未找到 Python${NC}"
        exit 1
    fi
fi

case "${1:-menu}" in
    start)
        start_runtime "$2"
        ;;
    stop)
        stop_runtime "$2"
        ;;
    status)
        show_status "$2"
        ;;
    logs)
        show_logs "$2"
        ;;
    start-all)
        start_all
        ;;
    stop-all)
        stop_all
        ;;
    infra-up)
        infra_up
        ;;
    infra-down)
        infra_down
        ;;
    infra-status)
        infra_status
        ;;
    fix-kafka)
        fix_kafka_dev
        ;;
    api)
        start_api
        ;;
    list)
        list_runtimes
        ;;
    menu)
        show_menu
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
