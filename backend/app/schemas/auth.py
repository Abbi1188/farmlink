from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OtpRequestIn(BaseModel):
    phone: str = Field(min_length=10, max_length=20)


class OtpRequestOut(BaseModel):
    message: str
    expires_in_minutes: int
    dev_otp: str | None = None  # only filled while OTP_DEBUG_RETURN=true (no SMS provider yet)


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    password: str = Field(min_length=6, max_length=72)
    role: Literal["farmer", "buyer"]
    language: Literal["en", "ur", "ps"] = "en"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    role: str
    language: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
