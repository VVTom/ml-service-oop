from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_current_user, get_db
from models import User
from schemas import BalanceResponse, BalanceTopUp
from services import credit_balance, get_balance


router = APIRouter(
    tags=["balance"],
)


@router.get(
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


@router.post(
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
