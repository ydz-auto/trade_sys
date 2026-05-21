"""
Generate Symbol-Specific Strategy Configs
生成币种专属策略配置文件
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from domain.strategy.symbol_config import (
    SymbolStrategyConfigManager,
    SymbolStrategyConfig,
    RiskParams,
    RSIStrategyParams,
    MACDStrategyParams,
    PanicReversalParams,
    LongLiquidationBounceParams,
    VolumeClimaxFadeParams,
    WeakBounceShortParams,
)


def generate_btc_config() -> SymbolStrategyConfig:
    """生成BTC配置"""
    return SymbolStrategyConfig(
        symbol="BTCUSDT",
        base_currency="BTC",
        quote_currency="USDT",
        enabled=True,
        description="Bitcoin - 高流动性、中等波动率币种",
        volatility_profile="medium",
        liquidity_profile="high",
        risk=RiskParams(
            position_size=0.025,
            max_leverage=25,
            min_leverage=10,
            stop_loss_pct=10.0,
            take_profit_pct=20.0,
            max_position_value=20000.0,
        ),
        rsi_strategy=RSIStrategyParams(
            period=14,
            oversold=28.0,
            overbought=72.0,
            default_quantity=0.01,
        ),
        macd_strategy=MACDStrategyParams(
            fast_period=12,
            slow_period=26,
            signal_period=9,
            default_quantity=0.01,
        ),
        panic_reversal=PanicReversalParams(
            drop_threshold=-0.018,
            volume_ratio_threshold=1.6,
            default_quantity=0.012,
        ),
        long_liquidation_bounce=LongLiquidationBounceParams(
            drop_threshold=-0.022,
            rsi_threshold=24.0,
            volume_ratio_threshold=2.0,
            default_quantity=0.012,
        ),
        volume_climax_fade=VolumeClimaxFadeParams(
            volume_ratio_threshold=2.2,
            upper_shadow_threshold=0.32,
            price_threshold=0.0035,
            default_quantity=0.008,
        ),
        weak_bounce_short=WeakBounceShortParams(
            drop_threshold_4h=-0.022,
            bounce_min=0.0035,
            bounce_max=0.016,
            volume_ratio_threshold=1.6,
            default_quantity=0.008,
        ),
        primary_timeframe="1h",
        confirmation_timeframe="4h",
        factor_weights={
            "momentum": 0.35,
            "trend": 0.30,
            "flow": 0.20,
            "sentiment": 0.15,
        },
    )


def generate_eth_config() -> SymbolStrategyConfig:
    """生成ETH配置"""
    return SymbolStrategyConfig(
        symbol="ETHUSDT",
        base_currency="ETH",
        quote_currency="USDT",
        enabled=True,
        description="Ethereum - 高流动性、中高波动率币种",
        volatility_profile="medium",
        liquidity_profile="high",
        risk=RiskParams(
            position_size=0.022,
            max_leverage=22,
            min_leverage=10,
            stop_loss_pct=10.0,
            take_profit_pct=20.0,
            max_position_value=15000.0,
        ),
        rsi_strategy=RSIStrategyParams(
            period=14,
            oversold=26.0,
            overbought=74.0,
            default_quantity=0.08,
        ),
        macd_strategy=MACDStrategyParams(
            fast_period=12,
            slow_period=26,
            signal_period=9,
            default_quantity=0.08,
        ),
        panic_reversal=PanicReversalParams(
            drop_threshold=-0.02,
            volume_ratio_threshold=1.5,
            default_quantity=0.1,
        ),
        long_liquidation_bounce=LongLiquidationBounceParams(
            drop_threshold=-0.025,
            rsi_threshold=22.0,
            volume_ratio_threshold=1.9,
            default_quantity=0.1,
        ),
        volume_climax_fade=VolumeClimaxFadeParams(
            volume_ratio_threshold=2.0,
            upper_shadow_threshold=0.35,
            price_threshold=0.004,
            default_quantity=0.06,
        ),
        weak_bounce_short=WeakBounceShortParams(
            drop_threshold_4h=-0.025,
            bounce_min=0.004,
            bounce_max=0.018,
            volume_ratio_threshold=1.5,
            default_quantity=0.06,
        ),
        primary_timeframe="1h",
        confirmation_timeframe="4h",
        factor_weights={
            "momentum": 0.32,
            "trend": 0.30,
            "flow": 0.23,
            "sentiment": 0.15,
        },
    )


def generate_sol_config() -> SymbolStrategyConfig:
    """生成SOL配置"""
    return SymbolStrategyConfig(
        symbol="SOLUSDT",
        base_currency="SOL",
        quote_currency="USDT",
        enabled=True,
        description="Solana - 高波动率、中等流动性币种",
        volatility_profile="high",
        liquidity_profile="medium",
        risk=RiskParams(
            position_size=0.015,
            max_leverage=15,
            min_leverage=8,
            stop_loss_pct=8.0,
            take_profit_pct=18.0,
            max_position_value=8000.0,
        ),
        rsi_strategy=RSIStrategyParams(
            period=12,
            oversold=22.0,
            overbought=78.0,
            default_quantity=1.5,
        ),
        macd_strategy=MACDStrategyParams(
            fast_period=10,
            slow_period=24,
            signal_period=8,
            default_quantity=1.5,
        ),
        panic_reversal=PanicReversalParams(
            drop_threshold=-0.028,
            volume_ratio_threshold=1.8,
            default_quantity=1.8,
        ),
        long_liquidation_bounce=LongLiquidationBounceParams(
            drop_threshold=-0.035,
            rsi_threshold=20.0,
            volume_ratio_threshold=2.2,
            default_quantity=1.8,
        ),
        volume_climax_fade=VolumeClimaxFadeParams(
            volume_ratio_threshold=2.5,
            upper_shadow_threshold=0.4,
            price_threshold=0.005,
            default_quantity=1.0,
        ),
        weak_bounce_short=WeakBounceShortParams(
            drop_threshold_4h=-0.035,
            bounce_min=0.005,
            bounce_max=0.022,
            volume_ratio_threshold=1.7,
            default_quantity=1.0,
        ),
        primary_timeframe="30m",
        confirmation_timeframe="2h",
        factor_weights={
            "momentum": 0.38,
            "trend": 0.25,
            "flow": 0.25,
            "sentiment": 0.12,
        },
    )


def generate_avax_config() -> SymbolStrategyConfig:
    """生成AVAX配置"""
    return SymbolStrategyConfig(
        symbol="AVAXUSDT",
        base_currency="AVAX",
        quote_currency="USDT",
        enabled=True,
        description="Avalanche - 高波动率币种",
        volatility_profile="high",
        liquidity_profile="medium",
        risk=RiskParams(
            position_size=0.012,
            max_leverage=12,
            min_leverage=8,
            stop_loss_pct=8.0,
            take_profit_pct=18.0,
            max_position_value=6000.0,
        ),
        rsi_strategy=RSIStrategyParams(
            period=12,
            oversold=24.0,
            overbought=76.0,
            default_quantity=5.0,
        ),
        macd_strategy=MACDStrategyParams(
            fast_period=10,
            slow_period=24,
            signal_period=8,
            default_quantity=5.0,
        ),
        panic_reversal=PanicReversalParams(
            drop_threshold=-0.025,
            volume_ratio_threshold=1.7,
            default_quantity=6.0,
        ),
        long_liquidation_bounce=LongLiquidationBounceParams(
            drop_threshold=-0.032,
            rsi_threshold=21.0,
            volume_ratio_threshold=2.1,
            default_quantity=6.0,
        ),
        volume_climax_fade=VolumeClimaxFadeParams(
            volume_ratio_threshold=2.3,
            upper_shadow_threshold=0.38,
            price_threshold=0.0045,
            default_quantity=3.5,
        ),
        weak_bounce_short=WeakBounceShortParams(
            drop_threshold_4h=-0.032,
            bounce_min=0.0045,
            bounce_max=0.02,
            volume_ratio_threshold=1.6,
            default_quantity=3.5,
        ),
        primary_timeframe="30m",
        confirmation_timeframe="2h",
        factor_weights={
            "momentum": 0.36,
            "trend": 0.26,
            "flow": 0.26,
            "sentiment": 0.12,
        },
    )


def generate_doge_config() -> SymbolStrategyConfig:
    """生成DOGE配置"""
    return SymbolStrategyConfig(
        symbol="DOGEUSDT",
        base_currency="DOGE",
        quote_currency="USDT",
        enabled=False,  # 默认不启用，因为波动太大
        description="Dogecoin - 极高波动率、投机性币种",
        volatility_profile="high",
        liquidity_profile="medium",
        risk=RiskParams(
            position_size=0.008,
            max_leverage=8,
            min_leverage=5,
            stop_loss_pct=6.0,
            take_profit_pct=15.0,
            max_position_value=3000.0,
        ),
        rsi_strategy=RSIStrategyParams(
            period=10,
            oversold=20.0,
            overbought=80.0,
            default_quantity=5000.0,
        ),
        macd_strategy=MACDStrategyParams(
            fast_period=8,
            slow_period=22,
            signal_period=7,
            default_quantity=5000.0,
        ),
        panic_reversal=PanicReversalParams(
            drop_threshold=-0.035,
            volume_ratio_threshold=2.2,
            default_quantity=6000.0,
        ),
        long_liquidation_bounce=LongLiquidationBounceParams(
            drop_threshold=-0.045,
            rsi_threshold=18.0,
            volume_ratio_threshold=2.5,
            default_quantity=6000.0,
        ),
        volume_climax_fade=VolumeClimaxFadeParams(
            volume_ratio_threshold=3.0,
            upper_shadow_threshold=0.45,
            price_threshold=0.006,
            default_quantity=3500.0,
        ),
        weak_bounce_short=WeakBounceShortParams(
            drop_threshold_4h=-0.045,
            bounce_min=0.006,
            bounce_max=0.028,
            volume_ratio_threshold=2.0,
            default_quantity=3500.0,
        ),
        primary_timeframe="15m",
        confirmation_timeframe="1h",
        factor_weights={
            "momentum": 0.40,
            "trend": 0.20,
            "flow": 0.25,
            "sentiment": 0.15,
        },
    )


def main():
    """主函数：生成所有配置文件"""
    config_dir = Path(__file__).parent.parent / "config" / "strategy" / "symbols"
    
    manager = SymbolStrategyConfigManager(str(config_dir))
    
    # 生成配置
    configs = [
        generate_btc_config(),
        generate_eth_config(),
        generate_sol_config(),
        generate_avax_config(),
        generate_doge_config(),
    ]
    
    # 保存配置
    for config in configs:
        try:
            manager.save_config(config, overwrite=True)
            print(f"✓ Generated config for {config.symbol}")
        except Exception as e:
            print(f"✗ Failed to save {config.symbol}: {e}")
    
    # 验证加载
    print("\n验证配置加载:")
    manager.reload_all()
    enabled_symbols = manager.get_enabled_symbols()
    print(f"启用的币种: {enabled_symbols}")
    
    for symbol in enabled_symbols:
        config = manager.get_config(symbol)
        if config:
            print(f"  - {symbol}: {config.description}")
    
    print("\n✓ 配置生成完成!")


if __name__ == "__main__":
    main()
