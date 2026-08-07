import asyncio
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv


ENVPATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENVPATH)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

dispatcher = Dispatcher()


@dispatcher.message(CommandStart())
async def start_command(message: Message):
    await message.answer(
        "Привет! Я бот ML-сервиса.\n\n  /start — показать список доступных команд"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не найден TELEGRAM_BOT_TOKEN. Проверь файл telegram_bot/.env"
        )

    bot = Bot(token=BOT_TOKEN)

    print("Бот запущен. Для остановки набери Ctrl+C")

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
