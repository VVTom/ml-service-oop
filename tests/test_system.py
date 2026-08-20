import time
import uuid

import pytest
import requests
from requests.auth import HTTPBasicAuth


BASE_URL = "http://localhost"
PASSWORD = "test_password_123"
MODEL_NAME = "sentiment-model"


# ----------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------

def make_user_data():
    """Создаёт уникальные данные тестового пользователя."""
    return {
        "login": f"pytest_{uuid.uuid4().hex[:8]}",
        "password": PASSWORD,
    }


def auth(user):
    """Создаёт Basic Auth для запросов от имени пользователя."""
    return HTTPBasicAuth(
        user["login"],
        user["password"],
    )


def get_balance(user):
    """Возвращает текущий баланс пользователя."""
    response = requests.get(
        f"{BASE_URL}/balance",
        auth=auth(user),
        timeout=10,
    )

    assert response.status_code == 200

    return response.json()["balance"]


def wait_for_prediction(user, task_id, timeout=20):
    """Ждёт, пока асинхронная ML-задача появится в истории."""
    deadline = time.time() + timeout

    while time.time() < deadline:
        response = requests.get(
            f"{BASE_URL}/history/predictions",
            auth=auth(user),
            timeout=10,
        )

        assert response.status_code == 200

        predictions = response.json()

        for prediction in predictions:
            if prediction["task_id"] == task_id:
                return prediction

        time.sleep(0.2)

    pytest.fail(
        f"Задача {task_id} не завершилась за {timeout} секунд"
    )


# ----------------------------------------------------------------------
# Фикстуры
# ----------------------------------------------------------------------

@pytest.fixture
def registered_user():
    """
    Перед тестом создаёт нового пользователя.

    Каждый тест получает своего пользователя,
    поэтому тесты не зависят друг от друга.
    """
    user = make_user_data()

    response = requests.post(
        f"{BASE_URL}/auth/register",
        json=user,
        timeout=10,
    )

    assert response.status_code == 201

    return user


@pytest.fixture
def funded_user(registered_user):
    """Создаёт пользователя с балансом 10.00."""
    response = requests.post(
        f"{BASE_URL}/balance/topup",
        json={"amount": 10},
        auth=auth(registered_user),
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["balance"] == "10.00"

    return registered_user


@pytest.fixture
def batch_funded_user(registered_user):
    """Создаёт пользователя с балансом 20.00."""
    response = requests.post(
        f"{BASE_URL}/balance/topup",
        json={"amount": 20},
        auth=auth(registered_user),
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["balance"] == "20.00"

    return registered_user


@pytest.fixture
def completed_prediction(funded_user):
    """
    Создаёт пользователя с 10 кредитами,
    отправляет ML-запрос и ждёт его завершения.
    """
    response = requests.post(
        f"{BASE_URL}/predict",
        json={
            "model_name": MODEL_NAME,
            "text": "Мне нравится этот отличный сервис",
        },
        auth=auth(funded_user),
        timeout=10,
    )

    assert response.status_code == 202

    task_id = response.json()["task_id"]

    prediction = wait_for_prediction(
        funded_user,
        task_id,
    )

    return {
        "user": funded_user,
        "task_id": task_id,
        "prediction": prediction,
    }


# ----------------------------------------------------------------------
# API
# ----------------------------------------------------------------------

def test_health():
    response = requests.get(
        f"{BASE_URL}/health",
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ----------------------------------------------------------------------
# Пользователи
# ----------------------------------------------------------------------

def test_registration():
    user = make_user_data()

    response = requests.post(
        f"{BASE_URL}/auth/register",
        json=user,
        timeout=10,
    )

    assert response.status_code == 201
    assert response.json()["login"] == user["login"]


def test_login(registered_user):
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json=registered_user,
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["login"] == registered_user["login"]


def test_repeated_login(registered_user):
    first_response = requests.post(
        f"{BASE_URL}/auth/login",
        json=registered_user,
        timeout=10,
    )

    second_response = requests.post(
        f"{BASE_URL}/auth/login",
        json=registered_user,
        timeout=10,
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200


def test_wrong_password(registered_user):
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={
            "login": registered_user["login"],
            "password": "wrong_password",
        },
        timeout=10,
    )

    assert response.status_code == 401


def test_duplicate_registration(registered_user):
    response = requests.post(
        f"{BASE_URL}/auth/register",
        json=registered_user,
        timeout=10,
    )

    assert response.status_code == 409


def test_protected_endpoint_without_auth():
    response = requests.get(
        f"{BASE_URL}/balance",
        timeout=10,
    )

    assert response.status_code == 401


# ----------------------------------------------------------------------
# Баланс
# ----------------------------------------------------------------------

def test_initial_balance(registered_user):
    balance = get_balance(registered_user)

    assert balance == "0.00"


def test_topup(registered_user):
    response = requests.post(
        f"{BASE_URL}/balance/topup",
        json={"amount": 10},
        auth=auth(registered_user),
        timeout=10,
    )

    assert response.status_code == 200
    assert response.json()["balance"] == "10.00"
    assert get_balance(registered_user) == "10.00"


def test_negative_topup_does_not_change_balance(registered_user):
    balance_before = get_balance(registered_user)

    response = requests.post(
        f"{BASE_URL}/balance/topup",
        json={"amount": -10},
        auth=auth(registered_user),
        timeout=10,
    )

    balance_after = get_balance(registered_user)

    assert response.status_code == 422
    assert balance_before == "0.00"
    assert balance_after == balance_before


# ----------------------------------------------------------------------
# ML-запросы
# ----------------------------------------------------------------------

def test_unknown_model_does_not_charge(funded_user):
    balance_before = get_balance(funded_user)

    response = requests.post(
        f"{BASE_URL}/predict",
        json={
            "model_name": "unknown-model",
            "text": "Тест неизвестной модели",
        },
        auth=auth(funded_user),
        timeout=10,
    )

    balance_after = get_balance(funded_user)

    assert response.status_code == 400
    assert balance_after == balance_before


def test_invalid_text_does_not_charge(funded_user):
    balance_before = get_balance(funded_user)

    response = requests.post(
        f"{BASE_URL}/predict",
        json={
            "model_name": MODEL_NAME,
            "text": "",
        },
        auth=auth(funded_user),
        timeout=10,
    )

    balance_after = get_balance(funded_user)

    assert response.status_code == 422
    assert balance_after == balance_before


def test_successful_prediction(completed_prediction):
    user = completed_prediction["user"]
    prediction = completed_prediction["prediction"]

    assert prediction["status"] == "completed"
    assert prediction["charged"] == "10.00"
    assert prediction["prediction"] is not None

    worker_id = prediction["prediction"]["worker_id"]

    assert worker_id in {"worker-1", "worker-2"}
    assert get_balance(user) == "0.00"


def test_prediction_without_money(registered_user):
    response = requests.post(
        f"{BASE_URL}/predict",
        json={
            "model_name": MODEL_NAME,
            "text": "Запрос при нулевом балансе",
        },
        auth=auth(registered_user),
        timeout=10,
    )

    assert response.status_code == 402
    assert get_balance(registered_user) == "0.00"


# ----------------------------------------------------------------------
# История
# ----------------------------------------------------------------------

def test_transaction_history(completed_prediction):
    user = completed_prediction["user"]
    task_id = completed_prediction["task_id"]

    response = requests.get(
        f"{BASE_URL}/history/transactions",
        auth=auth(user),
        timeout=10,
    )

    assert response.status_code == 200

    transactions = response.json()

    credits = [
        transaction
        for transaction in transactions
        if transaction["operation_type"] == "credit"
    ]

    debits = [
        transaction
        for transaction in transactions
        if transaction["operation_type"] == "debit"
    ]

    assert len(credits) == 1
    assert credits[0]["amount"] == "10.00"

    assert len(debits) == 1
    assert debits[0]["amount"] == "10.00"
    assert debits[0]["task_id"] == task_id


def test_prediction_history(completed_prediction):
    user = completed_prediction["user"]
    task_id = completed_prediction["task_id"]

    response = requests.get(
        f"{BASE_URL}/history/predictions",
        auth=auth(user),
        timeout=10,
    )

    assert response.status_code == 200

    predictions = response.json()

    task = next(
        prediction
        for prediction in predictions
        if prediction["task_id"] == task_id
    )

    assert task["status"] == "completed"
    assert task["charged"] == "10.00"
    assert task["prediction"] is not None


# ----------------------------------------------------------------------
# Batch
# ----------------------------------------------------------------------

def test_batch_with_invalid_rows(batch_funded_user):
    response = requests.post(
        f"{BASE_URL}/predict/batch",
        json={
            "model_name": MODEL_NAME,
            "rows": [
                "Мне очень нравится этот сервис",
                "",
                123,
                "Это ужасный продукт",
            ],
        },
        auth=auth(batch_funded_user),
        timeout=10,
    )

    assert response.status_code == 202

    body = response.json()

    accepted = body["accepted"]
    invalid_rows = body["invalid_rows"]

    assert len(accepted) == 2
    assert len(invalid_rows) == 2

    assert [item["row"] for item in accepted] == [1, 4]
    assert [item["row"] for item in invalid_rows] == [2, 3]

    task_ids = [
        item["task_id"]
        for item in accepted
    ]

    for task_id in task_ids:
        prediction = wait_for_prediction(
            batch_funded_user,
            task_id,
        )

        assert prediction["status"] == "completed"
        assert prediction["charged"] == "10.00"

    assert get_balance(batch_funded_user) == "0.00"


def test_batch_without_money(registered_user):
    response = requests.post(
        f"{BASE_URL}/predict/batch",
        json={
            "model_name": MODEL_NAME,
            "rows": [
                "Первая корректная строка",
                "Вторая корректная строка",
            ],
        },
        auth=auth(registered_user),
        timeout=10,
    )

    assert response.status_code == 402
    assert get_balance(registered_user) == "0.00"
