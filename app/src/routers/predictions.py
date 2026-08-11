from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_current_user, get_db
from models import User
from schemas import PredictionRequest, PredictionResponse
from services import (
    complete_ml_task,
    create_ml_task,
    get_balance,
    get_model_by_name,
)

router = APIRouter(
    tags=["predictions"],
)


# Make a demo prediction --------------------------------------------------
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


# -------------------------------------------------------------------------


@router.post(
    "/predict",
    response_model=PredictionResponse,
)
def predict(
    data: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PredictionResponse:
    try:
        ml_model = get_model_by_name(
            session=db,
            name=data.model_name,
        )

        task = create_ml_task(
            session=db,
            user_id=current_user.id,
            model_id=ml_model.id,
            input_data={
                "text": data.text,
            },
        )

        prediction = make_demo_prediction(data.text)

        complete_ml_task(
            session=db,
            task_id=task.id,
            prediction_data=prediction,
            invalid_rows=[],
        )

        db.commit()
        db.refresh(task)

        balance = get_balance(
            session=db,
            user_id=current_user.id,
        )

        return PredictionResponse(
            task_id=task.id,
            status=task.status.value,
            prediction=prediction,
            charged=ml_model.cost,
            balance=balance.amount,
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

    except Exception:
        db.rollback()
        raise
