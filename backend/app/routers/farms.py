from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.constants import Role, Verification
from app.core.security import require_role
from app.database import get_db
from app.models.farm import FarmProfile
from app.models.user import User
from app.schemas.farm import FarmIn, FarmOut, FarmPublic

router = APIRouter(prefix="/farms", tags=["farms"])


@router.post("/profile", response_model=FarmOut, status_code=201)
def create_profile(data: FarmIn, user: User = Depends(require_role(Role.FARMER)), db: Session = Depends(get_db)):
    if db.query(FarmProfile).filter(FarmProfile.owner_id == user.id).first():
        raise HTTPException(409, "You already have a farm profile")
    # No admin approval for the farm itself: approval happens per stock listing.
    farm = FarmProfile(owner_id=user.id, verification_status=Verification.APPROVED, **data.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.put("/profile", response_model=FarmOut)
def update_profile(data: FarmIn, user: User = Depends(require_role(Role.FARMER)), db: Session = Depends(get_db)):
    farm = db.query(FarmProfile).filter(FarmProfile.owner_id == user.id).first()
    if not farm:
        raise HTTPException(404, "Create your farm profile first")
    for key, value in data.model_dump().items():
        setattr(farm, key, value)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("/me", response_model=FarmOut)
def my_farm(user: User = Depends(require_role(Role.FARMER)), db: Session = Depends(get_db)):
    farm = db.query(FarmProfile).filter(FarmProfile.owner_id == user.id).first()
    if not farm:
        raise HTTPException(404, "No farm profile yet")
    return farm


@router.get("/{farm_id}", response_model=FarmPublic)
def public_farm(farm_id: int, db: Session = Depends(get_db)):
    farm = db.get(FarmProfile, farm_id)
    if not farm:
        raise HTTPException(404, "Farm not found")
    return farm
