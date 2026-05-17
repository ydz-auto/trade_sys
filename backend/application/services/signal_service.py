"""
Signal Service - 信号生成业务服务

职责：
- 事件检测逻辑
- 信号融合逻辑
- 策略决策逻辑

注意：这是纯业务逻辑，不包含 Kafka、Redis 等基础设施代码。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import defaultdict


@dataclass
class Event:
    """事件"""
    event_id: str
    event_type: str
    symbol: str
    direction: str
    strength: float
    timestamp: datetime
    metadata: Dict[str, Any] = None


@dataclass
class Signal:
    """信号"""
    signal_id: str
    symbol: str
    direction: str
    confidence: float
    event_count: int
    timestamp: datetime
    metadata: Dict[str, Any] = None
    market_type: str = "spot"  # spot, futures, perpetual
    leverage: int = 1  # 杠杆倍数
    entry_price: float = 0.0  # 预估入场价格
    risk_reward_ratio: float = 2.0  # 风险收益比


@dataclass
class Decision:
    """决策"""
    decision_id: str
    symbol: str
    action: str
    quantity: float
    confidence: float
    reason: str
    timestamp: datetime
    # 合约相关字段
    leverage: int = 1
    stop_loss_price: float = 0.0
    take_profit_price: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_pct: float = 0.0
    estimated_fees: float = 0.0
    risk_amount: float = 0.0  # 风险金额 USDT
    market_type: str = "perpetual"
    metadata: Dict[str, Any] = None


class EventDetector:
    """事件检测器 - 纯业务逻辑"""
    
    EVENT_PATTERNS = {
        "inflow": {"type": "etf_inflow", "direction": "bullish"},
        "outflow": {"type": "etf_outflow", "direction": "bearish"},
        "hack": {"type": "protocol_hack", "direction": "bearish"},
        "adoption": {"type": "adoption", "direction": "bullish"},
        "institutional": {"type": "institutional", "direction": "bullish"},
    }
    
    def detect(self, title: str, content: str) -> Optional[Dict[str, Any]]:
        """检测事件"""
        text = (title + " " + content).lower()
        
        for keyword, pattern in self.EVENT_PATTERNS.items():
            if keyword in text:
                return {
                    "event_type": pattern["type"],
                    "direction": pattern["direction"],
                    "strength": 0.7 + (0.3 * hash(title) % 100 / 100),
                    "asset": self._extract_asset(text),
                }
        
        return None
    
    def _extract_asset(self, text: str) -> str:
        """提取资产"""
        if "eth" in text or "ethereum" in text:
            return "ETH"
        elif "sol" in text or "solana" in text:
            return "SOL"
        return "BTC"


class SignalFusionEngine:
    """信号融合引擎 - 纯业务逻辑"""
    
    def __init__(self, window_seconds: int = 300, min_events: int = 1):
        self.window_seconds = window_seconds
        self.min_events = min_events
        self._events: List[Event] = []
    
    def add_event(self, event: Event) -> None:
        """添加事件"""
        self._events.append(event)
        self._cleanup_old_events()
    
    def _cleanup_old_events(self) -> None:
        """清理过期事件"""
        now = datetime.now()
        cutoff = now.timestamp() - self.window_seconds
        self._events = [e for e in self._events if e.timestamp.timestamp() > cutoff]
    
    def fuse(self) -> List[Signal]:
        """融合事件生成信号"""
        if len(self._events) < self.min_events:
            return []
        
        asset_map = defaultdict(lambda: {"bullish": 0.0, "bearish": 0.0, "events": []})
        
        for event in self._events:
            asset = event.symbol
            direction = event.direction
            
            if direction in ("bullish", "bearish"):
                asset_map[asset][direction] += event.strength
                asset_map[asset]["events"].append(event)
        
        signals = []
        
        for asset, data in asset_map.items():
            net = data["bullish"] - data["bearish"]
            
            if abs(net) < 0.05:
                continue
            
            direction = "bullish" if net > 0 else "bearish"
            confidence = abs(net)
            
            signal = Signal(
                signal_id=f"sig_{asset}_{datetime.now().timestamp()}",
                symbol=asset,
                direction=direction,
                confidence=confidence,
                event_count=len(data["events"]),
                timestamp=datetime.now(),
            )
            signals.append(signal)
        
        return signals


class DecisionEngine:
    """决策引擎 - 纯业务逻辑"""
    
    # 合约交易参数（支持 25-50x 杠杆）
    # 注意：这里的止损/止盈是杠杆后的资金损失百分比，不是价格变动百分比！
    DEFAULT_STOP_LOSS_PCT = 10.0  # 默认止损：总资金损失 10%（杠杆后）
    DEFAULT_TAKE_PROFIT_PCT = 20.0  # 默认止盈：总资金收益 20%（杠杆后）
    DEFAULT_LEVERAGE = 20  # 默认杠杆 20x
    MAX_LEVERAGE = 50  # 最大杠杆 50x
    MIN_LEVERAGE = 10  # 最小杠杆 10x
    FEE_RATE = 0.0004  # 合约手续费率约 0.04%
    
    # 爆仓安全边际
    LIQUIDATION_SAFETY_MARGIN = 0.15  # 15% 安全边际（防止被强平）
    
    def __init__(
        self,
        default_leverage: int = None,
        default_stop_loss_pct: float = None,
        default_take_profit_pct: float = None,
        risk_reward_ratio: float = 2.0,
    ):
        self.default_leverage = default_leverage or self.DEFAULT_LEVERAGE
        self.default_stop_loss_pct = default_stop_loss_pct or self.DEFAULT_STOP_LOSS_PCT
        self.default_take_profit_pct = default_take_profit_pct or self.DEFAULT_TAKE_PROFIT_PCT
        self.risk_reward_ratio = risk_reward_ratio
    
    def decide(self, signal: Signal) -> Decision:
        """根据信号生成决策，包含止损/止盈计算
        
        高杠杆合约交易规则：
        - 杠杆范围：10x - 50x
        - 止损设置：杠杆后总资金损失 10% → 对应价格变动 10% / 杠杆
        - 止盈设置：杠杆后总资金收益 20% → 对应价格变动 20% / 杠杆
        - 风险收益比：1:2
        """
        confidence = signal.confidence
        leverage = signal.leverage or self.default_leverage
        
        # 限制杠杆范围在 10-50x
        leverage = max(self.MIN_LEVERAGE, min(leverage, self.MAX_LEVERAGE))
        market_type = signal.market_type or "perpetual"  # 默认永续合约
        entry_price = signal.entry_price or 1.0
        
        # 根据置信度调整杠杆（高置信度可用更高杠杆）
        if confidence > 0.85:
            leverage = min(leverage, 50)  # 高置信度最多 50x
        elif confidence > 0.75:
            leverage = min(leverage, 30)  # 中高置信度最多 30x
        elif confidence > 0.65:
            leverage = min(leverage, 20)  # 中置信度最多 20x
        else:
            leverage = min(leverage, 15)  # 低置信度最多 15x
        
        if confidence < 0.1:
            action = "HOLD"
            quantity = 0.0
            reason = "信号模糊"
            leverage = 1
            stop_loss_pct = 0.0
            take_profit_pct = 0.0
        elif signal.direction == "bullish":
            action = "LONG"
            quantity = min(confidence * 0.08, 0.1)
            reason = f"信号看涨，置信度 {confidence:.3f}"
            
            # 合约模式：按杠杆后资金损失计算止损/止盈
            if market_type in ("futures", "perpetual"):
                # 杠杆后资金损失 10% → 价格变动 = 10% / 杠杆
                stop_loss_pct = self.default_stop_loss_pct / leverage
                # 杠杆后资金收益 20% → 价格变动 = 20% / 杠杆
                take_profit_pct = self.default_take_profit_pct / leverage
            else:
                stop_loss_pct = self.default_stop_loss_pct
                take_profit_pct = self.default_take_profit_pct
                
        elif signal.direction == "bearish":
            action = "SHORT"
            quantity = min(confidence * 0.08, 0.1)
            reason = f"信号看跌，置信度 {confidence:.3f}"
            
            # 合约模式：按杠杆后资金损失计算止损/止盈
            if market_type in ("futures", "perpetual"):
                stop_loss_pct = self.default_stop_loss_pct / leverage
                take_profit_pct = self.default_take_profit_pct / leverage
            else:
                stop_loss_pct = self.default_stop_loss_pct
                take_profit_pct = self.default_take_profit_pct
        else:
            action = "HOLD"
            quantity = 0.0
            reason = "中性信号"
            leverage = 1
            stop_loss_pct = 0.0
            take_profit_pct = 0.0
        
        # 计算止损/止盈价格
        if action in ("LONG", "SHORT") and entry_price > 0:
            if action == "LONG":
                stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
                take_profit_price = entry_price * (1 + take_profit_pct / 100)
            else:
                stop_loss_price = entry_price * (1 + stop_loss_pct / 100)
                take_profit_price = entry_price * (1 - take_profit_pct / 100)
        else:
            stop_loss_price = 0.0
            take_profit_price = 0.0
        
        # 计算预估手续费（开仓 + 平仓）
        position_value = quantity * entry_price if entry_price > 0 else 0
        estimated_fees = position_value * self.FEE_RATE * 2
        
        # 计算风险金额
        risk_amount = position_value * (stop_loss_pct / 100) if stop_loss_pct > 0 else 0
        
        # 计算爆仓价格（带安全边际）
        # 止损 10% + 15% 安全边际 = 距爆仓约 25%
        if action in ("LONG", "SHORT") and leverage > 1:
            if action == "LONG":
                # 多头爆仓价 = 止损价下方 15%
                liquidation_price = stop_loss_price * (1 - self.LIQUIDATION_SAFETY_MARGIN)
            else:
                # 空头爆仓价 = 止损价上方 15%
                liquidation_price = stop_loss_price * (1 + self.LIQUIDATION_SAFETY_MARGIN)
        else:
            liquidation_price = 0.0
        
        # 计算距爆仓距离百分比
        if liquidation_price > 0 and entry_price > 0:
            if action == "LONG":
                liquidation_distance_pct = ((entry_price - liquidation_price) / entry_price) * 100
            else:
                liquidation_distance_pct = ((liquidation_price - entry_price) / entry_price) * 100
        else:
            liquidation_distance_pct = 0.0
        
        return Decision(
            decision_id=f"dec_{signal.symbol}_{datetime.now().timestamp()}",
            symbol=signal.symbol,
            action=action,
            quantity=quantity,
            confidence=confidence,
            reason=reason,
            timestamp=datetime.now(),
            # 合约相关字段
            leverage=leverage,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            stop_loss_pct=stop_loss_pct,
            take_profit_pct=take_profit_pct,
            estimated_fees=estimated_fees,
            risk_amount=risk_amount,
            market_type=market_type,
            metadata={
                "liquidation_price": liquidation_price,
                "liquidation_distance_pct": liquidation_distance_pct,
                "safety_margin": self.LIQUIDATION_SAFETY_MARGIN,
            }
        )


class SignalService:
    """
    Signal Service - 信号生成业务服务
    
    编排事件检测、信号融合、决策生成的完整流程。
    这是纯业务逻辑层，不包含任何基础设施代码。
    """
    
    def __init__(
        self,
        fusion_window_seconds: int = 300,
        fusion_min_events: int = 1,
        default_leverage: int = 3,
        default_stop_loss_pct: float = 2.0,
        default_take_profit_pct: float = 6.0,
        risk_reward_ratio: float = 2.0,
    ):
        self.event_detector = EventDetector()
        self.fusion_engine = SignalFusionEngine(
            window_seconds=fusion_window_seconds,
            min_events=fusion_min_events,
        )
        self.decision_engine = DecisionEngine(
            default_leverage=default_leverage,
            default_stop_loss_pct=default_stop_loss_pct,
            default_take_profit_pct=default_take_profit_pct,
            risk_reward_ratio=risk_reward_ratio,
        )
    
    def detect_event(self, title: str, content: str) -> Optional[Dict[str, Any]]:
        """检测事件（纯业务逻辑）"""
        return self.event_detector.detect(title, content)
    
    def process_event(self, event: Event) -> List[Signal]:
        """处理事件生成信号（纯业务逻辑）"""
        self.fusion_engine.add_event(event)
        return self.fusion_engine.fuse()
    
    def generate_decision(self, signal: Signal) -> Decision:
        """生成决策（纯业务逻辑）"""
        return self.decision_engine.decide(signal)
    
    def process_raw_data(
        self,
        title: str,
        content: str,
        trace_id: str = None,
    ) -> List[Decision]:
        """
        处理原始数据的完整流程（纯业务逻辑）
        
        这是业务用例的入口点，编排整个业务流程。
        """
        detected = self.detect_event(title, content)
        if not detected:
            return []
        
        event = Event(
            event_id=f"evt_{trace_id or datetime.now().timestamp()}",
            event_type=detected["event_type"],
            symbol=detected["asset"],
            direction=detected["direction"],
            strength=detected["strength"],
            timestamp=datetime.now(),
        )
        
        signals = self.process_event(event)
        
        decisions = []
        for signal in signals:
            decision = self.generate_decision(signal)
            decisions.append(decision)
        
        return decisions
