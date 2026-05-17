"""
Test all data channels for connectivity and data fetching.
"""
import sys
import asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infrastructure.logging import get_logger
from infrastructure.resilience import get_multi_channel_manager

logger = get_logger("test_data_channels")

async def test_channel_connectivity():
    """Test each channel individually"""
    manager = get_multi_channel_manager()
    results = {}
    
    # Test all configured channels
    for channel_config in manager.config.channels:
        channel_type = channel_config.channel_type
        channel_name = channel_config.name
        
        if channel_type.value >= 100:  # Skip Mock for now
            continue
        
        logger.info(f"Testing channel: {channel_name} ({channel_type.name})")
        
        try:
            # Create a temporary manager with only this channel enabled
            from infrastructure.resilience.data_fallback import (
                MultiChannelConfig,
                ChannelConfig,
            )
            
            single_channel_config = MultiChannelConfig(
                channels=[channel_config],
                mock_mode=False,
            )
            
            # Re-initialize fetcher for just this channel
            manager_single = type(manager)(single_channel_config)
            
            start_time = asyncio.get_event_loop().time()
            price_data = await manager_single.get_price("BTCUSDT")
            latency = (asyncio.get_event_loop().time() - start_time) * 1000
            
            if price_data:
                results[channel_name] = {
                    "status": "success",
                    "price": price_data.price,
                    "latency_ms": round(latency, 2),
                    "source": price_data.source_channel.name
                }
                logger.info(f"✓ {channel_name} - {price_data.price} ({latency:.0f}ms)")
            else:
                results[channel_name] = {
                    "status": "failed",
                    "error": "No price data returned"
                }
                logger.warning(f"✗ {channel_name} - No price data")
                
        except Exception as e:
            results[channel_name] = {
                "status": "error",
                "error": str(e)
            }
            logger.error(f"✗ {channel_name} - Error: {e}")
    
    return results

async def test_full_multi_channel():
    """Test full multi-channel with fallback"""
    logger.info("\n" + "="*60)
    logger.info("Testing full multi-channel fallback")
    logger.info("="*60)
    
    manager = get_multi_channel_manager()
    
    health = manager.get_health_status()
    logger.info(f"Active channels: {[c.name for c in manager.config.channels]}")
    
    try:
        price_data = await manager.get_price("BTCUSDT")
        
        if price_data:
            logger.info(f"\n✓ Success - Final price from {price_data.source_channel.name}: {price_data.price}")
            if price_data.bid:
                logger.info(f"  Bid: {price_data.bid}, Ask: {price_data.ask}")
            if price_data.volume_24h:
                logger.info(f"  Volume (24h): {price_data.volume_24h}")
            if price_data.change_24h is not None:
                logger.info(f"  Change (24h): {price_data.change_24h:.2f}%")
            return price_data
        else:
            logger.error("✗ All channels failed!")
            return None
            
    except Exception as e:
        logger.error(f"✗ Error in multi-channel test: {e}")
        return None

async def main():
    logger.info("="*60)
    logger.info("Data Channel Connectivity Test Suite")
    logger.info("="*60)
    
    # Test 1: Individual channels
    logger.info("\n[Test 1] Individual channel connectivity")
    logger.info("-"*60)
    channel_results = await test_channel_connectivity()
    
    # Test 2: Full multi-channel
    logger.info("\n[Test 2] Full multi-channel with fallback")
    logger.info("-"*60)
    final_price = await test_full_multi_channel()
    
    # Summary
    logger.info("\n" + "="*60)
    logger.info("SUMMARY")
    logger.info("="*60)
    
    success_count = sum(1 for r in channel_results.values() if r["status"] == "success")
    total_count = len(channel_results)
    
    logger.info(f"Total channels: {total_count}")
    logger.info(f"Working channels: {success_count}")
    
    if success_count > 0:
        for name, result in channel_results.items():
            if result["status"] == "success":
                logger.info(f"✓ {name}: {result['price']} ({result['latency_ms']:.0f}ms)")
            else:
                logger.info(f"✗ {name}: {result.get('error', 'Unknown')}")
    
    if final_price:
        logger.info(f"\n✓ Multi-channel fallback working - got price from {final_price.source_channel.name}")
        return 0
    else:
        logger.error("\n✗ No working channels!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
