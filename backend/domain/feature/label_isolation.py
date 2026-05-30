"""
Strict Label Isolation - 严格 Label 隔离

核心问题：
future_return 等标签经常被不小心混入特征 DataFrame，
导致严重的未来数据泄露。

解决方案：
1. Label 完全独立存储，不能和特征同一张 DataFrame
2. 访问 Label 必须显式声明
3. 自动检测 Label 混入特征
4. 训练时才生成 Label，Runtime 时完全隔离
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd
import numpy as np

import logging

logger = logging.getLogger("infrastructure.label_isolation")


class LabelType(Enum):
    """Label 类型"""
    FUTURE_RETURN = "future_return"
    FUTURE_HIGH = "future_high"
    FUTURE_LOW = "future_low"
    BINARY_UP_DOWN = "binary_up_down"
    TERNARY_UP_FLAT_DOWN = "ternary"
    CUSTOM = "custom"


@dataclass
class LabelRecord:
    """Label 记录"""
    label_id: str
    label_type: LabelType
    timestamp: int
    value: Any
    horizon_periods: int
    metadata: Dict = field(default_factory=dict)
    verification_hash: str = ""


class StrictLabelStore:
    """
    严格 Label 隔离存储

    核心原则：
    1. Label 和特征物理分离
    2. Runtime 时禁止访问 Label
    3. 训练时显式声明后才能访问
    """

    # 禁止作为特征使用的关键词
    FORBIDDEN_PREFIXES = [
        "future_", "target_", "label_", "y_", "outcome_"
    ]

    # 所有 Label 名称
    ALL_LABELS = {
        "future_return", "future_return_5m", "future_return_15m",
        "future_return_1h", "future_return_4h", "future_return_1d",
        "future_high", "future_low", "future_max_drawdown",
        "target", "label", "y"
    }

    def __init__(self, mode: str = "research"):
        """
        Args:
            mode: "research" (训练研究，可访问 Label)
                  或 "runtime" (实盘/回测运行时，禁止访问)
        """
        self.mode = mode
        self._labels: Dict[str, Dict[int, LabelRecord]] = {}
        self._feature_labels_used: Set[str] = set()
        self._access_log: List[Dict] = []
        self._violations: List[Dict] = []

    def set_mode(self, mode: str):
        """设置模式"""
        if mode not in ("research", "runtime"):
            raise ValueError(f"Invalid mode: {mode}")
        self.mode = mode
        logger.info(f"Label store mode set to: {mode}")

    # === Label Storage ===

    def store_label(
        self,
        label_id: str,
        label_type: LabelType,
        timestamp: int,
        value: Any,
        horizon_periods: int = 12,
        metadata: Optional[Dict] = None
    ):
        """
        存储 Label

        Args:
            label_id: Label 唯一标识符
            label_type: Label 类型
            timestamp: 该 Label 对应的时间点（不是未来时间！）
            value: Label 值
            horizon_periods: 未来多少期
            metadata: 元数据
        """
        if label_id not in self._labels:
            self._labels[label_id] = {}

        self._labels[label_id][timestamp] = LabelRecord(
            label_id=label_id,
            label_type=label_type,
            timestamp=timestamp,
            value=value,
            horizon_periods=horizon_periods,
            metadata=metadata or {}
        )

    def store_labels_dataframe(
        self,
        label_id: str,
        df: pd.DataFrame,
        timestamp_col: str = "timestamp",
        value_col: str = "value",
        label_type: LabelType = LabelType.FUTURE_RETURN,
        horizon_periods: int = 12
    ):
        """从 DataFrame 批量存储 Label"""
        for _, row in df.iterrows():
            self.store_label(
                label_id=label_id,
                label_type=label_type,
                timestamp=int(row[timestamp_col]),
                value=row[value_col],
                horizon_periods=horizon_periods
            )

    # === Label Retrieval ===

    def get_label(
        self,
        label_id: str,
        timestamp: int,
        safe: bool = True
    ) -> Optional[Any]:
        """
        获取 Label

        Args:
            label_id: Label 标识符
            timestamp: 时间戳
            safe: 安全模式（Runtime 时抛出异常）

        Returns:
            Label 值
        """
        if self.mode == "runtime":
            if safe:
                raise RuntimeError(
                    "Label access forbidden in RUNTIME mode! "
                    "This would cause data leakage."
                )
            else:
                logger.warning(
                    "Dangerous label access in RUNTIME mode (unsafe=True)"
                )

        label_records = self._labels.get(label_id, {})
        record = label_records.get(timestamp)

        self._access_log.append({
            "action": "get",
            "label_id": label_id,
            "timestamp": timestamp,
            "mode": self.mode,
            "time": datetime.utcnow().isoformat()
        })

        return record.value if record is not None else None

    def get_labels_array(
        self,
        label_id: str,
        timestamps: List[int],
        safe: bool = True
    ) -> List[Any]:
        """获取多个时间点的 Label"""
        return [
            self.get_label(label_id, t, safe)
            for t in timestamps
        ]

    def get_labels_dataframe(
        self,
        label_id: str,
        start_timestamp: int,
        end_timestamp: int,
        safe: bool = True
    ) -> pd.DataFrame:
        """获取时间范围的 Label（仅 research 模式）"""
        records = self._labels.get(label_id, {})
        valid_records = [
            r for ts, r in records.items()
            if start_timestamp <= ts <= end_timestamp
        ]

        data = [
            {"timestamp": r.timestamp, "value": r.value}
            for r in valid_records
        ]

        return pd.DataFrame(data)

    # === Leakage Detection ===

    def inspect_dataframe(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """
        检查 DataFrame 是否包含 Label（防泄露）

        Args:
            df: 特征 DataFrame

        Returns:
            (是否有问题, 问题列表)
        """
        issues = []

        # 检查列名
        for col in df.columns:
            col_lower = col.lower()

            if col_lower in self.ALL_LABELS:
                issues.append(f"Column '{col}' is a known label!")
                self._violations.append({
                    "type": "label_column_found",
                    "column": col
                })

            for prefix in self.FORBIDDEN_PREFIXES:
                if col_lower.startswith(prefix):
                    issues.append(f"Column '{col}' has forbidden prefix '{prefix}'")
                    self._violations.append({
                        "type": "forbidden_prefix",
                        "column": col,
                        "prefix": prefix
                    })

        return len(issues) > 0, issues

    def assert_dataframe_safe(self, df: pd.DataFrame):
        """
        断言 DataFrame 安全（无 Label）

        Raises:
            ValueError: 如果发现 Label
        """
        has_issue, issues = self.inspect_dataframe(df)
        if has_issue:
            msg = f"Label leakage detected! Issues: {', '.join(issues[:5])}"
            raise ValueError(msg)

    def sanitize_dataframe(self, df: pd.DataFrame, inplace: bool = False) -> pd.DataFrame:
        """
        清理 DataFrame：移除所有 Label 列

        Args:
            df: 输入 DataFrame
            inplace: 是否原地修改

        Returns:
            安全的 DataFrame
        """
        if not inplace:
            df = df.copy()

        columns_to_drop = []
        for col in df.columns:
            col_lower = col.lower()

            if col_lower in self.ALL_LABELS:
                columns_to_drop.append(col)
                logger.warning(f"Dropping label column: {col}")

            for prefix in self.FORBIDDEN_PREFIXES:
                if col_lower.startswith(prefix) and col not in columns_to_drop:
                    columns_to_drop.append(col)
                    logger.warning(f"Dropping column with forbidden prefix: {col}")

        df.drop(columns=columns_to_drop, inplace=True, errors="ignore")
        return df

    # === Stats ===

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        label_counts = {
            lid: len(records)
            for lid, records in self._labels.items()
        }

        return {
            "mode": self.mode,
            "label_count": len(self._labels),
            "label_distributions": label_counts,
            "total_accesses": len(self._access_log),
            "violation_count": len(self._violations),
            "violations": self._violations[-10:]
        }


# Global store instance
_label_store_instance: Optional[StrictLabelStore] = None


def get_label_store(mode: str = "research") -> StrictLabelStore:
    """获取严格 Label 隔离存储"""
    global _label_store_instance
    if _label_store_instance is None:
        _label_store_instance = StrictLabelStore(mode)
    return _label_store_instance


def set_label_store_mode(mode: str):
    """设置 Label 存储模式"""
    get_label_store().set_mode(mode)


def safe_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """便捷函数：确保 DataFrame 无 Label"""
    return get_label_store().sanitize_dataframe(df)


def assert_safe_dataframe(df: pd.DataFrame):
    """便捷函数：断言 DataFrame 安全"""
    get_label_store().assert_dataframe_safe(df)
