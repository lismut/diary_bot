from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps
from config import ALLOWED_USERS


def restricted(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return
        if ALLOWED_USERS and user.id not in ALLOWED_USERS:
            if update.message:
                await update.message.reply_text("Доступ запрещён. Этот бот только для владельца.")
            elif update.callback_query:
                await update.callback_query.answer("Доступ запрещён", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper


def is_allowed(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS