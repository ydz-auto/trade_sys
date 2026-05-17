"""
Correlation Strategy Adapter - 策略模块读取接口

供策略模块（AlphaPipeline / FusionEngine）使用，
根据相关性分析结果动态调整信号权重。

用法:
    from services.correlation_service.strategy_adapter import get_correlation_adapter

    adapter = get_correlation_adapter()
    weight = adapter.get_signal_weight("rsi_14", "BTC", "1h")
    strong_signals = adapter.get_strong_signals("BTC", "1h", min_confidence=0.7)
"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from infrastructure.logging import get_logger

logger = get_logger("correlation_service.strategy")


@dataclass
class SignalWeight:
    """信号权重"""
    feature: str
    weight: float          # 正=增强, 负=反转, 1.0=默认
    direction: str         # positive / negative / neutral
    confidence: float
    strength: float


class CorrelationStrategyAdapter:
    """
    相关性策略适配器

    功能：
    1. 读取最新的 correlation 分析结果
    2. 将信号方向性转换为策略权重
    3. 提供强信号查询接口
    """

    def __init__(self, results_dir: str = "./data/correlation_results"):
        self.results_dir = Path(results_dir)
        self._cache: Dict[str, Dict] = {}  # symbol:timeframe -> result
        self._last_refresh: Optional[datetime] = None

    def refresh(self):
        """刷新结果缓存（从文件系统读取最新结果）"""
        if not self.results_dir.exists():
            logger.debug(f"Results directory not found: {self.results_dir}")
            return

        for result_file in self.results_dir.rglob("correlation_*.json"):
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                symbol = data.get("symbol", "UNKNOWN")
                timeframe = data.get("timeframe", "1h")
                cache_key = f"{symbol}:{timeframe}"

                # 只更新更新的结果
                existing = self._cache.get(cache_key)
                if existing is None or data.get("timestamp", "") > existing.get("timestamp", ""):
                    self._cache[cache_key] = data

            except Exception as e:
                logger.debug(f"Failed to read result file {result_file}: {e}")

        self._last_refresh = datetime.now()
        logger.debug(f"Refreshed correlation cache: {len(self._cache)} results")

    def update_from_kafka(self, result_dict: Dict, symbol: str, timeframe: str):
        """从 Kafka 消息更新缓存"""
        cache_key = f"{symbol}:{timeframe}"
        self._cache[cache_key] = result_dict
        self._last_refresh = datetime.now()

    def get_signal_weight(
        self,
        feature: str,
        symbol: str = "BTC",
        timeframe: str = "1h",
    ) -> SignalWeight:
        """
        获取信号权重

        规则：
        - 正相关 + 高置信度 → weight > 1.0（增强）
        - 负相关 + 高置信度 → weight < 0（反转）
        - 中性 → weight = 1.0（默认）
        """
        self._auto_refresh()

        cache_key = f"{symbol}:{timeframe}"
        result = self._cache.get(cache_key, {})
        assessments = result.get("signal_assessments", {})
        assessment = assessments.get(feature, {})

        direction = assessment.get("direction", "neutral")
        confidence = assessment.get("confidence", 0)
        strength = assessment.get("strength", 0)

        if direction == "positive" and confidence > 0.6:
            weight = 1.0 + strength * 0.5
        elif direction == "negative" and confidence > 0.6:
            weight = -(strength * 0.5)
        else:
            weight = 1.0

        return SignalWeight(
            feature=feature,
            weight=round(weight, 4),
            direction=direction,
            confidence=confidence,
            strength=strength,
        )

    def get_all_weights(
        self,
        symbol: str = "BTC",
        timeframe: str = "1h",
    ) -> Dict[str, SignalWeight]:
        """获取所有信号权重"""
        self._auto_refresh()

        cache_key = f"{symbol}:{timeframe}"
        result = self._cache.get(cache_key, {})
        assessments = result.get("signal_assessments", {})

        weights = {}
        for feature in assessments:
            weights[feature] = self.get_signal_weight(feature, symbol, timeframe)

        return weights

    def get_strong_signals(
        self,
        symbol: str = "BTC",
        timeframe: str = "1h",
        min_confidence: float = 0.7,
        direction: Optional[str] = None,
    ) -> List[SignalWeight]:
        """
        获取强信号列表

        Args:
            symbol: 交易对
            timeframe: 时间周期
            min_confidence: 最小置信度
            direction: 过滤方向 (positive/negative/None=全部)
        """
        all_weights = self.get_all_weights(symbol, timeframe)

        strong = []
        for feature, sw in all_weights.items():
            if sw.confidence < min_confidence:
                continue
            if direction and sw.direction != direction:
                continue
            if sw.direction == "neutral":
                continue
            strong.append(sw)

        # 按置信度排序
        strong.sort(key=lambda x: x.confidence, reverse=True)
        return strong

    def get_signal_direction(
        self,
        feature: str,
        symbol: str = "BTC",
        timeframe: str = "1h",
    ) -> str:
        """快速获取信号方向"""
        sw = self.get_signal_weight(feature, symbol, timeframe)
        return sw.direction

    def get_positive_signals(self, symbol: str = "BTC", timeframe: str = "1h") -> List[str]:
        """获取所有正相关信号"""
        result = self._cache.get(f"{symbol}:{timeframe}", {})
        return result.get("positive_signals", [])

    def get_negative_signals(self, symbol: str = "BTC", timeframe: str = "1h") -> List[str]:
        """获取所有负相关信号"""
        result = self._cache.get(f"{symbol}:{timeframe}", {})
        return result.get("negative_signals", [])

    def get_summary(self, symbol: str = "BTC", timeframe: str = "1h") -> Dict:
        """获取分析摘要"""
        self._auto_refresh()

        cache_key = f"{symbol}:{timeframe}"
        result = self._cache.get(cache_key, {})

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "available": cache_key in self._cache,
            "timestamp": result.get("timestamp"),
            "summary": result.get("summary", {}),
            "positive_count": len(result.get("positive_signals", [])),
            "negative_count": len(result.get("negative_signals", [])),
            "neutral_count": len(result.get("neutral_signals", [])),
            "strong_positive": len(self.get_strong_signals(symbol, timeframe, direction="positive")),
            "strong_negative": len(self.get_strong_signals(symbol, timeframe, direction="negative")),
        }

    def _auto_refresh(self):
        """自动刷新（每60秒最多一次）"""
        if self._last_refresh is None:
            self.refresh()
        elif (datetime.now() - self._last_refresh).total_seconds() > 60:
            self.refresh()


# ──────────────────────────────────────────────
# 全局实例
# ──────────────────────────────────────────────

_adapter: Optional[CorrelationStrategyAdapter] = None


def get_correlation_adapter(
    results_dir: str = "./data/correlation_results"
) -> CorrelationStrategyAdapter:
    """获取策略适配器单例"""
    global _adapter
    if _adapter is None:
        _adapter = CorrelationStrategyAdapter(results_dir)
    return _adapter
