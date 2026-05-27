"""
Backtest Execution Engine - 完整回测执行引擎

整合所有回测模型：
- FeeModel (手续费)
- SlippageModel (滑点)
- LiquidationModel (爆仓)
- FundingModel (资金费)
- AccountModel (账户)

提供真实交易成本模拟
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .fee_model import FeeModel, FeeResult, FeeType, calculate_fees, Exchange as FeeExchange
from .slippage import SlippageModel, SlippageResult, calculate_slippage, OrderType as SlippageOrderType
from .liquidation import LiquidationModel, LiquidationResult, LiquidationStatus, check_liquidation
from .funding import FundingModel, FundingResult, calculate_funding
from runtime.replay_runtime.account_model import AccountModel, AccountStatus, AccountSnapshot

from domain.execution.models.position import Position
from domain.execution.models.enums import Exchange, MarketType

import logging

logger = logging.getLogger(__name__)


class OrderSide(str, Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class BacktestExecutionConfig:
    """回测执行配置"""
    symbol: str = "BTCUSDT"
    initial_capital: float = 10000.0
    default_leverage: int = 5
    default_order_size: float = 0.01
    maker_fee: float = 0.0002
    taker_fee: float = 0.0005
    base_slippage_bps: float = 1.0
    max_slippage_bps: float = 50.0
    maintenance_margin_rate: float = 0.004
    funding_interval_hours: float = 8.0
    min_order_size: float = 0.0001
    enable_funding: bool = True
    enable_liquidation: bool = True
    enable_slippage: bool = True


@dataclass
class TradeExecutionResult:
    """交易执行结果"""
    success: bool
    
    order_id: str
    symbol: str
    side: OrderSide
    
    requested_price: float
    execution_price: float
    size: float
    
    fee: float
    fee_rate: float
    slippage_bps: float
    
    pnl: float
    realized_pnl: float
    
    position_before: Optional[Dict[str, Any]]
    position_after: Optional[Dict[str, Any]]
    
    account_snapshot: Optional[AccountSnapshot]
    
    liquidation_occurred: bool = False
    liquidation_details: Optional[Dict[str, Any]] = None
    
    error: Optional[str] = None


@dataclass
class BacktestExecutionEngine:
    """
    完整回测执行引擎
    
    整合所有交易成本模型，提供真实的回测环境
    """
    
    config: BacktestExecutionConfig
    account: AccountModel
    
    # 模型
    fee_model: FeeModel = field(default_factory=FeeModel)
    slippage_model: SlippageModel = field(default_factory=SlippageModel)
    liquidation_model: LiquidationModel = field(default_factory=LiquidationModel)
    funding_model: FundingModel = field(default_factory=FundingModel)
    
    # 状态
    _current_position: Optional[Position] = None
    _last_funding_time: Optional[datetime] = None
    _trade_counter: int = 0
    
    def __post_init__(self):
        if self.account is None:
            self.account = AccountModel(initial_balance=self.config.initial_capital)
        
        # 配置模型参数
        self.fee_model.maker_fee = self.config.maker_fee
        self.fee_model.taker_fee = self.config.taker_fee
        
        self.slippage_model.base_slippage_bps = self.config.base_slippage_bps
        self.slippage_model.max_slippage_bps = self.config.max_slippage_bps
        
        self.liquidation_model.maintenance_margin_rate = self.config.maintenance_margin_rate
        
        self.funding_model.funding_interval_hours = self.config.funding_interval_hours
        
        logger.info(f"BacktestExecutionEngine initialized for {self.config.symbol}")
    
    async def execute_order(
        self,
        side: OrderSide,
        size: float,
        price: float,
        order_type: SlippageOrderType = SlippageOrderType.MARKET,
        is_maker: bool = False,
        timestamp_ms: Optional[int] = None,
        current_funding_rate: float = 0.0,
        avg_daily_volume: float = 1000000.0,
        current_spread_bps: float = 2.0,
        volatility: float = 0.002,
        orderbook_depth: float = 100.0,
    ) -> TradeExecutionResult:
        """
        执行订单（完整回测）
        
        Args:
            side: 买卖方向
            size: 订单大小
            price: 当前价格
            order_type: 订单类型
            is_maker: 是否是 maker
            timestamp_ms: 时间戳（毫秒）
            current_funding_rate: 当前资金费率
            avg_daily_volume: 平均日交易量
            current_spread_bps: 当前买卖价差
            volatility: 波动率
            orderbook_depth: 订单簿深度
        """
        self._trade_counter += 1
        order_id = f"order_{self._trade_counter}_{timestamp_ms}"
        
        current_time = datetime.fromtimestamp(timestamp_ms / 1000.0) if timestamp_ms else datetime.now()
        
        try:
            # 1. 验证最小下单量
            if abs(size) < self.config.min_order_size:
                return TradeExecutionResult(
                    success=False,
                    order_id=order_id,
                    symbol=self.config.symbol,
                    side=side,
                    requested_price=price,
                    execution_price=price,
                    size=size,
                    fee=0.0,
                    fee_rate=0.0,
                    slippage_bps=0.0,
                    pnl=0.0,
                    realized_pnl=0.0,
                    position_before=self._get_position_state() if self._current_position else None,
                    position_after=self._get_position_state() if self._current_position else None,
                    account_snapshot=self.account.create_snapshot(),
                    error=f"Order size {size} below minimum {self.config.min_order_size}"
                )
            
            # 2. 检查是否爆仓
            if self.config.enable_liquidation and self._current_position:
                liq_result = self._check_liquidation(price, current_time)
                if liq_result.status == LiquidationStatus.LIQUIDATED:
                    return TradeExecutionResult(
                        success=False,
                        order_id=order_id,
                        symbol=self.config.symbol,
                        side=side,
                        requested_price=price,
                        execution_price=price,
                        size=size,
                        fee=0.0,
                        fee_rate=0.0,
                        slippage_bps=0.0,
                        pnl=0.0,
                        realized_pnl=0.0,
                        position_before=self._get_position_state(),
                        position_after=None,
                        account_snapshot=self.account.create_snapshot(),
                        liquidation_occurred=True,
                        liquidation_details={
                            "liquidation_price": liq_result.liquidation_price,
                            "equity": liq_result.equity
                        },
                        error="Position liquidated before order execution"
                    )
            
            # 3. 保存当前状态
            position_before = self._get_position_state() if self._current_position else None
            
            # 4. 计算滑点
            slippage_result = SlippageResult(
                requested_price=price,
                execution_price=price,
                slippage_bps=0.0,
                slippage_pct=0.0,
                market_impact=0.0,
                liquidity_impact=0.0,
                volatility_impact=0.0,
                total_impact=0.0
            )
            
            if self.config.enable_slippage:
                slippage_result = calculate_slippage(
                    order_type=order_type,
                    side=side.value,
                    size=size,
                    price=price,
                    avg_daily_volume=avg_daily_volume,
                    current_spread_bps=current_spread_bps,
                    volatility=volatility,
                    orderbook_depth=orderbook_depth,
                    model=self.slippage_model
                )
            
            execution_price = slippage_result.execution_price
            
            # 5. 计算手续费
            fee_result = calculate_fees(
                size=size,
                price=execution_price,
                side=side.value,
                is_maker=is_maker,
                exchange=FeeExchange.BINANCE,
                model=self.fee_model
            )
            
            # 6. 处理仓位
            realized_pnl = 0.0
            position_after = None
            
            if side == OrderSide.BUY:
                realized_pnl = self._handle_buy_order(size, execution_price, current_time)
            else:
                realized_pnl = self._handle_sell_order(size, execution_price, current_time)
            
            # 7. 扣除手续费
            self.account.add_fee(fee_result.trading_fee)
            
            # 8. 处理资金费（如果需要）
            if self.config.enable_funding and self._current_position:
                funding_fee = self._process_funding_payment(current_time, current_funding_rate)
                if funding_fee != 0.0:
                    self.account.add_funding(funding_fee)
            
            # 9. 更新未实现盈亏
            self._update_unrealized_pnl(price)
            
            # 10. 获取新状态
            if self._current_position:
                position_after = self._get_position_state()
            
            # 11. 再次检查爆仓
            liquidation_occurred = False
            liquidation_details = None
            
            if self.config.enable_liquidation and self._current_position:
                liq_result = self._check_liquidation(price, current_time)
                if liq_result.status == LiquidationStatus.LIQUIDATED:
                    liquidation_occurred = True
                    liquidation_details = {
                        "liquidation_price": liq_result.liquidation_price,
                        "equity": liq_result.equity
                    }
                    self._liquidate_position(liq_result, price)
            
            # 12. 创建账户快照
            account_snapshot = self.account.create_snapshot()
            
            # 13. 计算总盈亏
            total_pnl = realized_pnl - fee_result.trading_fee
            
            return TradeExecutionResult(
                success=True,
                order_id=order_id,
                symbol=self.config.symbol,
                side=side,
                requested_price=price,
                execution_price=execution_price,
                size=size,
                fee=fee_result.trading_fee,
                fee_rate=fee_result.fee_rate,
                slippage_bps=slippage_result.slippage_bps,
                pnl=total_pnl,
                realized_pnl=realized_pnl,
                position_before=position_before,
                position_after=position_after,
                account_snapshot=account_snapshot,
                liquidation_occurred=liquidation_occurred,
                liquidation_details=liquidation_details
            )
            
        except Exception as e:
            logger.error(f"Order execution failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            return TradeExecutionResult(
                success=False,
                order_id=order_id,
                symbol=self.config.symbol,
                side=side,
                requested_price=price,
                execution_price=price,
                size=size,
                fee=0.0,
                fee_rate=0.0,
                slippage_bps=0.0,
                pnl=0.0,
                realized_pnl=0.0,
                position_before=self._get_position_state() if self._current_position else None,
                position_after=self._get_position_state() if self._current_position else None,
                account_snapshot=self.account.create_snapshot(),
                error=str(e)
            )
    
    def _handle_buy_order(self, size: float, price: float, current_time: datetime) -> float:
        """处理买单"""
        realized_pnl = 0.0
        
        if self._current_position and self._current_position.is_short():
            # 平空或部分平空
            close_size = min(abs(self._current_position.quantity), size)
            
            # 计算平空的盈亏
            entry_price = self._current_position.average_price
            realized_pnl = (entry_price - price) * close_size
            self.account.add_realized_pnl(realized_pnl)
            
            # 更新仓位
            self._current_position.quantity += close_size
            
            if abs(self._current_position.quantity) < 1e-8:
                # 完全平仓
                self._release_position_margin()
                self._current_position = None
            else:
                # 部分平仓，重新计算平均价
                self._recalculate_position_margin(price)
            
            size -= close_size
        
        if size > 1e-8 and self._current_position is None:
            # 新开多单（只有在没有仓位的时候才开）
            self._open_position(OrderSide.BUY, size, price, current_time)
        elif size > 1e-8 and self._current_position and self._current_position.is_long():
            # 加多单
            self._add_to_position(size, price)
        
        return realized_pnl
    
    def _handle_sell_order(self, size: float, price: float, current_time: datetime) -> float:
        """处理卖单"""
        realized_pnl = 0.0
        
        if self._current_position and self._current_position.is_long():
            # 平多或部分平多
            close_size = min(self._current_position.quantity, size)
            
            # 计算平多的盈亏
            entry_price = self._current_position.average_price
            realized_pnl = (price - entry_price) * close_size
            self.account.add_realized_pnl(realized_pnl)
            
            # 更新仓位
            self._current_position.quantity -= close_size
            
            if abs(self._current_position.quantity) < 1e-8:
                # 完全平仓
                self._release_position_margin()
                self._current_position = None
            else:
                # 部分平仓，重新计算平均价
                self._recalculate_position_margin(price)
            
            size -= close_size
        
        if size > 1e-8 and self._current_position is None:
            # 新开空单（只有在没有仓位的时候才开）
            self._open_position(OrderSide.SELL, size, price, current_time)
        elif size > 1e-8 and self._current_position and self._current_position.is_short():
            # 加空单
            self._add_to_position(size, price)
        
        return realized_pnl
    
    def _open_position(self, side: OrderSide, size: float, price: float, current_time: datetime):
        """开新仓位"""
        quantity = size if side == OrderSide.BUY else -size
        
        self._current_position = Position(
            symbol=self.config.symbol,
            exchange=Exchange.BINANCE,
            quantity=quantity,
            average_price=price,
            current_price=price,
            leverage=self.config.default_leverage,
            entry_time=current_time,
            market_type=MarketType.USDT_FUTURES
        )
        
        # 计算保证金
        position_value = abs(quantity * price)
        margin = position_value / self.config.default_leverage
        
        # 检查资金是否足够
        if margin > self.account.available_balance:
            raise ValueError(f"Insufficient balance. Required: {margin}, Available: {self.account.available_balance}")
        
        self.account.add_margin(self.config.symbol, margin)
        self._current_position.margin = margin
        self._current_position.liquidation_price = self._current_position.calculate_liquidation_price()
        
        # 初始化资金费计时器
        if self._last_funding_time is None:
            self._last_funding_time = current_time
    
    def _add_to_position(self, size: float, price: float):
        """加仓"""
        old_quantity = self._current_position.quantity
        old_avg_price = self._current_position.average_price
        
        new_quantity = old_quantity + (size if self._current_position.is_long() else -size)
        
        # 计算新的平均价
        if abs(new_quantity) > 1e-8:
            total_value = abs(old_quantity * old_avg_price) + size * price
            new_avg_price = total_value / abs(new_quantity)
        else:
            new_avg_price = price
        
        self._current_position.quantity = new_quantity
        self._current_position.average_price = new_avg_price
        
        # 更新保证金
        self._recalculate_position_margin(price)
    
    def _recalculate_position_margin(self, current_price: float):
        """重新计算仓位保证金"""
        if self._current_position is None:
            return
        
        position_value = abs(self._current_position.quantity * current_price)
        new_margin = position_value / self.config.default_leverage
        
        old_margin = self._current_position.margin
        
        if new_margin > old_margin:
            delta = new_margin - old_margin
            if delta > self.account.available_balance:
                raise ValueError(f"Insufficient balance for additional margin. Required: {delta}")
            
            self.account.add_margin(self.config.symbol, delta)
        else:
            delta = old_margin - new_margin
            self.account.release_margin(self.config.symbol, delta)
        
        self._current_position.margin = new_margin
        self._current_position.liquidation_price = self._current_position.calculate_liquidation_price()
    
    def _release_position_margin(self):
        """释放仓位保证金"""
        if self._current_position and self._current_position.margin > 0:
            self.account.release_margin(self.config.symbol, self._current_position.margin)
    
    def _check_liquidation(self, current_price: float, current_time: datetime) -> LiquidationResult:
        """检查是否爆仓"""
        if self._current_position is None:
            return LiquidationResult(
                status=LiquidationStatus.SAFE,
                entry_price=0.0,
                current_price=current_price,
                liquidation_price=0.0,
                margin_used=0.0,
                maintenance_margin=0.0,
                available_margin=0.0,
                margin_ratio=0.0,
                distance_to_liquidation_pct=100.0,
                unrealized_pnl=0.0,
                equity=self.account.equity,
                leverage=self.config.default_leverage,
                effective_leverage=0.0
            )
        
        return check_liquidation(
            position_size=self._current_position.quantity,
            entry_price=self._current_position.average_price,
            current_price=current_price,
            leverage=self.config.default_leverage,
            account_balance=self.account.current_balance,
            position_side="long" if self._current_position.is_long() else "short",
            model=self.liquidation_model
        )
    
    def _liquidate_position(self, liq_result: LiquidationResult, execution_price: float):
        """执行爆仓"""
        # 计算爆仓损失
        loss = self.account.current_balance - liq_result.equity
        
        # 扣除所有剩余资金
        self.account.current_balance = max(0.0, liq_result.equity)
        self.account.unrealized_pnl = 0.0
        self.account.used_margin = 0.0
        
        # 清空仓位
        self._current_position = None
        
        logger.warning(f"Position liquidated! Loss: {loss:.2f}")
    
    def _process_funding_payment(self, current_time: datetime, current_funding_rate: float) -> float:
        """处理资金费支付"""
        if self._last_funding_time is None or self._current_position is None:
            return 0.0
        
        hours_since = (current_time - self._last_funding_time).total_seconds() / 3600
        
        if hours_since >= self.config.funding_interval_hours:
            # 到了资金费结算时间
            position_value = abs(self._current_position.quantity * self._current_position.current_price)
            funding_fee = position_value * current_funding_rate
            
            if self._current_position.is_short():
                funding_fee = -funding_fee
            
            self._last_funding_time = current_time
            logger.debug(f"Funding fee applied: {funding_fee:.4f}")
            
            return funding_fee
        
        return 0.0
    
    def _update_unrealized_pnl(self, current_price: float):
        """更新未实现盈亏"""
        if self._current_position is None:
            self.account.update_unrealized_pnl(0.0)
            return
        
        self._current_position.update_price(current_price)
        self.account.update_unrealized_pnl(self._current_position.unrealized_pnl)
    
    def _get_position_state(self) -> Optional[Dict[str, Any]]:
        """获取当前仓位状态"""
        if self._current_position is None:
            return None
        return self._current_position.to_dict()
    
    def get_position(self) -> Optional[Position]:
        """获取当前仓位"""
        return self._current_position
    
    def get_account_state(self) -> Dict[str, Any]:
        """获取账户状态"""
        return self.account.to_dict()
    
    def create_snapshot(self) -> AccountSnapshot:
        """创建账户快照"""
        return self.account.create_snapshot()
    
    def reset(self):
        """重置引擎状态"""
        self.account.reset()
        self._current_position = None
        self._last_funding_time = None
        self._trade_counter = 0
        logger.info("BacktestExecutionEngine reset")


def create_backtest_engine(
    symbol: str = "BTCUSDT",
    initial_capital: float = 10000.0,
    default_leverage: int = 5,
    **kwargs
) -> BacktestExecutionEngine:
    """
    创建回测执行引擎（工厂函数）
    """
    config = BacktestExecutionConfig(
        symbol=symbol,
        initial_capital=initial_capital,
        default_leverage=default_leverage,
        **kwargs
    )
    
    account = AccountModel(initial_balance=initial_capital)
    
    return BacktestExecutionEngine(config=config, account=account)
