import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    cnic: str | None = Field(default=None, max_length=20)  # required for farmers, ignored for buyers

    @model_validator(mode="after")
    def check_cnic(self):
        """Farmers must give a 13-digit CNIC; it is stored as 12345-1234567-1. Buyers do not store one."""
        if self.role == "farmer":
            digits = re.sub(r"\D", "", self.cnic or "")
            if len(digits) != 13:
                raise ValueError("A farmer must give a 13-digit CNIC number")
            self.cnic = f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
        else:
            self.cnic = None
        return self


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
