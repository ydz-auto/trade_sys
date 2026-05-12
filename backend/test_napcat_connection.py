#!/usr/bin/env python3
"""
测试 NapCatQQ WebSocket 连接

在配置环境之前，先用这个脚本测试 NapCatQQ 是否正常。
"""

import asyncio
import sys
import os

try:
    import websockets
except ImportError:
    print("❌ 需要安装 websockets:")
    print("   pip install websockets")
    sys.exit(1)

import json


async def test_napcat_connection():
    ws_url = os.getenv("QQ_WS_URL", "ws://127.0.0.1:3001")

    print("=" * 70)
    print("NapCatQQ 连接测试")
    print("=" * 70)
    print()
    print(f"WebSocket 地址: {ws_url}")
    print()
    print("正在连接...")
    print()

    try:
        async with websockets.connect(ws_url) as websocket:
            print("✅ 连接成功！")
            print()
            print("=" * 70)
            print("现在请在 QQ 群里发一条消息")
            print("按 Ctrl+C 停止")
            print("=" * 70)
            print()

            count = 0
            async for message in websocket:
                try:
                    data = json.loads(message)
                    count += 1

                    if data.get("post_type") == "message" and data.get("message_type") == "group":
                        group_id = data.get("group_id")
                        sender = data.get("sender", {}).get("nickname", "匿名")
                        msg_content = data.get("raw_message", "")

                        print(f"📱 [{count}] 群 {group_id} - {sender}")
                        print(f"   {msg_content}")
                        print()
                    else:
                        print(f"[{count}] 其他事件: {data.get('post_type')}")
                        print()

                except json.JSONDecodeError:
                    print(f"收到无效 JSON: {message[:50]}")
                except Exception as e:
                    print(f"处理消息出错: {e}")

    except ConnectionRefusedError:
        print("❌ 连接被拒绝！")
        print()
        print("请检查：")
        print("  1. NapCatQQ 是否正在运行？")
        print("  2. WebSocket 服务是否开启？")
        print("  3. 端口是否正确（默认 3001）？")
        print()
        print("NapCatQQ 下载: https://github.com/NapNeko/NapCatQQ/releases")
        print("配置指南: doc/交易系统/05_Data/05.15_NapCatQQ配置指南.md")
        return False

    except Exception as e:
        print(f"❌ 错误: {e}")
        print()
        return False


if __name__ == "__main__":
    try:
        asyncio.run(test_napcat_connection())
    except KeyboardInterrupt:
        print()
        print("=" * 70)
        print("停止")
        print("=" * 70)
