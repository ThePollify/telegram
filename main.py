import logging

from aiogram import Dispatcher
from aiogram.types import Update
from aiogram.utils.exceptions import MessageNotModified
from aiogram.utils.executor import start_polling

# isort: off

import bot
import models
import api
import states
import commands
import handlers

logging.basicConfig(level=logging.INFO)


@bot.dp.errors_handler()
async def error_handler(upd: Update, exc: Exception) -> bool | None:
    if isinstance(exc, (MessageNotModified,)):
        return True

    if upd.callback_query is not None:
        await upd.callback_query.answer()

    return None


async def on_startup(dispatcher: Dispatcher) -> None:
    await bot.bot.set_my_commands(commands.global_commands)


if __name__ == "__main__":
    start_polling(bot.dp, on_startup=on_startup)
