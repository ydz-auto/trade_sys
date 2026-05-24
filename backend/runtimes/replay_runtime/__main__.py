"""
Replay Runtime - 命令行入口
"""

import asyncio
from runtimes.replay_runtime.runtime import main

if __name__ == "__main__":
    asyncio.run(main())
