from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.handlers import common

router = Router()

HELP = (
    "🏋️ <b>Спортивный дневник</b>\n\n"
    "Записывай данные кнопками внизу. Всё сохраняется за активный день "
    "и раскладывается в отчётный чат по темам.\n\n"
    "<b>Кнопки:</b>\n"
    "😴 Сон — пробуждение, засыпание, качество 1–10\n"
    "⚖️ Вес — утренний вес\n"
    "💪 Тренировка — упражнения и бассейн (ЛФК и висы тоже пиши сюда)\n"
    "🧗 Лазание — категория, затем флеш / не флеш / не залез\n"
    "🤸 Висы — зацепки и отягощение (дублируются в тренировку)\n"
    "🍽 Питание — продукты, белок считается сам (протеин — тоже еда)\n"
    "💊 Добавки — креатин, коллаген и др. (тумблеры)\n"
    "👟 Шаги\n"
    "📋 Сводка дня · 📊 Статистика · 📤 В отчёт · 📅 День\n\n"
    "<b>Можно и просто писать строками:</b>\n"
    "<code>7:30</code> — пробуждение\n"
    "<code>Сон 7/10</code> — качество сна\n"
    "<code>78.1</code> — вес\n"
    "<code>Сон 00:30</code> — время засыпания\n"
    "<code>Творог 250г, кешью 20г</code> — еда (посчитаю белок)\n"
    "<code>Велик 30мин</code> — тренировка\n"
    "<code>Лфк с лентой</code> — ЛФК (в тренировку и в топик ЛФК)\n"
    "<code>5х6а</code> — 5 трасс 6а на флеш; <code>6б не залез 4</code>; <code>7а с 7 попытки</code>\n"
    "<code>Висы 10мм 10кг 5х10/50</code> — висы на зацепках\n"
    "<code>Шаги 15к</code> — шаги\n"
    "<code>Креатин, коллаген</code> — добавки (связки/суставы)\n"
    "<code>Басс 1 час</code> — бассейн\n"
    "<code>Настроение 8/10</code>, <code>Пульс 55</code>, <code>Вода 2л</code> — доп. метрики\n\n"
    "<b>Команды:</b>\n"
    "/menu — показать меню\n"
    "/day — какой день активен (сменить: <code>/day 05.11</code>)\n"
    "/today — вернуться к сегодняшнему дню\n"
    "/log — список строк активного дня\n"
    "/del N — удалить строку №N\n"
    "/undo — удалить последнюю строку\n"
    "/view — сводка за день\n"
    "/last — последние дни с записями\n"
    "/stats — графики и аналитика\n"
    "/publish — выложить графики в отчётный чат\n"
    "/report — отправить сводку дня в отчётный чат\n"
    "/get_chat_info — узнать ID чата и топика\n"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(HELP, parse_mode="HTML", reply_markup=common.main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP, parse_mode="HTML", reply_markup=common.main_keyboard())


@router.message(Command("get_chat_info", "id", "chatid"))
async def cmd_get_chat_info(message: Message):
    chat = message.chat
    thread_id = message.message_thread_id

    lines = ["ℹ️ <b>Информация о чате</b>\n"]
    lines.append(f"<b>ID чата:</b> <code>{chat.id}</code>")
    lines.append(f"<b>Тип:</b> {chat.type}")
    if chat.title:
        lines.append(f"<b>Название:</b> {chat.title}")
    if getattr(chat, "is_forum", False):
        lines.append("<b>Форум:</b> да")
    if thread_id:
        lines.append(f"<b>ID топика (thread_id):</b> <code>{thread_id}</code>")
    else:
        lines.append("<b>Топик:</b> нет")

    lines.append("\n<b>Что прописать в .env:</b>")
    if chat.type == "private":
        lines.append(f"<code>MAIN_CHAT_ID={chat.id}</code>")
    else:
        lines.append(f"<code>REPORT_CHAT_ID={chat.id}</code>")
        if thread_id:
            lines.append("А это — ID топика, вставь в нужный <code>TOPIC_*_ID</code>:")
            lines.append(f"<code>{thread_id}</code>")

    lines.append(f"\n<b>Ваш user_id:</b> <code>{message.from_user.id}</code>")
    lines.append("<code>ADMIN_IDS=" + str(message.from_user.id) + "</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")
