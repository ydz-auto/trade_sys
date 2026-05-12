#!/usr/bin/env python3
"""
测试 Risk Service
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.risk_service import (
    RiskService,
    RiskConfig,
    RiskLevel,
    RiskCheckResult,
    TradeRisk,
    init_risk_service
)


def test_risk_service():
    """测试风控服务"""
    print("=" * 70)
    print("测试 Risk Service")
    print("=" * 70)

    # 初始化
    config = RiskConfig(
        max_position_size=0.1,
        max_single_loss=0.02,
        max_daily_loss=0.05,
        max_drawdown=0.15,
        stop_loss_pct=0.02,
        take_profit_pct=0.05
    )
    risk_service = init_risk_service(config)

    print("\n📊 风控配置:")
    print(f"   最大仓位: {config.max_position_size:.0%}")
    print(f"   单笔最大亏损: {config.max_single_loss:.0%}")
    print(f"   日内最大亏损: {config.max_daily_loss:.0%}")
    print(f"   最大回撤: {config.max_drawdown:.0%}")
    print(f"   止损比例: {config.stop_loss_pct:.0%}")
    print(f"   止盈比例: {config.take_profit_pct:.0%}")

    # 测试正常信号
    print("\n" + "=" * 70)
    print("测试正常信号")
    print("=" * 70)

    report = risk_service.check_signal({
        "action": "LONG",
        "symbol": "BTC",
        "quantity": 0.01,
        "price": 50000.0,
        "confidence": 0.8
    })

    print(f"\n{'✅' if report.check_result == RiskCheckResult.PASSED else '❌'} 检查结果: {report.check_result.value}")
    print(f"   风险等级: {report.risk_level.value}")

    if report.rejected_reason:
        print(f"   拒绝原因: {report.rejected_reason}")

    if report.warnings:
        print(f"   警告: {', '.join(report.warnings)}")

    # 测试仓位过大
    print("\n" + "=" * 70)
    print("测试仓位过大")
    print("=" * 70)

    report = risk_service.check_signal({
        "action": "LONG",
        "symbol": "BTC",
        "quantity": 20.0,  # 仓位太大
        "price": 50000.0,
        "confidence": 0.8
    })

    print(f"\n{'✅' if report.check_result == RiskCheckResult.PASSED else '❌'} 检查结果: {report.check_result.value}")
    print(f"   风险等级: {report.risk_level.value}")

    if report.rejected_reason:
        print(f"   拒绝原因: {report.rejected_reason}")

    # 测试止损检查
    print("\n" + "=" * 70)
    print("测试止损检查")
    print("=" * 70)

    # 添加持仓
    risk_service.add_position(
        symbol="ETH",
        quantity=10.0,
        entry_price=3000.0,
        current_price=3000.0
    )

    print(f"\n添加持仓: ETH 10 @ 3000")

    # 价格下跌到止损位
    should_stop = risk_service.check_stop_loss("ETH", 2940.0)  # 2% 下跌
    print(f"\n价格 2940 (止损位 2940): {'触发止损!' if should_stop else '未触发'}")

    # 测试持仓风险
    print("\n" + "=" * 70)
    print("持仓风险")
    print("=" * 70)

    positions = risk_service.get_positions_risk()
    for pos in positions:
        print(f"\n  {pos.symbol}:")
        print(f"    数量: {pos.quantity}")
        print(f"    入场价: {pos.entry_price}")
        print(f"    当前价: {pos.current_price}")
        print(f"    浮盈: {pos.unrealized_pnl:.2f} ({pos.pnl_pct:.2%})")
        print(f"    止损: {pos.stop_loss}")
        print(f"    止盈: {pos.take_profit}")

    # 测试风控指标
    print("\n" + "=" * 70)
    print("风控指标")
    print("=" * 70)

    metrics = risk_service.get_metrics()
    print(f"\n  当前权益: ${metrics['current_equity']:,.2f}")
    print(f"  峰值权益: ${metrics['peak_equity']:,.2f}")
    print(f"  回撤: {metrics['drawdown']:.2%}")
    print(f"  日内盈亏: ${metrics['daily_pnl']:,.2f}")
    print(f"  总交易: {metrics['total_trades']}")
    print(f"  胜率: {metrics['win_rate']:.2%}")
    print(f"  持仓数: {metrics['positions_count']}")
    print(f"  风险敞口: {metrics['exposure_ratio']:.2%}")

    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)

    print("\n使用说明:")
    print("""
风控服务会自动检查：
1. 仓位大小 - 防止仓位过大
2. 单笔亏损 - 防止单笔损失过大
3. 日内亏损 - 防止日内连续亏损
4. 最大回撤 - 防止资金大幅缩水
5. 止损止盈 - 保护利润和控制亏损

集成到决策流程：
1. Strategy Service 产生信号
2. Risk Service 检查信号
3. 如果通过，执行订单
4. 如果拒绝，记录原因
""")


if __name__ == "__main__":
    test_risk_service()
