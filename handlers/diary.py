from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from db import db
from utils.visuals import visualizer
import json

MOOD, SLEEP, ENERGY, TEXT = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Добавить запись", callback_data="add_entry")],
        [InlineKeyboardButton("📊 Просмотреть за 7 дней", callback_data="view_week")],
        [InlineKeyboardButton("📈 График настроения", callback_data="chart_mood")],
        [InlineKeyboardButton("😴 Сон и энергия", callback_data="chart_sleep")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Привет! Я бот для ведения дневника.\nВыбери действие:",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "add_entry":
        await query.edit_message_text("Оцените настроение от 1 до 10:")
        return MOOD
    elif query.data == "view_week":
        entries = db.get_entries(query.from_user.id, days=7)
        if not entries:
            await query.edit_message_text("Записей пока нет.")
            return ConversationHandler.END
        text = "Последние записи:\n\n"
        for e in entries:
            text += f"📅 {e['date']}\n"
            if e['mood']: text += f"  Настроение: {e['mood']}/10\n"
            if e['sleep_hours']: text += f"  Сон: {e['sleep_hours']} ч\n"
            if e['energy']: text += f"  Энергия: {e['energy']}/10\n"
            if e['text']: text += f"  {e['text']}\n"
            text += "\n"
        await query.edit_message_text(text)
        return ConversationHandler.END
    elif query.data == "chart_mood":
        entries = db.get_entries_by_date_range(query.from_user.id, 
                                               entries := db.get_entries(query.from_user.id, 30) and 
                                               min([e['date'] for e in db.get_entries(query.from_user.id, 30)]) or 
                                               __import__('datetime').datetime.now().strftime('%Y-%m-%d'),
                                               __import__('datetime').datetime.now().strftime('%Y-%m-%d'))
        entries = list(reversed(db.get_entries(query.from_user.id, 30)))
        path = visualizer.plot_mood(entries, query.from_user.id)
        if path:
            await query.message.reply_photo(photo=open(path, 'rb'))
        else:
            await query.edit_message_text("Недостаточно данных для графика.")
        return ConversationHandler.END
    elif query.data == "chart_sleep":
        entries = list(reversed(db.get_entries(query.from_user.id, 30)))
        path = visualizer.plot_sleep_energy(entries, query.from_user.id)
        if path:
            await query.message.reply_photo(photo=open(path, 'rb'))
        else:
            await query.edit_message_text("Недостаточно данных для графика.")
        return ConversationHandler.END

async def mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        mood_val = int(update.message.text)
        if not 1 <= mood_val <= 10:
            await update.message.reply_text("Введите число от 1 до 10")
            return MOOD
        context.user_data['mood'] = mood_val
        await update.message.reply_text("Сколько часов спали? (можно пропустить, отправьте -)")
        return SLEEP
    except ValueError:
        await update.message.reply_text("Введите число от 1 до 10")
        return MOOD

async def sleep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '-':
        context.user_data['sleep_hours'] = None
    else:
        try:
            context.user_data['sleep_hours'] = float(text)
        except ValueError:
            await update.message.reply_text("Введите число или '-' для пропуска")
            return SLEEP
    await update.message.reply_text("Оцените энергию от 1 до 10? (можно пропустить, отправьте -)")
    return ENERGY

async def energy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '-':
        context.user_data['energy'] = None
    else:
        try:
            energy_val = int(text)
            if not 1 <= energy_val <= 10:
                await update.message.reply_text("Введите число от 1 до 10 или '-' для пропуска")
                return ENERGY
            context.user_data['energy'] = energy_val
        except ValueError:
            await update.message.reply_text("Введите число от 1 до 10 или '-' для пропуска")
            return ENERGY
    await update.message.reply_text("Добавьте заметку о дне? (можно пропустить, отправьте -)")
    return TEXT

async def text_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '-':
        text = None
    db.add_entry(
        user_id=update.effective_user.id,
        mood=context.user_data.get('mood'),
        sleep_hours=context.user_data.get('sleep_hours'),
        energy=context.user_data.get('energy'),
        text=text
    )
    await update.message.reply_text("Запись сохранена! ✅")
    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено", reply_markup=ReplyKeyboardRemove())
    context.user_data.clear()
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(button_handler, pattern="^add_entry$")],
    states={
        MOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, mood)],
        SLEEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, sleep)],
        ENERGY: [MessageHandler(filters.TEXT & ~filters.COMMAND, energy)],
        TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_entry)],
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
