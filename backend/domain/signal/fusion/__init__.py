"""
Signal Fusion - 信号融合层

因为现在信号是分散的，需要统一融合机制。

包含：
- Voting - 投票机制
- Blending - 混合机制
- Consensus - 共识机制
- Ensemble - 集成机制
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from collections import defaultdict
import numpy as np

from domain.signal.models import Signal, SignalDirection, SignalConfidence, SignalStrength


@dataclass
class FusionResult:
    """融合结果"""
    direction: SignalDirection
    confidence: SignalConfidence
    strength: SignalStrength
    contributing_signals: List[str]  # 信号ID列表
    method: str  # 使用的融合方法
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VotingFusion:
    """投票融合 - 简单投票机制"""
    
    def __init__(self, majority_threshold: float = 0.5):
        self.majority_threshold = majority_threshold
    
    def fuse(self, signals: List[Signal]) -> FusionResult:
        if not signals:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="voting",
            )
        
        votes = defaultdict(int)
        total_confidence = 0.0
        weighted_votes = defaultdict(float)
        
        for signal in signals:
            if signal.is_active():
                direction = signal.direction
                weight = signal.confidence.value
                
                votes[direction] += 1
                weighted_votes[direction] += weight
                total_confidence += weight
        
        if not votes:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="voting",
            )
        
        majority_dir = max(votes.items(), key=lambda x: x[1])[0]
        weighted_majority = max(weighted_votes.items(), key=lambda x: x[1])[0]
        
        final_dir = weighted_majority if total_confidence > 0 else majority_dir
        
        avg_confidence = total_confidence / len(signals) if signals else 0.0
        avg_strength = np.mean([s.strength.magnitude for s in signals if s.is_active()])
        
        return FusionResult(
            direction=final_dir,
            confidence=SignalConfidence(value=avg_confidence),
            strength=SignalStrength(magnitude=avg_strength),
            contributing_signals=[str(s.signal_id) for s in signals if s.is_active()],
            method="voting",
            metadata={
                "votes": dict(votes),
                "weighted_votes": dict(weighted_votes),
            },
        )


class BlendingFusion:
    """混合融合 - 加权混合"""
    
    def __init__(self, weights: Optional[Dict[SignalDirection, float]] = None):
        self.weights = weights or {
            SignalDirection.LONG: 1.0,
            SignalDirection.SHORT: 1.0,
            SignalDirection.NEUTRAL: 0.5,
        }
    
    def fuse(self, signals: List[Signal]) -> FusionResult:
        if not signals:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="blending",
            )
        
        long_score = 0.0
        short_score = 0.0
        total_weight = 0.0
        
        contributing = []
        
        for signal in signals:
            if not signal.is_active():
                continue
            
            weight = signal.confidence.value * signal.strength.magnitude
            direction_weight = self.weights.get(signal.direction, 1.0)
            total_score = weight * direction_weight
            
            if signal.direction == SignalDirection.LONG:
                long_score += total_score
            elif signal.direction == SignalDirection.SHORT:
                short_score += total_score
            
            total_weight += weight
            contributing.append(str(signal.signal_id))
        
        if total_weight == 0:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="blending",
            )
        
        net_score = long_score - short_score
        
        if abs(net_score) < 0.1:
            direction = SignalDirection.NEUTRAL
        elif net_score > 0:
            direction = SignalDirection.LONG
        else:
            direction = SignalDirection.SHORT
        
        confidence = SignalConfidence(value=min(1.0, abs(net_score) / total_weight * 2))
        strength = SignalStrength(magnitude=min(1.0, abs(net_score) / total_weight * 2))
        
        return FusionResult(
            direction=direction,
            confidence=confidence,
            strength=strength,
            contributing_signals=contributing,
            method="blending",
            metadata={
                "long_score": long_score,
                "short_score": short_score,
                "net_score": net_score,
                "total_weight": total_weight,
            },
        )


class ConsensusFusion:
    """共识融合 - 只在达成共识时发出信号"""
    
    def __init__(self, consensus_threshold: float = 0.8):
        self.consensus_threshold = consensus_threshold
    
    def fuse(self, signals: List[Signal]) -> FusionResult:
        if not signals:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="consensus",
            )
        
        active_signals = [s for s in signals if s.is_active()]
        
        if not active_signals:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="consensus",
            )
        
        directions = [s.direction for s in active_signals]
        direction_counts = defaultdict(int)
        
        for d in directions:
            direction_counts[d] += 1
        
        max_count = max(direction_counts.values())
        consensus_ratio = max_count / len(active_signals)
        
        if consensus_ratio < self.consensus_threshold:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="consensus",
                metadata={"consensus_ratio": consensus_ratio},
            )
        
        consensus_dir = max(direction_counts.items(), key=lambda x: x[1])[0]
        
        consensus_signals = [s for s in active_signals if s.direction == consensus_dir]
        avg_confidence = np.mean([s.confidence.value for s in consensus_signals])
        avg_strength = np.mean([s.strength.magnitude for s in consensus_signals])
        
        return FusionResult(
            direction=consensus_dir,
            confidence=SignalConfidence(value=avg_confidence),
            strength=SignalStrength(magnitude=avg_strength),
            contributing_signals=[str(s.signal_id) for s in consensus_signals],
            method="consensus",
            metadata={
                "consensus_ratio": consensus_ratio,
                "total_active": len(active_signals),
            },
        )


class EnsembleFusion:
    """集成融合 - 多种方法的集成"""
    
    def __init__(self):
        self.voting = VotingFusion()
        self.blending = BlendingFusion()
        self.consensus = ConsensusFusion()
    
    def fuse(self, signals: List[Signal]) -> FusionResult:
        voting_result = self.voting.fuse(signals)
        blending_result = self.blending.fuse(signals)
        consensus_result = self.consensus.fuse(signals)
        
        results = [voting_result, blending_result, consensus_result]
        
        if consensus_result.direction != SignalDirection.NEUTRAL:
            return consensus_result
        
        active_results = [r for r in results if r.direction != SignalDirection.NEUTRAL]
        
        if not active_results:
            return FusionResult(
                direction=SignalDirection.NEUTRAL,
                confidence=SignalConfidence(value=0.0),
                strength=SignalStrength(magnitude=0.0),
                contributing_signals=[],
                method="ensemble",
            )
        
        direction_votes = defaultdict(float)
        for r in active_results:
            direction_votes[r.direction] += r.confidence.value
        
        final_dir = max(direction_votes.items(), key=lambda x: x[1])[0]
        
        avg_confidence = np.mean([r.confidence.value for r in active_results if r.direction == final_dir])
        avg_strength = np.mean([r.strength.magnitude for r in active_results if r.direction == final_dir])
        
        all_contributing = set()
        for r in active_results:
            all_contributing.update(r.contributing_signals)
        
        return FusionResult(
            direction=final_dir,
            confidence=SignalConfidence(value=avg_confidence),
            strength=SignalStrength(magnitude=avg_strength),
            contributing_signals=list(all_contributing),
            method="ensemble",
            metadata={
                "voting_result": voting_result.direction.value,
                "blending_result": blending_result.direction.value,
                "consensus_result": consensus_result.direction.value,
            },
        )
