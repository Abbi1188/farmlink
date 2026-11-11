from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category_id: int
    default_unit: str


class ListingCreate(BaseModel):
    product_id: int
    total_qty: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=20)
    price_per_unit: float = Field(gt=0)
    is_organic: bool = False
    harvest_date: date | None = None
    expiry_date: date | None = None
    address_text: str = Field(min_length=3, max_length=255)
    city: str
    district: str
    province: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    origin_tag: str | None = Field(default=None, max_length=80)


class ListingUpdate(BaseModel):
    total_qty: float | None = Field(default=None, gt=0)
    price_per_unit: float | None = Field(default=None, gt=0)
    is_organic: bool | None = None
    expiry_date: date | None = None
    status: Literal["active", "paused", "sold_out"] | None = None
    origin_tag: str | None = Field(default=None, max_length=80)


class ListingOut(BaseModel):
    """Farmer's own view of a listing (includes exact location)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    product_name: str
    total_qty: float
    reserved_qty: float
    sold_qty: float
    available_qty: float
    unit: str
    price_per_unit: float
    is_organic: bool
    harvest_date: date | None
    expiry_date: date | None
    address_text: str
    city: str
    district: str
    latitude: float
    longitude: float
    origin_tag: str | None
    status: str


class ListingPublic(BaseModel):
    """Buyer's view in search results: distance and fulfilment label, no exact address."""

    id: int
    product_name: str
    farm_id: int
    farm_name: str
    available_qty: float
    unit: str
    price_per_unit: float
    is_organic: bool
    harvest_date: date | None
    city: str
    district: str
    origin_tag: str | None
    distance_km: float | None
    fulfilment_label: str
    delivery_available: bool
    pickup_available: bool
