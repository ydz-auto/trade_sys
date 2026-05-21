#!/usr/bin/env python3
"""
Binance Liquidation 下载脚本

注意: Binance 不提供历史 Liquidation 数据下载。
需要通过 WebSocket 实时获取。

此脚本提供 WebSocket 实时订阅功能。
"""

import asyncio
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
import websockets

WS_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"


async def subscribe_liquidation(data_root: Path = None, duration_hours: int = 24):
    """
    通过 WebSocket 订阅 Liquidation 数据
    
    Args:
        data_root: 数据根目录
        duration_hours: 订阅时长(小时)
    """
    if data_root is None:
        data_root = Path(__file__).parent.parent / "data_lake"
    
    save_base = data_root / "crypto" / "binance" / "liquidation"
    save_base.mkdir(parents=True, exist_ok=True)
    
    all_data = []
    
    print(f"开始订阅 Liquidation 数据，时长: {duration_hours} 小时")
    print("按 Ctrl+C 停止")
    
    start_time = datetime.now()
    end_time = start_time + pd.Timedelta(hours=duration_hours)
    
    try:
        async with websockets.connect(WS_URL) as ws:
            while datetime.now() < end_time:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(msg)
                    
                    if "o" in data:
                        order = data["o"]
                        order["timestamp"] = pd.to_datetime(order["T"], unit="ms")
                        order["exchange"] = "binance"
                        all_data.append(order)
                        
                        if len(all_data) % 100 == 0:
                            print(f"已收集 {len(all_data)} 条 Liquidation 记录")
                    
                except asyncio.TimeoutError:
                    continue
                    
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"错误: {e}")
    
    if all_data:
        df = pd.DataFrame(all_data)
        
        df = df.sort_values("timestamp")
        
        for symbol in df["s"].unique():
            symbol_df = df[df["s"] == symbol]
            
            save_dir = save_base / f"symbol={symbol}"
            save_dir.mkdir(parents=True, exist_ok=True)
            
            parquet_path = save_dir / f"liquidation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet"
            symbol_df.to_parquet(parquet_path, compression="zstd", index=False)
            
            print(f"保存 {len(symbol_df)} 条 {symbol} 记录到 {parquet_path}")


def download_liquidation(
    symbols: list,
    years: list,
    data_root: Path = None,
):
    """
    注意: Binance 不提供历史 Liquidation 数据。
    请使用 WebSocket 实时订阅。
    """
    print("=" * 60)
    print("警告: Binance 不提供历史 Liquidation 数据下载")
    print("请使用 WebSocket 实时订阅:")
    print("  python scripts/download_binance_liquidation.py --realtime")
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Binance Liquidation 数据")
    parser.add_argument("--realtime", action="store_true", help="实时订阅 Liquidation 数据")
    parser.add_argument("--duration", type=int, default=24, help="订阅时长(小时)")
    
    args = parser.parse_args()
    
    if args.realtime:
        asyncio.run(subscribe_liquidation(duration_hours=args.duration))
    else:
        download_liquidation([], [])
