# Docker GPU 部署指南

## 概述

本项目支持 GPU 加速部署，适用于：
- LSTM 深度学习策略
- 批量特征计算
- 参数优化

## 前置要求

### 1. NVIDIA GPU 驱动

```bash
# 检查驱动
nvidia-smi

# 输出示例
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.104.05   Driver Version: 535.104.05   CUDA Version: 12.1     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  RTX 2060 SUPER    Off  | 00000000:01:00.0  On |                  N/A |
| 27%   35C    P8    12W / 175W |    512MiB /  8192MiB |      1%      Default |
+-------------------------------+----------------------+----------------------+
```

### 2. NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 验证
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### 3. Windows

```powershell
# 安装 Docker Desktop
# 安装 NVIDIA 驱动
# Docker Desktop -> Settings -> General -> Enable "Use the WSL 2 based engine"
# Docker Desktop -> Settings -> Resources -> WSL Integration -> Enable for your distro
```

## 构建镜像

### CPU 镜像（默认）

```bash
cd backend
docker build -f docker/Dockerfile -t quant:latest .
```

### GPU 镜像

```bash
cd backend
docker build -f docker/Dockerfile.gpu -t quant-gpu:latest .
```

## 运行服务

### 启动基础设施

```bash
cd backend/docker
docker-compose up -d kafka redis clickhouse
```

### 启动 CPU 服务

```bash
docker-compose up -d
```

### 启动 GPU 服务

```bash
# 方式1: 仅启动 GPU 服务
docker-compose -f docker-compose.gpu.yml up -d

# 方式2: 与 CPU 服务混合部署
docker-compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

## 服务说明

| 服务 | 端口 | GPU | 用途 |
|------|------|-----|------|
| api-server | 8000 | ❌ | API 服务 |
| gpu-api-server | 8001 | ✅ | GPU 加速 API |
| signal-runtime | - | ❌ | 信号计算 |
| gpu-signal-runtime | - | ✅ | LSTM 策略 |
| gpu-optimization | - | ✅ | 参数优化 |

## 使用示例

### 1. GPU 特征计算

```bash
# 调用 GPU API
curl -X POST http://localhost:8001/api/features/compute \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "use_gpu": true
  }'
```

### 2. GPU 参数优化

```bash
curl -X POST http://localhost:8001/api/optimization/start \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "strategy_id": "lstm",
    "param_grid": [
      {"hidden_size": 64, "num_layers": 1},
      {"hidden_size": 128, "num_layers": 2}
    ],
    "use_gpu": true
  }'
```

### 3. LSTM 训练

```bash
curl -X POST http://localhost:8001/api/lstm/train \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "BTCUSDT",
    "epochs": 100,
    "batch_size": 64
  }'
```

## 资源限制

### 限制 GPU 内存

```yaml
services:
  gpu-signal-runtime:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      PYTORCH_CUDA_ALLOC_CONF: max_split_size_mb:512
```

### 多 GPU 选择

```yaml
services:
  gpu-signal-runtime:
    environment:
      NVIDIA_VISIBLE_DEVICES: "0"  # 使用第一个 GPU
      # NVIDIA_VISIBLE_DEVICES: "0,1"  # 使用前两个 GPU
```

## 监控

### GPU 使用率

```bash
# 宿主机
nvidia-smi -l 1

# Docker 容器内
docker exec gpu-signal-runtime nvidia-smi
```

### Prometheus 指标

GPU 服务暴露以下指标：
- `gpu_memory_used_bytes`
- `gpu_memory_total_bytes`
- `gpu_utilization_percent`
- `feature_compute_duration_seconds`
- `lstm_inference_duration_seconds`

## 故障排除

### 1. GPU 不可用

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi

# 如果失败，重新配置 Docker runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

### 2. CUDA Out of Memory

```bash
# 减小 batch_size
curl -X POST http://localhost:8001/api/lstm/train \
  -d '{"batch_size": 32}'

# 或限制 GPU 内存
export PYTORCH_CUDA_ALLOC_CONF=max_split_size_mb:128
```

### 3. PyTorch 找不到 GPU

```bash
# 进入容器检查
docker exec -it gpu-signal-runtime python -c "import torch; print(torch.cuda.is_available())"

# 如果返回 False，检查环境变量
docker exec -it gpu-signal-runtime env | grep NVIDIA
```

## 性能优化

### 1. 批量大小调优

| GPU | 推荐 batch_size | 推荐 sequence_length |
|-----|----------------|---------------------|
| RTX 2060S (8GB) | 32-64 | 60-120 |
| RTX 3080 (10GB) | 64-128 | 120-240 |
| RTX 4090 (24GB) | 128-256 | 240-480 |

### 2. 多进程数据加载

```yaml
environment:
  DATALOADER_NUM_WORKERS: 4
  DATALOADER_PIN_MEMORY: "true"
```

### 3. 混合精度训练

```yaml
environment:
  MIXED_PRECISION: "true"
```

## Mac M4 部署

Mac M4 使用 MPS (Metal Performance Shaders) 而非 CUDA：

```bash
# 使用 CPU 镜像即可
docker build -f docker/Dockerfile -t quant:latest .

# PyTorch 自动检测 MPS
# 无需特殊配置
```

```yaml
# docker-compose.mac.yml
services:
  signal-runtime:
    environment:
      TORCH_DEVICE: mps
```
