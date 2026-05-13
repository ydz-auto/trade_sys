
#!/usr/bin/env python3
"""
检查网络并帮助手机访问
"""

import socket
import os
import sys


def get_local_ip():
    """获取本地 IP 地址"""
    try:
        # 创建一个临时 socket 连接来获取本地 IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def main():
    local_ip = get_local_ip()

    print("=" * 80)
    print("手机访问问题诊断与解决")
    print("=" * 80)

    print("\n当前状态:")
    print("-" * 80)
    print(f"本地 IP 地址: {local_ip}")
    print("\n服务状态:")
    print(f"  - Execution Service: http://{local_ip}:8000")
    print(f"  - Frontend:           http://{local_ip}:3000")

    print("\n问题原因:")
    print("-" * 80)
    print("1. 服务可能仅绑定到 localhost (127.0.0.1)，仅本机可访问")
    print("2. 手机和电脑不在同一 Wi-Fi 网络")
    print("3. 防火墙阻止了外部连接")

    print("\n解决方法:")
    print("-" * 80)
    print("方案 1: 使用已运行的服务")
    print(f"  从手机浏览器访问:")
    print(f"    http://{local_ip}:3000/ (前端)")
    print(f"    http://{local_ip}:8000/ (执行服务)")
    print("\n  如果无法访问，请确保:")
    print("  - 手机和电脑在同一 Wi-Fi 网络")
    print("  - 服务绑定到 0.0.0.0 (所有网络接口)")

    print("\n方案 2: 检查 Vite 前端配置")
    print("-" * 80)
    print("Vite 前端服务默认可能绑定 localhost，需要改为 0.0.0.0")
    print("查看 vite.config.ts 文件，确保 host 配置正确")

    print("\n方案 3: 验证服务监听地址")
    print("-" * 80)
    print("运行以下命令检查监听端口:")
    print("  lsof -i :3000 (查看前端服务监听地址)")
    print("  lsof -i :8000 (查看执行服务监听地址)")

    print("\n" + "=" * 80)
    print("快速测试命令:")
    print("=" * 80)
    print(
        "\n# 测试本机访问 (这应该能工作)"
        f"\ncurl http://{local_ip}:3000/"
        f"\ncurl http://{local_ip}:8000/health"
    )

    print("\n" + "=" * 80)
    print("如果需要，请告诉我你想怎么改，我帮你重新启动！")


if __name__ == "__main__":
    main()

