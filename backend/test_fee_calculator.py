"""
测试手续费计算器和预计收益计算
"""

from domain.execution import (
    FeeConfig,
    Exchange,
    MarketType,
    FeeCalculator,
)
from domain.execution.config import ContractType


def test_fee_config():
    """测试手续费配置"""
    fee_config = FeeConfig()
    
    print("="*60)
    print("币安手续费配置 (VIP0):")
    print(f"  现货: Maker {fee_config.binance.spot_maker_fee_pct*100:.2f}%, Taker {fee_config.binance.spot_taker_fee_pct*100:.2f}%")
    print(f"  USDT永续: Maker {fee_config.binance.usdt_perpetual_maker_fee_pct*100:.4f}%, Taker {fee_config.binance.usdt_perpetual_taker_fee_pct*100:.4f}%")
    print(f"  USDC永续: Maker {fee_config.binance.usdc_perpetual_maker_fee_pct*100:.4f}%, Taker {fee_config.binance.usdc_perpetual_taker_fee_pct*100:.4f}%")
    print(f"  币本位季度: Maker {fee_config.binance.coin_quarterly_maker_fee_pct*100:.4f}%, Taker {fee_config.binance.coin_quarterly_taker_fee_pct*100:.4f}%")
    print()
    print("OKX手续费配置 (VIP0):")
    print(f"  现货: Maker {fee_config.okx.spot_maker_fee_pct*100:.2f}%, Taker {fee_config.okx.spot_taker_fee_pct*100:.2f}%")
    print(f"  USDT永续: Maker {fee_config.okx.usdt_perpetual_maker_fee_pct*100:.4f}%, Taker {fee_config.okx.usdt_perpetual_taker_fee_pct*100:.4f}%")
    print(f"  USDC永续: Maker {fee_config.okx.usdc_perpetual_maker_fee_pct*100:.4f}%, Taker {fee_config.okx.usdc_perpetual_taker_fee_pct*100:.4f}%")
    print(f"  币本位季度: Maker {fee_config.okx.coin_quarterly_maker_fee_pct*100:.4f}%, Taker {fee_config.okx.coin_quarterly_taker_fee_pct*100:.4f}%")
    print("="*60)
    return fee_config


def test_fee_calculation(fee_config: FeeConfig):
    """测试手续费计算"""
    position_value = 10000.0
    print(f"\n持仓价值: ${position_value:,.2f}")
    print("-"*60)
    
    # 测试币安现货
    fee = FeeCalculator.calculate_trade_cost(
        fee_config, Exchange.BINANCE, MarketType.SPOT, position_value
    )
    print(f"币安现货 Taker: ${fee:,.2f} ({fee/position_value*100:.2f}%)")
    
    # 测试币安USDT永续
    fee = FeeCalculator.calculate_trade_cost(
        fee_config, Exchange.BINANCE, MarketType.USDT_FUTURES, position_value, ContractType.USDT_PERPETUAL
    )
    print(f"币安USDT永续 Taker: ${fee:,.2f} ({fee/position_value*100:.4f}%)")
    
    # 测试OKX现货
    fee = FeeCalculator.calculate_trade_cost(
        fee_config, Exchange.OKX, MarketType.SPOT, position_value
    )
    print(f"OKX现货 Taker: ${fee:,.2f} ({fee/position_value*100:.2f}%)")
    
    # 测试OKX USDT永续
    fee = FeeCalculator.calculate_trade_cost(
        fee_config, Exchange.OKX, MarketType.USDT_FUTURES, position_value, ContractType.USDT_PERPETUAL
    )
    print(f"OKX USDT永续 Taker: ${fee:,.2f} ({fee/position_value*100:.4f}%)")
    
    # 测试双边交易成本
    round_trip_fee = FeeCalculator.calculate_round_trip_cost(
        fee_config, Exchange.BINANCE, MarketType.USDT_FUTURES, position_value, ContractType.USDT_PERPETUAL
    )
    print(f"币安USDT永续双边成本: ${round_trip_fee:,.2f} ({round_trip_fee/position_value*100:.4f}%)")


def test_expected_return(fee_config: FeeConfig):
    """测试预计收益计算"""
    entry_price = 100.0
    stop_loss_price = 98.0
    take_profit_price = 105.0
    
    print("\n" + "="*60)
    print(f"入场价格: ${entry_price}")
    print(f"止损价格: ${stop_loss_price}")
    print(f"止盈价格: ${take_profit_price}")
    print("-"*60)
    
    # 币安USDT永续
    ret = FeeCalculator.calculate_expected_return(
        fee_config,
        Exchange.BINANCE,
        MarketType.USDT_FUTURES,
        entry_price,
        stop_loss_price,
        take_profit_price,
        ContractType.USDT_PERPETUAL
    )
    print("币安USDT永续:")
    print(f"  预计盈利: {ret.expected_profit_pct:.2f}%")
    print(f"  预计亏损: {ret.expected_loss_pct:.2f}%")
    print(f"  风险回报比: {ret.risk_reward_ratio:.2f}")
    print(f"  预计手续费: {ret.estimated_fees_pct:.4f}%")
    print(f"  净预期收益: {ret.net_expected_return_pct:.4f}%")
    
    print()
    
    # OKX USDT永续
    ret = FeeCalculator.calculate_expected_return(
        fee_config,
        Exchange.OKX,
        MarketType.USDT_FUTURES,
        entry_price,
        stop_loss_price,
        take_profit_price,
        ContractType.USDT_PERPETUAL
    )
    print("OKX USDT永续:")
    print(f"  预计盈利: {ret.expected_profit_pct:.2f}%")
    print(f"  预计亏损: {ret.expected_loss_pct:.2f}%")
    print(f"  风险回报比: {ret.risk_reward_ratio:.2f}")
    print(f"  预计手续费: {ret.estimated_fees_pct:.4f}%")
    print(f"  净预期收益: {ret.net_expected_return_pct:.4f}%")
    
    print()
    
    # 币安现货
    ret = FeeCalculator.calculate_expected_return(
        fee_config,
        Exchange.BINANCE,
        MarketType.SPOT,
        entry_price,
        stop_loss_price,
        take_profit_price
    )
    print("币安现货:")
    print(f"  预计盈利: {ret.expected_profit_pct:.2f}%")
    print(f"  预计亏损: {ret.expected_loss_pct:.2f}%")
    print(f"  风险回报比: {ret.risk_reward_ratio:.2f}")
    print(f"  预计手续费: {ret.estimated_fees_pct:.4f}%")
    print(f"  净预期收益: {ret.net_expected_return_pct:.4f}%")
    print("="*60)


if __name__ == "__main__":
    fee_config = test_fee_config()
    test_fee_calculation(fee_config)
    test_expected_return(fee_config)
    print("\n测试完成 ✓")
