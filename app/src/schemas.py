from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    login: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=100)


class UserLogin(BaseModel):
    login: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=6, max_length=100)


class UserResponse(BaseModel):
    id: int
    login: str
    role: str


class BalanceTopUp(BaseModel):
    amount: Decimal = Field(gt=0)


class BalanceResponse(BaseModel):
    balance: Decimal


class PredictionRequest(BaseModel):
    model_name: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=5000)


class PredictionResponse(BaseModel):
    task_id: int
    status: str
    prediction: dict[str, Any]
    charged: Decimal
    balance: Decimal


class TransactionHistoryItem(BaseModel):
    id: int
    operation_type: str
    amount: Decimal
    task_id: int | None
    created_at: datetime


class PredictionHistoryItem(BaseModel):
    task_id: int
    model_name: str
    status: str
    charged: Decimal
    created_at: datetime
    completed_at: datetime | None
    prediction: dict[str, Any] | None


class MLTaskFeatures(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class MLTaskMessage(BaseModel):
    task_id: int
    features: MLTaskFeatures
    model: str
    timestamp: datetime


class PredictionAcceptedResponse(BaseModel):
    task_id: int
    status: str


class BatchPredictionRequest(BaseModel):
    model_name: str = Field(
        min_length=1,
        max_length=100,
    )

    rows: list[Any] = Field(
        min_length=1,
        max_length=100,
    )


class BatchAcceptedItem(BaseModel):
    row: int
    task_id: int
    status: str


class BatchInvalidRow(BaseModel):
    row: int
    value: Any
    error: str


class BatchPredictionResponse(BaseModel):
    accepted: list[BatchAcceptedItem]
    invalid_rows: list[BatchInvalidRow]


class WorkerResultRequest(BaseModel):
    prediction: dict[str, Any]


class WorkerResultResponse(BaseModel):
    task_id: int
    status: str
