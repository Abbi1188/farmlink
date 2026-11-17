from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

<<<<<<< HEAD
from app.config import settings
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import OtpRequestIn, OtpRequestOut, RegisterIn, TokenOut, UserOut
from app.services import otp_service
from app.services.otp_service import OtpError
=======
from app.core.security import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models.user import User
from app.schemas.auth import RegisterIn, TokenOut, UserOut
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224

router = APIRouter(prefix="/auth", tags=["auth"])


<<<<<<< HEAD
@router.post("/otp/request", response_model=OtpRequestOut)
def request_otp(data: OtpRequestIn, db: Session = Depends(get_db)):
    """Step 1 of registration: send a 6-digit code to the phone number."""
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This phone number is already registered")
    try:
        code = otp_service.request_otp(db, data.phone)
    except OtpError as exc:
        raise HTTPException(exc.status_code, str(exc))
    return OtpRequestOut(
        message="A 6-digit code was sent to your phone",
        expires_in_minutes=settings.otp_expire_minutes,
        dev_otp=code if settings.otp_debug_return else None,
    )


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    """Step 2: phone + OTP + password. Farmers and buyers can start straight away (no admin approval)."""
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This phone number is already registered")
    try:
        otp_service.verify_otp(db, data.phone, data.otp)
    except OtpError as exc:
        raise HTTPException(exc.status_code, str(exc))
=======
@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    if db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This phone number is already registered")
>>>>>>> d0ed8458cf1ece2668168d587a4573d01ca60224
    user = User(
        name=data.name,
        phone=data.phone,
        password_hash=hash_password(data.password),
        role=data.role,
        language=data.language,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user), user=user)


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """The form's `username` field holds the phone number."""
    user = db.query(User).filter(User.phone == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong phone number or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account is suspended")
    return TokenOut(access_token=create_access_token(user), user=user)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
