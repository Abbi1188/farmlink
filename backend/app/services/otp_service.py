"""Phone OTP for registration.

send_sms() is the only place that must change to use a real SMS provider
(a local SMS gateway, Twilio, etc.). Until then the code is printed in the backend
console, and, while settings.otp_debug_return is True, returned to the app so you can test.
"""
import hashlib
import hmac
import logging
import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.database import utcnow
from app.models.otp import OtpCode

log = logging.getLogger("farmlink.otp")


class OtpError(Exception):
    """Raised with a message that is safe to show to the user."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def send_sms(phone: str, message: str) -> None:
    # TODO: connect an SMS provider here. For now the message only goes to the server log.
    log.warning("SMS to %s: %s", phone, message)
    print(f"[FarmBridge OTP] SMS to {phone}: {message}")


def _hash(phone: str, code: str) -> str:
    return hmac.new(settings.secret_key.encode(), f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def request_otp(db: Session, phone: str) -> str:
    """Create and send a new code. Returns the code (the caller decides whether to expose it)."""
    now = utcnow()
    last = db.query(OtpCode).filter(OtpCode.phone == phone).order_by(OtpCode.id.desc()).first()
    if last and (now - last.created_at).total_seconds() < settings.otp_resend_seconds:
        wait = settings.otp_resend_seconds - int((now - last.created_at).total_seconds())
        raise OtpError(f"Please wait {wait} seconds before asking for a new code", 429)

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        OtpCode(
            phone=phone,
            code_hash=_hash(phone, code),
            expires_at=now + timedelta(minutes=settings.otp_expire_minutes),
        )
    )
    db.commit()
    send_sms(phone, f"Your FarmBridge code is {code}. It expires in {settings.otp_expire_minutes} minutes.")
    return code


def verify_otp(db: Session, phone: str, code: str) -> None:
    """Check the newest unused code for this phone. Marks it used on success."""
    now = utcnow()
    otp = (
        db.query(OtpCode)
        .filter(OtpCode.phone == phone, OtpCode.used.is_(False))
        .order_by(OtpCode.id.desc())
        .first()
    )
    if not otp or otp.expires_at < now:
        raise OtpError("The code has expired. Please request a new one.")
    if otp.attempts >= settings.otp_max_attempts:
        raise OtpError("Too many wrong attempts. Please request a new code.")
    if not hmac.compare_digest(otp.code_hash, _hash(phone, code)):
        otp.attempts += 1
        db.commit()
        raise OtpError("Wrong code. Please check and try again.")
    otp.used = True
    db.commit()
