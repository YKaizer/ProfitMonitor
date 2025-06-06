from aiogram.fsm.state import State, StatesGroup

class CommentState(StatesGroup):
    waiting_for_note = State()

class AddServerState(StatesGroup):
    waiting_for_ip = State()
    waiting_for_name = State()
