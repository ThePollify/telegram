from aiogram.dispatcher.filters.state import State, StatesGroup


class CodeState(StatesGroup):
    wait_code = State()


class AnswersState(StatesGroup):
    wait_question = State()
    wait_slider_value = State()
    wait_top_list_rank = State()

    selector = State()
    slider = State()
    top_list = State()
    text = State()
