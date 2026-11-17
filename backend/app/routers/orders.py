from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.constants import Role
from app.core.security import require_role
from app.database import get_db
from app.models.farm import FarmProfile
from app.models.order import Order
from app.models.user import User
from app.schemas.order import OrderBase, OrderCreate, OrderOut, StatusIn
from app.services import order_service
from app.services.order_service import OrderError, OrderPermissionError

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201)
def create_order(data: OrderCreate, user: User = Depends(require_role(Role.BUYER)), db: Session = Depends(get_db)):
    try:
        return order_service.place_order(db, user, data)
    except OrderError as exc:
        raise HTTPException(400, str(exc))


@router.get("/mine", response_model=list[OrderOut])
def my_orders(user: User = Depends(require_role(Role.BUYER)), db: Session = Depends(get_db)):
    return db.query(Order).filter(Order.buyer_id == user.id).order_by(Order.id.desc()).all()


@router.get("/farm", response_model=list[OrderBase])
def farm_orders(user: User = Depends(require_role(Role.FARMER)), db: Session = Depends(get_db)):
    farm = db.query(FarmProfile).filter(FarmProfile.owner_id == user.id).first()
    if not farm:
        return []
    return db.query(Order).filter(Order.farm_id == farm.id).order_by(Order.id.desc()).all()


@router.post("/{order_id}/status")
def update_status(
    order_id: int,
    data: StatusIn,
    user: User = Depends(require_role(Role.FARMER, Role.BUYER)),
    db: Session = Depends(get_db),
):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    try:
        updated = order_service.change_status(db, order, data.status, user, data.reason, data.code)
    except OrderPermissionError as exc:
        raise HTTPException(403, str(exc))
    except OrderError as exc:
        raise HTTPException(400, str(exc))
    schema = OrderOut if user.id == updated.buyer_id else OrderBase
    return schema.model_validate(updated)
