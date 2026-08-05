from decimal import Decimal

from sqlalchemy import func, select

from database import SessionLocal
from models import Balance, Transaction, TransactionType
from services import (
    complete_ml_task,
    create_ml_task,
    credit_balance,
    get_model_by_name,
    get_transaction_history,
    get_user_by_login,
)


def run_demo() -> None:
    with SessionLocal.begin() as session:
        user = get_user_by_login(
            session=session,
            login="demo_user",
        )

        ml_model = get_model_by_name(
            session=session,
            name="sentiment-model",
        )

        balance_before = session.scalar(
            select(Balance.amount).where(Balance.user_id == user.id)
        )

        credit_balance(
            session=session,
            user_id=user.id,
            amount=Decimal("25.00"),
        )

        task = create_ml_task(
            session=session,
            user_id=user.id,
            model_id=ml_model.id,
            input_data={"text": "Этот ML-сервис работает отлично"},
        )

        first_result = complete_ml_task(
            session=session,
            task_id=task.id,
            prediction_data={
                "sentiment": "positive",
                "probability": 0.97,
            },
            invalid_rows=[],
        )

        balance_after_first_call = session.scalar(
            select(Balance.amount).where(Balance.user_id == user.id)
        )

        # Повторно обрабатываем ту же задачу.
        second_result = complete_ml_task(
            session=session,
            task_id=task.id,
            prediction_data={
                "sentiment": "positive",
                "probability": 0.97,
            },
        )

        balance_after_second_call = session.scalar(
            select(Balance.amount).where(Balance.user_id == user.id)
        )

        debit_count = session.scalar(
            select(func.count(Transaction.id)).where(
                Transaction.task_id == task.id,
                Transaction.operation_type == TransactionType.DEBIT,
            )
        )

        history = get_transaction_history(
            session=session,
            user_id=user.id,
        )

        print(f"Баланс до операций: {balance_before}")
        print(f"Баланс после пополнения и предсказания: {balance_after_first_call}")
        print(f"Баланс после повторной обработки: {balance_after_second_call}")
        print(f"ID первого результата: {first_result.id}")
        print(f"ID повторного результата: {second_result.id}")
        print(f"Количество списаний задачи: {debit_count}")
        print(f"Транзакций пользователя: {len(history)}")

        assert first_result.id == second_result.id
        assert balance_after_first_call == balance_after_second_call
        assert debit_count == 1

    print("Демонстрационный сценарий успешно завершён!")


if __name__ == "__main__":
    run_demo()
