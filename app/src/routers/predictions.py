from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from datetime import datetime, timezone
from dependencies import get_current_user, get_db
from models import User
from rabbitmq import publish_ml_task
from schemas import (
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
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
