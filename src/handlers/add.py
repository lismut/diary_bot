from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import date
from src.db.base import async_session
from src.db import crud
from src.utils.helpers import get_date_from_text, format_date_russian, load_routines_config, calculate_protein
from src.services.reporter import ReportService

router = Router()


class AddData(StatesGroup):
    choosing_date = State()
    sleep_wake = State()
    sleep_bed = State()
    sleep_quality = State()
    weight = State()
    steps = State()
    add_exercise = State()
    exercise_name = State()
    exercise_sets = State()
    exercise_reps = State()
    exercise_weight = State()
    add_climbing = State()
    climbing_name = State()
    climbing_grade = State()
    climbing_attempts = State()
    add_hang = State()
    hang_hold = State()
    hang_weight = State()
    hang_duration = State()
    hang_sets = State()
    add_meal = State()
    meal_name = State()
    meal_amount = State()
    meal_type = State()
    routines = State()
    more = State()


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сегодня", callback_data="date_today")],
        [InlineKeyboardButton(text="Вчера", callback_data="date_yesterday")],
        [InlineKeyboardButton(text="Указать дату", callback_data="date_custom")],
    ])
    await message.answer("За какой день добавить данные?", reply_markup=kb)
    await state.set_state(AddData.choosing_date)


@router.callback_query(F.data.startswith("date_"))
async def choose_date(callback: CallbackQuery, state: FSMContext):
    from datetime import timedelta
    today = date.today()
    if callback.data == "date_today":
        chosen_date = today
    elif callback.data == "date_yesterday":
        chosen_date = today - timedelta(days=1)
    else:
        await callback.message.answer("Введи дату в формате ДД.ММ.ГГГГ или ДД.ММ")
        await state.set_state(AddData.choosing_date)
        await callback.answer()
        return
    
    await state.update_data(chosen_date=chosen_date.isoformat())
    await callback.message.answer(f"День: {format_date_russian(chosen_date)}\n\nНачинаем ввод. Пропусти любой пункт, написав '-'")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_sleep")]
    ])
    await callback.message.answer("Время пробуждения (например, 07:30):", reply_markup=kb)
    await state.set_state(AddData.sleep_wake)
    await callback.answer()


@router.message(AddData.choosing_date)
async def custom_date(message: Message, state: FSMContext):
    chosen_date = get_date_from_text(message.text)
    await state.update_data(chosen_date=chosen_date.isoformat())
    await message.answer(f"День: {format_date_russian(chosen_date)}\n\nНачинаем ввод. Пропусти любой пункт, написав '-'")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_sleep")]
    ])
    await message.answer("Время пробуждения (например, 07:30):", reply_markup=kb)
    await state.set_state(AddData.sleep_wake)


@router.message(AddData.sleep_wake)
async def sleep_wake(message: Message, state: FSMContext):
    if message.text.strip() != '-':
        await state.update_data(wake_up=message.text.strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_bed")]
    ])
    await message.answer("Время засыпания (например, 23:00):", reply_markup=kb)
    await state.set_state(AddData.sleep_bed)


@router.callback_query(F.data == "skip_sleep")
async def skip_sleep(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_bed")]
    ])
    await callback.message.answer("Время засыпания (например, 23:00):", reply_markup=kb)
    await state.set_state(AddData.sleep_bed)
    await callback.answer()


@router.message(AddData.sleep_bed)
async def sleep_bed(message: Message, state: FSMContext):
    if message.text.strip() != '-':
        await state.update_data(sleep_time=message.text.strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_quality")]
    ])
    await message.answer("Качество сна 1-10:", reply_markup=kb)
    await state.set_state(AddData.sleep_quality)


@router.callback_query(F.data == "skip_bed")
async def skip_bed(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_quality")]
    ])
    await callback.message.answer("Качество сна 1-10:", reply_markup=kb)
    await state.set_state(AddData.sleep_quality)
    await callback.answer()


@router.message(AddData.sleep_quality)
async def sleep_quality(message: Message, state: FSMContext):
    if message.text.strip() != '-':
        try:
            q = int(message.text.strip())
            await state.update_data(sleep_quality=q)
        except:
            pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_weight")]
    ])
    await message.answer("Утренний вес (кг):", reply_markup=kb)
    await state.set_state(AddData.weight)


@router.callback_query(F.data == "skip_quality")
async def skip_quality(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_weight")]
    ])
    await callback.message.answer("Утренний вес (кг):", reply_markup=kb)
    await state.set_state(AddData.weight)
    await callback.answer()


@router.message(AddData.weight)
async def weight_msg(message: Message, state: FSMContext):
    if message.text.strip() != '-':
        try:
            w = float(message.text.strip().replace(',', '.'))
            await state.update_data(weight=w)
        except:
            pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_steps")]
    ])
    await message.answer("Количество шагов за день:", reply_markup=kb)
    await state.set_state(AddData.steps)


@router.callback_query(F.data == "skip_weight")
async def skip_weight(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_steps")]
    ])
    await callback.message.answer("Количество шагов за день:", reply_markup=kb)
    await state.set_state(AddData.steps)
    await callback.answer()


@router.message(AddData.steps)
async def steps_msg(message: Message, state: FSMContext):
    if message.text.strip() != '-':
        try:
            s = int(message.text.strip())
            await state.update_data(steps=s)
        except:
            pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_ex_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_ex_no")],
    ])
    await message.answer("Была ли тренировка (упражнения)?", reply_markup=kb)
    await state.set_state(AddData.add_exercise)


@router.callback_query(F.data == "skip_steps")
async def skip_steps(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_ex_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_ex_no")],
    ])
    await callback.message.answer("Была ли тренировка (упражнения)?", reply_markup=kb)
    await state.set_state(AddData.add_exercise)
    await callback.answer()


@router.callback_query(F.data == "add_ex_yes")
async def add_ex_yes(callback: CallbackQuery, state: FSMContext):
    await state.update_data(exercises=[])
    await callback.message.answer("Название упражнения:")
    await state.set_state(AddData.exercise_name)
    await callback.answer()


@router.callback_query(F.data == "add_ex_no")
async def add_ex_no(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_climb_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_climb_no")],
    ])
    await callback.message.answer("Был ли скалодром?", reply_markup=kb)
    await state.set_state(AddData.add_climbing)
    await callback.answer()


@router.message(AddData.exercise_name)
async def ex_name(message: Message, state: FSMContext):
    await state.update_data(current_ex_name=message.text.strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_ex_sets")]
    ])
    await message.answer("Подходы:", reply_markup=kb)
    await state.set_state(AddData.exercise_sets)


@router.callback_query(F.data == "skip_ex_sets")
async def skip_ex_sets(callback: CallbackQuery, state: FSMContext):
    await state.update_data(current_ex_sets=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_ex_reps")]
    ])
    await callback.message.answer("Повторения:", reply_markup=kb)
    await state.set_state(AddData.exercise_reps)
    await callback.answer()


@router.message(AddData.exercise_sets)
async def ex_sets(message: Message, state: FSMContext):
    try:
        await state.update_data(current_ex_sets=int(message.text.strip()))
    except:
        await state.update_data(current_ex_sets=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_ex_reps")]
    ])
    await message.answer("Повторения:", reply_markup=kb)
    await state.set_state(AddData.exercise_reps)


@router.callback_query(F.data == "skip_ex_reps")
async def skip_ex_reps(callback: CallbackQuery, state: FSMContext):
    await state.update_data(current_ex_reps=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_ex_weight")]
    ])
    await callback.message.answer("Вес (кг):", reply_markup=kb)
    await state.set_state(AddData.exercise_weight)
    await callback.answer()


@router.message(AddData.exercise_reps)
async def ex_reps(message: Message, state: FSMContext):
    try:
        await state.update_data(current_ex_reps=int(message.text.strip()))
    except:
        await state.update_data(current_ex_reps=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_ex_weight")]
    ])
    await message.answer("Вес (кг):", reply_markup=kb)
    await state.set_state(AddData.exercise_weight)


@router.callback_query(F.data == "skip_ex_weight")
async def skip_ex_weight(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    exercises = data.get('exercises', [])
    exercises.append({
        'name': data['current_ex_name'],
        'sets': data.get('current_ex_sets'),
        'reps': data.get('current_ex_reps'),
        'weight': None
    })
    await state.update_data(exercises=exercises)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ещё упражнение", callback_data="add_another_ex")],
        [InlineKeyboardButton(text="Готово", callback_data="ex_done")],
    ])
    await callback.message.answer("Добавлено. Что дальше?", reply_markup=kb)
    await state.set_state(AddData.more)
    await callback.answer()


@router.message(AddData.exercise_weight)
async def ex_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.strip().replace(',', '.'))
        await state.update_data(current_ex_weight=w)
    except:
        await state.update_data(current_ex_weight=None)
    data = await state.get_data()
    exercises = data.get('exercises', [])
    exercises.append({
        'name': data['current_ex_name'],
        'sets': data.get('current_ex_sets'),
        'reps': data.get('current_ex_reps'),
        'weight': data.get('current_ex_weight')
    })
    await state.update_data(exercises=exercises)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ещё упражнение", callback_data="add_another_ex")],
        [InlineKeyboardButton(text="Готово", callback_data="ex_done")],
    ])
    await message.answer("Добавлено. Что дальше?", reply_markup=kb)
    await state.set_state(AddData.more)


@router.callback_query(F.data == "add_another_ex")
async def add_another_ex(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Название упражнения:")
    await state.set_state(AddData.exercise_name)
    await callback.answer()


@router.callback_query(F.data == "ex_done")
async def ex_done(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_climb_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_climb_no")],
    ])
    await callback.message.answer("Был ли скалодром?", reply_markup=kb)
    await state.set_state(AddData.add_climbing)
    await callback.answer()


@router.callback_query(F.data == "add_climb_yes")
async def add_climb_yes(callback: CallbackQuery, state: FSMContext):
    await state.update_data(climbs=[])
    await callback.message.answer("Название/описание трассы (или просто Enter для пропуска):")
    await state.set_state(AddData.climbing_name)
    await callback.answer()


@router.callback_query(F.data == "add_climb_no")
async def add_climb_no(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_hang_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_hang_no")],
    ])
    await callback.message.answer("Были ли висы на зацепках?", reply_markup=kb)
    await state.set_state(AddData.add_hang)
    await callback.answer()


@router.message(AddData.climbing_name)
async def climb_name(message: Message, state: FSMContext):
    await state.update_data(current_climb_name=message.text.strip() if message.text.strip() != '-' else None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_climb_grade")]
    ])
    await message.answer("Категория сложности (например, 6B, 7a):", reply_markup=kb)
    await state.set_state(AddData.climbing_grade)


@router.callback_query(F.data == "skip_climb_grade")
async def skip_climb_grade(callback: CallbackQuery, state: FSMContext):
    await state.update_data(current_climb_grade=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_climb_attempts")]
    ])
    await callback.message.answer("Количество попыток:", reply_markup=kb)
    await state.set_state(AddData.climbing_attempts)
    await callback.answer()


@router.message(AddData.climbing_grade)
async def climb_grade(message: Message, state: FSMContext):
    if message.text.strip() != '-':
        await state.update_data(current_climb_grade=message.text.strip())
    else:
        await state.update_data(current_climb_grade=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_climb_attempts")]
    ])
    await message.answer("Количество попыток:", reply_markup=kb)
    await state.set_state(AddData.climbing_attempts)


@router.callback_query(F.data == "skip_climb_attempts")
async def skip_climb_attempts(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    climbs = data.get('climbs', [])
    climbs.append({
        'name': data.get('current_climb_name'),
        'grade': data.get('current_climb_grade'),
        'attempts': None
    })
    await state.update_data(climbs=climbs)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ещё трассу", callback_data="add_another_climb")],
        [InlineKeyboardButton(text="Готово", callback_data="climb_done")],
    ])
    await callback.message.answer("Добавлено. Что дальше?", reply_markup=kb)
    await state.set_state(AddData.more)
    await callback.answer()


@router.message(AddData.climbing_attempts)
async def climb_attempts(message: Message, state: FSMContext):
    try:
        attempts = int(message.text.strip())
        await state.update_data(current_climb_attempts=attempts)
    except:
        await state.update_data(current_climb_attempts=None)
    data = await state.get_data()
    climbs = data.get('climbs', [])
    climbs.append({
        'name': data.get('current_climb_name'),
        'grade': data.get('current_climb_grade'),
        'attempts': data.get('current_climb_attempts')
    })
    await state.update_data(climbs=climbs)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ещё трассу", callback_data="add_another_climb")],
        [InlineKeyboardButton(text="Готово", callback_data="climb_done")],
    ])
    await message.answer("Добавлено. Что дальше?", reply_markup=kb)
    await state.set_state(AddData.more)


@router.callback_query(F.data == "add_another_climb")
async def add_another_climb(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Название/описание трассы:")
    await state.set_state(AddData.climbing_name)
    await callback.answer()


@router.callback_query(F.data == "climb_done")
async def climb_done(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_hang_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_hang_no")],
    ])
    await callback.message.answer("Были ли висы на зацепках?", reply_markup=kb)
    await state.set_state(AddData.add_hang)
    await callback.answer()


@router.callback_query(F.data == "add_hang_yes")
async def add_hang_yes(callback: CallbackQuery, state: FSMContext):
    await state.update_data(hangs=[])
    await callback.message.answer("Размер зацепки:")
    await state.set_state(AddData.hang_hold)
    await callback.answer()


@router.callback_query(F.data == "add_hang_no")
async def add_hang_no(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_meal_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_meal_no")],
    ])
    await callback.message.answer("Добавить приемы пищи?", reply_markup=kb)
    await state.set_state(AddData.add_meal)
    await callback.answer()


@router.message(AddData.hang_hold)
async def hang_hold(message: Message, state: FSMContext):
    await state.update_data(current_hang_hold=message.text.strip())
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_hang_weight")]
    ])
    await message.answer("Вес с отягощением (кг), или тело:", reply_markup=kb)
    await state.set_state(AddData.hang_weight)


@router.callback_query(F.data == "skip_hang_weight")
async def skip_hang_weight(callback: CallbackQuery, state: FSMContext):
    await state.update_data(current_hang_weight=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_hang_duration")]
    ])
    await callback.message.answer("Длительность висa (сек):", reply_markup=kb)
    await state.set_state(AddData.hang_duration)
    await callback.answer()


@router.message(AddData.hang_weight)
async def hang_weight(message: Message, state: FSMContext):
    try:
        w = float(message.text.strip().replace(',', '.'))
        await state.update_data(current_hang_weight=w)
    except:
        await state.update_data(current_hang_weight=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_hang_duration")]
    ])
    await message.answer("Длительность висa (сек):", reply_markup=kb)
    await state.set_state(AddData.hang_duration)


@router.callback_query(F.data == "skip_hang_duration")
async def skip_hang_duration(callback: CallbackQuery, state: FSMContext):
    await state.update_data(current_hang_duration=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_hang_sets")]
    ])
    await callback.message.answer("Количество подходов:", reply_markup=kb)
    await state.set_state(AddData.hang_sets)
    await callback.answer()


@router.message(AddData.hang_duration)
async def hang_duration(message: Message, state: FSMContext):
    try:
        d = int(message.text.strip())
        await state.update_data(current_hang_duration=d)
    except:
        await state.update_data(current_hang_duration=None)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_hang_sets")]
    ])
    await message.answer("Количество подходов:", reply_markup=kb)
    await state.set_state(AddData.hang_sets)


@router.callback_query(F.data == "skip_hang_sets")
async def skip_hang_sets(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    hangs = data.get('hangs', [])
    hangs.append({
        'hold_size': data['current_hang_hold'],
        'weight': data.get('current_hang_weight'),
        'duration_seconds': data.get('current_hang_duration'),
        'sets': None
    })
    await state.update_data(hangs=hangs)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ещё вис", callback_data="add_another_hang")],
        [InlineKeyboardButton(text="Готово", callback_data="hang_done")],
    ])
    await callback.message.answer("Добавлено. Что дальше?", reply_markup=kb)
    await state.set_state(AddData.more)
    await callback.answer()


@router.message(AddData.hang_sets)
async def hang_sets(message: Message, state: FSMContext):
    try:
        s = int(message.text.strip())
        await state.update_data(current_hang_sets=s)
    except:
        await state.update_data(current_hang_sets=None)
    data = await state.get_data()
    hangs = data.get('hangs', [])
    hangs.append({
        'hold_size': data['current_hang_hold'],
        'weight': data.get('current_hang_weight'),
        'duration_seconds': data.get('current_hang_duration'),
        'sets': data.get('current_hang_sets')
    })
    await state.update_data(hangs=hangs)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ещё вис", callback_data="add_another_hang")],
        [InlineKeyboardButton(text="Готово", callback_data="hang_done")],
    ])
    await message.answer("Добавлено. Что дальше?", reply_markup=kb)
    await state.set_state(AddData.more)


@router.callback_query(F.data == "add_another_hang")
async def add_another_hang(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Размер зацепки:")
    await state.set_state(AddData.hang_hold)
    await callback.answer()


@router.callback_query(F.data == "hang_done")
async def hang_done(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data="add_meal_yes")],
        [InlineKeyboardButton(text="Нет", callback_data="add_meal_no")],
    ])
    await callback.message.answer("Добавить приемы пищи?", reply_markup=kb)
    await state.set_state(AddData.add_meal)
    await callback.answer()


@router.callback_query(F.data == "add_meal_yes")
async def add_meal_yes(callback: CallbackQuery, state: FSMContext):
    await state.update_data(meals=[])
    await callback.message.answer("Что ел? (название продукта):")
    await state.set_state(AddData.meal_name)
    await callback.answer()


@router.callback_query(F.data == "add_meal_no")
async def add_meal_no(callback: CallbackQuery, state: FSMContext):
    await ask_routines(callback.message, state)


@router.message(AddData.meal_name)
async def meal_name(message: Message, state: FSMContext):
    await state.update_data(current_meal_name=message.text.strip())
    await message.answer("Количество в граммах:")
    await state.set_state(AddData.meal_amount)


@router.message(AddData.meal_amount)
async def meal_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(',', '.'))
        await state.update_data(current_meal_amount=amount)
    except:
        amount = 0
        await state.update_data(current_meal_amount=amount)
    data = await state.get_data()
    protein = calculate_protein(data['current_meal_name'], amount)
    meals = data.get('meals', [])
    meals.append({
        'name': data['current_meal_name'],
        'amount': amount,
        'protein': protein
    })
    await state.update_data(meals=meals)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить ещё", callback_data="add_another_meal")],
        [InlineKeyboardButton(text="Готово", callback_data="meal_done")],
    ])
    await message.answer(f"Добавлено (+{protein}г белка). Что дальше?", reply_markup=kb)
    await state.set_state(AddData.more)


@router.callback_query(F.data == "add_another_meal")
async def add_another_meal(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Что ел? (название продукта):")
    await state.set_state(AddData.meal_name)
    await callback.answer()


@router.callback_query(F.data == "meal_done")
async def meal_done(callback: CallbackQuery, state: FSMContext):
    await ask_routines(callback.message, state)


async def ask_routines(message: Message, state: FSMContext):
    routines_cfg = load_routines_config()
    routines = routines_cfg.get('routines', [])
    if not routines:
        await finish_add(message, state)
        return
    kb_buttons = []
    for r in routines:
        kb_buttons.append([InlineKeyboardButton(text=f"☐ {r}", callback_data=f"routine_toggle:{r}:off")])
    kb_buttons.append([InlineKeyboardButton(text="Готово", callback_data="routines_done")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer("Отметь выполненные рутины/добавки:", reply_markup=kb)
    await state.set_state(AddData.routines)
    await state.update_data(routines_status={})


@router.callback_query(F.data.startswith("routine_toggle:"))
async def toggle_routine(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(':')
    routine = parts[1]
    status = parts[2]
    data = await state.get_data()
    routines_status = data.get('routines_status', {})
    if status == 'off':
        routines_status[routine] = True
        new_status = 'on'
        new_text = f"☑️ {routine}"
    else:
        routines_status[routine] = False
        new_status = 'off'
        new_text = f"☐ {routine}"
    await state.update_data(routines_status=routines_status)
    
    routines_cfg = load_routines_config()
    routines = routines_cfg.get('routines', [])
    kb_buttons = []
    for r in routines:
        if routines_status.get(r):
            kb_buttons.append([InlineKeyboardButton(text=f"☑️ {r}", callback_data=f"routine_toggle:{r}:on")])
        else:
            kb_buttons.append([InlineKeyboardButton(text=f"☐ {r}", callback_data=f"routine_toggle:{r}:off")])
    kb_buttons.append([InlineKeyboardButton(text="Готово", callback_data="routines_done")])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "routines_done")
async def routines_done(callback: CallbackQuery, state: FSMContext):
    await finish_add(callback.message, state)
    await callback.answer()


async def finish_add(message: Message, state: FSMContext, bot: Bot = None):
    data = await state.get_data()
    chosen_date_str = data['chosen_date']
    from datetime import date as date_cls
    chosen_date = date_cls.fromisoformat(chosen_date_str)
    
    async with async_session() as session:
        # Save sleep
        if data.get('wake_up') or data.get('sleep_time') or data.get('sleep_quality'):
            await crud.update_sleep(session, chosen_date, data.get('wake_up'), data.get('sleep_time'), data.get('sleep_quality'))
        
        # Save weight
        if data.get('weight'):
            await crud.update_weight(session, chosen_date, data.get('weight'))
        
        # Save steps
        if data.get('steps'):
            await crud.update_steps(session, chosen_date, data.get('steps'))
        
        # Save exercises
        for ex in data.get('exercises', []):
            await crud.add_exercise(session, chosen_date, ex['name'], ex.get('sets'), ex.get('reps'), ex.get('weight'))
        
        # Save climbs
        for climb in data.get('climbs', []):
            await crud.add_climbing_route(session, chosen_date, climb.get('name'), climb.get('grade'), climb.get('attempts'))
        
        # Save hangs
        for hang in data.get('hangs', []):
            await crud.add_hang(session, chosen_date, hang['hold_size'], hang.get('weight'), hang.get('duration_seconds'), hang.get('sets'))
        
        # Save meals
        for meal in data.get('meals', []):
            await crud.add_meal(session, chosen_date, meal['name'], meal['amount'], 'snack', meal['protein'])
        
        # Save routines
        routines_status = data.get('routines_status', {})
        for routine_name, completed in routines_status.items():
            if completed:
                await crud.set_routine(session, chosen_date, routine_name, True)
        
        # Get full day record for posting
        day_record = await crud.get_day(session, chosen_date)
        # Reload with relations
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        result = await session.execute(select(crud.models.DayRecord).options(
            selectinload(crud.models.DayRecord.exercises),
            selectinload(crud.models.DayRecord.climbing_routes),
            selectinload(crud.models.DayRecord.hangs),
            selectinload(crud.models.DayRecord.meals),
            selectinload(crud.models.DayRecord.routines)
        ).where(crud.models.DayRecord.date == chosen_date))
        day_record = result.scalar_one()
    
    await message.answer(f"✅ Данные за {format_date_russian(chosen_date)} сохранены!")
    
    # Post to report chat if bot available
    if bot:
        reporter = ReportService(bot)
        try:
            await reporter.post_day_summary(day_record)
        except Exception as e:
            print(f"Failed to post report: {e}")
    
    await state.clear()
