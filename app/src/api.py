import os
from decimal import Decimal

import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_db, get_current_user
from schemas import (
    BalanceResponse,
    BalanceTopUp,
    PredictionHistoryItem,
    PredictionRequest,
    PredictionResponse,
    TransactionHistoryItem,
    UserRegister,
    UserResponse,
)
from services import (
    complete_ml_task,
    create_ml_task,
    credit_balance,
    get_balance,
    get_model_by_name,
    get_prediction_history,
    get_transaction_history,
    register_user,
)
from models import User


app = FastAPI()


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "ML service is running"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: UserRegister,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user = register_user(
            session=db,
            login=data.login,
            password=data.password,
        )

        db.commit()
        db.refresh(user)

        return UserResponse(
            id=user.id,
            login=user.login,
            role=user.role.value,
        )

    except ValueError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except Exception:
        db.rollback()
        raise


@app.get(
    "/users/me",
    response_model=UserResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        login=current_user.login,
        role=current_user.role.value,
    )


@app.get(
    "/balance",
    response_model=BalanceResponse,
)
def read_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BalanceResponse:
    balance = get_balance(
        session=db,
        user_id=current_user.id,
    )

    return BalanceResponse(
        balance=balance.amount,
    )


@app.post(
    "/balance/topup",
    response_model=BalanceResponse,
)
def top_up_balance(
    data: BalanceTopUp,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BalanceResponse:
    try:
        credit_balance(
            session=db,
            user_id=current_user.id,
            amount=data.amount,
        )

        db.commit()

        balance = get_balance(
            session=db,
            user_id=current_user.id,
        )

        return BalanceResponse(
            balance=balance.amount,
        )

    except ValueError as error:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    except Exception:
        db.rollback()
        raise


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


@app.post(
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


@app.get(
    "/history/transactions",
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


@app.get(
    "/history/predictions",
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
            charged=task.transaction.amount
            if task.transaction is not None
            else Decimal("0.00"),
            created_at=task.created_at,
            completed_at=task.completed_at,
            prediction=task.result.prediction_data if task.result is not None else None,
        )
        for task in tasks
    ]


# -------------------------------------------------------------------------
if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))

    uvicorn.run(app, host=host, port=port)
