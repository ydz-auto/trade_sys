"""
Data Quality Module - 数据质量检测模块
提供数据质量评估、异常检测和完整性检查
"""

from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import statistics

from infrastructure.logging import get_logger

logger = get_logger("shared.data_quality")


class QualityStatus(str, Enum):
    """质量状态"""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"


class IssueType(str, Enum):
    """问题类型"""
    NULL_VALUE = "null_value"
    OUTLIER = "outlier"
    INCOMPLETE = "incomplete"
    INCONSISTENT = "inconsistent"
    DUPLICATE = "duplicate"
    INVALID_RANGE = "invalid_range"
    STALE_DATA = "stale_data"
    SCHEMA_MISMATCH = "schema_mismatch"


@dataclass
class QualityIssue:
    """质量问题"""
    issue_type: IssueType
    field: str
    message: str

    severity: str = "warning"

    record_id: Optional[str] = None
    value: Any = None
    expected: Any = None

    detected_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))

    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "issue_type": self.issue_type.value,
            "field": self.field,
            "message": self.message,
            "severity": self.severity,
            "record_id": self.record_id,
            "value": self.value,
            "expected": self.expected,
            "detected_at": self.detected_at,
            "metadata": self.metadata,
        }


@dataclass
class QualityMetrics:
    """质量指标"""
    total_records: int
    valid_records: int
    null_count: int
    outlier_count: int
    duplicate_count: int

    completeness: float
    accuracy: float
    consistency: float
    timeliness: float

    status: QualityStatus

    issues: List[QualityIssue] = field(default_factory=list)

    generated_at: int = field(default_factory=lambda: int(datetime.now().timestamp() * 1000))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_records": self.total_records,
            "valid_records": self.valid_records,
            "null_count": self.null_count,
            "outlier_count": self.outlier_count,
            "duplicate_count": self.duplicate_count,
            "completeness": self.completeness,
            "accuracy": self.accuracy,
            "consistency": self.consistency,
            "timeliness": self.timeliness,
            "status": self.status.value,
            "issues": [i.to_dict() for i in self.issues],
            "generated_at": self.generated_at,
        }


@dataclass
class DataProfile:
    """数据画像"""
    field_name: str
    data_type: str

    count: int
    null_count: int
    unique_count: int

    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    median_value: Optional[float] = None
    std_dev: Optional[float] = None

    distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "data_type": self.data_type,
            "count": self.count,
            "null_count": self.null_count,
            "unique_count": self.unique_count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "median_value": self.median_value,
            "std_dev": self.std_dev,
            "distribution": self.distribution,
        }


class DataQualityChecker:
    """数据质量检查器"""

    def __init__(self):
        self._rules: Dict[str, Callable] = {}
        self._thresholds: Dict[str, float] = {
            "completeness": 0.95,
            "accuracy": 0.95,
            "consistency": 0.95,
            "timeliness": 0.90,
        }

    def register_rule(self, field: str, rule_func: Callable):
        """注册验证规则"""
        self._rules[field] = rule_func

    def set_threshold(self, metric: str, threshold: float):
        """设置阈值"""
        self._thresholds[metric] = threshold

    def check_null(self, value: Any) -> bool:
        """检查空值"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        return False

    def detect_outliers(
        self,
        values: List[float],
        method: str = "iqr",
        threshold: float = 3.0,
    ) -> List[int]:
        """检测异常值"""
        if len(values) < 3:
            return []

        if method == "iqr":
            sorted_vals = sorted(values)
            q1_idx = len(sorted_vals) // 4
            q3_idx = 3 * len(sorted_vals) // 4
            q1 = sorted_vals[q1_idx]
            q3 = sorted_vals[q3_idx]
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            outliers = []
            for i, v in enumerate(values):
                if v < lower or v > upper:
                    outliers.append(i)
            return outliers

        elif method == "zscore":
            mean = statistics.mean(values)
            std = statistics.stdev(values)

            if std == 0:
                return []

            outliers = []
            for i, v in enumerate(values):
                z = abs((v - mean) / std)
                if z > threshold:
                    outliers.append(i)
            return outliers

        return []

    def check_range(
        self,
        value: float,
        min_val: Optional[float] = None,
        max_val: Optional[float] = None,
    ) -> bool:
        """检查值范围"""
        if min_val is not None and value < min_val:
            return False
        if max_val is not None and value > max_val:
            return False
        return True

    def calculate_completeness(
        self,
        records: List[Dict],
        required_fields: List[str],
    ) -> Tuple[float, int, List[QualityIssue]]:
        """计算完整性"""
        total = len(records)
        if total == 0:
            return 1.0, 0, []

        null_count = 0
        issues = []

        for record in records:
            for field in required_fields:
                if self.check_null(record.get(field)):
                    null_count += 1
                    issues.append(QualityIssue(
                        issue_type=IssueType.NULL_VALUE,
                        field=field,
                        message=f"Null value in required field: {field}",
                        severity="warning",
                        record_id=str(record.get("id", "")),
                    ))

        completeness = 1.0 - (null_count / (total * len(required_fields)))
        return completeness, null_count, issues

    def calculate_accuracy(
        self,
        records: List[Dict],
        validation_func: Callable[[Dict], bool],
    ) -> Tuple[float, List[QualityIssue]]:
        """计算准确性"""
        total = len(records)
        if total == 0:
            return 1.0, []

        invalid_count = 0
        issues = []

        for record in records:
            if not validation_func(record):
                invalid_count += 1
                issues.append(QualityIssue(
                    issue_type=IssueType.INCONSISTENT,
                    field="record",
                    message="Record failed validation",
                    severity="error",
                    record_id=str(record.get("id", "")),
                ))

        accuracy = 1.0 - (invalid_count / total)
        return accuracy, issues

    def detect_duplicates(
        self,
        records: List[Dict],
        key_fields: List[str],
    ) -> Tuple[int, List[QualityIssue]]:
        """检测重复"""
        seen = set()
        duplicates = []
        issues = []

        for record in records:
            key = tuple(record.get(f) for f in key_fields)
            if key in seen:
                duplicates.append(record)
                issues.append(QualityIssue(
                    issue_type=IssueType.DUPLICATE,
                    field=", ".join(key_fields),
                    message=f"Duplicate record with key: {key}",
                    severity="info",
                    record_id=str(record.get("id", "")),
                ))
            else:
                seen.add(key)

        return len(duplicates), issues

    def check_timeliness(
        self,
        records: List[Dict],
        timestamp_field: str,
        max_age_seconds: int,
    ) -> Tuple[float, List[QualityIssue]]:
        """检查时效性"""
        total = len(records)
        if total == 0:
            return 1.0, []

        now = int(datetime.now().timestamp())
        stale_count = 0
        issues = []

        for record in records:
            timestamp = record.get(timestamp_field)
            if timestamp:
                age = now - timestamp
                if age > max_age_seconds:
                    stale_count += 1
                    issues.append(QualityIssue(
                        issue_type=IssueType.STALE_DATA,
                        field=timestamp_field,
                        message=f"Data is {age} seconds old (max: {max_age_seconds})",
                        severity="warning",
                        record_id=str(record.get("id", "")),
                        value=age,
                    ))

        timeliness = 1.0 - (stale_count / total)
        return timeliness, issues

    def profile_field(self, values: List[Any]) -> DataProfile:
        """分析字段"""
        non_null = [v for v in values if not self.check_null(v)]

        profile = DataProfile(
            field_name="",
            data_type=type(values[0]).__name__ if values else "unknown",
            count=len(values),
            null_count=len(values) - len(non_null),
            unique_count=len(set(non_null)),
        )

        numeric_values = [v for v in non_null if isinstance(v, (int, float))]
        if numeric_values:
            profile.min_value = min(numeric_values)
            profile.max_value = max(numeric_values)
            profile.mean_value = statistics.mean(numeric_values)
            profile.median_value = statistics.median(numeric_values)
            if len(numeric_values) > 1:
                profile.std_dev = statistics.stdev(numeric_values)

        return profile

    def assess_quality(
        self,
        records: List[Dict],
        required_fields: List[str],
        validation_func: Optional[Callable] = None,
        timestamp_field: Optional[str] = None,
        max_age_seconds: Optional[int] = None,
        key_fields: Optional[List[str]] = None,
    ) -> QualityMetrics:
        """评估数据质量"""
        total_records = len(records)

        completeness, null_count, completeness_issues = self.calculate_completeness(
            records, required_fields
        )

        accuracy = 1.0
        accuracy_issues = []
        if validation_func:
            accuracy, accuracy_issues = self.calculate_accuracy(records, validation_func)

        timeliness = 1.0
        timeliness_issues = []
        if timestamp_field and max_age_seconds:
            timeliness, timeliness_issues = self.check_timeliness(
                records, timestamp_field, max_age_seconds
            )

        duplicates = 0
        duplicate_issues = []
        if key_fields:
            duplicates, duplicate_issues = self.detect_duplicates(records, key_fields)

        all_issues = completeness_issues + accuracy_issues + timeliness_issues + duplicate_issues

        outlier_count = 0
        for field in required_fields:
            numeric_values = [r.get(field) for r in records if isinstance(r.get(field), (int, float))]
            if numeric_values:
                outliers = self.detect_outliers(numeric_values)
                outlier_count += len(outliers)

        valid_records = total_records - null_count - duplicates
        consistency = 1.0 - (duplicates / total_records if total_records > 0 else 0)

        status = QualityStatus.EXCELLENT
        if completeness < 0.8 or accuracy < 0.8 or consistency < 0.8:
            status = QualityStatus.POOR
        elif completeness < 0.9 or accuracy < 0.9:
            status = QualityStatus.FAIR
        elif completeness < 0.95 or accuracy < 0.95:
            status = QualityStatus.GOOD

        return QualityMetrics(
            total_records=total_records,
            valid_records=valid_records,
            null_count=null_count,
            outlier_count=outlier_count,
            duplicate_count=duplicates,
            completeness=completeness,
            accuracy=accuracy,
            consistency=consistency,
            timeliness=timeliness,
            status=status,
            issues=all_issues,
        )


class CandleDataQualityChecker(DataQualityChecker):
    """K线数据质量检查器"""

    def __init__(self):
        super().__init__()
        self._required_fields = [
            "open", "high", "low", "close",
            "volume", "open_time", "close_time"
        ]

    def check_price_consistency(self, record: Dict) -> bool:
        """检查价格一致性"""
        high = record.get("high", 0)
        low = record.get("low", 0)
        open_price = record.get("open", 0)
        close = record.get("close", 0)

        if high < low:
            return False
        if high < open_price or high < close:
            return False
        if low > open_price or low > close:
            return False
        return True

    def check_volume_positive(self, record: Dict) -> bool:
        """检查成交量为正"""
        volume = record.get("volume", 0)
        return volume >= 0

    def check_time_consistency(self, record: Dict) -> bool:
        """检查时间一致性"""
        open_time = record.get("open_time", 0)
        close_time = record.get("close_time", 0)
        return close_time > open_time

    def check_candles(self, candles: List[Dict]) -> QualityMetrics:
        """检查K线数据"""
        validation_func = lambda r: (
            self.check_price_consistency(r) and
            self.check_volume_positive(r) and
            self.check_time_consistency(r)
        )

        return self.assess_quality(
            records=candles,
            required_fields=self._required_fields,
            validation_func=validation_func,
            timestamp_field="open_time",
            max_age_seconds=3600 * 24,
        )


_data_quality_checker: Optional[DataQualityChecker] = None


def get_data_quality_checker() -> DataQualityChecker:
    """获取数据质量检查器"""
    global _data_quality_checker
    if _data_quality_checker is None:
        _data_quality_checker = DataQualityChecker()
    return _data_quality_checker


def get_candle_quality_checker() -> CandleDataQualityChecker:
    """获取K线数据质量检查器"""
    return CandleDataQualityChecker()
