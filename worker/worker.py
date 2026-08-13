import json
import os

import pika
import requests
from pydantic import ValidationError
from transformers import pipeline

from schemas import MLTaskMessage


QUEUE_NAME = "ml_tasks"

WORKER_ID = os.getenv("WORKER_ID", "worker")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

APP_BASE_URL = os.getenv(
    "APP_BASE_URL",
    "http://app:8000",
)

MODEL_NAME = "cointegrated/rubert-tiny-sentiment-balanced"


print(f"[{WORKER_ID}] Загрузка ML-модели...")

classifier = pipeline(
    "text-classification",
    model=MODEL_NAME,
    device=-1,
)

print(f"[{WORKER_ID}] ML-модель загружена")


def get_connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(
        username=RABBITMQ_USER,
        password=RABBITMQ_PASSWORD,
    )

    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
    )

    return pika.BlockingConnection(parameters)


def make_prediction(text: str) -> dict[str, object]:
    result = classifier(
        text,
        truncation=True,
    )[0]

    return {
        "sentiment": result["label"],
        "score": round(float(result["score"]), 6),
        "worker_id": WORKER_ID,
    }


def save_result(
    task_id: int,
    prediction: dict[str, object],
) -> None:
    response = requests.post(
        f"{APP_BASE_URL}/internal/tasks/{task_id}/result",
        json={
            "prediction": prediction,
        },
        timeout=15,
    )

    response.raise_for_status()


def process_message(
    channel,
    method,
    properties,
    body: bytes,
) -> None:
    try:
        raw_message = json.loads(body.decode("utf-8"))

        task = MLTaskMessage.model_validate(raw_message)

        print(f"[{WORKER_ID}] Получена задача {task.task_id}")

        prediction = make_prediction(task.features.text)

        print(
            f"[{WORKER_ID}] Prediction: "
            f"{prediction['sentiment']} "
            f"({prediction['score']})"
        )

        save_result(
            task_id=task.task_id,
            prediction=prediction,
        )

        channel.basic_ack(delivery_tag=method.delivery_tag)

        print(f"[{WORKER_ID}] Задача {task.task_id} выполнена")

    except (
        ValidationError,
        json.JSONDecodeError,
    ) as error:
        print(f"[{WORKER_ID}] Ошибка данных: {error}")

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as error:
        print(f"[{WORKER_ID}] Ошибка обработки: {error}")

        channel.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )


def main() -> None:
    connection = get_connection()

    channel = connection.channel()

    channel.queue_declare(
        queue=QUEUE_NAME,
        durable=True,
    )

    channel.basic_qos(
        prefetch_count=1,
    )

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_message,
    )

    print(f"[{WORKER_ID}] Ожидание задач...")

    channel.start_consuming()


if __name__ == "__main__":
    main()
