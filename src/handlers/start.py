from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from src.config import settings

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "🏋️ <b>Спортивный дневник</b>\n\n"
        "Я буду помогать вести твой спортивный дневник.\n\n"
        "<b>Команды:</b>\n"
        "/add - Добавить данные за день\n"
        "/edit - Редактировать данные за день\n"
        "/view - Просмотреть данные за день\n"
        "/stats - Статистика и графики\n"
        "/get_chat_info - Узнать ID чатов и топиков\n"
        "/help - Справка",
        parse_mode='HTML'
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "<b>Как пользоваться:</b>\n\n"
        "1. <b>/add</b> - пошаговый ввод данных за выбранный день\n"
        "2. <b>/edit</b> - изменить уже введенные данные\n"
        "3. <b>/view</b> - посмотреть что записано за день\n"
        "4. <b>/stats</b> - графики и аналитика за неделю/месяц/год\n"
        "5. <b>/get_chat_info</b> - получить ID текущего чата, форума и топиков\n\n"
        "Бот будет автоматически постить отчеты в настроенный отчетный чат по топикам.",
        parse_mode='HTML'
    )


@router.message(Command("get_chat_info"))
async def cmd_get_chat_info(message: Message):
    chat = message.chat
    thread_id = message.message_thread_id
    
    info = f"ℹ️ <b>Информация о чате</b>\n\n"
    info += f"<b>ID чата:</b> <code>{chat.id}</code>\n"
    info += f"<b>Тип чата:</b> {chat.type}\n"
    if chat.title:
        info += f"<b>Название:</b> {chat.title}\n"
    if thread_id:
        info += f"<b>ID топика (thread_id):</b> <code>{thread_id}</code>\n"
        info += f"<b>Топик:</b> Да (форум)\n"
    else:
        info += f"<b>Топик:</b> Нет\n"
    
    info += f"\n<b>Для настройки в .env:</b>\n"
    if chat.type == 'private':
        info += f"MAIN_CHAT_ID={chat.id}\n"
    elif chat.type in ['group', 'supergroup']:
        if thread_id:
            info += f"REPORT_CHAT_ID={chat.id}\n"
            info += f"# Текущий топик - добавь в соответствующий TOPIC_*_ID\n"
        else:
            info += f"REPORT_CHAT_ID={chat.id}\n"
    
    await message.answer(info, parse_mode='HTML')
