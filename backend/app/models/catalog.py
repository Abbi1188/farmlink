from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import Approval, ListingStatus
from app.database import Base, utcnow


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    default_unit: Mapped[str] = mapped_column(String(20), default="kg")

    category = relationship("Category")


class StockListing(Base):
    """One farm's stock of one product, with the location where it can be collected."""

    __tablename__ = "stock_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farm_profiles.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)

    total_qty: Mapped[float] = mapped_column(Float)
    reserved_qty: Mapped[float] = mapped_column(Float, default=0.0)
    sold_qty: Mapped[float] = mapped_column(Float, default=0.0)
    unit: Mapped[str] = mapped_column(String(20))
    price_per_unit: Mapped[float] = mapped_column(Float)
    is_organic: Mapped[bool] = mapped_column(Boolean, default=False)  # self-declared
    harvest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Stock location (can differ from the farm's own address)
    address_text: Mapped[str] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(80), index=True)
    district: Mapped[str] = mapped_column(String(80), index=True)
    province: Mapped[str] = mapped_column(String(80))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    origin_tag: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), default=ListingStatus.ACTIVE, index=True)
    # Every new listing waits for admin approval before buyers can see it.
    approval_status: Mapped[str] = mapped_column(String(20), default=Approval.PENDING, index=True)
    approval_note: Mapped[str | None] = mapped_column(String(255), nullable=True)  # reason when rejected
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    farm = relationship("FarmProfile", back_populates="listings")
    product = relationship("Product")

    @property
    def available_qty(self) -> float:
        return max(self.total_qty - self.reserved_qty - self.sold_qty, 0.0)

    @property
    def product_name(self) -> str:
        return self.product.name
