# =============================================================================
# TradeAgent Makefile
# =============================================================================
#
# 用法:
#   make start        # 启动所有服务
#   make stop         # 停止所有服务
#   make build        # 构建所有镜像
#   make logs         # 查看日志
#   make status       # 查看状态
#
# =============================================================================

.PHONY: all start stop build logs status clean help

DOCKER_DIR := docker
COMPOSE := docker-compose -f $(DOCKER_DIR)/docker-compose.yml

all: start

start:
	@cd $(DOCKER_DIR) && ./start.sh

start-infra:
	@cd $(DOCKER_DIR) && ./start.sh infra

start-runtimes:
	@cd $(DOCKER_DIR) && ./start.sh runtimes

stop:
	@cd $(DOCKER_DIR) && ./stop.sh

stop-runtimes:
	@cd $(DOCKER_DIR) && ./stop.sh runtimes

clean:
	@cd $(DOCKER_DIR) && ./stop.sh clean

build:
	@cd $(DOCKER_DIR) && ./build.sh

build-no-cache:
	@cd $(DOCKER_DIR) && ./build.sh --no-cache

logs:
	@cd $(DOCKER_DIR) && ./logs.sh

logs-follow:
	@cd $(DOCKER_DIR) && ./logs.sh -f

status:
	@$(COMPOSE) ps

ps:
	@$(COMPOSE) ps

restart:
	@$(COMPOSE) restart

restart-runtime:
	@read -p "Runtime name (e.g., signal): " name; \
	$(COMPOSE) restart $$name-runtime

shell:
	@read -p "Service name: " name; \
	$(COMPOSE) exec $$name /bin/bash

health:
	@curl -s http://localhost:8000/health | python3 -m json.tool || echo "API not responding"

kafka-topics:
	@$(COMPOSE) exec kafka kafka-topics --bootstrap-server localhost:9092 --list

kafka-consume:
	@read -p "Topic name: " topic; \
	$(COMPOSE) exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic $$topic --from-beginning

redis-cli:
	@$(COMPOSE) exec redis redis-cli

clickhouse-cli:
	@$(COMPOSE) exec clickhouse clickhouse-client

postgres-cli:
	@$(COMPOSE) exec postgres psql -U postgres -d tradeagent

grafana-open:
	@open http://localhost:3000

kafka-ui-open:
	@open http://localhost:8080

prometheus-open:
	@open http://localhost:9090

api-docs-open:
	@open http://localhost:8000/docs

help:
	@echo "TradeAgent Makefile Commands"
	@echo ""
	@echo "  make start          启动所有服务"
	@echo "  make start-infra    只启动基础设施"
	@echo "  make start-runtimes 只启动 Runtime 服务"
	@echo "  make stop           停止所有服务"
	@echo "  make clean          停止并清理数据卷"
	@echo "  make build          构建所有镜像"
	@echo "  make build-no-cache 不使用缓存构建"
	@echo "  make logs           查看日志"
	@echo "  make logs-follow    实时查看日志"
	@echo "  make status         查看服务状态"
	@echo "  make restart        重启所有服务"
	@echo "  make health         检查 API 健康状态"
	@echo ""
	@echo "  make kafka-topics   列出 Kafka topics"
	@echo "  make redis-cli      Redis CLI"
	@echo "  make clickhouse-cli ClickHouse CLI"
	@echo "  make postgres-cli   PostgreSQL CLI"
	@echo ""
	@echo "  make grafana-open   打开 Grafana"
	@echo "  make kafka-ui-open  打开 Kafka UI"
	@echo "  make api-docs-open  打开 API 文档"
