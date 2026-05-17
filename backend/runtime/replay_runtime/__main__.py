"""
Replay Runtime - 命令行入口
"""

import asyncio
from runtime.replay_runtime.runtime import main

if __name__ == "__main__":
    asyncio.run(main())
