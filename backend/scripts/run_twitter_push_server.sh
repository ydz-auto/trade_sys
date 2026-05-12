#!/bin/bash
# Twitter Push Notification Server 启动脚本

cd "$(dirname "$0")/.."

echo "========================================"
echo "  Twitter Push WebSocket Server"
echo "========================================"
echo ""

# 检查依赖
if ! python3 -c "import websockets" 2>/dev/null; then
    echo "❌ websockets 库未安装"
    echo "   安装: pip install websockets"
    exit 1
fi

# 启动服务器
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python3 services/data_service/twitter_push_server.py
