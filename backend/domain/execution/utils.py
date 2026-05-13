"""
Execution Utilities

执行相关的工具函数
包括手续费计算、预计收益计算等
"""

from typing import Optional, Tuple
from dataclasses import dataclass
from domain.execution.config import (
    FeeConfig,
    ExchangeFeeConfig,
    ContractType,
)
from domain.execution.models.enums import Exchange, MarketType


@dataclass
class ExpectedReturn:
    """预计收益信息"""
    expected_profit_pct: float
    expected_loss_pct: float
    risk_reward_ratio: float
    estimated_fees_pct: float
    net_expected_return_pct: float


class FeeCalculator:
    """手续费计算器"""

    @staticmethod
    def get_fee_config(
        fee_config: FeeConfig,
        exchange: Exchange
    ) -> ExchangeFeeConfig:
        """获取对应交易所的手续费配置"""
        if exchange == Exchange.BINANCE:
            return fee_config.binance
        elif exchange == Exchange.OKX:
            return fee_config.okx
        else:
            return fee_config.binance

    @staticmethod
    def get_fees(
        fee_config: FeeConfig,
        exchange: Exchange,
        market_type: MarketType,
        contract_type: Optional[ContractType] = None,
        is_taker: bool = True
    ) -> float:
        """
        获取手续费率

        Args:
            fee_config: 手续费配置
            exchange: 交易所
            market_type: 市场类型（现货/合约）
            contract_type: 合约类型（仅合约需要）
            is_taker: 是否为Taker

        Returns:
            手续费率（小数）
        """
        exch_fee = FeeCalculator.get_fee_config(fee_config, exchange)

        if market_type == MarketType.SPOT:
            return exch_fee.spot_taker_fee_pct if is_taker else exch_fee.spot_maker_fee_pct
        else:
            ct = contract_type or ContractType.USDT_PERPETUAL
            if ct == ContractType.USDT_PERPETUAL:
                return exch_fee.usdt_perpetual_taker_fee_pct if is_taker else exch_fee.usdt_perpetual_maker_fee_pct
            elif ct == ContractType.USDC_PERPETUAL:
                return exch_fee.usdc_perpetual_taker_fee_pct if is_taker else exch_fee.usdc_perpetual_maker_fee_pct
            else:
                return exch_fee.coin_quarterly_taker_fee_pct if is_taker else exch_fee.coin_quarterly_maker_fee_pct

    @staticmethod
    def calculate_trade_cost(
        fee_config: FeeConfig,
        exchange: Exchange,
        market_type: MarketType,
        position_value: float,
        contract_type: Optional[ContractType] = None,
        is_taker: bool = True
    ) -> float:
        """
        计算单次交易成本

        Args:
            fee_config: 手续费配置
            exchange: 交易所
            market_type: 市场类型
            position_value: 持仓价值
            contract_type: 合约类型
            is_taker: 是否为Taker

        Returns:
            手续费金额
        """
        fee_pct = FeeCalculator.get_fees(
            fee_config,
            exchange,
            market_type,
            contract_type,
            is_taker
        )
        return position_value * fee_pct

    @staticmethod
    def calculate_round_trip_cost(
        fee_config: FeeConfig,
        exchange: Exchange,
        market_type: MarketType,
        position_value: float,
        contract_type: Optional[ContractType] = None,
        is_taker_entry: bool = True,
        is_taker_exit: bool = True
    ) -> float:
        """
        计算完整交易对的成本（开仓+平仓）

        Args:
            fee_config: 手续费配置
            exchange: 交易所
            market_type: 市场类型
            position_value: 持仓价值
            contract_type: 合约类型
            is_taker_entry: 开仓是否Taker
            is_taker_exit: 平仓是否Taker

        Returns:
            总手续费金额
        """
        entry_fee = FeeCalculator.calculate_trade_cost(
            fee_config, exchange, market_type, position_value, contract_type, is_taker_entry
        )
        exit_fee = FeeCalculator.calculate_trade_cost(
            fee_config, exchange, market_type, position_value, contract_type, is_taker_exit
        )
        return entry_fee + exit_fee

    @staticmethod
    def calculate_expected_return(
        fee_config: FeeConfig,
        exchange: Exchange,
        market_type: MarketType,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        contract_type: Optional[ContractType] = None,
        is_taker_entry: bool = True,
        is_taker_exit: bool = True
    ) -> ExpectedReturn:
        """
        计算预计收益

        Args:
            fee_config: 手续费配置
            exchange: 交易所
            market_type: 市场类型
            entry_price: 入场价格
            stop_loss_price: 止损价格
            take_profit_price: 止盈价格
            contract_type: 合约类型
            is_taker_entry: 开仓是否Taker
            is_taker_exit: 平仓是否Taker

        Returns:
            预计收益信息
        """
        # 计算盈亏百分比
        price_range = take_profit_price - entry_price
        loss_range = entry_price - stop_loss_price

        expected_profit_pct = (price_range / entry_price) * 100
        expected_loss_pct = (loss_range / entry_price) * 100

        # 估算双边手续费
        position_value = 1.0
        round_trip_fee = FeeCalculator.calculate_round_trip_cost(
            fee_config, exchange, market_type, position_value, contract_type,
            is_taker_entry, is_taker_exit
        )
        estimated_fees_pct = round_trip_fee * 100

        # 计算净预期收益
        win_rate = 0.5
        net_expected_return_pct = (
            win_rate * expected_profit_pct -
            (1 - win_rate) * expected_loss_pct -
            estimated_fees_pct
        )

        # 计算风险回报比
        if expected_loss_pct > 0:
            risk_reward_ratio = expected_profit_pct / expected_loss_pct
        else:
            risk_reward_ratio = float('inf')

        return ExpectedReturn(
            expected_profit_pct=expected_profit_pct,
            expected_loss_pct=expected_loss_pct,
            risk_reward_ratio=risk_reward_ratio,
            estimated_fees_pct=estimated_fees_pct,
            net_expected_return_pct=net_expected_return_pct
        )
