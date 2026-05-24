"""
Partial Candle Handler - 不完整K线处理器

核心问题：
在周期未结束时使用完整的聚合数据会导致数据泄漏。

例如：
- 时间 10:15，错误地使用 10:00~11:00 完整的 1h K线
- 正确做法：只能使用 10:00~10:15 的 partial candle

解决方案：
1. 检测当前是否在周期内
2. 只使用已关闭的K线数据
3. 对于实时场景，提供 partial candle 的安全处理
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("domain.feature.infrastructure.partial_candle")


class CandleState(Enum):
    """K线状态"""
    CLOSED = "closed"           # 已关闭，可以安全使用
    PARTIAL = "partial"         # 未关闭，部分数据
    FUTURE = "future"           # 未来数据，禁止使用


@dataclass
class CandlePeriod:
    """K线周期信息"""
    period_ms: int              # 周期毫秒数
    period_start: int           # 周期开始时间
    period_end: int             # 周期结束时间
    current_time: int           # 当前时间
    state: CandleState          # K线状态
    elapsed_ms: int = 0         # 已经过时间
    remaining_ms: int = 0       # 剩余时间
    progress_pct: float = 0.0   # 完成进度
    
    def __post_init__(self):
        self.elapsed_ms = self.current_time - self.period_start
        self.remaining_ms = self.period_end - self.current_time
        self.progress_pct = self.elapsed_ms / self.period_ms if self.period_ms > 0 else 0.0
    
    def is_safe_to_use(self) -> bool:
        """是否可以安全使用"""
        return self.state == CandleState.CLOSED
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "period_ms": self.period_ms,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "current_time": self.current_time,
            "state": self.state.value,
            "elapsed_ms": self.elapsed_ms,
            "remaining_ms": self.remaining_ms,
            "progress_pct": self.progress_pct,
            "is_safe": self.is_safe_to_use(),
        }


@dataclass
class PartialCandleData:
    """部分K线数据"""
    timestamp: int
    period_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    trade_count: int = 0
    is_partial: bool = True
    progress_pct: float = 0.0
    
    def to_ohlc_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "trade_count": self.trade_count,
            "is_partial": self.is_partial,
            "progress_pct": self.progress_pct,
        }


class PartialCandleHandler:
    """
    不完整K线处理器
    
    核心功能：
    1. 检测K线是否已关闭
    2. 阻止使用未来完整K线
    3. 提供部分K线的安全处理
    """
    
    PERIOD_MS = {
        "1m": 60 * 1000,
        "5m": 5 * 60 * 1000,
        "15m": 15 * 60 * 1000,
        "30m": 30 * 60 * 1000,
        "1h": 60 * 60 * 1000,
        "4h": 4 * 60 * 60 * 1000,
        "1d": 24 * 60 * 60 * 1000,
    }
    
    def __init__(self, default_period: str = "1m"):
        self.default_period_ms = self.PERIOD_MS.get(default_period, 60 * 1000)
        self._strict_mode = True
        self._partial_candles: Dict[str, PartialCandleData] = {}
        self._leakage_log: List[Dict[str, Any]] = []
    
    def get_candle_state(
        self,
        candle_timestamp: int,
        current_time: int,
        period_ms: Optional[int] = None,
    ) -> CandlePeriod:
        """
        获取K线状态
        
        Args:
            candle_timestamp: K线开盘时间
            current_time: 当前时间
            period_ms: 周期毫秒数
        
        Returns:
            CandlePeriod: K线周期信息
        """
        period_ms = period_ms or self.default_period_ms
        period_start = (candle_timestamp // period_ms) * period_ms
        period_end = period_start + period_ms
        
        if current_time < period_start:
            state = CandleState.FUTURE
        elif current_time >= period_end:
            state = CandleState.CLOSED
        else:
            state = CandleState.PARTIAL
        
        return CandlePeriod(
            period_ms=period_ms,
            period_start=period_start,
            period_end=period_end,
            current_time=current_time,
            state=state,
        )
    
    def check_candle_availability(
        self,
        candle_timestamp: int,
        query_time: int,
        period_ms: Optional[int] = None,
        feature_name: str = "unknown",
    ) -> Tuple[bool, CandlePeriod]:
        """
        检查K线是否可用
        
        Args:
            candle_timestamp: K线开盘时间
            query_time: 查询时间
            period_ms: 周期毫秒数
            feature_name: 特征名称（用于日志）
        
        Returns:
            Tuple[bool, CandlePeriod]: (是否可用, 周期信息)
        """
        period = self.get_candle_state(candle_timestamp, query_time, period_ms)
        
        if period.state == CandleState.FUTURE:
            self._log_leakage_attempt(
                feature_name=feature_name,
                candle_timestamp=candle_timestamp,
                query_time=query_time,
                state=period.state,
                message="Attempted to use future candle",
            )
            
            if self._strict_mode:
                raise ValueError(
                    f"Data leakage: Attempted to use future candle at {candle_timestamp} "
                    f"when current time is {query_time}"
                )
            
            return False, period
        
        if period.state == CandleState.PARTIAL:
            self._log_leakage_attempt(
                feature_name=feature_name,
                candle_timestamp=candle_timestamp,
                query_time=query_time,
                state=period.state,
                message=f"Partial candle used at {period.progress_pct:.1%} completion",
            )
            
            if self._strict_mode:
                logger.warning(
                    f"Partial candle warning: {feature_name} using candle at "
                    f"{period.progress_pct:.1%} completion"
                )
        
        return period.state != CandleState.FUTURE, period
    
    def filter_closed_candles(
        self,
        df: pd.DataFrame,
        query_time: int,
        period_ms: Optional[int] = None,
        timestamp_col: str = "timestamp",
    ) -> pd.DataFrame:
        """
        过滤出已关闭的K线
        
        Args:
            df: 包含K线数据的DataFrame
            query_time: 查询时间
            period_ms: 周期毫秒数
            timestamp_col: 时间戳列名
        
        Returns:
            pd.DataFrame: 只包含已关闭K线的DataFrame
        """
        period_ms = period_ms or self.default_period_ms
        
        df = df.copy()
        df["_period_end"] = (df[timestamp_col] // period_ms + 1) * period_ms
        
        closed_mask = df["_period_end"] <= query_time
        
        removed_count = len(df) - closed_mask.sum()
        if removed_count > 0:
            logger.debug(
                f"Filtered out {removed_count} partial/future candles at query_time={query_time}"
            )
        
        result = df[closed_mask].drop(columns=["_period_end"])
        return result
    
    def get_latest_closed_candle(
        self,
        df: pd.DataFrame,
        query_time: int,
        period_ms: Optional[int] = None,
        timestamp_col: str = "timestamp",
    ) -> Optional[pd.Series]:
        """
        获取最新的已关闭K线
        
        Args:
            df: 包含K线数据的DataFrame
            query_time: 查询时间
            period_ms: 周期毫秒数
            timestamp_col: 时间戳列名
        
        Returns:
            Optional[pd.Series]: 最新已关闭K线，如果没有则返回None
        """
        closed_df = self.filter_closed_candles(df, query_time, period_ms, timestamp_col)
        
        if closed_df.empty:
            return None
        
        return closed_df.iloc[-1]
    
    def build_partial_candle(
        self,
        trades: pd.DataFrame,
        period_start: int,
        current_time: int,
        period_ms: Optional[int] = None,
    ) -> PartialCandleData:
        """
        从交易数据构建部分K线
        
        Args:
            trades: 交易数据DataFrame
            period_start: 周期开始时间
            current_time: 当前时间
            period_ms: 周期毫秒数
        
        Returns:
            PartialCandleData: 部分K线数据
        """
        period_ms = period_ms or self.default_period_ms
        
        period_trades = trades[
            (trades["timestamp"] >= period_start) &
            (trades["timestamp"] < current_time)
        ]
        
        if period_trades.empty:
            return PartialCandleData(
                timestamp=period_start,
                period_ms=period_ms,
                open=0.0,
                high=0.0,
                low=0.0,
                close=0.0,
                volume=0.0,
                is_partial=True,
                progress_pct=0.0,
            )
        
        return PartialCandleData(
            timestamp=period_start,
            period_ms=period_ms,
            open=period_trades["price"].iloc[0],
            high=period_trades["price"].max(),
            low=period_trades["price"].min(),
            close=period_trades["price"].iloc[-1],
            volume=period_trades["quantity"].sum() if "quantity" in period_trades.columns else len(period_trades),
            trade_count=len(period_trades),
            is_partial=True,
            progress_pct=(current_time - period_start) / period_ms,
        )
    
    def aggregate_to_higher_timeframe(
        self,
        lower_tf_df: pd.DataFrame,
        target_period_ms: int,
        query_time: int,
        timestamp_col: str = "timestamp",
        use_partial: bool = False,
    ) -> pd.DataFrame:
        """
        安全地聚合到更高时间周期
        
        Args:
            lower_tf_df: 低时间周期数据
            target_period_ms: 目标周期毫秒数
            query_time: 查询时间
            timestamp_col: 时间戳列名
            use_partial: 是否使用部分K线
        
        Returns:
            pd.DataFrame: 聚合后的数据
        """
        lower_tf_df = lower_tf_df.copy()
        lower_tf_df["_higher_tf_start"] = (lower_tf_df[timestamp_col] // target_period_ms) * target_period_ms
        
        agg_dict = {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
        
        available_cols = [col for col in agg_dict.keys() if col in lower_tf_df.columns]
        agg_dict = {k: v for k, v in agg_dict.items() if k in available_cols}
        
        higher_tf = lower_tf_df.groupby("_higher_tf_start").agg(agg_dict).reset_index()
        higher_tf = higher_tf.rename(columns={"_higher_tf_start": timestamp_col})
        
        if not use_partial:
            higher_tf = self.filter_closed_candles(higher_tf, query_time, target_period_ms, timestamp_col)
        
        return higher_tf
    
    def _log_leakage_attempt(
        self,
        feature_name: str,
        candle_timestamp: int,
        query_time: int,
        state: CandleState,
        message: str,
    ):
        """记录泄漏尝试"""
        self._leakage_log.append({
            "feature_name": feature_name,
            "candle_timestamp": candle_timestamp,
            "query_time": query_time,
            "state": state.value,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    def get_leakage_report(self) -> Dict[str, Any]:
        """获取泄漏报告"""
        partial_count = sum(1 for log in self._leakage_log if log["state"] == "partial")
        future_count = sum(1 for log in self._leakage_log if log["state"] == "future")
        
        return {
            "total_attempts": len(self._leakage_log),
            "partial_candle_attempts": partial_count,
            "future_candle_attempts": future_count,
            "recent_attempts": self._leakage_log[-10:],
        }
    
    def clear_cache(self):
        """清空缓存"""
        self._partial_candles.clear()
        self._leakage_log.clear()


_handler_instance: Optional[PartialCandleHandler] = None


def get_partial_candle_handler(default_period: str = "1m") -> PartialCandleHandler:
    """获取部分K线处理器实例"""
    global _handler_instance
    if _handler_instance is None:
        _handler_instance = PartialCandleHandler(default_period)
    return _handler_instance
