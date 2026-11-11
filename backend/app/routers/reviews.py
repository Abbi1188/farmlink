from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.constants import OrderStatus, Role
from app.core.security import require_role
from app.database import get_db
from app.models.order import Order
from app.models.review import Review
from app.models.user import User
from app.schemas.review import ReviewIn, ReviewOut

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", response_model=ReviewOut, status_code=201)
def create_review(data: ReviewIn, user: User = Depends(require_role(Role.BUYER)), db: Session = Depends(get_db)):
    order = db.get(Order, data.order_id)
    if not order or order.buyer_id != user.id:
        raise HTTPException(404, "Order not found")
    if order.status != OrderStatus.COMPLETED:
        raise HTTPException(400, "You can review an order only after it is completed")
    if db.query(Review).filter(Review.order_id == order.id).first():
        raise HTTPException(409, "You already reviewed this order")
    review = Review(order_id=order.id, buyer_id=user.id, farm_id=order.farm_id, stars=data.stars, comment=data.comment)
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


@router.get("/farm/{farm_id}", response_model=list[ReviewOut])
def farm_reviews(farm_id: int, db: Session = Depends(get_db)):
    return db.query(Review).filter(Review.farm_id == farm_id).order_by(Review.id.desc()).all()
