import asyncio
import os
from pathlib import Path
from typing import Any

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://localhost",
)

dispatcher = Dispatcher()


class LoginState(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()


def get_auth(
    login: str,
    password: str,
) -> aiohttp.BasicAuth:
    return aiohttp.BasicAuth(
        login=login,
        password=password,
    )


async def get_prediction_history(
    login: str,
    password: str,
) -> tuple[int, Any]:
    auth = get_auth(
        login=login,
        password=password,
    )

    async with aiohttp.ClientSession(auth=auth) as session:
        async with session.get(
            f"{API_BASE_URL}/history/predictions",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            data = await response.json()

            return response.status, data


async def wait_for_prediction(
    login: str,
    password: str,
    task_id: int,
    timeout: float = 20.0,
    interval: float = 0.5,
) -> dict[str, Any] | None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        status_code, predictions = await get_prediction_history(
            login=login,
            password=password,
        )

        if status_code != 200:
            return None

        for prediction in predictions:
            if prediction["task_id"] == task_id:
                return prediction

        await asyncio.sleep(interval)

    return None


@dispatcher.message(CommandStart())
async def start_command(
    message: Message,
) -> None:
    await message.answer(
        "Привет! Я бот ML-сервиса.\n\n"
        "Доступные команды:\n"
        "/start — справка\n"
        "/login — войти в ML-сервис\n"
        "/logout — выйти\n"
        "/balance — посмотреть баланс\n"
        "/topup 100 — пополнить баланс\n"
        "/predict sentiment-model текст — "
        "анализ одного текста\n"
        "/batch текст 1 | текст 2 | текст 3 — "
        "обработать несколько строк\n"
        "/transactions — история транзакций\n"
        "/history — история предсказаний\n"
    )


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

    await state.update_data(
        login=login,
    )

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

    auth = get_auth(
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

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
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
        await message.answer("Сначала войдите через /login")
        return

    auth = get_auth(
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

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 200:
        await message.answer(f"Ваш баланс: {response_data['balance']} кредитов")
        return

    if response.status == 401:
        await state.clear()

        await message.answer("Авторизация недействительна.\nВойдите снова через /login")
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
        await message.answer("Сначала войдите через /login")
        return

    if not message.text:
        await message.answer("Укажите сумму.\nПример: /topup 100")
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Укажите сумму.\nПример: /topup 100")
        return

    try:
        amount = float(parts[1])

    except ValueError:
        await message.answer("Сумма должна быть числом.")
        return

    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return

    auth = get_auth(
        login=login,
        password=password,
    )

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(
                f"{API_BASE_URL}/balance/topup",
                json={
                    "amount": amount,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                response_data = await response.json()

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 200:
        await message.answer(
            f"Баланс успешно пополнен.\nТекущий баланс: {response_data['balance']}"
        )
        return

    if response.status == 401:
        await state.clear()

        await message.answer("Авторизация недействительна.\nВойдите снова через /login")
        return

    await message.answer(
        response_data.get(
            "detail",
            "Не удалось пополнить баланс",
        )
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
        await message.answer("Сначала войдите через /login")
        return

    if not message.text:
        await message.answer(
            "Пример:\n/predict sentiment-model Мне нравится этот сервис"
        )
        return

    parts = message.text.split(maxsplit=2)

    if len(parts) != 3:
        await message.answer(
            "Неверный формат.\n"
            "Пример:\n"
            "/predict sentiment-model "
            "Мне нравится этот сервис"
        )
        return

    model_name = parts[1]
    text = parts[2].strip()

    if not text:
        await message.answer("Текст не может быть пустым.")
        return

    auth = get_auth(
        login=login,
        password=password,
    )

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(
                f"{API_BASE_URL}/predict",
                json={
                    "model_name": model_name,
                    "text": text,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                response_data = await response.json()

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 401:
        await state.clear()

        await message.answer("Авторизация недействительна.\nВойдите снова через /login")
        return

    if response.status == 402:
        await message.answer("Недостаточно средств.\nПополните баланс через /topup")
        return

    if response.status in {
        400,
        422,
    }:
        await message.answer(
            "Не удалось создать ML-задачу.\n"
            f"{response_data.get('detail', 'Некорректные данные')}"
        )
        return

    if response.status != 202:
        await message.answer(f"Ошибка ML-сервиса.\nКод ответа API: {response.status}")
        return

    task_id = response_data["task_id"]

    waiting_message = await message.answer(
        f"Задача #{task_id} принята.\nML-модель обрабатывает текст..."
    )

    try:
        prediction = await wait_for_prediction(
            login=login,
            password=password,
            task_id=task_id,
        )

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        prediction = None

    if prediction is None:
        await waiting_message.edit_text(
            f"Задача #{task_id} принята, "
            "но результат не получен вовремя.\n"
            "Проверьте позже через /history."
        )
        return

    result = prediction.get("prediction") or {}

    sentiment = result.get(
        "sentiment",
        "unknown",
    )

    score = result.get("score")

    worker_id = result.get(
        "worker_id",
        "unknown",
    )

    if score is not None:
        score_text = f"{float(score):.2%}"
    else:
        score_text = "—"

    await waiting_message.edit_text(
        "Предсказание выполнено ✅\n\n"
        f"Задача: #{task_id}\n"
        f"Статус: "
        f"{prediction['status']}\n"
        f"Тональность: {sentiment}\n"
        f"Уверенность: {score_text}\n"
        f"Worker: {worker_id}\n"
        f"Списано: "
        f"{prediction['charged']} кредитов"
    )


@dispatcher.message(Command("batch"))
async def batch_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите через /login")
        return

    if not message.text:
        await message.answer("Пример:\n/batch Отличный сервис | | Ужасный продукт")
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Добавьте тексты после команды.\nРазделяйте строки символом |"
        )
        return

    rows = [row.strip() for row in parts[1].split("|")]

    auth = get_auth(
        login=login,
        password=password,
    )

    try:
        async with aiohttp.ClientSession(auth=auth) as session:
            async with session.post(
                f"{API_BASE_URL}/predict/batch",
                json={
                    "model_name": ("sentiment-model"),
                    "rows": rows,
                },
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                response_data = await response.json()

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status == 401:
        await state.clear()

        await message.answer("Авторизация недействительна.\nВойдите снова через /login")
        return

    if response.status == 402:
        await message.answer(
            response_data.get(
                "detail",
                "Недостаточно средств",
            )
        )
        return

    if response.status != 202:
        await message.answer(
            response_data.get(
                "detail",
                "Не удалось обработать пакет",
            )
        )
        return

    accepted = response_data.get(
        "accepted",
        [],
    )

    invalid_rows = response_data.get(
        "invalid_rows",
        [],
    )

    lines = []

    if invalid_rows:
        lines.append("Отклонённые строки:")

        for item in invalid_rows:
            lines.append(f"Строка {item['row']}: {item['error']}")

    if not accepted:
        lines.append("Корректных строк для обработки нет.")

        await message.answer("\n".join(lines))
        return

    lines.append("\nПриняты в обработку:")

    for item in accepted:
        lines.append(f"Строка {item['row']} → задача #{item['task_id']}")

    status_message = await message.answer("\n".join(lines))

    result_lines = ["Результаты пакетной обработки ✅\n"]

    if invalid_rows:
        result_lines.append("Отклонённые строки:")

        for item in invalid_rows:
            result_lines.append(f"Строка {item['row']}: {item['error']}")

        result_lines.append("\nОбработанные строки:")

    for item in accepted:
        task_id = item["task_id"]
        row_number = item["row"]

        try:
            prediction = await wait_for_prediction(
                login=login,
                password=password,
                task_id=task_id,
            )

        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
        ):
            prediction = None

        if prediction is None:
            result_lines.append(
                f"Строка {row_number}: задача #{task_id} ещё не завершена"
            )
            continue

        result = prediction.get("prediction") or {}

        sentiment = result.get(
            "sentiment",
            "unknown",
        )

        score = result.get("score")

        if score is not None:
            score_text = f"{float(score):.2%}"
        else:
            score_text = "—"

        result_lines.append(
            f"Строка {row_number}: "
            f"{sentiment}, "
            f"{score_text}, "
            f"списано "
            f"{prediction['charged']}"
        )

    await status_message.edit_text("\n".join(result_lines))


@dispatcher.message(Command("transactions"))
async def transactions_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите через /login")
        return

    auth = get_auth(
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

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if response.status != 200:
        await message.answer("Не удалось получить историю транзакций.")
        return

    if not response_data:
        await message.answer("История транзакций пока пуста.")
        return

    lines = ["Последние транзакции:\n"]

    for transaction in response_data[:10]:
        lines.append(
            f"#{transaction['id']} | "
            f"{transaction['operation_type']} | "
            f"{transaction['amount']}"
        )

    await message.answer("\n".join(lines))


@dispatcher.message(Command("history"))
async def history_command(
    message: Message,
    state: FSMContext,
) -> None:
    data = await state.get_data()

    login = data.get("login")
    password = data.get("password")

    if not login or not password:
        await message.answer("Сначала войдите через /login")
        return

    try:
        (
            status_code,
            response_data,
        ) = await get_prediction_history(
            login=login,
            password=password,
        )

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        await message.answer("Не удалось подключиться к ML-сервису.")
        return

    if status_code != 200:
        await message.answer("Не удалось получить историю предсказаний.")
        return

    if not response_data:
        await message.answer("История предсказаний пока пуста.")
        return

    lines = ["Последние предсказания:\n"]

    for prediction in response_data[:10]:
        result = prediction.get("prediction") or {}

        sentiment = result.get(
            "sentiment",
            "—",
        )

        score = result.get("score")

        if score is not None:
            score_text = f"{float(score):.2%}"
        else:
            score_text = "—"

        lines.append(
            f"Задача #{prediction['task_id']}\n"
            f"Статус: "
            f"{prediction['status']}\n"
            f"Тональность: "
            f"{sentiment}\n"
            f"Уверенность: "
            f"{score_text}\n"
            f"Списано: "
            f"{prediction['charged']}\n"
        )

    await message.answer("\n".join(lines))


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("Не найден TELEGRAM_BOT_TOKEN. Проверь telegram_bot/.env")

    bot = Bot(token=BOT_TOKEN)

    print("Telegram-бот запущен")

    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
