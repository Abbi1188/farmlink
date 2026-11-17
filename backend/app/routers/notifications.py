from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.review import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def my_notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Notification).filter(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(100).all()
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    note = db.get(Notification, notification_id)
    if not note or note.user_id != user.id:
        raise HTTPException(404, "Notification not found")
    note.is_read = True
    db.commit()
    db.refresh(note)
    return note
