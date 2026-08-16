from datetime import datetime, timezone
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from dependencies import (
    get_current_user,
    get_db,
)
from models import User
from rabbitmq import publish_ml_task
from schemas import (
    BatchAcceptedItem,
    BatchInvalidRow,
    BatchPredictionRequest,
    BatchPredictionResponse,
    PredictionAcceptedResponse,
    PredictionRequest,
)
from services import (
    create_ml_task,
    get_balance,
    get_model_by_name,
)


router = APIRouter(
    tags=["predictions"],
)


@router.post(
    "/predict",
    response_model=PredictionAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def predict(
    data: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionAcceptedResponse:
    try:
        ml_model = get_model_by_name(
            session=db,
            name=data.model_name,
        )

        balance = get_balance(
            session=db,
            user_id=current_user.id,
        )

        if balance.amount < ml_model.cost:
            raise ValueError("Недостаточно средств на балансе")

        task = create_ml_task(
            session=db,
            user_id=current_user.id,
            model_id=ml_model.id,
            input_data={
                "text": data.text,
            },
        )

        db.commit()
        db.refresh(task)

        message = {
            "task_id": task.id,
            "features": {
                "text": data.text,
            },
            "model": ml_model.name,
            "timestamp": (datetime.now(timezone.utc).isoformat()),
        }

        publish_ml_task(message)

        return PredictionAcceptedResponse(
            task_id=task.id,
            status=task.status.value,
        )

    except ValueError as error:
        db.rollback()

        message = str(error)

        if message == "Недостаточно средств на балансе":
            status_code = status.HTTP_402_PAYMENT_REQUIRED
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error


@router.post(
    "/predict/batch",
    response_model=BatchPredictionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def predict_batch(
    data: BatchPredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BatchPredictionResponse:
    try:
        ml_model = get_model_by_name(
            session=db,
            name=data.model_name,
        )

        valid_rows: list[tuple[int, str]] = []
        invalid_rows: list[BatchInvalidRow] = []

        for row_number, raw_value in enumerate(
            data.rows,
            start=1,
        ):
            if not isinstance(raw_value, str):
                invalid_rows.append(
                    BatchInvalidRow(
                        row=row_number,
                        value=raw_value,
                        error=("Значение должно быть строкой"),
                    )
                )
                continue

            cleaned_text = raw_value.strip()

            if not cleaned_text:
                invalid_rows.append(
                    BatchInvalidRow(
                        row=row_number,
                        value=raw_value,
                        error="Пустая строка",
                    )
                )
                continue

            if len(cleaned_text) > 5000:
                invalid_rows.append(
                    BatchInvalidRow(
                        row=row_number,
                        value=raw_value,
                        error=("Текст длиннее 5000 символов"),
                    )
                )
                continue

            valid_rows.append(
                (
                    row_number,
                    cleaned_text,
                )
            )

        if not valid_rows:
            return BatchPredictionResponse(
                accepted=[],
                invalid_rows=invalid_rows,
            )

        balance = get_balance(
            session=db,
            user_id=current_user.id,
        )

        total_cost = ml_model.cost * len(valid_rows)

        if balance.amount < total_cost:
            raise ValueError(
                "Недостаточно средств на балансе "
                f"для обработки {len(valid_rows)} "
                f"корректных строк. "
                f"Требуется: {total_cost}, "
                f"доступно: {balance.amount}"
            )

        accepted: list[BatchAcceptedItem] = []

        messages: list[dict[str, Any]] = []

        for row_number, text in valid_rows:
            task = create_ml_task(
                session=db,
                user_id=current_user.id,
                model_id=ml_model.id,
                input_data={
                    "text": text,
                    "source_row": row_number,
                },
            )

            accepted.append(
                BatchAcceptedItem(
                    row=row_number,
                    task_id=task.id,
                    status=task.status.value,
                )
            )

            messages.append(
                {
                    "task_id": task.id,
                    "features": {
                        "text": text,
                    },
                    "model": ml_model.name,
                    "timestamp": (datetime.now(timezone.utc).isoformat()),
                }
            )

        db.commit()

        for message in messages:
            publish_ml_task(message)

        return BatchPredictionResponse(
            accepted=accepted,
            invalid_rows=invalid_rows,
        )

    except ValueError as error:
        db.rollback()

        message = str(error)

        if message.startswith("Недостаточно средств на балансе"):
            status_code = status.HTTP_402_PAYMENT_REQUIRED
        else:
            status_code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from error
