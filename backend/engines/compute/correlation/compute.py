from typing import Dict, List, Optional
from dataclasses import dataclass

from infrastructure.logging import get_logger

logger = get_logger("engines.compute.correlation")


@dataclass
class SignalWeight:
    feature: str
    weight: float
    direction: str
    confidence: float
    strength: float


def compute_signal_weight(
    feature: str,
    assessment: Dict,
) -> SignalWeight:
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


def compute_all_weights(
    assessments: Dict[str, Dict],
) -> Dict[str, SignalWeight]:
    weights = {}
    for feature, assessment in assessments.items():
        weights[feature] = compute_signal_weight(feature, assessment)
    return weights


def filter_strong_signals(
    weights: Dict[str, SignalWeight],
    min_confidence: float = 0.7,
    direction: Optional[str] = None,
) -> List[SignalWeight]:
    strong = []
    for feature, sw in weights.items():
        if sw.confidence < min_confidence:
            continue
        if direction and sw.direction != direction:
            continue
        if sw.direction == "neutral":
            continue
        strong.append(sw)
    strong.sort(key=lambda x: x.confidence, reverse=True)
    return strong


def compute_signal_direction(
    feature: str,
    assessments: Dict[str, Dict],
) -> str:
    sw = compute_signal_weight(feature, assessments.get(feature, {}))
    return sw.direction


def compute_summary(
    result: Dict,
    symbol: str,
    timeframe: str,
    weights: Dict[str, SignalWeight],
) -> Dict:
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "available": bool(result),
        "timestamp": result.get("timestamp"),
        "summary": result.get("summary", {}),
        "positive_count": len(result.get("positive_signals", [])),
        "negative_count": len(result.get("negative_signals", [])),
        "neutral_count": len(result.get("neutral_signals", [])),
        "strong_positive": len(filter_strong_signals(weights, direction="positive")),
        "strong_negative": len(filter_strong_signals(weights, direction="negative")),
    }
