from aiogram.fsm.state import State, StatesGroup


class AddKeywordState(StatesGroup):
    waiting_for_text = State()
