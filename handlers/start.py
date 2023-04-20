from aiogram.dispatcher import FSMContext
from aiogram.types import ContentType, ForceReply, Message

import handlers
from bot import dp
from states import CodeState


@dp.message_handler(commands=["start"])
async def start_command(msg: Message, state: FSMContext) -> None:
    args = msg.get_args()
    assert args is not None

    if len(args) == 0:
        await msg.reply(
            "Please send me connection code",
            reply_markup=ForceReply.create("Connection code"),
        )
        await CodeState.wait_code.set()
    else:
        try:
            poll_id = int(args)
        except ValueError:
            await msg.reply("Connection code is incorrect")
            return

        await handlers.poll.start_answers_state(poll_id, msg, state)


@dp.message_handler(commands=["cancel"], state=CodeState)
async def cancel_command(msg: Message, state: FSMContext) -> None:
    await msg.reply("Operation canceled. Send me /start to try again.")
    await state.finish()


@dp.message_handler(content_types=[ContentType.TEXT], state=CodeState.wait_code)
async def wait_code_handler(msg: Message, state: FSMContext) -> None:
    try:
        poll_id = int(msg.text)
    except ValueError:
        await msg.reply(
            "Connection code is incorrect. Try again.",
            reply_markup=ForceReply.create("Connection code"),
        )
        return

    await handlers.poll.start_answers_state(poll_id, msg, state)
