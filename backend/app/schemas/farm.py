from pydantic import BaseModel, ConfigDict, Field


class FarmIn(BaseModel):
    farm_name: str = Field(min_length=2, max_length=150)
    description: str | None = None
    delivery_enabled: bool = False
    pickup_enabled: bool = True
    delivery_radius_km: float = Field(10.0, gt=0, le=200)
    delivery_fee: float = Field(0.0, ge=0)
    min_order: float = Field(0.0, ge=0)
    pickup_hours: str | None = None
    address_text: str = Field(min_length=3, max_length=255)
    city: str
    district: str
    province: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class FarmOut(FarmIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    verification_status: str


class FarmPublic(BaseModel):
    """What buyers may see: no exact address or coordinates."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_name: str
    description: str | None
    city: str
    district: str
    delivery_enabled: bool
    pickup_enabled: bool
    delivery_radius_km: float
    delivery_fee: float
    min_order: float
    pickup_hours: str | None
