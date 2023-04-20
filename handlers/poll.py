from asyncio import Queue, Task
from html import escape
from json import loads
from uuid import UUID

from aiogram.dispatcher import FSMContext
from aiogram.types import (
    CallbackQuery,
    ContentType,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.callback_data import CallbackData

import api
import models
from bot import bot, dp
from commands import answers_state_commands, target_scope
from states import AnswersState

option_callback_data = CallbackData("option", "index")
change_question_callback_data = CallbackData("change", "action")
exit_callback_data = CallbackData("exit")
cancel_callback_data = CallbackData("cancel")

delete_callback_data = CallbackData("delete", "index")
add_callback_data = CallbackData("add")
send_callback_data = CallbackData("send")

change_question_buttons = InlineKeyboardMarkup().row(
    InlineKeyboardButton(
        "Stay on the current question",
        callback_data=change_question_callback_data.new(action="cancel"),
    ),
    InlineKeyboardButton(
        "Go to next question",
        callback_data=change_question_callback_data.new(action="accept"),
    ),
)
exit_buttons = InlineKeyboardMarkup().row(
    InlineKeyboardButton(
        "Exit from presentation",
        callback_data=exit_callback_data.new(),
    )
)
cancel_buttons = InlineKeyboardMarkup().row(
    InlineKeyboardButton(
        "Cancel",
        callback_data=cancel_callback_data.new(),
    )
)

add_button = InlineKeyboardButton(
    "+",
    callback_data=add_callback_data.new(),
)
send_button = InlineKeyboardButton(
    "Send",
    callback_data=send_callback_data.new(),
)

questions_pull: dict[int, tuple[Queue[models.poll.Question], Task[None]]] = {}


class QuestionModel(models.BaseModel):
    data: models.poll.Question


async def start_answers_state(
    poll_id: int,
    msg: Message,
    state: FSMContext,
) -> None:
    async def on_message(data: str | bytes) -> None:
        question = QuestionModel(data=loads(data)).data
        async with state.proxy() as proxy:
            current_question: models.poll.Question | None = proxy.get("question", None)
            completed: set[UUID] = proxy.get("completed", set())

            if question.question_id in completed:
                return

            completed.add(question.question_id)

            if current_question is None:
                await queue.put(question)
            elif current_question.question_id != question.question_id:
                await queue.put(question)
                if proxy["dialog"] is None:
                    proxy["dialog"] = await msg.reply(
                        "The question queue was changed.",
                        reply_markup=change_question_buttons,
                    )
            proxy["completed"] = completed

    queue: Queue[models.poll.Question] = Queue()
    task = await api.listen_questions(poll_id, on_message)
    questions_pull[msg.from_user.id] = (queue, task)

    async with state.proxy() as data:
        data["poll_id"] = poll_id
        data["completed"] = set()
        data["question"] = None
        data["dialog"] = None
        data["message"] = await msg.answer(
            "You are connected to the presentation, please wait for the new questions. Type /exit to exit.",
            reply_markup=exit_buttons,
        )

    await bot.set_my_commands(answers_state_commands, target_scope(msg.from_user.id))
    await wait_next_question(msg, queue, state)


async def stop_answers_state(user_id: int, state: FSMContext) -> None:
    task = questions_pull.pop(user_id)[1]

    async with state.proxy() as data:
        await data["message"].edit_text(
            "You are disconnected from the presentation."
            " To connect again scan the QR code from the presentation or enter /start and enter the connection code."
        )

    task.cancel()
    await task
    await bot.delete_my_commands(target_scope(user_id))
    await state.finish()


async def wait_next_question(
    msg: Message,
    queue: Queue[models.poll.Question],
    state: FSMContext,
) -> None:
    await AnswersState.wait_question.set()

    question = await queue.get()

    async with state.proxy() as data:
        if data["dialog"] is not None:
            await data["dialog"].delete()
            data["dialog"] = None
        data["question"] = question

    if isinstance(question, models.poll.SelectorQuestion):
        await start_selector_answer(msg, question, state)
    if isinstance(question, models.poll.SliderQuestion):
        await start_slider_answer(msg, question, state)
    if isinstance(question, models.poll.TopListQuestion):
        await start_top_list_answer(msg, question, state)
    if isinstance(question, models.poll.TextQuestion):
        await start_text_answer(msg, question, state)


def question_text(question: models.poll.Question) -> str:
    if question.description is not None:
        return (
            f"<b>{escape(question.label)}</b>\n\n"
            f"<i>{escape(question.description)}</i>"
        )
    else:
        return f"<b>{escape(question.label)}</b>\n"


def get_selector_buttons(
    question: models.poll.SelectorQuestion,
    selected: set[int],
) -> InlineKeyboardMarkup:
    buttons = InlineKeyboardMarkup()
    max_checked = (
        question.max_checked
        if question.max_checked is not None
        else len(question.options)
    )

    for index, option in enumerate(question.options):
        if len(selected) == max_checked and index not in selected:
            continue

        buttons.row(
            InlineKeyboardButton(
                f"{'●' if index in selected else '○'} {option.label}",
                callback_data=option_callback_data.new(index=index),
            )
        )

    if question.min_checked <= len(selected) <= max_checked:
        buttons.row(send_button)

    return buttons


async def start_selector_answer(
    msg: Message,
    question: models.poll.SelectorQuestion,
    state: FSMContext,
) -> None:
    await AnswersState.selector.set()

    selected: set[int] = set()
    async with state.proxy() as data:
        await data["message"].edit_text(
            question_text(question),
            reply_markup=get_selector_buttons(question, selected),
        )

        data["selected"] = selected


def get_slider_buttons(
    question: models.poll.SliderQuestion,
    sliders: list[int | None],
) -> InlineKeyboardMarkup:
    buttons = InlineKeyboardMarkup()

    for index, (option, value) in enumerate(zip(question.options, sliders)):
        buttons.row(
            InlineKeyboardButton(
                f"{option.label} - {value if value is not None else '⛶'}",
                callback_data=option_callback_data.new(index=index),
            )
        )

    if all(value is not None for value in sliders):
        buttons.row(send_button)

    return buttons


async def start_slider_answer(
    msg: Message,
    question: models.poll.SliderQuestion,
    state: FSMContext,
) -> None:
    await AnswersState.slider.set()

    sliders: list[int | None] = [None] * len(question.options)
    async with state.proxy() as data:
        await data["message"].edit_text(
            question_text(question),
            reply_markup=get_slider_buttons(question, sliders),
        )

        data["sliders"] = sliders


def get_top_list_buttons(
    question: models.poll.TopListQuestion,
    ranks: list[int],
) -> InlineKeyboardMarkup:
    buttons = InlineKeyboardMarkup()

    for index, option_index in enumerate(ranks):
        option = question.options[option_index]
        buttons.row(
            InlineKeyboardButton(
                f"{index+1} - {option.label}",
                callback_data=option_callback_data.new(index=index),
            ),
            InlineKeyboardButton(
                "Remove",
                callback_data=delete_callback_data.new(index=index),
            ),
        )

    max_ranks = (
        question.max_ranks if question.max_ranks is not None else len(question.options)
    )

    if len(ranks) < max_ranks:
        buttons.row(add_button)
    if question.min_ranks <= len(ranks) <= max_ranks:
        buttons.row(send_button)

    return buttons


def get_top_list_options(
    question: models.poll.TopListQuestion,
    ranks: list[int],
) -> InlineKeyboardMarkup:
    buttons = InlineKeyboardMarkup()

    for index, option in enumerate(question.options):
        if index in ranks:
            continue

        buttons.row(
            InlineKeyboardButton(
                option.label,
                callback_data=option_callback_data.new(index=index),
            )
        )

    return buttons


async def start_top_list_answer(
    msg: Message,
    question: models.poll.TopListQuestion,
    state: FSMContext,
) -> None:
    await AnswersState.top_list.set()

    ranks: list[int] = []
    async with state.proxy() as data:
        await data["message"].edit_text(
            question_text(question),
            reply_markup=get_top_list_buttons(question, ranks),
        )

        data["ranks"] = ranks


async def start_text_answer(
    msg: Message,
    question: models.poll.TextQuestion,
    state: FSMContext,
) -> None:
    await AnswersState.text.set()

    async with state.proxy() as data:
        await data["message"].edit_text(question_text(question))


@dp.callback_query_handler(change_question_callback_data.filter(), state=AnswersState)
async def change_question_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    await clb.message.delete()

    async with state.proxy() as data:
        data["dialog"] = None
        data["completed"].remove(data["question"].question_id)

    if callback_data["action"] == "accept":
        await wait_next_question(
            clb.message,
            questions_pull[clb.from_user.id][0],
            state,
        )

    await clb.answer()


@dp.message_handler(commands=["exit"], state=AnswersState)
async def exit_command_handler(msg: Message, state: FSMContext) -> None:
    await msg.delete()
    await stop_answers_state(msg.from_user.id, state)


@dp.callback_query_handler(exit_callback_data.filter(), state=AnswersState)
async def exit_handler(clb: CallbackQuery, state: FSMContext) -> None:
    await clb.answer()
    await stop_answers_state(clb.from_user.id, state)


@dp.callback_query_handler(send_callback_data.filter(), state=AnswersState)
async def send_handler(clb: CallbackQuery, state: FSMContext) -> None:
    await clb.message.edit_text("Sending ...")

    async with state.proxy() as data:
        value: models.answers.Value
        question: models.poll.Question = data["question"]
        poll_id: int = data["poll_id"]

        if isinstance(question, models.poll.SelectorQuestion):
            value = models.answers.SelectorValue(
                question_id=question.question_id,
                selected=data.pop("selected"),
            )
        elif isinstance(question, models.poll.SliderQuestion):
            value = models.answers.SliderValue(
                question_id=question.question_id,
                sliders=data.pop("sliders"),
            )
        elif isinstance(question, models.poll.TopListQuestion):
            value = models.answers.TopListValue(
                question_id=question.question_id,
                ranks=data.pop("ranks"),
            )
        elif isinstance(question, models.poll.TextQuestion):
            value = models.answers.TextValue(
                question_id=question.question_id,
                text=data.pop("text"),
            )

        await api.answers_add_value(poll_id, value)

        data["question"] = None

    await clb.message.edit_text(
        "Thanks for the answer, please wait for the next questions."
    )
    await clb.answer()

    await wait_next_question(clb.message, questions_pull[clb.from_user.id][0], state)


@dp.callback_query_handler(option_callback_data.filter(), state=AnswersState.selector)
async def selector_option_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    index = int(callback_data["index"])
    async with state.proxy() as data:
        selected: set[int] = data["selected"]

        if index not in selected:
            selected.add(index)
        else:
            selected.remove(index)

        await clb.message.edit_reply_markup(
            get_selector_buttons(
                data["question"],
                selected,
            )
        )
    await clb.answer()


@dp.callback_query_handler(option_callback_data.filter(), state=AnswersState.slider)
async def slider_option_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    await AnswersState.wait_slider_value.set()

    index = int(callback_data["index"])
    async with state.proxy() as data:
        question: models.poll.SliderQuestion = data["question"]
        data["index"] = index

        await clb.message.edit_text(
            f'Send me the value for "{question.options[index].label}".\n'
            f"Value must be between {question.min_value} and {question.max_value}.",
            reply_markup=cancel_buttons,
        )

    await clb.answer()


@dp.callback_query_handler(
    cancel_callback_data.filter(),
    state=AnswersState.wait_slider_value,
)
async def cancel_slider_value_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    await AnswersState.slider.set()

    async with state.proxy() as data:
        question: models.poll.SliderQuestion = data["question"]

        data.pop("index")
        await data["message"].edit_text(
            question_text(question),
            reply_markup=get_slider_buttons(question, data["sliders"]),
        )

    await clb.answer()


@dp.message_handler(
    content_types=[ContentType.TEXT],
    state=AnswersState.wait_slider_value,
)
async def slider_value_handler(msg: Message, state: FSMContext) -> None:
    await msg.delete()

    async with state.proxy() as data:
        question: models.poll.SliderQuestion = data["question"]
        sliders: list[int | None] = data["sliders"]

        try:
            value = int(msg.text)
        except ValueError:
            await data["message"].edit_text(
                "Value is incorrect. Try again.",
                reply_markup=cancel_buttons,
            )
            return

        if not (question.min_value <= value <= question.max_value):
            await data["message"].edit_text(
                f"Value must be between {question.min_value} and {question.max_value}.\n"
                "Try again.",
                reply_markup=cancel_buttons,
            )
            return

        sliders[data["index"]] = value
        data.pop("index")

        await data["message"].edit_text(
            question_text(question),
            reply_markup=get_slider_buttons(question, sliders),
        )

    await AnswersState.slider.set()


@dp.callback_query_handler(add_callback_data.filter(), state=AnswersState.top_list)
async def top_list_add_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    await AnswersState.wait_top_list_rank.set()

    async with state.proxy() as data:
        question: models.poll.TopListQuestion = data["question"]
        ranks: list[int] = data["ranks"]

        await clb.message.edit_text(
            "Select an option",
            reply_markup=get_top_list_options(question, ranks).row(
                cancel_buttons.inline_keyboard[0][0]
            ),
        )

    await clb.answer()


@dp.callback_query_handler(option_callback_data.filter(), state=AnswersState.top_list)
async def top_list_edit_option_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    await AnswersState.wait_top_list_rank.set()

    edit_index = int(callback_data["index"])
    async with state.proxy() as data:
        question: models.poll.TopListQuestion = data["question"]
        ranks: list[int] = data["ranks"]
        data["edit_index"] = edit_index

        await clb.message.edit_text(
            "Select an option",
            reply_markup=get_top_list_options(question, ranks).row(
                cancel_buttons.inline_keyboard[0][0]
            ),
        )

    await clb.answer()


@dp.callback_query_handler(delete_callback_data.filter(), state=AnswersState.top_list)
async def top_list_remove_option_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    index = int(callback_data["index"])
    async with state.proxy() as data:
        question: models.poll.TopListQuestion = data["question"]
        ranks: list[int] = data["ranks"]

        ranks.pop(index)

        await clb.message.edit_text(
            question_text(question),
            reply_markup=get_top_list_buttons(question, ranks),
        )

    await clb.answer()


@dp.callback_query_handler(
    cancel_callback_data.filter(),
    state=AnswersState.wait_top_list_rank,
)
async def cancel_top_list_select_option_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    await AnswersState.top_list.set()

    async with state.proxy() as data:
        question: models.poll.TopListQuestion = data["question"]

        await data["message"].edit_text(
            question_text(question),
            reply_markup=get_top_list_buttons(question, data["ranks"]),
        )

        data.pop("edit_index")

    await clb.answer()


@dp.callback_query_handler(
    option_callback_data.filter(), state=AnswersState.wait_top_list_rank
)
async def top_list_select_option_handler(
    clb: CallbackQuery,
    state: FSMContext,
    callback_data: dict[str, str],
) -> None:
    await AnswersState.top_list.set()

    index = int(callback_data["index"])
    async with state.proxy() as data:
        question: models.poll.TopListQuestion = data["question"]
        ranks: list[int] = data["ranks"]
        edit_index: int | None = data.pop("edit_index", None)

        if edit_index is None:
            ranks.append(index)
        else:
            ranks[edit_index] = index

        await clb.message.edit_text(
            question_text(question),
            reply_markup=get_top_list_buttons(question, ranks),
        )

    await clb.answer()


@dp.message_handler(content_types=[ContentType.TEXT], state=AnswersState.text)
async def text_answer_handler(msg: Message, state: FSMContext) -> None:
    await msg.delete()

    async with state.proxy() as data:
        question: models.poll.TextQuestion = data["question"]

        if question.min_length is not None and len(msg.text) < question.min_length:
            data["message"].edit_text(
                f"Message length must be greater than {question.min_length}"
            )
            return
        if question.max_length is not None and len(msg.text) > question.max_length:
            data["message"].edit_text(
                f"Message length must be less than {question.min_length}"
            )
            return

        data["text"] = msg.text
        await data["message"].edit_text(
            f"You answer is «{msg.text}».",
            reply_markup=InlineKeyboardMarkup().row(send_button),
        )


@dp.message_handler(content_types=[ContentType.TEXT], state=AnswersState)
async def other_message_handler(msg: Message) -> None:
    await msg.delete()
