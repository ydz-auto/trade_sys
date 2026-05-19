#!/usr/bin/env python3
"""
策略自动发现模块

功能：
1. 自动扫描市场数据，发现有统计显著性的模式
2. 将发现的模式转换成可执行的策略代码
3. 自动测试和验证策略
4. 将表现良好的策略自动添加到策略管理器
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
import pandas as pd
import numpy as np
from pathlib import Path

from infrastructure.logging import get_logger
from services.strategy_service.strategies import (
    BaseStrategy, StrategySignal, StrategyType, ActionType
)

logger = get_logger("strategy_discovery")


class PatternStrength(Enum):
    """模式强度"""
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    EXCELLENT = "excellent"


@dataclass
class DiscoveredPattern:
    """发现的模式"""
    pattern_id: str
    name: str
    description: str
    direction: int  # 1=做多, -1=做空
    win_rate: float
    avg_return: float
    sample_size: int
    confidence: float
    features: Dict[str, float]
    conditions: List[str]
    strength: PatternStrength
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class AutoDiscoveredStrategy(BaseStrategy):
    """自动发现的策略"""
    
    def __init__(
        self,
        strategy_id: str,
        pattern: DiscoveredPattern,
        default_quantity: float = 0.01,
    ):
        super().__init__(strategy_id)
        self.pattern = pattern
        self.default_quantity = default_quantity
    
    def evaluate_conditions(self, data: Dict, conditions: List[str]) -> bool:
        """
        评估条件是否满足
        
        简单的条件评估器
        """
        try:
            # 实现简单的条件评估逻辑
            # 在实际生产中可能需要更复杂的规则引擎
            local_vars = {
                "data": data,
                "np": np,
                "pd": pd,
            }
            
            for cond in conditions:
                # 这只是示例，实际需要更安全的方式
                # 在生产环境中，应该使用DSL而不是eval
                if not eval(cond, {}, local_vars):
                    return False
            
            return True
        except Exception as e:
            logger.error(f"Error evaluating conditions: {e}")
            return False
    
    def calculate(self, data: Dict) -> Optional[StrategySignal]:
        """执行自动发现的策略"""
        if not self._enabled:
            return None
        
        # 检查条件是否满足
        if not self.evaluate_conditions(data, self.pattern.conditions):
            return None
        
        current_price = data.get("close_prices", [0])[-1]
        symbol = data.get("symbol", "BTCUSDT")
        
        action = ActionType.LONG if self.pattern.direction == 1 else ActionType.SHORT
        
        signal = StrategySignal(
            strategy_id=self.strategy_id,
            strategy_type=StrategyType.ML_BASED,
            symbol=symbol,
            action=action,
            quantity=self.default_quantity,
            price=current_price,
            confidence=self.pattern.confidence,
            reason=f"Auto-discovered: {self.pattern.name}, "
                   f"Win rate: {self.pattern.win_rate*100:.1f}%, "
                   f"Avg return: {self.pattern.avg_return*100:.2f}%",
            metadata={
                "pattern_id": self.pattern.pattern_id,
                "win_rate": self.pattern.win_rate,
                "avg_return": self.pattern.avg_return,
                "sample_size": self.pattern.sample_size,
            },
        )
        
        return signal


class StrategyDiscoveryEngine:
    """策略发现引擎"""
    
    def __init__(
        self,
        data_path: str = None,
        min_win_rate: float = 0.6,
        min_sample_size: int = 50,
        min_avg_return: float = 0.005,
    ):
        self.min_win_rate = min_win_rate
        self.min_sample_size = min_sample_size
        self.min_avg_return = min_avg_return
        
        if data_path is None:
            data_path = Path(__file__).parent.parent.parent / "data_lake" / "features" / "binance"
        self.data_path = Path(data_path)
        
        self.discovered_patterns: Dict[str, DiscoveredPattern] = {}
        
        logger.info("StrategyDiscoveryEngine initialized")
    
    def load_market_data(self, symbol: str = "BTCUSDT") -> pd.DataFrame:
        """加载市场数据"""
        feature_path = self.data_path / symbol / "features_with_structure.parquet"
        
        if not feature_path.exists():
            logger.warning(f"Feature file not found: {feature_path}")
            return pd.DataFrame()
        
        df = pd.read_parquet(feature_path)
        logger.info(f"Loaded {len(df)} rows for {symbol}")
        
        return df
    
    def analyze_feature_distribution(self, df: pd.DataFrame, feature: str, target: str) -> Dict:
        """分析特征与目标的关系"""
        if feature not in df.columns or target not in df.columns:
            return {}
        
        df_clean = df[[feature, target]].dropna()
        if len(df_clean) < 100:
            return {}
        
        # 简单分析：计算分位数
        quantiles = np.percentile(df_clean[feature], [10, 25, 50, 75, 90])
        
        # 分析高/低值时的表现
        low_cutoff = quantiles[0]
        high_cutoff = quantiles[4]
        
        low_values = df_clean[df_clean[feature] <= low_cutoff]
        high_values = df_clean[df_clean[feature] >= high_cutoff]
        
        return {
            "feature": feature,
            "low_cutoff": low_cutoff,
            "high_cutoff": high_cutoff,
            "low_stats": {
                "count": len(low_values),
                "avg_return": low_values[target].mean(),
                "win_rate": (low_values[target] > 0).mean(),
            },
            "high_stats": {
                "count": len(high_values),
                "avg_return": high_values[target].mean(),
                "win_rate": (high_values[target] > 0).mean(),
            },
        }
    
    def scan_features(self, df: pd.DataFrame, target_feature: str = "future_ret_1h") -> List[Dict]:
        """扫描所有特征，发现有潜力的模式"""
        features_to_scan = [
            col for col in df.columns 
            if not col.startswith("timestamp") 
            and not col.startswith("close")
            and not col.startswith("high")
            and not col.startswith("low")
            and not col.startswith("open")
            and pd.api.types.is_numeric_dtype(df[col])  # 只扫描数值型特征
            and not pd.api.types.is_bool_dtype(df[col])  # 排除布尔类型
        ]
        
        promising_features = []
        
        for feature in features_to_scan[:50]:  # 限制扫描数量，避免性能问题
            analysis = self.analyze_feature_distribution(df, feature, target_feature)
            
            if not analysis:
                continue
            
            # 检查是否有统计显著性
            if (analysis["high_stats"]["win_rate"] >= self.min_win_rate and 
                analysis["high_stats"]["count"] >= self.min_sample_size):
                promising_features.append({
                    "feature": feature,
                    "side": "high",
                    "win_rate": analysis["high_stats"]["win_rate"],
                    "avg_return": analysis["high_stats"]["avg_return"],
                    "sample_size": analysis["high_stats"]["count"],
                    "cutoff": analysis["high_cutoff"],
                })
            
            if (analysis["low_stats"]["win_rate"] >= self.min_win_rate and 
                analysis["low_stats"]["count"] >= self.min_sample_size):
                promising_features.append({
                    "feature": feature,
                    "side": "low",
                    "win_rate": analysis["low_stats"]["win_rate"],
                    "avg_return": analysis["low_stats"]["avg_return"],
                    "sample_size": analysis["low_stats"]["count"],
                    "cutoff": analysis["low_cutoff"],
                })
        
        # 按预期收益排序
        promising_features.sort(
            key=lambda x: x["win_rate"] * x["avg_return"] * np.sqrt(x["sample_size"]),
            reverse=True
        )
        
        return promising_features
    
    def discover_patterns(self, df: pd.DataFrame) -> List[DiscoveredPattern]:
        """发现模式"""
        if df.empty:
            return []
        
        # 采样一部分数据以加快速度
        if len(df) > 10000:
            df = df.sample(10000, random_state=42).sort_index()
            logger.info(f"Sampled to {len(df)} rows for faster discovery")
        
        # 先计算未来收益（作为目标）
        df = df.copy()
        df["future_ret_1h"] = df["close"].pct_change(-12).shift(-12)
        
        # 扫描特征
        promising_features = self.scan_features(df)
        
        patterns = []
        
        for i, feature_info in enumerate(promising_features[:10]):  # 取前10个
            feature = feature_info["feature"]
            side = feature_info["side"]
            cutoff = feature_info["cutoff"]
            direction = 1 if feature_info["avg_return"] > 0 else -1
            
            # 生成条件
            if side == "high":
                condition = f"data.get('{feature}', 0) >= {cutoff}"
                name = f"High_{feature}"
            else:
                condition = f"data.get('{feature}', 0) <= {cutoff}"
                name = f"Low_{feature}"
            
            # 确定强度
            win_rate = feature_info["win_rate"]
            if win_rate >= 0.8:
                strength = PatternStrength.EXCELLENT
            elif win_rate >= 0.7:
                strength = PatternStrength.STRONG
            elif win_rate >= 0.6:
                strength = PatternStrength.MODERATE
            else:
                strength = PatternStrength.WEAK
            
            pattern = DiscoveredPattern(
                pattern_id=f"auto_pattern_{i}_{datetime.now().strftime('%Y%m%d')}",
                name=name,
                description=f"Auto-discovered pattern using {feature}",
                direction=direction,
                win_rate=feature_info["win_rate"],
                avg_return=feature_info["avg_return"],
                sample_size=feature_info["sample_size"],
                confidence=min(0.9, feature_info["win_rate"] * 0.5 + 0.4),
                features={feature: cutoff},
                conditions=[condition],
                strength=strength,
            )
            
            patterns.append(pattern)
            self.discovered_patterns[pattern.pattern_id] = pattern
        
        return patterns
    
    def convert_pattern_to_strategy(self, pattern: DiscoveredPattern) -> AutoDiscoveredStrategy:
        """将发现的模式转换成策略"""
        strategy = AutoDiscoveredStrategy(
            strategy_id=f"auto_{pattern.pattern_id}",
            pattern=pattern,
        )
        return strategy
    
    def backtest_pattern(self, df: pd.DataFrame, pattern: DiscoveredPattern) -> Dict:
        """回测发现的模式"""
        if df.empty:
            return {}
        
        df = df.copy()
        if "future_ret_1h" not in df.columns:
            df["future_ret_1h"] = df["close"].pct_change(-12).shift(-12)
        
        # 简单回测
        signals = []
        
        for _, row in df.iterrows():
            # 评估条件
            satisfied = True
            for feature, cutoff in pattern.features.items():
                if feature not in row:
                    satisfied = False
                    break
                
                if pattern.conditions[0].startswith("data.get"):
                    # 判断是大于还是小于
                    if ">=" in pattern.conditions[0]:
                        if row[feature] < cutoff:
                            satisfied = False
                    else:
                        if row[feature] > cutoff:
                            satisfied = False
            
            if satisfied:
                if "future_ret_1h" in row and not pd.isna(row["future_ret_1h"]):
                    signals.append({
                        "direction": pattern.direction,
                        "return": row["future_ret_1h"] * pattern.direction,
                    })
        
        if not signals:
            return {}
        
        returns = [s["return"] for s in signals]
        wins = sum(1 for r in returns if r > 0)
        
        return {
            "pattern_id": pattern.pattern_id,
            "sample_size": len(signals),
            "win_rate": wins / len(signals),
            "avg_return": np.mean(returns),
            "total_return": np.sum(returns),
            "sharpe": np.mean(returns) / (np.std(returns) + 1e-8) * np.sqrt(365 * 24),
        }
    
    def auto_discover_and_add(
        self,
        df: pd.DataFrame,
        orchestrator=None,
        max_strategies: int = 5,
    ) -> List[AutoDiscoveredStrategy]:
        """
        自动发现策略并添加到编排器
        
        Args:
            df: 市场数据
            orchestrator: 策略编排器（可选）
            max_strategies: 最多添加几个策略
        
        Returns:
            新发现的策略列表
        """
        logger.info("Starting auto strategy discovery...")
        
        # 发现模式
        patterns = self.discover_patterns(df)
        logger.info(f"Found {len(patterns)} candidate patterns")
        
        new_strategies = []
        
        for pattern in patterns[:max_strategies]:
            # 回测验证
            backtest_result = self.backtest_pattern(df, pattern)
            
            if not backtest_result:
                continue
            
            # 检查是否满足标准
            if (backtest_result["win_rate"] >= self.min_win_rate and
                backtest_result["avg_return"] >= self.min_avg_return and
                backtest_result["sample_size"] >= self.min_sample_size):
                
                # 转换为策略
                strategy = self.convert_pattern_to_strategy(pattern)
                new_strategies.append(strategy)
                
                # 如果有编排器，自动添加
                if orchestrator:
                    orchestrator.add_strategy(strategy)
                    logger.info(f"Auto-added strategy: {strategy.strategy_id}")
        
        logger.info(f"Auto-discovered and added {len(new_strategies)} strategies")
        return new_strategies
    
    def save_discovered_patterns(self, output_path: str):
        """保存发现的模式"""
        output = {
            "discovered_at": datetime.now().isoformat(),
            "patterns": [
                {
                    k: str(v) if isinstance(v, datetime) else v
                    for k, v in pattern.__dict__.items()
                }
                for pattern in self.discovered_patterns.values()
            ],
        }
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, "w") as f:
            json.dump(output, f, indent=2)
        
        logger.info(f"Discovered patterns saved to: {output_path}")
    
    def print_discovery_report(self):
        """打印发现报告"""
        print("\n" + "=" * 100)
        print("🤖 Auto Strategy Discovery Report")
        print("=" * 100)
        
        if not self.discovered_patterns:
            print("  No patterns discovered yet")
            return
        
        sorted_patterns = sorted(
            self.discovered_patterns.values(),
            key=lambda p: p.win_rate * p.avg_return * np.sqrt(p.sample_size),
            reverse=True
        )
        
        print(f"  Total patterns discovered: {len(self.discovered_patterns)}")
        print()
        
        for i, pattern in enumerate(sorted_patterns[:5], 1):
            direction = "LONG" if pattern.direction == 1 else "SHORT"
            print(f"  {i}. {pattern.name} ({direction})")
            print(f"     Win rate: {pattern.win_rate*100:.1f}%, Avg return: {pattern.avg_return*100:.2f}%")
            print(f"     Samples: {pattern.sample_size}, Strength: {pattern.strength.value}")
            print(f"     Conditions: {pattern.conditions}")
            print()


def demo_auto_discovery():
    """演示策略自动发现"""
    print("\n" + "=" * 100)
    print("🚀 Strategy Auto-Discovery Demo")
    print("=" * 100)
    
    engine = StrategyDiscoveryEngine(
        min_win_rate=0.6,
        min_sample_size=50,
        min_avg_return=0.005,
    )
    
    df = engine.load_market_data()
    
    if not df.empty:
        new_strategies = engine.auto_discover_and_add(df)
        engine.print_discovery_report()
        
        if new_strategies:
            output_path = Path(__file__).parent.parent / "data_lake" / "research" / "auto_discovered_patterns.json"
            engine.save_discovered_patterns(str(output_path))
            
            print(f"\n✅ {len(new_strategies)} new strategies discovered!")
            for s in new_strategies:
                print(f"   - {s.strategy_id}: {s.pattern.name}")
    
    return engine


if __name__ == "__main__":
    demo_auto_discovery()
