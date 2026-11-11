from sqlalchemy.orm import Session

from app.models.notification import Notification


def notify(db: Session, user_id: int, type_: str, message: str) -> None:
    """Queue an in-app notification. The caller commits.

    Push notifications (Firebase Cloud Messaging) can be added here later.
    """
    db.add(Notification(user_id=user_id, type=type_, message=message))
