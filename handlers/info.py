from telegram import Update
from telegram.ext import ContextTypes
from utils.access import restricted


@restricted
async def get_chat_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.effective_message

    lines = []
    lines.append(f"👤 Твой user_id: {user.id}")
    lines.append(f"💬 ID чата: {chat.id}")
    lines.append(f"ℹ️ Тип чата: {chat.type}")

    if chat.type == "private":
        lines.append("")
        lines.append("Это личный чат с ботом.")
        await msg.reply_text("\n".join(lines))
        return

    if getattr(chat, "is_forum", False):
        lines.append("📌 Это чат с включёнными топиками (форум).")
    else:
        lines.append("📌 Обычная супергруппа/группа.")

    thread_id = getattr(msg, "message_thread_id", None)
    if thread_id:
        lines.append("")
        lines.append(f"🧵 ID топика (message_thread_id): {thread_id}")
        lines.append("Этот ID копируй в .env как TOPIC_*_ID")
    else:
        lines.append("")
        lines.append("🧵 message_thread_id не найден.")
        lines.append("Если это форум — напиши команду /id ПРЯМО внутри нужного топика.")

    lines.append("")
    lines.append("Для .env:")
    lines.append(f"REPORT_CHAT_ID={chat.id}")

    await msg.reply_text("\n".join(lines))
