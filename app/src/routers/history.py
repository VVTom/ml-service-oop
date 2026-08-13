from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from dependencies import get_current_user, get_db
from models import User
from schemas import (
    PredictionHistoryItem,
    TransactionHistoryItem,
)
from services import (
    get_prediction_history,
    get_transaction_history,
)


router = APIRouter(
    prefix="/history",
    tags=["history"],
)


@router.get(
    "/transactions",
    response_model=list[TransactionHistoryItem],
)
def read_transaction_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TransactionHistoryItem]:
    transactions = get_transaction_history(
        session=db,
        user_id=current_user.id,
    )

    return [
        TransactionHistoryItem(
            id=transaction.id,
            operation_type=transaction.operation_type.value,
            amount=transaction.amount,
            task_id=transaction.task_id,
            created_at=transaction.created_at,
        )
        for transaction in transactions
    ]


@router.get(
    "/predictions",
    response_model=list[PredictionHistoryItem],
)
def read_prediction_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PredictionHistoryItem]:
    tasks = get_prediction_history(
        session=db,
        user_id=current_user.id,
    )

    return [
        PredictionHistoryItem(
            task_id=task.id,
            model_name=task.model.name,
            status=task.status.value,
            charged=(
                task.transaction.amount
                if task.transaction is not None
                else Decimal("0.00")
            ),
            created_at=task.created_at,
            completed_at=task.completed_at,
            prediction=(
                task.result.prediction_data if task.result is not None else None
            ),
        )
        for task in tasks
    ]
