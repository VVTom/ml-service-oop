import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


ENVPATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENVPATH)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://localhost",
)

dispatcher = Dispatcher()


@dispatcher.message(CommandStart())
async def start_command(message: Message):
    await message.answer(
        "Привет! Я бот ML-сервиса.\n\n"
        "Доступные команды:\n"
        "/start — показать справку\n"
        "/login — войти в ML-сервис\n"
        "/logout — выйти из ML-сервиса\n"
        "/balance — посмотреть баланс\n"
        "/topup 100 — пополнить баланс\n"
        "/predict sentiment-model текст — выполнить предсказание\n"
        "/transactions — история транзакций\n"
        "/history — история предсказаний\n"
    )


async def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "Не найден TELEGRAM_BOT_TOKEN. Проверь файл telegram_bot/.env"
        )

    bot = Bot(token=BOT_TOKEN)

    print("Бот запущен. Для остановки набери Ctrl+C")

    await dispatcher.start_polling(bot)


class LoginState(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()


@dispatcher.message(Command("login"))
async def login_command(
    message: Message,
    state: FSMContext,
) -> None:
    await state.set_state(LoginState.waiting_for_login)
    await message.answer("Введите логин от ML-сервиса:")


@dispatcher.message(LoginState.waiting_for_login)
async def process_login(
    message: Message,
    state: FSMContext,
) -> None:
    login = message.text

    if not login:
        await message.answer("Логин не может быть пустым")
        return

    await state.update_data(login=login)

    await state.set_state(LoginState.waiting_for_password)

    await message.answer("Введите пароль от ML-сервиса:")


@dispatcher.message(LoginState.waiting_for_password)
async def process_password(
    message: Message,
    state: FSMContext,
) -> None:
    password = message.text

    if not password:
        await message.answer("Пароль не может быть пустым")
        return

    data = await state.get_data()

    login = data["login"]

    auth = aiohttp.BasicAuth(
        login=login,
        password=password,
    )

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(
                f"{API_BASE_URL}/users/me",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response_data = await response.json()

    except aiohttp.ClientError:
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 401:
        await state.clear()

        await message.answer("Неверный логин или пароль.\nПопробуйте снова: /login")
        return

    if response.status == 200:
        await state.update_data(
            login=login,
            password=password,
        )

        await state.set_state(None)
        await message.answer(f"Вы успешно вошли как {response_data['login']}.")
        return

    await state.clear()

    await message.answer(f"Ошибка авторизации.\nКод ответа API: {response.status}")


@dispatcher.message(Command("logout"))
async def logout_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    if "login" not in data or "password" not in data:
        await message.answer("Вы не авторизованы.")
        return

    await state.clear()

    await message.answer("Вы вышли из ML-сервиса.")


@dispatcher.message(Command("balance"))
async def balance_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите в ML-сервис через /login")
        return

    auth = aiohttp.BasicAuth(
        login=login,
        password=password,
    )

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(
                f"{API_BASE_URL}/balance",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response_data = await response.json()

    except aiohttp.ClientError:
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 200:
        await message.answer(f"Ваш баланс: {response_data['balance']}")
        return

    if response.status == 401:
        await state.clear()

        await message.answer(
            "Сессия авторизации недействительна.\nВойдите снова через /login"
        )
        return

    await message.answer(
        f"Не удалось получить баланс.\nКод ответа API: {response.status}"
    )


@dispatcher.message(Command("topup"))
async def topup_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите в ML-сервис через /login")
        return

    if not message.text:
        await message.answer("Укажите сумму.\nПример: /topup 100")
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Укажите сумму.\nПример: /topup 100")
        return

    amount_text = parts[1]

    try:
        amount = float(amount_text)
    except ValueError:
        await message.answer("Сумма должна быть числом.")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return

    auth = aiohttp.BasicAuth(
        login=login,
        password=password,
    )

    payload = {
        "amount": amount,
    }

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(
                f"{API_BASE_URL}/balance/topup",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response_data = await response.json()

    except aiohttp.ClientError:
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 200:
        await message.answer(
            f"Баланс успешно пополнен.\nТекущий баланс: {response_data['balance']}"
        )
        return

    if response.status == 401:
        await state.clear()

        await message.answer(
            "Сессия авторизации недействительна.\nВойдите снова через /login"
        )
        return

    await message.answer(
        f"Не удалось пополнить баланс.\nКод ответа API: {response.status}"
    )


@dispatcher.message(Command("predict"))
async def predict_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите в ML-сервис через /login")
        return

    if not message.text:
        await message.answer(
            "Укажите модель и текст.\n"
            "Пример:\n"
            "/predict sentiment-model Мне нравится этот сервис"
        )
        return

    parts = message.text.split(maxsplit=2)

    if len(parts) != 3:
        await message.answer(
            "Неверный формат команды.\n"
            "Пример:\n"
            "/predict sentiment-model Мне нравится этот сервис"
        )
        return

    model_name = parts[1]
    text = parts[2]

    auth = aiohttp.BasicAuth(
        login=login,
        password=password,
    )

    payload = {
        "model_name": model_name,
        "text": text,
    }

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(
                f"{API_BASE_URL}/predict",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                response_data = await response.json()

    except aiohttp.ClientError:
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 200:
        prediction = response_data["prediction"]

        await message.answer(
            "Предсказание выполнено.\n\n"
            f"Задача: {response_data['task_id']}\n"
            f"Статус: {response_data['status']}\n"
            f"Результат: {prediction}\n"
            f"Списано: {response_data['charged']}\n"
            f"Баланс: {response_data['balance']}"
        )
        return

    if response.status == 401:
        await state.clear()

        await message.answer(
            "Сессия авторизации недействительна.\nВойдите снова через /login"
        )
        return

    if response.status == 402:
        await message.answer(
            "Недостаточно средств на балансе.\nПополните баланс через /topup"
        )
        return

    if response.status == 400:
        await message.answer(
            "Не удалось выполнить предсказание.\n"
            f"{response_data.get('detail', 'Некорректный запрос')}"
        )
        return

    await message.answer(f"Ошибка ML-сервиса.\nКод ответа API: {response.status}")


@dispatcher.message(Command("transactions"))
async def transactions_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите в ML-сервис через /login")
        return

    auth = aiohttp.BasicAuth(
        login=login,
        password=password,
    )

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(
                f"{API_BASE_URL}/history/transactions",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response_data = await response.json()

    except aiohttp.ClientError:
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 200:
        if not response_data:
            await message.answer("История транзакций пока пуста.")
            return

        lines = ["История транзакций:\n"]

        for transaction in response_data[:10]:
            lines.append(
                f"#{transaction['id']} | "
                f"{transaction['operation_type']} | "
                f"{transaction['amount']}"
            )

        await message.answer("\n".join(lines))
        return

    if response.status == 401:
        await state.clear()

        await message.answer(
            "Сессия авторизации недействительна.\nВойдите снова через /login"
        )
        return

    await message.answer(
        f"Не удалось получить историю транзакций.\nКод ответа API: {response.status}"
    )


@dispatcher.message(Command("history"))
async def history_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите в ML-сервис через /login")
        return

    auth = aiohttp.BasicAuth(
        login=login,
        password=password,
    )

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.get(
                f"{API_BASE_URL}/history/predictions",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response_data = await response.json()

    except aiohttp.ClientError:
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 200:
        if not response_data:
            await message.answer("История предсказаний пока пуста.")
            return

        lines = ["История предсказаний:\n"]

        for prediction in response_data[:10]:
            lines.append(
                f"Задача #{prediction['task_id']}\n"
                f"Модель: {prediction['model_name']}\n"
                f"Статус: {prediction['status']}\n"
                f"Списано: {prediction['charged']}\n"
                f"Результат: {prediction['prediction']}\n"
            )

        await message.answer("\n".join(lines))
        return

    if response.status == 401:
        await state.clear()

        await message.answer(
            "Сессия авторизации недействительна.\nВойдите снова через /login"
        )
        return

    await message.answer(
        f"Не удалось получить историю предсказаний.\nКод ответа API: {response.status}"
    )


# ------------------------------------------------------------------------------
if __name__ == "__main__":
    asyncio.run(main())
