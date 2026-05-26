"""
测试策略注册表 - 验证 StrategyBridge 已被移除
"""
import inspect
import unittest
from engines.compute.strategy import registry


class TestStrategyRegistryNoBridge(unittest.TestCase):
    
    def test_registry_no_strategy_bridge_class(self):
        """测试 registry.py 中不存在 StrategyBridge 类"""
        self.assertFalse(hasattr(registry, 'StrategyBridge'), 
                        "registry.py 中不应存在 StrategyBridge 类")
        
        source_code = inspect.getsource(registry)
        self.assertNotIn('StrategyBridge', source_code, 
                        "registry.py 源代码中不应出现 StrategyBridge")

    def test_strategy_registry_values_not_bridge(self):
        """测试 _STRATEGY_REGISTRY 的 value 都不是 StrategyBridge"""
        for strategy_id, strategy_class in registry._STRATEGY_REGISTRY.items():
            self.assertNotEqual(strategy_class.__name__, 'StrategyBridge',
                              f"策略 {strategy_id} 注册的类不应是 StrategyBridge")

    def test_all_strategies_have_generate_signal(self):
        """测试每个策略实例都有 generate_signal 方法"""
        for strategy_id in registry._STRATEGY_REGISTRY.keys():
            strategy_instance = registry.get_strategy(strategy_id)
            self.assertTrue(hasattr(strategy_instance, 'generate_signal'),
                          f"策略 {strategy_id} 实例应具有 generate_signal 方法")
            self.assertTrue(callable(getattr(strategy_instance, 'generate_signal')),
                          f"策略 {strategy_id} 的 generate_signal 应是可调用的")

    def test_generate_signal_with_empty_features(self):
        """测试每个策略用空 features 调用 generate_signal 不抛异常"""
        for strategy_id in registry._STRATEGY_REGISTRY.keys():
            strategy_instance = registry.get_strategy(strategy_id)
            try:
                result = strategy_instance.generate_signal({})
                self.assertTrue(result is None or isinstance(result, dict),
                              f"策略 {strategy_id} 的 generate_signal 返回值应为 None 或 dict")
            except Exception as e:
                self.fail(f"策略 {strategy_id} 调用 generate_signal 抛出异常: {e}")

    def test_get_strategy_auto_injects_strategy_id(self):
        """测试 get_strategy() 自动注入 strategy_id"""
        strategy_id = "rsi_oversold"
        strategy = registry.get_strategy(strategy_id)
        
        if hasattr(strategy, 'strategy_id'):
            self.assertEqual(strategy.strategy_id, strategy_id,
                          f"策略实例的 strategy_id 应为 {strategy_id}")


if __name__ == "__main__":
    unittest.main()
