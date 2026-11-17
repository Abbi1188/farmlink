from sqlalchemy.orm import Session

<<<<<<< HEAD
from app.core.constants import Role
from app.models.notification import Notification
from app.models.user import User
=======
from app.models.notification import Notification
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224


def notify(db: Session, user_id: int, type_: str, message: str) -> None:
    """Queue an in-app notification. The caller commits.

    Push notifications (Firebase Cloud Messaging) can be added here later.
    """
    db.add(Notification(user_id=user_id, type=type_, message=message))
<<<<<<< HEAD


def notify_admins(db: Session, type_: str, message: str) -> None:
    for admin in db.query(User).filter(User.role == Role.ADMIN, User.is_active.is_(True)).all():
        notify(db, admin.id, type_, message)
=======
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
