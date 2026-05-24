.PHONY: help dev prod test clean logs api projection

help:
	@echo "TradeLab - Docker Deployment Commands"
	@echo ""
	@echo "  make dev          - Start development environment"
	@echo "  make prod         - Start production environment"
	@echo "  make test         - Run tests"
	@echo "  make clean        - Clean up containers and volumes"
	@echo "  make logs         - View logs"
	@echo "  make api          - Start API server only"
	@echo "  make projection    - Start projection worker only"

dev:
	docker-compose -f docker-compose.simple.yml up

prod:
	docker-compose -f docker-compose.yml up -d

test:
	cd backend && PYTHONPATH=. python scripts/test_full_system.py

clean:
	docker-compose -f docker-compose.yml down -v 2>/dev/null || true
	docker-compose -f docker-compose.simple.yml down -v 2>/dev/null || true

logs:
	docker-compose -f docker-compose.simple.yml logs -f

api:
	cd backend && PYTHONPATH=. python api_server.py

projection:
	cd backend && PYTHONPATH=. python -m services.projection_worker.main

backend-shell:
	docker-compose -f docker-compose.simple.yml exec backend /bin/sh

redis-cli:
	docker-compose -f docker-compose.simple.yml exec redis redis-cli

kafka-topics:
	docker-compose -f docker-compose.simple.yml exec kafka kafka-topics.sh --bootstrap-server localhost:9092 --list

docker-build:
	docker-compose -f docker-compose.simple.yml build

docker-down:
	docker-compose -f docker-compose.simple.yml down
