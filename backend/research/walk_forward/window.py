
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from infrastructure.runtime_clock import now_ms


@dataclass
class TimeWindow:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

    @property
    def start_datetime(self) -> datetime:
        return datetime.utcfromtimestamp(self.start_ms / 1000)

    @property
    def end_datetime(self) -> datetime:
        return datetime.utcfromtimestamp(self.end_ms / 1000)

    def contains(self, ts_ms: int) -> bool:
        return self.start_ms <= ts_ms < self.end_ms

    def overlap(self, other: "TimeWindow") -> Optional["TimeWindow"]:
        start = max(self.start_ms, other.start_ms)
        end = min(self.end_ms, other.end_ms)
        if start >= end:
            return None
        return TimeWindow(start, end)

    def to_dict(self) -> dict:
        return {
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "start_iso": self.start_datetime.isoformat(),
            "end_iso": self.end_datetime.isoformat(),
        }


@dataclass
class RollingWindow:
    train: TimeWindow
    test: TimeWindow
    window_index: int

    @property
    def total_duration_ms(self) -> int:
        return self.test.end_ms - self.train.start_ms

    def to_dict(self) -> dict:
        return {
            "index": self.window_index,
            "train": self.train.to_dict(),
            "test": self.test.to_dict(),
        }


def generate_rolling_windows(
    total_start_ms: int,
    total_end_ms: int,
    train_duration_days: int = 90,
    test_duration_days: int = 14,
    step_days: int = 14,
) -> List[RollingWindow]:
    train_ms = train_duration_days * 86400 * 1000
    test_ms = test_duration_days * 86400 * 1000
    step_ms = step_days * 86400 * 1000

    windows = []
    index = 0

    current_test_start = total_start_ms + train_ms
    while current_test_start + test_ms <= total_end_ms:
        train_start = current_test_start - train_ms
        train_end = current_test_start
        test_end = current_test_start + test_ms

        window = RollingWindow(
            train=TimeWindow(start_ms=train_start, end_ms=train_end),
            test=TimeWindow(start_ms=current_test_start, end_ms=test_end),
            window_index=index,
        )
        windows.append(window)

        current_test_start += step_ms
        index += 1

    return windows
