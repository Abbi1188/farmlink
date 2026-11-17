"""Search by product, text and location (near me, radius, city, district, region of origin)."""
from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, contains_eager

from app.core.constants import Approval, ListingStatus, OrderStatus, Verification
from app.core.geo import haversine_km
from app.models.catalog import Product, StockListing
from app.models.farm import FarmProfile
from app.models.order import Order, OrderItem
from app.models.user import User


def to_public(listing: StockListing, lat: float | None, lon: float | None) -> dict:
    farm = listing.farm
    distance = None
    if lat is not None and lon is not None:
        distance = round(haversine_km(lat, lon, listing.latitude, listing.longitude), 1)

    delivery_ok = bool(distance is not None and farm.delivery_enabled and distance <= farm.delivery_radius_km)
    pickup_ok = bool(farm.pickup_enabled)

    if distance is None:
        label = "Set your location"
    elif delivery_ok:
        label = "Delivers to you"
    elif pickup_ok:
        label = "Pickup only"
    else:
        label = "Not available at your location"

    return {
        "id": listing.id,
        "product_name": listing.product.name,
        "farm_id": farm.id,
        "farm_name": farm.farm_name,
        "available_qty": listing.available_qty,
        "unit": listing.unit,
        "price_per_unit": listing.price_per_unit,
        "is_organic": listing.is_organic,
        "harvest_date": listing.harvest_date,
        "city": listing.city,
        "district": listing.district,
        "address_text": listing.address_text,
        "latitude": listing.latitude,
        "longitude": listing.longitude,
        "origin_tag": listing.origin_tag,
        "distance_km": distance,
        "fulfilment_label": label,
        "delivery_available": delivery_ok,
        "pickup_available": pickup_ok,
    }


def _visible_listings(db: Session):
    return (
        db.query(StockListing)
        .join(StockListing.product)
        .join(StockListing.farm)
        .options(contains_eager(StockListing.product), contains_eager(StockListing.farm))
        .filter(
            StockListing.status == ListingStatus.ACTIVE,
            StockListing.approval_status == Approval.APPROVED,  # admin must approve every new stock
            FarmProfile.verification_status == Verification.APPROVED,
            FarmProfile.owner.has(User.is_active.is_(True)),  # suspended farmers disappear
            (StockListing.total_qty - StockListing.reserved_qty - StockListing.sold_qty) > 0,
            or_(StockListing.expiry_date.is_(None), StockListing.expiry_date >= date.today()),
        )
    )


def search_listings(
    db: Session,
    *,
    q: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radius_km: float | None = None,
    city: str | None = None,
    district: str | None = None,
    origin: str | None = None,
    organic: bool | None = None,
    deliverable_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    query = _visible_listings(db)
    if q:
        query = query.filter(Product.name.ilike(f"%{q.strip()}%"))
    if city:
        query = query.filter(StockListing.city.ilike(city.strip()))
    if district:
        query = query.filter(StockListing.district.ilike(district.strip()))
    if origin:
        query = query.filter(StockListing.origin_tag.ilike(origin.strip()))
    if organic:
        query = query.filter(StockListing.is_organic.is_(True))

    results = []
    for listing in query.all():
        item = to_public(listing, lat, lon)
        if radius_km is not None and item["distance_km"] is not None and item["distance_km"] > radius_km:
            continue
        if deliverable_only and not item["delivery_available"]:
            continue
        results.append(item)

    # Nearest first when a location is given, otherwise cheapest first
    results.sort(key=lambda r: (r["distance_km"] is None, r["distance_km"] or 0, r["price_per_unit"]))
    return results[:limit]


def get_listing(db: Session, listing_id: int, lat: float | None = None, lon: float | None = None) -> dict | None:
    listing = _visible_listings(db).filter(StockListing.id == listing_id).first()
    return to_public(listing, lat, lon) if listing else None


def recent_listings(db: Session, *, lat: float | None = None, lon: float | None = None, limit: int = 8) -> list[dict]:
    """Newest approved stock."""
    rows = _visible_listings(db).order_by(StockListing.id.desc()).limit(limit).all()
    return [to_public(row, lat, lon) for row in rows]


def popular_listings(db: Session, *, lat: float | None = None, lon: float | None = None, limit: int = 8) -> list[dict]:
    """Most ordered approved stock. Listings nobody ordered yet fill the rest, newest first."""
    counts = dict(
        db.query(OrderItem.listing_id, func.count(OrderItem.id))
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status.notin_([OrderStatus.REJECTED, OrderStatus.CANCELLED, OrderStatus.FAILED_DELIVERY]))
        .group_by(OrderItem.listing_id)
        .all()
    )
    rows = _visible_listings(db).all()
    rows.sort(key=lambda row: (-counts.get(row.id, 0), -row.id))
    return [to_public(row, lat, lon) for row in rows[:limit]]
