import json
import os

import pika
from pydantic import ValidationError

from database import SessionLocal
from rabbitmq import QUEUE_NAME, get_connection
from schemas import MLTaskMessage
from services import complete_ml_task


WORKER_ID = os.getenv("WORKER_ID", "worker")


def make_demo_prediction(text: str) -> dict[str, object]:
    normalized_text = text.lower()

    positive_words = (
        "хорош",
        "отлич",
        "нрав",
        "класс",
        "люблю",
    )

    is_positive = any(word in normalized_text for word in positive_words)

    return {
        "sentiment": "positive" if is_positive else "neutral",
        "input_length": len(text),
    }


def process_message(
    channel,
    method,
    properties,
    body: bytes,
) -> None:
    session = SessionLocal()

    try:
        raw_message = json.loads(body.decode("utf-8"))

        task_message = MLTaskMessage.model_validate(raw_message)

        print(f"[{WORKER_ID}] Получена задача {task_message.task_id}")

        prediction = make_demo_prediction(task_message.features.text)

        complete_ml_task(
            session=session,
            task_id=task_message.task_id,
            prediction_data={
                **prediction,
                "worker_id": WORKER_ID,
            },
            invalid_rows=[],
        )

        session.commit()

        print(f"[{WORKER_ID}] Задача {task_message.task_id} выполнена")

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except (ValidationError, ValueError, json.JSONDecodeError) as error:
        session.rollback()

        print(f"[{WORKER_ID}] Ошибка обработки: {error}")

        channel.basic_ack(delivery_tag=method.delivery_tag)

    except Exception as error:
        session.rollback()

        print(f"[{WORKER_ID}] Неожиданная ошибка: {error}")

        channel.basic_nack(
            delivery_tag=method.delivery_tag,
            requeue=True,
        )

    finally:
        session.close()


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
