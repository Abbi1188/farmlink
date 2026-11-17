from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewIn(BaseModel):
    order_id: int
    stars: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    farm_id: int
    stars: int
    comment: str | None
    farmer_reply: str | None
    created_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    message: str
    is_read: bool
    created_at: datetime
