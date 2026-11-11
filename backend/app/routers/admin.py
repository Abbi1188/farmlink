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
from app.services.notification_service import notify

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_role(Role.ADMIN))])


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


def _farm_out(farm: FarmProfile) -> AdminFarmOut:
    data = FarmOut.model_validate(farm).model_dump()
    return AdminFarmOut(**data, owner_id=farm.owner_id, owner_name=farm.owner.name, owner_phone=farm.owner.phone)


@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    return {
        "farmers": db.query(User).filter(User.role == Role.FARMER).count(),
        "buyers": db.query(User).filter(User.role == Role.BUYER).count(),
        "pending_farms": db.query(FarmProfile).filter(FarmProfile.verification_status == Verification.PENDING).count(),
    }


@router.get("/users", response_model=list[AdminUserOut])
def list_users(role: str | None = None, db: Session = Depends(get_db)):
    """All users (optionally one role), with the farm details for farmers."""
    query = db.query(User).filter(User.role != Role.ADMIN)
    if role:
        query = query.filter(User.role == role)
    farms = {f.owner_id: f for f in db.query(FarmProfile).all()}
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
            )
        )
    return result


@router.get("/farms", response_model=list[AdminFarmOut])
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
