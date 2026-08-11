from fastapi import APIRouter, Depends

from dependencies import get_current_user
from models import User
from schemas import UserResponse


router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get(
    "/me",
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
