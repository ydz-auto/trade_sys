"""
Market State Machine 示例
展示如何使用市场状态机和 TradePressure 检测器
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from domain.market_state.state import (
    RegimeType,
    LiquidityState,
    PressureState,
    VolatilityState,
    TrendState,
    MarketState,
)
from domain.market_state.machine import MarketStateMachine
from domain.feature.indicators.trade_pressure import (
    TradePressureDetector,
    TradePressureSignal,
)
from domain.event.event_type import EventType
from domain.config.strategy_config import StrategyConfigV2, EntryParams, ExitParams, RiskParams


def example_market_state_machine():
    """示例：使用 MarketStateMachine"""
    print("=" * 60)
    print("示例 1: MarketStateMachine 基础使用")
    print("=" * 60)
    
    # 1. 创建状态机
    symbol = "BTCUSDT"
    state_machine = MarketStateMachine(symbol=symbol)
    print(f"创建了状态机，标的: {symbol}")
    print(f"初始状态: {state_machine.current_state}")
    
    # 2. 模拟几个事件
    events = [
        (EventType.TRADE_PRESSURE_FLUSH, {"pressure_zscore": -2.5, "volatility_zscore": 1.8}),
        (EventType.TRADE_PRESSURE_EXHAUSTION, {"pressure_zscore": 0.2, "trend_strength": -0.1}),
        (EventType.LIQUIDITY_VACUUM, {"liquidity_ratio": 0.2, "pressure_zscore": 2.2}),
    ]
    
    for i, (event_type, features) in enumerate(events, 1):
        print(f"\n--- 事件 {i} ---")
        print(f"事件类型: {event_type}")
        print(f"特征: {features}")
        
        # 更新状态
        new_state = state_machine.update(event_type, features)
        
        # 打印新状态
        print(f"新状态:")
        print(f"  - 整体市场状态: {new_state.regime}")
        print(f"  - 流动性状态: {new_state.liquidity}")
        print(f"  - 压力状态: {new_state.pressure}")
        print(f"  - 波动率状态: {new_state.volatility}")
        print(f"  - 趋势状态: {new_state.trend}")
        print(f"  - 信心度: {new_state.confidence:.2f}")
        print(f"  - 最后事件: {new_state.last_major_event}")
        
        # 使用便捷方法
        print(f"  - 是否耗尽: {new_state.is_exhausted()}")
        print(f"  - 是否流动性真空: {new_state.is_liquid_vacuum()}")
        print(f"  - 是否高信心: {new_state.is_high_confidence()}")
    
    # 3. 查看历史
    print(f"\n--- 历史状态 ({len(state_machine.history)} 条) ---")
    for i, state in enumerate(state_machine.get_history()):
        print(f"{i}: {state}")


def example_trade_pressure_detector():
    """示例：使用 TradePressureDetector"""
    print("\n" + "=" * 60)
    print("示例 2: TradePressureDetector 基础使用")
    print("=" * 60)
    
    # 1. 创建检测器
    detector = TradePressureDetector()
    print("创建了 TradePressureDetector")
    
    symbol = "BTCUSDT"
    
    # 2. 模拟市场数据序列
    market_data = [
        # (价格, 成交量, 买量, 卖量, 订单簿不平衡, 5分钟涨跌幅, 15分钟涨跌幅)
        (50000.0, 100, 60, 40, 0.2, 0.01, 0.03),
        (50200.0, 120, 75, 45, 0.3, 0.014, 0.032),
        (49500.0, 300, 80, 220, -0.4, -0.014, 0.02),
        (49000.0, 400, 100, 300, -0.5, -0.01, -0.005),
        (49200.0, 250, 200, 50, 0.4, 0.004, -0.002),
    ]
    
    for i, (price, vol, buy_vol, sell_vol, ob_imbalance, chg_5m, chg_15m) in enumerate(market_data, 1):
        print(f"\n--- 数据点 {i} ---")
        print(f"价格: {price}, 成交量: {vol}")
        print(f"买量: {buy_vol}, 卖量: {sell_vol}, 不平衡: {ob_imbalance:.2f}")
        
        # 检测事件
        event = detector.detect(
            current_price=price,
            volume=vol,
            buy_volume=buy_vol,
            sell_volume=sell_vol,
            orderbook_imbalance=ob_imbalance,
            price_change_5min=chg_5m,
            price_change_15min=chg_15m,
            symbol=symbol,
        )
        
        print(f"检测结果:")
        print(f"  - 信号类型: {event.signal_type}")
        print(f"  - 事件类型: {event.event_type}")
        print(f"  - 方向: {event.direction}")
        print(f"  - 压力分数: {event.pressure_score:.2f}")
        print(f"  - 信心度: {event.confidence:.2f}")
        print(f"  - 买卖不平衡: {event.buy_sell_imbalance:.2f}")


def example_configs():
    """示例：使用统一配置类型"""
    print("\n" + "=" * 60)
    print("示例 3: 统一配置类型")
    print("=" * 60)
    
    # 1. 创建策略配置
    strategy_config = StrategyConfigV2(
        strategy_id="my_reversal_strategy",
        strategy_name="均值回归策略",
        strategy_type="mean_reversion",
        entry_params=EntryParams(
            signal_threshold=0.6,
            max_entries_per_symbol=2,
        ),
        exit_params=ExitParams(
            stop_loss_pct=0.02,
            take_profit_pct=0.05,
        ),
        risk_params=RiskParams(
            position_size_pct=0.1,
            max_positions=5,
        ),
        supported_symbols=["BTCUSDT", "ETHUSDT"],
    )
    
    print(f"策略配置创建:")
    print(f"  - ID: {strategy_config.strategy_id}")
    print(f"  - 名称: {strategy_config.strategy_name}")
    print(f"  - 入场信号阈值: {strategy_config.entry_params.signal_threshold}")
    print(f"  - 止损: {strategy_config.exit_params.stop_loss_pct:.2%}")
    print(f"  - 仓位大小: {strategy_config.risk_params.position_size_pct:.2%}")
    
    # 2. 序列化和反序列化
    config_dict = strategy_config.to_dict()
    print(f"\n配置已序列化为 dict, 包含 {len(config_dict)} 个字段")
    
    restored_config = StrategyConfigV2.from_dict(config_dict)
    print(f"从 dict 恢复配置，名称匹配: {restored_config.strategy_name == strategy_config.strategy_name}")


def example_integration():
    """示例：集成使用所有组件"""
    print("\n" + "=" * 60)
    print("示例 4: 集成使用 - 从事件检测到状态更新")
    print("=" * 60)
    
    symbol = "BTCUSDT"
    
    # 1. 初始化所有组件
    state_machine = MarketStateMachine(symbol=symbol)
    tp_detector = TradePressureDetector()
    
    # 2. 模拟一个完整的场景
    print(f"\n初始市场状态: {state_machine.current_state.regime}")
    
    # 模拟价格下跌 + 成交量放大
    print("\n场景 1: 压力释放（Flush）")
    tp_event = tp_detector.detect(
        current_price=50000.0,
        volume=300,
        buy_volume=80,
        sell_volume=220,
        orderbook_imbalance=-0.4,
        price_change_5min=-0.03,
        price_change_15min=-0.05,
        symbol=symbol,
    )
    
    if tp_event.event_type:
        print(f"检测到: {tp_event.event_type}")
        print(f"信号: {tp_event.signal_type}")
        
        # 更新市场状态
        features = {
            "pressure_zscore": -2.5,
            "volatility_zscore": 2.0,
            "trend_strength": -0.6,
        }
        new_state = state_machine.update(tp_event.event_type, features)
        
        print(f"市场状态变为: {new_state.regime}")
        print(f"压力状态: {new_state.pressure}")
        print(f"是否耗尽: {new_state.is_exhausted()}")
        
        if new_state.is_exhausted():
            print(">>> 交易信号: 考虑做多反转！")
    
    print("\n示例演示完成！")


if __name__ == "__main__":
    # 运行所有示例
    example_market_state_machine()
    example_trade_pressure_detector()
    example_configs()
    example_integration()
