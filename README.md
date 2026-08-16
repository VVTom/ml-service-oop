# ML Service

Учебный проект ML-сервиса на Python.

В проекте реализованы:

- пользователи и авторизация;
- баланс пользователя;
- ML-задачи и результаты предсказаний;
- транзакции;
- PostgreSQL и SQLAlchemy ORM;
- REST API на FastAPI;
- Telegram-бот;
- RabbitMQ;
- два независимых ML-воркера;
- Web-интерфейс на Streamlit;
- реальная ML-модель для анализа тональности текста;
- Docker Compose;
- интеграционный тест API.

Средства списываются с баланса после успешного выполнения ML-задачи.

## Запуск

Создать `.env` файлы из примеров.

Для Windows:

```bat
copy .env.example .env
copy app\.env.example app\.env
copy telegram_bot\.env.example telegram_bot\.env
```

В `telegram_bot/.env` указать токен Telegram-бота.

Запустить проект:

```bat
docker compose up -d --build
```

Проверить контейнеры:

```bat
docker compose ps
```

Остановка:

```bat
docker compose down
```

После запуска доступны:

- приложение — `http://localhost`
- Swagger — `http://localhost/docs`
- healthcheck — `http://localhost/health`
- RabbitMQ — `http://localhost:15672`

## Docker Compose

Проект запускает восемь сервисов:

- `app` — FastAPI;
- `web-proxy` — Nginx;
- `database` — PostgreSQL;
- `rabbitmq` — RabbitMQ;
- `telegram-bot` — Telegram-бот;
- `worker-1` — обработчик ML-задач;
- `worker-2` — обработчик ML-задач;
- `web-ui` — Web-интерфейс на Streamlit.

ML-воркеры собираются из отдельного каталога `worker` и имеют собственные `Dockerfile` и `requirements.txt`.

## База данных

Используются PostgreSQL и SQLAlchemy ORM.

Основные сущности:

- `User`;
- `Balance`;
- `MLModel`;
- `MLTask`;
- `PredictionResult`;
- `Transaction`.

Инициализация базы:

```bat
docker compose exec app python init_db.py
```

## REST API

Доступные endpoints:

- `POST /auth/register` — регистрация;
- `POST /auth/login` — вход;
- `GET /users/me` — данные пользователя;
- `GET /balance` — просмотр баланса;
- `POST /balance/topup` — пополнение баланса;
- `POST /predict` — создание одиночной ML-задачи;
- `POST /predict/batch` — пакетный ML-запрос с частичной валидацией;
- `GET /history/transactions` — история транзакций;
- `GET /history/predictions` — история предсказаний.

Для защищённых запросов используется HTTP Basic Authentication.

Swagger:

```text
http://localhost/docs
```

## RabbitMQ и ML-воркеры

ML-задачи обрабатываются асинхронно через RabbitMQ.

После запроса:

```text
POST /predict
```

FastAPI создаёт задачу со статусом `pending` и отправляет сообщение в очередь:

```text
ml_tasks
```

К очереди подключены два воркера:

```text
worker-1
worker-2
```

RabbitMQ распределяет задачи между доступными воркерами.

Воркеры:

- получают сообщение из RabbitMQ;
- проверяют входные данные через Pydantic;
- выполняют предсказание с помощью ML-модели;
- отправляют результат обратно в FastAPI через внутренний REST endpoint;
- FastAPI сохраняет результат в PostgreSQL;
- после успешной обработки задача переводится в статус `completed`.

Пример ответа `/predict`:

```json
{
  "task_id": 19,
  "status": "pending"
}
```

После обработки результат можно получить через:

```text
GET /history/predictions
```

Пример результата:

```json
{
  "sentiment": "positive",
  "score": 0.986285,
  "worker_id": "worker-1"
}
```

При ручной проверке с реальной ML-моделью задачи распределились между двумя воркерами:

```text
worker-1: задачи 16, 17
worker-2: задачи 15, 18
```

## ML-модель

Для определения тональности текста используется готовая модель Hugging Face:

```text
cointegrated/rubert-tiny-sentiment-balanced
```

Модель возвращает один из классов:

- `positive`;
- `neutral`;
- `negative`.

Для inference используются Hugging Face Transformers и PyTorch.

Worker не зависит напрямую от FastAPI, SQLAlchemy и PostgreSQL.

После выполнения предсказания worker отправляет результат в приложение по HTTP, а уже FastAPI выполняет бизнес-логику сохранения результата и списания средств.


## Web-интерфейс

Web-интерфейс реализован на Streamlit и работает поверх существующего REST API.

Frontend не дублирует бизнес-логику backend.

Доступные возможности:

- главная страница;
- регистрация и авторизация;
- личный кабинет;
- просмотр и пополнение баланса;
- ML-анализ одного текста;
- обработка нескольких строк;
- отображение отклонённых данных;
- история транзакций;
- история предсказаний.

Web-интерфейс доступен по адресу:

```text
http://localhost:8501
```

После отправки ML-запроса frontend получает `task_id`, ожидает завершения асинхронной задачи и отображает результат модели, worker, статус и списанную сумму.

### Пакетная обработка

Во вкладке пакетного анализа Streamlit передаёт весь набор строк в backend endpoint:

```text
POST /predict/batch
```

Правила валидации не дублируются во frontend. Backend сам разделяет входные данные на:

- `accepted` — корректные строки, для которых создаются ML-задачи;
- `invalid_rows` — ошибочные строки с причиной отклонения.

Корректные строки продолжают обрабатываться, даже если часть пакета некорректна. Списание происходит только за успешно обработанные корректные строки.

## Пакетный REST API

Пример запроса:

```json
{
  "model_name": "sentiment-model",
  "rows": [
    "Мне очень нравится этот сервис",
    "",
    123,
    "Это ужасный продукт"
  ]
}
```

Пример ответа:

```json
{
  "accepted": [
    {
      "row": 1,
      "task_id": 40,
      "status": "pending"
    },
    {
      "row": 4,
      "task_id": 41,
      "status": "pending"
    }
  ],
  "invalid_rows": [
    {
      "row": 2,
      "value": "",
      "error": "Пустая строка"
    },
    {
      "row": 3,
      "value": 123,
      "error": "Значение должно быть строкой"
    }
  ]
}
```

Если средств недостаточно для всех корректных строк, пакет целиком отклоняется с `HTTP 402`, чтобы не создавать непредсказуемую частичную обработку по балансу.

## Telegram-бот

Telegram-бот работает с текущим асинхронным REST API.

Основные команды:

```text
/start
/login
/logout
/balance
/topup 100
/predict sentiment-model Мне нравится этот сервис
/batch Отличный сервис | | Это ужасный продукт
/history
/transactions
```

Команда `/predict` получает `task_id`, ожидает завершения задачи через историю предсказаний и показывает тональность, confidence score, worker и списанную сумму.

Команда `/batch` использует `POST /predict/batch`. Ошибочные строки выводятся пользователю отдельно, а корректные отправляются на ML-обработку.

Пример итогового ответа:

```text
Результаты пакетной обработки ✅

Отклонённые строки:
Строка 2: Пустая строка

Обработанные строки:
Строка 1: positive, 99.38%, списано 10.00
Строка 3: negative, 76.58%, списано 10.00
```

## Тестирование

Запуск интеграционного теста:

```bat
python api_smoke_test.py
```

Тест проверяет:

- регистрацию и авторизацию;
- работу баланса;
- валидацию данных;
- создание ML-задачи;
- отправку задачи на асинхронную обработку;
- обработку задачи одним из ML-воркеров;
- завершение задачи;
- списание средств;
- историю транзакций;
- историю предсказаний;
- пакетный endpoint `/predict/batch`;
- частично некорректные данные;
- возврат `invalid_rows`;
- обработку только корректных строк;
- списание только за корректные строки;
- отказ batch-запроса при недостаточном балансе.

При успешном прохождении:

```text
ВСЕ ИНТЕГРАЦИОННЫЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ
```

Для проверки RabbitMQ:

```bat
docker compose exec rabbitmq rabbitmqctl list_queues name messages_ready messages_unacknowledged consumers
```

Для просмотра работы воркеров:

```bat
docker compose logs worker-1
docker compose logs worker-2
```

## Структура проекта

```text
ml-service-oop/
├── app/
│   ├── Dockerfile
│   └── src/
│       ├── routers/
│       │   ├── auth.py
│       │   ├── balance.py
│       │   ├── history.py
│       │   ├── internal.py
│       │   ├── predictions.py
│       │   └── users.py
│       ├── api.py
│       ├── database.py
│       ├── dependencies.py
│       ├── models.py
│       ├── rabbitmq.py
│       ├── schemas.py
│       └── services.py
│
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── schemas.py
│   └── worker.py
│
├── web-ui/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── api_client.py
│   └── app.py
│
├── telegram_bot/
│   ├── Dockerfile
│   ├── bot.py
│   └── requirements.txt
│
├── web-proxy/
├── api_smoke_test.py
├── docker-compose.yml
└── README.md
```

## Используемые технологии

- Python
- FastAPI
- Streamlit
- Pydantic
- SQLAlchemy
- PostgreSQL
- RabbitMQ
- pika
- Hugging Face Transformers
- PyTorch
- aiogram
- Nginx
- Docker
- Docker Compose
