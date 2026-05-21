"""
Symbol-Specific Strategy Config - 币种专属策略配置

支持每个币种单独配置策略参数，包括：
- 技术指标参数
- 策略触发阈值
- 风险参数
- 杠杆设置
"""

from typing import Any, Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass, field
import yaml

from pydantic import BaseModel, Field, field_validator


@dataclass
class RSIStrategyParams:
    """RSI策略参数"""
    period: int = 14
    oversold: float = 30.0
    overbought: float = 70.0
    default_quantity: float = 0.01


@dataclass
class MACDStrategyParams:
    """MACD策略参数"""
    fast_period: int = 12
    slow_period: int = 26
    signal_period: int = 9
    default_quantity: float = 0.01


@dataclass
class PanicReversalParams:
    """恐慌反转策略参数"""
    drop_threshold: float = -0.015
    volume_ratio_threshold: float = 1.5
    default_quantity: float = 0.01


@dataclass
class LongLiquidationBounceParams:
    """多头踩踏反弹策略参数"""
    drop_threshold: float = -0.02
    rsi_threshold: float = 25.0
    volume_ratio_threshold: float = 2.0
    default_quantity: float = 0.01


@dataclass
class VolumeClimaxFadeParams:
    """放量高潮衰竭策略参数"""
    volume_ratio_threshold: float = 2.0
    upper_shadow_threshold: float = 0.3
    price_threshold: float = 0.003
    default_quantity: float = 0.01


@dataclass
class WeakBounceShortParams:
    """弱反弹做空策略参数"""
    drop_threshold_4h: float = -0.02
    bounce_min: float = 0.003
    bounce_max: float = 0.015
    volume_ratio_threshold: float = 1.5
    default_quantity: float = 0.01


@dataclass
class RiskParams:
    """风险参数"""
    position_size: float = 0.02
    max_leverage: int = 20
    min_leverage: int = 10
    stop_loss_pct: float = 10.0
    take_profit_pct: float = 20.0
    max_position_value: float = 10000.0


class SymbolStrategyConfig(BaseModel):
    """币种策略配置"""
    symbol: str = Field(..., description="交易对，如BTCUSDT")
    base_currency: str = Field(..., description="基础币种，如BTC")
    quote_currency: str = Field(default="USDT", description="计价币种")
    
    enabled: bool = Field(default=True, description="是否启用该币种策略")
    description: str = Field(default="", description="策略描述")
    
    # 市场特征参数
    volatility_profile: str = Field(default="medium", description="波动率特征: low/medium/high")
    liquidity_profile: str = Field(default="high", description="流动性特征: low/medium/high")
    
    # 风险参数
    risk: RiskParams = Field(default_factory=RiskParams)
    
    # 策略参数
    rsi_strategy: RSIStrategyParams = Field(default_factory=RSIStrategyParams)
    macd_strategy: MACDStrategyParams = Field(default_factory=MACDStrategyParams)
    panic_reversal: PanicReversalParams = Field(default_factory=PanicReversalParams)
    long_liquidation_bounce: LongLiquidationBounceParams = Field(default_factory=LongLiquidationBounceParams)
    volume_climax_fade: VolumeClimaxFadeParams = Field(default_factory=VolumeClimaxFadeParams)
    weak_bounce_short: WeakBounceShortParams = Field(default_factory=WeakBounceShortParams)
    
    # 策略启用状态
    enabled_strategies: List[str] = Field(default_factory=lambda: [
        "rsi_strategy",
        "macd_strategy", 
        "panic_reversal",
        "long_liquidation_bounce",
        "volume_climax_fade",
        "weak_bounce_short"
    ])
    
    # 时间周期配置
    primary_timeframe: str = Field(default="1h", description="主周期")
    confirmation_timeframe: str = Field(default="4h", description="确认周期")
    
    # 因子权重
    factor_weights: Dict[str, float] = Field(default_factory=lambda: {
        "momentum": 0.3,
        "trend": 0.3,
        "flow": 0.2,
        "sentiment": 0.2
    })
    
    # 其他元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @field_validator('factor_weights')
    @classmethod
    def validate_weights(cls, v):
        total = sum(v.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"因子权重之和必须为1.0，当前为{total}")
        return v
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SymbolStrategyConfig':
        """从字典创建"""
        return cls(**data)


class SymbolStrategyConfigManager:
    """币种策略配置管理器"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir or "config/strategy/symbols")
        self._configs: Dict[str, SymbolStrategyConfig] = {}
        self._load_all_configs()
    
    def _load_all_configs(self):
        """加载所有币种配置"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
            return
        
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                symbol = config_file.stem.upper()
                config = self._load_config(config_file)
                self._configs[symbol] = config
            except Exception as e:
                print(f"Failed to load config {config_file}: {e}")
    
    def _load_config(self, config_file: Path) -> SymbolStrategyConfig:
        """加载单个配置文件"""
        with open(config_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return SymbolStrategyConfig.from_dict(data)
    
    def get_config(self, symbol: str) -> Optional[SymbolStrategyConfig]:
        """获取币种配置"""
        symbol_upper = symbol.upper()
        return self._configs.get(symbol_upper)
    
    def get_all_configs(self) -> Dict[str, SymbolStrategyConfig]:
        """获取所有配置"""
        return self._configs.copy()
    
    def get_enabled_symbols(self) -> List[str]:
        """获取启用的币种列表"""
        return [
            symbol for symbol, config in self._configs.items()
            if config.enabled
        ]
    
    def save_config(self, config: SymbolStrategyConfig, overwrite: bool = False):
        """保存币种配置"""
        if not self.config_dir.exists():
            self.config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = self.config_dir / f"{config.symbol.lower()}.yaml"
        
        if config_file.exists() and not overwrite:
            raise FileExistsError(f"Config for {config.symbol} already exists")
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config.to_dict(), f, default_flow_style=False, allow_unicode=True)
        
        self._configs[config.symbol.upper()] = config
    
    def create_default_config(self, symbol: str, base_currency: str = None) -> SymbolStrategyConfig:
        """创建默认配置"""
        if base_currency is None:
            base_currency = symbol.replace("USDT", "").replace("USD", "")
        
        # 根据币种特性调整默认参数
        config = SymbolStrategyConfig(
            symbol=symbol,
            base_currency=base_currency,
            description=f"Default strategy config for {symbol}"
        )
        
        # 高波动币种调整
        if base_currency in ["SOL", "AVAX", "DOGE", "SHIB"]:
            config.volatility_profile = "high"
            config.risk.max_leverage = 15
            config.risk.position_size = 0.015
            config.panic_reversal.drop_threshold = -0.025
            config.long_liquidation_bounce.drop_threshold = -0.03
        
        # 低波动币种调整
        elif base_currency in ["BTC", "ETH"]:
            config.volatility_profile = "medium"
            config.risk.max_leverage = 25
            config.risk.position_size = 0.025
        
        return config
    
    def reload_config(self, symbol: str):
        """重新加载指定币种配置"""
        config_file = self.config_dir / f"{symbol.lower()}.yaml"
        if config_file.exists():
            config = self._load_config(config_file)
            self._configs[symbol.upper()] = config
    
    def reload_all(self):
        """重新加载所有配置"""
        self._configs.clear()
        self._load_all_configs()


# 全局配置管理器实例
_symbol_config_manager: Optional[SymbolStrategyConfigManager] = None


def get_symbol_config_manager(config_dir: str = None) -> SymbolStrategyConfigManager:
    """获取币种配置管理器单例"""
    global _symbol_config_manager
    if _symbol_config_manager is None:
        _symbol_config_manager = SymbolStrategyConfigManager(config_dir)
    return _symbol_config_manager
