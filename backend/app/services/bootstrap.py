"""Start-up tasks: make sure the one built-in admin account exists."""
from sqlalchemy.orm import Session

from app.config import settings
from app.core.constants import Role
from app.core.security import hash_password
from app.models.user import User


def ensure_default_admin(db: Session) -> bool:
    """Create the single admin from ADMIN_PHONE / ADMIN_PASSWORD if no admin exists. Returns True if created."""
    if db.query(User).filter(User.role == Role.ADMIN).first():
        return False
    existing = db.query(User).filter(User.phone == settings.admin_phone).first()
    if existing:  # the phone is taken by a normal account: promote nothing, ask the owner to change ADMIN_PHONE
        raise RuntimeError(
            f"ADMIN_PHONE {settings.admin_phone} already belongs to a {existing.role} account. "
            "Set a different ADMIN_PHONE in backend/.env."
        )
    db.add(
        User(
            name=settings.admin_name,
            phone=settings.admin_phone,
            password_hash=hash_password(settings.admin_password),
            role=Role.ADMIN,
        )
    )
    db.commit()
    return True
