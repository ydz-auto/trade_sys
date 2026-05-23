import asyncio
from runtime.feature_runtime import FeatureRuntime, FeatureConfig


async def main():
    config = FeatureConfig()
    runtime = FeatureRuntime(config)
    await runtime.start()
    try:
        while runtime._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())
