#!/usr/bin/env python3
"""
测试基于aggregation_service的历史特征提取器
"""
import asyncio
from services.aggregation_service import extract_historical_features, get_feature_status


async def main():
    print("=" * 80)
    print("测试历史特征提取器 (基于 aggregation_service)")
    print("=" * 80)

    symbol = "BTCUSDT"
    year = 2024
    month = 1
    intervals = ["1m", "5m"]

    print(f"交易对: {symbol}")
    print(f"时间: {year}-{month:02d}")
    print(f"周期: {intervals}")
    print()

    print("正在提取特征...")
    results = await extract_historical_features(
        symbol=symbol,
        years=[year],
        intervals=intervals
    )

    print("\n提取结果:")
    for result in results:
        if result["success"]:
            print(f"✓ {result['symbol']} {result['year']}-{result['month']:02d}")
            for interval, data in result["results"].items():
                print(f"  {interval}: {data['records']:,} 条记录, {data['size_mb']:.2f} MB")
        else:
            print(f"✗ {result['symbol']} {result['year']}-{result['month']:02d}: {result['message']}")

    print("\n" + "=" * 80)
    print("特征状态检查")
    print("=" * 80)
    status = await get_feature_status(symbol)
    for s in status:
        print(f"{s['interval']}: {s['records_count']:,} 条记录, {s['storage_size_mb']:.2f} MB")

    print("\n存储位置:")
    print("  e:\\00_crypto\\00_code\\backend\\data_lake\\features\\")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
