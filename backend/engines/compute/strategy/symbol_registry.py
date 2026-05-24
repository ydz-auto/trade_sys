"""
币种策略注册表 - 管理每个币种的策略配置和参数

功能：
1. 币种策略参数独立配置
2. 策略性能跟踪
3. 参数优化建议
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

from infrastructure.logging import get_logger

logger = get_logger("symbol_strategy_registry")


@dataclass
class SymbolStrategyParams:
    """币种策略参数"""
    symbol: str
    strategy_id: str
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    panic_drop_threshold: float = -0.015
    volume_ratio_threshold: float = 1.5
    llb_drop_threshold: float = -0.02
    llb_rsi_threshold: float = 25.0
    llb_volume_threshold: float = 2.0
    default_quantity: float = 0.01

    confidence_boost: float = 1.0
    last_optimized: Optional[datetime] = None


@dataclass
class StrategyPerformance:
    """策略性能记录"""
    symbol: str
    strategy_id: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


class SymbolStrategyRegistry:
    """
    币种策略注册表

    为每个币种管理独立的策略配置和性能跟踪
    """

    DEFAULT_PARAMS: Dict[str, Dict[str, Any]] = {
        "BTCUSDT": {
            "rsi_period": 14,
            "rsi_oversold": 30.0,
            "rsi_overbought": 70.0,
            "macd_fast": 12,
            "macd_slow": 26,
            "macd_signal": 9,
            "panic_drop_threshold": -0.015,
            "volume_ratio_threshold": 1.5,
            "llb_drop_threshold": -0.02,
            "llb_rsi_threshold": 25.0,
            "llb_volume_threshold": 2.0,
        },
        "ETHUSDT": {
            "rsi_period": 14,
            "rsi_oversold": 32.0,
            "rsi_overbought": 68.0,
            "macd_fast": 10,
            "macd_slow": 21,
            "macd_signal": 9,
            "panic_drop_threshold": -0.02,
            "volume_ratio_threshold": 1.8,
            "llb_drop_threshold": -0.025,
            "llb_rsi_threshold": 28.0,
            "llb_volume_threshold": 2.2,
        },
        "SOLUSDT": {
            "rsi_period": 14,
            "rsi_oversold": 28.0,
            "rsi_overbought": 72.0,
            "macd_fast": 8,
            "macd_slow": 21,
            "macd_signal": 7,
            "panic_drop_threshold": -0.025,
            "volume_ratio_threshold": 2.0,
            "llb_drop_threshold": -0.03,
            "llb_rsi_threshold": 30.0,
            "llb_volume_threshold": 2.5,
        },
    }

    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self._params: Dict[str, Dict[str, SymbolStrategyParams]] = {}
        self._performance: Dict[str, Dict[str, StrategyPerformance]] = {}

        self._initialize_default_params()

    def _initialize_default_params(self):
        """初始化默认参数"""
        for symbol, params in self.DEFAULT_PARAMS.items():
            self._params[symbol] = {}
            self._performance[symbol] = {}

            for strategy_id in ["rsi", "macd", "panic_reversal", "llb"]:
                full_strategy_id = f"{strategy_id}_{symbol}"
                self._params[symbol][full_strategy_id] = SymbolStrategyParams(
                    symbol=symbol,
                    strategy_id=full_strategy_id,
                    **params
                )

    def get_params(self, symbol: str, strategy_id: str = None) -> Dict[str, SymbolStrategyParams]:
        """
        获取币种策略参数

        Args:
            symbol: 币种
            strategy_id: 策略ID（可选，不指定返回所有策略参数）

        Returns:
            策略参数字典
        """
        if symbol not in self._params:
            logger.warning(f"Unknown symbol: {symbol}, using BTCUSDT defaults")
            symbol = "BTCUSDT"

        if strategy_id:
            return {strategy_id: self._params[symbol].get(strategy_id)}
        return self._params[symbol]

    def update_params(self, symbol: str, strategy_id: str, **kwargs):
        """更新策略参数"""
        if symbol not in self._params:
            self._params[symbol] = {}

        if strategy_id not in self._params[symbol]:
            self._params[symbol][strategy_id] = SymbolStrategyParams(
                symbol=symbol,
                strategy_id=strategy_id
            )

        for key, value in kwargs.items():
            if hasattr(self._params[symbol][strategy_id], key):
                setattr(self._params[symbol][strategy_id], key, value)

        self._params[symbol][strategy_id].last_optimized = datetime.now()
        logger.info(f"Updated params for {symbol}/{strategy_id}: {kwargs}")

    def record_performance(
        self,
        symbol: str,
        strategy_id: str,
        pnl: float,
        is_win: bool,
        drawdown: float = 0.0
    ):
        """记录策略性能"""
        if symbol not in self._performance:
            self._performance[symbol] = {}

        if strategy_id not in self._performance[symbol]:
            self._performance[symbol][strategy_id] = StrategyPerformance(
                symbol=symbol,
                strategy_id=strategy_id
            )

        perf = self._performance[symbol][strategy_id]
        perf.total_trades += 1
        perf.total_pnl += pnl

        if is_win:
            perf.winning_trades += 1
            if perf.avg_win == 0:
                perf.avg_win = pnl
            else:
                perf.avg_win = (perf.avg_win * (perf.winning_trades - 1) + pnl) / perf.winning_trades
        else:
            perf.losing_trades += 1
            if perf.avg_loss == 0:
                perf.avg_loss = abs(pnl)
            else:
                perf.avg_loss = (perf.avg_loss * (perf.losing_trades - 1) + abs(pnl)) / perf.losing_trades

        if drawdown > perf.max_drawdown:
            perf.max_drawdown = drawdown

        if perf.total_trades > 0:
            perf.win_rate = perf.winning_trades / perf.total_trades

        perf.last_updated = datetime.now()

    def get_performance(self, symbol: str, strategy_id: str = None) -> Dict[str, StrategyPerformance]:
        """获取策略性能"""
        if symbol not in self._performance:
            return {}

        if strategy_id:
            return {strategy_id: self._performance[symbol].get(strategy_id)}
        return self._performance[symbol]

    def get_optimization_suggestions(self, symbol: str) -> List[str]:
        """获取参数优化建议"""
        suggestions = []

        if symbol not in self._performance:
            return suggestions

        for strategy_id, perf in self._performance[symbol].items():
            if perf.total_trades < 20:
                suggestions.append(f"[{symbol}/{strategy_id}] 需要更多交易样本 (当前: {perf.total_trades})")
                continue

            if perf.win_rate < 0.45:
                suggestions.append(
                    f"[{symbol}/{strategy_id}] 胜率过低 ({perf.win_rate:.1%})，建议调整参数"
                )

            if perf.max_drawdown > 0.2:
                suggestions.append(
                    f"[{symbol}/{strategy_id}] 回撤过大 ({perf.max_drawdown:.1%})，建议收紧止损"
                )

            if perf.total_trades > 50 and perf.win_rate > 0.55:
                suggestions.append(
                    f"[{symbol}/{strategy_id}] 表现良好，胜率 {perf.win_rate:.1%}"
                )

        return suggestions

    def save_to_file(self, path: str = None):
        """保存配置到文件"""
        path = path or self.config_path
        if not path:
            return

        data = {
            "params": {
                symbol: {
                    sid: {
                        k: str(v) if isinstance(v, datetime) else v
                        for k, v in p.__dict__.items()
                    }
                    for sid, p in strategies.items()
                }
                for symbol, strategies in self._params.items()
            },
            "performance": {
                symbol: {
                    sid: {
                        k: str(v) if isinstance(v, datetime) else v
                        for k, v in perf.__dict__.items()
                    }
                    for sid, perf in strategies.items()
                }
                for symbol, strategies in self._performance.items()
            },
            "saved_at": datetime.now().isoformat(),
        }

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Saved registry to {path}")

    def load_from_file(self, path: str = None):
        """从文件加载配置"""
        path = path or self.config_path
        if not path or not Path(path).exists():
            return

        with open(path, 'r') as f:
            data = json.load(f)

        logger.info(f"Loaded registry from {path}")

    def get_all_symbols(self) -> List[str]:
        """获取所有注册的币种"""
        return list(self._params.keys())

    def summary(self) -> str:
        """获取注册表摘要"""
        lines = ["=" * 60]
        lines.append("Symbol Strategy Registry Summary")
        lines.append("=" * 60)

        for symbol in self._params:
            strategies = list(self._params[symbol].keys())
            lines.append(f"\n[{symbol}] {len(strategies)} strategies")

            for strategy_id, params in self._params[symbol].items():
                perf = self._performance[symbol].get(strategy_id)
                if perf and perf.total_trades > 0:
                    lines.append(
                        f"  {strategy_id}: win_rate={perf.win_rate:.1%}, "
                        f"trades={perf.total_trades}, pnl=${perf.total_pnl:.2f}"
                    )

        return "\n".join(lines)


_registry: Optional[SymbolStrategyRegistry] = None


def get_symbol_registry(config_path: str = None) -> SymbolStrategyRegistry:
    """获取币种策略注册表单例"""
    global _registry
    if _registry is None:
        _registry = SymbolStrategyRegistry(config_path)
    return _registry
