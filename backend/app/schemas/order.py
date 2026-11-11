from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrderItemIn(BaseModel):
    listing_id: int
    qty: float = Field(gt=0)


class OrderCreate(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)
    fulfilment_type: Literal["delivery", "pickup"]
    payment_method: Literal["cod", "jazzcash", "easypaisa", "card"] = "cod"
    delivery_address: str | None = None
    delivery_lat: float | None = Field(default=None, ge=-90, le=90)
    delivery_lon: float | None = Field(default=None, ge=-180, le=180)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    listing_id: int
    product_name: str
    qty: float
    unit_price: float


class OrderBase(BaseModel):
    """Farmer's view: no confirmation code (the buyer must tell it at handover)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    buyer_id: int
    farm_id: int
    status: str
    fulfilment_type: str
    payment_method: str
    payment_status: str
    delivery_address: str | None
    subtotal: float
    delivery_fee: float
    total: float
    rejection_reason: str | None
    placed_at: datetime
    items: list[OrderItemOut]


class OrderOut(OrderBase):
    """Buyer's view: includes the pickup or delivery code."""

    confirmation_code: str


class StatusIn(BaseModel):
    status: Literal[
        "accepted",
        "rejected",
        "preparing",
        "ready_for_pickup",
        "out_for_delivery",
        "completed",
        "cancelled",
        "failed_delivery",
    ]
    reason: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=4)  # required when completing
