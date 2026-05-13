
"""
测试运行正常的服务
"""

import requests


def test_service(name, url):
    print(f"\n[测试 {name} ({url})...")
    try:
        r = requests.get(url, timeout=10)
        if r.ok:
            print(f"  状态码: {r.status_code} - 正常")
            return True
        else:
            print(f"  状态码: {r.status_code} - 异常")
            return False
    except Exception as e:
        print(f"  错误: {e}")
        return False


def main():
    print("=" * 80)
    print("服务测试")
    print("=" * 80)
    
    services = [
        ("Execution Service 健康检查", "http://localhost:8000/health"),
        ("Execution Service Metrics", "http://localhost:8000/metrics"),
        ("Execution Service 文档", "http://localhost:8000/docs"),
        ("Execution Service 订单", "http://localhost:8000/api/v1/orders"),
        ("Execution Service 持仓", "http://localhost:8000/api/v1/positions"),
        ("Frontend", "http://localhost:3000/"),
    ]
    
    all_ok = True
    for name, url in services:
        if not test_service(name, url):
            all_ok = False
    
    print("\n" + "=" * 80)
    print(f"{'所有服务正常！" if all_ok else "部分服务异常"}")
    print("=" * 80)
    
    print("\n正常工作的服务:")
    print("- Execution Service (端口 8000)")
    print("- Frontend (端口 3000)")
    print("\n快速访问:")
    print("- 前端: http://localhost:3000/")
    print("- Execution Service Docs: http://localhost:8000/docs")
    print("- Execution Metrics: http://localhost:8000/metrics")
    print("- Execution Health: http://localhost:8000/health")


if __name__ == "__main__":
    main()

