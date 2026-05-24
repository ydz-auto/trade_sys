from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import numpy as np

import logging

logger = logging.getLogger(__name__)


class SlippageStatus(str, Enum):
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SlippageMeasurement:
    timestamp: datetime
    symbol: str
    expected_price: float
    actual_price: float
    slippage_bps: float
    slippage_pct: float
    order_size: float
    market_conditions: Dict[str, Any]


@dataclass
class SlippageControlResult:
    status: SlippageStatus
    current_slippage_bps: float
    avg_slippage_bps: float
    max_slippage_bps: float
    should_pause: bool
    should_reduce_size: bool
    recommended_size_pct: float
    alert_message: Optional[str]


@dataclass
class SlippageController:
    warning_threshold_bps: float = 5.0
    high_threshold_bps: float = 15.0
    critical_threshold_bps: float = 30.0
    history_size: int = 100
    cooldown_seconds: float = 60.0
    size_reduction_factor: float = 0.5

    def __post_init__(self):
        self._history: Dict[str, List[SlippageMeasurement]] = {}
        self._pause_until: Dict[str, datetime] = {}

    def record(
        self,
        symbol: str,
        expected_price: float,
        actual_price: float,
        order_size: float,
        market_conditions: Dict[str, Any],
    ) -> SlippageMeasurement:
        timestamp = datetime.now()

        slippage_pct = (actual_price - expected_price) / expected_price
        slippage_bps = abs(slippage_pct) * 10000

        measurement = SlippageMeasurement(
            timestamp=timestamp,
            symbol=symbol,
            expected_price=expected_price,
            actual_price=actual_price,
            slippage_bps=slippage_bps,
            slippage_pct=slippage_pct,
            order_size=order_size,
            market_conditions=market_conditions,
        )

        if symbol not in self._history:
            self._history[symbol] = []

        self._history[symbol].append(measurement)

        if len(self._history[symbol]) > self.history_size:
            self._history[symbol] = self._history[symbol][-self.history_size:]

        return measurement

    def check(
        self,
        symbol: str,
        proposed_size: float,
    ) -> SlippageControlResult:
        history = self._history.get(symbol, [])

        if not history:
            return self._normal_result()

        recent = history[-20:]

        current_bps = recent[-1].slippage_bps if recent else 0.0
        avg_bps = np.mean([m.slippage_bps for m in recent])
        max_bps = max(m.slippage_bps for m in recent)

        status = self._determine_status(current_bps, avg_bps)

        should_pause = self._should_pause(symbol, status, current_bps)
        should_reduce = status in [SlippageStatus.HIGH, SlippageStatus.CRITICAL]

        recommended_pct = self._calculate_recommended_size(
            status, current_bps, avg_bps
        )

        alert = self._generate_alert(status, current_bps, avg_bps)

        return SlippageControlResult(
            status=status,
            current_slippage_bps=current_bps,
            avg_slippage_bps=avg_bps,
            max_slippage_bps=max_bps,
            should_pause=should_pause,
            should_reduce_size=should_reduce,
            recommended_size_pct=recommended_pct,
            alert_message=alert,
        )

    def _determine_status(
        self,
        current: float,
        avg: float,
    ) -> SlippageStatus:
        if current >= self.critical_threshold_bps:
            return SlippageStatus.CRITICAL

        if current >= self.high_threshold_bps or avg >= self.high_threshold_bps:
            return SlippageStatus.HIGH

        if current >= self.warning_threshold_bps or avg >= self.warning_threshold_bps:
            return SlippageStatus.ELEVATED

        return SlippageStatus.NORMAL

    def _should_pause(
        self,
        symbol: str,
        status: SlippageStatus,
        current_bps: float,
    ) -> bool:
        if status == SlippageStatus.CRITICAL:
            self._pause_until[symbol] = datetime.now() + timedelta(seconds=self.cooldown_seconds)
            return True

        if symbol in self._pause_until:
            if datetime.now() < self._pause_until[symbol]:
                return True
            else:
                del self._pause_until[symbol]

        return False

    def _calculate_recommended_size(
        self,
        status: SlippageStatus,
        current: float,
        avg: float,
    ) -> float:
        if status == SlippageStatus.NORMAL:
            return 1.0

        if status == SlippageStatus.ELEVATED:
            return 0.8

        if status == SlippageStatus.HIGH:
            return self.size_reduction_factor

        return self.size_reduction_factor * 0.5

    def _generate_alert(
        self,
        status: SlippageStatus,
        current: float,
        avg: float,
    ) -> Optional[str]:
        if status == SlippageStatus.NORMAL:
            return None

        if status == SlippageStatus.CRITICAL:
            return f"CRITICAL: Slippage {current:.1f} bps exceeds threshold. Trading paused."

        if status == SlippageStatus.HIGH:
            return f"HIGH: Slippage {current:.1f} bps (avg: {avg:.1f}). Consider reducing size."

        return f"ELEVATED: Slippage {current:.1f} bps. Monitor closely."

    def _normal_result(self) -> SlippageControlResult:
        return SlippageControlResult(
            status=SlippageStatus.NORMAL,
            current_slippage_bps=0.0,
            avg_slippage_bps=0.0,
            max_slippage_bps=0.0,
            should_pause=False,
            should_reduce_size=False,
            recommended_size_pct=1.0,
            alert_message=None,
        )

    def get_stats(self, symbol: str) -> Dict[str, Any]:
        history = self._history.get(symbol, [])

        if not history:
            return {"count": 0}

        slippages = [m.slippage_bps for m in history]

        return {
            "count": len(history),
            "current_bps": slippages[-1],
            "avg_bps": np.mean(slippages),
            "max_bps": max(slippages),
            "min_bps": min(slippages),
            "std_bps": np.std(slippages),
            "trend": slippages[-1] - slippages[0] if len(slippages) > 1 else 0.0,
        }


def control_slippage(
    symbol: str,
    expected_price: float,
    actual_price: float,
    order_size: float,
    market_conditions: Dict[str, Any],
    controller: Optional[SlippageController] = None,
) -> SlippageControlResult:
    controller = controller or SlippageController()
    controller.record(
        symbol, expected_price, actual_price,
        order_size, market_conditions
    )
    return controller.check(symbol, order_size)


class SplitStrategy(str, Enum):
    EQUAL = "equal"
    PROPORTIONAL = "proportional"
    RANDOM = "random"
    STEALTH = "stealth"


@dataclass
class OrderSlice:
    slice_id: int
    size: float
    price: float
    delay_seconds: float
    is_visible: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SplitResult:
    original_size: float
    original_price: float
    slices: List[OrderSlice]
    total_slices: int
    visible_slices: int
    estimated_total_time_seconds: float
    size_variance: float
    stealth_score: float


@dataclass
class OrderSplitter:
    max_slice_size_pct: float = 0.1
    min_slices: int = 1
    max_slices: int = 20
    stealth_enabled: bool = True
    random_variance: float = 0.2

    def split(
        self,
        order_size: float,
        order_price: float,
        orderbook_depth: float,
        avg_trade_size: float,
        strategy: SplitStrategy = SplitStrategy.STEALTH,
    ) -> SplitResult:
        num_slices = self._calculate_num_slices(
            order_size, orderbook_depth, avg_trade_size
        )

        sizes = self._calculate_slice_sizes(
            order_size, num_slices, strategy
        )

        delays = self._calculate_delays(num_slices, strategy)

        prices = self._calculate_slice_prices(
            order_price, num_slices, strategy
        )

        slices = []
        for i in range(num_slices):
            is_visible = self._is_slice_visible(i, num_slices, strategy)

            slices.append(OrderSlice(
                slice_id=i,
                size=sizes[i],
                price=prices[i],
                delay_seconds=delays[i],
                is_visible=is_visible,
            ))

        total_time = max(delays) if delays else 0.0

        size_variance = np.var(sizes) / (np.mean(sizes) ** 2) if sizes and np.mean(sizes) > 0 else 0.0

        stealth_score = self._calculate_stealth_score(
            num_slices, size_variance, strategy
        )

        return SplitResult(
            original_size=order_size,
            original_price=order_price,
            slices=slices,
            total_slices=num_slices,
            visible_slices=sum(1 for s in slices if s.is_visible),
            estimated_total_time_seconds=total_time,
            size_variance=size_variance,
            stealth_score=stealth_score,
        )

    def _calculate_num_slices(
        self,
        order_size: float,
        depth: float,
        avg_size: float,
    ) -> int:
        max_single_size = depth * self.max_slice_size_pct

        if max_single_size <= 0:
            return self.min_slices

        min_needed = int(np.ceil(order_size / max_single_size))

        by_avg = int(np.ceil(order_size / (avg_size * 3)))

        num_slices = max(min_needed, by_avg, self.min_slices)
        num_slices = min(num_slices, self.max_slices)

        return num_slices

    def _calculate_slice_sizes(
        self,
        total_size: float,
        num_slices: int,
        strategy: SplitStrategy,
    ) -> List[float]:
        if strategy == SplitStrategy.EQUAL:
            sizes = [total_size / num_slices] * num_slices

        elif strategy == SplitStrategy.PROPORTIONAL:
            weights = np.linspace(1, 0.5, num_slices)
            weights = weights / weights.sum()
            sizes = list(total_size * weights)

        elif strategy == SplitStrategy.RANDOM:
            base_size = total_size / num_slices
            sizes = []
            remaining = total_size

            for i in range(num_slices - 1):
                variance = base_size * self.random_variance
                size = base_size + np.random.uniform(-variance, variance)
                size = max(size, base_size * 0.5)
                size = min(size, remaining * 0.8)
                sizes.append(size)
                remaining -= size

            sizes.append(remaining)

        else:
            sizes = self._stealth_sizes(total_size, num_slices)

        return sizes

    def _stealth_sizes(
        self,
        total_size: float,
        num_slices: int,
    ) -> List[float]:
        sizes = []
        remaining = total_size

        base_size = total_size / num_slices

        for i in range(num_slices - 1):
            noise = np.random.normal(0, base_size * 0.15)
            size = base_size + noise

            size = max(size, base_size * 0.3)
            size = min(size, remaining * 0.5)

            sizes.append(size)
            remaining -= size

        sizes.append(remaining)

        return sizes

    def _calculate_delays(
        self,
        num_slices: int,
        strategy: SplitStrategy,
    ) -> List[float]:
        if strategy == SplitStrategy.AGGRESSIVE:
            return [0.0] * num_slices

        base_interval = 5.0

        if strategy == SplitStrategy.STEALTH:
            intervals = []
            for i in range(num_slices):
                noise = np.random.exponential(2.0)
                intervals.append(i * base_interval + noise)
            return intervals

        return [i * base_interval for i in range(num_slices)]

    def _calculate_slice_prices(
        self,
        base_price: float,
        num_slices: int,
        strategy: SplitStrategy,
    ) -> List[float]:
        if strategy in [SplitStrategy.EQUAL, SplitStrategy.PROPORTIONAL]:
            return [base_price] * num_slices

        prices = []
        for i in range(num_slices):
            tick = base_price * 0.0001 * (i % 2 * 2 - 1)
            prices.append(base_price + tick)

        return prices

    def _is_slice_visible(
        self,
        index: int,
        total: int,
        strategy: SplitStrategy,
    ) -> bool:
        if strategy != SplitStrategy.STEALTH:
            return True

        if not self.stealth_enabled:
            return True

        return index < total * 0.3

    def _calculate_stealth_score(
        self,
        num_slices: int,
        size_variance: float,
        strategy: SplitStrategy,
    ) -> float:
        if strategy != SplitStrategy.STEALTH:
            return 0.0

        score = 0.5

        if num_slices >= 5:
            score += 0.2

        if size_variance > 0.01:
            score += 0.2

        if self.stealth_enabled:
            score += 0.1

        return min(1.0, score)


def split_order(
    order_size: float,
    order_price: float,
    orderbook_depth: float,
    avg_trade_size: float,
    strategy: SplitStrategy = SplitStrategy.STEALTH,
    splitter: Optional[OrderSplitter] = None,
) -> SplitResult:
    splitter = splitter or OrderSplitter()
    return splitter.split(
        order_size, order_price,
        orderbook_depth, avg_trade_size,
        strategy
    )
