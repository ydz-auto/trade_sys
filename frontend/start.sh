#!/bin/bash

# 前端启动脚本

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}  启动前端开发服务器${NC}"
echo -e "${GREEN}================================${NC}"

# 检查是否在正确目录
if [ ! -f "package.json" ]; then
    echo -e "${RED}错误: 未找到 package.json，请确保在 frontend 目录下${NC}"
    exit 1
fi

# 检查 node_modules
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}正在安装依赖...${NC}"
    npm install
fi

# 启动开发服务器
echo -e "${GREEN}正在启动开发服务器...${NC}"
npm run dev
