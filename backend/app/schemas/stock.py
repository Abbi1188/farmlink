from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.constants import Approval, Role
from app.core.security import require_role
from app.database import get_db
from app.models.catalog import Product, StockListing
from app.models.farm import FarmProfile
from app.models.user import User
from app.schemas.stock import ListingCreate, ListingOut, ListingUpdate
from app.services.notification_service import notify_admins
from app.services.photo_service import add_photos, delete_files
from app.services.stock_service import refresh_status

router = APIRouter(prefix="/stock", tags=["farmer stock"])


def _my_farm(user: User, db: Session) -> FarmProfile:
    farm = db.query(FarmProfile).filter(FarmProfile.owner_id == user.id).first()
    if not farm:
        raise HTTPException(400, "Create your farm profile first")
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
    # A farmer may add any number of listings, but each new one waits for admin approval.
    listing = StockListing(farm_id=farm.id, approval_status=Approval.PENDING, **data.model_dump())
    db.add(listing)
    db.flush()
    product = db.get(Product, data.product_id)
    notify_admins(db, "stock", f"New stock to approve: {product.name} from {farm.farm_name} (listing #{listing.id})")
    db.commit()
    db.refresh(listing)
    return listing


@router.post("/{listing_id}/photos", response_model=ListingOut)
def upload_photos(
    listing_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(require_role(Role.FARMER)),
    db: Session = Depends(get_db),
):
    """Add pictures to one of your listings (3 in total, JPG, PNG or WebP, 5 MB each)."""
    farm = _my_farm(user, db)
    listing = _my_listing(listing_id, farm, db)
    add_photos(db, listing, files)
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
    if listing.approval_status == Approval.REJECTED:
        # Editing a rejected listing sends it back for another review.
        listing.approval_status = Approval.PENDING
        listing.approval_note = None
        notify_admins(db, "stock", f"Stock resubmitted for approval: listing #{listing.id}")
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
    filenames = [photo.filename for photo in listing.photo_rows]
    db.delete(listing)
    db.commit()
    delete_files(filenames)  # the pictures go with the listing
