from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from dependencies import get_db
from schemas import WorkerResultRequest, WorkerResultResponse
from services import complete_ml_task


router = APIRouter(
    prefix="/internal",
    tags=["internal"],
)


@router.post(
    "/tasks/{task_id}/result",
    response_model=WorkerResultResponse,
)
def save_worker_result(
    task_id: int,
    data: WorkerResultRequest,
    db: Session = Depends(get_db),
) -> WorkerResultResponse:
    try:
        complete_ml_task(
            session=db,
            task_id=task_id,
            prediction_data=data.prediction,
            invalid_rows=[],
        )

        db.commit()

        return WorkerResultResponse(
            task_id=task_id,
            status="completed",
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
