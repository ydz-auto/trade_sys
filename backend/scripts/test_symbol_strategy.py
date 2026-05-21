"""
测试币种专属策略系统
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.strategy.symbol_config import (
    SymbolStrategyConfigManager,
    get_symbol_config_manager,
)
from services.strategy_service.symbol_strategies import (
    SymbolStrategyOrchestrator,
    get_symbol_strategy_orchestrator,
)


def test_config_loading():
    """测试配置加载"""
    print("=" * 60)
    print("测试 1: 配置加载")
    print("=" * 60)
    
    config_dir = Path(__file__).parent.parent / "config" / "strategy" / "symbols"
    manager = SymbolStrategyConfigManager(str(config_dir))
    
    print(f"\n配置目录: {config_dir}")
    print(f"加载的配置数量: {len(manager.get_all_configs())}")
    
    enabled_symbols = manager.get_enabled_symbols()
    print(f"启用的币种: {enabled_symbols}")
    
    for symbol in enabled_symbols:
        config = manager.get_config(symbol)
        if config:
            print(f"\n  {symbol}:")
            print(f"    描述: {config.description}")
            print(f"    波动率特征: {config.volatility_profile}")
            print(f"    流动性特征: {config.liquidity_profile}")
            print(f"    最大杠杆: {config.risk.max_leverage}x")
            print(f"    启用的策略: {config.enabled_strategies}")
    
    print("\n✓ 配置加载测试通过")
    return manager


def test_strategy_orchestrator():
    """测试策略编排器"""
    print("\n" + "=" * 60)
    print("测试 2: 策略编排器初始化")
    print("=" * 60)
    
    config_dir = Path(__file__).parent.parent / "config" / "strategy" / "symbols"
    orchestrator = SymbolStrategyOrchestrator(str(config_dir))
    
    enabled_symbols = orchestrator.get_enabled_symbols()
    print(f"\n启用策略的币种: {enabled_symbols}")
    
    for symbol in enabled_symbols:
        risk_config = orchestrator.get_risk_config(symbol)
        if risk_config:
            print(f"\n  {symbol} 风险配置:")
            print(f"    仓位大小: {risk_config['position_size']}")
            print(f"    杠杆范围: {risk_config['min_leverage']}x - {risk_config['max_leverage']}x")
            print(f"    止损: {risk_config['stop_loss_pct']}%")
            print(f"    止盈: {risk_config['take_profit_pct']}%")
    
    print("\n✓ 策略编排器测试通过")
    return orchestrator


def generate_test_data(symbol: str, num_points: int = 100) -> dict:
    """生成测试市场数据"""
    import random
    
    base_price = {
        "BTCUSDT": 70000,
        "ETHUSDT": 3500,
        "SOLUSDT": 150,
    }.get(symbol, 100)
    
    # 生成一些随机价格数据
    prices = []
    current = base_price
    for _ in range(num_points):
        change = random.uniform(-0.02, 0.02)
        current = current * (1 + change)
        prices.append(current)
    
    volumes = [random.uniform(100, 1000) for _ in range(num_points)]
    
    return {
        "symbol": symbol,
        "close_prices": prices,
        "high_prices": [p * 1.01 for p in prices],
        "low_prices": [p * 0.99 for p in prices],
        "volumes": volumes,
    }


def test_strategy_execution(orchestrator):
    """测试策略执行"""
    print("\n" + "=" * 60)
    print("测试 3: 策略执行")
    print("=" * 60)
    
    enabled_symbols = orchestrator.get_enabled_symbols()
    
    for symbol in enabled_symbols:
        print(f"\n处理 {symbol}...")
        
        # 生成测试数据
        data = generate_test_data(symbol, 200)
        orchestrator.update_market_data(symbol, data)
        
        # 处理并获取信号
        signals = orchestrator.process_symbol(symbol)
        
        print(f"  产生信号数: {len(signals)}")
        for signal in signals:
            print(f"    - {signal.strategy_name}: {signal.action} @ {signal.price:.2f}, 置信度: {signal.confidence:.2f}")
            print(f"      原因: {signal.reason}")
    
    print("\n✓ 策略执行测试通过")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("币种专属策略系统测试")
    print("=" * 60)
    
    try:
        # 测试1: 配置加载
        manager = test_config_loading()
        
        # 测试2: 策略编排器
        orchestrator = test_strategy_orchestrator()
        
        # 测试3: 策略执行
        test_strategy_execution(orchestrator)
        
        print("\n" + "=" * 60)
        print("所有测试通过! ✓")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
