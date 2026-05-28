from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import asyncio
import json
import math

from infrastructure.logging import get_logger
from runtime.replay_runtime.models.fee_model import FeeModel, FeeType
from runtime.replay_runtime.models.liquidation import LiquidationModel, LiquidationStatus
from runtime.replay_runtime.models.funding import FundingModel

logger = get_logger("backtest_service")


class SignalType(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    side: SignalType
    leverage: float = 1.0
    entry_fee: float = 0.0
    exit_fee: float = 0.0
    funding_fee: float = 0.0
    liquidated: bool = False


@dataclass
class PerformanceMetrics:
    total_return: float = 0.0
    total_return_pct: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    avg_trade_return: float = 0.0
    avg_trade_duration: float = 0.0
    total_fees: float = 0.0
    liquidation_count: int = 0


@dataclass
class BacktestConfig:
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.0005
    position_size: float = 0.1
    stop_loss: float = 0.02
    take_profit: float = 0.05
    leverage: float = 1.0
    stop_loss_type: str = "price"
    maintenance_margin_rate: float = 0.005
    use_realistic_fees: bool = True
    data_frequency_minutes: int = 60
    compound: bool = False


@dataclass
class BacktestResult:
    config: BacktestConfig
    metrics: PerformanceMetrics
    trades: List[Trade]
    equity_curve: List[float]
    drawdown_curve: List[float]
    start_date: datetime
    end_date: datetime
    duration_days: int


class MockDataGenerator:

    @staticmethod
    def generate_bars(
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_price: float = 50000.0,
        volatility: float = 0.02
    ) -> List[Bar]:
        import random
        bars = []
        current_price = initial_price
        current_date = start_date

        while current_date <= end_date:
            if current_date.weekday() < 5:
                change = random.gauss(0, volatility)
                open_price = current_price
                close_price = current_price * (1 + change)

                high_price = max(open_price, close_price) * (1 + abs(change) * 0.5)
                low_price = min(open_price, close_price) * (1 - abs(change) * 0.5)

                volume = random.uniform(1000, 10000)

                bars.append(Bar(
                    timestamp=current_date,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume
                ))

                current_price = close_price

            current_date += timedelta(days=1)

        return bars


class BacktestEngine:

    def __init__(self, config: BacktestConfig = None, enable_gpu: bool = True):
        self.config = config or BacktestConfig()
        self._bars: List[Bar] = []
        self._trades: List[Trade] = []
        self._equity_curve: List[float] = []
        self._drawdown_curve: List[float] = []
        self._position: Optional[Dict] = None
        self._capital: float = 0.0
        self._peak_capital: float = 0.0

        self._fee_model = FeeModel()
        self._liquidation_model = LiquidationModel(
            maintenance_margin_rate=self.config.maintenance_margin_rate
        )
        self._funding_model = FundingModel()
        
        self._total_fees: float = 0.0
        self._liquidation_count: int = 0
        self._last_funding_time: Optional[datetime] = None
        self._current_funding_rate: float = 0.0

        self._enable_gpu = enable_gpu
        self._gpu_available = False
        self._gpu_feature_calculator = None

    def _init_gpu(self):
        if not self._enable_gpu:
            return

        try:
            from infrastructure.acceleration import is_gpu_available, get_accelerator_info
            from engines.compute.feature.torch_calculator import TorchFeatureCalculator

            info = get_accelerator_info()
            self._gpu_available = info['is_gpu']

            if self._gpu_available:
                self._gpu_feature_calculator = TorchFeatureCalculator()
                logger.info(f"BacktestEngine GPU acceleration enabled: {info['device_type']}")
            else:
                logger.info("BacktestEngine using CPU (GPU not available)")

        except ImportError as e:
            logger.warning(f"GPU acceleration not available: {e}")
            self._gpu_available = False
        except Exception as e:
            logger.warning(f"GPU initialization failed: {e}")
            self._gpu_available = False

    def compute_features_gpu(self, bars: List[Bar]) -> List[Dict[str, Any]]:
        if not self._gpu_available or not self._gpu_feature_calculator:
            self._init_gpu()

        if not self._gpu_available:
            return self._compute_features_cpu(bars)

        try:
            import pandas as pd

            df = pd.DataFrame([
                {
                    'timestamp': bar.timestamp,
                    'open': bar.open,
                    'high': bar.high,
                    'low': bar.low,
                    'close': bar.close,
                    'volume': bar.volume,
                }
                for bar in bars
            ])

            features_df = self._gpu_feature_calculator.compute_batch(df, use_gpu=True)

            features_list = []
            for idx, row in features_df.iterrows():
                feature_dict = {
                    'timestamp': row.get('timestamp'),
                    'close': row.get('close'),
                }
                for col in features_df.columns:
                    if col not in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
                        feature_dict[col] = row[col]
                features_list.append(feature_dict)

            return features_list

        except Exception as e:
            logger.error(f"GPU feature computation failed: {e}")
            return self._compute_features_cpu(bars)

    def _compute_features_cpu(self, bars: List[Bar]) -> List[Dict[str, Any]]:
        features_list = []

        for i, bar in enumerate(bars):
            feature_dict = {
                'timestamp': bar.timestamp,
                'close': bar.close,
            }

            if i >= 14:
                closes = [b.close for b in bars[max(0, i-14):i+1]]
                deltas = [closes[j+1] - closes[j] for j in range(len(closes)-1)]
                gains = [d for d in deltas if d > 0]
                losses = [-d for d in deltas if d < 0]

                avg_gain = sum(gains) / 14 if gains else 0
                avg_loss = sum(losses) / 14 if losses else 0

                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))

                feature_dict['rsi_14'] = rsi

            if i >= 20:
                closes = [b.close for b in bars[max(0, i-20):i+1]]
                sma = sum(closes) / len(closes)
                feature_dict['sma_20'] = sma

            features_list.append(feature_dict)

        return features_list

    def load_data(self, bars: List[Bar]) -> "BacktestEngine":
        self._bars = sorted(bars, key=lambda x: x.timestamp)
        return self

    def load_mock_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        initial_price: float = 50000.0
    ) -> "BacktestEngine":
        self._bars = MockDataGenerator.generate_bars(
            symbol, start_date, end_date, initial_price
        )
        return self

    def run(
        self,
        signal_generator: Callable[[Bar, Optional[Dict]], SignalType]
    ) -> BacktestResult:
        if not self._bars:
            raise ValueError("No data loaded")

        self._trades = []
        self._equity_curve = []
        self._drawdown_curve = []
        self._position = None
        self._capital = self.config.initial_capital
        self._peak_capital = self.config.initial_capital
        self._total_fees = 0.0
        self._liquidation_count = 0

        peak_equity = self._capital

        for i, bar in enumerate(self._bars):
            signal = signal_generator(bar, self._position)

            if self._position:
                if i > 0:
                    hours_passed = (bar.timestamp - self._bars[i-1].timestamp).total_seconds() / 3600
                    self._position["holding_hours"] = self._position.get("holding_hours", 0.0) + hours_passed
                
                if self._position["side"] == SignalType.BUY:
                    pnl_pct = (bar.close - self._position["entry_price"]) / self._position["entry_price"] * self.config.leverage
                else:
                    pnl_pct = (self._position["entry_price"] - bar.close) / self._position["entry_price"] * self.config.leverage
                
                stop_loss_triggered = False
                if self.config.stop_loss_type == "price":
                    if pnl_pct <= -self.config.stop_loss:
                        stop_loss_triggered = True
                elif self.config.stop_loss_type == "capital":
                    if pnl_pct * self.config.position_size <= -self.config.stop_loss:
                        stop_loss_triggered = True
                
                liquidated = False
                if self.config.use_realistic_fees and self.config.leverage > 1:
                    liq_result = self._liquidation_model.check(
                        self._position["quantity"],
                        self._position["entry_price"],
                        bar.close,
                        self.config.leverage,
                        self._capital,
                        "long" if self._position["side"] == SignalType.BUY else "short"
                    )
                    if liq_result.status == LiquidationStatus.LIQUIDATED:
                        liquidated = True
                
                if liquidated:
                    self._close_position(bar, "liquidation", True)
                elif stop_loss_triggered:
                    self._close_position(bar, "stop_loss")
                elif pnl_pct >= self.config.take_profit:
                    self._close_position(bar, "take_profit")
                elif signal == (SignalType.SELL if self._position["side"] == SignalType.BUY else SignalType.BUY):
                    self._close_position(bar, "signal")

            if not self._position and signal != SignalType.HOLD:
                self._open_position(bar, signal)

            current_equity = self._capital
            if self._position:
                if self._position["side"] == SignalType.BUY:
                    pos_pnl = (bar.close - self._position["entry_price"]) * self._position["quantity"]
                else:
                    pos_pnl = (self._position["entry_price"] - bar.close) * self._position["quantity"]
                current_equity += pos_pnl + self._position["margin_used"]

            self._equity_curve.append(current_equity)
            
            if current_equity > self._peak_capital:
                self._peak_capital = current_equity

            if current_equity > peak_equity:
                peak_equity = current_equity
            drawdown = peak_equity - current_equity
            drawdown_pct = drawdown / peak_equity if peak_equity > 0 else 0
            self._drawdown_curve.append(drawdown_pct)

        if self._position:
            self._close_position(self._bars[-1], "end")

        metrics = self._calculate_metrics()

        return BacktestResult(
            config=self.config,
            metrics=metrics,
            trades=self._trades,
            equity_curve=self._equity_curve,
            drawdown_curve=self._drawdown_curve,
            start_date=self._bars[0].timestamp if self._bars else datetime.now(),
            end_date=self._bars[-1].timestamp if self._bars else datetime.now(),
            duration_days=len(self._bars)
        )

    def _open_position(self, bar: Bar, signal: SignalType):
        if self.config.compound:
            available_capital = self._capital
        else:
            available_capital = self.config.initial_capital
            
        position_value = available_capital * self.config.position_size
        notional_value = position_value * self.config.leverage
        quantity = notional_value / bar.close
        
        entry_price = bar.close * (1 + self.config.slippage if signal == SignalType.BUY else 1 - self.config.slippage)
        
        margin_used = position_value
        
        if margin_used > self._capital:
            return
        
        entry_fee = 0.0
        if self.config.use_realistic_fees:
            fee_result = self._fee_model.calculate(
                quantity, entry_price, "buy" if signal == SignalType.BUY else "sell", False
            )
            entry_fee = fee_result.total_fee
        
        total_cost = margin_used + entry_fee
        
        if total_cost > self._capital:
            return

        self._position = {
            "entry_time": bar.timestamp,
            "entry_price": entry_price,
            "quantity": quantity,
            "side": signal,
            "margin_used": margin_used,
            "notional_value": notional_value,
            "leverage": self.config.leverage,
            "entry_fee": entry_fee,
            "holding_hours": 0.0
        }

        self._capital -= total_cost
        self._total_fees += entry_fee
        
        if self._last_funding_time is None:
            self._last_funding_time = bar.timestamp

    def _close_position(self, bar: Bar, reason: str, liquidated: bool = False):
        if not self._position:
            return

        exit_price = bar.close * (1 - self.config.slippage) if self._position["side"] == SignalType.BUY else bar.close * (1 + self.config.slippage)
        
        if self._position["side"] == SignalType.BUY:
            price_change_pct = (exit_price - self._position["entry_price"]) / self._position["entry_price"]
        else:
            price_change_pct = (self._position["entry_price"] - exit_price) / self._position["entry_price"]
        
        pnl = price_change_pct * self._position["notional_value"]
        
        exit_fee = 0.0
        funding_fee = 0.0
        if self.config.use_realistic_fees:
            fee_result = self._fee_model.calculate(
                self._position["quantity"], exit_price, "sell" if self._position["side"] == SignalType.BUY else "buy", False
            )
            exit_fee = fee_result.total_fee
            
            holding_hours = self._position.get("holding_hours", 0.0)
            if holding_hours > 0 and self._current_funding_rate != 0:
                funding_result = self._funding_model.calculate_holding_cost(
                    self._position["notional_value"],
                    self._current_funding_rate,
                    holding_hours,
                    "long" if self._position["side"] == SignalType.BUY else "short"
                )
                funding_fee = funding_result["total_funding_cost"]
        
        net_pnl = pnl - exit_fee - abs(funding_fee)
        
        capital_return = self._position["margin_used"] + net_pnl
        
        trade = Trade(
            entry_time=self._position["entry_time"],
            exit_time=bar.timestamp,
            entry_price=self._position["entry_price"],
            exit_price=exit_price,
            quantity=self._position["quantity"],
            pnl=net_pnl,
            pnl_pct=net_pnl / self._position["margin_used"] if self._position["margin_used"] > 0 else 0,
            side=self._position["side"],
            leverage=self._position["leverage"],
            entry_fee=self._position.get("entry_fee", 0.0),
            exit_fee=exit_fee,
            funding_fee=funding_fee,
            liquidated=liquidated
        )

        self._trades.append(trade)
        self._total_fees += exit_fee + abs(funding_fee)
        
        if liquidated:
            self._liquidation_count += 1
            self._capital += max(0, capital_return)
        else:
            self._capital += max(0, capital_return)
            
        self._position = None

    def _calculate_metrics(self) -> PerformanceMetrics:
        if not self._equity_curve:
            return PerformanceMetrics()

        total_return = self._equity_curve[-1] - self.config.initial_capital
        total_return_pct = total_return / self.config.initial_capital

        peak = self.config.initial_capital
        max_drawdown = 0.0
        for equity in self._equity_curve:
            if equity > peak:
                peak = equity
            drawdown = peak - equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        max_drawdown_pct = max_drawdown / peak if peak > 0 else 0

        total_trades = len(self._trades)
        winning_trades = sum(1 for t in self._trades if t.pnl > 0)
        losing_trades = sum(1 for t in self._trades if t.pnl <= 0)

        win_rate = winning_trades / total_trades if total_trades > 0 else 0

        avg_win = sum(t.pnl for t in self._trades if t.pnl > 0) / winning_trades if winning_trades > 0 else 0
        avg_loss = sum(t.pnl for t in self._trades if t.pnl <= 0) / losing_trades if losing_trades > 0 else 0

        total_wins = sum(t.pnl for t in self._trades if t.pnl > 0)
        total_losses = abs(sum(t.pnl for t in self._trades if t.pnl <= 0))
        profit_factor = total_wins / total_losses if total_losses > 0 else 0

        returns = []
        for i in range(1, len(self._equity_curve)):
            ret = (self._equity_curve[i] - self._equity_curve[i-1]) / self._equity_curve[i-1] if self._equity_curve[i-1] > 0 else 0
            returns.append(ret)

        sharpe_ratio = 0.0
        if returns:
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            
            minutes_per_year = 365 * 24 * 60
            periods_per_year = minutes_per_year / self.config.data_frequency_minutes
            
            if std_return > 0:
                sharpe_ratio = (avg_return / std_return) * math.sqrt(periods_per_year)

        avg_trade_return = sum(t.pnl_pct for t in self._trades) / total_trades if total_trades > 0 else 0

        durations = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in self._trades]
        avg_duration = sum(durations) / len(durations) if durations else 0

        return PerformanceMetrics(
            total_return=total_return,
            total_return_pct=total_return_pct,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            max_drawdown_pct=max_drawdown_pct,
            win_rate=win_rate,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            profit_factor=profit_factor,
            avg_trade_return=avg_trade_return,
            avg_trade_duration=avg_duration,
            total_fees=self._total_fees,
            liquidation_count=self._liquidation_count
        )

    def print_result(self, result: BacktestResult):
        print("\n" + "=" * 80)
        print("📊 回测结果")
        print("=" * 80)

        print(f"\n📅 时间范围: {result.start_date.date()} ~ {result.end_date.date()}")
        print(f"   持续天数: {result.duration_days}")
        
        cfg = result.config
        print(f"\n⚙️  配置")
        print(f"   初始资金: ${cfg.initial_capital:,.2f}")
        print(f"   杠杆倍数: {cfg.leverage}x")
        print(f"   仓位大小: {cfg.position_size:.1%}")
        print(f"   止损: {cfg.stop_loss:.1%} ({cfg.stop_loss_type})")
        print(f"   止盈: {cfg.take_profit:.1%}")
        print(f"   真实费用: {'是' if cfg.use_realistic_fees else '否'}")
        print(f"   复利: {'是' if cfg.compound else '否'}")

        m = result.metrics

        print(f"\n💰 收益")
        print(f"   总收益: ${m.total_return:,.2f} ({m.total_return_pct:.2%})")
        print(f"   夏普比率: {m.sharpe_ratio:.2f}")

        print(f"\n📉 风险")
        print(f"   最大回撤: ${m.max_drawdown:,.2f} ({m.max_drawdown_pct:.2%})")
        print(f"   总费用: ${m.total_fees:,.2f}")
        print(f"   强平次数: {m.liquidation_count}")

        print(f"\n📈 交易统计")
        print(f"   总交易: {m.total_trades}")
        print(f"   胜率: {m.win_rate:.2%}")
        print(f"   盈利交易: {m.winning_trades}")
        print(f"   亏损交易: {m.losing_trades}")
        print(f"   平均盈利: ${m.avg_win:,.2f}")
        print(f"   平均亏损: ${m.avg_loss:,.2f}")
        print(f"   盈亏比: {m.profit_factor:.2f}")
        print(f"   平均持仓: {m.avg_trade_duration:.1f} 小时")

        print("\n" + "=" * 80)


def run_backtest(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    strategy: Callable[[Bar, Optional[Dict]], SignalType],
    config: BacktestConfig = None,
    enable_gpu: bool = True,
) -> BacktestResult:
    engine = BacktestEngine(config, enable_gpu=enable_gpu)
    engine.load_mock_data(symbol, start_date, end_date)
    result = engine.run(strategy)
    engine.print_result(result)
    return result


async def run_parallel_optimization(
    symbol: str,
    strategy_id: str,
    param_grid: List[Dict[str, Any]],
    start_time: int,
    end_time: int,
    data_path: Optional[Path] = None,
    n_workers: Optional[int] = None,
    enable_gpu: bool = True,
    optimization_engine=None,
) -> List[Any]:
    if optimization_engine is None:
        from application.optimization_service.engine import OptimizationBacktestEngine, BacktestConfig as OptBacktestConfig
        config = OptBacktestConfig()
        optimization_engine = OptimizationBacktestEngine(config)

    engine = optimization_engine

    max_concurrent = n_workers or get_default_workers()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _run_single(params: Dict[str, Any]):
        async with semaphore:
            return await engine.run(
                symbol=symbol,
                strategy_id=strategy_id,
                params=params,
                start_time=start_time,
                end_time=end_time,
                data_path=data_path,
            )

    tasks = [_run_single(params) for params in param_grid]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    return [r for r in results if not isinstance(r, Exception)]


def example_sma_crossover_strategy(bar: Bar, position: Optional[Dict]) -> SignalType:
    import random

    if position:
        return SignalType.HOLD

    if random.random() > 0.95:
        return SignalType.BUY

    return SignalType.HOLD


if __name__ == "__main__":
    result = run_backtest(
        symbol="BTC/USDT",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 12, 31),
        strategy=example_sma_crossover_strategy
    )
