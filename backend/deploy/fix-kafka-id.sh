#!/usr/bin/env bash
# =============================================================================
# Kafka 集群ID安全修复脚本
# 
# 功能：智能修复 InconsistentClusterIdException 问题
# 
# 用法:
#   ./fix-kafka-id.sh check          # 检查当前状态
#   ./fix-kafka-id.sh fix            # 修复 Kafka ID（生产推荐）
#   ./fix-kafka.sh reset-zk          # 重置 ZooKeeper（⚠️ 危险，仅开发用）
#
# 重要：
#   - 生产环境：使用 fix 命令（只修改 meta.properties）
#   - 开发环境：可以使用 reset-zk（会丢失数据）
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo -e "${CYAN}╔════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Kafka 集群ID修复工具 (安全版)    ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════╝${NC}"
echo ""

# 获取 Kafka 数据卷名称
get_kafka_volume() {
    local volume_name=""
    
    # 尝试多个可能的卷名
    for vol in deploy_kafka_data docker_kafka_data kafka_data; do
        if docker volume inspect "$vol" &>/dev/null; then
            volume_name="$vol"
            break
        fi
    done
    
    if [ -z "$volume_name" ]; then
        echo -e "${RED}✗ 无法找到 Kafka 数据卷${NC}"
        return 1
    fi
    
    echo "$volume_name"
}

# 获取 ZooKeeper 容器名
get_zk_container() {
    local container_name=""
    
    for name in zookeeper deploy_zookeeper_1; do
        if docker ps --format '{{.Names}}' | grep -q "^${name}$"; then
            container_name="$name"
            break
        fi
    done
    
    if [ -z "$container_name" ]; then
        echo -e "${RED}✗ 无法找到 ZooKeeper 容器${NC}"
        return 1
    fi
    
    echo "$container_name"
}

# 从 Kafka 日志提取期望的 Cluster ID
get_expected_cluster_id() {
    local kafka_logs=$(docker logs kafka 2>&1)
    
    # 提取日志中的 Cluster ID（格式：The Cluster ID XXX doesn't match...）
    # macOS grep 不支持 -P，使用 sed 替代
    local expected_id=$(echo "$kafka_logs" | sed -n 's/.*The Cluster ID \([^ ]*\).*/\1/p' | head -1)
    
    if [ -z "$expected_id" ]; then
        # 尝试另一种格式
        expected_id=$(echo "$kafka_logs" | sed -n 's/.*Cluster ID \([^ ]*\).*/\1/p' | grep -E '^[A-Za-z0-9_-]+$' | head -1)
    fi
    
    echo "$expected_id"
}

# 从 meta.properties 获取当前的 Cluster ID
get_current_cluster_id() {
    local kafka_volume=$(get_kafka_volume)
    if [ -z "$kafka_volume" ]; then
        return 1
    fi
    
    # 使用 kafka 容器读取文件
    local kafka_container=$(docker ps --format '{{.Names}}' | grep kafka | head -1)
    if [ -z "$kafka_container" ]; then
        kafka_container="kafka"
    fi
    
    # 尝试多个可能的路径（Kafka 官方镜像使用 /var/lib/kafka/data）
    docker exec "$kafka_container" sh -c "cat /var/lib/kafka/data/meta.properties 2>/dev/null | grep 'cluster.id' | cut -d= -f2" || \
    docker exec "$kafka_container" sh -c "cat /opt/kafka/data/meta.properties 2>/dev/null | grep 'cluster.id' | cut -d= -f2" || \
    docker exec "$kafka_container" sh -c "cat /var/lib/kafka/kraft-logs/meta.properties 2>/dev/null | grep 'cluster.id' | cut -d= -f2" || \
    echo ""
}

# 检查状态
check_status() {
    echo -e "${CYAN}检查 Kafka 集群ID状态...${NC}"
    echo ""
    
    # 检查 Kafka 是否运行
    local kafka_running=$(docker ps -q -f name=kafka)
    if [ -z "$kafka_running" ]; then
        echo -e "${YELLOW}⚠ Kafka 容器未运行${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ Kafka 容器运行中${NC}"
    
    # 获取当前 ID
    local current_id=$(get_current_cluster_id)
    echo ""
    echo -e "${CYAN}当前 meta.properties 中的 Cluster ID:${NC}"
    if [ -n "$current_id" ]; then
        echo -e "  ${YELLOW}$current_id${NC}"
    else
        echo -e "  ${RED}无法读取（文件不存在或为空）${NC}"
    fi
    
    # 获取期望的 ID
    local expected_id=$(get_expected_cluster_id)
    echo ""
    echo -e "${CYAN}Kafka 日志中期望的 Cluster ID:${NC}"
    if [ -n "$expected_id" ]; then
        echo -e "  ${YELLOW}$expected_id${NC}"
    else
        echo -e "  ${GREEN}Kafka 运行正常，无需修复${NC}"
        return 0
    fi
    
    # 比较
    echo ""
    if [ "$current_id" = "$expected_id" ]; then
        echo -e "${GREEN}✓ Cluster ID 匹配，无需修复${NC}"
    else
        echo -e "${RED}✗ Cluster ID 不匹配！${NC}"
        echo ""
        echo -e "${CYAN}修复方案:${NC}"
        echo "  当前: $current_id"
        echo "  期望: $expected_id"
        echo ""
        echo "使用以下命令修复:"
        echo -e "  ${GREEN}$0 fix${NC}"
    fi
}

# 修复 Kafka ID（推荐）
fix_kafka_id() {
    echo -e "${CYAN}修复 Kafka 集群ID...${NC}"
    echo ""
    
    # 获取 Kafka 卷名
    local kafka_volume=$(get_kafka_volume)
    if [ -z "$kafka_volume" ]; then
        echo -e "${RED}✗ 无法找到 Kafka 数据卷${NC}"
        return 1
    fi
    
    echo -e "${CYAN}使用的数据卷: $kafka_volume${NC}"
    
    # 获取期望的 ID
    local expected_id=$(get_expected_cluster_id)
    if [ -z "$expected_id" ]; then
        echo -e "${RED}✗ 无法从日志获取期望的 Cluster ID${NC}"
        echo ""
        echo "请确保 Kafka 容器正在运行并产生错误日志"
        return 1
    fi
    
    echo ""
    echo -e "${CYAN}修复步骤:${NC}"
    echo "  1. 停止 Kafka 容器"
    echo "  2. 修改 meta.properties 中的 cluster.id"
    echo "  3. 重启 Kafka 容器"
    echo ""
    echo -e "${CYAN}新 Cluster ID: $expected_id${NC}"
    echo ""
    
    # 确认操作
    read -p "确认修复? (y/N): " confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        echo "已取消"
        return 1
    fi
    
    # 步骤1: 停止 Kafka
    echo ""
    echo -e "${YELLOW}步骤 1/3: 停止 Kafka...${NC}"
    docker stop kafka 2>/dev/null || true
    
    # 步骤2: 修改 meta.properties
    echo -e "${YELLOW}步骤 2/3: 修改 meta.properties...${NC}"
    
    # 使用临时容器修改文件（因为 Kafka 容器已停止）
    echo "备份并更新 meta.properties..."
    
    local result=$(docker run --rm -v ${kafka_volume}:/data confluentinc/cp-kafka:7.5.0 bash -c "
        # 查找 meta.properties 文件
        if [ -f /data/meta.properties ]; then
            META_PATH=/data/meta.properties
        else
            echo 'ERROR: meta.properties not found'
            exit 1
        fi
        
        # 备份
        cp \"\$META_PATH\" \"\${META_PATH}.bak\" 2>/dev/null || true
        
        # 写入新的 cluster.id
        echo 'version=0' > \"\$META_PATH\"
        echo 'cluster.id=${expected_id}' >> \"\$META_PATH\"
        
        # 验证
        echo 'SUCCESS'
        cat \"\$META_PATH\"
    " 2>&1)
    
    if echo "$result" | grep -q "SUCCESS"; then
        echo -e "${GREEN}✓ 已更新 cluster.id${NC}"
        echo ""
        echo "新内容:"
        echo "$result" | grep -A2 "SUCCESS" | tail -2
    else
        echo -e "${RED}✗ 修改失败: $result${NC}"
        return 1
    fi
    
    # 步骤3: 重启 Kafka
    echo ""
    echo -e "${YELLOW}步骤 3/3: 重启 Kafka...${NC}"
    docker start kafka
    
    # 等待 Kafka 启动
    echo ""
    echo -e "${CYAN}等待 Kafka 启动...${NC}"
    local max_wait=30
    local waited=0
    while [ $waited -lt $max_wait ]; do
        local kafka_health=$(docker inspect --format='{{.State.Health.Status}}' kafka 2>/dev/null || echo "unknown")
        if [ "$kafka_health" = "healthy" ]; then
            break
        fi
        echo -e "${YELLOW}等待... ($waited/$max_wait)${NC}"
        sleep 2
        waited=$((waited + 2))
    done
    
    # 验证
    echo ""
    local kafka_health=$(docker inspect --format='{{.State.Health.Status}}' kafka 2>/dev/null || echo "unknown")
    if [ "$kafka_health" = "healthy" ]; then
        echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║   ✓ Kafka 修复成功!                  ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"
        return 0
    else
        echo -e "${RED}╔════════════════════════════════════════╗${NC}"
        echo -e "${RED}║   ✗ Kafka 启动失败，请检查日志        ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════╝${NC}"
        echo ""
        echo "查看日志: docker logs kafka --tail 50"
        return 1
    fi
}

# 重置 ZooKeeper（危险）
reset_zookeeper() {
    echo -e "${RED}╔════════════════════════════════════════╗${NC}"
    echo -e "${RED}║   ⚠️  警告：这是危险操作！           ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${RED}此操作将删除 ZooKeeper 数据，导致:${NC}"
    echo "  - Kafka 消费者组偏移量丢失"
    echo "  - Topic 配置丢失"
    echo "  - ACL 配置丢失"
    echo "  - 需要重新消费所有消息"
    echo ""
    echo "建议仅在开发环境中使用此命令"
    echo ""
    read -p "确定要继续吗? (type 'RESET ZOOKEEPER' to confirm): " confirm
    if [ "$confirm" != "RESET ZOOKEEPER" ]; then
        echo "已取消"
        return 1
    fi
    
    echo ""
    echo -e "${YELLOW}手动重置 ZooKeeper 数据...${NC}"
    echo ""
    
    # 获取 ZooKeeper 数据卷
    local zk_volume=""
    for vol in deploy_zookeeper_data docker_zookeeper_data zookeeper_data; do
        if docker volume inspect "$vol" &>/dev/null; then
            zk_volume="$vol"
            break
        fi
    done
    
    if [ -z "$zk_volume" ]; then
        echo -e "${RED}✗ 无法找到 ZooKeeper 数据卷${NC}"
        return 1
    fi
    
    echo -e "${CYAN}ZooKeeper 数据卷: $zk_volume${NC}"
    echo ""
    echo "执行以下命令:"
    echo ""
    echo -e "${YELLOW}# 1. 停止服务${NC}"
    echo "docker stop kafka zookeeper"
    echo ""
    echo -e "${YELLOW}# 2. 删除数据卷${NC}"
    echo "docker volume rm $zk_volume"
    echo ""
    echo -e "${YELLOW}# 3. 重启服务${NC}"
    echo "docker compose -f $SCRIPT_DIR/docker-compose.yml up -d"
    echo ""
    echo -e "${RED}请手动执行以上命令！${NC}"
}

# 显示帮助
show_help() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  check         检查当前状态（默认）"
    echo "  fix           修复 Kafka ID（生产推荐）"
    echo "  reset-zk      重置 ZooKeeper（⚠️ 危险）"
    echo "  help          显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 check      # 检查状态"
    echo "  $0 fix        # 安全修复"
}

# 主函数
main() {
    case "${1:-check}" in
        check)
            check_status
            ;;
        fix)
            fix_kafka_id
            ;;
        reset-zk)
            reset_zookeeper
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
}

main "$@"
