from aiogram.types import BotCommand as cmd
from aiogram.types import BotCommandScopeAllPrivateChats as all_private_scope
from aiogram.types import BotCommandScopeChat as target_scope

global_commands = [cmd("start", "Connect to presentation")]
code_state_commands = [cmd("cancel", "Cancel connection to presentation")]
answers_state_commands = [cmd("exit", "Exit from presentation")]
