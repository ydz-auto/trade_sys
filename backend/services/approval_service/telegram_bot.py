"""
Telegram Approval Bot - Telegram 审批 Bot
"""

import os
from typing import Optional, List, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from infrastructure.config.manager import get_config_manager
from infrastructure.logging import get_logger
from ..approval_service.main import get_approval_service, ApprovalService

logger = get_logger("telegram_bot")


class TelegramApprovalBot:
    """Telegram 审批 Bot"""
    
    def __init__(self, approval_service: Optional[ApprovalService] = None):
        self._config = get_config_manager()
        self._approval_service = approval_service or get_approval_service()
        self._app: Optional[Application] = None
        self._chat_ids: List[int] = []
        self._parse_mode: str = "HTML"
        self._initialized: bool = False
    
    async def initialize(self):
        """初始化 Bot"""
        if self._initialized:
            return
        
        bot_token = self._config.get("approval.telegram.bot_token", "")
        if not bot_token:
            logger.warning("Telegram bot token not configured")
            return
        
        chat_ids_str = self._config.get("approval.telegram.approved_chat_ids", "")
        if chat_ids_str:
            self._chat_ids = [int(cid.strip()) for cid in chat_ids_str.split(",") if cid.strip()]
        
        self._parse_mode = self._config.get("approval.telegram.parse_mode", "HTML")
        
        self._app = Application.builder().token(bot_token).build()
        
        self._app.add_handler(CommandHandler("start", self._handle_start))
        self._app.add_handler(CommandHandler("list", self._handle_list))
        self._app.add_handler(CommandHandler("approve", self._handle_approve_command))
        self._app.add_handler(CommandHandler("reject", self._handle_reject_command))
        self._app.add_handler(CallbackQueryHandler(self._handle_callback))
        
        await self._app.initialize()
        self._initialized = True
        
        logger.info(f"Telegram bot initialized, chat_ids={self._chat_ids}")
    
    async def start(self):
        """启动 Bot"""
        if not self._initialized:
            await self.initialize()
        
        if not self._app:
            logger.error("Telegram bot not initialized")
            return
        
        await self._app.start()
        await self._app.updater.start_polling()
        
        logger.info("Telegram bot started")
    
    async def stop(self):
        """停止 Bot"""
        if self._app:
            await self._app.stop()
            logger.info("Telegram bot stopped")
    
    async def send_approval(
        self,
        request,
        is_recalculated: bool = False
    ):
        """发送审批消息"""
        if not self._app:
            logger.error("Telegram bot not initialized")
            return
        
        title = "🔄 重新计算 - 交易确认" if is_recalculated else "📊 交易确认请求"
        
        warning_text = ""
        if request.signal_age > 30:
            warning_text = f"\n⚠️ <b>信号已生成 {request.signal_age:.0f} 秒前</b>"
        if request.signal_age > 60:
            warning_text = f"\n🚨 <b>警告：信号已生成 {request.signal_age:.0f} 秒，市场可能已变化</b>"
        if is_recalculated:
            warning_text = "\n🔄 <b>此为重新计算后的信号，请再次确认</b>"
        
        action_text = "买入" if request.action == "BUY" else "卖出" if request.action == "SELL" else "平仓"
        action_button = f"✅ 确认{action_text}"
        
        keyboard = [
            [
                InlineKeyboardButton(
                    action_button,
                    callback_data=f"approve:{request.id}"
                ),
                InlineKeyboardButton(
                    "❌ 拒绝",
                    callback_data=f"reject:{request.id}"
                ),
            ],
        ]
        
        if request.signal_age > 30:
            keyboard.append([
                InlineKeyboardButton(
                    "⏩ 强制批准",
                    callback_data=f"force:{request.id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton(
                "⏰ 延迟 10 分钟",
                callback_data=f"delay:{request.id}"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = f"""
{title}{warning_text}

<b>操作:</b> <code>{request.action} {request.symbol}</code>
<b>价格:</b> <code>${request.price:,.2f}</code>
<b>数量:</b> <code>{request.quantity}</code>
<b>价值:</b> <code>${request.estimated_value:,.2f}</code>

<b>信号理由:</b>
{request.reason}

⚠️ <b>风险等级:</b> {request.risk_level}
📈 <b>置信度:</b> {request.confidence * 100:.0f}%

⏱️ 请在 {request.timeout_seconds // 60} 分钟内确认
🔢 重试次数: {request.retry_count}/{request.max_retries}
        """
        
        for chat_id in self._chat_ids:
            try:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=message.strip(),
                    parse_mode=self._parse_mode,
                    reply_markup=reply_markup
                )
                logger.info(f"Sent approval message to {chat_id}: {request.id}")
            except Exception as e:
                logger.error(f"Failed to send message to {chat_id}: {e}")
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /start 命令"""
        await update.message.reply_text(
            text="🤖 <b>TradeAgent 审批 Bot</b>\n\n"
                 "可用命令:\n"
                 "/start - 显示此消息\n"
                 "/list - 显示待审批列表\n"
                 "/approve [id] - 批准指定审批\n"
                 "/reject [id] - 拒绝指定审批",
            parse_mode="HTML"
        )
    
    async def _handle_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /list 命令"""
        pending = self._approval_service.get_pending()
        
        if not pending:
            await update.message.reply_text("📭 暂无待审批交易")
            return
        
        message = f"📋 <b>待审批列表</b> ({len(pending)} 条)\n\n"
        
        for i, req in enumerate(pending[:10], 1):
            action_text = "买入" if req.action == "BUY" else "卖出" if req.action == "SELL" else "平仓"
            message += (
                f"{i}. <code>{req.action} {req.symbol}</code>\n"
                f"   💰 价格: ${req.price:,.2f}\n"
                f"   📊 价值: ${req.estimated_value:,.2f}\n"
                f"   ⏱️ ID: {req.id}\n"
                f"   📅 已等待: {req.approval_delay:.0f}s\n\n"
            )
        
        await update.message.reply_text(message.strip(), parse_mode="HTML")
    
    async def _handle_approve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /approve 命令"""
        if not context.args:
            await update.message.reply_text("请提供审批 ID: /approve [id]")
            return
        
        approval_id = context.args[0]
        result = await self._approval_service.approve(
            approval_id,
            approved_by=f"telegram:{update.effective_chat.id}",
            force=False
        )
        
        if result.success:
            await update.message.reply_text(f"✅ 已批准: {approval_id}")
        else:
            await update.message.reply_text(
                f"❌ 批准失败: {result.message}\n"
                f"ID: {approval_id}"
            )
    
    async def _handle_reject_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理 /reject 命令"""
        if not context.args:
            await update.message.reply_text("请提供审批 ID: /reject [id]")
            return
        
        approval_id = context.args[0]
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else ""
        
        success = await self._approval_service.reject(
            approval_id,
            reason=reason,
            rejected_by=f"telegram:{update.effective_chat.id}"
        )
        
        if success:
            await update.message.reply_text(f"❌ 已拒绝: {approval_id}")
        else:
            await update.message.reply_text(f"❌ 拒绝失败: {approval_id}")
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理回调按钮"""
        query = update.callback_query
        await query.answer()
        
        data = query.data.split(":")
        action = data[0]
        approval_id = data[1]
        
        request = self._approval_service.get(approval_id)
        if not request:
            await query.edit_message_text(
                text=f"❌ 审批请求不存在: {approval_id}"
            )
            return
        
        if action == "approve":
            result = await self._approval_service.approve(
                approval_id,
                approved_by=f"telegram:{query.from_user.id}"
            )
            
            if result.success:
                await query.edit_message_text(
                    text=f"✅ <b>已批准交易</b>\n"
                         f"操作: {request.action} {request.symbol}\n"
                         f"价格: ${request.price:,.2f}\n"
                         f"ID: {approval_id}",
                    parse_mode="HTML"
                )
            else:
                if result.needs_recalculation:
                    await query.edit_message_text(
                        text=f"⚠️ <b>需要重新计算</b>\n"
                             f"{result.message}\n"
                             f"ID: {approval_id}",
                        parse_mode="HTML"
                    )
                else:
                    await query.edit_message_text(
                        text=f"❌ <b>批准失败</b>\n{result.message}",
                        parse_mode="HTML"
                    )
        
        elif action == "force":
            result = await self._approval_service.approve(
                approval_id,
                approved_by=f"telegram:{query.from_user.id}",
                force=True
            )
            
            if result.success:
                await query.edit_message_text(
                    text=f"⚡ <b>已强制批准</b>\n"
                         f"操作: {request.action} {request.symbol}\n"
                         f"价格: ${request.price:,.2f}\n"
                         f"ID: {approval_id}",
                    parse_mode="HTML"
                )
        
        elif action == "reject":
            success = await self._approval_service.reject(
                approval_id,
                reason="User rejected via Telegram",
                rejected_by=f"telegram:{query.from_user.id}"
            )
            
            if success:
                await query.edit_message_text(
                    text=f"❌ <b>已拒绝交易</b>\n"
                         f"操作: {request.action} {request.symbol}\n"
                         f"ID: {approval_id}",
                    parse_mode="HTML"
                )
        
        elif action == "delay":
            success = await self._approval_service.delay(
                approval_id,
                additional_seconds=600
            )
            
            if success:
                await query.edit_message_text(
                    text=f"⏰ <b>已延长 10 分钟</b>\n"
                         f"新到期时间: {request.expires_at.strftime('%H:%M:%S')}\n"
                         f"ID: {approval_id}",
                    parse_mode="HTML"
                )


_telegram_bot: Optional[TelegramApprovalBot] = None


def get_telegram_bot(
    approval_service: Optional[ApprovalService] = None
) -> TelegramApprovalBot:
    """获取 Telegram Bot 单例"""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramApprovalBot(approval_service)
    return _telegram_bot


__all__ = [
    "TelegramApprovalBot",
    "get_telegram_bot",
]
