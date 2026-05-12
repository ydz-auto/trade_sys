"""
QQ → Telegram 桥 - 消息转发

很多人会这样做：
- QQ 群消息 → Telegram 私人频道
- 原因：
  * Telegram 更容易检索
  * 更适合 AI 处理
  * 更容易做历史分析

运行：
    cd backend
    python3 examples/qq_to_telegram.py

需要：
1. NapCatQQ (见 qq_mvp.py)
2. Telegram Bot Token
3. Telegram Chat ID
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.data_service.sources.qq_realtime import QQRealtimeSource


class QQTelegramBridge:
    """QQ → Telegram 消息桥"""

    def __init__(self):
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️  未配置 Telegram")
            print("需要设置:")
            print("  TELEGRAM_BOT_TOKEN=your_bot_token")
            print("  TELEGRAM_CHAT_ID=your_chat_id")
            self._can_send = False
        else:
            self._can_send = True

    async def send_to_telegram(self, message: str):
        """发送到 Telegram"""
        if not self._can_send:
            return

        import aiohttp

        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as resp:
                    if resp.status != 200:
                        print(f"Telegram 发送失败: {resp.status}")
        except Exception as e:
            print(f"Telegram 错误: {e}")

    def format_message(self, event) -> str:
        """格式化消息"""
        priority = event.metadata.get("priority", "P2")
        priority_emoji = {"P0": "🔴", "P1": "🟡", "P2": "🟢"}.get(priority, "⚪")

        symbols = ", ".join(event.symbols) if event.symbols else "无"

        sentiment_emoji = {
            "bullish": "📈",
            "bearish": "📉",
            "neutral": "➖"
        }.get(event.sentiment, "➖")

        message = f"""
{priority_emoji} <b>[{priority}]</b> {event.metadata.get('sender', '匿名')}
{sentiment_emoji} {event.content[:200]}
📊 币种: {symbols}
🏷️ 群: {event.metadata.get('group_id', 'N/A')}
        """.strip()

        return message


async def main():
    print("=" * 70)
    print("QQ → Telegram 桥")
    print("=" * 70)

    bridge = QQTelegramBridge()

    if not bridge._can_send:
        print("\n⚠️  跳过 Telegram 发送，仅打印消息")
        print()

    source = QQRealtimeSource()

    async def on_event(event):
        if event.metadata.get("priority") in ["P0", "P1"]:
            message = bridge.format_message(event)

            print(f"\n📨 转发消息:")
            print(message)
            print()

            if bridge._can_send:
                await bridge.send_to_telegram(message)

    source.on_event = on_event

    print("\n监听中... (Ctrl+C 停止)")
    print()

    try:
        await source.listen()
    except KeyboardInterrupt:
        print("\n\n停止中...")
        await source.stop()


if __name__ == "__main__":
    asyncio.run(main())
