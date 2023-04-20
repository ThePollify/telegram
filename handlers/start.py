from aiogram.dispatcher import FSMContext
from aiogram.types import ContentType, ForceReply, Message

import handlers
from bot import bot, dp
from commands import code_state_commands, target_scope
from states import CodeState


@dp.message_handler(commands=["start"])
async def start_command(msg: Message, state: FSMContext) -> None:
    args = msg.get_args()
    assert args is not None

    if len(args) == 0:
        await msg.reply(
            "Please send me connection code.\nType /cancel to cancel connection",
            reply_markup=ForceReply.create("Connection code"),
        )
        await CodeState.wait_code.set()
        await bot.set_my_commands(code_state_commands, target_scope(msg.from_user.id))
    else:
        try:
            poll_id = int(args)
        except ValueError:
            await msg.reply(
                "Connection code is incorrect.\n"
                "Try again or type /cancel to cancel connection."
            )
            return

        await handlers.poll.start_answers_state(poll_id, msg, state)


@dp.message_handler(commands=["cancel"], state=CodeState)
async def cancel_command(msg: Message, state: FSMContext) -> None:
    await msg.reply("Operation canceled. Send me /start to try again.")
    await bot.delete_my_commands(target_scope(msg.from_user.id))
    await state.finish()


@dp.message_handler(content_types=[ContentType.TEXT], state=CodeState.wait_code)
async def wait_code_handler(msg: Message, state: FSMContext) -> None:
    try:
        poll_id = int(msg.text)
    except ValueError:
        await msg.reply(
            "Connection code is incorrect.\n"
            "Try again or type /cancel to cancel connection.",
            reply_markup=ForceReply.create("Connection code"),
        )
        return

    await handlers.poll.start_answers_state(poll_id, msg, state)
