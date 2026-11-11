from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
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
