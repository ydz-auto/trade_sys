"""
完整验证脚本

测试所有新增的组件是否正常工作
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def run_module_check():
    """检查所有模块是否可以导入"""
    modules = [
        ("策略引擎", "services.strategy_service.strategies"),
        ("风控服务", "services.risk_service.main_kafka"),
        ("决策模型", "infrastructure.messaging.schema.decision"),
        ("敏感过滤", "infrastructure.logging.sensitive_filter"),
        ("模拟脚本", "scripts.simulate_pipeline"),
        ("监控面板", "services.monitoring.monitoring_panel"),
    ]
    
    success = True
    print("=" * 70)
    print("模块导入检查")
    print("=" * 70)
    
    for name, module_path in modules:
        try:
            __import__(module_path)
            print(f"✅ {name} 导入成功")
        except Exception as e:
            print(f"❌ {name} 导入失败: {e}")
            import traceback
            print(f"   堆栈: {traceback.format_exc()}")
            success = False
    
    print("\n" + "=" * 70)
    return success


def check_files():
    """检查关键文件是否存在"""
    base_path = Path(__file__).parent.parent
    files = [
        ("QUICKSTART.md", base_path / "QUICKSTART.md"),
        ("架构完成文档", base_path / "docs" / "ARCHITECTURE_COMPLETION.md"),
        ("策略实现", base_path / "services" / "strategy_service" / "strategies.py"),
        ("风控服务主程序", base_path / "services" / "risk_service" / "main_kafka.py"),
        ("决策模型", base_path / "infrastructure" / "messaging" / "schema" / "decision.py"),
        ("敏感过滤器", base_path / "infrastructure" / "logging" / "sensitive_filter.py"),
        ("模拟脚本", base_path / "scripts" / "simulate_pipeline.py"),
        ("监控面板", base_path / "services" / "monitoring" / "monitoring_panel.py"),
        ("集成测试", base_path / "tests" / "integration" / "test_pipeline.py"),
    ]
    
    print("\n" + "=" * 70)
    print("文件存在检查")
    print("=" * 70)
    
    success = True
    for name, path in files:
        if path.exists():
            print(f"✅ {name} 存在")
        else:
            print(f"❌ {name} 不存在")
            success = False
    
    print("\n" + "=" * 70)
    return success


def check_strategy_engine():
    """测试策略引擎"""
    print("\n" + "=" * 70)
    print("策略引擎检查")
    print("=" * 70)
    
    try:
        from services.strategy_service.strategies import (
            create_default_strategies,
            RSIStrategy,
            MACDStrategy,
        )
        
        # 创建策略引擎
        orchestrator = create_default_strategies()
        print("✅ 策略引擎创建成功")
        
        # 检查策略数量
        strategy_count = len(orchestrator._strategies)
        print(f"✅ 策略数量: {strategy_count}")
        
        # 检查具体策略
        if "rsi_14" in orchestrator._strategies:
            print("✅ RSI 策略已加载")
        if "macd_12_26_9" in orchestrator._strategies:
            print("✅ MACD 策略已加载")
        
        return True
    except Exception as e:
        print(f"❌ 策略引擎检查失败: {e}")
        import traceback
        print(f"堆栈: {traceback.format_exc()}")
        return False


def check_decision_model():
    """测试决策模型"""
    print("\n" + "=" * 70)
    print("决策模型检查")
    print("=" * 70)
    
    try:
        from infrastructure.messaging.schema.decision import Decision, RiskCheckedDecision
        from infrastructure.messaging.schema.signal import Signal
        from datetime import datetime
        
        # 创建测试决策
        decision = Decision(
            decision_id="test_dec_001",
            action="LONG",
            symbol="BTCUSDT",
            quantity=0.01,
            price=50000.0,
            confidence=0.85,
            reason="测试决策",
            source="test",
            timestamp=int(datetime.now().timestamp() * 1000),
        )
        
        print("✅ Decision 模型创建成功")
        print(f"   决策: {decision.action} {decision.symbol}")
        
        # 创建风控后的决策
        checked = RiskCheckedDecision(
            decision_id=decision.decision_id,
            approved=True,
            reason=None,
            risk_level="low",
            original_decision=decision,
            check_results={"all": "ok"},
        )
        
        print("✅ RiskCheckedDecision 模型创建成功")
        print(f"   批准: {checked.approved}")
        
        return True
    except Exception as e:
        print(f"❌ 决策模型检查失败: {e}")
        import traceback
        print(f"堆栈: {traceback.format_exc()}")
        return False


def check_risk_service():
    """测试风控服务"""
    print("\n" + "=" * 70)
    print("风控服务检查")
    print("=" * 70)
    
    try:
        from services.risk_service.risk_engine import RiskService, RiskConfig
        
        # 创建风控服务
        config = RiskConfig(
            max_position_size=0.5,
            max_single_loss=0.02,
            max_daily_loss=0.05,
            max_drawdown=0.15,
        )
        service = RiskService(config)
        print("✅ 风控服务创建成功")
        
        # 获取指标
        metrics = service.get_metrics()
        print(f"✅ 获取指标: {metrics}")
        
        return True
    except Exception as e:
        print(f"❌ 风控服务检查失败: {e}")
        import traceback
        print(f"堆栈: {traceback.format_exc()}")
        return False


def check_sensitive_filter():
    """测试敏感过滤器"""
    print("\n" + "=" * 70)
    print("敏感数据过滤检查")
    print("=" * 70)
    
    try:
        from infrastructure.logging.sensitive_filter import (
            get_sensitive_filter,
            mask_sensitive_dict,
        )
        
        filter = get_sensitive_filter()
        print("✅ 敏感过滤器获取成功")
        
        # 测试敏感数据
        test_data = {
            "api_key": "test_api_key_12345",
            "api_secret": "test_secret_abcde",
            "password": "mypassword",
            "other": "safe_value",
        }
        
        filtered = mask_sensitive_dict(test_data)
        print(f"✅ 过滤前: {test_data}")
        print(f"✅ 过滤后: {filtered}")
        
        if filtered["api_key"] != test_data["api_key"]:
            print("✅ API Key 已正确屏蔽")
        else:
            print("❌ API Key 未正确屏蔽")
            return False
        
        return True
    except Exception as e:
        print(f"❌ 敏感过滤检查失败: {e}")
        import traceback
        print(f"堆栈: {traceback.format_exc()}")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("完整验证")
    print("=" * 70)
    
    checks = [
        ("文件检查", check_files),
        ("模块导入", run_module_check),
        ("策略引擎", check_strategy_engine),
        ("决策模型", check_decision_model),
        ("风控服务", check_risk_service),
        ("敏感过滤", check_sensitive_filter),
    ]
    
    results = []
    for name, check_fn in checks:
        try:
            result = check_fn()
            results.append((name, result))
        except Exception as e:
            print(f"❌ {name} 检查异常: {e}")
            results.append((name, False))
    
    print("\n" + "=" * 70)
    print("验证结果")
    print("=" * 70)
    
    all_passed = True
    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{name}: {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ 所有检查通过！")
        print("\n下一步:")
        print("1. 运行完整模拟: python -m scripts.simulate_pipeline")
        print("2. 启动监控面板: python -m services.monitoring.monitoring_panel")
        print("3. 查看 QUICKSTART.md 了解更多信息")
    else:
        print("❌ 部分检查失败，请检查错误信息")
    print("=" * 70)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
