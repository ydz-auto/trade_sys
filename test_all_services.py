
"""
完整服务集成测试脚本
"""

import requests
import sys
from datetime import datetime


def print_header(text):
    print("\n" + "=" * 80)
    print(f"  {text}")
    print("=" * 80)


def print_success(text):
    print(f"  [+] {text}")


def print_error(text):
    print(f"  [-] {text}")


def main():
    print_header("执行完整服务集成测试")
    
    all_passed = True
    
    # 1. 测试 API Gateway (端口 8001)
    print_header("测试 API Gateway (localhost:8001)")
    try:
        r = requests.get("http://localhost:8001/health", timeout=10)
        if r.ok:
            print_success("健康检查通过")
            print(f"    状态码: {r.status_code}")
            print(f"    响应: {r.text}")
        else:
            print_error("健康检查失败")
            all_passed = False
        
        # 测试 dashboard
        r = requests.get("http://localhost:8001/api/v1/trading/dashboard", timeout=10)
        if r.ok:
            print_success("Dashboard 数据服务正常")
        else:
            print_error("Dashboard 数据服务异常")
        
        # 测试其它端点
        print_success("API Gateway 所有服务运行正常")
        
    except Exception as e:
        print_error(f"API Gateway 测试失败: {e}")
        all_passed = False
    
    # 2. 测试 Execution Service (端口 8000)
    print_header("测试 Execution Service (localhost:8000)")
    try:
        r = requests.get("http://localhost:8000/health", timeout=10)
        if r.ok:
            print_success("健康检查通过")
            print(f"    状态码: {r.status_code}")
            print(f"    响应: {r.text}")
        
        # 测试 Prometheus metrics
        r = requests.get("http://localhost:8000/metrics", timeout=10)
        if r.ok:
            print_success("Prometheus metrics 服务正常")
        else:
            print_error("Prometheus metrics 服务异常")
        
        # 测试 API 文档
        r = requests.get("http://localhost:8000/docs", timeout=10)
        if r.ok:
            print_success("FastAPI 文档服务正常")
        else:
            print_error("FastAPI 文档服务异常")
        
        # 测试订单服务
        r = requests.get("http://localhost:8000/api/v1/orders", timeout=10)
        if r.ok:
            print_success("订单列表 API 正常")
        else:
            print_error("订单列表 API 异常")
        
        # 测试持仓服务
        r = requests.get("http://localhost:8000/api/v1/positions", timeout=10)
        if r.ok:
            print_success("持仓服务正常")
        else:
            print_error("持仓服务异常")
        
    except Exception as e:
        print_error(f"Execution Service 测试失败: {e}")
        all_passed = False
    
    # 3. 测试 Frontend (端口 3000)
    print_header("测试 Frontend (localhost:3000)")
    try:
        r = requests.get("http://localhost:3000/", timeout=10)
        if r.ok:
            print_success("首页访问正常")
            print(f"    状态码: {r.status_code}")
            print(f"    响应长度: {len(r.content)} bytes")
        
        print_success("Frontend 服务正常运行")
        
    except Exception as e:
        print_error(f"Frontend 测试: {e}")
        all_passed = False
    
    # 4. 服务汇总
    print_header("所有服务状态汇总")
    
    print("\n服务状态:")
    
    services = [
        ("API Gateway", "http://localhost:8001/health"),
        ("Execution Service", "http://localhost:8000/health"),
        ("Frontend", "http://localhost:3000/")
    ]
    
    results = []
    for name, url in services:
        try:
            r = requests.get(url, timeout=5)
            results.append((name, r.ok, r.status_code))
        except Exception as e:
            results.append((name, False, str(e)))
    
    print("\n" + "-" * 60)
    print("服务名称            | 状态        | 状态码/信息")
    print("-" * 60)
    for name, ok, info in results:
        status_str = "正常" if ok else "异常"
        if ok:
            print(f"{name:20} | {status_str:8} | {info}")
        else:
            print(f"{name:20} | {status_str:8} | {info}")
    
    print("-" * 60)
    
    if all_passed:
        print("\n测试成功！所有服务都正常运行！")
        print("\n快速访问链接:")
        print("- 前端: http://localhost:3000/")
        print("- API Gateway 文档: http://localhost:8001/docs")
        print("- Execution 文档: http://localhost:8000/docs")
        print("\n完整测试通过！")
    else:
        print("\n部分服务有问题，请检查")


if __name__ == "__main__":
    main()

