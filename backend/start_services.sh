#!/bin/bash
# 服务启动脚本
# 使用方法:
#   ./start_services.sh - 启动所有服务（后台）
#   ./start_services.sh -p - 仅监控面板
#   ./start_services.sh -h - 显示帮助

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

cd "$BACKEND_DIR" || exit 1

print_header() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════════╗"
    echo "║                    交易系统 - 服务启动器                       ║"
    echo "╚═══════════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -m, --monitor    仅启动监控面板（前台）"
    echo "  -s, --simulate   运行完整模拟"
    echo "  -v, --verify     运行系统验证"
    echo "  -h, --help       显示帮助"
    echo ""
    echo "示例:"
    echo "  $0                    # 显示菜单"
    echo "  $0 -m                # 启动监控面板"
    echo "  $0 -s                # 运行模拟"
}

print_menu() {
    print_header
    echo "请选择要执行的操作:"
    echo ""
    echo "  1) 运行完整验证"
    echo "  2) 运行完整模拟"
    echo "  3) 启动监控面板"
    echo "  4) 查看快速开始指南"
    echo "  5) 查看架构文档"
    echo "  0) 退出"
    echo ""
}

run_verify() {
    echo -e "${GREEN}正在运行系统验证...${NC}"
    echo ""
    python -m scripts.verify_all
}

run_simulation() {
    echo -e "${GREEN}正在运行完整模拟...${NC}"
    echo ""
    python -m scripts.simulate_pipeline
}

start_monitoring() {
    echo -e "${GREEN}正在启动监控面板...${NC}"
    echo -e "${BLUE}请在浏览器中打开: http://localhost:8000${NC}"
    echo -e "${YELLOW}按 Ctrl+C 停止服务器${NC}"
    echo ""
    python -m services.monitoring.monitoring_panel
}

view_quickstart() {
    if [ -f "$BACKEND_DIR/QUICKSTART.md" ]; then
        if command -v less &> /dev/null; then
            less "$BACKEND_DIR/QUICKSTART.md"
        else
            cat "$BACKEND_DIR/QUICKSTART.md"
        fi
    else
        echo -e "${RED}错误: QUICKSTART.md 文件不存在${NC}"
    fi
}

view_architecture() {
    if [ -f "$BACKEND_DIR/docs/ARCHITECTURE_COMPLETION.md" ]; then
        if command -v less &> /dev/null; then
            less "$BACKEND_DIR/docs/ARCHITECTURE_COMPLETION.md"
        else
            cat "$BACKEND_DIR/docs/ARCHITECTURE_COMPLETION.md"
        fi
    else
        echo -e "${RED}错误: 架构文档不存在${NC}"
    fi
}

# 检查 Python
if ! command -v python &> /dev/null; then
    if command -v python3 &> /dev/null; then
        alias python=python3
    else
        echo -e "${RED}错误: 未找到 Python${NC}"
        exit 1
    fi
fi

# 检查是否在正确目录
if [ ! -f "$BACKEND_DIR/QUICKSTART.md" ]; then
    echo -e "${YELLOW}警告: 当前目录可能不正确${NC}"
    echo "当前目录: $(pwd)"
    echo ""
fi

# 解析参数
if [ $# -gt 0 ]; then
    case "$1" in
        -m|--monitor)
            start_monitoring
            exit 0
            ;;
        -s|--simulate)
            run_simulation
            exit 0
            ;;
        -v|--verify)
            run_verify
            exit 0
            ;;
        -h|--help)
            print_help
            exit 0
            ;;
        *)
            echo -e "${RED}未知选项: $1${NC}"
            print_help
            exit 1
            ;;
    esac
fi

# 菜单模式
while true; do
    print_menu
    read -rp "请输入选项: " choice

    case "$choice" in
        1)
            run_verify
            ;;
        2)
            run_simulation
            ;;
        3)
            start_monitoring
            ;;
        4)
            view_quickstart
            ;;
        5)
            view_architecture
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
