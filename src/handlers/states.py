from aiogram.fsm.state import State, StatesGroup


class EntryStates(StatesGroup):
    """Состояния пошагового ввода данных через кнопки."""

    sleep_time = State()
    sleep_quality = State()
    weight = State()
    steps = State()
    exercise = State()
    climb_count = State()
    climb_text = State()
    hang_weight = State()
    hang_text = State()
    food = State()
    lfk = State()
    day_input = State()
