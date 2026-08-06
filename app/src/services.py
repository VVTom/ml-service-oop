import hashlib
import os

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import (
    Balance,
    MLModel,
    MLTask,
    PredictionResult,
    TaskStatus,
    Transaction,
    TransactionType,
    User,
)


def validate_amount(amount: Decimal) -> Decimal:
    amount = Decimal(str(amount))

    if amount <= 0:
        raise ValueError("Сумма операции должна быть положительной")

    return amount


def get_user_by_login(
    session: Session,
    login: str,
) -> User:
    user = session.scalar(select(User).where(User.login == login))

    if user is None:
        raise ValueError(f"Пользователь {login!r} не найден")

    return user


def get_model_by_name(
    session: Session,
    name: str,
) -> MLModel:
    ml_model = session.scalar(select(MLModel).where(MLModel.name == name))

    if ml_model is None:
        raise ValueError(f"ML-модель {name!r} не найдена")

    if not ml_model.is_active:
        raise ValueError(f"ML-модель {name!r} недоступна")

    return ml_model


def get_balance(
    session: Session,
    user_id: int,
    lock: bool = False,
) -> Balance:
    statement = select(Balance).where(Balance.user_id == user_id)

    if lock:
        statement = statement.with_for_update()

    balance = session.scalar(statement)

    if balance is None:
        raise ValueError(f"Баланс пользователя с id={user_id} не найден")

    return balance


def credit_balance(
    session: Session,
    user_id: int,
    amount: Decimal,
) -> Transaction:
    amount = validate_amount(amount)

    balance = get_balance(
        session=session,
        user_id=user_id,
        lock=True,
    )

    balance.amount += amount

    transaction = Transaction(
        user_id=user_id,
        operation_type=TransactionType.CREDIT,
        amount=amount,
    )

    session.add(transaction)
    session.flush()

    return transaction


def create_ml_task(
    session: Session,
    user_id: int,
    model_id: int,
    input_data: dict[str, Any],
) -> MLTask:
    user = session.get(User, user_id)

    if user is None:
        raise ValueError(f"Пользователь с id={user_id} не найден")

    ml_model = session.get(MLModel, model_id)

    if ml_model is None:
        raise ValueError(f"ML-модель с id={model_id} не найдена")

    if not ml_model.is_active:
        raise ValueError("ML-модель сейчас недоступна")

    task = MLTask(
        user_id=user_id,
        model_id=model_id,
        status=TaskStatus.PENDING,
        input_data=input_data,
    )

    session.add(task)
    session.flush()

    return task


def complete_ml_task(
    session: Session,
    task_id: int,
    prediction_data: dict[str, Any],
    invalid_rows: list[dict[str, Any]] | None = None,
) -> PredictionResult:
    task = session.scalar(select(MLTask).where(MLTask.id == task_id).with_for_update())

    if task is None:
        raise ValueError(f"ML-задача с id={task_id} не найдена")

    # Повторная обработка не должна повторно списывать деньги.
    if task.status == TaskStatus.COMPLETED and task.charged:
        if task.result is None:
            raise RuntimeError("Задача завершена, но результат отсутствует")

        return task.result

    if task.status == TaskStatus.FAILED:
        raise ValueError("Нельзя завершить ошибочную задачу")

    ml_model = session.get(MLModel, task.model_id)

    if ml_model is None:
        raise ValueError("Связанная ML-модель не найдена")

    if not ml_model.is_active:
        raise ValueError("ML-модель сейчас недоступна")

    balance = get_balance(
        session=session,
        user_id=task.user_id,
        lock=True,
    )

    if balance.amount < ml_model.cost:
        raise ValueError("Недостаточно средств на балансе")

    result = PredictionResult(
        task_id=task.id,
        prediction_data=prediction_data,
        invalid_rows=invalid_rows or [],
    )

    session.add(result)

    if ml_model.cost > 0:
        balance.amount -= ml_model.cost

        transaction = Transaction(
            user_id=task.user_id,
            task_id=task.id,
            operation_type=TransactionType.DEBIT,
            amount=ml_model.cost,
        )

        session.add(transaction)

    task.status = TaskStatus.COMPLETED
    task.charged = True
    task.completed_at = datetime.now(timezone.utc)

    session.flush()

    return result


def get_transaction_history(
    session: Session,
    user_id: int,
) -> list[Transaction]:
    transactions = session.scalars(
        select(Transaction)
        .where(Transaction.user_id == user_id)
        .order_by(
            Transaction.created_at.desc(),
            Transaction.amount.desc(),
        )
    ).all()

    return list(transactions)


def get_prediction_history(
    session: Session,
    user_id: int,
) -> list[MLTask]:
    tasks = session.scalars(
        select(MLTask)
        .where(
            MLTask.user_id == user_id,
            MLTask.status == TaskStatus.COMPLETED,
        )
        .order_by(MLTask.created_at.desc())
    ).all()

    return list(tasks)


def hash_password(password: str) -> str:
    salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000,
    )

    return f"{salt.hex()}${password_hash.hex()}"


def verify_password(
    password: str,
    stored_password_hash: str,
) -> bool:
    try:
        salt_hex, password_hash_hex = stored_password_hash.split("$", maxsplit=1)
    except ValueError:
        return False

    salt = bytes.fromhex(salt_hex)

    calculated_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        100_000,
    )

    return calculated_hash.hex() == password_hash_hex


def register_user(
    session: Session,
    login: str,
    password: str,
) -> User:
    existing_user = session.scalar(select(User).where(User.login == login))

    if existing_user is not None:
        raise ValueError(f"Пользователь с таким логином уже существует")

    user = User(
        login=login,
        password_hash=hash_password(password),
    )

    user.balance = Balance(
        amount=Decimal("0.00"),
    )

    session.add(user)
    session.flush()

    return user
