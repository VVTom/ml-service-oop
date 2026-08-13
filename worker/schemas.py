from datetime import datetime

from pydantic import BaseModel, Field


class MLTaskFeatures(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


class MLTaskMessage(BaseModel):
    task_id: int
    features: MLTaskFeatures
    model: str
    timestamp: datetime
