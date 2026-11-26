from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.farm import FarmOut
from app.schemas.order import OrderItemOut


class AdminUserOut(BaseModel):
    id: int
    name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime
    cnic: str | None = None
    farm_id: int | None = None
    farm_name: str | None = None
    farm_status: str | None = None


class AdminFarmOut(FarmOut):
    owner_id: int
    owner_name: str
    owner_phone: str


class AdminStockOut(BaseModel):
    """A stock listing as the admin sees it, with who owns it and where it is."""

    model_config = ConfigDict(from_attributes=True)

    id: int
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
    province: str
    latitude: float
    longitude: float
    origin_tag: str | None
    status: str
    approval_status: str
    approval_note: str | None
    created_at: datetime
    farm_id: int
    farm_name: str
    farmer_name: str
    farmer_phone: str


class AdminFarmerOut(AdminUserOut):
    """A farmer with the farm details and every stock listing (shown as an expandable list)."""

    stock_total: int = 0
    stock_pending: int = 0
    stocks: list[AdminStockOut] = []


class RejectIn(BaseModel):
    reason: str | None = None


# ---------- order tracking ----------
class PlaceOut(BaseModel):
    """One end of an order's journey (source = farm stock, destination = buyer)."""

    name: str  # farm name (source) or buyer name (destination)
    contact_name: str
    contact_phone: str
    kind: str  # "Stock location", "Delivery address" or "Pickup at the stock location"
    address: str
    city: str | None = None
    district: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class OrderEventOut(BaseModel):
    status: str
    at: datetime | None


class AdminOrderOut(BaseModel):
    id: int
    status: str
    fulfilment_type: str
    payment_method: str
    payment_status: str
    subtotal: float
    delivery_fee: float
    total: float
    placed_at: datetime
    rejection_reason: str | None
    items: list[OrderItemOut]
    source: PlaceOut
    destination: PlaceOut
    distance_km: float | None
    events: list[OrderEventOut]
