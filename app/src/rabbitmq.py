import json
import os
from typing import Any

import pika


QUEUE_NAME = "ml_tasks"


def get_connection() -> pika.BlockingConnection:
    host = os.getenv("RABBITMQ_HOST", "rabbitmq")
    port = int(os.getenv("RABBITMQ_PORT", "5672"))

    credentials = pika.PlainCredentials(
        username=os.getenv("RABBITMQ_USER", "guest"),
        password=os.getenv("RABBITMQ_PASSWORD", "guest"),
    )

    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
    )

    return pika.BlockingConnection(parameters)


def publish_ml_task(message: dict[str, Any]) -> None:
    connection = get_connection()

    try:
        channel = connection.channel()

        channel.queue_declare(
            queue=QUEUE_NAME,
            durable=True,
        )

        channel.basic_publish(
            exchange="",
            routing_key=QUEUE_NAME,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
            ),
        )
    finally:
        connection.close()