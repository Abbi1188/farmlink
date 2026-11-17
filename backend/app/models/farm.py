from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import Verification
from app.database import Base


class FarmProfile(Base):
    __tablename__ = "farm_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    farm_name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), default=Verification.PENDING)

    # Fulfilment options
    delivery_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_radius_km: Mapped[float] = mapped_column(Float, default=10.0)
    delivery_fee: Mapped[float] = mapped_column(Float, default=0.0)
    min_order: Mapped[float] = mapped_column(Float, default=0.0)
    pickup_hours: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Farm location
    address_text: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(80))
    district: Mapped[str] = mapped_column(String(80))
    province: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    owner = relationship("User")
    listings = relationship("StockListing", back_populates="farm")
