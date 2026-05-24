# =============================================================================
# Docker 三层镜像模板
# =============================================================================
#
# Layer 1: quant-base - 基础镜像 (Python + 常用库 + Telemetry)
# Layer 2: runtime-base - 运行时基础镜像 (应用代码)
# Layer 3: runtime-entry - 入口镜像 (仅 CMD)
#
# 构建命令:
#   docker build -f docker/Dockerfile.base -t quant-base:latest .
#   docker build -f docker/Dockerfile.runtime -t runtime-base:latest .
#   docker build -f docker/Dockerfile.ingestion -t ingestion-runtime:latest .
# =============================================================================

# -----------------------------------------------------------------------------
# Layer 1: quant-base
# 基础镜像：Python + 常用库 + OpenTelemetry
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS quant-base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1


# -----------------------------------------------------------------------------
# Layer 2: runtime-base
# 运行时基础镜像：应用代码
# -----------------------------------------------------------------------------
FROM quant-base AS runtime-base

COPY config/ ./config/
COPY infrastructure/ ./infrastructure/
COPY domain/ ./domain/
COPY runtime/ ./runtime/
COPY services/ ./services/
COPY research/ ./research/
COPY api/ ./api/
COPY shared/ ./shared/

ENV CONFIG_DIR=/app/config


# -----------------------------------------------------------------------------
# Layer 3: runtime-entry
# 入口镜像：各 runtime 的具体入口
# -----------------------------------------------------------------------------

# Ingestion Runtime
FROM runtime-base AS ingestion-runtime
ENV RUNTIME_NAME=ingestion_runtime
CMD ["python", "-m", "runtime.ingestion_runtime"]

# Projection Runtime
FROM runtime-base AS projection-runtime
ENV RUNTIME_NAME=projection_runtime
CMD ["python", "-m", "runtime.projection_runtime"]

# Signal Runtime
FROM runtime-base AS signal-runtime
ENV RUNTIME_NAME=signal_runtime
CMD ["python", "-m", "runtime.signal_runtime"]

# Execution Runtime
FROM runtime-base AS execution-runtime
ENV RUNTIME_NAME=execution_runtime
CMD ["python", "-m", "runtime.execution_runtime"]

# Correlation Runtime
FROM runtime-base AS correlation-runtime
ENV RUNTIME_NAME=correlation_runtime
CMD ["python", "-m", "runtime.correlation_runtime"]

# Narrative Runtime
FROM runtime-base AS narrative-runtime
ENV RUNTIME_NAME=narrative_runtime
CMD ["python", "-m", "runtime.narrative_runtime"]

# Monitoring Runtime
FROM runtime-base AS monitoring-runtime
ENV RUNTIME_NAME=monitoring_runtime
CMD ["python", "-m", "runtime.monitoring_runtime"]

# Scheduler Runtime
FROM runtime-base AS scheduler-runtime
ENV RUNTIME_NAME=scheduler_runtime
CMD ["python", "-m", "runtime.scheduler_runtime"]

# API Server
FROM runtime-base AS api-server
COPY api_server.py .
COPY api_config.py .
EXPOSE 8000
CMD ["python", "api_server.py"]
