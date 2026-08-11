from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_db
from schemas import UserLogin, UserRegister, UserResponse
from services import authenticate_user, register_user


router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)


@router.post(
    "/register",
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


@router.post(
    "/login",
    response_model=UserResponse,
)
def login(
    data: UserLogin,
    db: Session = Depends(get_db),
) -> UserResponse:
    try:
        user = authenticate_user(
            session=db,
            login=data.login,
            password=data.password,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(error),
        ) from error

    return UserResponse(
        id=user.id,
        login=user.login,
        role=user.role.value,
    )