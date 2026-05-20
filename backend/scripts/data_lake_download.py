#!/usr/bin/env python3
"""
数据湖下载脚本 - 统一入口
支持: Binance/OKX K线, Funding Rate, Open Interest, Liquidation, Trades
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from infrastructure.data_lake import get_data_lake_root_cached

DATA_LAKE_ROOT = get_data_lake_root_cached()


def ensure_data_dirs():
    dirs = [
        "crypto/binance/klines",
        "crypto/binance/funding",
        "crypto/binance/oi",
        "crypto/binance/trades",
        "crypto/binance/liquidation",
        "crypto/okx/klines",
        "crypto/okx/funding",
        "crypto/okx/oi",
        "crypto/okx/trades",
        "crypto/okx/liquidation",
    ]
    for d in dirs:
        path = DATA_LAKE_ROOT / d
        path.mkdir(parents=True, exist_ok=True)
        print(f"[OK] {path}")


def download_binance_klines(symbols, years, interval="1m"):
    from scripts.download_binance_klines import download_klines
    download_klines(symbols, years, interval, DATA_LAKE_ROOT)


def download_okx_klines(symbols, years, interval="1m"):
    from scripts.download_okx_klines import download_klines
    download_klines(symbols, years, interval, DATA_LAKE_ROOT)


def download_binance_funding(symbols, years):
    from scripts.download_binance_funding import download_funding
    download_funding(symbols, years, DATA_LAKE_ROOT)


def download_binance_oi(symbols, years):
    from scripts.download_binance_oi import download_oi
    download_oi(symbols, years, DATA_LAKE_ROOT)


def download_binance_trades(symbols, years):
    from scripts.download_binance_trades import download_trades
    download_trades(symbols, years, DATA_LAKE_ROOT)


def download_binance_liquidation(symbols, years):
    from scripts.download_binance_liquidation import download_liquidation
    download_liquidation(symbols, years, DATA_LAKE_ROOT)


def download_okx_funding(symbols, years):
    from scripts.download_okx_funding import download_funding
    download_funding(symbols, years, DATA_LAKE_ROOT)


def download_okx_oi(symbols, years):
    from scripts.download_okx_oi import download_oi
    download_oi(symbols, years, DATA_LAKE_ROOT)


def download_okx_trades(symbols, years):
    from scripts.download_okx_trades import download_trades
    download_trades(symbols, years, DATA_LAKE_ROOT)


def download_okx_liquidation(symbols, years):
    from scripts.download_okx_liquidation import download_liquidation
    download_liquidation(symbols, years, DATA_LAKE_ROOT)


def main():
    parser = argparse.ArgumentParser(description="数据湖下载工具")
    parser.add_argument("--init", action="store_true", help="初始化目录结构")
    
    parser.add_argument("--binance-klines", action="store_true", help="下载Binance K线")
    parser.add_argument("--binance-funding", action="store_true", help="下载Binance Funding")
    parser.add_argument("--binance-oi", action="store_true", help="下载Binance OI")
    parser.add_argument("--binance-trades", action="store_true", help="下载Binance Trades")
    parser.add_argument("--binance-liquidation", action="store_true", help="下载Binance Liquidation")
    parser.add_argument("--binance-all", action="store_true", help="下载Binance全部数据")
    
    parser.add_argument("--okx-klines", action="store_true", help="下载OKX K线")
    parser.add_argument("--okx-funding", action="store_true", help="下载OKX Funding")
    parser.add_argument("--okx-oi", action="store_true", help="下载OKX OI")
    parser.add_argument("--okx-trades", action="store_true", help="下载OKX Trades")
    parser.add_argument("--okx-liquidation", action="store_true", help="下载OKX Liquidation")
    parser.add_argument("--okx-all", action="store_true", help="下载OKX全部数据")
    
    parser.add_argument("--all", action="store_true", help="下载全部数据")
    
    parser.add_argument("--symbols", nargs="+", default=["BTCUSDT", "ETHUSDT", "SOLUSDT", "ZECUSDT"])
    parser.add_argument("--years", nargs="+", type=int, default=[2024, 2025, 2026])
    parser.add_argument("--interval", default="1m", help="K线周期")
    
    args = parser.parse_args()
    
    if args.init:
        print("=" * 60)
        print("初始化数据湖目录结构")
        print("=" * 60)
        ensure_data_dirs()
        print(f"\n数据湖根目录: {DATA_LAKE_ROOT}")
        return
    
    if args.all:
        args.binance_all = True
        args.okx_all = True
    
    if args.binance_all:
        args.binance_klines = True
        args.binance_funding = True
        args.binance_oi = True
        args.binance_trades = True
        args.binance_liquidation = True
    
    if args.okx_all:
        args.okx_klines = True
        args.okx_funding = True
        args.okx_oi = True
        args.okx_trades = True
        args.okx_liquidation = True
    
    ensure_data_dirs()
    
    okx_symbols = [s.replace("USDT", "-USDT-SWAP") for s in args.symbols]
    
    if args.binance_klines:
        print("\n" + "=" * 60)
        print("下载 Binance K线数据")
        print("=" * 60)
        download_binance_klines(args.symbols, args.years, args.interval)
    
    if args.binance_funding:
        print("\n" + "=" * 60)
        print("下载 Binance Funding Rate")
        print("=" * 60)
        download_binance_funding(args.symbols, args.years)
    
    if args.binance_oi:
        print("\n" + "=" * 60)
        print("下载 Binance Open Interest")
        print("=" * 60)
        download_binance_oi(args.symbols, args.years)
    
    if args.binance_trades:
        print("\n" + "=" * 60)
        print("下载 Binance Trades")
        print("=" * 60)
        download_binance_trades(args.symbols, args.years)
    
    if args.binance_liquidation:
        print("\n" + "=" * 60)
        print("下载 Binance Liquidation")
        print("=" * 60)
        download_binance_liquidation(args.symbols, args.years)
    
    if args.okx_klines:
        print("\n" + "=" * 60)
        print("下载 OKX K线数据")
        print("=" * 60)
        download_okx_klines(okx_symbols, args.years, args.interval)
    
    if args.okx_funding:
        print("\n" + "=" * 60)
        print("下载 OKX Funding Rate")
        print("=" * 60)
        download_okx_funding(okx_symbols, args.years)
    
    if args.okx_oi:
        print("\n" + "=" * 60)
        print("下载 OKX Open Interest")
        print("=" * 60)
        download_okx_oi(okx_symbols, args.years)
    
    if args.okx_trades:
        print("\n" + "=" * 60)
        print("下载 OKX Trades")
        print("=" * 60)
        download_okx_trades(okx_symbols, args.years)
    
    if args.okx_liquidation:
        print("\n" + "=" * 60)
        print("下载 OKX Liquidation")
        print("=" * 60)
        download_okx_liquidation(okx_symbols, args.years)
    
    print("\n" + "=" * 60)
    print("下载完成!")
    print(f"数据存储位置: {DATA_LAKE_ROOT}")
    print("=" * 60)


if __name__ == "__main__":
    main()
