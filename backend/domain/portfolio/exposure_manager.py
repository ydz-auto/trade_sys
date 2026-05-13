"""
ExposureManager - 敞口管理器

管理投资组合的敞口风险
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class ExposureType(str, Enum):
    """敞口类型"""
    LONG = "long"
    SHORT = "short"
    NET = "net"
    GROSS = "gross"


@dataclass
class Exposure:
    """敞口"""
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
        """是否平衡（多空对冲）"""
        return abs(self.net_quantity) < 1e-8
    
    @property
    def long_ratio(self) -> float:
        """多头占比"""
        total = self.long_value + self.short_value
        return self.long_value / total if total > 0 else 0.0
    
    @property
    def short_ratio(self) -> float:
        """空头占比"""
        total = self.long_value + self.short_value
        return self.short_value / total if total > 0 else 0.0


@dataclass
class ExposureConfig:
    """敞口配置"""
    max_single_exposure: float = 0.2
    max_total_exposure: float = 1.0
    max_long_exposure: float = 0.8
    max_short_exposure: float = 0.8
    max_correlated_exposure: float = 0.5
    enable_auto_hedge: bool = False
    hedge_ratio: float = 0.5


class ExposureManager:
    """
    敞口管理器
    
    职责：
    1. 计算各品种敞口
    2. 监控敞口限制
    3. 敞口预警
    4. 相关性敞口控制
    """
    
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
        """更新敞口"""
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
        """获取敞口"""
        key = f"{exchange}:{symbol}"
        return self.exposures.get(key)
    
    def get_total_exposure(self, exposure_type: ExposureType = ExposureType.GROSS) -> float:
        """获取总敞口"""
        if exposure_type == ExposureType.LONG:
            return sum(e.long_value for e in self.exposures.values())
        elif exposure_type == ExposureType.SHORT:
            return sum(e.short_value for e in self.exposures.values())
        elif exposure_type == ExposureType.NET:
            return sum(abs(e.net_value) for e in self.exposures.values())
        else:
            return sum(e.gross_value for e in self.exposures.values())
    
    def get_exposure_ratio(self, capital: float) -> float:
        """获取敞口比率"""
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
        """
        检查敞口限制
        
        Returns:
            (是否通过, 原因)
        """
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
        """获取敞口预警"""
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
        """计算对冲建议"""
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
        """设置相关性"""
        if symbol1 not in self._correlation_matrix:
            self._correlation_matrix[symbol1] = {}
        if symbol2 not in self._correlation_matrix:
            self._correlation_matrix[symbol2] = {}
        
        self._correlation_matrix[symbol1][symbol2] = correlation
        self._correlation_matrix[symbol2][symbol1] = correlation
    
    def get_correlated_exposure(self, symbol: str, threshold: float = 0.7) -> float:
        """获取相关品种的总敞口"""
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
