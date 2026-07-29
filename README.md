# ML Service

Учебный проект ML-сервиса на Python.

В проекте есть:

* пользователь;
* отдельный баланс;
* ML-задачи;
* демонстрационная модель;
* результаты предсказаний;
* транзакции.

Валидные данные отправляются в модель, ошибочные строки возвращаются отдельно. Средства списываются только после успешного выполнения задачи.

## Запуск

1. Создать `.env` из примера:

```bat
copy .env.example .env
```

2. Запустить сервисы:

```bat
docker compose up --build
```

После запуска:

* приложение — http://localhost
* FastAPI docs — http://localhost/docs
* RabbitMQ — http://localhost:15672

Логин и пароль RabbitMQ:

```text
guest / guest
```

Остановка:

```bat
docker compose down
```

## Сервисы

Проект запускает четыре контейнера:

* `app` — FastAPI;
* `web-proxy` — Nginx;
* `database` — PostgreSQL;
* `rabbitmq` — RabbitMQ.

FastAPI не публикует порт напрямую: запросы идут через Nginx.
