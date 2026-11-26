"""Order placement and status rules."""
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import Approval, Fulfilment, ListingStatus, OrderStatus, Verification
from app.core.geo import haversine_km
from app.database import utcnow
from app.models.catalog import StockListing
from app.models.farm import FarmProfile
from app.models.order import Order, OrderEvent, OrderItem
from app.models.user import User
from app.schemas.order import OrderCreate
from app.services import stock_service
from app.services.notification_service import notify
from app.services.stock_service import StockError


class OrderError(Exception):
    pass


class OrderPermissionError(Exception):
    pass


ALLOWED_TRANSITIONS = {
    OrderStatus.PLACED: {OrderStatus.ACCEPTED, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.ACCEPTED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY_FOR_PICKUP, OrderStatus.OUT_FOR_DELIVERY},
    OrderStatus.READY_FOR_PICKUP: {OrderStatus.COMPLETED},
    OrderStatus.OUT_FOR_DELIVERY: {OrderStatus.COMPLETED, OrderStatus.FAILED_DELIVERY},
}
STOCK_RELEASING = {OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.FAILED_DELIVERY}


def place_order(db: Session, buyer: User, data: OrderCreate) -> Order:
    ids = [i.listing_id for i in data.items]
    if len(set(ids)) != len(ids):
        raise OrderError("The same item appears twice in the cart")

    # FOR UPDATE locks rows on PostgreSQL so two buyers cannot take the last kilogram; SQLite ignores it.
    listings = {
        l.id: l for l in db.query(StockListing).filter(StockListing.id.in_(ids)).with_for_update().all()
    }
    if len(listings) != len(ids):
        raise OrderError("One of the items no longer exists")

    if any(l.approval_status != Approval.APPROVED for l in listings.values()):
        raise OrderError("One of the items is not available yet")

    farm_ids = {l.farm_id for l in listings.values()}
    if len(farm_ids) != 1:
        raise OrderError("An order can contain items from one farm only")
    farm = db.get(FarmProfile, farm_ids.pop())
    if farm.verification_status != Verification.APPROVED:
        raise OrderError("This farm is not available")

    subtotal = sum(listings[i.listing_id].price_per_unit * i.qty for i in data.items)
    fee = 0.0

    if data.fulfilment_type == Fulfilment.PICKUP:
        if not farm.pickup_enabled:
            raise OrderError("This farm does not offer pickup")
    else:
        if not farm.delivery_enabled:
            raise OrderError("This farm does not offer delivery")
        if data.delivery_lat is None or data.delivery_lon is None or not data.delivery_address:
            raise OrderError("A delivery address with location is required")
        first = listings[ids[0]]
        distance = haversine_km(data.delivery_lat, data.delivery_lon, first.latitude, first.longitude)
        if distance > farm.delivery_radius_km:
            raise OrderError(
                f"Your address is {distance:.1f} km away; this farm delivers within {farm.delivery_radius_km:g} km"
            )
        if subtotal < farm.min_order:
            raise OrderError(f"Minimum order for delivery is Rs {farm.min_order:g}")
        fee = farm.delivery_fee

    order = Order(
        buyer_id=buyer.id,
        farm_id=farm.id,
        status=OrderStatus.PLACED,
        fulfilment_type=data.fulfilment_type,
        payment_method=data.payment_method,
        delivery_address=data.delivery_address,
        delivery_lat=data.delivery_lat,
        delivery_lon=data.delivery_lon,
        subtotal=subtotal,
        delivery_fee=fee,
        total=subtotal + fee,
        confirmation_code=f"{secrets.randbelow(10000):04d}",
    )
    try:
        for item in data.items:
            listing = listings[item.listing_id]
            stock_service.reserve(listing, item.qty)
            order.items.append(
                OrderItem(
                    listing_id=listing.id,
                    product_name=listing.product.name,
                    qty=item.qty,
                    unit_price=listing.price_per_unit,
                )
            )
    except StockError as exc:
        db.rollback()
        raise OrderError(str(exc)) from exc

    order.events.append(OrderEvent(status=OrderStatus.PLACED))
    db.add(order)
    db.flush()
    notify(db, farm.owner_id, "order", f"New order #{order.id} received")
    db.commit()
    db.refresh(order)
    return order


def _apply_status(db: Session, order: Order, new_status: str) -> None:
    order.status = new_status
    order.events.append(OrderEvent(status=new_status))
    for item in order.items:
        listing = db.get(StockListing, item.listing_id)
        if new_status in STOCK_RELEASING:
            stock_service.release(listing, item.qty)
        elif new_status == OrderStatus.COMPLETED:
            stock_service.commit_sale(listing, item.qty)
    if new_status == OrderStatus.COMPLETED:
        order.payment_status = "paid"


def change_status(
    db: Session, order: Order, new_status: str, actor: User, reason: str | None = None, code: str | None = None
) -> Order:
    farm = db.get(FarmProfile, order.farm_id)
    is_farmer = actor.id == farm.owner_id
    is_buyer = actor.id == order.buyer_id
    if not (is_farmer or is_buyer):
        raise OrderPermissionError("This is not your order")

    if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
        raise OrderError(f"An order that is '{order.status}' cannot become '{new_status}'")

    if not is_farmer and (new_status != OrderStatus.CANCELLED or order.status != OrderStatus.PLACED):
        raise OrderPermissionError("Buyers can only cancel an order before the farmer accepts it")

    if new_status == OrderStatus.READY_FOR_PICKUP and order.fulfilment_type != Fulfilment.PICKUP:
        raise OrderError("This is a delivery order")
    if new_status == OrderStatus.OUT_FOR_DELIVERY and order.fulfilment_type != Fulfilment.DELIVERY:
        raise OrderError("This is a pickup order")
    if new_status == OrderStatus.COMPLETED and code != order.confirmation_code:
        raise OrderError("The confirmation code from the buyer is missing or wrong")

    if new_status == OrderStatus.REJECTED:
        order.rejection_reason = reason

    _apply_status(db, order, new_status)
    other_party = order.buyer_id if is_farmer else farm.owner_id
    notify(db, other_party, "order", f"Order #{order.id} is now {new_status.replace('_', ' ')}")
    db.commit()
    db.refresh(order)
    return order


def expire_stale_orders(db: Session) -> int:
    """Cancel orders the farmer did not answer in time and release their stock."""
    cutoff = utcnow() - timedelta(minutes=settings.order_response_timeout_minutes)
    stale = db.query(Order).filter(Order.status == OrderStatus.PLACED, Order.placed_at < cutoff).all()
    for order in stale:
        _apply_status(db, order, OrderStatus.CANCELLED)
        order.rejection_reason = "Farmer did not respond in time"
        notify(db, order.buyer_id, "order", f"Order #{order.id} was cancelled: no response from the farm")
    db.commit()
    return len(stale)
