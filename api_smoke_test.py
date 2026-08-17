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


def get_current_balance() -> str:
    status_code, body = send_request(
        method="GET",
        path="/balance",
        authenticated=True,
    )

    assert_status(
        test_name="Получение текущего баланса",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    return body["balance"]


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

    initial_balance = get_current_balance()

    assert initial_balance == "0.00", (
        f"Ожидался начальный баланс 0.00, получено: {initial_balance}"
    )

    print("[OK] Начальный баланс нового пользователя равен 0.00")

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

    status_code, body = send_request(
        method="POST",
        path="/auth/login",
        payload={
            "login": TEST_LOGIN,
            "password": TEST_PASSWORD,
        },
    )

    assert_status(
        test_name="Повторная авторизация",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    assert body["login"] == TEST_LOGIN, (
        f"Повторная авторизация вернула неверного пользователя: {body}"
    )

    print("[OK] Повторная авторизация работает")

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

    assert get_current_balance() == "0.00", (
        "После ошибочного пополнения баланс изменился"
    )

    print("[OK] Ошибочное пополнение не изменяет баланс")

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

    assert get_current_balance() == "10.00", (
        "Запрос к неизвестной модели изменил баланс"
    )

    print("[OK] Ошибка неизвестной модели не списывает кредиты")

    status_code, body = send_request(
        method="POST",
        path="/predict",
        payload={
            "model_name": "sentiment-model",
            "text": "",
        },
        authenticated=True,
    )

    assert_status(
        test_name="Некорректный пустой ML-запрос",
        actual_status=status_code,
        expected_status=422,
        response_body=body,
    )

    assert get_current_balance() == "10.00", (
        "Некорректный ML-запрос изменил баланс"
    )

    print("[OK] Некорректные входные данные не приводят к списанию")

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

    assert get_current_balance() == "0.00", (
        "После отказа из-за недостаточного баланса баланс изменился"
    )

    print("[OK] При недостаточном балансе списание отсутствует")

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

    # 14. Пополняем баланс для batch из двух валидных строк.
    status_code, body = send_request(
        method="POST",
        path="/balance/topup",
        payload={
            "amount": 20,
        },
        authenticated=True,
    )

    assert_status(
        test_name="Пополнение баланса для batch-запроса",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    assert body["balance"] == "20.00", (
        f"После пополнения ожидался баланс 20.00, но получено: {body}"
    )

    # 15. Batch: две корректные строки и две некорректные.
    batch_payload = {
        "model_name": "sentiment-model",
        "rows": [
            "Мне очень нравится этот сервис",
            "",
            123,
            "Это ужасный продукт",
        ],
    }

    status_code, batch_body = send_request(
        method="POST",
        path="/predict/batch",
        payload=batch_payload,
        authenticated=True,
    )

    assert_status(
        test_name="Batch-запрос с частично некорректными данными",
        actual_status=status_code,
        expected_status=202,
        response_body=batch_body,
    )

    accepted = batch_body["accepted"]
    invalid_rows = batch_body["invalid_rows"]

    assert len(accepted) == 2, (
        f"Ожидалось 2 принятые строки, получено: {accepted}"
    )

    assert len(invalid_rows) == 2, (
        f"Ожидалось 2 отклонённые строки, получено: {invalid_rows}"
    )

    assert [item["row"] for item in accepted] == [1, 4], (
        f"Ожидались принятые строки 1 и 4, получено: {accepted}"
    )

    assert [item["row"] for item in invalid_rows] == [2, 3], (
        f"Ожидались отклонённые строки 2 и 3, получено: {invalid_rows}"
    )

    invalid_errors = {
        item["row"]: item["error"]
        for item in invalid_rows
    }

    assert invalid_errors[2] == "Пустая строка", (
        f"Некорректная ошибка для строки 2: {invalid_rows}"
    )

    assert invalid_errors[3] == "Значение должно быть строкой", (
        f"Некорректная ошибка для строки 3: {invalid_rows}"
    )

    print(
        "[OK] Backend вернул невалидные строки отдельно, "
        "а валидные принял в обработку"
    )

    batch_task_ids = [
        item["task_id"]
        for item in accepted
    ]

    for batch_task_id in batch_task_ids:
        batch_prediction = wait_for_prediction(batch_task_id)

        assert batch_prediction["status"] == "completed", (
            f"Batch-задача {batch_task_id} не завершена: {batch_prediction}"
        )

        assert batch_prediction["charged"] == "10.00", (
            f"Для batch-задачи {batch_task_id} ожидалось списание 10.00: "
            f"{batch_prediction}"
        )

        batch_worker_id = batch_prediction["prediction"].get("worker_id")

        assert batch_worker_id in {"worker-1", "worker-2"}, (
            f"Некорректный worker_id batch-задачи {batch_task_id}: "
            f"{batch_prediction}"
        )

        print(
            f"[OK] Batch-задача {batch_task_id} завершена воркером "
            f"{batch_worker_id}"
        )

    # 16. За две валидные строки должно списаться ровно 20 кредитов.
    status_code, body = send_request(
        method="GET",
        path="/balance",
        authenticated=True,
    )

    assert_status(
        test_name="Баланс после batch-запроса",
        actual_status=status_code,
        expected_status=200,
        response_body=body,
    )

    assert body["balance"] == "0.00", (
        "После двух валидных строк ожидался баланс 0.00, "
        f"получено: {body}"
    )

    print("[OK] За batch списано только за две корректные строки")

    # 17. При нехватке денег batch не должен принимать задачи частично.
    status_code, body = send_request(
        method="POST",
        path="/predict/batch",
        payload={
            "model_name": "sentiment-model",
            "rows": [
                "Первая корректная строка",
                "Вторая корректная строка",
            ],
        },
        authenticated=True,
    )

    assert_status(
        test_name="Недостаточно средств для batch-запроса",
        actual_status=status_code,
        expected_status=402,
        response_body=body,
    )

    print(
        "[OK] Batch-запрос целиком отклонён при недостаточном балансе"
    )

    # 18. Повторно проверяем историю транзакций и сопоставляем её с действиями.
    status_code, transactions = send_request(
        method="GET",
        path="/history/transactions",
        authenticated=True,
    )

    assert_status(
        test_name="Финальная проверка истории транзакций",
        actual_status=status_code,
        expected_status=200,
        response_body=transactions,
    )

    credit_transactions = [
        transaction
        for transaction in transactions
        if transaction["operation_type"] == "credit"
    ]

    debit_transactions = [
        transaction
        for transaction in transactions
        if transaction["operation_type"] == "debit"
    ]

    assert len(credit_transactions) == 2, (
        f"Ожидалось 2 пополнения, получено: {credit_transactions}"
    )

    assert len(debit_transactions) == 3, (
        f"Ожидалось 3 списания, получено: {debit_transactions}"
    )

    successful_task_ids = {
        task_id,
        *batch_task_ids,
    }

    debit_task_ids = {
        transaction["task_id"]
        for transaction in debit_transactions
    }

    assert debit_task_ids == successful_task_ids, (
        "Списания не совпадают с успешно выполненными ML-задачами. "
        f"Ожидались task_id={successful_task_ids}, "
        f"получены task_id={debit_task_ids}"
    )

    print(
        "[OK] История транзакций соответствует пополнениям "
        "и успешно выполненным ML-задачам"
    )

    # 19. Проверяем, что batch-задачи появились в истории.
    status_code, predictions = send_request(
        method="GET",
        path="/history/predictions",
        authenticated=True,
    )

    assert_status(
        test_name="История после batch-запроса",
        actual_status=status_code,
        expected_status=200,
        response_body=predictions,
    )

    history_task_ids = {
        prediction["task_id"]
        for prediction in predictions
    }

    assert all(
        batch_task_id in history_task_ids
        for batch_task_id in batch_task_ids
    ), (
        f"Не все batch-задачи найдены в истории: {batch_task_ids}"
    )

    print("[OK] Batch-задачи присутствуют в истории предсказаний")

    print()
    print("=" * 70)
    print("ВСЕ ОБЯЗАТЕЛЬНЫЕ СЦЕНАРИИ ЗАДАНИЯ №7 УСПЕШНО ПРОЙДЕНЫ")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()
