from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.stock import ListingPublic
from app.services import search_service

router = APIRouter(tags=["search"])


@router.get("/search", response_model=list[ListingPublic])
def search(
    q: str | None = Query(None, description="Product name, e.g. wheat or milk"),
    lat: float | None = Query(None, ge=-90, le=90, description="Buyer latitude"),
    lon: float | None = Query(None, ge=-180, le=180, description="Buyer longitude"),
    radius_km: float | None = Query(None, gt=0, le=500),
    city: str | None = None,
    district: str | None = None,
    origin: str | None = Query(None, description="Region of origin tag, e.g. Swat"),
    organic: bool | None = None,
    deliverable_only: bool = False,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return search_service.search_listings(
        db,
        q=q,
        lat=lat,
        lon=lon,
        radius_km=radius_km,
        city=city,
        district=district,
        origin=origin,
        organic=organic,
        deliverable_only=deliverable_only,
        limit=limit,
    )


<<<<<<< HEAD
@router.get("/listings/popular", response_model=list[ListingPublic])
def popular(
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(8, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Most ordered stock, for the home page."""
    return search_service.popular_listings(db, lat=lat, lon=lon, limit=limit)


@router.get("/listings/recent", response_model=list[ListingPublic])
def recent(
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    limit: int = Query(8, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """Newly added stock, for the home page."""
    return search_service.recent_listings(db, lat=lat, lon=lon, limit=limit)


=======
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
@router.get("/listings/{listing_id}", response_model=ListingPublic)
def listing_detail(
    listing_id: int,
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    db: Session = Depends(get_db),
):
    listing = search_service.get_listing(db, listing_id, lat, lon)
    if not listing:
        raise HTTPException(404, "Listing not found or no longer available")
    return listing
