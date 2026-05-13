"""
Execution Metrics

Prometheus 指标导出
"""

from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

from infrastructure.logging import get_logger

logger = get_logger("execution_service.metrics")


@dataclass
class MetricPoint:
    """单个指标点"""
    timestamp: float
    value: float


class ExecutionMetrics:
    """执行服务 Prometheus 指标管理器

    记录所有关键指标，支持导出为 Prometheus 格式
    """

    def __init__(self):
        # 计数指标
        self.orders_submitted: int = 0
        self.orders_filled: int = 0
        self.orders_cancelled: int = 0
        self.orders_rejected: int = 0
        self.orders_failed: int = 0

        # 风控指标
        self.risk_checks_passed: int = 0
        self.risk_checks_failed: int = 0
        self.risk_warnings: int = 0

        # 持仓指标
        self.open_positions: int = 0
        self.total_pnl: float = 0.0
        self.unrealized_pnl: float = 0.0

        # 延迟指标（毫秒）
        self.order_latencies: list = []  # 记录最后 N 次
        self.engine_latencies: list = []

        # 时间追踪
        self.start_time: datetime = datetime.now()
        self.last_order_time: Optional[datetime] = None

        # 按交易对统计
        self.symbol_metrics: Dict[str, Dict] = {}

        logger.info("Prometheus metrics initialized")

    def order_submitted(self, symbol: str):
        """记录订单提交"""
        self.orders_submitted += 1
        self.last_order_time = datetime.now()
        self._update_symbol_metric(symbol, "submitted", 1)
        logger.debug(f"Order submitted: {symbol}, total: {self.orders_submitted}")

    def order_filled(self, symbol: str):
        """记录订单成交"""
        self.orders_filled += 1
        self._update_symbol_metric(symbol, "filled", 1)
        logger.debug(f"Order filled: {symbol}, total: {self.orders_filled}")

    def order_cancelled(self, symbol: str):
        """记录订单取消"""
        self.orders_cancelled += 1
        self._update_symbol_metric(symbol, "cancelled", 1)
        logger.debug(f"Order cancelled: {symbol}, total: {self.orders_cancelled}")

    def order_rejected(self, symbol: str):
        """记录订单拒绝"""
        self.orders_rejected += 1
        self._update_symbol_metric(symbol, "rejected", 1)
        logger.warning(f"Order rejected: {symbol}")

    def order_failed(self, symbol: str):
        """记录订单失败"""
        self.orders_failed += 1
        self._update_symbol_metric(symbol, "failed", 1)
        logger.error(f"Order failed: {symbol}")

    def risk_check_passed(self):
        """记录风控通过"""
        self.risk_checks_passed += 1

    def risk_check_failed(self, reason: str):
        """记录风控失败"""
        self.risk_checks_failed += 1
        logger.warning(f"Risk check failed: {reason}")

    def risk_warning(self):
        """记录风控警告"""
        self.risk_warnings += 1

    def update_positions(self, open_count: int, unrealized: float, total: float):
        """更新持仓指标"""
        self.open_positions = open_count
        self.unrealized_pnl = unrealized
        self.total_pnl = total
        logger.debug(f"Positions update: open={open_count}, pnl={total:.2f}")

    def record_order_latency(self, ms: float):
        """记录订单执行延迟"""
        self.order_latencies.append(ms)
        # 只保留最近 1000 次
        if len(self.order_latencies) > 1000:
            self.order_latencies.pop(0)

    def record_engine_latency(self, ms: float):
        """记录引擎处理延迟"""
        self.engine_latencies.append(ms)
        if len(self.engine_latencies) > 1000:
            self.engine_latencies.pop(0)

    def _update_symbol_metric(self, symbol: str, metric: str, value: int):
        """更新按交易对统计"""
        if symbol not in self.symbol_metrics:
            self.symbol_metrics[symbol] = {
                "submitted": 0,
                "filled": 0,
                "cancelled": 0,
                "rejected": 0,
                "failed": 0,
            }
        self.symbol_metrics[symbol][metric] += value

    def avg_order_latency(self) -> Optional[float]:
        """平均订单延迟"""
        return sum(self.order_latencies) / len(self.order_latencies) if self.order_latencies else None

    def avg_engine_latency(self) -> Optional[float]:
        """平均引擎延迟"""
        return sum(self.engine_latencies) / len(self.engine_latencies) if self.engine_latencies else None

    def uptime_seconds(self) -> int:
        """运行时间（秒）"""
        return int((datetime.now() - self.start_time).total_seconds())

    def export_prometheus(self) -> str:
        """导出为 Prometheus 文本格式"""
        lines = []
        now = int(datetime.now().timestamp() * 1000)

        # 订单计数
        lines.append(f'# HELP execution_orders_total Total orders processed by type')
        lines.append(f'# TYPE execution_orders_total counter')
        lines.append(f'execution_orders_total{{type="submitted"}} {self.orders_submitted} {now}')
        lines.append(f'execution_orders_total{{type="filled"}} {self.orders_filled} {now}')
        lines.append(f'execution_orders_total{{type="cancelled"}} {self.orders_cancelled} {now}')
        lines.append(f'execution_orders_total{{type="rejected"}} {self.orders_rejected} {now}')
        lines.append(f'execution_orders_total{{type="failed"}} {self.orders_failed} {now}')

        # 风控计数
        lines.append(f'# HELP execution_risk_checks_total Risk check results')
        lines.append(f'# TYPE execution_risk_checks_total counter')
        lines.append(f'execution_risk_checks_total{{result="passed"}} {self.risk_checks_passed} {now}')
        lines.append(f'execution_risk_checks_total{{result="failed"}} {self.risk_checks_failed} {now}')
        lines.append(f'execution_risk_checks_total{{result="warning"}} {self.risk_warnings} {now}')

        # 持仓指标
        lines.append(f'# HELP execution_positions_open Number of open positions')
        lines.append(f'# TYPE execution_positions_open gauge')
        lines.append(f'execution_positions_open {self.open_positions} {now}')

        lines.append(f'# HELP execution_pnl_realized Realized PnL')
        lines.append(f'# TYPE execution_pnl_realized gauge')
        lines.append(f'execution_pnl_realized {self.total_pnl} {now}')

        lines.append(f'# HELP execution_pnl_unrealized Unrealized PnL')
        lines.append(f'# TYPE execution_pnl_unrealized gauge')
        lines.append(f'execution_pnl_unrealized {self.unrealized_pnl} {now}')

        # 延迟指标
        avg_ord_lat = self.avg_order_latency()
        avg_eng_lat = self.avg_engine_latency()

        if avg_ord_lat:
            lines.append(f'# HELP execution_order_latency_ms Average order execution latency in ms')
            lines.append(f'# TYPE execution_order_latency_ms gauge')
            lines.append(f'execution_order_latency_ms {avg_ord_lat:.2f} {now}')

        if avg_eng_lat:
            lines.append(f'# HELP execution_engine_latency_ms Average engine processing latency in ms')
            lines.append(f'# TYPE execution_engine_latency_ms gauge')
            lines.append(f'execution_engine_latency_ms {avg_eng_lat:.2f} {now}')

        # 运行时间
        lines.append(f'# HELP execution_uptime_seconds Execution service uptime in seconds')
        lines.append(f'# TYPE execution_uptime_seconds gauge')
        lines.append(f'execution_uptime_seconds {self.uptime_seconds()} {now}')

        # 按交易对统计
        for symbol, stats in self.symbol_metrics.items():
            lines.append(f'# HELP execution_symbol_orders_total Orders per symbol')
            lines.append(f'# TYPE execution_symbol_orders_total counter')
            for typ, val in stats.items():
                lines.append(f'execution_symbol_orders_total{{symbol="{symbol}",type="{typ}"}} {val} {now}')

        return "\n".join(lines) + "\n"


# 全局单例
_metrics_instance: Optional[ExecutionMetrics] = None


def get_execution_metrics() -> ExecutionMetrics:
    """获取指标管理器单例"""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = ExecutionMetrics()
    return _metrics_instance


def reset_execution_metrics():
    """重置指标（测试用）"""
    global _metrics_instance
    _metrics_instance = ExecutionMetrics()
