#!/usr/bin/env python3
"""
API 测试脚本
测试所有 API 端点
"""

import sys
import requests
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8001"


class APITester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results: List[Dict[str, Any]] = []
        
    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "info": "ℹ️",
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "header": "📋"
        }.get(level, "ℹ️")
        print(f"[{timestamp}] {prefix} {message}")
        
    def test_endpoint(self, method: str, path: str, params: Dict = None, name: str = None) -> bool:
        """测试单个端点"""
        test_name = name or path
        url = f"{self.base_url}{path}"
        
        self.log(f"测试: {test_name}", "info")
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, params=params, timeout=10)
            else:
                response = requests.request(method, url, params=params, timeout=10)
                
            if response.status_code == 200:
                data = response.json()
                self.log(f"{test_name} - 成功! 状态码: {response.status_code}", "success")
                # 打印部分响应内容作为验证
                if isinstance(data, dict):
                    keys = list(data.keys())[:5]
                    self.log(f"  响应字段: {', '.join(keys)}", "info")
                elif isinstance(data, list):
                    self.log(f"  响应数量: {len(data)} 项", "info")
                self.results.append({
                    "name": test_name,
                    "path": path,
                    "status": "success",
                    "status_code": response.status_code
                })
                return True
            else:
                self.log(f"{test_name} - 失败! 状态码: {response.status_code}", "error")
                self.log(f"  响应: {response.text[:200]}", "error")
                self.results.append({
                    "name": test_name,
                    "path": path,
                    "status": "error",
                    "status_code": response.status_code,
                    "error": response.text[:200]
                })
                return False
                
        except requests.exceptions.ConnectionError:
            self.log(f"{test_name} - 连接失败! 请确保服务器已启动", "error")
            self.results.append({
                "name": test_name,
                "path": path,
                "status": "connection_error",
                "error": "无法连接到服务器"
            })
            return False
        except Exception as e:
            self.log(f"{test_name} - 错误: {str(e)}", "error")
            self.results.append({
                "name": test_name,
                "path": path,
                "status": "exception",
                "error": str(e)
            })
            return False
    
    def test_all(self):
        """测试所有 API 端点"""
        self.log("=" * 60, "header")
        self.log("开始 API 测试", "header")
        self.log("=" * 60, "header")
        
        # 检查服务器是否可用
        self.log("\n检查服务器连接...", "info")
        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            self.log("服务器响应正常!", "success")
        except:
            self.log(f"无法连接到服务器 ({self.base_url})", "error")
            self.log("请先启动服务器: python -m api_server", "warning")
            return False
        
        # 基础测试
        self.log("\n📊 基础端点测试", "header")
        self.test_endpoint("GET", "/health", name="健康检查")
        
        # API 测试
        self.log("\n📊 API 端点测试", "header")
        self.test_endpoint("GET", "/api/v1/trading/dashboard", name="仪表板")
        self.test_endpoint("GET", "/api/v1/news", params={"limit": 5}, name="新闻列表")
        self.test_endpoint("GET", "/api/v1/prices", name="价格数据")
        self.test_endpoint("GET", "/api/v1/prices", params={"symbols": "BTC,ETH"}, name="价格数据(指定符号)")
        self.test_endpoint("GET", "/api/v1/etf", name="ETF资金流")
        self.test_endpoint("GET", "/api/v1/etf", params={"symbol": "ETH"}, name="ETF资金流(ETH)")
        self.test_endpoint("GET", "/api/v1/factors", name="因子数据")
        self.test_endpoint("GET", "/api/v1/regime", name="市场状态")
        self.test_endpoint("GET", "/api/v1/risk", name="风险评估")
        self.test_endpoint("GET", "/api/v1/signal", name="交易信号")
        self.test_endpoint("GET", "/api/v1/positions", name="持仓信息")
        self.test_endpoint("GET", "/api/v1/weights/versions", name="权重版本")
        
        # 测试 Swagger 文档
        self.log("\n📊 文档端点测试", "header")
        self.test_endpoint("GET", "/docs", name="Swagger UI")
        self.test_endpoint("GET", "/redoc", name="ReDoc")
        self.test_endpoint("GET", "/openapi.json", name="OpenAPI JSON")
        
        # 统计结果
        self.print_summary()
        
    def print_summary(self):
        """打印测试总结"""
        self.log("\n" + "=" * 60, "header")
        self.log("测试总结", "header")
        self.log("=" * 60, "header")
        
        success_count = sum(1 for r in self.results if r["status"] == "success")
        error_count = sum(1 for r in self.results if r["status"] in ["error", "connection_error", "exception"])
        total_count = len(self.results)
        
        self.log(f"总计: {total_count} 个端点", "info")
        self.log(f"成功: {success_count} 个", "success")
        self.log(f"失败: {error_count} 个", "error" if error_count > 0 else "info")
        
        if error_count == 0:
            self.log("\n🎉 所有 API 测试通过!", "success")
        else:
            self.log("\n⚠️  部分 API 测试失败", "warning")
            self.log("\n失败列表:", "warning")
            for r in self.results:
                if r["status"] != "success":
                    self.log(f"  - {r['name']}: {r.get('error', r['status'])}", "error")


def main():
    tester = APITester()
    tester.test_all()


if __name__ == "__main__":
    main()
