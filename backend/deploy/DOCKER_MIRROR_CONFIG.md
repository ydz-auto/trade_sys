# Docker 镜像加速配置指南

## 问题描述

Docker Desktop 无法从 Docker Hub 拉取镜像，错误信息：
```
failed to do request: Head "https://registry-1.docker.io/v2/confluentinc/cp-kafka/manifests/7.5.0"
dialing registry-1.docker.io:443 container via direct connection because Docker Desktop has no HTTPS proxy
connectex: A connection attempt failed because the connected party did not properly respond
```

## 原因

Docker Hub 在国内访问受限，需要配置镜像加速器。

## 解决方案

### 方法 1: 配置 Docker Desktop 镜像加速器（推荐）

1. 打开 Docker Desktop
2. 点击右上角设置图标（⚙️）
3. 选择 "Docker Engine"
4. 在编辑器中添加以下配置：

```json
{
  "builder": {
    "gc": {
      "defaultKeepStorage": "20GB",
      "enabled": true
    }
  },
  "experimental": false,
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://dockerproxy.link",
    "https://docker.m.daocloud.io",
    "https://registry.cyou"
  ]
}
```

5. 点击 "Apply & Restart"

### 方法 2: 手动创建 daemon.json（Windows）

1. 打开 Docker Desktop 设置
2. 找到 Docker Engine 配置
3. 添加镜像加速器配置
4. 应用并重启

### 方法 3: 使用代理

如果公司网络需要代理：

1. 打开 Docker Desktop 设置
2. 选择 "Resources" > "Proxies"
3. 配置 HTTPS 代理
4. 应用并重启

## 常用镜像加速器

| 加速器 | 地址 |
|--------|------|
| 中国科技大学 | https://docker.mirrors.ustc.edu.cn |
| 网易 | https://hub-mirror.c.163.com |
| 百度 | https://mirror.baidubce.com |
| 阿里云 | https://<your-id>.mirror.aliyuncs.com |
| Docker Hub 官方 | 无需配置，直接拉取 |

## 验证配置

配置完成后，运行以下命令验证：

```powershell
docker info
```

应该看到类似输出：
```
Registry Mirrors:
 https://docker.mirrors.ustc.edu.cn/
 https://hub-mirror.c.163.com/
```

## 拉取镜像测试

```powershell
# 测试拉取 Redis
docker pull redis:7-alpine

# 测试拉取 Kafka
docker pull confluentinc/cp-kafka:7.5.0
```

## 常见问题

### Q: 配置后仍然无法拉取镜像

A: 检查以下几点：
1. Docker Desktop 是否已重启
2. 网络是否可达加速器地址
3. 尝试更换加速器地址

### Q: 企业网络无法访问外网

A: 需要联系 IT 部门：
1. 配置企业代理
2. 或使用私有镜像仓库
3. 或在防火墙白名单中添加加速器地址

### Q: 镜像拉取超时

A: 可以尝试：
1. 增加超时时间
2. 更换网络较好的加速器
3. 使用 `docker pull --progress=plain` 查看详细进度

## 备选方案

如果镜像加速器无法使用，可以手动拉取镜像：

1. 在其他可以访问 Docker Hub 的机器上拉取镜像
2. 导出镜像为 tar 文件：`docker save -o image.tar image:tag`
3. 复制到本机
4. 导入镜像：`docker load -i image.tar`

## 参考链接

- Docker 官方文档：https://docs.docker.com/docker-hub/mirrors/
- Docker Desktop Windows：https://docs.docker.com/desktop/windows/
