from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import Role, Verification
from app.core.security import require_role
from app.database import get_db
from app.models.catalog import Product, StockListing
from app.models.farm import FarmProfile
from app.models.user import User
from app.schemas.stock import ListingCreate, ListingOut, ListingUpdate
from app.services.stock_service import refresh_status

router = APIRouter(prefix="/stock", tags=["farmer stock"])


def _my_farm(user: User, db: Session) -> FarmProfile:
    farm = db.query(FarmProfile).filter(FarmProfile.owner_id == user.id).first()
    if not farm:
        raise HTTPException(400, "Create your farm profile first")
    if settings.require_farm_approval and farm.verification_status != Verification.APPROVED:
        raise HTTPException(403, "Your farm is waiting for admin approval")
    return farm


def _my_listing(listing_id: int, farm: FarmProfile, db: Session) -> StockListing:
    listing = db.get(StockListing, listing_id)
    if not listing or listing.farm_id != farm.id:
        raise HTTPException(404, "Listing not found")
    return listing


@router.post("", response_model=ListingOut, status_code=201)
def create_listing(data: ListingCreate, user: User = Depends(require_role(Role.FARMER)), db: Session = Depends(get_db)):
    farm = _my_farm(user, db)
    if not db.get(Product, data.product_id):
        raise HTTPException(404, "Unknown product")
    listing = StockListing(farm_id=farm.id, **data.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/mine", response_model=list[ListingOut])
def my_listings(user: User = Depends(require_role(Role.FARMER)), db: Session = Depends(get_db)):
    farm = db.query(FarmProfile).filter(FarmProfile.owner_id == user.id).first()
    if not farm:
        return []
    return db.query(StockListing).filter(StockListing.farm_id == farm.id).order_by(StockListing.id.desc()).all()


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(
    listing_id: int,
    data: ListingUpdate,
    user: User = Depends(require_role(Role.FARMER)),
    db: Session = Depends(get_db),
):
    farm = _my_farm(user, db)
    listing = _my_listing(listing_id, farm, db)
    changes = data.model_dump(exclude_unset=True)
    new_total = changes.get("total_qty", listing.total_qty)
    if new_total < listing.reserved_qty + listing.sold_qty:
        raise HTTPException(409, "Quantity cannot be lower than what is already reserved or sold")
    for key, value in changes.items():
        setattr(listing, key, value)
    refresh_status(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.delete("/{listing_id}", status_code=204)
def delete_listing(listing_id: int, user: User = Depends(require_role(Role.FARMER)), db: Session = Depends(get_db)):
    farm = _my_farm(user, db)
    listing = _my_listing(listing_id, farm, db)
    if listing.reserved_qty > 0 or listing.sold_qty > 0:
        raise HTTPException(409, "This listing has orders. Pause it instead of deleting.")
    db.delete(listing)
    db.commit()
