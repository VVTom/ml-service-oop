import os
import time
from typing import Any

import requests


API_BASE_URL = os.getenv(
    "API_BASE_URL",
    "http://app:8000",
)


def get_error_message(
    response: requests.Response,
    default_message: str,
) -> str:
    try:
        data = response.json()
    except ValueError:
        return default_message

    detail = data.get("detail")

    if isinstance(detail, str):
        return detail

    if isinstance(detail, list):
        messages = []

        for item in detail:
            if isinstance(item, dict):
                messages.append(item.get("msg", str(item)))
            else:
                messages.append(str(item))

        return "; ".join(messages)

    return default_message


def check_api() -> bool:
    try:
        response = requests.get(
            f"{API_BASE_URL}/health",
            timeout=5,
        )

        return response.status_code == 200

    except requests.RequestException:
        return False


def register_user(
    login: str,
    password: str,
) -> tuple[bool, dict[str, Any]]:
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            json={
                "login": login,
                "password": password,
            },
            timeout=5,
        )

        if response.status_code == 201:
            return True, response.json()

        return False, {
            "detail": get_error_message(
                response,
                "Ошибка регистрации",
            )
        }

    except requests.RequestException as error:
        return False, {"detail": (f"Ошибка подключения к backend: {error}")}


def login_user(
    login: str,
    password: str,
) -> tuple[bool, dict[str, Any]]:
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={
                "login": login,
                "password": password,
            },
            timeout=5,
        )

        if response.status_code == 200:
            return True, response.json()

        return False, {
            "detail": get_error_message(
                response,
                "Ошибка авторизации",
            )
        }

    except requests.RequestException as error:
        return False, {"detail": (f"Ошибка подключения к backend: {error}")}


def get_balance(
    login: str,
    password: str,
) -> tuple[bool, dict[str, Any]]:
    try:
        response = requests.get(
            f"{API_BASE_URL}/balance",
            auth=(login, password),
            timeout=5,
        )

        if response.status_code == 200:
            return True, response.json()

        return False, {
            "detail": get_error_message(
                response,
                "Не удалось получить баланс",
            )
        }

    except requests.RequestException as error:
        return False, {"detail": (f"Ошибка подключения к backend: {error}")}


def top_up_balance(
    login: str,
    password: str,
    amount: float,
) -> tuple[bool, dict[str, Any]]:
    try:
        response = requests.post(
            f"{API_BASE_URL}/balance/topup",
            auth=(login, password),
            json={
                "amount": amount,
            },
            timeout=5,
        )

        if response.status_code == 200:
            return True, response.json()

        return False, {
            "detail": get_error_message(
                response,
                "Ошибка пополнения баланса",
            )
        }

    except requests.RequestException as error:
        return False, {"detail": (f"Ошибка подключения к backend: {error}")}


def create_prediction(
    login: str,
    password: str,
    text: str,
) -> tuple[bool, dict[str, Any]]:
    try:
        response = requests.post(
            f"{API_BASE_URL}/predict",
            auth=(login, password),
            json={
                "model_name": "sentiment-model",
                "text": text,
            },
            timeout=10,
        )

        if response.status_code == 202:
            return True, response.json()

        return False, {
            "detail": get_error_message(
                response,
                "Не удалось создать ML-задачу",
            ),
            "status_code": response.status_code,
        }

    except requests.RequestException as error:
        return False, {"detail": (f"Ошибка подключения к backend: {error}")}


def get_prediction_history(
    login: str,
    password: str,
) -> tuple[bool, list | dict]:
    try:
        response = requests.get(
            f"{API_BASE_URL}/history/predictions",
            auth=(login, password),
            timeout=10,
        )

        if response.status_code == 200:
            return True, response.json()

        return False, {
            "detail": get_error_message(
                response,
                "Не удалось получить историю предсказаний",
            )
        }

    except requests.RequestException as error:
        return False, {"detail": (f"Ошибка подключения к backend: {error}")}


def get_transaction_history(
    login: str,
    password: str,
) -> tuple[bool, list | dict]:
    try:
        response = requests.get(
            f"{API_BASE_URL}/history/transactions",
            auth=(login, password),
            timeout=10,
        )

        if response.status_code == 200:
            return True, response.json()

        return False, {
            "detail": get_error_message(
                response,
                "Не удалось получить историю транзакций",
            )
        }

    except requests.RequestException as error:
        return False, {"detail": (f"Ошибка подключения к backend: {error}")}


def wait_for_prediction(
    login: str,
    password: str,
    task_id: int,
    timeout: float = 20.0,
    interval: float = 0.5,
) -> tuple[bool, dict]:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        success, response = get_prediction_history(
            login=login,
            password=password,
        )

        if not success:
            return False, response

        for prediction in response:
            if prediction["task_id"] != task_id:
                continue

            if prediction["status"] == "completed":
                return True, prediction

            if prediction["status"] == "failed":
                return False, {"detail": (f"ML-задача {task_id} завершилась с ошибкой")}

        time.sleep(interval)

    return False, {
        "detail": (f"ML-задача {task_id} не завершилась за отведённое время")
    }
