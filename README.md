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
- Docker Compose;
- интеграционный тест API.

Средства списываются с баланса только после успешного выполнения ML-задачи. Повторная обработка завершённой задачи не приводит к повторному списанию.

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

## Сервисы Docker Compose

Проект запускает пять сервисов:

- `app` — FastAPI-приложение;
- `web-proxy` — Nginx;
- `database` — PostgreSQL;
- `rabbitmq` — RabbitMQ;
- `telegram-bot` — Telegram-бот.

FastAPI доступен через Nginx.

Для `app` настроен healthcheck через `/health`.

RabbitMQ пока запускается как отдельный сервис и будет использоваться на следующих этапах проекта.

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

Endpoints разделены по отдельным файлам в `app/src/routers`.

Доступные endpoints:

- `POST /auth/register` — регистрация;
- `POST /auth/login` — вход;
- `GET /users/me` — данные пользователя;
- `GET /balance` — просмотр баланса;
- `POST /balance/topup` — пополнение баланса;
- `POST /predict` — выполнение предсказания;
- `GET /history/transactions` — история транзакций;
- `GET /history/predictions` — история предсказаний.

Для защищённых запросов используется HTTP Basic Authentication.

Swagger:

```text
http://localhost/docs
```

На текущем этапе `/predict` использует простую демонстрационную функцию определения тональности текста.

## Telegram-бот

Telegram-бот работает с REST API и поддерживает команды:

- `/start`
- `/login`
- `/logout`
- `/balance`
- `/topup 100`
- `/predict sentiment-model текст`
- `/transactions`
- `/history`

Пример:

```text
/login
```

После авторизации:

```text
/topup 100
/predict sentiment-model Мне нравится этот сервис
/history
```

## Тестирование

Для проверки REST API используется:

```text
api_smoke_test.py
```

Запуск:

```bat
python api_smoke_test.py
```

Тест проверяет:

- регистрацию и вход;
- неправильный пароль;
- работу авторизации;
- пополнение баланса;
- валидацию данных;
- выполнение предсказания;
- списание средств;
- недостаточный баланс;
- историю транзакций;
- историю предсказаний.

При успешном прохождении теста:

```text
ВСЕ ИНТЕГРАЦИОННЫЕ ТЕСТЫ УСПЕШНО ПРОЙДЕНЫ
```

## Структура проекта

```text
ml-service-oop/
├── app/
│   ├── Dockerfile
│   └── src/
│       ├── routers/
│       │   ├── auth.py
│       │   ├── users.py
│       │   ├── balance.py
│       │   ├── predictions.py
│       │   └── history.py
│       ├── api.py
│       ├── database.py
│       ├── dependencies.py
│       ├── models.py
│       ├── schemas.py
│       └── services.py
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
- Pydantic
- SQLAlchemy
- PostgreSQL
- aiogram
- Nginx
- RabbitMQ
- Docker
- Docker Compose