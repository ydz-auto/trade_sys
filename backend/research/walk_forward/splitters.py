
from typing import Protocol, List, Iterator, Dict, Any
from abc import ABC, abstractmethod
from dataclasses import dataclass

from research.walk_forward.context import WindowSpec, TimeRange


class WindowSplitter(Protocol):
    """
    窗口切分器 Protocol
    
    作用：将完整数据 range 切分成多个 train/test 窗口
    
    关键类型：
    - Rolling：普通 walk-forward
    - Expanding：累积训练
    - Anchored：固定起点
    - RegimeSplit：regime-aware
    - PurgedKFold：防标签泄漏
    - EmbargoSplit：防标签污染
    """
    
    def split(
        self,
        total_range: TimeRange,
        n_windows: int,
    ) -> List[WindowSpec]:
        """生成所有窗口"""
        ...
    
    def get_purge_gap(self) -> int:
        """purge gap ms"""
        ...
    
    def get_embargo(self) -> int:
        """embargo ms"""
        ...


@dataclass(frozen=True)
class RollingSplitter:
    """
    Rolling Walk-Forward Splitter
    
    固定训练窗口，固定测试窗口，步进滑动
    
    Example:
    Window 1: train=[Jan-Mar], test=[Apr 1-14]
    Window 2: train=[Jan-Apr], test=[Apr 15-28]
    Window 3: train=[Jan-May], test=[May 1-14]
    """
    train_duration_ms: int = 90 * 86400000
    test_duration_ms: int = 14 * 86400000
    step_ms: int = 14 * 86400000
    
    purge_gap_ms: int = 0
    embargo_ms: int = 0
    
    def split(self, total_range: TimeRange, n_windows: int = 0) -> List[WindowSpec]:
        windows = []
        index = 0
        
        test_start = total_range.start_ms + self.train_duration_ms
        
        while test_start + self.test_duration_ms <= total_range.end_ms:
            train_end = test_start
            train_start = train_end - self.train_duration_ms
            
            if train_start < total_range.start_ms:
                break
            
            window = WindowSpec(
                name=f"rolling_{index}",
                train_range=TimeRange(start_ms=train_start, end_ms=train_end),
                test_range=TimeRange(start_ms=test_start, end_ms=test_start + self.test_duration_ms),
                purge_gap_ms=self.purge_gap_ms,
                embargo_ms=self.embargo_ms,
                window_index=index,
            )
            windows.append(window)
            
            test_start += self.step_ms
            index += 1
            
            if n_windows > 0 and index >= n_windows:
                break
        
        return windows
    
    def get_purge_gap(self) -> int:
        return self.purge_gap_ms
    
    def get_embargo(self) -> int:
        return self.embargo_ms


@dataclass(frozen=True)
class ExpandingSplitter:
    """
    Expanding Window Splitter
    
    测试窗口固定，训练窗口不断扩展
    
    Example:
    Window 1: train=[Jan],        test=[Feb 1-14]
    Window 2: train=[Jan-Feb],   test=[Feb 15-28]
    Window 3: train=[Jan-Mar],   test=[Mar 1-14]
    """
    test_duration_ms: int = 14 * 86400000
    step_ms: int = 14 * 86400000
    min_train_ms: int = 30 * 86400000
    
    purge_gap_ms: int = 0
    embargo_ms: int = 0
    
    def split(self, total_range: TimeRange, n_windows: int = 0) -> List[WindowSpec]:
        windows = []
        index = 0
        
        train_start = total_range.start_ms
        test_start = train_start + self.min_train_ms
        
        while test_start + self.test_duration_ms <= total_range.end_ms:
            window = WindowSpec(
                name=f"expanding_{index}",
                train_range=TimeRange(start_ms=train_start, end_ms=test_start),
                test_range=TimeRange(start_ms=test_start, end_ms=test_start + self.test_duration_ms),
                purge_gap_ms=self.purge_gap_ms,
                embargo_ms=self.embargo_ms,
                window_index=index,
            )
            windows.append(window)
            
            test_start += self.step_ms
            index += 1
            
            if n_windows > 0 and index >= n_windows:
                break
        
        return windows
    
    def get_purge_gap(self) -> int:
        return self.purge_gap_ms
    
    def get_embargo(self) -> int:
        return self.embargo_ms


@dataclass(frozen=True)
class AnchoredSplitter:
    """
    Anchored Splitter
    
    固定训练起点，每次扩展训练终点，测试窗口固定
    
    Example:
    Window 1: train=[Jan-Dec],  test=[Jan+1Y 1-14]
    Window 2: train=[Jan-Dec+1M], test=[Jan+1Y+1M 1-14]
    """
    anchor_start_ms: int
    train_extension_ms: int = 30 * 86400000
    test_duration_ms: int = 14 * 86400000
    step_ms: int = 14 * 86400000
    
    purge_gap_ms: int = 0
    embargo_ms: int = 0
    
    def split(self, total_range: TimeRange, n_windows: int = 0) -> List[WindowSpec]:
        windows = []
        index = 0
        
        train_end = self.anchor_start_ms + self.train_extension_ms
        
        while True:
            test_start = train_end
            if test_start + self.test_duration_ms > total_range.end_ms:
                break
            
            window = WindowSpec(
                name=f"anchored_{index}",
                train_range=TimeRange(start_ms=self.anchor_start_ms, end_ms=train_end),
                test_range=TimeRange(start_ms=test_start, end_ms=test_start + self.test_duration_ms),
                purge_gap_ms=self.purge_gap_ms,
                embargo_ms=self.embargo_ms,
                window_index=index,
            )
            windows.append(window)
            
            train_end += self.step_ms
            test_start += self.step_ms
            index += 1
            
            if n_windows > 0 and index >= n_windows:
                break
        
        return windows
    
    def get_purge_gap(self) -> int:
        return self.purge_gap_ms
    
    def get_embargo(self) -> int:
        return self.embargo_ms


@dataclass(frozen=True)
class PurgedKFoldSplitter:
    """
    Purged K-Fold Splitter
    
    核心：训练/测试之间有 purge gap，防止 label overlap leakage
    
    Example (k=5, purge_gap=2 bars):
    Fold 1: train=[--],         test=[==]
    Fold 2: train=[----],       test=[====]
    (中间跳过的区域是 purge gap)
    """
    n_folds: int = 5
    purge_gap_ms: int = 4 * 3600000
    embargo_ms: int = 0
    
    train_ratio: float = 0.7
    
    def split(self, total_range: TimeRange, n_windows: int = 0) -> List[WindowSpec]:
        total_ms = total_range.duration_ms
        fold_ms = total_ms / self.n_folds
        train_folds = int(self.n_folds * self.train_ratio)
        
        windows = []
        
        for i in range(self.n_folds):
            test_start = int(total_range.start_ms + i * fold_ms)
            test_end = int(test_start + fold_ms)
            
            train_end = test_start - self.purge_gap_ms
            train_start = int(total_range.start_ms + max(0, (i - train_folds)) * fold_ms)
            
            if train_start >= train_end:
                continue
            if test_end > total_range.end_ms:
                test_end = total_range.end_ms
            
            window = WindowSpec(
                name=f"purged_kfold_{i}",
                train_range=TimeRange(start_ms=train_start, end_ms=train_end),
                test_range=TimeRange(start_ms=test_start + self.purge_gap_ms, end_ms=test_end),
                purge_gap_ms=self.purge_gap_ms,
                embargo_ms=self.embargo_ms,
                window_index=i,
            )
            windows.append(window)
        
        return windows
    
    def get_purge_gap(self) -> int:
        return self.purge_gap_ms
    
    def get_embargo(self) -> int:
        return self.embargo_ms


@dataclass(frozen=True)
class EmbargoSplitter:
    """
    Embargo Splitter
    
    核心：测试集最后一个 bar 之后，排除 embargo 期间的数据不参与训练
    
    用途：防止 future information 从测试集 leakage 到训练集
    （例如日内策略：测试集收盘后利用当天 PnL 做决策）
    """
    n_folds: int = 5
    embargo_ms: int = 4 * 3600000
    purge_gap_ms: int = 0
    
    def split(self, total_range: TimeRange, n_windows: int = 0) -> List[WindowSpec]:
        total_ms = total_range.duration_ms
        fold_ms = total_ms / self.n_folds
        
        windows = []
        
        for i in range(self.n_folds):
            test_start = int(total_range.start_ms + i * fold_ms)
            test_end = int(test_start + fold_ms)
            
            train_end = test_start - self.purge_gap_ms
            train_start = int(total_range.start_ms + max(0, i - self.n_folds) * fold_ms)
            
            embargo_end = test_end + self.embargo_ms
            
            window = WindowSpec(
                name=f"embargo_{i}",
                train_range=TimeRange(start_ms=train_start, end_ms=train_end),
                test_range=TimeRange(start_ms=test_start, end_ms=test_end),
                purge_gap_ms=self.purge_gap_ms,
                embargo_ms=self.embargo_ms,
                window_index=i,
                metadata=(("embargo_until_ms", embargo_end),),
            )
            windows.append(window)
        
        return windows
    
    def get_purge_gap(self) -> int:
        return self.purge_gap_ms
    
    def get_embargo(self) -> int:
        return self.embargo_ms


def create_splitter(
    splitter_type: str,
    **kwargs,
) -> WindowSplitter:
    """工厂函数：创建 Splitter"""
    splitters = {
        "rolling": RollingSplitter,
        "expanding": ExpandingSplitter,
        "anchored": AnchoredSplitter,
        "purged_kfold": PurgedKFoldSplitter,
        "embargo": EmbargoSplitter,
    }
    
    cls = splitters.get(splitter_type.lower())
    if cls is None:
        raise ValueError(f"Unknown splitter type: {splitter_type}. Available: {list(splitters.keys())}")
    
    return cls(**kwargs)
