<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.constants import Approval, Fulfilment, OrderStatus, Role
from app.core.geo import haversine_km
from app.core.security import require_role
from app.database import get_db
from app.models.catalog import StockListing
from app.models.farm import FarmProfile
from app.models.order import Order
from app.models.user import User
from app.schemas.admin import (
    AdminFarmerOut,
    AdminFarmOut,
    AdminOrderOut,
    AdminStockOut,
    AdminUserOut,
    OrderEventOut,
    PlaceOut,
    RejectIn,
)
from app.schemas.farm import FarmOut
from app.schemas.order import OrderItemOut
=======
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.constants import Role, Verification
from app.core.security import require_role
from app.database import get_db
from app.models.farm import FarmProfile
from app.models.user import User
from app.schemas.farm import FarmOut
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
from app.services.notification_service import notify

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(Role.ADMIN))])


<<<<<<< HEAD
# ---------- helpers ----------
=======
class AdminUserOut(BaseModel):
    id: int
    name: str
    phone: str
    role: str
    is_active: bool
    created_at: datetime
    farm_id: int | None = None
    farm_name: str | None = None
    farm_status: str | None = None


class AdminFarmOut(FarmOut):
    owner_id: int
    owner_name: str
    owner_phone: str


>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
def _farm_out(farm: FarmProfile) -> AdminFarmOut:
    data = FarmOut.model_validate(farm).model_dump()
    return AdminFarmOut(**data, owner_id=farm.owner_id, owner_name=farm.owner.name, owner_phone=farm.owner.phone)


<<<<<<< HEAD
def _stock_out(listing: StockListing) -> AdminStockOut:
    farm = listing.farm
    return AdminStockOut(
        id=listing.id,
        product_name=listing.product.name,
        total_qty=listing.total_qty,
        reserved_qty=listing.reserved_qty,
        sold_qty=listing.sold_qty,
        available_qty=listing.available_qty,
        unit=listing.unit,
        price_per_unit=listing.price_per_unit,
        is_organic=listing.is_organic,
        harvest_date=listing.harvest_date,
        expiry_date=listing.expiry_date,
        address_text=listing.address_text,
        city=listing.city,
        district=listing.district,
        province=listing.province,
        latitude=listing.latitude,
        longitude=listing.longitude,
        origin_tag=listing.origin_tag,
        status=listing.status,
        approval_status=listing.approval_status,
        approval_note=listing.approval_note,
        created_at=listing.created_at,
        farm_id=farm.id,
        farm_name=farm.farm_name,
        farmer_name=farm.owner.name,
        farmer_phone=farm.owner.phone,
    )


def _user_out(user: User, farm: FarmProfile | None) -> dict:
    return dict(
        id=user.id, name=user.name, phone=user.phone, role=user.role,
        is_active=user.is_active, created_at=user.created_at,
        farm_id=farm.id if farm else None,
        farm_name=farm.farm_name if farm else None,
        farm_status=farm.verification_status if farm else None,
    )


def _order_out(order: Order) -> AdminOrderOut:
    farm = order.farm
    owner = farm.owner
    buyer = order.buyer
    # Source = the stock location of the first item (an order holds one farm's stock only).
    stock = order.items[0].listing if order.items else None
    src_address = stock.address_text if stock else farm.address_text
    src_city = stock.city if stock else farm.city
    src_district = stock.district if stock else farm.district
    src_lat = stock.latitude if stock else farm.latitude
    src_lon = stock.longitude if stock else farm.longitude

    source = PlaceOut(
        name=farm.farm_name,
        contact_name=owner.name,
        contact_phone=owner.phone,
        kind="Stock location",
        address=src_address,
        city=src_city,
        district=src_district,
        latitude=src_lat,
        longitude=src_lon,
    )

    distance = None
    if order.fulfilment_type == Fulfilment.DELIVERY:
        destination = PlaceOut(
            name=buyer.name,
            contact_name=buyer.name,
            contact_phone=buyer.phone,
            kind="Delivery address",
            address=order.delivery_address or "Not given",
            latitude=order.delivery_lat,
            longitude=order.delivery_lon,
        )
        if order.delivery_lat is not None and order.delivery_lon is not None:
            distance = round(haversine_km(src_lat, src_lon, order.delivery_lat, order.delivery_lon), 1)
    else:
        destination = PlaceOut(
            name=buyer.name,
            contact_name=buyer.name,
            contact_phone=buyer.phone,
            kind="Pickup at the stock location",
            address=src_address,
            city=src_city,
            district=src_district,
            latitude=src_lat,
            longitude=src_lon,
        )

    events = [OrderEventOut(status=e.status, at=e.created_at) for e in order.events]
    if not events:  # orders placed before status history existed
        events = [OrderEventOut(status=OrderStatus.PLACED, at=order.placed_at)]
        if order.status != OrderStatus.PLACED:
            events.append(OrderEventOut(status=order.status, at=None))

    return AdminOrderOut(
        id=order.id,
        status=order.status,
        fulfilment_type=order.fulfilment_type,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        subtotal=order.subtotal,
        delivery_fee=order.delivery_fee,
        total=order.total,
        placed_at=order.placed_at,
        rejection_reason=order.rejection_reason,
        items=[OrderItemOut.model_validate(i) for i in order.items],
        source=source,
        destination=destination,
        distance_km=distance,
        events=events,
    )


# ---------- dashboard ----------
=======
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return {
        "farmers": db.query(User).filter(User.role == Role.FARMER).count(),
        "buyers": db.query(User).filter(User.role == Role.BUYER).count(),
<<<<<<< HEAD
        "pending_stock": db.query(StockListing).filter(StockListing.approval_status == Approval.PENDING).count(),
        "orders": db.query(Order).count(),
        "active_orders": db.query(Order)
        .filter(Order.status.notin_([OrderStatus.COMPLETED, OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.FAILED_DELIVERY]))
        .count(),
    }


# ---------- users: buyers and farmers ----------
=======
        "pending_farms": db.query(FarmProfile).filter(FarmProfile.verification_status == Verification.PENDING).count(),
    }


>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
@router.get("/users", response_model=list[AdminUserOut])
def list_users(role: str | None = None, db: Session = Depends(get_db)):
    """All users (optionally one role), with the farm details for farmers."""
    query = db.query(User).filter(User.role != Role.ADMIN)
    if role:
        query = query.filter(User.role == role)
    farms = {f.owner_id: f for f in db.query(FarmProfile).all()}
<<<<<<< HEAD
    return [AdminUserOut(**_user_out(u, farms.get(u.id))) for u in query.order_by(User.created_at.desc()).all()]


@router.get("/farmers", response_model=list[AdminFarmerOut])
def list_farmers(db: Session = Depends(get_db)):
    """Every farmer with all of their stock listings (any approval state)."""
    farms = {f.owner_id: f for f in db.query(FarmProfile).all()}
    listings_by_farm: dict[int, list[StockListing]] = {}
    for listing in db.query(StockListing).order_by(StockListing.id.desc()).all():
        listings_by_farm.setdefault(listing.farm_id, []).append(listing)

    result = []
    for user in db.query(User).filter(User.role == Role.FARMER).order_by(User.created_at.desc()).all():
        farm = farms.get(user.id)
        stocks = [_stock_out(l) for l in listings_by_farm.get(farm.id, [])] if farm else []
        result.append(
            AdminFarmerOut(
                **_user_out(user, farm),
                stock_total=len(stocks),
                stock_pending=sum(1 for s in stocks if s.approval_status == Approval.PENDING),
                stocks=stocks,
=======
    result = []
    for user in query.order_by(User.created_at.desc()).all():
        farm = farms.get(user.id)
        result.append(
            AdminUserOut(
                id=user.id, name=user.name, phone=user.phone, role=user.role,
                is_active=user.is_active, created_at=user.created_at,
                farm_id=farm.id if farm else None,
                farm_name=farm.farm_name if farm else None,
                farm_status=farm.verification_status if farm else None,
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
            )
        )
    return result


@router.get("/farms", response_model=list[AdminFarmOut])
<<<<<<< HEAD
def list_farms(db: Session = Depends(get_db)):
    return [_farm_out(f) for f in db.query(FarmProfile).order_by(FarmProfile.id.desc()).all()]
=======
def list_farms(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(FarmProfile)
    if status:
        query = query.filter(FarmProfile.verification_status == status)
    return [_farm_out(f) for f in query.order_by(FarmProfile.id.desc()).all()]


@router.get("/farms/pending", response_model=list[AdminFarmOut])
def pending_farms(db: Session = Depends(get_db)):
    farms = db.query(FarmProfile).filter(FarmProfile.verification_status == Verification.PENDING).all()
    return [_farm_out(f) for f in farms]


def _set_status(db: Session, farm_id: int, status: str, message: str) -> FarmProfile:
    farm = db.get(FarmProfile, farm_id)
    if not farm:
        raise HTTPException(404, "Farm not found")
    farm.verification_status = status
    notify(db, farm.owner_id, "account", message)
    db.commit()
    db.refresh(farm)
    return farm


@router.post("/farms/{farm_id}/approve", response_model=FarmOut)
def approve_farm(farm_id: int, db: Session = Depends(get_db)):
    return _set_status(db, farm_id, Verification.APPROVED, "Your farm is approved. You can now add stock.")


@router.post("/farms/{farm_id}/reject", response_model=FarmOut)
def reject_farm(farm_id: int, db: Session = Depends(get_db)):
    return _set_status(db, farm_id, Verification.REJECTED, "Your farm was not approved. Please update your details.")
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224


@router.post("/users/{user_id}/suspend")
def suspend_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.role == Role.ADMIN:
        raise HTTPException(400, "Admin accounts cannot be suspended")
    user.is_active = False
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@router.post("/users/{user_id}/activate")
def activate_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = True
    db.commit()
    return {"id": user.id, "is_active": user.is_active}
<<<<<<< HEAD


# ---------- stock approval ----------
@router.get("/stock/pending", response_model=list[AdminStockOut])
def pending_stock(db: Session = Depends(get_db)):
    rows = (
        db.query(StockListing)
        .filter(StockListing.approval_status == Approval.PENDING)
        .order_by(StockListing.id)
        .all()
    )
    return [_stock_out(r) for r in rows]


def _review_stock(db: Session, listing_id: int, approved: bool, reason: str | None) -> AdminStockOut:
    listing = db.get(StockListing, listing_id)
    if not listing:
        raise HTTPException(404, "Stock listing not found")
    farm = listing.farm
    name = listing.product.name
    if approved:
        listing.approval_status = Approval.APPROVED
        listing.approval_note = None
        notify(db, farm.owner_id, "stock", f"Your stock '{name}' is approved and now visible to buyers.")
    else:
        listing.approval_status = Approval.REJECTED
        listing.approval_note = (reason or "").strip() or None
        extra = f" Reason: {listing.approval_note}" if listing.approval_note else ""
        notify(db, farm.owner_id, "stock", f"Your stock '{name}' was not approved.{extra}")
    db.commit()
    db.refresh(listing)
    return _stock_out(listing)


@router.post("/stock/{listing_id}/approve", response_model=AdminStockOut)
def approve_stock(listing_id: int, db: Session = Depends(get_db)):
    return _review_stock(db, listing_id, True, None)


@router.post("/stock/{listing_id}/reject", response_model=AdminStockOut)
def reject_stock(listing_id: int, data: RejectIn | None = None, db: Session = Depends(get_db)):
    return _review_stock(db, listing_id, False, data.reason if data else None)


# ---------- order tracking ----------
@router.get("/orders", response_model=list[AdminOrderOut])
def list_orders(status: str | None = None, db: Session = Depends(get_db)):
    """All orders, newest first, each with source (farm stock) and destination (buyer) details."""
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    return [_order_out(o) for o in query.order_by(Order.id.desc()).limit(300).all()]


@router.get("/orders/{order_id}", response_model=AdminOrderOut)
def order_detail(order_id: int, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    return _order_out(order)
=======
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
