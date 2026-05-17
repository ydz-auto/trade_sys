
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import asyncio
from services.data_service.collectors.exchange_collector import ExchangeCollector

async def test():
    print("Testing ExchangeCollector...")
    collector = ExchangeCollector(['BTC', 'ETH', 'SOL'], ['binance'])
    result = await collector.collect()
    print('Success:', result.success)
    if result.success:
        for symbol, multi_prices in result.data.items():
            print(f'\n{symbol}:')
            for exchange, price in multi_prices.prices.items():
                if price.status == 'ok':
                    print(f'  {exchange}: ${price.price:.2f} (24h change: {price.change_24h:.2f}%)')
                else:
                    print(f'  {exchange}: {price.status}')

asyncio.run(test())
