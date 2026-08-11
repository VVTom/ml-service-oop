import base64
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BASE_URL = "http://localhost"

TEST_LOGIN = f"api_test_{int(time.time())}"
TEST_PASSWORD = "test_password_123"


def make_basic_auth_header(login: str, password: str) -> str:
    credentials = f"{login}:{password}".encode("utf-8")
    encoded_credentials = base64.b64encode(credentials).decode("ascii")

    return f"Basic {encoded_credentials}"


def send_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    authenticated: bool = False,
) -> tuple[int, Any]:
    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        headers["Content-Type"] = "application/json"

    if authenticated:
        headers["Authorization"] = make_basic_auth_header(
            TEST_LOGIN,
            TEST_PASSWORD,
        )

    body = None

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(
        url=f"{BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")

            parsed_body = json.loads(response_body) if response_body else None

            return response.status, parsed_body

    except HTTPError as error:
        response_body = error.read().decode("utf-8")

        parsed_body = json.loads(response_body) if response_body else None

        return error.code, parsed_body

    except URLError as error:
        raise RuntimeError(
            f"Не удалось подключиться к API: {error.reason}. "
            "Убедитесь, что Docker Compose запущен."
        ) from error


def assert_status(
    test_name: str,
    actual_status: int,
    expected_status: int,
    response_body: Any,
) -> None:
    if actual_status != expected_status:
        raise AssertionError(
            f"\nТест провален: {test_name}\n"
            f"Ожидался статус: {expected_status}\n"
            f"Получен статус: {actual_status}\n"
            f"Ответ API: {response_body}"
        )

    print(f"[OK] {test_name}: HTTP {actual_status}")


def wait_for_prediction(
    task_id: int,
    timeout: float = 10.0,
    interval: float = 0.2,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        status_code, predictions = send_request(
            method="GET",
            path="/history/predictions",
            authenticated=True,
        )

        assert_status(
            test_name="Получение истории предсказаний во время ожидания",
            actual_status=status_code,
            expected_status=200,
            response_body=predictions,
        )

        for prediction in predictions:
            if prediction["task_id"] == task_id:
                return prediction

        time.sleep(interval)

    raise AssertionError(
        f"Задача {task_id} не завершилась за {timeout} секунд"
    )


def run_tests() -> None:
    print("=" * 70)
    print("Запуск интеграционных тестов REST API")
    print(f"Тестовый пользователь: {TEST_LOGIN}")
    print("=" * 70)

    # 1. Проверяем доступность API.
    status_code, body = send_request(
        method="GET",
        path="/health",
    )

    assert_status(
        test_name="API доступен",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    # 2. Успешная регистрация.
    registration_payload = {
        "login": TEST_LOGIN,
        "password": TEST_PASSWORD,
    }

    status_code, body = send_request(
        method="POST",
        path="/auth/register",
        payload=registration_payload,
    )

    assert_status(
        test_name="Регистрация нового пользователя",
        actual_status=status_code,
        expected_status=201,
        response_body=body,
    )

    # 3. Успешный логин.
    status_code, body = send_request(
        method="POST",
        path="/auth/login",
        payload={
            "login": TEST_LOGIN,
            "password": TEST_PASSWORD,
        },
    )

    assert_status(
        test_name="Успешный логин",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    assert body["login"] == TEST_LOGIN, (
        f"Ожидался пользователь {TEST_LOGIN}, получено: {body}"
    )

    print("[OK] Пользователь успешно авторизован")

    # 4. Логин с неверным паролем должен вернуть 401.
    status_code, body = send_request(
        method="POST",
        path="/auth/login",
        payload={
            "login": TEST_LOGIN,
            "password": "wrong_password",
        },
    )

    assert_status(
        test_name="Логин с неверным паролем",
        actual_status=status_code,
        expected_status=401,
        response_body=body,
    )

    # 5. Повторная регистрация должна вернуть 409.
    status_code, body = send_request(
        method="POST",
        path="/auth/register",
        payload=registration_payload,
    )

    assert_status(
        test_name="Повторная регистрация",
        actual_status=status_code,
        expected_status=409,
        response_body=body,
    )

    # 6. Запрос баланса без авторизации должен вернуть 401.
    status_code, body = send_request(
        method="GET",
        path="/balance",
    )

    assert_status(
        test_name="Доступ к балансу без авторизации",
        actual_status=status_code,
        expected_status=401,
        response_body=body,
    )

    # 7. Отрицательное пополнение должно вернуть 422.
    status_code, body = send_request(
        method="POST",
        path="/balance/topup",
        payload={
            "amount": -10,
        },
        authenticated=True,
    )

    assert_status(
        test_name="Отрицательное пополнение",
        actual_status=status_code,
        expected_status=422,
        response_body=body,
    )

    # 8. Пополняем баланс ровно на стоимость одного предсказания.
    status_code, body = send_request(
        method="POST",
        path="/balance/topup",
        payload={
            "amount": 10,
        },
        authenticated=True,
    )

    assert_status(
        test_name="Успешное пополнение баланса",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    assert body["balance"] == "10.00", (
        f"После пополнения ожидался баланс 10.00, но получено: {body}"
    )

    print("[OK] Баланс после пополнения равен 10.00")

    # 9. Неизвестная модель должна вернуть 400.
    status_code, body = send_request(
        method="POST",
        path="/predict",
        payload={
            "model_name": "unknown-model",
            "text": "Тест неизвестной модели",
        },
        authenticated=True,
    )

    assert_status(
        test_name="Запрос к неизвестной модели",
        actual_status=status_code,
        expected_status=400,
        response_body=body,
    )

    # 10. Успешный запрос на предсказание ставится в очередь RabbitMQ.
    status_code, body = send_request(
        method="POST",
        path="/predict",
        payload={
            "model_name": "sentiment-model",
            "text": "Мне нравится этот отличный сервис",
        },
        authenticated=True,
    )

    assert_status(
        test_name="ML-задача принята в обработку",
        actual_status=status_code,
        expected_status=202,
        response_body=body,
    )

    assert body["status"] == "pending", (
        f"Ожидался статус pending, получено: {body}"
    )

    task_id = body["task_id"]
    print(f"[OK] Задача {task_id} отправлена в RabbitMQ")

    # Ждём, пока один из воркеров обработает задачу.
    completed_prediction = wait_for_prediction(task_id)

    assert completed_prediction["status"] == "completed", (
        f"Ожидался статус completed, получено: {completed_prediction}"
    )

    worker_id = completed_prediction["prediction"].get("worker_id")

    assert worker_id in {"worker-1", "worker-2"}, (
        f"Не найден корректный worker_id: {completed_prediction}"
    )

    assert completed_prediction["charged"] == "10.00", (
        f"Ожидалось списание 10.00, получено: {completed_prediction}"
    )

    print(
        f"[OK] Задача {task_id} обработана асинхронно воркером {worker_id}"
    )

    status_code, body = send_request(
        method="GET",
        path="/balance",
        authenticated=True,
    )

    assert_status(
        test_name="Получение баланса после обработки ML-задачи",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    assert body["balance"] == "0.00", (
        f"После списания ожидался баланс 0.00, получено: {body}"
    )

    print("[OK] После обработки задачи баланс уменьшился до 0.00")

    # 11. Второе предсказание после списания должно вернуть 402.
    status_code, body = send_request(
        method="POST",
        path="/predict",
        payload={
            "model_name": "sentiment-model",
            "text": "Ещё одно предсказание",
        },
        authenticated=True,
    )

    assert_status(
        test_name="Недостаточно средств",
        actual_status=status_code,
        expected_status=402,
        response_body=body,
    )

    # 12. Проверяем историю транзакций.
    status_code, transactions = send_request(
        method="GET",
        path="/history/transactions",
        authenticated=True,
    )

    assert_status(
        test_name="Получение истории транзакций",
        actual_status=status_code,
        expected_status=200,
        response_body=transactions,
    )

    transaction_types = {transaction["operation_type"] for transaction in transactions}

    assert "credit" in transaction_types, "В истории отсутствует credit-транзакция"

    assert "debit" in transaction_types, "В истории отсутствует debit-транзакция"

    print("[OK] История содержит credit и debit")

    # 13. Проверяем историю предсказаний.
    status_code, predictions = send_request(
        method="GET",
        path="/history/predictions",
        authenticated=True,
    )

    assert_status(
        test_name="Получение истории предсказаний",
        actual_status=status_code,
        expected_status=200,
        response_body=predictions,
    )

    matching_predictions = [
        prediction
        for prediction in predictions
        if prediction["task_id"] == task_id
    ]

    assert len(matching_predictions) == 1, (
        f"Не найдена завершённая задача {task_id}: {predictions}"
    )

    assert matching_predictions[0]["status"] == "completed", (
        f"Некорректный статус задачи: {matching_predictions[0]}"
    )

    assert matching_predictions[0]["prediction"].get("worker_id") in {
        "worker-1",
        "worker-2",
    }, (
        f"В результате отсутствует корректный worker_id: "
        f"{matching_predictions[0]}"
    )

    print("[OK] История содержит завершённое предсказание с worker_id")

    print()
    print("=" * 70)
    print("ВСЕ ИНТЕГРАЦИОННЫЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
