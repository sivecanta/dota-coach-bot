"""/start and /help."""

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from dota_coach.bot import presenter
from dota_coach.bot.handlers.common import is_private
from dota_coach.bot.handlers.link import begin_link

router = Router(name="basic")


@router.message(CommandStart())
async def start(message: Message, command: CommandObject, state: FSMContext) -> None:
    if command.args == "link" and is_private(message):
        await begin_link(message, state)
        return
    await message.answer(presenter.HELP)


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(presenter.HELP)
