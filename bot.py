from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from settings import settings

bot = Bot(token=settings.token)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
