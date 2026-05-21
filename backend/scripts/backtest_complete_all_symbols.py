#!/usr/bin/env python3
"""
完整策略回测系统
支持多个交易对：BTC、ETH、SOL、ZEC
参数设置：
- 初始资金：$10,000
- 杠杆倍数：50x
- 最大本金止损：10%
- 止盈方式：固定和移动止盈
- 时间周期：5分钟K线
"""

import sys
from pathlib import Path

script_dir = Path(__file__).parent
backend_path = script_dir.parent
sys.path.insert(0, str(backend_path))

import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import pandas as pd
import numpy as np

from infrastructure.logging import get_logger

logger = get_logger("complete_backtest_all_symbols")


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    leverage: float = 50.0
    capital_stop_loss_pct: float = 0.10  # 最大本金止损10%
    trailing_stop_pct: float = 0.15  # 移动止盈回撤15%
    fixed_take_profit_pct: Optional[float] = 0.20  # 固定止盈20%
    max_hold_hours: int = 48
    timeframe: str = "5m"


@dataclass
class Position:
    strategy_id: str
    symbol: str
    direction: int  # 1=做多, -1=做空
    entry_price: float
    entry_time: datetime
    margin: float
    stop_loss_price: float
    trailing_stop_price: float
    take_profit_price: Optional[float]
    highest_price: float
    lowest_price: float


@dataclass
class Trade:
    trade_id: str
    strategy_id: str
    symbol: str
    direction: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    margin: float
    pnl: float
    pnl_pct: float
    exit_reason: str
    duration_hours: float


# 策略配置
STRATEGIES = {
    # 经典技术指标策略
    "rsi_14": {
        "name": "RSI 14",
        "direction": 0,  # 双向
        "description": "RSI超买超卖策略",
    },
    "macd_12_26_9": {
        "name": "MACD 12/26/9",
        "direction": 0,
        "description": "MACD金叉死叉策略",
    },
    "bollinger_bands": {
        "name": "Bollinger Bands",
        "direction": 0,
        "description": "布林带突破策略",
    },
    
    # 事件驱动策略
    "panic_reversal": {
        "name": "Panic Reversal",
        "direction": 1,  # 做多
        "description": "恐慌反弹策略",
    },
    "long_liquidation_bounce": {
        "name": "Long Liquidation Bounce",
        "direction": 1,
        "description": "多头踩踏反弹策略",
    },
    "volume_climax_fade": {
        "name": "Volume Climax Fade",
        "direction": -1,  # 做空
        "description": "放量高潮衰竭策略",
    },
    "weak_bounce_short": {
        "name": "Weak Bounce Short",
        "direction": -1,
        "description": "弱反弹做空策略",
    },
    "fake_breakout_trap": {
        "name": "Fake Breakout Trap",
        "direction": -1,
        "description": "假突破反杀策略",
    },
    "short_squeeze_hunt": {
        "name": "Short Squeeze Hunt",
        "direction": 1,
        "description": "抓空头挤压策略",
    },
    "funding_reset": {
        "name": "Funding Reset",
        "direction": -1,
        "description": "资金费率重置策略",
    },
    "oi_flush": {
        "name": "OI Flush",
        "direction": -1,
        "description": "持仓量洗盘策略",
    },
    
    # Playbook策略
    "pb_panic_reversal": {
        "name": "Playbook Panic Reversal",
        "direction": 1,
        "description": "Playbook恐慌反弹",
    },
    "pb_fake_breakout": {
        "name": "Playbook Fake Breakout",
        "direction": -1,
        "description": "Playbook假突破",
    },
    "pb_oi_flush": {
        "name": "Playbook OI Flush",
        "direction": 1,
        "description": "Playbook OI洗盘",
    },
    "pb_short_squeeze": {
        "name": "Playbook Short Squeeze",
        "direction": 1,
        "description": "Playbook空头挤压",
    },
    "pb_volume_climax": {
        "name": "Playbook Volume Climax",
        "direction": 1,
        "description": "Playbook放量高潮",
    },
}


class CompleteBacktester:
    def __init__(self, config: BacktestConfig = None):
        self.config = config or BacktestConfig()
        self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"]
        self.results = {}
        self.trades = []
        self.equity_curves = {}
        
        # 计算价格止损/止盈
        self.price_stop_loss_pct = self.config.capital_stop_loss_pct / self.config.leverage
        self.price_trailing_stop_pct = self.config.trailing_stop_pct / self.config.leverage
        self.price_take_profit_pct = self.config.fixed_take_profit_pct / self.config.leverage if self.config.fixed_take_profit_pct else None
    
    def load_data(self, symbol: str, months: int = 5) -> pd.DataFrame:
        """从数据湖加载数据"""
        data_path = backend_path / "data_lake" / "crypto" / "binance" / "klines"
        
        try:
            # 尝试从特征数据加载（如果存在）
            feature_path = backend_path / "data_lake" / "features" / "binance" / symbol / "features_with_structure.parquet"
            if feature_path.exists():
                df = pd.read_parquet(feature_path)
                logger.info(f"Loaded {len(df)} feature rows for {symbol}")
                return df
        except Exception as e:
            logger.warning(f"Could not load feature data: {e}")
        
        try:
            # 从K线数据加载
            import pyarrow.parquet as pq
            
            klines_path = data_path
            if klines_path.exists():
                dataset = pq.ParquetDataset(klines_path, filters=[('symbol', '=', symbol)])
                table = dataset.read()
                df = table.to_pandas()
                logger.info(f"Loaded {len(df)} K-line rows for {symbol}")
                return df
        except Exception as e:
            logger.warning(f"Could not load K-line data: {e}")
        
        # 如果没有数据，生成模拟数据
        logger.warning(f"No data found for {symbol}, generating mock data")
        return self.generate_mock_data(symbol, months)
    
    def generate_mock_data(self, symbol: str, months: int) -> pd.DataFrame:
        """生成模拟数据"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        # 5分钟K线
        periods = int((end_date - start_date).total_seconds() / (5 * 60))
        
        base_prices = {
            "BTCUSDT": 60000,
            "ETHUSDT": 3500,
            "SOLUSDT": 150,
            "ZECUSDT": 60,
        }
        
        base_price = base_prices.get(symbol, 100)
        
        np.random.seed(42)
        timestamps = pd.date_range(start=start_date, end=end_date, periods=periods)
        
        # 生成带漂移和波动的价格
        returns = np.random.normal(0.0001, 0.005, periods)
        prices = base_price * (1 + returns).cumprod()
        
        # 添加一些极端行情
        crash_days = np.random.choice(periods, size=10, replace=False)
        prices[crash_days] *= 0.95
        rally_days = np.random.choice(periods, size=10, replace=False)
        prices[rally_days] *= 1.05
        
        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": prices * (1 + np.random.normal(0, 0.001, periods)),
            "high": prices * (1 + np.random.uniform(0, 0.005, periods)),
            "low": prices * (1 - np.random.uniform(0, 0.005, periods)),
            "close": prices,
            "volume": np.random.uniform(1000, 10000, periods),
            "symbol": symbol,
        })
        
        # 添加一些技术指标
        df["returns_1h"] = df["close"].pct_change(12)
        df["returns_4h"] = df["close"].pct_change(48)
        
        # RSI
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df["rsi_14"] = 100 - (100 / (1 + rs))
        
        # 布林带
        df["bb_middle"] = df["close"].rolling(window=20).mean()
        df["bb_std"] = df["close"].rolling(window=20).std()
        df["bb_upper"] = df["bb_middle"] + 2 * df["bb_std"]
        df["bb_lower"] = df["bb_middle"] - 2 * df["bb_std"]
        
        # 成交量比率
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=288).mean()
        
        # MACD
        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        df["macd"] = ema12 - ema26
        df["macd_signal"] = df["macd"].ewm(span=9).mean()
        
        # 模拟资金费率
        df["funding_rate"] = np.random.normal(0.0001, 0.0005, periods)
        df["funding_delta"] = df["funding_rate"].diff(12)
        
        # 模拟持仓量变化
        df["oi_change_1h"] = np.random.normal(0, 0.02, periods)
        
        # 时间特征
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"] >= 5
        
        # 上影线比例
        df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
        
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """准备特征"""
        df = df.copy()
        
        # 确保时间排序
        df = df.sort_values("timestamp").reset_index(drop=True)
        
        # 如果缺少某些列，补充
        if "returns_1h" not in df.columns:
            df["returns_1h"] = df["close"].pct_change(12)
        if "returns_4h" not in df.columns:
            df["returns_4h"] = df["close"].pct_change(48)
        if "hour" not in df.columns:
            df["hour"] = df["timestamp"].dt.hour
        if "day_of_week" not in df.columns:
            df["day_of_week"] = df["timestamp"].dt.dayofweek
        if "is_weekend" not in df.columns:
            df["is_weekend"] = df["day_of_week"] >= 5
        if "volume_ratio" not in df.columns and "volume" in df.columns:
            df["volume_ratio"] = df["volume"] / df["volume"].rolling(288).mean()
        if "wick_ratio" not in df.columns:
            df["wick_ratio"] = (df["high"] - df["close"]) / (df["high"] - df["low"] + 0.001)
        
        return df
    
    # 策略检测函数
    def detect_rsi_14(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """RSI策略"""
        rsi = row.get("rsi_14", 50)
        if pd.isna(rsi):
            return 0, 0
        
        if len(prev_rows) >= 1:
            prev_rsi = prev_rows.iloc[-1].get("rsi_14", 50)
            
            if prev_rsi >= 30 and rsi < 30:
                return 1, 0.7  # 做多
            elif prev_rsi <= 70 and rsi > 70:
                return -1, 0.7  # 做空
        
        return 0, 0
    
    def detect_macd_12_26_9(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """MACD策略"""
        macd = row.get("macd", 0)
        macd_signal = row.get("macd_signal", 0)
        if pd.isna(macd) or pd.isna(macd_signal):
            return 0, 0
        
        if len(prev_rows) >= 1:
            prev_macd = prev_rows.iloc[-1].get("macd", 0)
            prev_macd_signal = prev_rows.iloc[-1].get("macd_signal", 0)
            
            if prev_macd <= prev_macd_signal and macd > macd_signal:
                return 1, 0.7  # 金叉做多
            elif prev_macd >= prev_macd_signal and macd < macd_signal:
                return -1, 0.7  # 死叉做空
        
        return 0, 0
    
    def detect_bollinger_bands(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """布林带策略"""
        close = row["close"]
        bb_upper = row.get("bb_upper", close * 1.02)
        bb_lower = row.get("bb_lower", close * 0.98)
        
        if pd.isna(bb_upper) or pd.isna(bb_lower):
            return 0, 0
        
        if close < bb_lower:
            return 1, 0.6  # 跌破下轨做多
        elif close > bb_upper:
            return -1, 0.6  # 突破上轨做空
        
        return 0, 0
    
    def detect_panic_reversal(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """恐慌反弹策略"""
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        
        if returns_1h < -0.015 and volume_ratio > 1.5:
            return 1, 0.8
        
        return 0, 0
    
    def detect_long_liquidation_bounce(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """多头踩踏反弹策略"""
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        rsi = row.get("rsi_14", 50)
        
        conditions_met = 0
        if returns_1h < -0.02:
            conditions_met += 1
        if rsi < 25:
            conditions_met += 1
        if volume_ratio > 2.0:
            conditions_met += 1
        
        if conditions_met >= 2:
            return 1, 0.6 + conditions_met * 0.1
        
        return 0, 0
    
    def detect_volume_climax_fade(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """放量高潮衰竭策略"""
        volume_ratio = row.get("volume_ratio", 1)
        wick_ratio = row.get("wick_ratio", 0)
        returns_1h = row.get("returns_1h", 0)
        
        if volume_ratio > 2.0 and wick_ratio > 0.3 and returns_1h > 0.003:
            return -1, 0.75
        
        return 0, 0
    
    def detect_weak_bounce_short(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """弱反弹做空策略"""
        if len(prev_rows) < 48:
            return 0, 0
        
        close_4h_ago = prev_rows.iloc[-48]["close"]
        close_1h_ago = prev_rows.iloc[-12]["close"]
        current_close = row["close"]
        
        drop_4h = (close_4h_ago - close_1h_ago) / close_4h_ago
        bounce = (current_close - close_1h_ago) / close_1h_ago
        volume_ratio = row.get("volume_ratio", 1)
        
        if drop_4h > 0.02 and 0.003 < bounce < 0.015 and volume_ratio > 1.5:
            return -1, 0.7
        
        return 0, 0
    
    def detect_fake_breakout_trap(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """假突破反杀策略"""
        if len(prev_rows) < 24:
            return 0, 0
        
        rolling_high = prev_rows.iloc[-24:]["high"].max()
        breakout = row["high"] > rolling_high * 1.005
        volume_ratio = row.get("volume_ratio", 1)
        price_rejected = row["close"] < row["high"] * 0.998
        
        if breakout and volume_ratio < 1.2 and price_rejected:
            return -1, 0.7
        
        return 0, 0
    
    def detect_short_squeeze_hunt(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """抓空头挤压策略"""
        funding_rate = row.get("funding_rate", 0)
        oi_change_1h = row.get("oi_change_1h", 0)
        returns_1h = row.get("returns_1h", 0)
        
        if funding_rate < -0.00005 and oi_change_1h > 0.01 and returns_1h > 0.008:
            return 1, 0.7
        
        return 0, 0
    
    def detect_funding_reset(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """资金费率重置策略"""
        funding_rate = row.get("funding_rate", 0)
        funding_delta = row.get("funding_delta", 0)
        
        if funding_rate > 0.0003 and funding_delta < -0.00005:
            return -1, 0.65
        
        return 0, 0
    
    def detect_oi_flush(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """OI洗盘策略"""
        oi_change_1h = row.get("oi_change_1h", 0)
        returns_1h = row.get("returns_1h", 0)
        
        if oi_change_1h < -0.05 and abs(returns_1h) < 0.02:
            return -1, 0.6
        
        return 0, 0
    
    # Playbook策略
    def detect_pb_panic_reversal(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """Playbook恐慌反弹（更宽松）"""
        returns_1h = row.get("returns_1h", 0)
        volume_ratio = row.get("volume_ratio", 1)
        
        if returns_1h < -0.015 and volume_ratio > 1.3:
            return 1, 0.7
        
        return 0, 0
    
    def detect_pb_fake_breakout(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """Playbook假突破"""
        if len(prev_rows) < 60:
            return 0, 0
        
        rolling_high = prev_rows.iloc[-60:]["high"].max()
        if row["high"] > rolling_high * 1.005:
            return -1, 0.6
        
        return 0, 0
    
    def detect_pb_oi_flush(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """Playbook OI洗盘"""
        funding_rate = row.get("funding_rate", 0)
        volume_ratio = row.get("volume_ratio", 1)
        returns_5m = row.get("returns_5m", 0) or row["close"] / prev_rows.iloc[-1]["close"] - 1 if len(prev_rows) >= 1 else 0
        
        if funding_rate > 0.0002 and volume_ratio > 1.5 and returns_5m > 0.01:
            return 1, 0.6
        
        return 0, 0
    
    def detect_pb_short_squeeze(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """Playbook空头挤压"""
        funding_rate = row.get("funding_rate", 0)
        returns_5m = row.get("returns_5m", 0) or row["close"] / prev_rows.iloc[-1]["close"] - 1 if len(prev_rows) >= 1 else 0
        volume_ratio = row.get("volume_ratio", 1)
        
        if funding_rate > 0.0003 and returns_5m > 0.01 and volume_ratio > 1.5:
            return 1, 0.65
        
        return 0, 0
    
    def detect_pb_volume_climax(self, row: pd.Series, prev_rows: pd.DataFrame) -> Tuple[int, float]:
        """Playbook放量高潮"""
        volume_ratio = row.get("volume_ratio", 1)
        wick_ratio = row.get("wick_ratio", 0)
        
        if volume_ratio > 1.8 and wick_ratio > 0.015:
            return 1, 0.55
        
        return 0, 0
    
    def get_detector(self, strategy_id: str):
        """获取策略检测器"""
        detectors = {
            "rsi_14": self.detect_rsi_14,
            "macd_12_26_9": self.detect_macd_12_26_9,
            "bollinger_bands": self.detect_bollinger_bands,
            "panic_reversal": self.detect_panic_reversal,
            "long_liquidation_bounce": self.detect_long_liquidation_bounce,
            "volume_climax_fade": self.detect_volume_climax_fade,
            "weak_bounce_short": self.detect_weak_bounce_short,
            "fake_breakout_trap": self.detect_fake_breakout_trap,
            "short_squeeze_hunt": self.detect_short_squeeze_hunt,
            "funding_reset": self.detect_funding_reset,
            "oi_flush": self.detect_oi_flush,
            "pb_panic_reversal": self.detect_pb_panic_reversal,
            "pb_fake_breakout": self.detect_pb_fake_breakout,
            "pb_oi_flush": self.detect_pb_oi_flush,
            "pb_short_squeeze": self.detect_pb_short_squeeze,
            "pb_volume_climax": self.detect_pb_volume_climax,
        }
        return detectors.get(strategy_id)
    
    def run_backtest(self, symbol: str, df: pd.DataFrame) -> Dict:
        """运行单个交易对的回测"""
        logger.info(f"Running backtest for {symbol}...")
        
        positions: Dict[str, Position] = {}  # strategy_id -> Position
        trades: List[Trade] = []
        equity_curve = []
        capital = self.config.initial_capital
        peak_capital = capital
        trade_count = 0
        
        # 每个策略的独立结果
        strategy_results = defaultdict(lambda: {
            "trades": [],
            "capital": self.config.initial_capital,
            "peak_capital": self.config.initial_capital,
        })
        
        for i in range(100, len(df)):
            row = df.iloc[i]
            prev_rows = df.iloc[max(0, i-300):i]
            current_time = row["timestamp"]
            current_price = row["close"]
            
            # 1. 检查现有持仓
            positions_to_close = []
            
            for strategy_id, pos in list(positions.items()):
                # 更新最高/最低价
                if pos.direction == 1:
                    if row["high"] > pos.highest_price:
                        pos.highest_price = row["high"]
                        # 更新移动止损
                        new_ts = pos.highest_price * (1 - self.price_trailing_stop_pct)
                        if new_ts > pos.trailing_stop_price:
                            pos.trailing_stop_price = new_ts
                else:
                    if row["low"] < pos.lowest_price:
                        pos.lowest_price = row["low"]
                        # 更新移动止损
                        new_ts = pos.lowest_price * (1 + self.price_trailing_stop_pct)
                        if new_ts < pos.trailing_stop_price:
                            pos.trailing_stop_price = new_ts
                
                # 检查平仓条件
                close_reason = None
                exit_price = current_price
                
                # 固定止损
                if pos.direction == 1:
                    if row["low"] <= pos.stop_loss_price:
                        close_reason = "stop_loss"
                        exit_price = pos.stop_loss_price
                else:
                    if row["high"] >= pos.stop_loss_price:
                        close_reason = "stop_loss"
                        exit_price = pos.stop_loss_price
                
                # 固定止盈
                if not close_reason and pos.take_profit_price:
                    if pos.direction == 1:
                        if row["high"] >= pos.take_profit_price:
                            close_reason = "take_profit"
                            exit_price = pos.take_profit_price
                    else:
                        if row["low"] <= pos.take_profit_price:
                            close_reason = "take_profit"
                            exit_price = pos.take_profit_price
                
                # 移动止损
                if not close_reason:
                    if pos.direction == 1:
                        if row["low"] <= pos.trailing_stop_price:
                            close_reason = "trailing_stop"
                            exit_price = pos.trailing_stop_price
                    else:
                        if row["high"] >= pos.trailing_stop_price:
                            close_reason = "trailing_stop"
                            exit_price = pos.trailing_stop_price
                
                # 时间止损
                if not close_reason:
                    hold_hours = (current_time - pos.entry_time).total_seconds() / 3600
                    if hold_hours >= self.config.max_hold_hours:
                        close_reason = "time_exit"
                
                if close_reason:
                    positions_to_close.append((strategy_id, exit_price, close_reason))
            
            # 平仓
            for strategy_id, exit_price, close_reason in positions_to_close:
                pos = positions.pop(strategy_id)
                
                # 计算盈亏
                if pos.direction == 1:
                    ret = (exit_price - pos.entry_price) / pos.entry_price
                else:
                    ret = (pos.entry_price - exit_price) / pos.entry_price
                
                pnl = ret * self.config.leverage * pos.margin
                pnl_pct = ret * self.config.leverage
                
                # 扣除手续费（模拟0.1%）
                fee = pos.margin * 0.001
                pnl -= fee
                
                duration_hours = (current_time - pos.entry_time).total_seconds() / 3600
                
                trade = Trade(
                    trade_id=f"{symbol}_{strategy_id}_{trade_count}",
                    strategy_id=strategy_id,
                    symbol=symbol,
                    direction="long" if pos.direction == 1 else "short",
                    entry_time=pos.entry_time,
                    exit_time=current_time,
                    entry_price=pos.entry_price,
                    exit_price=exit_price,
                    margin=pos.margin,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    exit_reason=close_reason,
                    duration_hours=duration_hours,
                )
                
                trades.append(trade)
                trade_count += 1
                
                # 更新策略资金
                strategy_results[strategy_id]["trades"].append(trade)
                strategy_results[strategy_id]["capital"] += pnl
                if strategy_results[strategy_id]["capital"] > strategy_results[strategy_id]["peak_capital"]:
                    strategy_results[strategy_id]["peak_capital"] = strategy_results[strategy_id]["capital"]
            
            # 2. 检查新信号
            for strategy_id, strategy_config in STRATEGIES.items():
                # 跳过已有持仓的策略
                if strategy_id in positions:
                    continue
                
                detector = self.get_detector(strategy_id)
                if not detector:
                    continue
                
                try:
                    direction, confidence = detector(row, prev_rows)
                except Exception:
                    continue
                
                if direction == 0:
                    continue
                
                # 检查策略方向限制
                if strategy_config["direction"] != 0 and direction != strategy_config["direction"]:
                    continue
                
                # 计算仓位大小（每笔用全部资金）
                margin = strategy_results[strategy_id]["capital"] * 0.95  # 留5%缓冲
                
                # 计算止损/止盈价格
                if direction == 1:
                    stop_loss_price = current_price * (1 - self.price_stop_loss_pct)
                    trailing_stop_price = stop_loss_price
                    take_profit_price = current_price * (1 + self.price_take_profit_pct) if self.price_take_profit_pct else None
                else:
                    stop_loss_price = current_price * (1 + self.price_stop_loss_pct)
                    trailing_stop_price = stop_loss_price
                    take_profit_price = current_price * (1 - self.price_take_profit_pct) if self.price_take_profit_pct else None
                
                positions[strategy_id] = Position(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    direction=direction,
                    entry_price=current_price,
                    entry_time=current_time,
                    margin=margin,
                    stop_loss_price=stop_loss_price,
                    trailing_stop_price=trailing_stop_price,
                    take_profit_price=take_profit_price,
                    highest_price=current_price,
                    lowest_price=current_price,
                )
            
            # 3. 计算总权益（所有策略的总和）
            total_equity = sum(strat_res["capital"] for strat_res in strategy_results.values())
            for pos in positions.values():
                # 计算持仓浮盈
                if pos.direction == 1:
                    ret = (current_price - pos.entry_price) / pos.entry_price
                else:
                    ret = (pos.entry_price - current_price) / pos.entry_price
                unrealized_pnl = ret * self.config.leverage * pos.margin
                total_equity += unrealized_pnl
            
            if total_equity > peak_capital:
                peak_capital = total_equity
            
            equity_curve.append({
                "timestamp": current_time,
                "equity": total_equity,
                "drawdown": (peak_capital - total_equity) / peak_capital if peak_capital > 0 else 0,
            })
            
            # 检查总资金止损
            if total_equity <= self.config.initial_capital * (1 - self.config.capital_stop_loss_pct):
                logger.warning(f"Global stop loss triggered for {symbol}!")
                break
        
        # 回测结束，平掉剩余持仓
        for strategy_id, pos in list(positions.items()):
            current_time = df.iloc[-1]["timestamp"]
            current_price = df.iloc[-1]["close"]
            
            if pos.direction == 1:
                ret = (current_price - pos.entry_price) / pos.entry_price
            else:
                ret = (pos.entry_price - current_price) / pos.entry_price
            
            pnl = ret * self.config.leverage * pos.margin
            pnl_pct = ret * self.config.leverage
            
            fee = pos.margin * 0.001
            pnl -= fee
            
            duration_hours = (current_time - pos.entry_time).total_seconds() / 3600
            
            trade = Trade(
                trade_id=f"{symbol}_{strategy_id}_{trade_count}",
                strategy_id=strategy_id,
                symbol=symbol,
                direction="long" if pos.direction == 1 else "short",
                entry_time=pos.entry_time,
                exit_time=current_time,
                entry_price=pos.entry_price,
                exit_price=current_price,
                margin=pos.margin,
                pnl=pnl,
                pnl_pct=pnl_pct,
                exit_reason="end_of_data",
                duration_hours=duration_hours,
            )
            
            trades.append(trade)
            trade_count += 1
            
            strategy_results[strategy_id]["trades"].append(trade)
            strategy_results[strategy_id]["capital"] += pnl
        
        # 汇总结果
        symbol_result = {
            "symbol": symbol,
            "trades": trades,
            "equity_curve": equity_curve,
            "strategy_results": {},
        }
        
        for strategy_id, strat_res in strategy_results.items():
            strat_trades = strat_res["trades"]
            if not strat_trades:
                continue
            
            final_capital = strat_res["capital"]
            total_return = final_capital - self.config.initial_capital
            total_return_pct = total_return / self.config.initial_capital
            peak_capital = strat_res["peak_capital"]
            max_drawdown = (peak_capital - min(t.pnl for t in strat_trades) - final_capital) / peak_capital if peak_capital > 0 else 0
            
            winning_trades = [t for t in strat_trades if t.pnl > 0]
            win_rate = len(winning_trades) / len(strat_trades) if strat_trades else 0
            avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t.pnl for t in strat_trades if t.pnl <= 0]) if [t for t in strat_trades if t.pnl <= 0] else 0
            profit_factor = abs(sum(t.pnl for t in winning_trades) / sum(t.pnl for t in strat_trades if t.pnl <= 0)) if sum(t.pnl for t in strat_trades if t.pnl <= 0) != 0 else 0
            
            exit_reasons = defaultdict(int)
            for t in strat_trades:
                exit_reasons[t.exit_reason] += 1
            
            symbol_result["strategy_results"][strategy_id] = {
                "strategy_id": strategy_id,
                "strategy_name": STRATEGIES[strategy_id]["name"],
                "final_capital": final_capital,
                "total_return": total_return,
                "total_return_pct": total_return_pct,
                "peak_capital": peak_capital,
                "max_drawdown_pct": max_drawdown,
                "total_trades": len(strat_trades),
                "winning_trades": len(winning_trades),
                "win_rate": win_rate,
                "avg_win": avg_win,
                "avg_loss": avg_loss,
                "profit_factor": profit_factor,
                "avg_duration_hours": np.mean([t.duration_hours for t in strat_trades]),
                "exit_reasons": dict(exit_reasons),
            }
        
        return symbol_result
    
    def run_all(self) -> Dict:
        """运行所有交易对的回测"""
        all_results = {}
        all_trades = []
        
        for symbol in self.symbols:
            df = self.load_data(symbol, months=5)
            df = self.prepare_features(df)
            
            result = self.run_backtest(symbol, df)
            all_results[symbol] = result
            all_trades.extend(result["trades"])
        
        # 汇总所有结果
        summary = self.summarize_results(all_results)
        
        return {
            "config": {
                "initial_capital": self.config.initial_capital,
                "leverage": self.config.leverage,
                "capital_stop_loss_pct": self.config.capital_stop_loss_pct,
                "trailing_stop_pct": self.config.trailing_stop_pct,
                "fixed_take_profit_pct": self.config.fixed_take_profit_pct,
                "symbols": self.symbols,
            },
            "symbol_results": all_results,
            "summary": summary,
            "all_trades": all_trades,
        }
    
    def summarize_results(self, all_results: Dict) -> Dict:
        """汇总回测结果"""
        # 按策略汇总
        strategy_summary = defaultdict(lambda: {
            "total_trades": 0,
            "winning_trades": 0,
            "total_return": 0,
            "symbols": set(),
        })
        
        for symbol, result in all_results.items():
            for strategy_id, strat_res in result["strategy_results"].items():
                ss = strategy_summary[strategy_id]
                ss["total_trades"] += strat_res["total_trades"]
                ss["winning_trades"] += strat_res["winning_trades"]
                ss["total_return"] += strat_res["total_return"]
                ss["symbols"].add(symbol)
        
        # 转换为列表并排序
        summary_list = []
        for strategy_id, ss in strategy_summary.items():
            avg_return = ss["total_return"] / len(ss["symbols"]) if ss["symbols"] else 0
            win_rate = ss["winning_trades"] / ss["total_trades"] if ss["total_trades"] > 0 else 0
            
            summary_list.append({
                "strategy_id": strategy_id,
                "strategy_name": STRATEGIES[strategy_id]["name"],
                "total_trades": ss["total_trades"],
                "winning_trades": ss["winning_trades"],
                "win_rate": win_rate,
                "total_return": ss["total_return"],
                "avg_return_per_symbol": avg_return,
                "symbols_traded": list(ss["symbols"]),
            })
        
        summary_list.sort(key=lambda x: x["total_return"], reverse=True)
        
        return {
            "strategies": summary_list,
        }
    
    def print_report(self, results: Dict):
        """打印回测报告"""
        print("\n" + "=" * 120)
        print("🚀 完整策略回测报告 - 多交易对")
        print("=" * 120)
        print(f"初始资金: ${self.config.initial_capital:,.0f} | 杠杆: {self.config.leverage}x | 本金止损: {self.config.capital_stop_loss_pct*100:.0f}%")
        print(f"移动止盈回撤: {self.config.trailing_stop_pct*100:.0f}% | 固定止盈: {self.config.fixed_take_profit_pct*100:.0f}%")
        print(f"交易对: {', '.join(self.symbols)}")
        print("=" * 120)
        
        print("\n📊 策略综合排名（按总收益）:")
        print("-" * 120)
        print(f"{'策略':<30} | {'交易对':<15} | {'总交易':<8} | {'胜率':<8} | {'总收益':<15} | {'平均收益/交易对':<15}")
        print("-" * 120)
        
        for s in results["summary"]["strategies"]:
            if s["total_trades"] == 0:
                continue
            status = "✅" if s["total_return"] > 0 else "❌"
            print(f"{status} {s['strategy_name']:<28} | {len(s['symbols_traded']):<15} | {s['total_trades']:<8} | {s['win_rate']*100:>6.1f}% | ${s['total_return']:>12,.2f} | ${s['avg_return_per_symbol']:>12,.2f}")
        
        # 每个交易对的详细结果
        for symbol in self.symbols:
            if symbol not in results["symbol_results"]:
                continue
            
            print(f"\n\n{'='*120}")
            print(f"📈 {symbol} 详细结果")
            print(f"{'='*120}")
            
            symbol_result = results["symbol_results"][symbol]
            strat_results = list(symbol_result["strategy_results"].items())
            strat_results.sort(key=lambda x: x[1]["total_return"], reverse=True)
            
            print(f"\n{'策略':<30} | {'最终资金':<12} | {'总收益':<12} | {'胜率':<8} | {'交易数':<8} | {'盈亏比':<8}")
            print("-" * 120)
            
            for strategy_id, sr in strat_results:
                status = "✅" if sr["total_return"] > 0 else "❌"
                print(f"{status} {sr['strategy_name']:<28} | ${sr['final_capital']:>10,.0f} | ${sr['total_return']:>10,.2f} | {sr['win_rate']*100:>6.1f}% | {sr['total_trades']:<8} | {sr['profit_factor']:>6.2f}")
        
        print("\n" + "=" * 120)
    
    def save_results(self, results: Dict):
        """保存结果"""
        output_dir = backend_path / "data_lake" / "research"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存完整结果
        output_path = output_dir / "complete_backtest_all_symbols.json"
        
        # 转换为可序列化格式
        def serialize(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            if isinstance(obj, Trade):
                return obj.__dict__
            return obj
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=serialize, ensure_ascii=False)
        
        print(f"\n💾 结果已保存: {output_path}")


def main():
    print("=" * 120)
    print("🚀 完整策略回测系统启动")
    print("=" * 120)
    
    config = BacktestConfig(
        initial_capital=10000.0,
        leverage=50.0,
        capital_stop_loss_pct=0.10,
        trailing_stop_pct=0.15,
        fixed_take_profit_pct=0.20,
        max_hold_hours=48,
    )
    
    tester = CompleteBacktester(config)
    results = tester.run_all()
    tester.print_report(results)
    tester.save_results(results)
    
    print("\n✅ 回测完成!")


if __name__ == "__main__":
    main()
