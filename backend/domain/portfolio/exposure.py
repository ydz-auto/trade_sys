from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    LIQUIDATED = "liquidated"


@dataclass
class Position:
    position_id: str
    symbol: str
    exchange: str

    side: PositionSide = PositionSide.FLAT
    status: PositionStatus = PositionStatus.OPEN

    quantity: float = 0.0
    available_quantity: float = 0.0

    entry_price: float = 0.0
    average_price: float = 0.0
    current_price: float = 0.0

    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    leverage: int = 1
    margin: float = 0.0
    liquidation_price: float = 0.0

    strategy_id: str = ""
    account_id: str = ""

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None

    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: Optional[datetime] = None

    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.quantity > 0:
            self.side = PositionSide.LONG
        elif self.quantity < 0:
            self.side = PositionSide.SHORT
        else:
            self.side = PositionSide.FLAT

    @property
    def is_long(self) -> bool:
        return self.side == PositionSide.LONG

    @property
    def is_short(self) -> bool:
        return self.side == PositionSide.SHORT

    @property
    def is_flat(self) -> bool:
        return self.side == PositionSide.FLAT or abs(self.quantity) < 1e-8

    @property
    def is_open(self) -> bool:
        return self.status == PositionStatus.OPEN

    @property
    def notional_value(self) -> float:
        return abs(self.quantity) * self.current_price

    @property
    def margin_used(self) -> float:
        if self.leverage > 0:
            return self.notional_value / self.leverage
        return 0.0

    @property
    def pnl_percent(self) -> float:
        if self.entry_price > 0:
            return (self.current_price - self.entry_price) / self.entry_price * 100 * (1 if self.is_long else -1)
        return 0.0

    def update_price(self, current_price: float) -> None:
        self.current_price = current_price

        if self.quantity != 0:
            if self.is_long:
                self.unrealized_pnl = (current_price - self.average_price) * self.quantity
            else:
                self.unrealized_pnl = (self.average_price - current_price) * abs(self.quantity)

        self.updated_at = datetime.utcnow()

    def add_quantity(self, quantity: float, price: float) -> None:
        if quantity == 0:
            return

        new_quantity = self.quantity + quantity

        if self.quantity == 0:
            self.entry_price = price
            self.average_price = price
        elif (self.quantity > 0 and quantity > 0) or (self.quantity < 0 and quantity < 0):
            total_cost = abs(self.quantity) * self.average_price + abs(quantity) * price
            total_qty = abs(new_quantity)
            self.average_price = total_cost / total_qty if total_qty > 0 else 0.0

        self.quantity = new_quantity
        self.available_quantity = new_quantity
        self.__post_init__()
        self.updated_at = datetime.utcnow()

    def reduce_quantity(self, quantity: float, price: float) -> float:
        if quantity == 0 or self.is_flat:
            return 0.0

        close_quantity = min(abs(self.quantity), abs(quantity))
        if self.is_long:
            realized = (price - self.average_price) * close_quantity
        else:
            realized = (self.average_price - price) * close_quantity

        self.realized_pnl += realized

        if self.quantity > 0:
            self.quantity -= close_quantity
        else:
            self.quantity += close_quantity

        self.available_quantity = self.quantity
        self.__post_init__()

        if self.is_flat:
            self.status = PositionStatus.CLOSED
            self.closed_at = datetime.utcnow()

        self.updated_at = datetime.utcnow()
        return realized

    def set_stop_loss(self, price: float) -> None:
        self.stop_loss = price
        self.updated_at = datetime.utcnow()

    def set_take_profit(self, price: float) -> None:
        self.take_profit = price
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "exchange": self.exchange,
            "side": self.side.value,
            "status": self.status.value,
            "quantity": self.quantity,
            "available_quantity": self.available_quantity,
            "entry_price": self.entry_price,
            "average_price": self.average_price,
            "current_price": self.current_price,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "leverage": self.leverage,
            "margin": self.margin,
            "liquidation_price": self.liquidation_price,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "notional_value": self.notional_value,
            "pnl_percent": self.pnl_percent,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Position":
        return cls(
            position_id=data["position_id"],
            symbol=data["symbol"],
            exchange=data["exchange"],
            side=PositionSide(data.get("side", "flat")),
            status=PositionStatus(data.get("status", "open")),
            quantity=data.get("quantity", 0.0),
            available_quantity=data.get("available_quantity", 0.0),
            entry_price=data.get("entry_price", 0.0),
            average_price=data.get("average_price", 0.0),
            current_price=data.get("current_price", 0.0),
            unrealized_pnl=data.get("unrealized_pnl", 0.0),
            realized_pnl=data.get("realized_pnl", 0.0),
            leverage=data.get("leverage", 1),
            margin=data.get("margin", 0.0),
            liquidation_price=data.get("liquidation_price", 0.0),
            strategy_id=data.get("strategy_id", ""),
            account_id=data.get("account_id", ""),
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else datetime.utcnow(),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            metadata=data.get("metadata", {}),
        )


class ExposureType(str, Enum):
    LONG = "long"
    SHORT = "short"
    NET = "net"
    GROSS = "gross"


@dataclass
class Exposure:
    symbol: str
    exchange: str

    long_quantity: float = 0.0
    short_quantity: float = 0.0
    net_quantity: float = 0.0

    long_value: float = 0.0
    short_value: float = 0.0
    net_value: float = 0.0
    gross_value: float = 0.0

    price: float = 0.0

    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_balanced(self) -> bool:
        return abs(self.net_quantity) < 1e-8

    @property
    def long_ratio(self) -> float:
        total = self.long_value + self.short_value
        return self.long_value / total if total > 0 else 0.0

    @property
    def short_ratio(self) -> float:
        total = self.long_value + self.short_value
        return self.short_value / total if total > 0 else 0.0


@dataclass
class ExposureConfig:
    max_single_exposure: float = 0.2
    max_total_exposure: float = 1.0
    max_long_exposure: float = 0.8
    max_short_exposure: float = 0.8
    max_correlated_exposure: float = 0.5
    enable_auto_hedge: bool = False
    hedge_ratio: float = 0.5


class ExposureManager:
    def __init__(self, config: ExposureConfig = None):
        self.config = config or ExposureConfig()
        self.exposures: Dict[str, Exposure] = {}
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}

    def update_exposure(
        self,
        symbol: str,
        exchange: str,
        long_quantity: float,
        short_quantity: float,
        price: float,
    ) -> Exposure:
        key = f"{exchange}:{symbol}"

        long_value = abs(long_quantity) * price
        short_value = abs(short_quantity) * price

        exposure = Exposure(
            symbol=symbol,
            exchange=exchange,
            long_quantity=long_quantity,
            short_quantity=short_quantity,
            net_quantity=long_quantity + short_quantity,
            long_value=long_value,
            short_value=short_value,
            net_value=long_value - short_value,
            gross_value=long_value + short_value,
            price=price,
        )

        self.exposures[key] = exposure
        return exposure

    def get_exposure(self, symbol: str, exchange: str = "binance") -> Optional[Exposure]:
        key = f"{exchange}:{symbol}"
        return self.exposures.get(key)

    def get_total_exposure(self, exposure_type: ExposureType = ExposureType.GROSS) -> float:
        if exposure_type == ExposureType.LONG:
            return sum(e.long_value for e in self.exposures.values())
        elif exposure_type == ExposureType.SHORT:
            return sum(e.short_value for e in self.exposures.values())
        elif exposure_type == ExposureType.NET:
            return sum(abs(e.net_value) for e in self.exposures.values())
        else:
            return sum(e.gross_value for e in self.exposures.values())

    def get_exposure_ratio(self, capital: float) -> float:
        if capital > 0:
            return self.get_total_exposure(ExposureType.GROSS) / capital
        return 0.0

    def check_exposure_limit(
        self,
        symbol: str,
        exchange: str,
        additional_value: float,
        capital: float,
        is_long: bool = True,
    ) -> tuple[bool, str]:
        exposure = self.get_exposure(symbol, exchange)

        current_long = exposure.long_value if exposure else 0.0
        current_short = exposure.short_value if exposure else 0.0

        if is_long:
            new_long_value = current_long + additional_value
            single_exposure = new_long_value / capital if capital > 0 else 0.0

            if single_exposure > self.config.max_single_exposure:
                return False, f"单品种敞口超限: {single_exposure:.2%} > {self.config.max_single_exposure:.2%}"

            total_long = self.get_total_exposure(ExposureType.LONG) + additional_value
            long_ratio = total_long / capital if capital > 0 else 0.0

            if long_ratio > self.config.max_long_exposure:
                return False, f"总多头敞口超限: {long_ratio:.2%} > {self.config.max_long_exposure:.2%}"
        else:
            new_short_value = current_short + additional_value
            single_exposure = new_short_value / capital if capital > 0 else 0.0

            if single_exposure > self.config.max_single_exposure:
                return False, f"单品种敞口超限: {single_exposure:.2%} > {self.config.max_single_exposure:.2%}"

            total_short = self.get_total_exposure(ExposureType.SHORT) + additional_value
            short_ratio = total_short / capital if capital > 0 else 0.0

            if short_ratio > self.config.max_short_exposure:
                return False, f"总空头敞口超限: {short_ratio:.2%} > {self.config.max_short_exposure:.2%}"

        new_total = self.get_total_exposure(ExposureType.GROSS) + additional_value
        total_ratio = new_total / capital if capital > 0 else 0.0

        if total_ratio > self.config.max_total_exposure:
            return False, f"总敞口超限: {total_ratio:.2%} > {self.config.max_total_exposure:.2%}"

        return True, "OK"

    def get_exposure_warnings(self, capital: float) -> List[Dict[str, Any]]:
        warnings = []

        total_exposure = self.get_exposure_ratio(capital)
        if total_exposure > self.config.max_total_exposure * 0.8:
            warnings.append({
                "type": "high_exposure",
                "message": f"总敞口较高: {total_exposure:.2%}",
                "severity": "warning" if total_exposure < self.config.max_total_exposure else "critical",
            })

        for key, exposure in self.exposures.items():
            single_ratio = exposure.gross_value / capital if capital > 0 else 0.0
            if single_ratio > self.config.max_single_exposure * 0.8:
                warnings.append({
                    "type": "single_exposure",
                    "symbol": exposure.symbol,
                    "exchange": exposure.exchange,
                    "message": f"单品种敞口较高: {exposure.symbol} {single_ratio:.2%}",
                    "severity": "warning" if single_ratio < self.config.max_single_exposure else "critical",
                })

        return warnings

    def calculate_hedge_suggestion(self, capital: float) -> Dict[str, Any]:
        total_long = self.get_total_exposure(ExposureType.LONG)
        total_short = self.get_total_exposure(ExposureType.SHORT)
        net_exposure = total_long - total_short

        suggestion = {
            "net_exposure": net_exposure,
            "net_ratio": net_exposure / capital if capital > 0 else 0.0,
            "hedge_needed": 0.0,
            "hedge_direction": None,
        }

        if self.config.enable_auto_hedge and abs(net_exposure) > capital * 0.3:
            hedge_amount = abs(net_exposure) * self.config.hedge_ratio
            suggestion["hedge_needed"] = hedge_amount
            suggestion["hedge_direction"] = "short" if net_exposure > 0 else "long"

        return suggestion

    def set_correlation(self, symbol1: str, symbol2: str, correlation: float) -> None:
        if symbol1 not in self._correlation_matrix:
            self._correlation_matrix[symbol1] = {}
        if symbol2 not in self._correlation_matrix:
            self._correlation_matrix[symbol2] = {}

        self._correlation_matrix[symbol1][symbol2] = correlation
        self._correlation_matrix[symbol2][symbol1] = correlation

    def get_correlated_exposure(self, symbol: str, threshold: float = 0.7) -> float:
        correlated = [symbol]

        if symbol in self._correlation_matrix:
            for other, corr in self._correlation_matrix[symbol].items():
                if abs(corr) >= threshold:
                    correlated.append(other)

        total = 0.0
        for s in correlated:
            for key, exposure in self.exposures.items():
                if exposure.symbol == s:
                    total += exposure.gross_value

        return total

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": {
                "max_single_exposure": self.config.max_single_exposure,
                "max_total_exposure": self.config.max_total_exposure,
                "max_long_exposure": self.config.max_long_exposure,
                "max_short_exposure": self.config.max_short_exposure,
            },
            "exposures": {k: {
                "symbol": e.symbol,
                "exchange": e.exchange,
                "long_value": e.long_value,
                "short_value": e.short_value,
                "net_value": e.net_value,
                "gross_value": e.gross_value,
            } for k, e in self.exposures.items()},
            "total_exposure": {
                "long": self.get_total_exposure(ExposureType.LONG),
                "short": self.get_total_exposure(ExposureType.SHORT),
                "net": self.get_total_exposure(ExposureType.NET),
                "gross": self.get_total_exposure(ExposureType.GROSS),
            },
        }
